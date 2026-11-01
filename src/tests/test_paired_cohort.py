"""Offline cohort selection tests: no provider calls, no OpenRCA data."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.paired_cohort import (
    HISTORICAL_CASE_IDS,
    PROTOCOL,
    costruisci_piano_abbinato,
    save_plan_exclusive,
)


def write_csv(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def fake_rows():
    dev = [
        {"case_id": f"cloudbed-1_q{i:03}", "split": "development"}
        for i in range(1, 13)
    ] + [
        {"case_id": f"cloudbed-2_q{i:03}", "split": "development"}
        for i in range(1, 13)
    ]
    # Historical pilot cases are allowed in the split, but excluded from cohort.
    dev.extend([
        {"case_id": "cloudbed-1_q040", "split": "development"},
        {"case_id": "cloudbed-1_q052", "split": "development"},
        {"case_id": "cloudbed-2_q031", "split": "development"},
    ])
    dev.extend([
        {"case_id": "cloudbed-1_q090", "split": "evaluation"},
        {"case_id": "cloudbed-2_q091", "split": "ood_holdout"},
        {"case_id": "cloudbed-1_q092", "split": "mixed_quarantine"},
    ])
    return dev


class TestPairedCohort(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.split = self.home / "split_market_v1.csv"
        self.manifest = self.home / "benchmark_inputs_market.csv"
        self.rows = fake_rows()
        self.write(self.rows)

    def write(self, rows):
        write_csv(self.split, ["case_id", "split"], rows)
        write_csv(
            self.manifest, ["case_id", "instruction"],
            [{"case_id": r["case_id"], "instruction": "Investigate"}
             for r in rows],
        )

    def build(self, **kw):
        return costruisci_piano_abbinato(self.split, self.manifest, **kw)

    def test_paired_eight_cases_balanced_cloudbeds(self):
        plan = self.build()
        self.assertEqual(plan["case_count"], 8)
        self.assertEqual(plan["run_count"], 16)
        self.assertEqual(
            sum(p["cloudbed"] == "cloudbed-1" for p in plan["pairs"]), 4
        )
        self.assertEqual(
            sum(p["cloudbed"] == "cloudbed-2" for p in plan["pairs"]), 4
        )

    def test_pilot_and_holdout_are_not_selected(self):
        plan = self.build()
        selected = {p["case_id"] for p in plan["pairs"]}
        self.assertFalse(selected.intersection(HISTORICAL_CASE_IDS))
        self.assertNotIn("cloudbed-1_q090", selected)
        self.assertNotIn("cloudbed-2_q091", selected)
        self.assertNotIn("cloudbed-1_q092", selected)

    def test_split_counts_are_visible(self):
        plan = self.build()
        self.assertEqual(plan["split_counts"]["evaluation"], 1)
        self.assertEqual(plan["split_counts"]["ood_holdout"], 1)
        self.assertEqual(plan["split_counts"]["development"], 27)

    def test_no_ground_truth_or_telemetry_needed(self):
        plan = self.build()
        self.assertFalse(plan["read_ground_truth"])
        self.assertFalse(plan["read_telemetry"])
        self.assertEqual(plan["llm_calls"], 0)

    def test_order_is_paired_and_run_ids_unique(self):
        plan = self.build()
        all_ids = []
        for pair in plan["pairs"]:
            self.assertEqual(set(pair["ordered_variants"]), {"A1", "A1_VERIFY"})
            self.assertEqual(pair["trial"], 1)
            self.assertEqual(pair["max_tool_rounds"], 6)
            self.assertEqual(pair["max_verification_checks"], 2)
            self.assertEqual(pair["output_contract_mode"], "legacy")
            all_ids.extend(pair["run_ids"])
        self.assertEqual(len(all_ids), len(set(all_ids)))
        self.assertEqual(len(all_ids), 16)

    def test_deterministic_selection_does_not_depend_on_csv_row_order(self):
        first = self.build()
        reversed_rows = list(reversed(self.rows))
        self.write(reversed_rows)
        second = self.build()
        self.assertEqual(first["pairs"], second["pairs"])
        # SHA of input changes, correctly recording a different file layout.
        self.assertNotEqual(first["split_file_sha256"], second["split_file_sha256"])

    def test_invalid_or_missing_split_column_fails_closed(self):
        write_csv(
            self.split, ["case_id", "dataset_partition"],
            [{"case_id": "cloudbed-1_q001", "dataset_partition": "development"}],
        )
        with self.assertRaisesRegex(ValueError, "colonne mancanti"):
            self.build()

    def test_ground_truth_bearing_split_rejected_before_selection(self):
        write_csv(
            self.split, ["case_id", "split", "ground_truth"],
            [{"case_id": r["case_id"], "split": r["split"],
              "ground_truth": "NOT_ALLOWED"} for r in self.rows],
        )
        with self.assertRaisesRegex(ValueError, "GT"):
            self.build()

    def test_unknown_split_label_fails_closed(self):
        rows = list(self.rows)
        rows[0] = {**rows[0], "split": "mystery"}
        self.write(rows)
        with self.assertRaisesRegex(ValueError, "Partizione"):
            self.build()

    def test_duplicate_case_id_across_splits_fails_closed(self):
        rows = list(self.rows)
        rows.append({**rows[0], "split": "evaluation"})
        self.write(rows)
        with self.assertRaisesRegex(ValueError, "duplicato"):
            self.build()

    def test_manifest_case_not_present_fails_closed(self):
        write_csv(
            self.manifest, ["case_id", "instruction"],
            [{"case_id": "cloudbed-1_q001", "instruction": "hi"}],
        )
        with self.assertRaisesRegex(ValueError, "assenti dal manifest"):
            self.build()

    def test_manifest_gt_columns_fails_closed(self):
        write_csv(
            self.manifest, ["case_id", "reason"],
            [{"case_id": r["case_id"], "reason": "SECRET"} for r in self.rows],
        )
        with self.assertRaisesRegex(ValueError, "GT"):
            self.build()

    def test_invalid_case_id_fails_closed(self):
        rows = list(self.rows)
        rows[0] = {"case_id": "case_001", "split": "development"}
        self.write(rows)
        with self.assertRaisesRegex(ValueError, "Case ID"):
            self.build()

    def test_too_few_new_cases_in_one_cloudbed_fails(self):
        with self.assertRaisesRegex(ValueError, "Non abbastanza"):
            self.build(per_cloudbed=13)

    def test_bad_sampling_count_rejected(self):
        for n in (0, -1, True, 1.5):
            with self.subTest(n=n):
                with self.assertRaises(ValueError):
                    self.build(per_cloudbed=n)

    def test_exclusive_save_does_not_overwrite(self):
        plan = self.build()
        path = self.home / "preregistration" / "plan.json"
        saved = save_plan_exclusive(plan, path)
        self.assertEqual(saved, path)
        initial = path.read_bytes()
        self.assertEqual(json.loads(initial)["protocol"], PROTOCOL)
        with self.assertRaises(FileExistsError):
            save_plan_exclusive(plan, path)
        self.assertEqual(path.read_bytes(), initial)

    def test_invalid_plan_not_saved(self):
        path = self.home / "preregistration" / "plan.json"
        with self.assertRaises(ValueError):
            save_plan_exclusive({}, path)
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
