"""Test GT-free, senza LLM, del contratto task-aware comune ai 5 agenti."""
import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from evaluation.experiment_config import ExperimentConfig
from output.v2_task_contract import (
    COMPONENT, REASON, TASK_REQUIRED_FIELDS, TIME,
    audit_task_output, enforce_task_output, task_output_instruction,
)

TZ = ZoneInfo("Asia/Shanghai")
START = int(datetime(2022, 3, 20, 10, tzinfo=TZ).timestamp())
END = int(datetime(2022, 3, 20, 10, 30, tzinfo=TZ).timestamp())
ONE = "The system experienced a failure during this incident."
TWO = "Two failures were detected in the system."
VALUES = {
    TIME: "2022-03-20 10:14:00",
    COMPONENT: "node-1",
    REASON: "node CPU load",
}


def payload_for(task_index, count=1, *, extras=()):
    keys = (*TASK_REQUIRED_FIELDS[task_index], *extras)
    return json.dumps({
        str(index): {field: VALUES[field] for field in keys}
        for index in range(1, count + 1)
    })


def check(raw, task, instruction=ONE):
    return audit_task_output(
        raw, task_index=task, instruction=instruction,
        start_unix=START, end_unix=END,
    )


class TaskAwareV2Tests(unittest.TestCase):
    def test_each_seven_official_task_schemas(self):
        for task in TASK_REQUIRED_FIELDS:
            with self.subTest(task=task):
                report = check(payload_for(task), task)
                self.assertTrue(report["valid"], report["error"])
                self.assertEqual(
                    report["required_fields"], list(TASK_REQUIRED_FIELDS[task])
                )
                self.assertEqual(report["diagnosed_faults"], 1)

    def test_two_faults_for_all_task_types(self):
        for task in TASK_REQUIRED_FIELDS:
            with self.subTest(task=task):
                self.assertTrue(check(
                    payload_for(task, 2), task, TWO,
                )["valid"])

    def test_only_required_fields_are_mandatory(self):
        report = check(payload_for("task_1"), "task_1")
        self.assertTrue(report["valid"])
        self.assertEqual(report["extra_fields"], [])
        # Senza datetime quando il task non lo richiede.
        report2 = check(payload_for("task_6"), "task_6")
        self.assertTrue(report2["valid"])
        self.assertIsNone(report2["timestamp_in_window"])

    def test_additional_known_fields_are_allowed(self):
        raw = payload_for("task_2", extras=(TIME, COMPONENT))
        report = check(raw, "task_2")
        self.assertTrue(report["valid"])
        self.assertEqual(report["extra_fields"], [COMPONENT, TIME])
        self.assertTrue(report["timestamp_in_window"])

    def test_missing_required_field_is_rejected(self):
        raw = json.dumps({"1": {COMPONENT: "node-1"}})
        report = check(raw, "task_6")
        self.assertFalse(report["valid"])
        self.assertIn(REASON, report["error"])

    def test_time_outside_window_is_warning_not_invalid_json(self):
        raw = json.dumps({"1": {TIME: "2022-03-20 10:30:20"}})
        report = check(raw, "task_1")
        self.assertTrue(report["valid"])
        self.assertFalse(report["timestamp_in_window"])
        self.assertEqual(
            report["temporal_outliers"][0][
                "signed_seconds_from_nearest_boundary"
            ], 20,
        )
        encoded, status, report2 = enforce_task_output(
            raw, task_index="task_1", instruction=ONE,
            start_unix=START, end_unix=END,
        )
        self.assertEqual(status, "valid_json")
        self.assertEqual(json.loads(encoded), json.loads(raw))
        self.assertFalse(report2["timestamp_in_window"])

    def test_end_boundary_exactly_is_temporal_warning(self):
        raw = json.dumps({"1": {TIME: "2022-03-20 10:30:00"}})
        report = check(raw, "task_1")
        self.assertTrue(report["valid"])
        self.assertFalse(report["timestamp_in_window"])
        self.assertEqual(
            report["temporal_outliers"][0][
                "signed_seconds_from_nearest_boundary"
            ], 0,
        )

    def test_extra_timestamp_malformed_does_not_fail_unrequested_field(self):
        raw = json.dumps({"1": {REASON: "node CPU load", TIME: "unknown"}})
        report = check(raw, "task_2")
        self.assertTrue(report["valid"])
        self.assertIsNone(report["timestamp_in_window"])

    def test_cardinality_not_guessed_from_output(self):
        report = check(payload_for("task_1"), "task_1", TWO)
        self.assertFalse(report["valid"])
        self.assertIn("Numero di guasti", report["error"])

    def test_nonconsecutive_or_duplicate_indices_are_rejected(self):
        bad = json.dumps({"2": {TIME: VALUES[TIME]}})
        self.assertFalse(check(bad, "task_1")["valid"])
        duplicated = '{"1":{"root cause occurrence datetime":"2022-03-20 10:00:00"},' \
                     '"1":{"root cause occurrence datetime":"2022-03-20 10:00:10"}}'
        self.assertFalse(check(duplicated, "task_1")["valid"])

    def test_reject_nan_even_in_extra_field(self):
        report = check('{"1":{"root cause reason":"x","score":NaN}}', "task_2")
        self.assertFalse(report["valid"])

    def test_chronological_order_reported_separately(self):
        raw = json.dumps({
            "1": {TIME: "2022-03-20 10:20:00"},
            "2": {TIME: "2022-03-20 10:05:00"},
        })
        report = check(raw, "task_1", TWO)
        self.assertTrue(report["valid"])
        self.assertFalse(report["chronological_order"])

    def test_prompt_is_from_gt_free_task_and_count(self):
        prompt = task_output_instruction(task_index="task_6", instruction=TWO)
        self.assertIn("exactly 2", prompt)
        self.assertIn(COMPONENT, prompt)
        self.assertIn(REASON, prompt)
        self.assertNotIn("ground truth", prompt.lower())

    def test_runner_config_defaults_and_modes(self):
        common = {"variant": "A0", "case_id": "cloudbed-1_q001"}
        self.assertEqual(ExperimentConfig(**common).output_contract_mode, "legacy")
        self.assertEqual(
            ExperimentConfig(**common, output_contract_mode="v2_audit")
            .output_contract_mode,
            "v2_audit",
        )
        self.assertEqual(
            ExperimentConfig(**common, output_contract_mode="v2_enforce")
            .output_contract_mode,
            "v2_enforce",
        )
        with self.assertRaises(ValueError):
            ExperimentConfig(**common, output_contract_mode="bad")


if __name__ == "__main__":
    unittest.main()
