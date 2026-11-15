"""Test offline del solo nuovo contratto D task-aware V4.

Nessun LLM, provider, telemetria, GT, Drive, record o claim reale.
Non si rieseguono test storici RQ1/V2/V3.
"""
from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

from output.v2_task_contract import TASK_REQUIRED_FIELDS
from evaluation.rq2_v4_d_task_aware_contract import (
    VERSION, V4DTaskAwareBlocked,
    classify_v4_d, require_v4_d_status, validate_v4_d_task_aware,
)

TIME = "root cause occurrence datetime"
COMP = "root cause component"
REASON = "root cause reason"
VALUES = {
    TIME: "2026-01-02 03:04:05",
    COMP: "service-a",
    REASON: "database connection exhausted",
}
ROW = {
    "stage": "D",
    "case_id": "cloudbed-1_q032",
    "logical_model": "gemini",
    "harness": "A0",
}


def fixture(task: str, *, count: int = 1, extra: tuple[str, ...] = ()) -> dict:
    required = TASK_REQUIRED_FIELDS[task]
    fields = tuple(dict.fromkeys((*required, *extra)))
    faults = {
        str(index): {name: VALUES[name] for name in fields}
        for index in range(1, count + 1)
    }
    raw = json.dumps(faults, ensure_ascii=False)
    audit = {
        "contract": "openrca_v2_task_aware_v1",
        "valid": True,
        "error": None,
        "task_index": task,
        "required_fields": list(required),
        "expected_faults": count,
        "diagnosed_faults": count,
        "timestamp_in_window": None,
        "temporal_outliers": [],
        "chronological_order": True if TIME in fields and count > 1 else None,
        "extra_fields": sorted(set(fields) - set(required)),
    }
    return {
        "task_index": task,
        "output_contract_mode": "v2_enforce",
        "output_contract_v2": audit,
        "json_status": "valid_json",
        "error": None,
        "raw_response": raw,
        "prediction": raw,
    }


