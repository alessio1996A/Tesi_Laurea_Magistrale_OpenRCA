"""G4K: actual live-capable stage path, with SDK/HTTP strictly mocked.

No real release, API, GT, Market or user approval. LIVE_API_ENABLED
is patched True ONLY inside a TemporaryDirectory unittest and both
provider functions are separately mocked. Tests never grant permission
for a real stage. These are synthetic integration tests.
"""
from __future__ import annotations

import csv
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluation.rq2_v2_unified_live_dispatcher as subject
import evaluation.rq2_v2_unified_scientific_ledger as ledger_mod
from evaluation.rq2_probe_adapter import CAUSE_SYSTEM, RULE_SYSTEM
from evaluation.rq2_v2_unified_discovery_plan import DISCOVERY, TEST
from evaluation.rq2_v2_unified_scientific_release_contract import (
    canonical_release, release_digest,
)
from evaluation.rq2_v2_unified_release_blueprint import build_unified_release_blueprint
from evaluation.rq2_v2_unified_scientific_ledger import UnifiedScientificLedger
from evaluation.rq2_v2_unified_live_dispatcher import (
    RQ2V2LiveDispatchBlocked, run_one_claimed_unified_stage,
)
from test_rq2_v2_unified_provider_result_adapter_offline import (
    run as fake_d, ck_call,
)
from test_rq2_v2_unified_scientific_release_contract_offline import (
    FAKE_COMMIT, source_fixture, release_fixture,
)
from test_rq2_v2_unified_live_stage_preflight_offline import (
    CSV_HEADER, FAKE_INSTRUCTION,
)
from test_rq2_v2_unified_scientific_ledger_offline import sid
from test_rq2_v2_unified_synthetic_journal import cause, rule

TEST_ONLY_APPROVAL = "SYNTHETIC_G4K_FAKE_TRANSPORT_NOT_USER_APPROVAL"


class UnifiedLiveMockDispatcherTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(
            prefix="rq2_v2_g4k_gate_mock_"
        )
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "fake_data"
        self.repo = self.root / "fake_repo"
        self.data.mkdir()
        (self.repo / "src").mkdir(parents=True)

        source = source_fixture()
        source["C_system_prompt_sha256"] = hashlib.sha256(
            CAUSE_SYSTEM.encode("utf-8"),
        ).hexdigest()
        source["K_system_prompt_sha256"] = hashlib.sha256(
            RULE_SYSTEM.encode("utf-8"),
        ).hexdigest()
        blueprint = build_unified_release_blueprint(source_preview=source)
        release = release_fixture(source, blueprint)
        release["approval_reference"] = TEST_ONLY_APPROVAL
        self.release = release
        self.sha = release_digest(release)
        path = self.data / ledger_mod.RELEASE_FILE
        path.parent.mkdir(parents=True)
        path.write_bytes(canonical_release(release))
        self.release_path = path

        processed = self.data / "data/processed"
        processed.mkdir(parents=True)
        with (processed / "benchmark_inputs_market.csv").open(
            "w", newline="", encoding="utf-8",
        ) as handle:
            w = csv.writer(handle)
            w.writerow(CSV_HEADER)
            w.writerow([
                DISCOVERY[0], FAKE_INSTRUCTION, "1", "cloudbed-1",
                1760000000, 1760000600, 32,
            ])
        self._call_count = {"d": 0, "ck": 0}
        p_git = patch.object(
            ledger_mod, "_repository_commit", return_value=(FAKE_COMMIT, ""),
        )
        p_source = patch.object(
            ledger_mod, "preview_unified_source_bound", return_value=source,
        )
        p_live = patch.object(subject, "LIVE_API_ENABLED", True)
        for p in (p_git, p_source, p_live):
            p.start()
            self.addCleanup(p.stop)

    def dispatch(self, stage="D", *, model="gemini", harness="A0",
                 case=None, approved_id=None, approved_ref=TEST_ONLY_APPROVAL,
                 confirm=True):
        stage_id = sid(model, harness, stage, case=case)
        return run_one_claimed_unified_stage(
            data_dir=self.data, repo_dir=self.repo,
            stage_id=stage_id, expected_commit=FAKE_COMMIT,
            approved_release_sha256=self.sha,
            external_approval_reference=approved_ref,
            approved_stage_id=stage_id if approved_id is None else approved_id,
            confirm_paid_api=confirm,
        )

    def real_ledger(self):
        return UnifiedScientificLedger(
            data_dir=self.data, repo_dir=self.repo,
            expected_commit=FAKE_COMMIT, approved_release_sha256=self.sha,
        )

    def _d_with_mock(self, *, model="gemini", harness="A0",
                     answer=None, factory_error=False):
        fake_llm = object()
        def fake_runner(config, *, llm, verbose, salva):
            self.assertIs(llm, fake_llm)
            self.assertFalse(verbose)
            self.assertFalse(salva)
            self.assertEqual(config.output_contract_mode, "v2_enforce")
            self.assertEqual(config.variant_scheme, "current")
            self.assertEqual(config.case_id, DISCOVERY[0])
            self.assertEqual(config.max_tool_rounds, 6)
            # A create-only claim MUST exist before any runner action.
            self.assertIsNotNone(
                self.real_ledger().load_claim(
                    stage_id=sid(model, harness, "D"),
                )
            )
            self._call_count["d"] += 1
            return fake_d(model, harness) if answer is None else answer
        with (
            patch.object(
                subject, "crea_modello_rq2",
                side_effect=(ImportError("MOCK") if factory_error else None),
                return_value=(None if factory_error else fake_llm),
            ) as factory,
            patch.object(subject, "run_experiment", side_effect=fake_runner) as runner,
        ):
            receipt = self.dispatch(model=model, harness=harness)
        factory.assert_called_once()
        if factory_error:
            runner.assert_not_called()
        else:
            runner.assert_called_once()
        return receipt

    def _ck_with_mock(self, stage, *, model="gemini", harness="A0",
                      raw=None, provider_error=None,
                      missing_usage=False):
        if raw is None and provider_error is None:
            raw = cause() if stage == "C" else rule()
        value = ck_call(raw, error=provider_error)
        if provider_error is not None:
            value["raw_response"] = None
        if missing_usage:
            value["usage"].update({
                "complete": False,
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
            })
        from langchain_core.messages import HumanMessage, SystemMessage
        def fake_ck(provider, model_id, messages):
            self.assertEqual(provider, "google" if model=="gemini" else "anthropic")
            self.assertIsInstance(messages[0], SystemMessage)
            self.assertIsInstance(messages[1], HumanMessage)
            self.assertEqual(len(messages), 2)
            self.assertIsNotNone(self.real_ledger().load_claim(
                stage_id=sid(model, harness, stage),
            ))
            self._call_count["ck"] += 1
            return value
        with patch.object(
            subject, "_call_ck_model", side_effect=fake_ck,
        ) as transport:
            receipt = self.dispatch(stage, model=model, harness=harness)
        transport.assert_called_once()
        return receipt

    def test_live_gate_is_disabled_by_default_without_sdk(self):
        with patch.object(subject, "LIVE_API_ENABLED", False), (
            patch.object(subject, "crea_modello_rq2") as factory
        ):
            with self.assertRaisesRegex(
                RQ2V2LiveDispatchBlocked, "disabled",
            ):
                self.dispatch(confirm=True)
            factory.assert_not_called()
        self.assertFalse((self.data / ledger_mod.CLAIMS).exists())

    def test_missing_confirmation_rejected_before_ledger(self):
        with self.assertRaisesRegex(
            RQ2V2LiveDispatchBlocked, "approval required",
        ):
            self.dispatch(confirm=False)
        self.assertFalse((self.data / ledger_mod.CLAIMS).exists())

    def test_explicit_wrong_stage_approval_rejected(self):
        with self.assertRaises(RQ2V2LiveDispatchBlocked):
            self.dispatch(approved_id=sid("haiku", "A0", "D"))
        self.assertFalse((self.data / ledger_mod.CLAIMS).exists())

    def test_synthetic_approval_ref_is_forbidden(self):
        with self.assertRaises(RQ2V2LiveDispatchBlocked):
            self.dispatch(approved_ref="SYNTHETIC_APPROVAL_NOT_REAL")
        self.assertFalse((self.data / ledger_mod.CLAIMS).exists())

    def test_wrong_external_release_sha_rejected(self):
        self.sha = "0" * 64
        with self.assertRaises(Exception):
            self.dispatch()
        self.assertFalse((self.data / ledger_mod.CLAIMS).exists())

    def test_unapproved_test_ood_stage_denied(self):
        with self.assertRaises(Exception):
            self.dispatch(case=TEST[0])
        self.assertFalse((self.data / ledger_mod.CLAIMS).exists())

    def test_all_three_d_models_harness_ids_recorded_with_no_retries(self):
        for model, harness in (
            ("gemini", "A0"),
            ("sonnet", "A1_8R_Planning"),
            ("haiku", "A1_PAVE"),
        ):
            with self.subTest(model=model, harness=harness):
                receipt = self._d_with_mock(model=model, harness=harness)
                self.assertEqual(receipt["status"], "RECORDED_COMPLETE")
                self.assertEqual(receipt["model_id"], {
                    "gemini": "gemini-3.5-flash-lite",
                    "sonnet": "claude-sonnet-5-5",
                    "haiku": "claude-haiku-5-5",
                }[model])
                self.assertEqual(
                    receipt["reported_usage"]["cost_estimate_usd_not_invoice"],
                    "UNKNOWN",
                )
                self.assertFalse(receipt["usd_hard_cap_guaranteed"])
        audit = self.real_ledger().audit_restart()
        self.assertEqual((audit["claims"], audit["records"]), (3, 3))

    def test_d_then_c_then_k_three_separate_mock_provider_invocations(self):
        self._d_with_mock()
        c = self._ck_with_mock("C")
        k = self._ck_with_mock("K")
        self.assertEqual([c["status"], k["status"]],
                         ["RECORDED_COMPLETE"] * 2)
        self.assertEqual(self._call_count, {"d": 1, "ck": 2})
        audit = self.real_ledger().audit_restart()
        self.assertEqual((audit["claims"], audit["records"]), (3, 3))
        self.assertEqual(audit["orphan_claims"], 0)

    def test_invalid_d_is_archived_and_ck_blocked_without_requests(self):
        self._d_with_mock(answer=fake_d(json_valid=False))
        self.assertEqual(
            self.real_ledger().load_record(stage_id=sid(stage="C"))["status"],
            "BLOCKED_DEPENDENCY",
        )
        self.assertEqual(self.real_ledger().audit_restart()["claims"], 1)
        with self.assertRaises(Exception):
            self.dispatch("C")

    def test_invalid_c_is_archived_and_k_blocked(self):
        self._d_with_mock()
        result = self._ck_with_mock("C", raw="invalid not JSON")
        self.assertEqual(result["status"], "INVALID_OUTPUT")
        self.assertEqual(self.real_ledger().audit_restart()["records"], 3)
        self.assertEqual(
            self.real_ledger().load_record(stage_id=sid(stage="K"))["status"],
            "BLOCKED_DEPENDENCY",
        )

    def test_ck_provider_timeout_is_recorded_with_unknown_cost(self):
        self._d_with_mock()
        receipt = self._ck_with_mock(
            "C", provider_error="PROVIDER_ERROR:TimeoutError:HTTP_503",
            missing_usage=True,
        )
        self.assertEqual(receipt["status"], "PROVIDER_ERROR")
        self.assertEqual(receipt["reported_usage"]["observed_model_requests"], 1)
        self.assertFalse(receipt["reported_usage"]["usage_complete"])
        self.assertEqual(receipt["reported_usage"]["cost_estimate_usd_not_invoice"],
                         "UNKNOWN")

    def test_d_sdk_construction_error_is_pre_request_no_retry(self):
        # This code path should never call the RQ1 runner.
        with (
            patch.object(
                subject, "crea_modello_rq2", side_effect=ImportError("mock"),
            ),
            patch.object(subject, "run_experiment") as runner,
        ):
            receipt = self.dispatch()
            runner.assert_not_called()
        self.assertEqual(receipt["status"], "PROVIDER_ERROR")
        self.assertEqual(receipt["reported_usage"]["observed_model_requests"], 0)
        self.assertEqual(self.real_ledger().audit_restart()["records"], 3)

    def test_duplicate_d_attempt_cannot_make_second_provider_call(self):
        self._d_with_mock()
        with patch.object(subject, "crea_modello_rq2") as factory:
            with self.assertRaises(Exception):
                self.dispatch()
            factory.assert_not_called()
        self.assertEqual(self.real_ledger().audit_restart()["records"], 1)

    def test_crash_after_claim_remains_orphan(self):
        with (
            patch.object(subject, "crea_modello_rq2", return_value=object()),
            patch.object(
                subject, "run_experiment", side_effect=RuntimeError("crash"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "crash"):
                self.dispatch()
        self.assertEqual(self.real_ledger().audit_restart()["orphan_claims"], 1)

    def test_d_incomplete_usage_without_token_invoice_is_preserved(self):
        answer = fake_d()
        answer["metrics"]["token_usage_complete"] = False
        answer["metrics"]["input_tokens"] = None
        answer["metrics"]["output_tokens"] = 12
        answer["metrics"]["total_tokens"] = None
        receipt = self._d_with_mock(answer=answer)
        self.assertEqual(receipt["status"], "RECORDED_COMPLETE")
        self.assertFalse(receipt["reported_usage"]["usage_complete"])
        self.assertEqual(receipt["reported_usage"]["output_tokens_observed"], 12)

    def test_real_release_reference_mismatch_does_not_create_claim(self):
        # Change only fake release approval, recompute synthetic digest;
        # a caller's different reference must be rejected before claims.
        self.release["approval_reference"] = "WRONG_RELEASE_REFERENCE_FAKE"
        self.sha = release_digest(self.release)
        self.release_path.write_bytes(canonical_release(self.release))
        with self.assertRaises(RQ2V2LiveDispatchBlocked):
            self.dispatch()
        self.assertFalse((self.data / ledger_mod.CLAIMS).exists())

    def test_sdk_not_instantiated_until_after_claim(self):
        def spy_factory(provider, model):
            self.assertIsNotNone(
                self.real_ledger().load_claim(stage_id=sid()),
            )
            return object()
        with (
            patch.object(subject, "crea_modello_rq2", side_effect=spy_factory),
            patch.object(subject, "run_experiment", return_value=fake_d()),
        ):
            self.dispatch()
        self.assertEqual(self.real_ledger().audit_restart()["records"], 1)

    def test_ck_messages_are_source_bound_not_caller_supplied(self):
        self._d_with_mock()
        with patch.object(subject, "_call_ck_model") as transport:
            transport.return_value = ck_call(cause())
            result = self.dispatch("C")
            args = transport.call_args.args
            messages = args[2]
            self.assertIn("UNTRUSTED OBSERVED DATA", messages[1].content)
            self.assertEqual(messages[0].content, CAUSE_SYSTEM)
        self.assertEqual(result["status"], "RECORDED_COMPLETE")


if __name__ == "__main__":
    unittest.main()
