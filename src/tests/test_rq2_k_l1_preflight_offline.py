"""Test sintetici del preflight L1 (nessun dato reale, nessuna API, nessun sigillato)."""
from __future__ import annotations

import copy
import tempfile
import unittest
import zipfile
from pathlib import Path

import pandas as pd

from agent.tools import _get_telemetry_csv_paths
from evaluation import rq2_fault_type_eval_policy as policy
from evaluation import rq2_k_catalog as cat
from evaluation import rq2_k_l1_preflight as pf

START = 1647748800                 # 12:00 a Shanghai: la storia di poche ore resta nello stesso giorno
WINDOW = 1800
END = START + WINDOW

NODE_KPIS = ("system.cpu.pct_usage", "system.cpu.iowait", "system.mem.used", "ping.can_connect")
CONTAINER_KPIS = ("container_start_time_seconds", "container_fs_writes./dev/vda",
                  "container_fs_writes_MB./dev/vda", "container_cpu_cfs_throttled_periods",
                  "container_network_receive_packets_dropped.eth0",
                  "container_network_receive_packets.eth0", "container_memory_usage_MB")


def _catalog(cases=("cloudbed-1_q032",)):
    levels = {"node": NODE_KPIS, "container": CONTAINER_KPIS}
    per_case = {c: {"cloudbed": "cloudbed-1", "window_seconds": WINDOW,
                    "components_total": {"node": 3, "container": 5},
                    "levels": {lv: {k: {"components": 4 if lv == "container" else 3,
                                        "step_seconds": 60.0, "coverage_min": 1.0,
                                        "coverage_median": 1.0} for k in kpis}
                               for lv, kpis in levels.items()}} for c in cases}
    aggregate = {lv: {k: {"cloudbeds": ["cloudbed-1"], "cases": list(cases), "step_seconds": 60.0,
                          "coverage_min": 1.0, "components_missing_max": 1} for k in kpis}
                 for lv, kpis in levels.items()}
    return {"version": "t", "cases": list(cases), "per_case": per_case, "aggregate": aggregate,
            "median_step_seconds_by_level": {"node": 60.0, "container": 60.0}}


def _cond(metric, operator=">", threshold=1.0, aggregation="last", window=300, unit="s"):
    return {"metric": metric, "operator": operator, "threshold": threshold, "unit": unit,
            "aggregation": aggregation, "window_seconds": window}


def _rule(conds, combination="all", fault="container process termination", name="regola"):
    return {"status": "candidate", "combination": combination, "conditions": conds,
            "hypothesized_fault_type": fault, "rule_name": name, "pseudocode": "ignorato"}


def _entry(rule, stage_id="p:case:gemini:A1:K", outcome="candidate"):
    return {"stage_id": stage_id, "case_id": "cloudbed-1_q032", "model": "gemini",
            "harness": "A1", "stage": "K", "record_status": "RECORDED_COMPLETE",
            "rule": rule if outcome == "candidate" else None, "outcome": outcome}


def _classify(conds, **kwargs):
    catalog = _catalog()
    return pf.classify_candidate(_entry(_rule(conds, **kwargs)), catalog, pf.kpi_level_map(catalog))


