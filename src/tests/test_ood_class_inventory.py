"""Synthetic-only tests of controlled fault-label inventory (no real GT/API)."""
import csv
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from evaluation.ood_class_inventory import aggregate_ood_classes


class OodClassInventoryTests(unittest.TestCase):
    @staticmethod
    def _csv_bytes(fieldnames, rows):
        import io
        out = io.StringIO(newline="")
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        return out.getvalue().encode("utf-8")

    def setup_fixture(self, path: Path, *, change=None):
        # Original row order and scoring_points are synthetic, not Microsoft GT.
        samples = {
            "cloudbed-1": [
                ("task_2", 100, "node CPU spike", "node-1", True),
                ("task_3", 200, "container packet loss", "c1", True),
                ("task_5", 2100, "container CPU load", "c1", False),
            ],
            "cloudbed-2": [
                ("task_6", 2000, "container write I/O load", "c2", True),
                ("task_7", 4000, "container process termination", "c3", True),
            ],
        }
        if change == "unknown_reason":
            samples["cloudbed-2"][1] = (
                "task_7", 4000, "some new fault", "c3", True
            )
        split_rows, manifest_rows = [], []
        (path / "data/processed").mkdir(parents=True)
        with ZipFile(path / "Market.zip", "w", ZIP_DEFLATED) as z:
            for bed, entries in samples.items():
                queries, records = [], []
                for idx, (task, stamp, reason, component, ood) in enumerate(entries):
                    case_id = f"{bed}_q{idx:03d}"
                    start = stamp // 1800 * 1800
                    end = start + 1800
                    instruction = f"diagnose {bed} {idx}"
                    dt = f"synthetic-date-{stamp}"
                    fields = {
                        "task_2": f"The reason is {reason}",
                        "task_3": f"The component is {component}",
                        "task_5": f"At {dt} on {component}",
                        "task_6": f"Reason {reason}, component {component}",
                        "task_7": f"Time {dt}, component {component}, reason {reason}",
                    }
                    q = {
                        "task_index": task, "instruction": instruction,
                        "scoring_points": fields[task],
                    }
                    if change == "bad_task" and case_id == "cloudbed-1_q000":
                        q["task_index"] = "task_7"
                    queries.append(q)
                    records.append({
                        "timestamp": stamp + (3600 if change == "bad_timestamp"
                                              and case_id == "cloudbed-1_q000" else 0),
                        "level": "pod", "component": component,
                        "reason": reason, "datetime": dt,
                    })
                    split_rows.append({
                        "case_id": case_id, "cloudbed": bed,
                        "start_unix": start, "end_unix": end,
                        "split": "ood_holdout" if ood else "evaluation",
                    })
                    manifest_rows.append({
                        "case_id": case_id, "cloudbed": bed,
                        "query_index": idx, "task_index": task,
                        "instruction": instruction, "start_unix": start,
                        "end_unix": end,
                    })
                base = f"Market/{bed}"
                z.writestr(base + "/query.csv", self._csv_bytes(
                    ["task_index", "instruction", "scoring_points"], queries
                ))
                z.writestr(base + "/record.csv", self._csv_bytes(
                    ["timestamp", "level", "component", "reason", "datetime"],
                    records
                ))
                # Other ZIP entries must never be opened by this audit.
                z.writestr(base + "/telemetry/log.csv", "SECRET_DATA")
        for name, fields, rows in (
            ("split_market_v1.csv",
             ["case_id", "cloudbed", "start_unix", "end_unix", "split"], split_rows),
            ("benchmark_inputs_market.csv",
             ["case_id", "cloudbed", "query_index", "task_index",
              "instruction", "start_unix", "end_unix"], manifest_rows),
        ):
            (path / "data/processed" / name).write_bytes(
                self._csv_bytes(fields, rows)
            )

    def test_aggregate_only_and_shared_window(self):
        with tempfile.TemporaryDirectory() as td:
            self.setup_fixture(Path(td))
            result = aggregate_ood_classes(Path(td), verify_original_hashes=False)
        self.assertEqual(result["alignment_checked_manifest_cases"], 5)
        self.assertEqual(result["ood_query_count"], 4)
        self.assertEqual(result["ood_disjoint_window_groups"], 3)
        self.assertEqual(result["classification_status"], "complete")
        self.assertEqual(result["known_target_reason_query_count"], 4)
        for label in ("node CPU spike", "container packet loss",
                      "container write I/O load", "container process termination"):
            self.assertEqual(result["target_classes"][label]["ood_query_count"], 1)
        self.assertTrue(result["read_ground_truth"])
        self.assertFalse(result["emits_case_label_mapping"])
        self.assertFalse(result["read_telemetry"])
        self.assertEqual(result["model_api_calls"], 0)
        self.assertFalse(result["files_written"])
        self.assertNotIn("cloudbed-1_q000", str(result))
        self.assertNotIn("SECRET_DATA", str(result))

    def test_unknown_reason_requires_review(self):
        with tempfile.TemporaryDirectory() as td:
            self.setup_fixture(Path(td), change="unknown_reason")
            result = aggregate_ood_classes(Path(td), verify_original_hashes=False)
        self.assertEqual(result["classification_status"], "requires_nomenclature_review")
        self.assertEqual(result["unrecognized_reason_query_count"], 1)
        self.assertEqual(result["known_target_reason_query_count"], 3)
        self.assertEqual(result["unrecognized_reason_labels_aggregated"][0]["ood_query_count"], 1)

    def test_task_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            self.setup_fixture(Path(td), change="bad_task")
            with self.assertRaisesRegex(ValueError, "Task mismatch"):
                aggregate_ood_classes(Path(td), verify_original_hashes=False)

    def test_record_timestamp_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            self.setup_fixture(Path(td), change="bad_timestamp")
            with self.assertRaisesRegex(ValueError, "Record outside"):
                aggregate_ood_classes(Path(td), verify_original_hashes=False)

    def test_missing_original_archive_is_error(self):
        with tempfile.TemporaryDirectory() as td:
            self.setup_fixture(Path(td))
            (Path(td) / "Market.zip").unlink()
            with self.assertRaises(FileNotFoundError):
                aggregate_ood_classes(Path(td), verify_original_hashes=False)


if __name__ == "__main__":
    unittest.main()
