"""Synthetic-only tests for read-only, GT-free DEVELOPMENT service-log audit."""
import csv
import json
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from evaluation.rq2_q045_development_log_audit import (
    DevelopmentLogAuditError,
    VERSION,
    audit_development_service_warnings,
)

SPLIT_COLUMNS = ("case_id", "cloudbed", "start_unix", "end_unix", "split")
MANIFEST_COLUMNS = (
    "case_id", "cloudbed", "query_index", "task_index",
    "instruction", "start_unix", "end_unix",
)
MEMBER = "Market/cloudbed-2/telemetry/1970_01_01/log/log_service.csv"
LOG_ROWS = (
    "timestamp,cmdb_id,log_id,value\n"
    "125,productcatalogservice-0,a,severity: warning simulated error\n"
    "180,productcatalogservice-1,b,SeVeRiTy : WARNING synthetic\n"
    "200,productcatalogservice-2,c,normal synthetic log\n"
    "230,other-service-0,d,severity: warning excluded scope\n"
    "299,productcatalogservice-0,e,severity: warning end of discovery\n"
    "300,productcatalogservice-0,f,severity: warning outside development\n"
    "370,productcatalogservice-2,g,severity: warning synthetic OOD\n"
    "520,productcatalogservice-2,h,severity: warning synthetic evaluation\n"
    "610,productcatalogservice-2,i,severity: warning synthetic quarantine\n"
)


def records():
    return [
        {"case_id": "cloudbed-2_q001", "cloudbed": "cloudbed-2",
         "start_unix": "120", "end_unix": "240", "split": "development"},
        {"case_id": "cloudbed-2_q002", "cloudbed": "cloudbed-2",
         "start_unix": "180", "end_unix": "300", "split": "development"},
        {"case_id": "cloudbed-2_q003", "cloudbed": "cloudbed-2",
         "start_unix": "360", "end_unix": "420", "split": "ood_holdout"},
        {"case_id": "cloudbed-2_q004", "cloudbed": "cloudbed-2",
         "start_unix": "500", "end_unix": "560", "split": "evaluation"},
        {"case_id": "cloudbed-2_q005", "cloudbed": "cloudbed-2",
         "start_unix": "600", "end_unix": "660", "split": "mixed_quarantine"},
    ]


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def fixture(
    root, *, rows=None, logs=LOG_ROWS, omit=False, duplicate=False,
    malformed_split=False, manifest_mismatch=False,
):
    rows = records() if rows is None else rows
    split_fields = SPLIT_COLUMNS + (("ground_truth",) if malformed_split else ())
    if malformed_split:
        rows = [{**r, "ground_truth": "FORBIDDEN"} for r in rows]
    split_path = root / "data/processed/split_market_v1.csv"
    manifest_path = root / "data/processed/benchmark_inputs_market.csv"
    write_csv(split_path, split_fields, rows)
    manifest = [{
        "case_id": r["case_id"], "cloudbed": r["cloudbed"],
        "query_index": str(i), "task_index": "task_1",
        "instruction": "Synthetic instruction with no labels",
        "start_unix": r["start_unix"],
        "end_unix": (
            "999" if manifest_mismatch and i == 0 else r["end_unix"]
        ),
    } for i, r in enumerate(rows)]
    write_csv(manifest_path, MANIFEST_COLUMNS, manifest)
    with ZipFile(root / "Market.zip", "w") as archive:
        if not omit:
            archive.writestr(MEMBER, logs)
            if duplicate:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    archive.writestr(MEMBER, logs)
        archive.writestr("Market/cloudbed-2/record.csv", b"FORBIDDEN")
        archive.writestr("Market/cloudbed-2/query.csv", b"FORBIDDEN")
        archive.writestr(
            "Market/cloudbed-2/telemetry/1970_01_02/log/log_service.csv",
            b"FORBIDDEN",
        )


def audit(root):
    return audit_development_service_warnings(
        root, _synthetic_test_fixture=True,
    )


