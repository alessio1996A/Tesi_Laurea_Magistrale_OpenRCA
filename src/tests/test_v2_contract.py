"""Test V2 sintetici, offline, senza API o ground truth."""
import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from output.openrca_contract import OutputContractError
from output.v2_contract import (
    audit_openrca_v2,
    infer_requested_faults,
    validate_openrca_v2,
)


TZ = ZoneInfo("Asia/Shanghai")
START = int(datetime(2022, 3, 20, 10, 0, tzinfo=TZ).timestamp())
END = int(datetime(2022, 3, 20, 10, 30, tzinfo=TZ).timestamp())
ONE = "The cloudbed experienced a failure from 10:00 to 10:30."
TWO = "The system experienced two failures during this incident."


def raw_faults(*dates):
    return json.dumps({
        str(i): {
            "root cause occurrence datetime": date,
            "root cause component": f"component-{i}",
            "root cause reason": "synthetic fault",
        }
        for i, date in enumerate(dates, 1)
    })


class V2ContractTests(unittest.TestCase):
    def test_cardinality_extracted_from_instruction_only(self):
        examples = {
            "a failure": 1,
            "one failure": 1,
            "single failure": 1,
            "a single fault": 1,
            "two failures": 2,
            "two failures and a failure was described": 2,
            "three distinct faults": 3,
        }
        for instruction, expected in examples.items():
            with self.subTest(instruction=instruction):
                self.assertEqual(infer_requested_faults(instruction), expected)

    def test_unknown_or_conflicting_cardinality(self):
        self.assertIsNone(infer_requested_faults("The system degraded."))
        with self.assertRaisesRegex(OutputContractError, "ambigua"):
            infer_requested_faults("One failure and two failures occurred.")

    def test_valid_one_fault_in_shanghai_window(self):
        diag = validate_openrca_v2(
            raw_faults("2022-03-20 10:01:00"),
            instruction=ONE, start_unix=START, end_unix=END,
        )
        self.assertEqual(len(diag.root_causes), 1)

    def test_valid_two_faults_in_shanghai_window(self):
        diag = validate_openrca_v2(
            raw_faults("2022-03-20 10:05:00", "2022-03-20 10:16:00"),
            instruction=TWO, start_unix=START, end_unix=END,
        )
        self.assertEqual(len(diag.root_causes), 2)

    def test_wrong_fault_cardinality_is_rejected(self):
        with self.assertRaisesRegex(OutputContractError, "Cardinalita"):
            validate_openrca_v2(
                raw_faults("2022-03-20 10:05:00"),
                instruction=TWO, start_unix=START, end_unix=END,
            )

    def test_boundary_start_inclusive_end_exclusive(self):
        self.assertEqual(len(validate_openrca_v2(
            raw_faults("2022-03-20 10:00:00"),
            instruction=ONE, start_unix=START, end_unix=END,
        ).root_causes), 1)
        with self.assertRaisesRegex(OutputContractError, "fuori"):
            validate_openrca_v2(
                raw_faults("2022-03-20 10:30:00"),
                instruction=ONE, start_unix=START, end_unix=END,
            )

    def test_reject_timestamp_outside_prior_to_window(self):
        with self.assertRaisesRegex(OutputContractError, "fuori"):
            validate_openrca_v2(
                raw_faults("2022-03-20 09:59:59"),
                instruction=ONE, start_unix=START, end_unix=END,
            )

    def test_reject_noncanonical_datetime_and_extra_keys(self):
        item = json.loads(raw_faults("2022-03-20 10:08:00"))
        item["1"]["root cause occurrence datetime"] = "2022-03-20T10:08:00"
        with self.assertRaisesRegex(OutputContractError, "Timestamp"):
            validate_openrca_v2(
                json.dumps(item),
                instruction=ONE, start_unix=START, end_unix=END,
            )
        item["1"]["root cause occurrence datetime"] = "2022-03-20 10:08:00"
        item["1"]["extra"] = "not allowed"
        with self.assertRaisesRegex(OutputContractError, "aggiuntivi"):
            validate_openrca_v2(
                json.dumps(item),
                instruction=ONE, start_unix=START, end_unix=END,
            )

    def test_reject_duplicate_and_nonconsecutive_keys(self):
        duplicate = (
            '{"1":{"root cause occurrence datetime":"2022-03-20 10:01:00",'
            '"root cause component":"a","root cause reason":"x"},'
            '"1":{"root cause occurrence datetime":"2022-03-20 10:02:00",'
            '"root cause component":"b","root cause reason":"y"}}'
        )
        with self.assertRaisesRegex(OutputContractError, "duplicata"):
            validate_openrca_v2(
                duplicate, instruction=ONE, start_unix=START, end_unix=END,
            )
        item = json.loads(raw_faults("2022-03-20 10:03:00"))
        item["2"] = item.pop("1")
        with self.assertRaisesRegex(OutputContractError, "consecutive"):
            validate_openrca_v2(
                json.dumps(item),
                instruction=ONE, start_unix=START, end_unix=END,
            )

    def test_refuse_ambiguous_instructions_without_labels(self):
        with self.assertRaisesRegex(OutputContractError, "Numero di guasti"):
            validate_openrca_v2(
                raw_faults("2022-03-20 10:15:00"),
                instruction="Investigate the incident.",
                start_unix=START, end_unix=END,
            )

    def test_bad_window_rejected(self):
        with self.assertRaisesRegex(OutputContractError, "Finestra"):
            validate_openrca_v2(
                raw_faults("2022-03-20 10:15:00"),
                instruction=ONE, start_unix=END, end_unix=START,
            )

    def test_audit_does_not_repair_or_invent(self):
        raw = raw_faults("2022-03-20 10:15:00")
        original = raw
        valid = audit_openrca_v2(
            raw, instruction=ONE, start_unix=START, end_unix=END,
        )
        invalid = audit_openrca_v2(
            None, instruction=ONE, start_unix=START, end_unix=END,
        )
        self.assertTrue(valid["valid"])
        self.assertEqual(valid["expected_faults"], 1)
        self.assertFalse(invalid["valid"])
        self.assertEqual(raw, original)
        self.assertNotIn("raw_response", valid)


if __name__ == "__main__":
    unittest.main()
