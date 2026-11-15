"""OFFLINE-only strict V3 scientific D/C/K receipt adapter tests.

Uses the actual V3 plan, original ledger's pure scientific validators,
original synthetic D run fixtures, and optional mocked C/K transport.
No source-data access, actual release, API, ledger write or GT.
"""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

import evaluation.rq2_v2_ck_provider_transport_candidate as transport
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_v2_ck_text_extraction_candidate import POLICY
from evaluation.rq2_v3_d_final_stream_candidate import D_META_SCHEMA
from evaluation.rq2_v3_d_runner_capture_candidate import VERSION as D_CAPTURE
from evaluation.rq2_v3_scientific_receipt_adapter_candidate import (
    V3ScientificReceiptBlocked,
    normalize_v3_d_capture,
    normalize_v3_ck_call,
    validate_v3_scientific_artifact,
)
from evaluation.rq2_v3_unified_gtfree_discovery_plan import VERSION as V3
from test_rq2_v2_unified_provider_result_adapter_offline import run
from test_rq2_v2_unified_synthetic_journal import cause, rule


def sid(model="gemini", harness="A0", stage="D", case="cloudbed-1_q032"):
    return f"{V3}:{case}:{model}:{harness}:{stage}"


def source_d(model="gemini", harness="A0"):
    raw = run(model=model, harness=harness)
    raw["case_id"] = "cloudbed-1_q032"
    return raw


def capture(run_dict):
    raw = run_dict.get("raw_response")
    return {
        "version": D_CAPTURE,
        "diagnostic_run": run_dict,
        "d_final_text_extraction": {
            "schema": D_META_SCHEMA,
            "policy": POLICY,
            "content_kind": "str" if raw is not None else "not_observed",
            "text_blocks": int(bool(raw)) if raw is not None else 0,
            "nontext_blocks": 0,
        },
        "can_execute_api": False,
        "scientific_release_frozen": False,
        "can_write_scientific_records": False,
    }


def ck_call(raw, *, error=None, kind="list", n=2, others=0):
    return {
        "raw_response": raw if error is None else None,
        "provider_error": error,
        "api_attempts": 1,
        "usage": {
            "complete": True, "input_tokens": 20,
            "output_tokens": 8, "total_tokens": 28,
            "input_token_details": None, "output_token_details": None,
        },
        "content_extraction_policy": POLICY,
        "response_content_kind": kind if error is None else "not_observed",
        "text_blocks_observed": n if error is None else 0,
        "nontext_blocks_observed": others if error is None else 0,
    }


class FakeModel:
    def __init__(self, content):
        self.content = content
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        return AIMessage(
            content=self.content,
            usage_metadata={
                "input_tokens": 20, "output_tokens": 8,
                "total_tokens": 28,
            },
            response_metadata={"finish_reason": "stop"},
        )


