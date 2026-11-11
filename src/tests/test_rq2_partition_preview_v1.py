"""Synthetic V1 tests; no real GT, telemetry, provider calls or writes."""
import csv
import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from test_rq2_partition_preview import RQ2PartitionPreviewTests
from evaluation.rq2_partition_preview_v1 import (
    _gap, propose_partition_v1,
)


class BalancedRQ2PartitionTests(unittest.TestCase):
    @staticmethod
    def fixture(root: Path, mode=None):
        RQ2PartitionPreviewTests().fixture(root, mode=mode)

    @staticmethod
    def move_record_and_window(root, bed, index, timestamp):
        """Synthetic edit: keep archive record and frozen-style manifest aligned."""
        zip_path = root / "Market.zip"
        member = f"Market/{bed}/record.csv"
        with ZipFile(zip_path, "r") as z:
            entries = [(item.filename, z.read(item.filename))
                       for item in z.infolist()]
        out = []
        for name, raw in entries:
            if name == member:
                rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
                rows[index]["timestamp"] = str(timestamp)
                raw = RQ2PartitionPreviewTests._csv_bytes(
                    ["timestamp", "level", "component", "reason", "datetime"], rows
                )
            out.append((name, raw))
        with ZipFile(zip_path, "w", ZIP_DEFLATED) as z:
            for name, raw in out:
                z.writestr(name, raw)
        cid = f"{bed}_q{index:03d}"
        for file in ("split_market_v1.csv", "benchmark_inputs_market.csv"):
            p = root / "data/processed" / file
            with p.open(encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                columns = list(reader.fieldnames)
                rows = list(reader)
            for row in rows:
                if row["case_id"] == cid:
                    row["start_unix"] = str(timestamp // 1800 * 1800)
                    row["end_unix"] = str(timestamp // 1800 * 1800 + 1800)
            p.write_bytes(RQ2PartitionPreviewTests._csv_bytes(columns, rows))

    def test_balanced_discovery_and_preserve_test_beds(self):
        with tempfile.TemporaryDirectory() as td:
            self.fixture(Path(td))
            result = propose_partition_v1(Path(td), verify_original_hashes=False)
        self.assertEqual(result["status"], "DRAFT_NOT_EXECUTABLE")
        self.assertEqual(result["discovery_query_count"], 4)
        self.assertEqual(result["test_query_count"], 11)
        self.assertEqual(result["discovery_by_cloudbed"],
                         {"cloudbed-1": 2, "cloudbed-2": 2})
        self.assertEqual(result["discovery_window_groups"], 4)
        self.assertEqual(result["test_window_groups"], 10)
        self.assertGreater(result["valid_candidate_partitions_count"], 0)
        for name in (
            "node CPU spike", "container write I/O load",
            "container process termination", "container packet loss"
        ):
            self.assertEqual(
                result["class_balance_aggregate_only"][name]["discovery_queries"],
                1
            )
            self.assertEqual(
                result["class_balance_aggregate_only"][name]["test_queries"],
                {"node CPU spike": 2, "container write I/O load": 2,
                 "container process termination": 3,
                 "container packet loss": 4}[name]
            )
            self.assertEqual(
                result["class_balance_aggregate_only"][name]["cloudbeds_represented_in_test"],
                2
            )

    def test_shared_window_group_stays_in_test(self):
        with tempfile.TemporaryDirectory() as td:
            self.fixture(Path(td))
            result = propose_partition_v1(Path(td), verify_original_hashes=False)
        a, b = "cloudbed-1_q000", "cloudbed-1_q001"
        self.assertTrue({a, b}.issubset(result["test_case_ids"]))
        self.assertIn(
            {"phase": "test", "case_ids": [a, b]},
            result["window_groups"]
        )

    def test_deterministic_and_no_gt_association_in_output(self):
        with tempfile.TemporaryDirectory() as td:
            self.fixture(Path(td))
            a = propose_partition_v1(Path(td), verify_original_hashes=False)
            b = propose_partition_v1(Path(td), verify_original_hashes=False)
        self.assertEqual(a, b)
        self.assertEqual(a["model_api_calls"], 0)
        self.assertFalse(a["files_written"])
        self.assertFalse(a["read_telemetry"])
        self.assertFalse(a["read_predictions"])
        self.assertTrue(a["read_ground_truth"])
        self.assertFalse(a["emits_case_label_mapping"])
        self.assertNotIn("scoring_points", str(a))
        self.assertEqual(
            len(set(a["discovery_case_ids"]) | set(a["test_case_ids"])), 15
        )
        self.assertFalse(set(a["discovery_case_ids"]) & set(a["test_case_ids"]))

    def test_adjacent_windows_are_not_selected_for_discovery(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.fixture(root)
            # cloudbed-2 q000 window [0,1800), q001 now [1800,3600)
            self.move_record_and_window(root, "cloudbed-2", 1, 1800)
            result = propose_partition_v1(root, verify_original_hashes=False)
        self.assertNotIn("cloudbed-2_q001", result["discovery_case_ids"])
        self.assertIn("cloudbed-2_q001", result["test_case_ids"])
        self.assertEqual(result["discovery_by_cloudbed"],
                         {"cloudbed-1": 2, "cloudbed-2": 2})

    def test_unknown_reason_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.fixture(root, mode="unknown_label")
            with self.assertRaisesRegex(ValueError, "Unrecognized classes"):
                propose_partition_v1(root, verify_original_hashes=False)

    def test_missing_archive_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.fixture(root)
            (root / "Market.zip").unlink()
            with self.assertRaises(FileNotFoundError):
                propose_partition_v1(root, verify_original_hashes=False)

    def test_gap_uses_same_cloudbed_only(self):
        a = {"cloudbed":"cloudbed-1","start_unix":"0","end_unix":"1800"}
        b = {"cloudbed":"cloudbed-1","start_unix":"1800","end_unix":"3600"}
        c = {"cloudbed":"cloudbed-2","start_unix":"1800","end_unix":"3600"}
        d = {"cloudbed":"cloudbed-1","start_unix":"7200","end_unix":"9000"}
        self.assertEqual(_gap(a,b),0)
        self.assertIsNone(_gap(a,c))
        self.assertEqual(_gap(a,d),5400)


if __name__ == "__main__":
    unittest.main()
