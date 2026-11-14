"""Synthetic-only unit tests: no datasets, GT, model API or real OOD cases."""
import copy
import unittest

from evaluation.rq2_q045_warning_detector_synthetic import (
    K_RECORD_SHA256, SyntheticWarningDetectorError,
    inspect_synthetic_warning_windows,
)


def row(timestamp=120, log_id="event-1",
        component="productcatalogservice-0",
        message="severity: warning, synthetic event"):
    return {
        "timestamp": timestamp,
        "cmdb_id": component,
        "log_id": log_id,
        "value": message,
    }


def inspect(rows=None, complete=(True, True), start=120, end=240,
            phase="synthetic"):
    return inspect_synthetic_warning_windows(
        rows=[] if rows is None else rows,
        start_unix=start,
        end_unix=end,
        complete_windows=complete,
        phase=phase,
    )


class Q045WarningSyntheticTests(unittest.TestCase):
    def test_provenance_and_all_non_execution_flags(self):
        out = inspect([row()])
        self.assertEqual(out["candidate_origin_k_record_sha256"], K_RECORD_SHA256)
        self.assertEqual(out["version"], "rq2_q045_warning_detector_synthetic_v0")
        self.assertFalse(out["scientific_freeze"])
        self.assertFalse(out["ready_for_ood_test"])
        self.assertFalse(out["dns_causality_verified"])
        self.assertFalse(out["ground_truth_read"])
        self.assertFalse(out["reads_files"])
        self.assertFalse(out["files_written"])
        self.assertEqual(out["model_api_calls"], 0)
        self.assertFalse(out["model_pseudocode_executed"])

    def test_explicit_warning_is_positive(self):
        out = inspect([row()])
        self.assertEqual(out["buckets"][0]["decision"], "positive")
        self.assertEqual(out["buckets"][0]["warning_count"], 1)
        self.assertEqual(out["buckets"][1]["decision"], "negative")

    def test_exact_60s_boundary_moves_event_to_next_bucket(self):
        out = inspect([row(180)])
        self.assertEqual([b["warning_count"] for b in out["buckets"]], [0, 1])
        self.assertEqual([b["decision"] for b in out["buckets"]], [
            "negative", "positive",
        ])

    def test_pooled_instances_not_counted_as_separate_minutes(self):
        out = inspect([
            row(138, "a", "productcatalogservice-0"),
            row(147, "b", "productcatalogservice-1"),
            row(148, "c", "productcatalogservice-2"),
        ])
        self.assertEqual([b["warning_count"] for b in out["buckets"]], [3, 0])
        self.assertEqual(out["instance_policy"],
                         "pooled warning count across scoped instances")

    def test_case_and_spacing_of_literal_warning_marker(self):
        out = inspect([row(message="SeVeRiTy :  WARNING; synthetic")])
        self.assertEqual(out["buckets"][0]["warning_count"], 1)

    def test_warning_word_alone_or_plural_does_not_match(self):
        out = inspect([
            row(120, "a", message="warning: there might be a problem"),
            row(125, "b", message="severity: warnings"),
        ])
        self.assertEqual(out["buckets"][0]["decision"], "negative")

    def test_dns_text_without_severity_is_not_warning(self):
        out = inspect([row(message="dial tcp: lookup synthetic failed")])
        self.assertEqual(out["buckets"][0]["warning_count"], 0)

    def test_incomplete_bucket_abstains_even_with_warning(self):
        out = inspect([row()], complete=(False, True))
        self.assertEqual(out["buckets"][0]["warning_count"], 1)
        self.assertEqual(out["buckets"][0]["decision"], "abstain")

    def test_empty_incomplete_bucket_abstains(self):
        out = inspect([], complete=(False, True))
        self.assertEqual(out["buckets"][0]["decision"], "abstain")

    def test_empty_complete_bucket_is_synthetic_negative(self):
        out = inspect([])
        self.assertEqual([b["decision"] for b in out["buckets"]], [
            "negative", "negative",
        ])

    def test_repeated_exact_event_is_counted_once(self):
        event = row()
        out = inspect([event, copy.deepcopy(event)])
        self.assertEqual(out["buckets"][0]["warning_count"], 1)
        self.assertEqual(out["deduplicated_identical_rows"], 1)

    def test_same_log_id_different_message_is_rejected(self):
        with self.assertRaisesRegex(SyntheticWarningDetectorError, "duplicate"):
            inspect([row(), row(message="severity: warning, different")])

    def test_same_log_id_different_component_is_rejected(self):
        with self.assertRaises(SyntheticWarningDetectorError):
            inspect([row(), row(component="productcatalogservice-1")])

    def test_scope_excludes_other_service(self):
        out = inspect([
            row(120, "a", component="other-service-1"),
            row(120, "b", component="productcatalogservice-7"),
        ])
        self.assertEqual(out["ignored_other_scope_rows"], 1)
        self.assertEqual(out["buckets"][0]["warning_count"], 1)

    def test_prefix_without_instance_is_not_in_scope(self):
        out = inspect([row(component="productcatalogservice-")])
        self.assertEqual(out["ignored_other_scope_rows"], 1)
        self.assertEqual(out["buckets"][0]["decision"], "negative")

    def test_rejects_ood_test_discovery_and_development_phases(self):
        for phase in ("ood_test", "test", "development", "discovery"):
            with self.subTest(phase=phase):
                with self.assertRaisesRegex(
                    SyntheticWarningDetectorError, "synthetic"
                ):
                    inspect([row()], phase=phase)

    def test_rejects_non_string_phase(self):
        with self.assertRaises(SyntheticWarningDetectorError):
            inspect([], phase=None)

    def test_rejects_unaligned_start(self):
        with self.assertRaisesRegex(SyntheticWarningDetectorError, "unaligned"):
            inspect([], start=121)

    def test_rejects_unaligned_end(self):
        with self.assertRaises(SyntheticWarningDetectorError):
            inspect([], end=239)

    def test_rejects_400_second_interval(self):
        with self.assertRaises(SyntheticWarningDetectorError):
            inspect([], end=520)

    def test_rejects_empty_and_reversed_interval(self):
        for end in (120, 60):
            with self.subTest(end=end):
                with self.assertRaises(SyntheticWarningDetectorError):
                    inspect([], end=end)

    def test_rejects_log_at_exclusive_end(self):
        with self.assertRaisesRegex(SyntheticWarningDetectorError, "timestamp"):
            inspect([row(240)])

    def test_rejects_log_before_start(self):
        with self.assertRaises(SyntheticWarningDetectorError):
            inspect([row(119)])

    def test_rejects_float_or_bool_timestamp(self):
        for ts in (130.0, True, "130"):
            with self.subTest(ts=ts):
                with self.assertRaises(SyntheticWarningDetectorError):
                    inspect([row(ts)])

    def test_rejects_invalid_completeness_list(self):
        with self.assertRaises(SyntheticWarningDetectorError):
            inspect([], complete=[True, True])

    def test_rejects_missing_or_nonboolean_completeness(self):
        for bad in ((True,), (True, 1), ("true", True)):
            with self.subTest(bad=bad):
                with self.assertRaises(SyntheticWarningDetectorError):
                    inspect([], complete=bad)

    def test_rejects_row_with_unknown_or_missing_field(self):
        event = row()
        event["ground_truth"] = "not permitted"
        with self.assertRaises(SyntheticWarningDetectorError):
            inspect([event])
        event.pop("timestamp")
        with self.assertRaises(SyntheticWarningDetectorError):
            inspect([event])

    def test_rejects_invalid_log_event_value(self):
        for value in ("", None, 15):
            with self.subTest(value=value):
                with self.assertRaises(SyntheticWarningDetectorError):
                    inspect([row(message=value)])

    def test_rejects_invalid_component_and_id(self):
        for event in (
            row(component=""),
            row(log_id=""),
            row(component=None),
        ):
            with self.subTest(event=event):
                with self.assertRaises(SyntheticWarningDetectorError):
                    inspect([event])

    def test_refuses_more_than_1440_minutes(self):
        with self.assertRaises(SyntheticWarningDetectorError):
            inspect([], start=0, end=86460,
                    complete=(True,) * 1441)

    def test_does_not_execute_untrusted_log_content(self):
        text = "severity: warning; __import__('os').system('dangerous')"
        out = inspect([row(message=text)])
        self.assertEqual(out["buckets"][0]["warning_count"], 1)
        self.assertFalse(out["model_pseudocode_executed"])
        self.assertNotIn("dangerous", str(out))


if __name__ == "__main__":
    unittest.main()