class LevelMapAndFamilyTests(unittest.TestCase):
    def test_class_names_are_the_four_official_ones(self):
        self.assertEqual(pf.CLASSES, policy.CANONICAL)

    def test_level_map_is_read_from_the_catalog(self):
        levels = pf.kpi_level_map(_catalog())
        self.assertEqual(levels["system.cpu.pct_usage"], "node")
        self.assertEqual(levels["container_start_time_seconds"], "container")

    def test_a_kpi_in_both_levels_is_an_error(self):
        catalog = _catalog()
        catalog["aggregate"]["node"]["container_memory_usage_MB"] = {}
        with self.assertRaises(pf.CatalogLevelError):
            pf.kpi_level_map(catalog)

    def test_empty_or_unknown_level_catalog_is_an_error(self):
        with self.assertRaises(pf.CatalogLevelError):
            pf.kpi_level_map({"aggregate": {}})
        with self.assertRaises(pf.CatalogLevelError):
            pf.kpi_level_map({"aggregate": {"service": {"mrt": {}}}})

    def test_families(self):
        cases = {("system.cpu.pct_usage", "node"): "node_cpu_usage",
                 ("system.cpu.iowait", "node"): "node_cpu_iowait",
                 ("system.mem.used", "node"): "node_other",
                 ("container_start_time_seconds", "container"): "container_start_time",
                 ("container_fs_writes./dev/vda", "container"): "container_fs_write",
                 ("container_fs_writes_MB./dev/vda", "container"): "container_fs_write",
                 ("container_fs_reads./dev/vda", "container"): "container_other",
                 ("container_network_receive_packets_dropped.eth0", "container"): "container_network_loss",
                 ("container_network_transmit_errors.eth0", "container"): "container_network_loss",
                 ("container_network_receive_packets.eth0", "container"): "container_network_other",
                 ("container_cpu_cfs_throttled_periods", "container"): "container_cpu_cfs"}
        for (kpi, level), expected in cases.items():
            self.assertEqual(pf.kpi_family(kpi, level)["id"], expected, kpi)

    def test_ping_can_connect_is_explicitly_a_node_kpi_without_direct_signature(self):
        family = pf.kpi_family("ping.can_connect", "node")
        self.assertEqual(family["id"], "node_ping_can_connect")
        self.assertEqual(family["classes"], ())
        self.assertIsNone(pf.kpi_family("ping.can_connect", "container"))

    def test_semantic_table_hash_is_the_frozen_one(self):
        # Se questo test fallisce la tabella e' cambiata dopo il congelamento: serve un nuovo freeze.
        self.assertEqual(pf.semantic_table_sha256(), "642b9d2c5f3bfd1b6bb70fe93d4410e142b0addf99c301ce34055ee87289c981")

    def test_the_restart_rule_carries_the_caveat(self):
        row = _classify([_cond("container_start_time_seconds")])
        self.assertEqual(len(row["caveats"]), 1)
        self.assertIn("RIAVVIO OSSERVABILE", row["caveats"][0])
        self.assertIn("non dimostra", row["caveats"][0])
        self.assertEqual(_classify([_cond("system.cpu.iowait")])["caveats"], [])

    def test_level_matters_and_unknown_names_have_no_family(self):
        self.assertIsNone(pf.kpi_family("system.cpu.pct_usage", "container"))
        self.assertIsNone(pf.kpi_family("qualcosa", "node"))

    def test_family_coverage_lists_every_catalog_kpi_once(self):
        coverage = pf.family_coverage(_catalog())
        listed = [k for kpis in coverage["by_family"].values() for k in kpis]
        self.assertEqual(sorted(listed), sorted(NODE_KPIS + CONTAINER_KPIS))
        self.assertEqual(coverage["unmatched"], [])

    def test_semantic_table_hash_is_stable(self):
        self.assertEqual(pf.semantic_table_sha256(), pf.semantic_table_sha256())
        self.assertEqual(len(pf.semantic_table_sha256()), 64)