class V3ScientificReceiptAdapterOfflineTests(unittest.TestCase):
    def test_complete_v3_d_c_k_for_three_models_and_five_harnesses(self):
        for model in ("gemini", "sonnet", "haiku"):
            for harness in ("A0", "A1", "A1_8R",
                            "A1_8R_Planning", "A1_PAVE"):
                with self.subTest(model=model, harness=harness):
                    diag = source_d(model, harness)
                    d = normalize_v3_d_capture(
                        stage_id=sid(model, harness, "D"),
                        logical_model=model, captured=capture(diag),
                    )
                    self.assertEqual(d["status"], "RECORDED_COMPLETE")
                    self.assertEqual(d["artifact"]["d_final_text_extraction"][
                        "content_kind"], "str")
                    self.assertEqual(d["artifact"]["stage_meter"][
                        "observed_model_requests"], 2)
                    for stage, raw in (("C", cause()), ("K", rule())):
                        receipt = normalize_v3_ck_call(
                            stage_id=sid(model, harness, stage),
                            logical_model=model, call=ck_call(raw),
                            diagnostic_run=diag,
                        )
                        self.assertEqual(receipt["status"], "RECORDED_COMPLETE")
                        self.assertEqual(receipt["artifact"]["raw_response"], raw)
                        self.assertEqual(receipt["artifact"]["text_extraction"][
                            "text_blocks"], 2)
                        validate_v3_scientific_artifact(
                            stage_id=sid(model, harness, stage),
                            logical_model=model, status=receipt["status"],
                            artifact=receipt["artifact"],
                            diagnostic_run=diag,
                        )

    def test_frozen_v2_ids_and_wrong_stage_model_are_refused(self):
        diag = source_d()
        old = sid().replace(V3, "rq2_v2_unified_five_harness_discovery_v0", 1)
        with self.assertRaises(V3ScientificReceiptBlocked):
            normalize_v3_d_capture(
                stage_id=old, logical_model="gemini",
                captured=capture(diag),
            )
        with self.assertRaises(V3ScientificReceiptBlocked):
            normalize_v3_d_capture(
                stage_id=sid(model="sonnet"), logical_model="gemini",
                captured=capture(diag),
            )
        with self.assertRaises(V3ScientificReceiptBlocked):
            normalize_v3_ck_call(
                stage_id=sid(stage="D"), logical_model="gemini",
                call=ck_call(cause()), diagnostic_run=diag,
            )
        with self.assertRaises(V3ScientificReceiptBlocked):
            normalize_v3_ck_call(
                stage_id=sid(case="cloudbed-2_q000", stage="C"),
                logical_model="gemini", call=ck_call(cause()),
                diagnostic_run=diag,
            )

    def test_d_error_is_sanitized_and_usage_never_assumed_zero(self):
        diag = source_d()
        diag["error"] = "Timeout FAKE_SECRET_IN_A_PROVIDER_MESSAGE"
        diag["raw_response"] = None
        diag["metrics"]["token_usage_complete"] = False
        receipt = normalize_v3_d_capture(
            stage_id=sid(), logical_model="gemini",
            captured=capture(diag),
        )
        self.assertEqual(receipt["status"], "PROVIDER_ERROR")
        self.assertTrue(receipt["artifact"]["provider_error"].startswith(
            "RUNNER_EXECUTION_ERROR_SHA256_"
        ))
        self.assertNotIn("FAKE_SECRET", str(receipt))
        self.assertFalse(receipt["artifact"]["stage_meter"]["usage_complete"])
        self.assertEqual(
            receipt["artifact"]["stage_meter"]["cost_estimate_usd_not_invoice"],
            "UNKNOWN",
        )

    def test_invalid_c_json_kept_invalid_with_original_raw_and_metadata(self):
        raw = cause().replace(
            "rq2_cause_probe_v0", "rq2_cause\n_probe_v0"
        )
        diag = source_d()
        receipt = normalize_v3_ck_call(
            stage_id=sid(stage="C"), logical_model="gemini",
            call=ck_call(raw, kind="list", n=1),
            diagnostic_run=diag,
        )
        self.assertEqual(receipt["status"], "INVALID_OUTPUT")
        self.assertEqual(receipt["artifact"]["raw_response"], raw)
        self.assertEqual(receipt["artifact"]["text_extraction"]["text_blocks"], 1)

    def test_c_k_transport_errors_keep_attempt_and_redacted_reason(self):
        for stage in ("C", "K"):
            with self.subTest(stage=stage):
                receipt = normalize_v3_ck_call(
                    stage_id=sid(stage=stage), logical_model="gemini",
                    call=ck_call(None, error="PROVIDER_ERROR:TimeoutError"),
                    diagnostic_run=source_d(),
                )
                self.assertEqual(receipt["status"], "PROVIDER_ERROR")
                self.assertEqual(
                    receipt["artifact"]["stage_meter"]["observed_model_requests"],
                    1,
                )
                self.assertEqual(
                    receipt["artifact"]["text_extraction"]["content_kind"],
                    "not_observed",
                )
                self.assertNotIn("raw_response", receipt["artifact"])

    def test_rejects_missing_and_tampered_c_k_provenance(self):
        diag = source_d()
        call = ck_call(cause())
        for key, bad in (
            ("content_extraction_policy", "unknown_policy"),
            ("response_content_kind", "fictional"),
            ("text_blocks_observed", -1),
            ("nontext_blocks_observed", 9999),
        ):
            with self.subTest(key=key):
                tampered = copy.deepcopy(call)
                tampered[key] = bad
                with self.assertRaises(V3ScientificReceiptBlocked):
                    normalize_v3_ck_call(
                        stage_id=sid(stage="C"),
                        logical_model="gemini", call=tampered,
                        diagnostic_run=diag,
                    )
        missing = copy.deepcopy(call)
        missing.pop("content_extraction_policy")
        with self.assertRaises(V3ScientificReceiptBlocked):
            normalize_v3_ck_call(
                stage_id=sid(stage="C"),
                logical_model="gemini", call=missing,
                diagnostic_run=diag,
            )

    def test_rejects_d_identity_provenance_and_meter_tampering(self):
        diag = source_d()
        for field, bad in (
            ("model", "fake-other"),
            ("variant", "A1"),
            ("case_id", "cloudbed-2_q000"),
        ):
            with self.subTest(field=field):
                edited = copy.deepcopy(diag)
                edited[field] = bad
                with self.assertRaises(V3ScientificReceiptBlocked):
                    normalize_v3_d_capture(
                        stage_id=sid(), logical_model="gemini",
                        captured=capture(edited),
                    )
        meta = capture(diag)
        meta["d_final_text_extraction"]["text_blocks"] = -1
        with self.assertRaises(V3ScientificReceiptBlocked):
            normalize_v3_d_capture(
                stage_id=sid(), logical_model="gemini", captured=meta,
            )
        metering = copy.deepcopy(diag)
        metering["metrics"]["total_tokens"] = -100
        with self.assertRaises(V3ScientificReceiptBlocked):
            normalize_v3_d_capture(
                stage_id=sid(), logical_model="gemini",
                captured=capture(metering),
            )

    def test_readback_rejects_unredacted_provider_errors_and_wrong_parent(self):
        diag = source_d()
        bad = copy.deepcopy(diag)
        bad["error"] = "Timeout synthetic_secret"
        bad["raw_response"] = None
        bad["metrics"]["token_usage_complete"] = False
        d = normalize_v3_d_capture(
            stage_id=sid(), logical_model="gemini",
            captured=capture(bad),
        )
        poisoned = copy.deepcopy(d["artifact"])
        poisoned["provider_error"] = "RAW SECRET FROM AN SDK"
        with self.assertRaises(V3ScientificReceiptBlocked):
            validate_v3_scientific_artifact(
                stage_id=sid(), logical_model="gemini",
                status="PROVIDER_ERROR", artifact=poisoned,
            )

        ck = normalize_v3_ck_call(
            stage_id=sid(stage="C"), logical_model="gemini",
            call=ck_call(None, error="PROVIDER_ERROR:TimeoutError"),
            diagnostic_run=diag,
        )
        poisoned = copy.deepcopy(ck["artifact"])
        poisoned["provider_error"] = "PROVIDER_ERROR:Timeout SECRET"
        with self.assertRaises(V3ScientificReceiptBlocked):
            validate_v3_scientific_artifact(
                stage_id=sid(stage="C"), logical_model="gemini",
                status="PROVIDER_ERROR", artifact=poisoned,
                diagnostic_run=diag,
            )

        wrong_source = source_d(model="haiku")
        with self.assertRaises(V3ScientificReceiptBlocked):
            normalize_v3_ck_call(
                stage_id=sid(stage="C"), logical_model="gemini",
                call=ck_call(cause()), diagnostic_run=wrong_source,
            )

    def test_sdk_mock_transport_then_v3_receipt_is_pure_and_metered(self):
        model = "gemini"
        spec = CANDIDATE_MODELS[model]
        raw = cause()
        first, second = raw.split("_probe_v0", 1)
        fake = FakeModel([
            {"type": "text", "text": first},
            {"type": "text", "text": "_probe_v0" + second},
        ])
        msgs = [
            SystemMessage(content="Synthetic system"),
            HumanMessage(content="Synthetic evidence"),
        ]
        with patch.object(transport, "crea_modello", return_value=fake):
            call = transport.one_ck_call_candidate(
                spec["provider"], spec["model_id"], msgs,
            )
        self.assertEqual(fake.calls, 1)
        self.assertEqual(call["raw_response"], raw)
        receipt = normalize_v3_ck_call(
            stage_id=sid(stage="C"), logical_model="gemini",
            call=call, diagnostic_run=source_d(),
        )
        self.assertEqual(receipt["status"], "RECORDED_COMPLETE")
        self.assertEqual(receipt["artifact"]["text_extraction"]["text_blocks"], 2)
        self.assertEqual(receipt["artifact"]["stage_meter"][
            "input_tokens_observed"], 20)
        self.assertIs(receipt["can_write_scientific_records"], False)


if __name__ == "__main__":
    unittest.main()