class V4DTaskAwareContractTests(unittest.TestCase):
    def test_all_seven_tasks_accept_exact_required_fields(self):
        for task, required in TASK_REQUIRED_FIELDS.items():
            with self.subTest(task=task):
                run = fixture(task)
                proof = validate_v4_d_task_aware(run)
                self.assertEqual(proof["version"], VERSION)
                self.assertEqual(proof["required_fields"], list(required))
                self.assertEqual(proof["fault_count"], 1)
                self.assertFalse(proof["causal_correctness_verified"])

    def test_task_2_reason_only_regression(self):
        run = fixture("task_2")
        item = json.loads(run["raw_response"])["1"]
        self.assertEqual(set(item), {REASON})
        self.assertTrue(validate_v4_d_task_aware(run)["task_contract_valid"])

    def test_task_2_extra_components_do_not_invalidate(self):
        run = fixture("task_2", extra=(COMP,))
        self.assertTrue(validate_v4_d_task_aware(run)["task_contract_valid"])

    def test_missing_required_field_is_rejected(self):
        run = fixture("task_6")
        item = json.loads(run["raw_response"])
        del item["1"][COMP]
        run["raw_response"] = json.dumps(item)
        run["prediction"] = run["raw_response"]
        with self.assertRaises(V4DTaskAwareBlocked):
            validate_v4_d_task_aware(run)

    def test_missing_or_spoofed_audit_fails_closed(self):
        for change in ("missing", "false", "wrong_task", "wrong_fields"):
            with self.subTest(change=change):
                run = fixture("task_2")
                if change == "missing":
                    del run["output_contract_v2"]
                elif change == "false":
                    run["output_contract_v2"]["valid"] = False
                elif change == "wrong_task":
                    run["output_contract_v2"]["task_index"] = "task_7"
                else:
                    run["output_contract_v2"]["required_fields"] = [
                        TIME, COMP, REASON
                    ]
                with self.assertRaises(V4DTaskAwareBlocked):
                    validate_v4_d_task_aware(run)

    def test_task_fault_count_must_match_audit(self):
        run = fixture("task_2", count=2)
        run["output_contract_v2"]["expected_faults"] = 1
        with self.assertRaises(V4DTaskAwareBlocked):
            validate_v4_d_task_aware(run)

    def test_fault_index_must_be_contiguous_from_one(self):
        run = fixture("task_2")
        run["raw_response"] = json.dumps({"2": {REASON: VALUES[REASON]}})
        run["prediction"] = run["raw_response"]
        with self.assertRaises(V4DTaskAwareBlocked):
            validate_v4_d_task_aware(run)

    def test_duplicate_json_keys_are_rejected(self):
        run = fixture("task_2")
        run["raw_response"] = (
            '{"1":{"root cause reason":"first","root cause reason":"second"}}'
        )
        with self.assertRaises(V4DTaskAwareBlocked):
            validate_v4_d_task_aware(run)

    def test_invalid_required_datetime_is_rejected(self):
        run = fixture("task_1")
        run["raw_response"] = json.dumps({"1": {TIME: "not-a-date"}})
        run["prediction"] = run["raw_response"]
        with self.assertRaises(V4DTaskAwareBlocked):
            validate_v4_d_task_aware(run)

    def test_nonchronological_multi_fault_is_rejected(self):
        run = fixture("task_4", count=2)
        payload = json.loads(run["raw_response"])
        payload["1"][TIME] = "2026-01-04 03:04:05"
        payload["2"][TIME] = "2026-01-02 03:04:05"
        run["raw_response"] = json.dumps(payload)
        run["prediction"] = run["raw_response"]
        run["output_contract_v2"]["chronological_order"] = False
        with self.assertRaises(V4DTaskAwareBlocked):
            validate_v4_d_task_aware(run)

    def test_prediction_must_match_original_response(self):
        run = fixture("task_2")
        run["prediction"] = '{"1":{"root cause reason":"different"}}'
        with self.assertRaises(V4DTaskAwareBlocked):
            validate_v4_d_task_aware(run)

    def test_invalid_runner_state_is_rejected(self):
        for field, value in (
            ("error", "provider failed"),
            ("json_status", "invalid_v2_task_output"),
            ("output_contract_mode", "legacy"),
        ):
            with self.subTest(field=field):
                run = fixture("task_2")
                run[field] = value
                with self.assertRaises(V4DTaskAwareBlocked):
                    validate_v4_d_task_aware(run)

    def test_readback_uses_exact_same_classifier(self):
        run = fixture("task_2")
        with patch(
            "evaluation.rq2_v4_d_task_aware_contract.audit_captured_v2_d",
            return_value={"status": "OFFLINE_MOCK_ONLY"},
        ) as provenance:
            self.assertEqual(
                classify_v4_d(row=ROW, run=run), "RECORDED_COMPLETE"
            )
            require_v4_d_status(
                row=ROW, run=run, status="RECORDED_COMPLETE"
            )
            with self.assertRaises(V4DTaskAwareBlocked):
                require_v4_d_status(
                    row=ROW, run=run, status="INVALID_OUTPUT"
                )
            self.assertEqual(provenance.call_count, 3)

    def test_invalid_json_classified_as_invalid_not_complete(self):
        run = fixture("task_2")
        run["raw_response"] = "not json"
        with patch(
            "evaluation.rq2_v4_d_task_aware_contract.audit_captured_v2_d",
            return_value={},
        ):
            self.assertEqual(
                classify_v4_d(row=ROW, run=run), "INVALID_OUTPUT"
            )
            require_v4_d_status(row=ROW, run=run, status="INVALID_OUTPUT")

    def test_unverifiable_provenance_is_invalid(self):
        run = fixture("task_2")
        from evaluation.rq2_v2_unified_provenance_gate import (
            UnifiedRQ2ProvenanceError,
        )
        with patch(
            "evaluation.rq2_v4_d_task_aware_contract.audit_captured_v2_d",
            side_effect=UnifiedRQ2ProvenanceError("synthetic absent IDs"),
        ):
            self.assertEqual(
                classify_v4_d(row=ROW, run=run), "INVALID_OUTPUT"
            )

    def test_provider_error_must_not_be_mislabelled_invalid(self):
        run = fixture("task_2")
        run["error"] = "provider failed"
        with self.assertRaises(V4DTaskAwareBlocked):
            classify_v4_d(row=ROW, run=run)

    def test_no_ground_truth_or_external_calls_in_fixture(self):
        run = fixture("task_2")
        before = copy.deepcopy(run)
        validate_v4_d_task_aware(run)
        self.assertEqual(run, before)


if __name__ == "__main__":
    unittest.main()
