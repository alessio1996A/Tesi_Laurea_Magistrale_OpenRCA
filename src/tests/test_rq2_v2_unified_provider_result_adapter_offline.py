"""G4J: real scientific ledger-compatible receipts, ALL OFFLINE.

Uses RQ1-style D dictionaries and C/K _one_call-style dictionaries from
fixtures; never instantiates SDK/provider, never accesses Market or GT.
A complete D→C→K claim/record/readback also runs in TemporaryDirectory.
"""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluation.rq2_v2_unified_scientific_ledger as ledger
from evaluation.rq2_v2_unified_provider_result_adapter import (
    UnifiedProviderReceiptBlocked, normalize_d_run, normalize_ck_call,
)
from evaluation.rq2_v2_unified_release_blueprint import (
    build_unified_release_blueprint,
)
from evaluation.rq2_v2_unified_scientific_release_contract import (
    canonical_release, release_digest,
)
from test_rq2_v2_unified_scientific_release_contract_offline import (
    FAKE_COMMIT, source_fixture, release_fixture,
)
from test_rq2_v2_unified_scientific_ledger_offline import sid
from test_rq2_v2_unified_synthetic_journal import (
    fake_run, cause, rule, model_id,
)


def run(model="gemini", harness="A0", *, json_valid=True):
    result = fake_run(model, harness, json_valid=json_valid)
    result["metrics"].update({
        "llm_calls": 2,
        "input_tokens": 120,
        "output_tokens": 30,
        "total_tokens": 150,
    })
    return result


def ck_call(raw=None, *, attempts=1, error=None,
            complete=True, input_tokens=15, output_tokens=6):
    if raw is None and error is None:
        raw = cause()
    return {
        "raw_response": raw,
        "provider_error": error,
        "api_attempts": attempts,
        "usage": {
            "complete": complete,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": (
                input_tokens + output_tokens
                if type(input_tokens) is int and type(output_tokens) is int
                else None
            ),
            "input_token_details": None,
            "output_token_details": None,
        },
    }


