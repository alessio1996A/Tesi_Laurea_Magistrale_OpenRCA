"""V4 dispatcher offline: consenso, singolo stage, claim-first, no retry.

NESSUNA credenziale, dati OpenRCA, SDK esterni o nuove release.
Per testare il percorso positivo si usano esclusivamente Mock di provider
e ledger sintetici; il gate reale V4 continua a richiedere release e prova.
"""
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from evaluation.rq2_v4_unified_gtfree_discovery_plan import (
    VERSION as PROTOCOL, build_offline_v4_discovery_plan,
)
import evaluation.rq2_v4_scientific_single_stage_dispatcher as dispatcher
from evaluation.rq2_v4_scientific_ledger import V4ScientificLedgerBlocked

PIN = "a" * 40
RELEASE = "b" * 64
STAGE = PROTOCOL + ":cloudbed-1_q032:gemini:A0:D"
ROW = next(
    r for r in build_offline_v4_discovery_plan()["entries"]
    if r["stage_id"] == STAGE
)


def authorization(*, stage_id=STAGE, model_id=None, budget="0.10"):
    return {
        "scope": "ONE_V4_STAGE_CLAIM_ONLY",
        "stage_id": stage_id,
        "model_id": ROW["model_id"] if model_id is None else model_id,
        "source_commit": PIN,
        "release_sha256": RELEASE,
        "approval_reference": "SYNTHETIC_V4_ONLY_NEVER_REAL",
        "stage_budget_usd": budget,
    }


def args(*, approved=STAGE, stage=STAGE, auth=None, confirm=True):
    return {
        "data_dir": None,
        "repo_dir": None,
        "stage_id": stage,
        "approved_stage_id": approved,
        "expected_commit": PIN,
        "approved_release_sha256": RELEASE,
        "stage_authorization": (
            authorization() if auth is None else auth
        ),
        "confirm_paid_api": confirm,
    }


