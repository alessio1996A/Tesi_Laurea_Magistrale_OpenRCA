"""Test offline A/4: solo artefatti JSON sintetici, senza Market, GT o API."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.network_feasibility_summary import summarize


class TestNetworkFeasibilitySummary(unittest.TestCase):
    def fixture(self, directory: Path):
        inventory_path = directory / "network_kpi_inventory_v1.json"
        profile_path = directory / "network_signal_profile_v1.json"
        windows = [
            dict(case_id="cloudbed-1_q010", cloudbed="cloudbed-1",
                 start_unix=100, end_unix=200, split="development"),
            dict(case_id="cloudbed-2_q020", cloudbed="cloudbed-2",
                 start_unix=300, end_unix=400, split="development"),
        ]
        inventory = dict(
            audit="network_kpi_inventory_v1",
            read_ground_truth=False,
            read_metric_values=False,
            gemini_calls=0,
            selected_windows=windows,
            development_case_ids_now_seen=[
                "cloudbed-1_q010", "cloudbed-2_q020"
            ],
        )
        inventory_path.write_text(
            json.dumps(inventory), encoding="utf-8"
        )
        data = inventory_path.read_bytes()

        def row(cb, case_id, source, component, kpi,
                minimum, p95, maximum, distinct, decreasing=0, missing=0):
            n = 4 if maximum is not None else 0
            return dict(
                cloudbed=cb, case_id=case_id, source=source,
                cmdb_id=component, kpi_name=kpi,
                unit="non_verificata",
                signal_semantics="non_verificata",
                root_cause_verified=False,
                statistics=dict(
                    rows=n + missing, numeric_samples=n,
                    non_numeric_or_non_finite=missing,
                    distinct_values=distinct, decreasing_steps=decreasing,
                    minimum=minimum, p95=p95, maximum=maximum,
                ),
            )

        profiles = [
            row("cloudbed-1", "cloudbed-1_q010", "metric_node.csv",
                "node-1", "system.net.tcp.retrans_segs",
                0, 0.08, 0.1, 3, decreasing=1),
            row("cloudbed-2", "cloudbed-2_q020", "metric_node.csv",
                "node-2", "system.tcp.retrans_pct",
                0, 0, 0, 1),
            row("cloudbed-1", "cloudbed-1_q010", "metric_container.csv",
                "node-1.svc-0", "container_network_receive_errors.eth0",
                0, 0, 0, 1),
            row("cloudbed-2", "cloudbed-2_q020", "metric_node.csv",
                "node-2", "system.net.packets_in.error",
                0.01, 0.05, 0.1, 3),
            row("cloudbed-1", "cloudbed-1_q010", "metric_mesh.csv",
                "frontend", "istio_request_duration_milliseconds.grpc.200.0.0",
                0, 5.0, 15.0, 3),
            row("cloudbed-1", "cloudbed-1_q010", "metric_mesh.csv",
                "frontend", "istio_requests.grpc.200.0.0",
                1, 3, 4, 3),
            row("cloudbed-2", "cloudbed-2_q020", "metric_container.csv",
                "node-2.svc-0", "container_network_transmit_errors.eth0",
                None, None, None, 0, missing=4),
        ]
        profile = dict(
            audit="network_signal_profile_v1",
            source_inventory_sha256=hashlib.sha256(data).hexdigest(),
            selected_windows=windows,
            development_case_ids_now_seen=inventory["development_case_ids_now_seen"],
            profile_count=len(profiles),
            profiles=profiles,
            ground_truth_read=False,
            gemini_calls=0,
            classification_performed=False,
        )
        profile_path.write_text(json.dumps(profile), encoding="utf-8")
        return inventory_path, profile_path

    def test_summarizes_retransmission_errors_and_duration_separately(self):
        with tempfile.TemporaryDirectory() as temp:
            inventory, profile = self.fixture(Path(temp))
            report = summarize(inventory, profile)
            second = summarize(inventory, profile)
        self.assertEqual(report, second)
        self.assertEqual(report["source_profile_count"], 7)
        self.assertFalse(report["read_ground_truth"])
        self.assertFalse(report["read_market_zip"])
        self.assertFalse(report["classification_performed"])
        self.assertEqual(report["gemini_calls"], 0)
        groups = {
            (r["family"], r["kpi_name"]): r for r in report["group_summary"]
        }
        retrans = groups[("tcp_node_retransmission", "system.net.tcp.retrans_segs")]
        self.assertEqual(retrans["positive_max_profiles"], 1)
        self.assertEqual(retrans["profiles_with_decreases"], 1)
        errors = groups[(
            "container_rx_tx_errors", "container_network_receive_errors.eth0"
        )]
        self.assertEqual(errors["all_zero_profiles"], 1)
        missing = groups[(
            "container_rx_tx_errors", "container_network_transmit_errors.eth0"
        )]
        self.assertEqual(missing["non_numeric_only_profiles"], 1)
        self.assertEqual(missing["all_zero_profiles"], 0)
        duration = groups[(
            "mesh_request_duration", "istio_request_duration_milliseconds.grpc.200.0.0"
        )]
        self.assertEqual(duration["maximum_across_profiles"], 15.0)

    def test_rejects_profile_inventory_sha_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            inventory, profile = self.fixture(Path(temp))
            data = json.loads(inventory.read_text(encoding="utf-8"))
            data["new"] = "modifica dopo la profilazione"
            inventory.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Hash dell'inventario"):
                summarize(inventory, profile)

    def test_rejects_evaluation_windows_even_with_consistent_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            inventory, profile = self.fixture(Path(temp))
            inv = json.loads(inventory.read_text(encoding="utf-8"))
            inv["selected_windows"][0]["split"] = "evaluation"
            inventory.write_text(json.dumps(inv), encoding="utf-8")
            pro = json.loads(profile.read_text(encoding="utf-8"))
            pro["selected_windows"] = inv["selected_windows"]
            pro["source_inventory_sha256"] = hashlib.sha256(
                inventory.read_bytes()
            ).hexdigest()
            profile.write_text(json.dumps(pro), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-development"):
                summarize(inventory, profile)

    def test_rejects_root_cause_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            inventory, profile = self.fixture(Path(temp))
            data = json.loads(profile.read_text(encoding="utf-8"))
            data["profiles"][0]["root_cause_verified"] = True
            profile.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Semantica o causa"):
                summarize(inventory, profile)

    def test_rejects_invalid_statistics(self):
        with tempfile.TemporaryDirectory() as temp:
            inventory, profile = self.fixture(Path(temp))
            data = json.loads(profile.read_text(encoding="utf-8"))
            data["profiles"][0]["statistics"]["maximum"] = -1
            profile.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "contraddittorie"):
                summarize(inventory, profile)

    def test_rejects_duplicate_profiles(self):
        with tempfile.TemporaryDirectory() as temp:
            inventory, profile = self.fixture(Path(temp))
            data = json.loads(profile.read_text(encoding="utf-8"))
            data["profiles"].append(data["profiles"][0])
            data["profile_count"] += 1
            profile.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicato"):
                summarize(inventory, profile)


if __name__ == "__main__":
    unittest.main()