class Q045DevelopmentSourceAuditTests(unittest.TestCase):
    def test_union_of_development_windows_only(self):
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td))
            result = audit(Path(td))
        self.assertEqual(result["version"], VERSION)
        self.assertEqual(result["development_cases"], 2)
        self.assertEqual(result["allowed_service_log_files_read"], 1)
        # 125, 180, 200 and 299; 180 appears in two overlapping
        # development case windows but is counted ONCE.
        self.assertEqual(result["scoped_log_rows"], 4)
        self.assertEqual(result["explicit_warning_rows"], 3)

    def test_heldout_evaluation_and_quarantine_rows_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td))
            result = audit(Path(td))
        self.assertEqual(result["explicit_warning_rows"], 3)
        self.assertEqual(result["by_cloudbed"]["cloudbed-2"]["scoped_log_rows"], 4)
        self.assertEqual(result["by_cloudbed"]["cloudbed-1"]["scoped_log_rows"], 0)
        self.assertTrue(result["nondevelopment_rows_filtered_before_log_parsing"])
        self.assertFalse(result["reads_ood_telemetry_for_analysis"])

    def test_epoch_minute_occupancy_not_service_minute_pairs(self):
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td))
            result = audit(Path(td))
        # 125 -> minute 120; 180 -> 180; 299 -> 240.
        self.assertEqual(result["global_60s_bed_buckets_with_warnings"], 3)

    def test_no_prediction_freeze_or_causality_claim(self):
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td))
            result = audit(Path(td))
        for field in (
            "negative_decisions_produced", "dns_causality_verified",
            "scientific_freeze", "ready_for_ood_test",
            "logging_completeness_verified", "event_identity_deduplicated",
            "model_pseudocode_executed", "files_written",
            "reads_ground_truth", "reads_model_responses", "reads_scoring",
        ):
            self.assertFalse(result[field], field)
        self.assertEqual(result["model_api_calls"], 0)

    def test_no_case_predictions_or_sensitive_raw_log_in_report(self):
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td))
            report = json.dumps(audit(Path(td)))
        for forbidden in (
            "cloudbed-2_q001", "cloudbed-2_q003", "simulated error",
            "synthetic OOD", "synthetic evaluation", "FORBIDDEN",
        ):
            self.assertNotIn(forbidden, report)

    def test_mismatched_sha_refuses_real_mode(self):
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td))
            with self.assertRaisesRegex(DevelopmentLogAuditError, "SHA-256"):
                audit_development_service_warnings(Path(td))

    def test_cross_split_ood_overlap_rejected(self):
        entries = records()
        entries[2]["start_unix"] = "220"
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td), rows=entries)
            with self.assertRaisesRegex(ValueError, "holdout windows intersect"):
                audit(Path(td))

    def test_cross_split_evaluation_overlap_rejected(self):
        entries = records()
        entries[3]["start_unix"] = "220"
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td), rows=entries)
            with self.assertRaisesRegex(DevelopmentLogAuditError, "overlaps"):
                audit(Path(td))

    def test_cross_split_quarantine_overlap_rejected(self):
        entries = records()
        entries[4]["start_unix"] = "220"
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td), rows=entries)
            with self.assertRaisesRegex(DevelopmentLogAuditError, "overlaps"):
                audit(Path(td))

    def test_malformed_gt_bearing_split_schema_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td), malformed_split=True)
            with self.assertRaisesRegex(ValueError, "Schema GT-free"):
                audit(Path(td))

    def test_manifest_window_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td), manifest_mismatch=True)
            with self.assertRaisesRegex(ValueError, "disagree"):
                audit(Path(td))

    def test_missing_archive_member_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td), omit=True)
            with self.assertRaisesRegex(DevelopmentLogAuditError, "Missing"):
                audit(Path(td))

    def test_repeated_archive_member_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td), duplicate=True)
            with self.assertRaisesRegex(DevelopmentLogAuditError, "repeated"):
                audit(Path(td))

    def test_open_never_touches_record_query_or_other_days(self):
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td))
            original = ZipFile.open
            accessed = []

            def guard(obj, name, *args, **kwargs):
                accessed.append(str(name))
                self.assertEqual(str(name), MEMBER)
                return original(obj, name, *args, **kwargs)

            with patch.object(ZipFile, "open", new=guard):
                audit(Path(td))
        self.assertEqual(accessed, [MEMBER])

    def test_nonintegral_scoped_timestamp_fails_closed(self):
        raw = LOG_ROWS + (
            "200.5,productcatalogservice-0,nonint,severity: warning\n"
        )
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td), logs=raw)
            with self.assertRaisesRegex(
                DevelopmentLogAuditError, "Non-integral"
            ):
                audit(Path(td))

    def test_empty_message_and_missing_id_are_flagged_not_approved(self):
        raw = LOG_ROWS + (
            "220,productcatalogservice-1,,\n"
        )
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td), logs=raw)
            result = audit(Path(td))
        self.assertEqual(result["scoped_log_rows"], 5)
        self.assertEqual(result["missing_log_id_rows"], 1)
        self.assertEqual(result["empty_message_rows"], 1)
        self.assertFalse(result["logging_completeness_verified"])

    def test_no_development_cases_rejected(self):
        entries = records()
        for item in entries:
            if item["split"] == "development":
                item["split"] = "evaluation"
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td), rows=entries)
            with self.assertRaisesRegex(ValueError, "No development"):
                audit(Path(td))

    def test_result_is_deterministic_and_synthetic_not_real(self):
        with tempfile.TemporaryDirectory() as td:
            fixture(Path(td))
            a = audit(Path(td))
            b = audit(Path(td))
        self.assertEqual(a, b)
        self.assertFalse(a["source_verified"])
        self.assertFalse(a["market_zip_sha256_verified"])

    def test_no_detection_imports_or_real_dataset_reader(self):
        from evaluation import rq2_q045_development_log_audit as module
        self.assertFalse(hasattr(module, "evaluate_group_decisions"))
        self.assertFalse(hasattr(module, "run_one_k"))
        self.assertFalse(hasattr(module, "predict_ood"))

    def test_wrong_dev_source_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fixture(root)
            split_path = root / "data/processed/split_market_v1.csv"
            new_path = root / "split_backup.csv"
            split_path.rename(new_path)
            split_path.symlink_to(new_path)
            with self.assertRaisesRegex(DevelopmentLogAuditError, "symlinked"):
                audit(root)


if __name__ == "__main__":
    unittest.main()