class DispatcherAdmissionOfflineTests(unittest.TestCase):
    def test_default_opt_in_is_disabled(self):
        self.assertEqual(
            dispatcher.LIVE_OPT_IN_ENV,
            "OPENRCA_RQ2_V4_ENABLE_PAID_SINGLE_STAGE",
        )
        with patch.object(dispatcher, "LIVE_API_ENABLED", False):
            with self.assertRaises(dispatcher.V4SingleStageDispatchBlocked):
                dispatcher.run_one_v4_stage(**args())

    def test_missing_confirmation_is_no_go(self):
        with patch.object(dispatcher, "LIVE_API_ENABLED", True):
            with self.assertRaises(dispatcher.V4SingleStageDispatchBlocked):
                dispatcher._admission(
                    stage_id=STAGE, approved_stage_id=STAGE,
                    expected_commit=PIN, approved_release_sha256=RELEASE,
                    stage_authorization=authorization(),
                    confirm_paid_api=False,
                )

    def test_exact_stage_mismatch_is_no_go(self):
        with patch.object(dispatcher, "LIVE_API_ENABLED", True):
            with self.assertRaises(dispatcher.V4SingleStageDispatchBlocked):
                dispatcher._admission(
                    stage_id=STAGE,
                    approved_stage_id=STAGE[:-1] + "C",
                    expected_commit=PIN, approved_release_sha256=RELEASE,
                    stage_authorization=authorization(),
                    confirm_paid_api=True,
                )

    def test_wrong_model_cannot_take_another_model_budget(self):
        with patch.object(dispatcher, "LIVE_API_ENABLED", True):
            with self.assertRaises(dispatcher.V4SingleStageDispatchBlocked):
                dispatcher._admission(
                    stage_id=STAGE, approved_stage_id=STAGE,
                    expected_commit=PIN, approved_release_sha256=RELEASE,
                    stage_authorization=authorization(model_id="claude-haiku-5-5"),
                    confirm_paid_api=True,
                )

    def test_invalid_budget_and_wrong_scope_fail_closed(self):
        with patch.object(dispatcher, "LIVE_API_ENABLED", True):
            for bad_budget in ("0", "-1", "0.001", "NaN"):
                with self.subTest(budget=bad_budget):
                    with self.assertRaises(dispatcher.V4SingleStageDispatchBlocked):
                        dispatcher._admission(
                            stage_id=STAGE, approved_stage_id=STAGE,
                            expected_commit=PIN, approved_release_sha256=RELEASE,
                            stage_authorization=authorization(budget=bad_budget),
                            confirm_paid_api=True,
                        )
            auth = authorization()
            auth["scope"] = "GLOBAL_CAMPAIGN"
            with self.assertRaises(dispatcher.V4SingleStageDispatchBlocked):
                dispatcher._admission(
                    stage_id=STAGE, approved_stage_id=STAGE,
                    expected_commit=PIN, approved_release_sha256=RELEASE,
                    stage_authorization=auth, confirm_paid_api=True,
                )

    def test_v3_ids_and_ood_cases_rejected(self):
        old = STAGE.replace(PROTOCOL, "rq2_v3_unified_equal_ck_extraction_discovery_v0", 1)
        ood = build_offline_v4_discovery_plan()["ood_test_cases_locked"][0]
        future = PROTOCOL + ":" + ood + ":gemini:A0:D"
        with patch.object(dispatcher, "LIVE_API_ENABLED", True):
            for stage in (old, future):
                with self.subTest(stage=stage):
                    with self.assertRaises(dispatcher.V4SingleStageDispatchBlocked):
                        dispatcher._admission(
                            stage_id=stage, approved_stage_id=stage,
                            expected_commit=PIN, approved_release_sha256=RELEASE,
                            stage_authorization=authorization(stage_id=stage),
                            confirm_paid_api=True,
                        )

    def test_without_verified_release_no_claim_or_provider(self):
        with (
            patch.object(dispatcher, "LIVE_API_ENABLED", True),
            patch.object(
                dispatcher, "V4ScientificLedger",
                side_effect=V4ScientificLedgerBlocked("NO_V4_RELEASE"),
            ) as ledger,
            patch.object(dispatcher, "_provider_once") as provider,
        ):
            with self.assertRaises(V4ScientificLedgerBlocked):
                dispatcher.run_one_v4_stage(**args())
        ledger.assert_called_once()
        provider.assert_not_called()


