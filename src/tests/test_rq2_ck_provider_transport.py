"""RQ2 live C/K integration gate, with fake SDK *inside the tests only*.

The production RELEASE_SHA256 is None. These tests patch a synthetic release
hash and monkeypatch the provider factory. NO real API, GT, Market or scoring
is used. They validate the genuine claim -> provider transport -> recorder
path and persistent token receipt before preregistration.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

import evaluation.rq2_ck_provider_transport as transport
import test_rq2_claim_recorder_end_to_end as fixtures
import test_rq2_output_contracts as contract_fixtures
import test_rq2_stage_binding as binding_fixtures
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_dryrun_plan import DISCOVERY, TEST, HARNESSES, MAX_TOOL_ROUNDS
from evaluation.rq2_toolfree_fake_transport import (
    PREFREEZE_C_SYSTEM_SHA256, PREFREEZE_K_SYSTEM_SHA256,
)

MODEL = fixtures.MODEL
USAGE = {"input_tokens": 120, "output_tokens": 25, "total_tokens": 145}


class InMemoryChat:
    def __init__(self, content, *, usage=USAGE, tool_calls=None):
        self.calls = 0
        self.content = content
        self.usage = usage
        self.tool_calls = tool_calls or []
        self.messages = None

    def bind_tools(self, tools):
        raise AssertionError("C/K must NOT bind tools")

    def invoke(self, messages):
        self.calls += 1
        self.messages = messages
        assert len(messages) == 2
        assert type(messages[0]) is SystemMessage
        assert type(messages[1]) is HumanMessage
        return AIMessage(
            content=self.content,
            usage_metadata=self.usage,
            tool_calls=self.tool_calls,
            response_metadata={
                "finish_reason": "stop", "model_name": MODEL,
            },
        )


class InMemoryErrorChat:
    def __init__(self):
        self.calls = 0
    def invoke(self, messages):
        self.calls += 1
        raise TimeoutError("fake SECRET_CREDENTIAL must never persist")


class RQ2ActualCKProviderAdapterOfflineTests(unittest.TestCase):
    def setUp(self):
        parent = fixtures.RQ2ClaimRecorderEndToEndTests(
            methodName="test_three_claims_three_artifacts_and_restart"
        )
        parent.setUp()
        self.addCleanup(parent.doCleanups)
        self.parent = parent
        self.root = parent.root
        self.recorded_d = False

        # Release exists ONLY in this isolated fake testcase and is trusted
        # only by patching RELEASE_SHA256 in the test's local process.
        release = {
            "status": "SCIENTIFIC_DISCOVERY_RELEASE",
            "test_unlocked": False,
            "enable_discovery_CK": True,
            "retry_policy": "NO_AUTOMATIC_RETRY",
            "model_ids": {
                x: CANDIDATE_MODELS[x]["model_id"] for x in CANDIDATE_MODELS
            },
            "C_K_tool_calls_allowed": False,
            "budget_limit_usd": None,
            "D_output_contract_mode": "v2_enforce",
            "D_variant_scheme": "current",
            "D_max_tool_rounds": MAX_TOOL_ROUNDS,
            "D_recursion_limit": 30,
            "harnesses": list(HARNESSES),
            "discovery_case_ids": list(DISCOVERY),
            "test_case_ids": list(TEST),
            "C_system_prompt_sha256": PREFREEZE_C_SYSTEM_SHA256,
            "K_system_prompt_sha256": PREFREEZE_K_SYSTEM_SHA256,
            "plan_preview_sha256": parent.plan["preview_sha256"],
            "source_manifest_sha256": parent.plan["manifest_sha256"],
            "source_split_sha256": parent.plan["split_sha256"],
        }
        release_path = (
            self.root / "data/rq2" / transport.RELEASE_FILENAME
        )
        release_path.parent.mkdir(parents=True, exist_ok=True)
        release_path.write_bytes(json.dumps(release).encode("utf-8"))
        self.release_path = release_path
        self.release_hash = hashlib.sha256(release_path.read_bytes()).hexdigest()
        self.release_patch = patch.object(
            transport, "RELEASE_SHA256", self.release_hash
        )
        self.release_patch.start()
        self.addCleanup(self.release_patch.stop)

    def d(self):
        self.parent.claim("D")
        self.parent.recorder.record_d(
            stage_id=self.parent.sid("D"), model_id_proposed=MODEL,
            diagnostic_run=self.parent.diagnostic(
                output_contract_mode="v2_enforce"
            ),
        )
        self.recorded_d = True

    def run(self, stage, model):
        with patch.object(
            transport, "crea_modello", return_value=model
        ) as factory:
            result = transport.run_one_claimed_ck(
                data_dir=self.root, stage_id=self.parent.sid(stage),
                confirm_paid_api=True,
            )
        factory.assert_called_once_with("anthropic", MODEL)
        return result

    def test_release_with_wrong_D_mode_is_refused_even_if_sha_matches(self):
        self.d()
        data = json.loads(self.release_path.read_text(encoding="utf-8"))
        data["D_output_contract_mode"] = "legacy"
        self.release_path.write_bytes(json.dumps(data).encode("utf-8"))
        bad_hash = hashlib.sha256(self.release_path.read_bytes()).hexdigest()
        with patch.object(transport, "RELEASE_SHA256", bad_hash):
            with patch.object(transport, "crea_modello") as factory:
                with self.assertRaisesRegex(
                    transport.RQ2LiveCKBlocked, "mandatory safeguards"
                ):
                    transport.run_one_claimed_ck(
                        data_dir=self.root, stage_id=self.parent.sid("C"),
                        confirm_paid_api=True,
                    )
                factory.assert_not_called()

    def test_confirmation_required_before_source_or_provider(self):
        with patch.object(
            transport, "crea_modello",
            side_effect=AssertionError("NO SDK"),
        ):
            with self.assertRaisesRegex(
                transport.RQ2LiveCKBlocked, "confirmation required"
            ):
                transport.run_one_claimed_ck(
                    data_dir=self.root, stage_id=self.parent.sid("C"),
                )
        self.assertFalse(self.parent.journal.root.exists())

    def test_release_hash_must_match_exact_bytes(self):
        self.d()
        self.release_path.write_bytes(self.release_path.read_bytes() + b"\n")
        with patch.object(transport, "crea_modello") as factory:
            with self.assertRaisesRegex(
                transport.RQ2LiveCKBlocked, "release bytes changed"
            ):
                transport.run_one_claimed_ck(
                    data_dir=self.root, stage_id=self.parent.sid("C"),
                    confirm_paid_api=True,
                )
            factory.assert_not_called()
        self.assertEqual(self.parent.journal.audit_restart()["claims"], 1)

    def test_live_gate_fails_without_pinned_release_even_if_confirmed(self):
        self.d()
        with patch.object(transport, "RELEASE_SHA256", None):
            with patch.object(transport, "crea_modello") as factory:
                with self.assertRaisesRegex(
                    transport.RQ2LiveCKBlocked, "not frozen"
                ):
                    transport.run_one_claimed_ck(
                        data_dir=self.root, stage_id=self.parent.sid("C"),
                        confirm_paid_api=True,
                    )
                factory.assert_not_called()
        self.assertEqual(self.parent.journal.audit_restart()["claims"], 1)

    def test_missing_d_blocks_C_without_sdk_or_claim(self):
        with patch.object(transport, "crea_modello") as factory:
            with self.assertRaisesRegex(
                transport.RQ2LiveCKBlocked, "Missing valid"
            ):
                transport.run_one_claimed_ck(
                    data_dir=self.root, stage_id=self.parent.sid("C"),
                    confirm_paid_api=True,
                )
            factory.assert_not_called()
        self.assertFalse(self.parent.journal.root.exists())

    def test_stage_test_is_not_accepted_even_with_test_release_mock(self):
        self.d()
        sid = (
            "rq2_dryrun_workflow_preview_v0:"
            "cloudbed-1_q000:sonnet:A1:C"
        )
        with patch.object(transport, "crea_modello") as factory:
            with self.assertRaisesRegex(transport.RQ2LiveCKBlocked,
                                        "Only discovery"):
                transport.run_one_claimed_ck(
                    data_dir=self.root, stage_id=sid,
                    confirm_paid_api=True,
                )
            factory.assert_not_called()

    def test_one_c_api_simulation_persists_exact_usage_and_model(self):
        self.d()
        chat = InMemoryChat(binding_fixtures.cause())
        result = self.run("C", chat)
        self.assertEqual(chat.calls, 1)
        self.assertEqual(result["status"], "RECORDED_COMPLETE")
        self.assertEqual(result["provider_attempts"], 1)
        self.assertEqual(result["usage"]["total_tokens"], 145)
        self.assertIsNone(result["financial_cost_ceiling"])
        receipt = self.parent.recorder.store.load_discovery_stage(
            stage_id=self.parent.sid("C")
        )["artifact"]["transport_receipt"]
        self.assertEqual(receipt["model_id"], MODEL)
        self.assertEqual(receipt["api_attempts"], 1)
        self.assertEqual(receipt["usage"]["input_tokens"], 120)
        self.assertEqual(receipt["usage"]["output_tokens"], 25)
        self.assertTrue(receipt["usage"]["complete"])
        self.assertFalse(receipt["tools_enabled"])
        self.assertFalse(receipt["is_synthetic"])  # transport format, SDK is patched

    def test_one_k_after_c_persists_real_adapter_receipt(self):
        self.d()
        self.run("C", InMemoryChat(binding_fixtures.cause()))
        self.run("K", InMemoryChat(
            json.dumps(contract_fixtures.RQ2OutputContractsTests.rule())
        ))
        audit = self.parent.journal.audit_restart()
        self.assertEqual(audit["claims"], 3)
        self.assertEqual(audit["finished_with_matching_result"], 3)
        self.assertEqual(audit["unresolved_manual_review"], 0)
        k = self.parent.recorder.store.load_discovery_stage(
            stage_id=self.parent.sid("K")
        )
        self.assertEqual(k["status"], "RECORDED_COMPLETE")
        self.assertTrue(k["artifact"]["transport_receipt"]["usage"]["complete"])
        self.assertFalse(k["artifact"]["scientific_freeze"])

    def test_provider_error_does_not_save_exception_text_or_retry(self):
        self.d()
        chat = InMemoryErrorChat()
        result = self.run("C", chat)
        self.assertEqual(chat.calls, 1)
        self.assertEqual(result["status"], "PROVIDER_ERROR")
        self.assertEqual(result["provider_attempts"], 1)
        c = self.parent.recorder.store.load_discovery_stage(
            stage_id=self.parent.sid("C")
        )
        self.assertIn("TimeoutError", c["artifact"]["provider_error"])
        self.assertNotIn("SECRET_CREDENTIAL", str(c))
        self.assertFalse(c["artifact"]["transport_receipt"]["usage"]["complete"])

    def test_response_invalid_json_kept_and_usage_still_saved(self):
        self.d()
        self.run("C", InMemoryChat("NOT JSON"))
        c = self.parent.recorder.store.load_discovery_stage(
            stage_id=self.parent.sid("C")
        )
        self.assertEqual(c["status"], "INVALID_OUTPUT")
        self.assertEqual(c["artifact"]["raw_response"], "NOT JSON")
        self.assertEqual(c["artifact"]["transport_receipt"]["api_attempts"], 1)
        self.assertEqual(c["artifact"]["transport_receipt"]["usage"]["total_tokens"], 145)

    def test_tool_attempt_refused_without_dispatching_tool(self):
        self.d()
        self.run("C", InMemoryChat(
            "", tool_calls=[{
                "name": "tool_get_node_metrics", "args": {},
                "id": "must-not-execute",
            }]
        ))
        c = self.parent.recorder.store.load_discovery_stage(
            stage_id=self.parent.sid("C")
        )
        self.assertEqual(c["status"], "PROVIDER_ERROR")
        self.assertIn("ToolCallsForbidden", c["artifact"]["provider_error"])
        self.assertEqual(self.parent.journal.audit_restart()["claims"], 2)

    def test_missing_usage_preserved_null(self):
        self.d()
        self.run("C", InMemoryChat(binding_fixtures.cause(), usage=None))
        c = self.parent.recorder.store.load_discovery_stage(
            stage_id=self.parent.sid("C")
        )
        receipt = c["artifact"]["transport_receipt"]
        self.assertFalse(receipt["usage"]["complete"])
        self.assertIsNone(receipt["usage"]["input_tokens"])

    def test_duplicate_c_run_blocked_before_second_factory(self):
        self.d()
        self.run("C", InMemoryChat(binding_fixtures.cause()))
        with patch.object(transport, "crea_modello") as factory:
            with self.assertRaises(transport.RQ2LiveCKBlocked):
                transport.run_one_claimed_ck(
                    data_dir=self.root, stage_id=self.parent.sid("C"),
                    confirm_paid_api=True,
                )
            factory.assert_not_called()

    def test_claim_exists_before_factory_is_called(self):
        self.d()
        observed = []
        chat = InMemoryChat(binding_fixtures.cause())
        def factory(provider, model_name):
            observed.append(self.parent.journal._read_claim(
                self.parent.sid("C")
            ) is not None)
            return chat
        with patch.object(transport, "crea_modello", side_effect=factory):
            transport.run_one_claimed_ck(
                data_dir=self.root, stage_id=self.parent.sid("C"),
                confirm_paid_api=True,
            )
        self.assertEqual(observed, [True])

    def test_bogus_usage_cannot_be_persisted_as_verified(self):
        self.d()
        bogus = {"input_tokens": 10, "output_tokens": 10, "total_tokens": 99}
        self.run("C", InMemoryChat(binding_fixtures.cause(), usage=bogus))
        c = self.parent.recorder.store.load_discovery_stage(
            stage_id=self.parent.sid("C")
        )
        self.assertFalse(c["artifact"]["transport_receipt"]["usage"]["complete"])


if __name__ == "__main__":
    unittest.main()
