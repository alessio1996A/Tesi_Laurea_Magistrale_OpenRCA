"""Synthetic development-only KPI audit tests. No actual OpenRCA data/API."""
import csv
import json
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from evaluation.rq2_development_kpi_audit import (
    KPIAuditError, VERSION, audit_development_kpis,
)


FIELDS_SPLIT = ("case_id", "cloudbed", "start_unix", "end_unix", "split")
FIELDS_MANIFEST = (
    "case_id", "cloudbed", "query_index", "task_index",
    "instruction", "start_unix", "end_unix",
)
METRIC_HEADER = "timestamp,cmdb_id,kpi_name,value\n"
NODE_DATA = METRIC_HEADER + (
    "120,synthetic-node,system.cpu.pct_usage,10.0\n"
    "160,synthetic-node,system.cpu.pct_usage,20.0\n"
    "180,synthetic-node,system.cpu.pct_usage,40.0\n"
    "200,synthetic-node,synthetic_unrecognized_metric,9.0\n"
    "259,synthetic-node,system.cpu.pct_usage,60.0\n"
    "260,synthetic-node,system.cpu.pct_usage,1000.0\n"
    "320,synthetic-node,system.cpu.pct_usage,99999.0\n"
    "400,synthetic-node,system.cpu.pct_usage,88888.0\n"
)
CONTAINER_DATA = METRIC_HEADER + (
    "125,synthetic-container,container_memory_usage_MB,10\n"
    "240,synthetic-container,container_memory_usage_MB,not_a_number\n"
    "320,synthetic-container,container_memory_usage_MB,99999\n"
)


def test_rows():
    return [
        {"case_id": "cloudbed-1_q001", "cloudbed": "cloudbed-1",
         "start_unix": "100", "end_unix": "200", "split": "development"},
        {"case_id": "cloudbed-1_q002", "cloudbed": "cloudbed-1",
         "start_unix": "140", "end_unix": "260", "split": "development"},
        {"case_id": "cloudbed-1_q003", "cloudbed": "cloudbed-1",
         "start_unix": "300", "end_unix": "380", "split": "ood_holdout"},
        {"case_id": "cloudbed-2_q001", "cloudbed": "cloudbed-2",
         "start_unix": "100", "end_unix": "190", "split": "evaluation"},
    ]