class DispatcherExecutionOfflineTests(unittest.TestCase):
    def run_mocked(self, *, result_status="RECORDED_COMPLETE", fail_provider=False,
                   orphans=0):
        events = []
        ledger = Mock()
        ledger.claim_stage.side_effect = lambda **kw: (
            events.append("claim") or {"claim_sha256": "c" * 64}
        )
        ledger.record_stage.side_effect = lambda **kw: (
            events.append("record") or {
                "status": result_status,
                "record_sha256": "d" * 64,
            }
        )
        ledger.audit_restart.return_value = {"orphan_claims": orphans}

        def provider_once(**kwargs):
            events.append("provider")
            if fail_provider:
                raise RuntimeError("SYNTHETIC_PROVIDER_FAILURE")
            return {"synthetic": True}

        kwargs = {
            "data_dir": None,
            "repo_dir": None,
            "stage_id": STAGE,
            "approved_stage_id": STAGE,
            "expected_commit": PIN,
            "approved_release_sha256": RELEASE,
            "stage_authorization": authorization(),
            "confirm_paid_api": True,
        }
        with (
            patch.object(dispatcher, "LIVE_API_ENABLED", True),
            patch.object(dispatcher, "V4ScientificLedger", return_value=ledger),
            patch.object(
                dispatcher, "_prepare",
                return_value=(ROW, Mock(), None, None),
            ),
            patch.object(dispatcher, "_provider_once", side_effect=provider_once),
            patch.object(
                dispatcher, "_block_descendants",
                return_value=[
                    STAGE[:-1] + "C", STAGE[:-1] + "K",
                ],
            ) as blocked,
        ):
            if fail_provider or orphans:
                with self.assertRaises(RuntimeError):
                    dispatcher.run_one_v4_stage(**kwargs)
                result = None
            else:
                result = dispatcher.run_one_v4_stage(**kwargs)
        return events, ledger, blocked, result

    def test_one_successful_stage_claims_before_call_then_records(self):
        events, ledger, blocked, result = self.run_mocked()
        self.assertEqual(events, ["claim", "provider", "record"])
        self.assertEqual(result["status"], "V4_ONE_STAGE_RECORDED")
        self.assertEqual(result["record_status"], "RECORDED_COMPLETE")
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertEqual(result["claims_created"], 1)
        blocked.assert_not_called()
        ledger.claim_stage.assert_called_once()
        ledger.record_stage.assert_called_once()

    def test_invalid_d_blocks_c_and_k_without_more_provider_calls(self):
        events, ledger, blocked, result = self.run_mocked(
            result_status="INVALID_OUTPUT",
        )
        self.assertEqual(events, ["claim", "provider", "record"])
        self.assertEqual(result["record_status"], "INVALID_OUTPUT")
        self.assertEqual(result["descendants_blocked"], [
            STAGE[:-1] + "C", STAGE[:-1] + "K",
        ])
        blocked.assert_called_once()
        ledger.claim_stage.assert_called_once()

    def test_provider_error_after_claim_never_retries_or_records(self):
        events, ledger, blocked, result = self.run_mocked(fail_provider=True)
        self.assertEqual(events, ["claim", "provider"])
        ledger.claim_stage.assert_called_once()
        ledger.record_stage.assert_not_called()
        blocked.assert_not_called()
        self.assertIsNone(result)

    def test_orphan_audit_must_be_fail_closed(self):
        events, ledger, _, result = self.run_mocked(orphans=1)
        self.assertEqual(events, ["claim", "provider", "record"])
        ledger.claim_stage.assert_called_once()
        self.assertIsNone(result)

    def test_d_provider_path_is_exactly_one_runner_call(self):
        class FakeCapture:
            def __init__(self, *, harness):
                self.harness = harness
            def __enter__(self):
                return self
            def __exit__(self, typ, val, tb):
                return False
            def build_receipt(self, value):
                return {"captured": value}
        with (
            patch.object(dispatcher, "crea_modello_rq2",
                         return_value=Mock(name="fake_llm")) as factory,
            patch.object(dispatcher, "V3DRunnerCapture", FakeCapture),
            patch.object(dispatcher, "run_experiment",
                         return_value={"synthetic": 1}) as run,
            patch.object(dispatcher, "normalize_v4_d_capture",
                         return_value={"receipt": 1}) as norm,
        ):
            result = dispatcher._provider_once(
                row=ROW, config=Mock(), diagnostic_run=None, package=None,
            )
        self.assertEqual(result, {"receipt": 1})
        factory.assert_called_once_with("google", "gemini-3.5-flash-lite")
        run.assert_called_once()
        self.assertFalse(run.call_args.kwargs["salva"])
        norm.assert_called_once()

    def test_c_and_k_use_one_ck_transport_in_mock(self):
        messages = [
            {"role": "system", "content": "synthetic system"},
            {"role": "user", "content": "synthetic user"},
        ]
        for stage in ("C", "K"):
            row = {**ROW, "stage": stage, "stage_id": STAGE[:-1] + stage}
            with (
                patch.object(dispatcher, "one_ck_call_candidate",
                             return_value={"synthetic": 1}) as transport,
                patch.object(dispatcher, "normalize_v4_ck_call",
                             return_value={"receipt": stage}) as norm,
            ):
                out = dispatcher._provider_once(
                    row=row, config=Mock(),
                    diagnostic_run={"synthetic_d": True},
                    package={"messages": messages},
                )
            self.assertEqual(out, {"receipt": stage})
            transport.assert_called_once()
            norm.assert_called_once()


if __name__ == "__main__":
    unittest.main()
