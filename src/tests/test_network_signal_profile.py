"""Test offline A/3: ZIP e split interamente sintetici."""
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from evaluation.network_kpi_inventory import (
    METRIC_SOURCES, SPLIT_HEADERS, select_audit_windows,
)
from evaluation.network_signal_profile import profile_signals


class TestNetworkSignalProfile(unittest.TestCase):
    def prepare(self, root: Path):
        split = root / "split_market_v1.csv"
        manifest = root / "benchmark_inputs_market.csv"
        with split.open("w", encoding="utf-8") as f:
            f.write("case_id,cloudbed,start_unix,end_unix,split\n")
            for cb in ("cloudbed-1", "cloudbed-2"):
                for n, start, end, partition in [
                    (1, 100, 200, "development"),
                    (2, 200, 300, "development"),
                    (3, 300, 400, "development"),
                    (4, 400, 500, "evaluation"),
                    (5, 450, 550, "development"),
                    (6, 600, 700, "development"),
                ]:
                    f.write(f"{cb}_q{n:03d},{cb},{start},{end},{partition}\n")
        manifest.write_text("GT-free test manifest\n", encoding="utf-8")
        seen = frozenset()
        selected, consumed = select_audit_windows(
            split, per_cloudbed=2, verify_hash=False, seen_case_ids=seen,
        )
        inventory = {
            "audit": "network_kpi_inventory_v1",
            "read_ground_truth": False,
            "read_metric_values": False,
            "gemini_calls": 0,
            "split_sha256": hashlib.sha256(split.read_bytes()).hexdigest(),
            "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "selected_windows": [
                {k: w[k] for k in SPLIT_HEADERS} for w in selected
            ],
            "development_case_ids_now_seen": consumed,
        }
        inventory_path = root / "inventory.json"
        inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
        zpath = root / "Market.zip"
        with zipfile.ZipFile(zpath, "w") as z:
            z.writestr("Market/record.csv", "sensitive\nGROUND_TRUTH_NEVER_READ\n")
            for cb in ("cloudbed-1", "cloudbed-2"):
                for source in METRIC_SOURCES:
                    if source == "metric_container.csv":
                        target = "container_network_receive_errors.eth0"
                    elif source == "metric_node.csv":
                        target = "system.net.tcp.retrans_segs"
                    else:
                        target = "istio_request_duration_milliseconds.http.200."
                    lines = ["timestamp,cmdb_id,kpi_name,value"]
                    lines += [
                        f"150,node-1.svc-0,{target},1",
                        f"155,node-1.svc-0,{target},2",
                        f"250,node-1.svc-0,{target},NaN",
                        f"350,node-1.svc-0,{target},3",
                        f"475,node-1.svc-0,{target},9999999",  # evaluation
                        "150,node-1.svc-0,unlisted_kpi,8888888",
                    ]
                    z.writestr(
                        f"Market/{cb}/telemetry/1970_01_01/metric/{source}",
                        "\n".join(lines) + "\n",
                    )
        return {
            "market_zip": zpath, "split_path": split,
            "manifest_path": manifest, "inventory_path": inventory_path,
            "per_cloudbed": 2, "verify_hashes": False,
            "seen_case_ids": seen,
        }

    def test_profiles_use_only_selected_windows_and_whitelisted_kpis(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.prepare(Path(tmp))
            report = profile_signals(**args)
            again = profile_signals(**args)
        self.assertEqual(report, again)
        self.assertFalse(report["ground_truth_read"])
        self.assertFalse(report["classification_performed"])
        self.assertEqual(report["gemini_calls"], 0)
        self.assertTrue(report["profiles"])
        missing_only = []
        for profile in report["profiles"]:
            stats = profile["statistics"]
            self.assertNotEqual(profile["kpi_name"], "unlisted_kpi")
            self.assertEqual(profile["unit"], "non_verificata")
            self.assertFalse(profile["root_cause_verified"])
            self.assertEqual(
                stats["rows"],
                stats["numeric_samples"] + stats["non_numeric_or_non_finite"],
            )
            if stats["numeric_samples"] > 0:
                self.assertIsNotNone(stats["maximum"])
                self.assertLessEqual(stats["maximum"], 3.0)
            else:
                # NaN non e' uno zero misurato: il profilo e' privo
                # di campioni numerici e deve conservare il valore None.
                self.assertIsNone(stats["minimum"])
                self.assertIsNone(stats["median"])
                self.assertIsNone(stats["maximum"])
                self.assertGreater(stats["non_numeric_or_non_finite"], 0)
                missing_only.append(profile)
        self.assertTrue(missing_only, "La prova sintetica deve coprire NaN")
        rendered = json.dumps(report, allow_nan=False)
        self.assertNotIn("GROUND_TRUTH_NEVER_READ", rendered)
        self.assertNotIn("8888888", rendered)
        self.assertNotIn("9999999", rendered)

    def test_describe_entirely_non_numeric_series(self):
        from evaluation.network_signal_profile import _describe

        stats = _describe([(100, None), (110, None)])
        self.assertEqual(stats["rows"], 2)
        self.assertEqual(stats["numeric_samples"], 0)
        self.assertEqual(stats["non_numeric_or_non_finite"], 2)
        self.assertIsNone(stats["minimum"])
        self.assertIsNone(stats["median"])
        self.assertIsNone(stats["p95"])
        self.assertIsNone(stats["maximum"])

    def test_inventory_selection_tampering_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.prepare(Path(tmp))
            inv_path = args["inventory_path"]
            inv = json.loads(inv_path.read_text(encoding="utf-8"))
            inv["selected_windows"][0]["split"] = "evaluation"
            inv_path.write_text(json.dumps(inv), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Finestre"):
                profile_signals(**args)

    def test_inventory_ground_truth_flag_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.prepare(Path(tmp))
            inv_path = args["inventory_path"]
            inv = json.loads(inv_path.read_text(encoding="utf-8"))
            inv["read_ground_truth"] = True
            inv_path.write_text(json.dumps(inv), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "GT-free"):
                profile_signals(**args)

    def test_missing_telemetry_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.prepare(Path(tmp))
            with zipfile.ZipFile(args["market_zip"], "w") as z:
                z.writestr("irrelevant.csv", "a,b\n1,2\n")
            with self.assertRaises(FileNotFoundError):
                profile_signals(**args)

    def test_manifest_hash_mismatch_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.prepare(Path(tmp))
            args["manifest_path"].write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Hash manifest"):
                profile_signals(**args)


if __name__ == "__main__":
    unittest.main()