class ClassificationTests(unittest.TestCase):
    def test_start_time_rule_is_formalizable_for_process_termination(self):
        row = _classify([_cond("container_start_time_seconds", ">", 0, "delta", 600)])
        self.assertEqual(row["l1_outcome"], pf.FORMALIZABLE)
        self.assertTrue(row["executable"])
        self.assertEqual(row["classes"], [pf.C_PROCESS])
        self.assertEqual(row["required_history_seconds"], 600)

    def test_two_kpis_of_the_same_class_stay_formalizable(self):
        row = _classify([_cond("container_fs_writes./dev/vda"), _cond("container_fs_writes_MB./dev/vda")])
        self.assertEqual((row["l1_outcome"], row["classes"]), (pf.FORMALIZABLE, [pf.C_WRITE_IO]))

    def test_node_cpu_usage_maps_to_node_cpu_spike(self):
        row = _classify([_cond("system.cpu.pct_usage", threshold=90, unit="pct")])
        self.assertEqual((row["l1_outcome"], row["classes"]), (pf.FORMALIZABLE, [pf.C_NODE_CPU]))

    def test_iowait_is_executable_but_not_classifiable(self):
        row = _classify([_cond("system.cpu.iowait", threshold=20, unit="pct")])
        self.assertEqual(row["l1_outcome"], pf.NOT_CLASSIFIABLE)
        self.assertTrue(row["executable"])
        self.assertIn("nessuna_firma_diretta", row["reason"])

    def test_cfs_throttling_is_not_classifiable(self):
        row = _classify([_cond("container_cpu_cfs_throttled_periods", aggregation="delta")])
        self.assertEqual(row["l1_outcome"], pf.NOT_CLASSIFIABLE)

    def test_conflicting_classes_are_not_classifiable(self):
        row = _classify([_cond("container_start_time_seconds"), _cond("container_fs_writes./dev/vda")])
        self.assertEqual(row["l1_outcome"], pf.NOT_CLASSIFIABLE)
        self.assertIn("classi_in_conflitto", row["reason"])

    def test_one_condition_without_signature_blocks_the_class(self):
        row = _classify([_cond("container_start_time_seconds"), _cond("container_memory_usage_MB", unit="MB")])
        self.assertEqual(row["l1_outcome"], pf.NOT_CLASSIFIABLE)

    def test_kpi_outside_the_catalog_is_not_formalizable_and_named(self):
        row = _classify([_cond("mrt_max"), _cond("container_start_time_seconds")])
        self.assertEqual(row["l1_outcome"], pf.NOT_FORMALIZABLE)
        self.assertFalse(row["executable"])
        self.assertIn("mrt_max", row["reason"])
        self.assertNotIn("container_start_time_seconds", row["reason"])

    def test_mixed_levels_are_not_formalizable(self):
        row = _classify([_cond("system.cpu.pct_usage"), _cond("container_start_time_seconds")])
        self.assertEqual(row["l1_outcome"], pf.NOT_FORMALIZABLE)
        self.assertIn("livelli_misti", row["reason"])

    def test_rule_refused_by_the_executor_is_reported_not_raised(self):
        row = _classify([_cond("container_start_time_seconds", operator="!=")])
        self.assertEqual(row["l1_outcome"], pf.NOT_FORMALIZABLE)
        self.assertIn("regola_rifiutata_dall_esecutore", row["reason"])

    def test_the_llm_hypothesis_is_provenance_only(self):
        conds = [_cond("container_start_time_seconds")]
        a = _classify(conds, fault="container process termination")
        b = _classify(conds, fault="container packet loss")
        self.assertEqual((a["l1_outcome"], a["classes"]), (b["l1_outcome"], b["classes"]))
        self.assertEqual(b["hypothesized_fault_type"], "container packet loss")

    def test_no_label_or_ground_truth_field_in_the_row(self):
        row = _classify([_cond("container_start_time_seconds")])
        forbidden = ("gt", "label", "truth", "reference", "reason_gt", "scoring")
        self.assertFalse([k for k in row if any(h == k.lower() for h in forbidden)])

    def test_components_per_case_come_from_the_catalog(self):
        row = _classify([_cond("container_start_time_seconds")])
        self.assertEqual(row["conditions"][0]["components_per_case"]["cloudbed-1_q032"],
                         {"with_kpi": 4, "components_total": 5})


