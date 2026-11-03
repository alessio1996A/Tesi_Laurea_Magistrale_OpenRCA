"""Test sintetici offline per la Fase A/2: senza dataset reale, GT o API."""
import csv
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from evaluation.network_kpi_inventory import (
    METRIC_SOURCES,
    inventory_kpis,
    select_audit_windows,
)


class TestNetworkKpiInventory(unittest.TestCase):
    def make_inputs(self, directory):
        root = Path(directory)
        split = root / "split_market_v1.csv"
        manifest = root / "benchmark_inputs_market.csv"
        rows = [
            ("cloudbed-1_q001", "cloudbed-1", 100, 200, "development"),
            ("cloudbed-1_q002", "cloudbed-1", 100, 200, "development"),
            ("cloudbed-1_q003", "cloudbed-1", 200, 300, "development"),
            ("cloudbed-1_q004", "cloudbed-1", 300, 400, "development"),
            ("cloudbed-1_q005", "cloudbed-1", 400, 500, "ood_holdout"),
            ("cloudbed-1_q006", "cloudbed-1", 450, 550, "development"),
            ("cloudbed-1_q007", "cloudbed-1", 600, 700, "development"),
            ("cloudbed-1_q008", "cloudbed-1", 650, 750, "development"),
            ("cloudbed-2_q001", "cloudbed-2", 100, 200, "development"),
            ("cloudbed-2_q002", "cloudbed-2", 200, 300, "development"),
            ("cloudbed-2_q003", "cloudbed-2", 300, 400, "development"),
            ("cloudbed-2_q004", "cloudbed-2", 400, 500, "evaluation"),
            ("cloudbed-2_q005", "cloudbed-2", 450, 550, "development"),
        ]
        with split.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["case_id", "cloudbed", "start_unix", "end_unix", "split"])
            writer.writerows(rows)
        manifest.write_text("synthetic-GT-free-manifest\n", encoding="utf-8")
        return split, manifest

    def make_zip(self, root):
        zpath = Path(root) / "Market.zip"
        with zipfile.ZipFile(zpath, "w") as z:
            z.writestr("Market/record.csv", "secret_ground_truth\nMUST_NOT_READ\n")
            for cb in ("cloudbed-1", "cloudbed-2"):
                for source in METRIC_SOURCES:
                    records = [
                        "timestamp,cmdb_id,kpi_name,value",
                        "150,service-a,container_net_retransmits,SECRET_VALUE",
                        "250,service-a,service_duration,42",
                        "350,service-b,other_metric,8",
                        "475,service-x,HOLDOUT_ONLY_KPI,42",
                        "675,service-y,HISTORICAL_ONLY_KPI,33",
                    ]
                    z.writestr(
                        f"Market/{cb}/telemetry/1970_01_01/metric/{source}",
                        "\n".join(records) + "\n",
                    )
        return zpath

    def test_excludes_holdout_history_and_duplicate_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            split, _ = self.make_inputs(tmp)
            selected, consumed = select_audit_windows(
                split, per_cloudbed=2, verify_hash=False,
                seen_case_ids=frozenset({"cloudbed-1_q007"}),
            )
        self.assertEqual(len(selected), 4)
        self.assertEqual(len({(s["cloudbed"], s["start_unix"]) for s in selected}), 4)
        self.assertNotIn("cloudbed-1_q006", [s["case_id"] for s in selected])
        self.assertNotIn("cloudbed-1_q007", [s["case_id"] for s in selected])
        self.assertNotIn("cloudbed-1_q008", [s["case_id"] for s in selected])
        self.assertNotIn("cloudbed-2_q005", [s["case_id"] for s in selected])
        self.assertEqual(consumed, sorted(consumed))

    def test_inventory_names_only_and_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            split, manifest = self.make_inputs(tmp)
            zpath = self.make_zip(tmp)
            opts = {
                "market_zip": zpath, "split_path": split,
                "manifest_path": manifest, "verify_hashes": False,
                "seen_case_ids": frozenset({"cloudbed-1_q007"}),
                "per_cloudbed": 2,
            }
            first = inventory_kpis(**opts)
            second = inventory_kpis(**opts)
        self.assertEqual(first, second)
        self.assertFalse(first["read_ground_truth"])
        self.assertFalse(first["read_metric_values"])
        self.assertEqual(first["gemini_calls"], 0)
        self.assertEqual(len(first["selected_windows"]), 4)
        output = json.dumps(first)
        self.assertNotIn("HOLDOUT_ONLY_KPI", output)
        self.assertNotIn("HISTORICAL_ONLY_KPI", output)
        self.assertNotIn("SECRET_VALUE", output)
        self.assertNotIn("MUST_NOT_READ", output)
        self.assertTrue(all(
            "metric_" in f for f in first["files_read"]
        ))

    def test_strict_sha256_blocks_unverified_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            split, _ = self.make_inputs(tmp)
            with self.assertRaisesRegex(ValueError, "SHA-256 split"):
                select_audit_windows(
                    split, seen_case_ids=frozenset(),
                )

    def test_rejects_gt_bearing_split_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            split, _ = self.make_inputs(tmp)
            with split.open("r", encoding="utf-8") as f:
                original = f.read()
            split.write_text(
                original.replace("end_unix,split", "end_unix,split,reason"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "ESATTAMENTE"):
                select_audit_windows(
                    split, verify_hash=False, seen_case_ids=frozenset(),
                )

    def test_missing_telemetry_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            split, manifest = self.make_inputs(tmp)
            zpath = Path(tmp) / "Market.zip"
            with zipfile.ZipFile(zpath, "w") as z:
                z.writestr("other_file.txt", "no telemetry")
            with self.assertRaises(FileNotFoundError):
                inventory_kpis(
                    zpath, split, manifest,
                    verify_hashes=False,
                    seen_case_ids=frozenset({"cloudbed-1_q007"}),
                )

    def test_invalid_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            split, _ = self.make_inputs(tmp)
            with self.assertRaises(ValueError):
                select_audit_windows(
                    split, per_cloudbed=0, verify_hash=False,
                    seen_case_ids=frozenset(),
                )


if __name__ == "__main__":
    unittest.main()
