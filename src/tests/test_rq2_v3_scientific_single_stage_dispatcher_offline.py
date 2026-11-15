"""Single-stage V3 dispatcher contract tests: fake ledger/providers ONLY.

No real V3 scientific release exists and the unmocked runtime gate is NO-GO.
Every fake executes in memory; there are NO SDK calls, paid requests,
credentials, persisted scientific results or GT reads.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import evaluation.rq2_v3_scientific_single_stage_dispatcher as dispatch
from evaluation.rq2_probe_adapter import CAUSE_SYSTEM, RULE_SYSTEM
from evaluation.rq2_v3_scientific_ledger import V3ScientificLedgerBlocked
from evaluation.rq2_v3_unified_gtfree_discovery_plan import (
    VERSION as PROTOCOL, build_offline_v3_discovery_plan,
)

PIN = "a" * 40
RELEASE = "b" * 64
PACKAGE_SHA = "c" * 64
PLAN = build_offline_v3_discovery_plan()
ROWS = {item["stage_id"]: item for item in PLAN["entries"]}


def sid(stage="D", harness="A0", model="gemini", case="cloudbed-1_q032"):
    return f"{PROTOCOL}:{case}:{model}:{harness}:{stage}"


def auth(stage_id):
    return {
        "scope": "ONE_V3_STAGE_CLAIM_ONLY",
        "stage_id": stage_id,
        "model_id": ROWS[stage_id]["model_id"],
        "source_commit": PIN,
        "release_sha256": RELEASE,
        "approval_reference": "TEST_APPROVAL_ONLY_V3",
        "stage_budget_usd": "0.10",
    }


def package(stage="C"):
    prompt = CAUSE_SYSTEM if stage == "C" else RULE_SYSTEM
    return {
        "stage": stage,
        "system_prompt_sha256":
            hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "package_sha256": PACKAGE_SHA,
        "ready_for_api": False,
        "model_api_calls": 0,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "synthetic evidence only"},
        ],
    }


class FakeLedger:
    def __init__(self, trace):
        self.trace = trace
        self.data = Path("/tmp/FAKE_RQ2_V3_ONLY")
        self.repo = Path("/tmp/FAKE_RQ2_V3_SOURCE_ONLY")
        self.plan = PLAN
        self.claims = {}
        self.records = {}
        self.last_receipt = None
        self.claim_shas = {}
        self.source_sha = "d" * 64

    def _row(self, stage_id, model_id=None):
        self.trace.append("lookup")
        row = ROWS.get(stage_id)
        if row is None or (model_id is not None and row["model_id"] != model_id):
            raise V3ScientificLedgerBlocked("Unknown/OOD stage")
        return row

    def load_claim(self, *, stage_id):
        return self.claims.get(stage_id)

    def load_record(self, *, stage_id):
        return self.records.get(stage_id)

    def audit_restart(self):
        return {
            "orphan_claims": len(set(self.claims) - set(self.records)),
            "can_execute_api": False,
            "can_run_ood_test": False,
        }

    def claim_stage(self, *, stage_id, model_id, stage_authorization):
        self.trace.append("claim")
        if stage_id in self.claims or stage_id in self.records:
            raise V3ScientificLedgerBlocked("No retry")
        value = {"claim_sha256": "e" * 64}
        self.claims[stage_id] = value
        return value

    def record_stage(self, *, stage_id, model_id,
                     blocked=False, receipt=None, expected_claim_sha256=None):
        self.trace.append("blocked" if blocked else "record")
        if stage_id in self.records:
            raise V3ScientificLedgerBlocked("No overwrite")
        status = "BLOCKED_DEPENDENCY" if blocked else receipt["status"]
        self.records[stage_id] = {
            "status": status,
            "artifact": {} if blocked else receipt.get("artifact", {}),
            "record_sha256": "f" * 64,
        }
        self.last_receipt = receipt
        return {"status": status, "record_sha256": "f" * 64}


class V3SingleStageDispatcherOfflineTests(unittest.TestCase):
    def setUp(self):
        self.trace = []
        self.ledger = FakeLedger(self.trace)
        self.patches = [
            patch.object(dispatch, "V3ScientificLedger", return_value=self.ledger),
            patch.object(dispatch, "_source_instruction",
                         return_value="synthetic instruction"),
            patch.object(dispatch, "_read", return_value={
                "C_system_prompt_sha256":
                    hashlib.sha256(CAUSE_SYSTEM.encode("utf-8")).hexdigest(),
                "K_system_prompt_sha256":
                    hashlib.sha256(RULE_SYSTEM.encode("utf-8")).hexdigest(),
            }),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def run_one(self, stage_id=None, *, approve=True, authorization=None):
        stage_id = sid() if stage_id is None else stage_id
        return dispatch.run_one_v3_stage(
            data_dir=self.ledger.data, repo_dir=self.ledger.repo,
            stage_id=stage_id, approved_stage_id=stage_id,
            expected_commit=PIN, approved_release_sha256=RELEASE,
            stage_authorization=(
                auth(stage_id) if authorization is None else authorization
            ),
            confirm_paid_api=approve,
        )

    def parent_d(self, stage_id=sid()):
        self.ledger.records[stage_id] = {
            "status": "RECORDED_COMPLETE",
            "artifact": {"diagnostic_run": {"synthetic": True}},
            "record_sha256": "f" * 64,
        }

    def parent_c(self, stage_id=sid(stage="C")):
        self.ledger.records[stage_id] = {
            "status": "RECORDED_COMPLETE",
            "artifact": {"raw_response": "synthetic json"},
            "record_sha256": "e" * 64,
        }

    def test_default_flag_blocks_before_ledger_or_sdk(self):
        with patch.object(dispatch, "LIVE_API_ENABLED", False):
            with patch.object(dispatch, "_provider_once") as api:
                with self.assertRaises(dispatch.V3SingleStageDispatchBlocked):
                    self.run_one()
                api.assert_not_called()
        self.assertEqual(self.trace, [])

    def test_exact_opt_in_still_requires_paid_user_approval(self):
        with patch.object(dispatch, "LIVE_API_ENABLED", True):
            with patch.object(dispatch, "_provider_once") as api:
                with self.assertRaises(dispatch.V3SingleStageDispatchBlocked):
                    self.run_one(approve=False)
                api.assert_not_called()
        self.assertEqual(self.trace, [])

    def test_mismatched_stage_model_or_release_approval_rejected(self):
        for field, wrong in (
            ("stage_id", sid(harness="A1")),
            ("model_id", "gemini"),
            ("release_sha256", "0" * 64),
            ("stage_budget_usd", "-1.00"),
        ):
            with self.subTest(field=field):
                wrong_auth = auth(sid())
                wrong_auth[field] = wrong
                with patch.object(dispatch, "LIVE_API_ENABLED", True):
                    with self.assertRaises(
                        dispatch.V3SingleStageDispatchBlocked,
                    ):
                        self.run_one(authorization=wrong_auth)
        self.assertEqual(self.trace, [])

    def test_v2_ood_and_unknown_rejected_before_source(self):
        variants = (
            sid().replace(PROTOCOL, "rq2_v2_unified_five_harness_discovery_v0"),
            sid(case="cloudbed-2_q077"),
            sid(harness="NONEXISTENT"),
        )
        for bad in variants:
            with self.subTest(bad=bad):
                with patch.object(dispatch, "LIVE_API_ENABLED", True):
                    with self.assertRaises(
                        dispatch.V3SingleStageDispatchBlocked,
                    ):
                        dispatch.run_one_v3_stage(
                            data_dir=self.ledger.data, repo_dir=self.ledger.repo,
                            stage_id=bad, approved_stage_id=bad,
                            expected_commit=PIN, approved_release_sha256=RELEASE,
                            stage_authorization=auth(sid()),
                            confirm_paid_api=True,
                        )
        self.assertEqual(self.trace, [])

    def test_d_success_claim_first_then_one_provider_receipt(self):
        def synthetic_provider(**kwargs):
            self.assertIn(sid(), self.ledger.claims)
            self.trace.append("provider")
            return {"status": "RECORDED_COMPLETE", "artifact": {}}
        with (
            patch.object(dispatch, "LIVE_API_ENABLED", True),
            patch.object(dispatch, "_provider_once", side_effect=synthetic_provider)
                as provider,
        ):
            result = self.run_one()
        self.assertEqual(result["record_status"], "RECORDED_COMPLETE")
        self.assertEqual(result["claims_created"], 1)
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertEqual(provider.call_count, 1)
        self.assertLess(self.trace.index("claim"), self.trace.index("provider"))
        self.assertLess(self.trace.index("provider"), self.trace.index("record"))

    def test_d_invalid_blocks_c_and_k_without_more_claims(self):
        with (
            patch.object(dispatch, "LIVE_API_ENABLED", True),
            patch.object(dispatch, "_provider_once", return_value={
                "status": "INVALID_OUTPUT", "artifact": {},
            }) as provider,
        ):
            result = self.run_one()
        self.assertEqual(result["record_status"], "INVALID_OUTPUT")
        self.assertEqual(result["descendants_blocked"],
                         [sid(stage="C"), sid(stage="K")])
        self.assertEqual(len(self.ledger.claims), 1)
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(self.ledger.records[sid(stage="K")]["status"],
                         "BLOCKED_DEPENDENCY")

    def test_c_missing_d_blocks_before_claim(self):
        with (
            patch.object(dispatch, "LIVE_API_ENABLED", True),
            patch.object(dispatch, "_provider_once") as provider,
        ):
            with self.assertRaises(dispatch.V3SingleStageDispatchBlocked):
                self.run_one(sid(stage="C"))
            provider.assert_not_called()
        self.assertEqual(self.ledger.claims, {})

    def test_c_complete_provenance_bound_to_parent(self):
        self.parent_d()
        with (
            patch.object(dispatch, "LIVE_API_ENABLED", True),
            patch.object(dispatch, "prepare_cause_probe",
                         return_value=package("C")),
            patch.object(dispatch, "_provider_once", return_value={
                "status": "RECORDED_COMPLETE", "artifact": {},
            }) as provider,
        ):
            result = self.run_one(sid(stage="C"))
        self.assertEqual(result["stage"], "C")
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(provider.call_args.kwargs["diagnostic_run"],
                         {"synthetic": True})
        self.assertEqual(provider.call_args.kwargs["package"]["package_sha256"],
                         PACKAGE_SHA)

    def test_c_invalid_blocks_only_k(self):
        self.parent_d()
        with (
            patch.object(dispatch, "LIVE_API_ENABLED", True),
            patch.object(dispatch, "prepare_cause_probe",
                         return_value=package("C")),
            patch.object(dispatch, "_provider_once", return_value={
                "status": "INVALID_OUTPUT", "artifact": {},
            }),
        ):
            result = self.run_one(sid(stage="C"))
        self.assertEqual(result["descendants_blocked"], [sid(stage="K")])
        self.assertNotIn(sid(stage="K"), self.ledger.claims)

    def test_k_requires_both_valid_d_and_c(self):
        self.parent_d()
        with patch.object(dispatch, "LIVE_API_ENABLED", True):
            with self.assertRaises(dispatch.V3SingleStageDispatchBlocked):
                self.run_one(sid(stage="K"))
        self.assertEqual(self.ledger.claims, {})

    def test_k_prepares_only_discovery_rule_and_claims_one_stage(self):
        self.parent_d()
        self.parent_c()
        with (
            patch.object(dispatch, "LIVE_API_ENABLED", True),
            patch.object(dispatch, "prepare_candidate_rule",
                         return_value=package("K")) as prepare,
            patch.object(dispatch, "_provider_once", return_value={
                "status": "RECORDED_COMPLETE", "artifact": {},
            }),
        ):
            result = self.run_one(sid(stage="K"))
        self.assertEqual(result["stage"], "K")
        self.assertEqual(result["descendants_blocked"], [])
        self.assertEqual(prepare.call_args.kwargs["phase"], "discovery")
        self.assertEqual(prepare.call_args.kwargs["cause_raw_json"],
                         "synthetic json")

    def test_provider_exception_leaves_orphan_no_retry(self):
        with (
            patch.object(dispatch, "LIVE_API_ENABLED", True),
            patch.object(dispatch, "_provider_once",
                         side_effect=RuntimeError("synthetic interruption"))
                as provider,
        ):
            with self.assertRaisesRegex(RuntimeError, "synthetic interruption"):
                self.run_one()
            self.assertIn(sid(), self.ledger.claims)
            self.assertNotIn(sid(), self.ledger.records)
            with self.assertRaises(dispatch.V3SingleStageDispatchBlocked):
                self.run_one()
            self.assertEqual(provider.call_count, 1)

    def test_duplicate_record_blocks_before_provider(self):
        self.ledger.records[sid()] = {
            "status": "RECORDED_COMPLETE", "artifact": {},
            "record_sha256": "f" * 64,
        }
        with (
            patch.object(dispatch, "LIVE_API_ENABLED", True),
            patch.object(dispatch, "_provider_once") as provider,
        ):
            with self.assertRaises(dispatch.V3SingleStageDispatchBlocked):
                self.run_one()
            provider.assert_not_called()

    def test_bad_gt_free_manifest_blocks_before_claim(self):
        with (
            patch.object(dispatch, "LIVE_API_ENABLED", True),
            patch.object(dispatch, "_source_instruction",
                         side_effect=dispatch.UnifiedStagePreviewBlocked("no file")),
            patch.object(dispatch, "_provider_once") as provider,
        ):
            with self.assertRaises(dispatch.V3SingleStageDispatchBlocked):
                self.run_one()
            provider.assert_not_called()
        self.assertEqual(self.ledger.claims, {})

    def test_read_only_preview_uses_ledger_gate_and_no_claim(self):
        response = dispatch.preview_one_v3_stage(
            data_dir=self.ledger.data, repo_dir=self.ledger.repo,
            stage_id=sid(), expected_commit=PIN,
            approved_release_sha256=RELEASE,
        )
        self.assertEqual(response["status"], "V3_STAGE_PREPARED_NO_API")
        self.assertFalse(response["can_execute_api"])
        self.assertIsNone(response["prepared_package_sha256"])
        self.assertEqual(self.ledger.claims, {})

    def test_claim_failure_never_reaches_provider(self):
        with (
            patch.object(dispatch, "LIVE_API_ENABLED", True),
            patch.object(self.ledger, "claim_stage",
                         side_effect=V3ScientificLedgerBlocked("writer blocked")),
            patch.object(dispatch, "_provider_once") as provider,
        ):
            with self.assertRaises(V3ScientificLedgerBlocked):
                self.run_one()
            provider.assert_not_called()

    def test_d_adapter_runner_context_order_one_logical_run(self):
        class FakeCapture:
            def __init__(self, *, harness):
                self.harness = harness
            def __enter__(self):
                self_ = self
                self_.entered = True
                return self_
            def __exit__(self, exc_type, exc, tb):
                self.exited = True
                return False
            def build_receipt(self, result):
                assert self.exited
                return {"synthetic_captured": result}
        row = ROWS[sid()]
        config = MagicMock()
        with (
            patch.object(dispatch, "crea_modello_rq2", return_value="fake_llm")
                as factory,
            patch.object(dispatch, "V3DRunnerCapture", FakeCapture),
            patch.object(dispatch, "run_experiment",
                         return_value={"raw_response": "SYNTHETIC"})
                as experiment,
            patch.object(dispatch, "normalize_v3_d_capture",
                         return_value={"status": "RECORDED_COMPLETE"})
                as normalizer,
        ):
            response = dispatch._provider_once(
                row=row, config=config,
                diagnostic_run=None, package=None,
            )
        self.assertEqual(response["status"], "RECORDED_COMPLETE")
        factory.assert_called_once_with(row["model_provider"], row["model_id"])
        self.assertFalse(experiment.call_args.kwargs["salva"])
        self.assertEqual(normalizer.call_args.kwargs["captured"][
            "synthetic_captured"]["raw_response"], "SYNTHETIC")

    def test_ck_provider_transport_single_call_with_exact_messages(self):
        row = ROWS[sid(stage="C")]
        fake = {"api_attempts": 1}
        with (
            patch.object(dispatch, "one_ck_call_candidate", return_value=fake)
                as transport,
            patch.object(dispatch, "normalize_v3_ck_call",
                         return_value={"status": "RECORDED_COMPLETE"})
                as normalizer,
        ):
            response = dispatch._provider_once(
                row=row, config=MagicMock(),
                diagnostic_run={"synthetic": True}, package=package("C"),
            )
        self.assertEqual(response["status"], "RECORDED_COMPLETE")
        transport.assert_called_once()
        self.assertEqual(transport.call_args.args[:2],
                         (row["model_provider"], row["model_id"]))
        self.assertEqual(len(transport.call_args.args[2]), 2)
        self.assertEqual(normalizer.call_args.kwargs["call"], fake)


if __name__ == "__main__":
    unittest.main()
