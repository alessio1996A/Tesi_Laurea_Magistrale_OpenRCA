"""Synthetic-only safety tests for RQ2 offline allocation preview."""
import csv
import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from evaluation.rq2_partition_preview import SALT, propose_partition


class RQ2PartitionPreviewTests(unittest.TestCase):
    @staticmethod
    def _csv_bytes(columns, rows):
        s = io.StringIO(newline="")
        writer = csv.DictWriter(s, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
        return s.getvalue().encode("utf-8")

    def fixture(self, root: Path, mode=None):
        # One shared window (different classes), 15 unique record rows.
        by_bed = {
            "cloudbed-1": [
                ("node CPU spike", 100),
                ("container packet loss", 100),
                ("node CPU spike", 3700),
                ("container write I/O load", 7300),
                ("container process termination", 10900),
                ("container packet loss", 14500),
                ("container process termination", 18100),
            ],
            "cloudbed-2": [
                ("node CPU spike", 200),
                ("container write I/O load", 3800),
                ("container write I/O load", 7400),
                ("container process termination", 11000),
                ("container process termination", 14600),
                ("container packet loss", 18200),
                ("container packet loss", 21800),
                ("container packet loss", 25400),
            ],
        }
        if mode == "only_shared_node":
            by_bed["cloudbed-1"][2] = ("container packet loss", 3700)
            by_bed["cloudbed-2"][0] = ("container packet loss", 200)
        if mode == "unknown_label":
            by_bed["cloudbed-2"][7] = ("completely unknown issue", 25400)

        splits, manifests = [], []
        folder = root / "data/processed"
        folder.mkdir(parents=True)
        with ZipFile(root / "Market.zip", "w", ZIP_DEFLATED) as z:
            for bed, fault_rows in by_bed.items():
                qs, rs = [], []
                for index, (reason, timestamp) in enumerate(fault_rows):
                    case_id = f"{bed}_q{index:03d}"
                    start = timestamp // 1800 * 1800
                    end = start + 1800
                    instruction = f"Diagnose synthetic incident {case_id}"
                    qs.append({
                        "task_index": "task_2",
                        "instruction": instruction,
                        "scoring_points": f"Cause: {reason}",
                    })
                    rs.append({
                        "timestamp": timestamp,
                        "level": "container",
                        "component": f"synthetic-component-{index}",
                        "reason": reason,
                        "datetime": f"synthetic-{timestamp}",
                    })
                    splits.append({
                        "case_id": case_id, "cloudbed": bed,
                        "start_unix": start, "end_unix": end,
                        "split": "ood_holdout",
                    })
                    manifests.append({
                        "case_id": case_id, "cloudbed": bed,
                        "query_index": index,
                        "task_index": "task_2",
                        "instruction": instruction,
                        "start_unix": start,
                        "end_unix": end,
                    })
                base = f"Market/{bed}"
                z.writestr(base + "/query.csv", self._csv_bytes(
                    ["task_index", "instruction", "scoring_points"], qs
                ))
                z.writestr(base + "/record.csv", self._csv_bytes(
                    ["timestamp", "level", "component", "reason", "datetime"], rs
                ))
                z.writestr(base + "/metric/telemetry.csv", "private telemetry")
        (folder / "split_market_v1.csv").write_bytes(self._csv_bytes(
            ["case_id", "cloudbed", "start_unix", "end_unix", "split"], splits
        ))
        (folder / "benchmark_inputs_market.csv").write_bytes(self._csv_bytes(
            ["case_id", "cloudbed", "query_index", "task_index",
             "instruction", "start_unix", "end_unix"], manifests
        ))

    def test_deterministic_four_discovery_eleven_test(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            result = propose_partition(root, verify_original_hashes=False)
            again = propose_partition(root, verify_original_hashes=False)
        self.assertEqual(result, again)
        self.assertEqual(result["status"], "DRAFT_NOT_EXECUTABLE")
        self.assertEqual(result["selection_salt"], SALT)
        self.assertEqual(result["discovery_query_count"], 4)
        self.assertEqual(result["test_query_count"], 11)
        self.assertEqual(result["discovery_window_groups"], 4)
        self.assertEqual(result["test_window_groups"], 10)
        self.assertFalse(result["files_written"])
        self.assertEqual(result["model_api_calls"], 0)
        self.assertTrue(result["read_ground_truth"])
        self.assertFalse(result["emits_case_label_mapping"])

    def test_shared_multi_fault_window_is_all_test(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            result = propose_partition(root, verify_original_hashes=False)
        shared = {"cloudbed-1_q000", "cloudbed-1_q001"}
        self.assertTrue(shared.issubset(set(result["test_case_ids"])))
        group = next(
            g for g in result["window_groups"]
            if shared == set(g["case_ids"])
        )
        self.assertEqual(group["phase"], "test")
        all_ids = result["discovery_case_ids"] + result["test_case_ids"]
        self.assertEqual(len(all_ids), 15)
        self.assertEqual(len(set(all_ids)), 15)

    def test_aggregate_class_counts_without_case_label_mapping(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            result = propose_partition(root, verify_original_hashes=False)
        balance = result["class_balance_aggregate_only"]
        expected = {
            "node CPU spike": 2,
            "container write I/O load": 2,
            "container process termination": 3,
            "container packet loss": 4,
        }
        for name, remaining in expected.items():
            self.assertEqual(balance[name]["discovery_query_count"], 1)
            self.assertEqual(balance[name]["test_query_count"], remaining)
        self.assertTrue(all(
            set(item) == {"phase", "case_ids"}
            for item in result["window_groups"]
        ))
        self.assertFalse(result["read_telemetry"])
        self.assertFalse(result["read_predictions"])
        self.assertNotIn("scoring_points", str(result))

    def test_no_singleton_for_class_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, mode="only_shared_node")
            with self.assertRaisesRegex(ValueError, "No singleton discovery"):
                propose_partition(root, verify_original_hashes=False)

    def test_unknown_class_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root, mode="unknown_label")
            with self.assertRaisesRegex(ValueError, "Unrecognized OOD class"):
                propose_partition(root, verify_original_hashes=False)

    def test_no_archive_is_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            (root / "Market.zip").unlink()
            with self.assertRaises(FileNotFoundError):
                propose_partition(root, verify_original_hashes=False)


if __name__ == "__main__":
    unittest.main()
