"""Offline tests for the six-rule A1-R adapter (no model, no labels)."""
import json
import unittest

import pandas as pd

from harness.rule_batch import RULE_SPECS, costruisci_evidenze_regole


class TestRuleBatch(unittest.TestCase):
    def setUp(self):
        # One component/node, one-minute sampling, 30-minute window.
        # Positive candidate traces: CPU node and container after minute 23.
        start = 1_647_756_000
        self.start = start
        self.end = start + 1800
        self.container = "node-6.shippingservice-0"
        self.node = "node-6"
        container_records = []
        node_records = []
        for i in range(30):
            ts = start + i * 60
            cpu = (0.2 + 0.015 * (i % 3)) if i < 23 else 5.0
            for kpi, value in (
                ("container_cpu_usage_seconds", cpu),
                ("container_cpu_cfs_throttled_periods", 5.0),
                ("container_cpu_cfs_periods", 10.0),
                ("container_memory_working_set_MB", 30.0 + 0.2 * (i % 3)),
                ("container_memory_usage_MB", 40.0),
                ("container_spec_memory_limit_MB", 256.0),
                ("container_fs_reads_MB./dev/vda", 0.0),
                ("container_fs_reads./dev/vda", 0.0),
            ):
                container_records.append((ts, self.container, kpi, value))
            for kpi, value in (
                ("system.cpu.pct_usage", 6.0 + (i % 3)) if i < 23 else ("system.cpu.pct_usage", 32.0),
                ("system.cpu.iowait", 0.3),
                ("system.mem.pct_usage", 40.0 + 0.1 * (i % 3)),
                ("system.mem.used", 1000.0),
                ("system.disk.pct_usage", 42.0 + 0.01 * (i % 3)),
                ("system.disk.used", 10_000_000_000.0),
            ):
                node_records.append((ts, self.node, kpi, value))
        self.df_container = pd.DataFrame(container_records, columns=["timestamp", "cmdb_id", "kpi_name", "value"])
        self.df_node = pd.DataFrame(node_records, columns=["timestamp", "cmdb_id", "kpi_name", "value"])

    def evaluate(self):
        return costruisci_evidenze_regole(self.df_node, self.df_container, self.start, self.end)

    def test_six_classes_allowlisted(self):
        self.assertEqual([x[0] for x in RULE_SPECS], ["R01", "R02", "R06", "R07", "R08", "R11"])
        self.assertEqual(len({x[4] for x in RULE_SPECS}), 6)

    def test_json_determinism(self):
        a, b = self.evaluate(), self.evaluate()
        self.assertEqual(json.dumps(a, allow_nan=False, sort_keys=True), json.dumps(b, allow_nan=False, sort_keys=True))

    def test_candidates_and_count(self):
        report = self.evaluate()
        self.assertEqual(report["versione"], "rule_based_A1_R_v0")
        self.assertEqual(len(report["conteggi_per_regola"]), 6)
        self.assertEqual(report["finestra"]["baseline_end_unix"], self.start + 720)
        self.assertIn("R01", {c["regola"] for c in report["candidati_riportati"]})
        self.assertIn("R07", {c["regola"] for c in report["candidati_riportati"]})
        self.assertEqual(report["totale_candidati"], len(report["candidati_riportati"]))
        for row in report["conteggi_per_regola"]:
            self.assertEqual(row["componenti_valutati"], 1)
            self.assertEqual(sum(row[s] for s in ("candidati", "nessun_candidato", "evidenza_insufficiente")), 1)

    def test_budget_does_not_change_counts(self):
        report = costruisci_evidenze_regole(self.df_node, self.df_container, self.start, self.end, max_candidati_report=1)
        self.assertEqual(len(report["candidati_riportati"]), 1)
        self.assertEqual(report["candidati_omessi_per_budget"], report["totale_candidati"] - 1)

    def test_empty_telemetry(self):
        c = self.df_container.iloc[:0].copy()
        n = self.df_node.iloc[:0].copy()
        report = costruisci_evidenze_regole(n, c, self.start, self.end)
        self.assertEqual(report["totale_candidati"], 0)
        self.assertTrue(all(row["componenti_valutati"] == 0 for row in report["conteggi_per_regola"]))

    def test_invalid_window(self):
        with self.assertRaises(ValueError):
            costruisci_evidenze_regole(self.df_node, self.df_container, self.end, self.start)

    def test_window_filter(self):
        extra = pd.DataFrame([(-1, "outside", "system.cpu.pct_usage", 50.0)], columns=self.df_node.columns)
        report = costruisci_evidenze_regole(pd.concat([self.df_node, extra]), self.df_container, self.start, self.end)
        self.assertEqual(report["conteggi_per_regola"][3]["componenti_valutati"], 1)


if __name__ == "__main__":
    unittest.main()
