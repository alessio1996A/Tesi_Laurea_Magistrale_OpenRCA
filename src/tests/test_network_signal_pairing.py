"""Test A/5 offline: nessun Market.zip, label o chiamata Gemini."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.network_signal_pairing import analyze_pairing


class TestNetworkSignalPairing(unittest.TestCase):
    def fixture(self, root: Path):
        inventory = root / "inventory.json"
        profile = root / "profile.json"
        windows = [
            {
                "case_id": "cloudbed-1_q010",
                "cloudbed": "cloudbed-1",
                "start_unix": 100,
                "end_unix": 200,
                "split": "development",
            },
            {
                "case_id": "cloudbed-2_q020",
                "cloudbed": "cloudbed-2",
                "start_unix": 300,
                "end_unix": 400,
                "split": "development",
            },
        ]
        seen = ["cloudbed-1_q010", "cloudbed-2_q020"]
        inv = {
            "audit": "network_kpi_inventory_v1",
            "read_ground_truth": False,
            "read_metric_values": False,
            "gemini_calls": 0,
            "selected_windows": windows,
            "development_case_ids_now_seen": seen,
        }
        inventory.write_text(json.dumps(inv), encoding="utf-8")

        def row(cb, case, source, component, kpi, *,
                minimum=0.0, maximum=1.0, distinct=2, decreases=0):
            return {
                "cloudbed": cb, "case_id": case,
                "source": source, "cmdb_id": component, "kpi_name": kpi,
                "unit": "non_verificata",
                "signal_semantics": "non_verificata",
                "root_cause_verified": False,
                "statistics": {
                    "rows": 4, "numeric_samples": 4,
                    "non_numeric_or_non_finite": 0,
                    "distinct_values": distinct,
                    "decreasing_steps": decreases,
                    "minimum": minimum, "p95": maximum,
                    "maximum": maximum,
                },
            }

        a, b = "cloudbed-1_q010", "cloudbed-2_q020"
        rows = [
            row("cloudbed-1", a, "metric_node.csv", "node-1",
                "system.net.tcp.retrans_segs", maximum=0.4, decreases=2),
            row("cloudbed-1", a, "metric_node.csv", "node-1",
                "system.tcp.retrans_pct", maximum=0.01, distinct=1),
            row("cloudbed-1", a, "metric_node.csv", "node-1",
                "system.net.tcp.in_segs", maximum=12),
            row("cloudbed-1", a, "metric_node.csv", "node-1",
                "system.net.tcp.out_segs", maximum=13),
            row("cloudbed-2", b, "metric_node.csv", "node-2",
                "system.net.tcp.retrans_segs", maximum=0.8),
            row("cloudbed-1", a, "metric_mesh.csv", "frontend",
                "istio_request_duration_milliseconds.grpc.200.0.0",
                maximum=20),
            row("cloudbed-1", a, "metric_mesh.csv", "frontend",
                "istio_requests.grpc.200.0.0", maximum=5),
            row("cloudbed-1", a, "metric_mesh.csv", "frontend",
                "istio_request_duration_milliseconds.http.200.",
                maximum=5),
            row("cloudbed-1", a, "metric_mesh.csv", "frontend",
                "istio_requests.http.200.", maximum=0, distinct=1),
            row("cloudbed-2", b, "metric_mesh.csv", "frontend",
                "istio_request_duration_milliseconds.grpc.200.0.0",
                maximum=15),
            row("cloudbed-2", b, "metric_mesh.csv", "backend",
                "istio_requests.grpc.200.0.0", maximum=10),
        ]
        pro = {
            "audit": "network_signal_profile_v1",
            "source_inventory_sha256": hashlib.sha256(inventory.read_bytes()).hexdigest(),
            "selected_windows": windows,
            "development_case_ids_now_seen": seen,
            "profile_count": len(rows),
            "profiles": rows,
            "ground_truth_read": False,
            "classification_performed": False,
            "gemini_calls": 0,
        }
        profile.write_text(json.dumps(pro), encoding="utf-8")
        return inventory, profile

    def test_pairs_only_matching_node_and_mesh_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            inv, pro = self.fixture(Path(folder))
            result = analyze_pairing(inv, pro)
            again = analyze_pairing(inv, pro)
        self.assertEqual(result, again)
        self.assertEqual(result["source_profile_count"], 11)
        self.assertFalse(result["read_ground_truth"])
        self.assertFalse(result["read_market_zip"])
        self.assertEqual(result["gemini_calls"], 0)
        self.assertFalse(result["classification_performed"])

        n = result["r03_node_pairing"]["total"]
        self.assertEqual(n["r03_pairs_present"], 1)
        self.assertEqual(n["r03_pairs_incomplete"], 1)
        self.assertEqual(n["r03_pairs_both_positive_max"], 1)
        self.assertEqual(n["r03_pairs_with_in_and_out_segs"], 1)
        self.assertEqual(n["r03_retrans_decreasing_profiles"], 1)

        m = result["r05_mesh_pairing"]["total"]
        self.assertEqual(m["matched_duration_request_pairs"], 2)
        self.assertEqual(m["matched_pairs_both_positive_max"], 1)
        self.assertEqual(
            m["matched_pairs_duration_positive_requests_zero_max"], 1
        )
        self.assertEqual(m["unpaired_duration_profiles"], 1)
        self.assertEqual(m["unpaired_request_profiles"], 1)

    def test_mesh_suffix_and_component_mismatch_are_not_joined(self):
        with tempfile.TemporaryDirectory() as folder:
            inv, pro = self.fixture(Path(folder))
            obj = json.loads(pro.read_text(encoding="utf-8"))
            # Lo stesso componente ma un HTTP status diverso.
            for row in obj["profiles"]:
                if row["kpi_name"] == "istio_requests.http.200.":
                    row["kpi_name"] = "istio_requests.http.500."
            pro.write_text(json.dumps(obj), encoding="utf-8")
            result = analyze_pairing(inv, pro)
        m = result["r05_mesh_pairing"]["total"]
        self.assertEqual(m["matched_duration_request_pairs"], 1)
        self.assertEqual(m["unpaired_duration_profiles"], 2)
        self.assertEqual(m["unpaired_request_profiles"], 2)

    def test_rejects_inventory_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            inv, pro = self.fixture(Path(folder))
            obj = json.loads(inv.read_text(encoding="utf-8"))
            obj["tampered"] = True
            inv.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Hash"):
                analyze_pairing(inv, pro)

    def test_rejects_non_development_even_if_hashes_updated(self):
        with tempfile.TemporaryDirectory() as folder:
            inv, pro = self.fixture(Path(folder))
            i = json.loads(inv.read_text(encoding="utf-8"))
            i["selected_windows"][0]["split"] = "evaluation"
            inv.write_text(json.dumps(i), encoding="utf-8")
            p = json.loads(pro.read_text(encoding="utf-8"))
            p["selected_windows"] = i["selected_windows"]
            p["source_inventory_sha256"] = hashlib.sha256(
                inv.read_bytes()
            ).hexdigest()
            pro.write_text(json.dumps(p), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-development"):
                analyze_pairing(inv, pro)

    def test_rejects_unverified_root_cause(self):
        with tempfile.TemporaryDirectory() as folder:
            inv, pro = self.fixture(Path(folder))
            p = json.loads(pro.read_text(encoding="utf-8"))
            p["profiles"][0]["root_cause_verified"] = True
            pro.write_text(json.dumps(p), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Semantica o causa"):
                analyze_pairing(inv, pro)

    def test_rejects_missing_json(self):
        with tempfile.TemporaryDirectory() as folder:
            inv, pro = self.fixture(Path(folder))
            with self.assertRaises(FileNotFoundError):
                analyze_pairing(inv, Path(folder) / "missing.json")


if __name__ == "__main__":
    unittest.main()
