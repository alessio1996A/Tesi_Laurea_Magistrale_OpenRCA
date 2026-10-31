"""Test offline di integrazione dell'adattatore A1-R8 (otto regole).

I dati sono sintetici: non si usano Gemini, ground truth o casi Market.
"""

import json
import unittest

import pandas as pd

from harness.rule_batch import RULE_SPECS, costruisci_evidenze_regole


class TestRuleBatch(unittest.TestCase):
    def setUp(self):
        # Un nodo e un container, con campionamento ogni 60 s per 30 minuti.
        self.start = 1_647_756_000
        self.end = self.start + 1800
        self.container = "node-6.shippingservice-0"
        self.node = "node-6"

        container_records = []
        node_records = []

        for i in range(30):
            timestamp = self.start + i * 60
            cpu_container = (0.2 + 0.015 * (i % 3)) if i < 23 else 5.0
            cpu_node = (6.0 + (i % 3)) if i < 23 else 32.0

            for kpi, value in (
                ("container_cpu_usage_seconds", cpu_container),
                ("container_cpu_cfs_throttled_periods", 5.0),
                ("container_cpu_cfs_periods", 10.0),
                ("container_memory_working_set_MB", 30.0 + 0.2 * (i % 3)),
                ("container_memory_usage_MB", 40.0),
                ("container_spec_memory_limit_MB", 256.0),
                ("container_fs_reads_MB./dev/vda", 0.0),
                ("container_fs_reads./dev/vda", 0.0),
            ):
                container_records.append((timestamp, self.container, kpi, value))

            for kpi, value in (
                ("system.cpu.pct_usage", cpu_node),
                ("system.cpu.iowait", 0.3),
                ("system.mem.pct_usage", 40.0 + 0.1 * (i % 3)),
                ("system.mem.used", 1000.0),
                ("system.disk.pct_usage", 42.0 + 0.01 * (i % 3)),
                ("system.disk.used", 10_000_000_000.0),
            ):
                node_records.append((timestamp, self.node, kpi, value))

        columns = ["timestamp", "cmdb_id", "kpi_name", "value"]
        self.df_container = pd.DataFrame(container_records, columns=columns)
        self.df_node = pd.DataFrame(node_records, columns=columns)

    def evaluate(self):
        return costruisci_evidenze_regole(
            self.df_node, self.df_container, self.start, self.end
        )

    def test_eight_classes_allowlisted(self):
        self.assertEqual(
            [spec[0] for spec in RULE_SPECS],
            ["R01", "R02", "R06", "R07", "R08", "R09", "R10", "R11"],
        )
        self.assertEqual(len({spec[4] for spec in RULE_SPECS}), 8)

    def test_json_determinism(self):
        first = self.evaluate()
        second = self.evaluate()
        self.assertEqual(
            json.dumps(first, allow_nan=False, sort_keys=True),
            json.dumps(second, allow_nan=False, sort_keys=True),
        )

    def test_candidates_and_count(self):
        report = self.evaluate()

        self.assertEqual(report["versione"], "rule_based_A1_R_v1")
        self.assertEqual(len(report["conteggi_per_regola"]), 8)
        self.assertEqual(
            report["finestra"]["baseline_end_unix"],
            self.start + 720,
        )

        candidate_rules = {
            candidate["regola"] for candidate in report["candidati_riportati"]
        }
        self.assertIn("R01", candidate_rules)
        self.assertIn("R07", candidate_rules)
        self.assertEqual(
            report["totale_candidati"],
            len(report["candidati_riportati"]),
        )

        for row in report["conteggi_per_regola"]:
            self.assertEqual(row["componenti_valutati"], 1)
            self.assertEqual(
                sum(
                    row[status]
                    for status in (
                        "candidati",
                        "nessun_candidato",
                        "evidenza_insufficiente",
                    )
                ),
                1,
            )

    def test_budget_does_not_change_counts(self):
        report = costruisci_evidenze_regole(
            self.df_node,
            self.df_container,
            self.start,
            self.end,
            max_candidati_report=1,
        )
        self.assertEqual(len(report["candidati_riportati"]), 1)
        self.assertEqual(
            report["candidati_omessi_per_budget"],
            report["totale_candidati"] - 1,
        )

    def test_empty_telemetry(self):
        empty_nodes = self.df_node.iloc[:0].copy()
        empty_containers = self.df_container.iloc[:0].copy()

        report = costruisci_evidenze_regole(
            empty_nodes, empty_containers, self.start, self.end
        )

        self.assertEqual(report["totale_candidati"], 0)
        self.assertTrue(
            all(
                row["componenti_valutati"] == 0
                for row in report["conteggi_per_regola"]
            )
        )

    def test_invalid_window(self):
        with self.assertRaises(ValueError):
            costruisci_evidenze_regole(
                self.df_node,
                self.df_container,
                self.end,
                self.start,
            )

    def test_window_filter(self):
        # Un nodo fuori finestra non deve entrare nei conteggi.
        extra = pd.DataFrame(
            [(-1, "outside", "system.cpu.pct_usage", 50.0)],
            columns=self.df_node.columns,
        )
        nodes = pd.concat([self.df_node, extra], ignore_index=True)

        report = costruisci_evidenze_regole(
            nodes, self.df_container, self.start, self.end
        )

        # Cerchiamo R07 per identificativo, non per posizione nella lista.
        r07 = next(
            row
            for row in report["conteggi_per_regola"]
            if row["regola"] == "R07"
        )
        self.assertEqual(r07["componenti_valutati"], 1)

    def test_read_write_rules_integrated(self):
        # Simuliamo due aumenti persistenti nello stesso nodo:
        # letture/s (R09) e scritture/s (R10), minuti 15-17.
        records = []

        for i in range(30):
            timestamp = self.start + i * 60
            value = 20.0 if 15 <= i <= 17 else 0.0

            for kpi, metric_value in (
                ("system.io.r_s", value),
                ("system.io.rkb_s", value * 8),
                ("system.io.w_s", value),
                ("system.io.w_await", 0.5),
            ):
                records.append(
                    {
                        "timestamp": timestamp,
                        "cmdb_id": self.node,
                        "kpi_name": kpi,
                        "value": metric_value,
                    }
                )

        nodes = pd.concat(
            [self.df_node, pd.DataFrame(records)],
            ignore_index=True,
        )

        report = costruisci_evidenze_regole(
            nodes, self.df_container, self.start, self.end
        )

        candidates = {
            candidate["regola"]: candidate
            for candidate in report["candidati_riportati"]
        }

        for rule_id in ("R09", "R10"):
            with self.subTest(regola=rule_id):
                self.assertIn(rule_id, candidates)
                self.assertEqual(
                    candidates[rule_id]["timestamp_primo_segnale_unix"],
                    self.start + 15 * 60,
                )
                self.assertEqual(
                    candidates[rule_id]["campioni_consecutivi"], 3
                )
                self.assertIn("kpi_accessorio", candidates[rule_id]["evidenze"])


if __name__ == "__main__":
    unittest.main()