class ProviderReceiptAdapterOfflineTests(unittest.TestCase):
    def d(self, value=None, *, model="gemini", harness="A0",
          stage_id=None):
        return normalize_d_run(
            stage_id=sid(model, harness, "D") if stage_id is None else stage_id,
            logical_model=model,
            run=run(model, harness) if value is None else value,
        )

    def ck(self, value=None, *, stage="C", model="gemini", harness="A0",
           source=None, stage_id=None):
        if value is None:
            value = ck_call(cause() if stage == "C" else rule())
        return normalize_ck_call(
            stage_id=sid(model, harness, stage) if stage_id is None else stage_id,
            logical_model=model,
            call=value,
            diagnostic_run=run(model, harness) if source is None else source,
        )

    def test_d_success_three_models_is_recordable(self):
        for model in ("gemini", "sonnet", "haiku"):
            with self.subTest(model=model):
                receipt = self.d(model=model)
                self.assertEqual(receipt["status"], "RECORDED_COMPLETE")
                self.assertEqual(receipt["artifact"]["stage_meter"][
                    "observed_model_requests"
                ], 2)
                self.assertEqual(receipt["artifact"]["stage_meter"][
                    "input_tokens_observed"
                ], 120)
                self.assertEqual(receipt["artifact"]["stage_meter"][
                    "output_tokens_observed"
                ], 30)
                self.assertFalse(receipt["can_execute_api"])
                self.assertFalse(receipt["usd_cost_known"])

    def test_d_planning_source_and_harness_preserved(self):
        receipt = self.d(
            model="sonnet", harness="A1_8R_Planning",
        )
        self.assertEqual(receipt["status"], "RECORDED_COMPLETE")
        self.assertEqual(receipt["artifact"]["diagnostic_run"]["variant"],
                         "A1_8R_Planning")

    def test_d_invalid_json_is_not_repaired(self):
        result = self.d(run(json_valid=False))
        self.assertEqual(result["status"], "INVALID_OUTPUT")
        self.assertEqual(
            result["artifact"]["diagnostic_run"]["raw_response"],
            "INVALID SYNTHETIC JSON",
        )

    def test_d_unpaired_native_tool_is_invalid(self):
        result = run()
        result["tool_trajectory"][1]["tool_call_id"] = "unpaired"
        receipt = self.d(result)
        self.assertEqual(receipt["status"], "INVALID_OUTPUT")

    def test_d_runner_error_is_sanitized_not_echoed(self):
        result = run()
        result["error"] = "provider SECRET_TOKEN fake error"
        result["metrics"].update({
            "llm_calls": 1, "input_tokens": 0,
            "output_tokens": 0, "total_tokens": 0,
            "token_usage_complete": False,
        })
        receipt = self.d(result)
        self.assertEqual(receipt["status"], "PROVIDER_ERROR")
        self.assertNotIn("SECRET_TOKEN", str(receipt))
        self.assertIn("RUNNER_EXECUTION_ERROR_SHA256_",
                      receipt["artifact"]["provider_error"])
        self.assertEqual(receipt["artifact"]["stage_meter"][
            "cost_estimate_usd_not_invoice"
        ], "UNKNOWN")

    def test_d_pre_request_error_may_have_zero_invocations(self):
        result = run()
        result["error"] = "synthetic construction failed"
        result["metrics"].update({
            "llm_calls": 0, "input_tokens": 0,
            "output_tokens": 0, "total_tokens": 0,
            "token_usage_complete": False,
        })
        receipt = self.d(result)
        self.assertEqual(receipt["status"], "PROVIDER_ERROR")
        self.assertEqual(
            receipt["artifact"]["stage_meter"]["observed_model_requests"], 0,
        )

    def test_d_success_with_zero_calls_fails_closed(self):
        result = run()
        result["metrics"]["llm_calls"] = 0
        with self.assertRaises(UnifiedProviderReceiptBlocked):
            self.d(result)

    def test_d_incomplete_metrics_preserve_known_lower_bounds(self):
        result = run()
        result["metrics"].update({
            "token_usage_complete": False, "input_tokens": None,
            "output_tokens": 19, "total_tokens": None,
        })
        receipt = self.d(result)
        meter = receipt["artifact"]["stage_meter"]
        self.assertFalse(meter["usage_complete"])
        self.assertEqual(meter["input_tokens_observed"], 0)
        self.assertEqual(meter["output_tokens_observed"], 19)
        self.assertEqual(meter["cost_estimate_usd_not_invoice"], "UNKNOWN")

    def test_d_complete_usage_missing_total_rejected(self):
        result = run()
        result["metrics"]["total_tokens"] = 111
        with self.assertRaises(UnifiedProviderReceiptBlocked):
            self.d(result)

    def test_d_cross_model_identity_rejected(self):
        with self.assertRaises(UnifiedProviderReceiptBlocked):
            self.d(run(model="sonnet"))

    def test_d_ood_identity_rejected(self):
        with self.assertRaises(UnifiedProviderReceiptBlocked):
            self.d(stage_id=sid(case="cloudbed-2_q000"))

    def test_ck_valid_c_and_k_from_all_three_models(self):
        for model in ("gemini", "sonnet", "haiku"):
            for stage in ("C", "K"):
                with self.subTest(model=model, stage=stage):
                    receipt = self.ck(model=model, stage=stage)
                    self.assertEqual(receipt["status"], "RECORDED_COMPLETE")
                    self.assertEqual(
                        receipt["artifact"]["stage_meter"][
                            "observed_model_requests"
                        ], 1,
                    )
                    self.assertEqual(
                        receipt["artifact"]["stage_meter"][
                            "cost_estimate_usd_not_invoice"
                        ], "UNKNOWN",
                    )

    def test_ck_insufficient_evidence_is_valid_nonrule(self):
        receipt = self.ck(
            ck_call(rule(insufficient=True)), stage="K",
        )
        self.assertEqual(receipt["status"], "RECORDED_COMPLETE")

    def test_ck_forged_evidence_is_invalid_output(self):
        receipt = self.ck(
            ck_call(cause(invalid_ref=True)),
        )
        self.assertEqual(receipt["status"], "INVALID_OUTPUT")

    def test_ck_provider_error_after_attempt_retains_unknown_bill(self):
        receipt = self.ck(
            ck_call(
                raw=None, attempts=1,
                error="PROVIDER_ERROR:TimeoutError:HTTP_503",
                complete=False, input_tokens=None, output_tokens=None,
            ),
        )
        self.assertEqual(receipt["status"], "PROVIDER_ERROR")
        meter = receipt["artifact"]["stage_meter"]
        self.assertEqual(meter["observed_model_requests"], 1)
        self.assertFalse(meter["usage_complete"])
        self.assertEqual(meter["cost_estimate_usd_not_invoice"], "UNKNOWN")

    def test_ck_construction_error_zero_attempts(self):
        receipt = self.ck(
            ck_call(
                raw=None, attempts=0, error="SDK_CONSTRUCTION_ERROR:ImportError",
                complete=False, input_tokens=None, output_tokens=None,
            )
        )
        self.assertEqual(receipt["status"], "PROVIDER_ERROR")
        self.assertEqual(receipt["artifact"]["stage_meter"][
            "observed_model_requests"
        ], 0)

    def test_ck_forbidden_tool_call_error_is_preserved(self):
        receipt = self.ck(
            ck_call(
                raw=None, attempts=1,
                error="PROTOCOL_ERROR:ToolCallsForbidden",
                complete=True, input_tokens=15, output_tokens=6,
            )
        )
        self.assertEqual(receipt["status"], "PROVIDER_ERROR")

    def test_ck_missing_usage_is_not_claimed_valid(self):
        value = ck_call(cause())
        value["usage"] = {}
        with self.assertRaises(UnifiedProviderReceiptBlocked):
            self.ck(value)

    def test_ck_inconsistent_complete_usage_is_rejected(self):
        value = ck_call(cause())
        value["usage"]["total_tokens"] = 999
        with self.assertRaises(UnifiedProviderReceiptBlocked):
            self.ck(value)

    def test_ck_missing_response_and_error_is_rejected(self):
        with self.assertRaises(UnifiedProviderReceiptBlocked):
            self.ck(ck_call(raw=None, attempts=0, error=None))

    def test_ck_error_leaking_raw_secret_is_rejected(self):
        with self.assertRaises(UnifiedProviderReceiptBlocked):
            self.ck(ck_call(
                raw=None, attempts=1, error="PROVIDER_ERROR:Timeout SECRET",
            ))

    def test_ck_cross_model_d_provenance_is_rejected(self):
        with self.assertRaises(UnifiedProviderReceiptBlocked):
            self.ck(source=run(model="haiku"))

    def test_ck_missing_usage_may_be_incomplete_without_zero_bill(self):
        receipt = self.ck(
            ck_call(
                cause(), complete=False, input_tokens=None, output_tokens=None,
            ),
        )
        self.assertEqual(receipt["status"], "RECORDED_COMPLETE")
        self.assertFalse(receipt["artifact"]["stage_meter"]["usage_complete"])
        self.assertFalse(receipt["usd_cost_known"])

    def test_adapter_receipt_is_deterministic_and_pure(self):
        src = run()
        before = copy.deepcopy(src)
        one = self.d(src)
        two = self.d(src)
        self.assertEqual(one, two)
        self.assertEqual(src, before)
        self.assertEqual(one["provider_requests_sent_here"], 0)

    def test_dck_receipts_are_accepted_by_real_create_only_ledger(self):
        with tempfile.TemporaryDirectory(
            prefix="rq2_v2_g4j_receipt_",
        ) as tmp:
            root = Path(tmp)
            data = root / "data_fake"
            repo = root / "repo_fake"
            data.mkdir()
            (repo / "src").mkdir(parents=True)
            source = source_fixture()
            blueprint = build_unified_release_blueprint(source_preview=source)
            release = release_fixture(source, blueprint)
            sha = release_digest(release)
            release_path = data / ledger.RELEASE_FILE
            release_path.parent.mkdir(parents=True)
            release_path.write_bytes(canonical_release(release))
            with (
                patch.object(ledger, "_repository_commit",
                             return_value=(FAKE_COMMIT, "")),
                patch.object(ledger, "preview_unified_source_bound",
                             return_value=source),
            ):
                journal = ledger.UnifiedScientificLedger(
                    data_dir=data, repo_dir=repo,
                    expected_commit=FAKE_COMMIT,
                    approved_release_sha256=sha,
                )
                d = run()
                receipts = [
                    normalize_d_run(
                        stage_id=sid(stage="D"), logical_model="gemini", run=d,
                    ),
                    normalize_ck_call(
                        stage_id=sid(stage="C"), logical_model="gemini",
                        call=ck_call(cause()), diagnostic_run=d,
                    ),
                    normalize_ck_call(
                        stage_id=sid(stage="K"), logical_model="gemini",
                        call=ck_call(rule()), diagnostic_run=d,
                    ),
                ]
                for stage, receipt in zip(("D", "C", "K"), receipts):
                    journal.claim_stage(
                        stage_id=sid(stage=stage), model_id=model_id("gemini"),
                    )
                    journal.record_stage(
                        stage_id=sid(stage=stage), model_id=model_id("gemini"),
                        status=receipt["status"], artifact=receipt["artifact"],
                    )
                report = journal.audit_restart()
                self.assertEqual(report["claims"], 3)
                self.assertEqual(report["records"], 3)
                self.assertEqual(report["orphan_claims"], 0)
                self.assertFalse(report["can_execute_api"])


if __name__ == "__main__":
    unittest.main()