def write_csv(path: Path, fields: tuple, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def setup_data(root: Path, rows=None, *, omit_container=False,
               malformed_headers=False, duplicate_node=False):
    rows = test_rows() if rows is None else rows
    split_path = root / "data/processed/split_market_v1.csv"
    manifest_path = root / "data/processed/benchmark_inputs_market.csv"
    write_csv(
        split_path,
        FIELDS_SPLIT + (("ground_truth",) if malformed_headers else ()),
        rows,
    )
    manifest = [
        {
            **r, "query_index": str(i), "task_index": "task_1",
            "instruction": "Synthetic task without labels",
        }
        for i, r in enumerate(rows)
    ]
    write_csv(manifest_path, FIELDS_MANIFEST, manifest)
    with ZipFile(root / "Market.zip", "w") as z:
        node = "Market/cloudbed-1/telemetry/1970_01_01/metric/metric_node.csv"
        container = "Market/cloudbed-1/telemetry/1970_01_01/metric/metric_container.csv"
        z.writestr(node, NODE_DATA)
        if duplicate_node:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                z.writestr(node, NODE_DATA)
        if not omit_container:
            z.writestr(container, CONTAINER_DATA)
        # If the module opens this member, strict mock tests fail.
        z.writestr("Market/cloudbed-1/record.csv", b"\x00FORBIDDEN")
        z.writestr("Market/cloudbed-1/query.csv", b"\x00FORBIDDEN")
        z.writestr("Market/cloudbed-1/telemetry/1970_01_02/metric/metric_node.csv",
                   b"\x00FORBIDDEN")
    return split_path, manifest_path


def run(root):
    return audit_development_kpis(root, _synthetic_test_fixture=True)


class RQ2DevelopmentKPIAuditTests(unittest.TestCase):
    def test_only_development_union_counted(self):
        with tempfile.TemporaryDirectory() as td:
            setup_data(Path(td))
            r = run(Path(td))
        self.assertEqual(r["audit"], VERSION)
        self.assertEqual(r["development_cases"], 2)
        self.assertEqual(r["metrics_archive_members_read"], 2)
        # Node rows 120, 160, 180, 200, 259: each exactly once even though
        # 160/180 occur in two development windows.
        # Container rows 125 and 240, one nonnumeric.
        self.assertEqual(r["rows_in_union_of_development_windows"], 7)
        self.assertEqual(r["valid_numeric_rows"], 6)

    def test_ood_window_values_never_enter_counts(self):
        with tempfile.TemporaryDirectory() as td:
            setup_data(Path(td))
            r = run(Path(td))
        node = next(x for x in r["catalog_known_metrics"]
                    if x["metric"] == "system.cpu.pct_usage")
        self.assertEqual(node["numeric_rows_in_union_of_development_windows"], 4)
        self.assertTrue(r["statistics_only_development_windows"])
        self.assertTrue(r["possible_non_development_rows_decoded_from_shared_csv"])
        self.assertFalse(r["read_ood_telemetry_for_analysis"])

    def test_nonnumeric_rows_not_counted_as_numeric(self):
        with tempfile.TemporaryDirectory() as td:
            setup_data(Path(td))
            r = run(Path(td))
        mem = next(x for x in r["catalog_known_metrics"]
                   if x["metric"] == "container_memory_usage_MB")
        self.assertEqual(mem["numeric_rows_in_union_of_development_windows"], 1)

    def test_unknown_source_metric_is_not_treated_as_dataset_absent(self):
        with tempfile.TemporaryDirectory() as td:
            setup_data(Path(td))
            r = run(Path(td))
        self.assertEqual(r["other_source_metric_names_count"], 1)
        self.assertEqual(r["other_source_metric_names_sample"], [
            {"layer": "node", "metric": "synthetic_unrecognized_metric"}
        ])

    def test_catalog_remains_not_physically_verified(self):
        with tempfile.TemporaryDirectory() as td:
            setup_data(Path(td))
            r = run(Path(td))
        self.assertFalse(r["catalog_physically_verified"])
        self.assertFalse(r["can_execute_rule"])
        for x in r["catalog_known_metrics"]:
            self.assertFalse(x["market_unit_verified"])
            self.assertFalse(x["counter_or_rate_semantics_verified"])

    def test_never_opens_record_query_or_other_zip_members(self):
        with tempfile.TemporaryDirectory() as td:
            setup_data(Path(td))
            real_open = ZipFile.open
            accessed = []

            def guarded(self, name, *args, **kwargs):
                accessed.append(str(name))
                if not str(name).endswith((
                    "/metric/metric_node.csv", "/metric/metric_container.csv"
                )):
                    raise AssertionError("Non-telemetry archive member opened")
                return real_open(self, name, *args, **kwargs)

            with patch.object(ZipFile, "open", new=guarded):
                r = run(Path(td))
        self.assertEqual(len(accessed), 2)
        self.assertEqual(r["model_api_calls"], 0)
        self.assertFalse(r["files_written"])
        self.assertFalse(r["read_record_csv"])
        self.assertFalse(r["read_scoring"])

    def test_non_synthetic_mode_fails_on_input_hash(self):
        with tempfile.TemporaryDirectory() as td:
            setup_data(Path(td))
            with self.assertRaisesRegex(KPIAuditError, "SHA-256"):
                audit_development_kpis(Path(td))

    def test_split_schema_with_gt_field_refused(self):
        with tempfile.TemporaryDirectory() as td:
            setup_data(Path(td), malformed_headers=True)
            with self.assertRaisesRegex(ValueError, "Schema GT-free"):
                run(Path(td))

    def test_missing_metric_member_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            setup_data(Path(td), omit_container=True)
            with self.assertRaisesRegex(KPIAuditError, "Missing/ambiguous"):
                run(Path(td))

    def test_duplicate_metric_zip_entry_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            setup_data(Path(td), duplicate_node=True)
            with self.assertRaisesRegex(KPIAuditError, "Missing/ambiguous"):
                run(Path(td))

    def test_wrong_manifest_window_refused(self):
        with tempfile.TemporaryDirectory() as td:
            split, manifest = setup_data(Path(td))
            text = manifest.read_text()
            manifest.write_text(text.replace(",140,260\n", ",141,260\n"), encoding="utf-8")
            with self.assertRaisesRegex(KPIAuditError, "disagree"):
                run(Path(td))

    def test_development_ood_window_overlap_fails_closed(self):
        rows = test_rows()
        rows[2]["start_unix"] = "170"
        rows[2]["end_unix"] = "350"
        with tempfile.TemporaryDirectory() as td:
            setup_data(Path(td), rows=rows)
            with self.assertRaisesRegex(KPIAuditError, "holdout windows intersect"):
                run(Path(td))

    def test_no_development_rows_is_an_error(self):
        rows = test_rows()
        for row in rows:
            if row["split"] == "development":
                row["split"] = "evaluation"
        with tempfile.TemporaryDirectory() as td:
            setup_data(Path(td), rows=rows)
            with self.assertRaisesRegex(KPIAuditError, "No development"):
                run(Path(td))

    def test_no_case_or_value_mapping_is_exported(self):
        with tempfile.TemporaryDirectory() as td:
            setup_data(Path(td))
            report = run(Path(td))
        payload = json.dumps(report)
        self.assertNotIn("cloudbed-1_q", payload)
        self.assertNotIn("99999", payload)
        self.assertNotIn("88888", payload)
        self.assertNotIn("record.csv", payload)
        self.assertNotIn("scoring_points", payload)

    def test_deterministic_aggregates(self):
        with tempfile.TemporaryDirectory() as td:
            setup_data(Path(td))
            self.assertEqual(run(Path(td)), run(Path(td)))

    def test_synthetic_fixture_is_not_reported_as_real_data(self):
        with tempfile.TemporaryDirectory() as td:
            setup_data(Path(td))
            r = run(Path(td))
        self.assertFalse(r["source_verified"])
        self.assertFalse(r["read_ground_truth"])
        self.assertFalse(r["read_model_predictions"])


if __name__ == "__main__":
    unittest.main()
