"""Test offline della pre-registrazione ST: nessun dato reale o chiamata API."""
import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from evaluation.paired_st_cohort import costruisci_piano, PREVIOUS, COUNTS


class TestPairedStructuralCohort(unittest.TestCase):
    def make_inputs(self, folder, *, extra_gt=False):
        split = folder / "split_market_v1.csv"
        manifest = folder / "benchmark_inputs_market.csv"
        entries = []
        for index in range(148):
            cloudbed = "cloudbed-1" if index < 74 else "cloudbed-2"
            local = index if index < 74 else index - 74
            case_id = f"{cloudbed}_q{local:03d}"
            partition = (
                "development" if index < 92 else
                "evaluation" if index < 115 else
                "mixed_quarantine" if index < 133 else "ood_holdout"
            )
            entries.append((case_id, cloudbed, index * 100, (index + 1) * 100, partition))
        with split.open("w", encoding="utf-8", newline="") as stream:
            fields = ["case_id", "cloudbed", "start_unix", "end_unix", "split"]
            if extra_gt:
                fields.append("reason")
            w = csv.DictWriter(stream, fieldnames=fields)
            w.writeheader()
            for case_id, cb, start, end, partition in entries:
                item = dict(case_id=case_id, cloudbed=cb,
                            start_unix=start, end_unix=end, split=partition)
                if extra_gt:
                    item["reason"] = "SENSITIVE"
                w.writerow(item)
        with manifest.open("w", encoding="utf-8", newline="") as stream:
            w = csv.DictWriter(stream, fieldnames=[
                "case_id", "cloudbed", "query_index", "task_index",
                "instruction", "start_unix", "end_unix",
            ])
            w.writeheader()
            for case_id, cb, start, end, _ in entries:
                w.writerow(dict(
                    case_id=case_id, cloudbed=cb, query_index=0,
                    task_index="task_1", instruction="Diagnose",
                    start_unix=start, end_unix=end,
                ))
        return split, manifest

    def test_deterministic_balanced_excludes_past_and_holdouts(self):
        with TemporaryDirectory() as tmp:
            split, manifest = self.make_inputs(Path(tmp))
            first = costruisci_piano(split, manifest)
            second = costruisci_piano(split, manifest)
        self.assertEqual(first, second)
        self.assertEqual(first["split_counts"], COUNTS)
        self.assertEqual(first["run_count"], 16)
        self.assertEqual(first["llm_calls"], 0)
        self.assertEqual(first["case_count"], 8)
        self.assertTrue(all(
            pair["case_id"] not in PREVIOUS
            and pair["max_tool_rounds"] == 6
            and pair["max_verification_checks"] == 2
            and set(pair["ordered_variants"]) == {"A1_VERIFY", "A1_VERIFY_ST"}
            for pair in first["pairs"]
        ))
        self.assertEqual(
            sum(pair["cloudbed"] == "cloudbed-1" for pair in first["pairs"]), 4
        )
        self.assertEqual(
            sum(pair["cloudbed"] == "cloudbed-2" for pair in first["pairs"]), 4
        )

    def test_same_historical_window_is_excluded_even_with_different_id(self):
        with TemporaryDirectory() as tmp:
            split, manifest = self.make_inputs(Path(tmp))
            initial = costruisci_piano(split, manifest)
            target = next(p["case_id"] for p in initial["pairs"]
                          if p["cloudbed"] == "cloudbed-1")
            historical = "cloudbed-1_q052"

            def replace_window(path):
                with path.open("r", newline="", encoding="utf-8") as inp:
                    reader = csv.DictReader(inp)
                    fields = reader.fieldnames
                    rows = list(reader)
                old = next(r for r in rows if r["case_id"] == historical)
                victim = next(r for r in rows if r["case_id"] == target)
                victim["start_unix"], victim["end_unix"] = (
                    old["start_unix"], old["end_unix"]
                )
                with path.open("w", newline="", encoding="utf-8") as output:
                    writer = csv.DictWriter(output, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(rows)

            replace_window(split)
            replace_window(manifest)
            new_plan = costruisci_piano(split, manifest)
            self.assertNotIn(
                target, {row["case_id"] for row in new_plan["pairs"]}
            )
            self.assertEqual(new_plan["case_count"], 8)

    def test_label_column_rejected(self):
        with TemporaryDirectory() as tmp:
            split, manifest = self.make_inputs(Path(tmp), extra_gt=True)
            with self.assertRaisesRegex(ValueError, "Colonne"):
                costruisci_piano(split, manifest)


if __name__ == "__main__":
    unittest.main(verbosity=2)
