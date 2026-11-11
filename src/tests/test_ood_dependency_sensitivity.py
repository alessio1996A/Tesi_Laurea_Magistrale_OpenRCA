"""Synthetic dependency sensitivity tests. No real benchmark ground truth."""
import csv
import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import test_ood_class_inventory as fixtures
from evaluation.ood_dependency_sensitivity import (
    _cluster, dependency_sensitivity,
)


class DependencySensitivityTests(unittest.TestCase):
    @staticmethod
    def fixture(path, change=None):
        fixtures.OodClassInventoryTests().setup_fixture(path, change=change)

    def test_base_four_ood_queries_three_disjoint_windows(self):
        with tempfile.TemporaryDirectory() as td:
            self.fixture(Path(td))
            result = dependency_sensitivity(
                Path(td), verify_original_hashes=False
            )
        self.assertEqual(result["ood_query_count"], 4)
        self.assertEqual(result["shared_window_pairs"], 1)
        self.assertEqual(result["threshold_sensitivity"]["0"]["candidate_dependency_groups"], 3)
        self.assertEqual(result["threshold_sensitivity"]["14400"]["candidate_dependency_groups"], 3)
        self.assertTrue(result["read_ground_truth"])
        self.assertFalse(result["read_telemetry"])
        self.assertFalse(result["emits_case_label_mapping"])
        self.assertEqual(result["model_api_calls"], 0)
        self.assertFalse(result["files_written"])
        self.assertNotIn("cloudbed-1_q000", str(result))

    def test_unknown_reason_blocks_sensitivity_audit(self):
        with tempfile.TemporaryDirectory() as td:
            self.fixture(Path(td), change="unknown_reason")
            with self.assertRaisesRegex(ValueError, "Unknown OOD labels"):
                dependency_sensitivity(Path(td), verify_original_hashes=False)

    def test_missing_archive_fails(self):
        with tempfile.TemporaryDirectory() as td:
            self.fixture(Path(td))
            (Path(td) / "Market.zip").unlink()
            with self.assertRaises(FileNotFoundError):
                dependency_sensitivity(Path(td), verify_original_hashes=False)

    def test_transitive_cluster(self):
        groups = _cluster(4, [(0, 1), (1, 2)])
        self.assertEqual(sorted(sorted(x) for x in groups), [[0, 1, 2], [3]])

    def test_nearby_same_cause_component_disjoint_window(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.fixture(root)
            archive = root / "Market.zip"
            with ZipFile(archive, "r") as src:
                members = [(info.filename, src.read(info.filename)) for info in src.infolist()]
            new_members = []
            for name, raw in members:
                if name.endswith("/cloudbed-1/query.csv"):
                    # task_3 asks component, so update scoring accordingly.
                    records = list(csv.DictReader(io.StringIO(raw.decode())))
                    records[1]["scoring_points"] = "The component is node-1"
                    raw = fixtures.OodClassInventoryTests._csv_bytes(
                        ["task_index", "instruction", "scoring_points"], records
                    )
                elif name.endswith("/cloudbed-1/record.csv"):
                    records = list(csv.DictReader(io.StringIO(raw.decode())))
                    records[1]["timestamp"] = "2000"
                    records[1]["reason"] = "node CPU spike"
                    records[1]["component"] = "node-1"
                    raw = fixtures.OodClassInventoryTests._csv_bytes(
                        ["timestamp", "level", "component", "reason", "datetime"], records
                    )
                new_members.append((name, raw))
            with ZipFile(archive, "w", ZIP_DEFLATED) as dst:
                for name, raw in new_members:
                    dst.writestr(name, raw)
            for name in ("split_market_v1.csv", "benchmark_inputs_market.csv"):
                p = root / "data/processed" / name
                with p.open(encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    fields = list(reader.fieldnames)
                    rows = list(reader)
                for row in rows:
                    if row["case_id"] == "cloudbed-1_q001":
                        row["start_unix"] = "1800"
                        row["end_unix"] = "3600"
                p.write_bytes(fixtures.OodClassInventoryTests._csv_bytes(fields, rows))

            result = dependency_sensitivity(root, verify_original_hashes=False)
        self.assertEqual(result["shared_window_pairs"], 0)
        self.assertEqual(result["threshold_sensitivity"]["1800"]["candidate_dependency_groups"], 4)
        self.assertEqual(result["threshold_sensitivity"]["3600"]["candidate_dependency_groups"], 3)
        self.assertEqual(result["threshold_sensitivity"]["3600"]["additional_pairs_beyond_window_overlap"], 1)


if __name__ == "__main__":
    unittest.main()
