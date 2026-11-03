"""Test offline A/6 — dataset e ZIP artificiali, senza etichette o API."""
import csv
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from evaluation.network_kpi_inventory import SPLIT_HEADERS, select_audit_windows
from evaluation.network_temporal_alignment import analyze_temporal_alignment


class TestNetworkTemporalAlignment(unittest.TestCase):
    def fixture(self, root: Path) -> dict:
        folder = root / "data" / "processed"
        folder.mkdir(parents=True)
        split = folder / "split_market_v1.csv"
        manifest = folder / "benchmark_inputs_market.csv"
        rows = []
        for cb in ("cloudbed-1", "cloudbed-2"):
            rows.extend([
                (f"{cb}_q001", cb, 100, 200, "development"),
                (f"{cb}_q002", cb, 200, 300, "development"),
                (f"{cb}_q003", cb, 400, 500, "ood_holdout"),
            ])
        with split.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(SPLIT_HEADERS)
            writer.writerows(rows)
        manifest.write_text("GT-free synthetic\n", encoding="utf-8")
        selected, consumed = select_audit_windows(
            split, per_cloudbed=2, verify_hash=False, seen_case_ids=frozenset(),
        )
        windows = [{k: w[k] for k in SPLIT_HEADERS} for w in selected]
        inventory = root / "inventory.json"
        inv = {
            "audit": "network_kpi_inventory_v1",
            "read_ground_truth": False,
            "read_metric_values": False,
            "gemini_calls": 0,
            "selected_windows": windows,
            "development_case_ids_now_seen": consumed,
            "split_sha256": hashlib.sha256(split.read_bytes()).hexdigest(),
            "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        }
        inventory.write_text(json.dumps(inv), encoding="utf-8")

        profiles = []
        for w in selected:
            for source, name in (
                ("metric_node.csv", "system.net.tcp.retrans_segs"),
                ("metric_mesh.csv", "istio_requests.grpc.200.0.0"),
            ):
                profiles.append({
                    "cloudbed": w["cloudbed"], "case_id": w["case_id"],
                    "source": source, "cmdb_id": "node-1" if source == "metric_node.csv" else "svc1",
                    "kpi_name": name,
                    "unit": "non_verificata",
                    "signal_semantics": "non_verificata",
                    "root_cause_verified": False,
                    "statistics": {
                        "rows": 2, "numeric_samples": 2,
                        "non_numeric_or_non_finite": 0,
                        "distinct_values": 2, "decreasing_steps": 0,
                        "minimum": 0, "p95": 2, "maximum": 3,
                    },
                })
        profile = root / "profile.json"
        pro = {
            "audit": "network_signal_profile_v1",
            "source_inventory_sha256": hashlib.sha256(inventory.read_bytes()).hexdigest(),
            "selected_windows": windows,
            "development_case_ids_now_seen": consumed,
            "profile_count": len(profiles),
            "profiles": profiles,
            "ground_truth_read": False,
            "classification_performed": False,
            "gemini_calls": 0,
        }
        profile.write_text(json.dumps(pro), encoding="utf-8")

        pairing = root / "pairing.json"
        pair = {
            "audit": "network_signal_pairing_v1",
            "input_inventory_sha256": hashlib.sha256(inventory.read_bytes()).hexdigest(),
            "input_profile_sha256": hashlib.sha256(profile.read_bytes()).hexdigest(),
            "source_windows": windows,
            "read_ground_truth": False,
            "read_market_zip": False,
            "classification_performed": False,
            "gemini_calls": 0,
        }
        pairing.write_text(json.dumps(pair), encoding="utf-8")

        node_lines = [
            "timestamp,cmdb_id,kpi_name,value",
            "110,node-1,system.net.tcp.retrans_segs,2",
            "110,node-1,system.tcp.retrans_pct,0.01",
            "110,node-1,system.net.tcp.in_segs,9",
            "110,node-1,system.net.tcp.out_segs,12",
            "120,node-1,system.net.tcp.retrans_segs,2",
            "125,node-1,system.tcp.retrans_pct,0.02",
            "140,node-1,system.net.tcp.retrans_segs,2",
            "140,node-1,system.net.tcp.retrans_segs,3",
            "140,node-1,system.tcp.retrans_pct,0.02",
            "150,node-1,system.net.tcp.retrans_segs,NaN",
            "150,node-1,system.tcp.retrans_pct,0.02",
            "210,node-1,system.net.tcp.retrans_segs,1",
            "210,node-1,system.tcp.retrans_pct,0",
            "220,node-1,system.tcp.retrans_pct,NaN",
            "400,node-1,system.net.tcp.retrans_segs,9999999",
            "400,node-1,system.tcp.retrans_pct,9999999",
        ]
        mesh_lines = [
            "timestamp,cmdb_id,kpi_name,value",
            "110,svc1,istio_request_duration_milliseconds.grpc.200.0.0,8",
            "110,svc1,istio_requests.grpc.200.0.0,4",
            "120,svc1,istio_request_duration_milliseconds.grpc.200.0.0,9",
            "125,svc1,istio_requests.grpc.200.0.0,5",
            "210,svc1,istio_request_duration_milliseconds.grpc.200.0.0,0",
            "210,svc1,istio_requests.grpc.200.0.0,0",
            "220,svc1,istio_request_duration_milliseconds.grpc.200.0.0,5",
            "220,svc2,istio_requests.grpc.200.0.0,5",
            "400,svc1,istio_request_duration_milliseconds.grpc.200.0.0,9999999",
            "400,svc1,istio_requests.grpc.200.0.0,9999999",
        ]
        with zipfile.ZipFile(root / "Market.zip", "w") as archive:
            archive.writestr("Market/record.csv", "secret\nGT_MUST_NOT_READ\n")
            for cb in ("cloudbed-1", "cloudbed-2"):
                prefix = f"Market/{cb}/telemetry/1970_01_01/metric/"
                archive.writestr(prefix + "metric_node.csv", "\n".join(node_lines) + "\n")
                archive.writestr(prefix + "metric_mesh.csv", "\n".join(mesh_lines) + "\n")

        return {
            "data_dir": root, "inventory_path": inventory,
            "profile_path": profile, "pairing_path": pairing,
            "verify_hashes": False, "seen_case_ids": frozenset(),
        }

    def test_exact_timestamp_and_component_matching(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.fixture(Path(tmp))
            report = analyze_temporal_alignment(**args)
            again = analyze_temporal_alignment(**args)
        self.assertEqual(report, again)
        self.assertFalse(report["read_ground_truth"])
        self.assertTrue(report["read_market_zip"])
        self.assertEqual(report["new_case_count"], 0)
        self.assertEqual(report["gemini_calls"], 0)
        r03 = report["r03"]["total"]
        self.assertEqual(r03["exact_timestamp_pairs"], 8)
        self.assertEqual(r03["both_numeric_pairs"], 4)
        self.assertEqual(r03["both_positive_same_timestamp"], 2)
        self.assertEqual(r03["first_positive_second_nonpositive"], 2)
        self.assertEqual(r03["ambiguous_duplicate_pairs"], 2)
        self.assertEqual(r03["non_numeric_pairs"], 2)
        self.assertEqual(r03["timestamp_pairs_with_both_context_kpis"], 2)
        r05 = report["r05"]["total"]
        self.assertEqual(r05["exact_timestamp_pairs"], 4)
        self.assertEqual(r05["both_numeric_pairs"], 4)
        self.assertEqual(r05["both_positive_same_timestamp"], 2)
        self.assertEqual(r05["neither_positive"], 2)
        # Vietato serializzare o persino considerare valori holdout.
        serialized = json.dumps(report)
        self.assertNotIn("9999999", serialized)
        self.assertNotIn("GT_MUST_NOT_READ", serialized)
        self.assertEqual(len(report["metric_files_read"]), 4)

    def test_refuses_altered_pairing_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.fixture(Path(tmp))
            p = args["pairing_path"]
            obj = json.loads(p.read_text(encoding="utf-8"))
            obj["input_profile_sha256"] = "wrong"
            p.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Provenienza A/5"):
                analyze_temporal_alignment(**args)

    def test_refuses_non_development_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.fixture(Path(tmp))
            inv = args["inventory_path"]
            obj = json.loads(inv.read_text(encoding="utf-8"))
            obj["selected_windows"][0]["split"] = "evaluation"
            inv.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(ValueError):
                analyze_temporal_alignment(**args)

    def test_refuses_wrong_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.fixture(Path(tmp))
            manifest = args["data_dir"] / "data/processed/benchmark_inputs_market.csv"
            manifest.write_text("TAMPERED", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Hash manifest"):
                analyze_temporal_alignment(**args)

    def test_fails_closed_when_csv_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.fixture(Path(tmp))
            with zipfile.ZipFile(args["data_dir"] / "Market.zip", "w") as archive:
                archive.writestr("Market/record.csv", "GT\nfoo\n")
            with self.assertRaises(FileNotFoundError):
                analyze_temporal_alignment(**args)

    def test_strict_split_sha_blocks_fabricated_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.fixture(Path(tmp))
            args["verify_hashes"] = True
            with self.assertRaisesRegex(ValueError, "SHA-256 split"):
                analyze_temporal_alignment(**args)


if __name__ == "__main__":
    unittest.main()
