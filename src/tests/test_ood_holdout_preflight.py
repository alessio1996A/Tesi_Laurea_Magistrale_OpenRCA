"""Test unitari offline dell'audit OOD: solo CSV sintetici e nessuna API."""
import csv
import tempfile
import unittest
from pathlib import Path

from evaluation.ood_holdout_preflight import inventory_ood


class OODPreflightTests(unittest.TestCase):
    def make_data(self, root: Path) -> Path:
        folder = root / "data/processed"
        folder.mkdir(parents=True)
        rows = [
            ("cloudbed-1_q000", "cloudbed-1", 1000, 2800, "ood_holdout", "task_1"),
            ("cloudbed-1_q001", "cloudbed-1", 1100, 2900, "ood_holdout", "task_2"),
            ("cloudbed-2_q002", "cloudbed-2", 1000, 2800, "ood_holdout", "task_3"),
            ("cloudbed-1_q003", "cloudbed-1", 2500, 4300, "evaluation", "task_1"),
            ("cloudbed-2_q004", "cloudbed-2", 5000, 6800, "development", "task_1"),
        ]
        with (folder / "split_market_v1.csv").open(
            "w", encoding="utf-8", newline=""
        ) as f:
            writer = csv.writer(f)
            writer.writerow(["case_id", "cloudbed", "start_unix", "end_unix", "split"])
            for cid, cloudbed, start, end, split, task in rows:
                writer.writerow([cid, cloudbed, start, end, split])
        with (folder / "benchmark_inputs_market.csv").open(
            "w", encoding="utf-8", newline=""
        ) as f:
            writer = csv.writer(f)
            writer.writerow([
                "case_id", "cloudbed", "query_index", "task_index",
                "instruction", "start_unix", "end_unix",
            ])
            for i, (cid, cloudbed, start, end, split, task) in enumerate(rows):
                writer.writerow([cid, cloudbed, i, task, "Example task", start, end])
        return root

    def test_counts_groups_overlaps_and_no_ground_truth(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_data(Path(temp))
            (root / "record.csv").write_text("DO NOT READ", encoding="utf-8")
            data = inventory_ood(root, verify_original_hashes=False)
        self.assertEqual(data["ood_query_count"], 3)
        self.assertEqual(data["ood_window_groups_count"], 2)
        self.assertEqual(data["ood_by_cloudbed"], {
            "cloudbed-1": 2, "cloudbed-2": 1,
        })
        self.assertEqual(
            data["ood_window_groups"],
            [["cloudbed-1_q000", "cloudbed-1_q001"], ["cloudbed-2_q002"]],
        )
        self.assertEqual(len(data["ood_cross_split_overlaps"]), 2)
        self.assertFalse(data["read_ground_truth"])
        self.assertFalse(data["read_record_csv"])
        self.assertFalse(data["read_telemetry"])
        self.assertEqual(data["model_api_calls"], 0)
        self.assertFalse(data["files_written"])

    def test_modified_original_hashes_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_data(Path(temp))
            with self.assertRaisesRegex(ValueError, "GT-free congelate"):
                inventory_ood(root)

    def test_split_manifest_window_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_data(Path(temp))
            manifest = root / "data/processed/benchmark_inputs_market.csv"
            raw = manifest.read_text(encoding="utf-8")
            manifest.write_text(raw.replace(",1000,2800", ",999,2800", 1),
                                encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Incoerenza"):
                inventory_ood(root, verify_original_hashes=False)

    def test_unknown_split_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = self.make_data(Path(temp))
            split = root / "data/processed/split_market_v1.csv"
            raw = split.read_text(encoding="utf-8")
            split.write_text(raw.replace("development", "not_valid", 1),
                             encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sconosciuto"):
                inventory_ood(root, verify_original_hashes=False)


if __name__ == "__main__":
    unittest.main()