class UnitTests(unittest.TestCase):
    def test_unit_checks(self):
        self.assertEqual(pf.unit_check("system.cpu.pct_usage", "pct"), "coerente")
        self.assertEqual(pf.unit_check("system.cpu.pct_usage", "%"), "coerente")
        self.assertEqual(pf.unit_check("container_memory_usage_MB", "MB"), "coerente")
        self.assertEqual(pf.unit_check("container_start_time_seconds", "s"), "coerente")
        self.assertTrue(pf.unit_check("system.cpu.pct_usage", "MB").startswith("incoerente"))
        self.assertEqual(pf.unit_check("system.io.w_s", "count"), "non_verificabile_dal_nome")


class TableTests(unittest.TestCase):
    def _entries(self):
        return [_entry(_rule([_cond("container_start_time_seconds")]), "p:a:gemini:A1:K"),
                _entry(_rule([_cond("system.cpu.iowait")]), "p:b:gemini:A1:K"),
                _entry(_rule([_cond("mrt_max")]), "p:c:gemini:A1:K"),
                _entry(None, "p:d:gemini:A1:K", outcome="insufficient_evidence")]

    def test_counts_only_candidates_and_executable_lists(self):
        table = pf.build_table(self._entries(), _catalog())
        self.assertEqual(table["candidates"], 3)
        self.assertEqual(table["outcome_counts"], {pf.FORMALIZABLE: 1, pf.NOT_CLASSIFIABLE: 1,
                                                   pf.NOT_FORMALIZABLE: 1})
        self.assertEqual(sum(1 for r in table["rows"] if r["executable"]), 2)

    def test_fingerprints_are_deterministic_and_react_to_a_rule_change(self):
        first = pf.build_table(self._entries(), _catalog())
        second = pf.build_table(self._entries(), _catalog())
        self.assertEqual(first["executable_sha256"], second["executable_sha256"])
        changed = self._entries()
        changed[0]["rule"]["conditions"][0]["threshold"] = 2.0
        third = pf.build_table(changed, _catalog())
        self.assertNotEqual(first["executable_sha256"], third["executable_sha256"])
        self.assertNotEqual(first["l2_ready_sha256"], third["l2_ready_sha256"])

    def test_inputs_are_not_mutated(self):
        entries, catalog = self._entries(), _catalog()
        before = copy.deepcopy((entries, catalog))
        pf.build_table(entries, catalog)
        self.assertEqual(before, (entries, catalog))

    def test_render_mentions_outcomes_and_semantic_table(self):
        text = pf.render_table(pf.build_table(self._entries(), _catalog()))
        for needle in (pf.FORMALIZABLE, pf.NOT_CLASSIFIABLE, pf.NOT_FORMALIZABLE,
                       "mrt_max", pf.SEMANTIC_TABLE_VERSION, "container_start_time", "CAUTELA"):
            self.assertIn(needle, text)


