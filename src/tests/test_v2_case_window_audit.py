"""Audit finestre V2: test offline, solo CSV/JSON sintetici."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.v2_case_window_audit import (
    PROTOCOLS,
    audit_case_windows,
)


class CaseWindowAuditTests(unittest.TestCase):
    def make_data(self, root: Path) -> dict:
        processed = root / "data/processed"
        protocols = root / "data/protocols"
        processed.mkdir(parents=True)
        protocols.mkdir(parents=True)
        rows = []
        for cb in ("cloudbed-1", "cloudbed-2"):
            for i in range(1, 11):
                start = 10000 * (1 if cb == "cloudbed-1" else 2) + i * 3600
                # Il pilota 9 ha la stessa finestra del caso 1.
                if i == 9:
                    start = 10000 * (1 if cb == "cloudbed-1" else 2) + 3600
                rows.append({
                    "case_id": f"{cb}_q{i:03d}", "cloudbed": cb,
                    "start_unix": str(start), "end_unix": str(start + 1800),
                    "split": "development" if i <= 9 else "evaluation",
                })
        with (processed / "split_market_v1.csv").open(
            "w", encoding="utf-8", newline=""
        ) as stream:
            writer = csv.DictWriter(
                stream, fieldnames=[
                    "case_id", "cloudbed", "start_unix", "end_unix", "split"
                ]
            )
            writer.writeheader()
            writer.writerows(rows)
        with (processed / "benchmark_inputs_market.csv").open(
            "w", encoding="utf-8", newline=""
        ) as stream:
            fieldnames = [
                "case_id", "cloudbed", "query_index", "task_index",
                "instruction", "start_unix", "end_unix",
            ]
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            for i, row in enumerate(rows):
                writer.writerow({
                    **{k: row[k] for k in (
                        "case_id", "cloudbed", "start_unix", "end_unix"
                    )},
                    "query_index": i,
                    "task_index": "task_1",
                    "instruction": "A failure occurred.",
                })
        import hashlib
        split_hash = hashlib.sha256(
            (processed / "split_market_v1.csv").read_bytes()
        ).hexdigest()
        manifest_hash = hashlib.sha256(
            (processed / "benchmark_inputs_market.csv").read_bytes()
        ).hexdigest()
        for study, protocol in enumerate(PROTOCOLS):
            positions = range(1, 5) if study == 0 else range(5, 9)
            ids = [
                f"{cb}_q{i:03d}"
                for cb in ("cloudbed-1", "cloudbed-2")
                for i in positions
            ]
            previous = (
                ["cloudbed-1_q009", "cloudbed-2_q009"]
                if study == 0 else
                [
                    f"{cb}_q{i:03d}"
                    for cb in ("cloudbed-1", "cloudbed-2")
                    for i in list(range(1, 5)) + [9]
                ]
            )
            plan = {
                "protocol": protocol,
                "split_file_sha256": split_hash,
                "input_manifest_sha256": manifest_hash,
                "run_count": 16,
                "case_count": 8,
                "historical_exclusions": previous,
                "pairs": [
                    {
                        "case_id": name,
                        "cloudbed": name.split("_")[0],
                        "max_tool_rounds": 6,
                        "max_verification_checks": 2,
                    }
                    for name in ids
                ],
            }
            (protocols / (protocol + "_cohort_v1.json")).write_text(
                json.dumps(plan), encoding="utf-8",
            )
        return {
            "data_dir": root,
            "verify_original_hashes": False,
        }

    def test_reports_original_pilot_window_overlap(self):
        with tempfile.TemporaryDirectory() as d:
            result = audit_case_windows(**self.make_data(Path(d)))
        self.assertEqual(result["checked_selected_development_cases"], 16)
        self.assertEqual(result["selected_window_durations_seconds"], [1800])
        self.assertEqual(result["selected_window_overlaps"], [])
        self.assertTrue(any(
            x["case_id"] == "cloudbed-1_q001"
            and x["historical_case_id"] == "cloudbed-1_q009"
            and x["same_window"]
            for x in result["overlaps_with_historical_pilots"]
        ))
        self.assertFalse(result["read_ground_truth"])
        self.assertFalse(result["read_predictions"])
        self.assertEqual(result["gemini_calls"], 0)

    def test_split_manifest_disagreement_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.make_data(Path(d))
            path = Path(d) / "data/processed/benchmark_inputs_market.csv"
            content = path.read_text(encoding="utf-8")
            path.write_text(content.replace("cloudbed-1_q001", "wrong-id", 1),
                            encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Insieme case_id"):
                audit_case_windows(**args)

    def test_non_development_case_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.make_data(Path(d))
            path = Path(d) / "data/protocols" / (PROTOCOLS[0] + "_cohort_v1.json")
            plan = json.loads(path.read_text(encoding="utf-8"))
            plan["pairs"][0]["case_id"] = "cloudbed-1_q010"
            path.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non development"):
                audit_case_windows(**args)

    def test_selected_window_collision_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.make_data(Path(d))
            # Modifichiamo assieme split, manifest e hash dei piani
            # per verificare l'invariante di indipendenza delle finestre.
            split = Path(d) / "data/processed/split_market_v1.csv"
            manifest = Path(d) / "data/processed/benchmark_inputs_market.csv"
            split_text = split.read_text(encoding="utf-8")
            manifest_text = manifest.read_text(encoding="utf-8")
            # Caso 2 assume la stessa finestra del caso 1.
            split_text = split_text.replace(
                "cloudbed-1_q002,cloudbed-1,17200,19000",
                "cloudbed-1_q002,cloudbed-1,13600,15400",
            )
            manifest_text = manifest_text.replace(
                "cloudbed-1_q002", "cloudbed-1_q002", 1
            ).replace(",17200,19000", ",13600,15400", 1)
            split.write_text(split_text, encoding="utf-8")
            manifest.write_text(manifest_text, encoding="utf-8")
            import hashlib
            for protocol in PROTOCOLS:
                path = Path(d) / "data/protocols" / (protocol + "_cohort_v1.json")
                plan = json.loads(path.read_text(encoding="utf-8"))
                plan["split_file_sha256"] = hashlib.sha256(split.read_bytes()).hexdigest()
                plan["input_manifest_sha256"] = hashlib.sha256(manifest.read_bytes()).hexdigest()
                path.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sovrapposte"):
                audit_case_windows(**args)

    def test_original_hashes_fail_closed_on_synthetic_input(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.make_data(Path(d))
            args["verify_original_hashes"] = True
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                audit_case_windows(**args)

    def test_label_bearing_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.make_data(Path(d))
            path = Path(d) / "data/processed/benchmark_inputs_market.csv"
            contents = path.read_text(encoding="utf-8")
            path.write_text(contents.replace(
                "case_id,cloudbed,query_index",
                "case_id,ground_truth,cloudbed,query_index",
            ), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Schema GT-free"):
                audit_case_windows(**args)


if __name__ == "__main__":
    unittest.main()