class ProfileTests(unittest.TestCase):
    def _frame(self, rows):
        return pd.DataFrame(rows, columns=cat.COLUMNS)

    def _series(self, cmdb, kpi, first, last, step=60, value=lambda i: 1.0):
        return [{"timestamp": t, "cmdb_id": cmdb, "kpi_name": kpi, "value": value(i)}
                for i, t in enumerate(range(first, last, step))]

    def test_history_and_first_window(self):
        kpi = "container_start_time_seconds"
        rows = (self._series("c1", kpi, START - 600, END) + self._series("c2", kpi, START, END))
        prof = pf.profile_kpi(self._frame(rows), kpi, start_unix=START, window_seconds=600)
        self.assertEqual(prof["components_with_kpi"], 2)
        self.assertEqual(prof["components_with_sample_in_first_window"], 2)
        self.assertEqual(prof["components_with_full_history"], 1)      # c2 inizia a START

    def test_missing_kpi_gives_zeros_not_an_exception(self):
        prof = pf.profile_kpi(self._frame([]), "assente", start_unix=START, window_seconds=300)
        self.assertEqual(prof["components_with_kpi"], 0)
        self.assertIsNone(prof["value_max"])

    def test_cumulative_counter_hint(self):
        rows = self._series("c1", "k", START - 600, END, value=lambda i: float(i))
        prof = pf.profile_kpi(self._frame(rows), "k", start_unix=START, window_seconds=600)
        self.assertTrue(prof["cumulative_counter_hint"])
        flat = self._series("c1", "k", START - 600, END, value=lambda i: 3.0)
        self.assertFalse(pf.profile_kpi(self._frame(flat), "k", start_unix=START,
                                        window_seconds=600)["cumulative_counter_hint"])

    def test_constant_series_with_different_values_per_component_is_not_a_counter(self):
        # Istante di avvio: costante in ogni componente, diverso tra componenti.
        rows = (self._series("c1", "k", START - 600, END, value=lambda i: 1000.0)
                + self._series("c2", "k", START - 600, END, value=lambda i: 2000.0))
        prof = pf.profile_kpi(self._frame(rows), "k", start_unix=START, window_seconds=600)
        self.assertFalse(prof["cumulative_counter_hint"])
        self.assertEqual(prof["rising_series_fraction"], 0.0)

    def test_a_restart_makes_the_series_not_monotone(self):
        values = [1.0, 2.0, 3.0, 0.0, 1.0]
        rows = self._series("c1", "k", START, START + 300, value=lambda i: values[i])
        self.assertFalse(pf.profile_kpi(self._frame(rows), "k", start_unix=START,
                                        window_seconds=60)["cumulative_counter_hint"])

    def test_non_finite_values_are_ignored(self):
        rows = self._series("c1", "k", START, START + 300, value=lambda i: float("nan") if i == 0 else 2.0)
        prof = pf.profile_kpi(self._frame(rows), "k", start_unix=START, window_seconds=60)
        self.assertEqual(prof["value_min"], 2.0)

    def test_threshold_check(self):
        prof = {"value_min": 0.0, "value_max": 10.0}
        check = lambda op, thr, agg="max": pf.threshold_check(  # noqa: E731
            {"operator": op, "threshold": thr, "aggregation": agg}, prof)
        self.assertEqual(check(">", 10), "soglia_sopra_il_massimo_osservato")
        self.assertEqual(check(">=", 10), "raggiungibile")
        self.assertEqual(check(">", 9.9), "raggiungibile")
        self.assertEqual(check("<", 0), "soglia_sotto_il_minimo_osservato")
        self.assertEqual(check("<=", 0), "raggiungibile")
        self.assertEqual(check(">", 1000, "delta"), "non_confrontabile_con_l_intervallo")
        self.assertEqual(check("==", 5), "non_confrontabile_con_l_intervallo")
        self.assertEqual(pf.threshold_check({"operator": ">", "threshold": 1, "aggregation": "max"},
                                            {"value_max": None}), "nessun_dato")


class TelemetryReadTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "data/processed").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _manifest(self, extra=None):
        row = {"case_id": "cloudbed-1_q032", "cloudbed": "cloudbed-1",
               "start_unix": START, "end_unix": END, **(extra or {})}
        path = self.root / cat.MANIFEST_RELATIVE
        pd.DataFrame([row]).to_csv(path, index=False)
        return path

    def _zip(self, files):
        path = self.root / "Market.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for name, rows in files.items():
                archive.writestr(name, pd.DataFrame(rows, columns=cat.COLUMNS).to_csv(index=False))
        return path

    def _rows(self, cmdb, kpi, first, last, step=60, value=lambda i: float(i)):
        return [{"timestamp": t, "cmdb_id": cmdb, "kpi_name": kpi, "value": value(i)}
                for i, t in enumerate(range(first, last, step))]

    def test_read_interval_reports_missing_files_without_raising(self):
        lo = START - 13 * 3600                       # attraversa la mezzanotte di Shanghai
        paths = _get_telemetry_csv_paths(lo, END, "cloudbed-1", "container_metrics")
        self.assertEqual(len(paths), 2)
        zip_path = self._zip({paths[1]: self._rows("c1", "k", START, END)})
        frame, missing = pf.read_interval(zip_path, "cloudbed-1", "container_metrics", lo, END)
        self.assertEqual(missing, [paths[0]])
        self.assertEqual(len(frame), len(range(START, END, 60)))

    def test_read_interval_filters_kpis_and_interval(self):
        name = _get_telemetry_csv_paths(START - 600, END, "cloudbed-1", "node_metrics")[0]
        rows = self._rows("n1", "a", START - 1200, END + 600) + self._rows("n1", "b", START - 1200, END)
        frame, missing = pf.read_interval(self._zip({name: rows}), "cloudbed-1", "node_metrics",
                                          START - 600, END, {"a"})
        self.assertEqual(missing, [])
        self.assertEqual(set(frame["kpi_name"]), {"a"})
        self.assertTrue(frame["timestamp"].min() >= START - 600 and frame["timestamp"].max() < END)

    def _table_rows(self, conds):
        catalog = _catalog()
        return pf.build_table([_entry(_rule(conds))], catalog)["rows"]

    def test_history_report_end_to_end(self):
        kpi = "container_start_time_seconds"
        name = _get_telemetry_csv_paths(START - 600, END, "cloudbed-1", "container_metrics")[0]
        rows = (self._rows("c1", kpi, START - 600, END) + self._rows("c2", kpi, START, END))
        zip_path = self._zip({name: rows})
        table_rows = self._table_rows([_cond(kpi, ">", 5, "last", 600)])
        report = pf.history_report(zip_path, self._manifest(), table_rows, cases=("cloudbed-1_q032",))
        info = report["checks"][0]["conditions"][0]["cases"]["cloudbed-1_q032"]
        self.assertEqual(info["components_with_kpi"], 2)
        self.assertEqual(info["with_full_history"], 1)
        self.assertEqual(info["threshold"], "raggiungibile")
        self.assertTrue(info["cumulative_counter_hint"])             # crescente e senza delta
        self.assertEqual(report["files_missing"], [])
        self.assertIn("CONTATORE CUMULATIVO", pf.render_history(report))

    def test_delta_aggregation_silences_the_cumulative_hint(self):
        kpi = "container_start_time_seconds"
        name = _get_telemetry_csv_paths(START - 600, END, "cloudbed-1", "container_metrics")[0]
        zip_path = self._zip({name: self._rows("c1", kpi, START - 600, END)})
        rows = self._table_rows([_cond(kpi, ">", 0, "delta", 600)])
        report = pf.history_report(zip_path, self._manifest(), rows, cases=("cloudbed-1_q032",))
        self.assertFalse(report["checks"][0]["conditions"][0]["cases"]["cloudbed-1_q032"]["cumulative_counter_hint"])

    def test_non_executable_rules_are_not_read(self):
        rows = self._table_rows([_cond("mrt_max")])
        report = pf.history_report(self.root / "non_esiste.zip", self._manifest(), rows,
                                   cases=("cloudbed-1_q032",))
        self.assertEqual(report["checks"], [])

    def test_sealed_cases_are_refused(self):
        rows = self._table_rows([_cond("container_start_time_seconds")])
        with self.assertRaises(cat.CatalogScopeError):
            pf.history_report(self.root / "Market.zip", self._manifest(), rows, cases=("cloudbed-1_q014",))

    def test_manifest_with_ground_truth_columns_is_refused(self):
        rows = self._table_rows([_cond("container_start_time_seconds")])
        with self.assertRaises(cat.CatalogScopeError):
            pf.history_report(self.root / "Market.zip", self._manifest({"reason": "x"}), rows,
                              cases=("cloudbed-1_q032",))


if __name__ == "__main__":
    unittest.main()
