"""Test offline dell'esecutore delle regole K (dati completamente sintetici).

Nessuna API, nessuna telemetria reale, nessun caso sigillato, nessuna etichetta.
"""
import inspect
import unittest

import pandas as pd

from evaluation import rq2_k_rule_executor as ex

START = 10_000
END = START + 600           # 10 minuti, griglia a 60 s -> 10 istanti


def _series(cmdb_id, kpi, values, first_ts=START - 600, step=60):
    return [{"timestamp": first_ts + i * step, "cmdb_id": cmdb_id,
             "kpi_name": kpi, "value": v} for i, v in enumerate(values)]


def _frame(rows):
    return pd.DataFrame(rows, columns=["timestamp", "cmdb_id", "kpi_name", "value"])


def _cond(metric="cpu", operator=">", threshold=80, aggregation="last", window=60):
    return {"metric": metric, "operator": operator, "threshold": threshold,
            "unit": "pct", "aggregation": aggregation, "window_seconds": window}


def _rule(conditions, combination="all", pseudocode="ignorato"):
    return {"status": "candidate", "combination": combination,
            "conditions": conditions, "pseudocode": pseudocode}


HISTORY = START - 600
FLAT = [10.0] * 30                      # 30 campioni da START-600 a START+1140 (copre la griglia)


def _run(rule, rows, level="node", **kwargs):
    telemetry = {"node": pd.DataFrame(columns=["timestamp", "cmdb_id", "kpi_name", "value"]),
                 "container": pd.DataFrame(columns=["timestamp", "cmdb_id", "kpi_name", "value"])}
    telemetry[level] = _frame(rows)
    # Livelli fissati come farebbe il catalogo: ogni KPI dei dati sintetici ha il suo livello.
    kpi_levels = kwargs.get("kpi_levels") or {r["kpi_name"]: level for r in rows}
    return ex.execute_rule(rule, telemetry, start_unix=START, end_unix=END,
                           history_start_unix=kwargs.get("history", HISTORY),
                           kpi_levels=kpi_levels)


class ThreeValuedLogicTests(unittest.TestCase):
    def test_all(self):
        self.assertEqual(ex.kleene_all(["T", "T"]), "T")
        self.assertEqual(ex.kleene_all(["T", "U"]), "U")
        self.assertEqual(ex.kleene_all(["F", "U"]), "F")       # un falso basta
        self.assertEqual(ex.kleene_all(["F", "T"]), "F")

    def test_any(self):
        self.assertEqual(ex.kleene_any(["F", "F"]), "F")
        self.assertEqual(ex.kleene_any(["F", "U"]), "U")
        self.assertEqual(ex.kleene_any(["T", "U"]), "T")       # un vero basta
        self.assertEqual(ex.kleene_any(["T", "F"]), "T")


class AggregationTests(unittest.TestCase):
    def _value(self, aggregation, values, window=180):
        # campioni a passo 60 s fino a t = START: finestra (START-180, START] = ultimi 3
        stamps = [START - 4 * 60 + i * 60 for i in range(len(values))]
        import numpy as np
        return ex._aggregate(np.array(stamps), np.array(values, dtype=float),
                             START, window, aggregation)

    def test_aggregations_on_a_known_window(self):
        values = [1.0, 2.0, 4.0, 8.0, 16.0]      # istanti START-240 ... START
        # finestra (START-180, START] contiene START-120, START-60, START -> 4, 8, 16
        self.assertEqual(self._value("last", values), (16.0, None))
        self.assertEqual(self._value("max", values), (16.0, None))
        self.assertEqual(self._value("min", values), (4.0, None))
        self.assertEqual(self._value("sum", values), (28.0, None))
        self.assertEqual(self._value("count", values), (3.0, None))
        self.assertEqual(self._value("delta", values), (12.0, None))     # 16 - 4
        self.assertAlmostEqual(self._value("mean", values)[0], 28 / 3)
        self.assertAlmostEqual(self._value("p95", values)[0], 15.2)      # interpolazione lineare

    def test_left_edge_excluded_right_edge_included(self):
        import numpy as np
        stamps = np.array([START - 60, START])          # START-60 e' sul bordo sinistro
        values = np.array([100.0, 1.0])
        self.assertEqual(ex._aggregate(stamps, values, START, 60, "max"), (1.0, None))

    def test_empty_window_and_delta_with_one_sample_are_unknown(self):
        import numpy as np
        stamps = np.array([START - 5000])
        values = np.array([1.0])
        self.assertEqual(ex._aggregate(stamps, values, START, 60, "mean"),
                         (None, ex.CAUSE_NO_SAMPLES))
        stamps = np.array([START])
        self.assertEqual(ex._aggregate(stamps, values, START, 60, "delta"),
                         (None, ex.CAUSE_DELTA_ONE_SAMPLE))


class GroupDecisionTests(unittest.TestCase):
    def test_positive_with_first_fire_time_per_component(self):
        spike = FLAT[:]
        spike[13] = 95.0                       # campione a START-600+13*60 = START+180
        rows = _series("node-1", "cpu", spike) + _series("node-2", "cpu", FLAT)
        result = _run(_rule([_cond()]), rows)
        self.assertEqual(result["decision"], "positive")
        self.assertEqual(result["first_fire_unix_by_component"], {"node-1": START + 180})
        self.assertEqual(result["level"], "node")

    def test_positive_even_if_other_cells_are_unknown(self):
        # node-2 ha pochi campioni dentro la finestra: le celle successive sono sconosciute.
        rows = (_series("node-1", "cpu", [95.0] * 30)
                + _series("node-2", "cpu", [10.0] * 3, first_ts=START))
        result = _run(_rule([_cond()]), rows)
        self.assertEqual(result["decision"], "positive")      # un sospetto basta (any T)
        self.assertGreater(result["cells"]["unknown"], 0)

    def test_negative_only_when_everything_is_evaluable(self):
        rows = _series("node-1", "cpu", FLAT) + _series("node-2", "cpu", FLAT)
        result = _run(_rule([_cond()]), rows)
        self.assertEqual(result["decision"], "negative")
        self.assertEqual(result["cells"]["unknown"], 0)
        self.assertEqual(result["evaluable_fraction"], 1.0)
        self.assertEqual(result["first_fire_unix_by_component"], {})

    def test_component_without_the_kpi_is_excluded_counted_and_named(self):
        rows = _series("node-1", "cpu", FLAT) + _series("node-2", "mem", FLAT)
        result = _run(_rule([_cond()]), rows)          # node-2 non ha "cpu"
        self.assertEqual(result["decision"], "negative")   # vale per la POPOLAZIONE: solo node-1
        self.assertEqual(result["population"], ["node-1"])
        self.assertEqual(result["components_total"], 2)
        self.assertEqual(result["components_in_population"], 1)
        self.assertEqual(result["components_excluded"], ["node-2"])
        self.assertEqual(result["excluded_missing_metrics"], {"node-2": ["cpu"]})
        self.assertEqual(result["population_coverage"], 0.5)
        self.assertEqual(result["cells"]["unknown"], 0)    # l'escluso non diventa "sconosciuto"

    def test_an_excluded_component_never_makes_the_group_positive(self):
        rows = _series("node-1", "cpu", FLAT) + _series("node-2", "mem", [99.0] * 30)
        result = _run(_rule([_cond("cpu")]), rows)
        self.assertEqual(result["decision"], "negative")
        self.assertEqual(result["first_fire_unix_by_component"], {})

    def test_kpi_only_in_the_history_does_not_count_as_exposed(self):
        # node-2 espone "cpu" solo prima della finestra di gruppo: non e' nella popolazione.
        rows = (_series("node-1", "cpu", FLAT)
                + _series("node-2", "cpu", [10.0] * 5, first_ts=START - 600)
                + _series("node-2", "mem", FLAT))
        result = _run(_rule([_cond("cpu")]), rows)
        self.assertEqual(result["population"], ["node-1"])
        self.assertEqual(result["excluded_missing_metrics"], {"node-2": ["cpu"]})

    def test_every_required_kpi_is_needed_even_for_combination_any(self):
        rows = _series("node-1", "cpu", [95.0] * 30)       # nessun "mem"
        conds = [_cond("cpu"), _cond("mem", threshold=1)]
        levels = {"cpu": "node", "mem": "node"}
        for combination in ("all", "any"):
            result = _run(_rule(conds, combination), rows, kpi_levels=levels)
            self.assertEqual(result["decision"], "abstain")
            self.assertEqual(result["reason"]["code"], "empty_population")
            self.assertEqual(result["components_excluded"], ["node-1"])

    def test_a_gap_larger_than_the_window_makes_the_group_abstain(self):
        # nessun campione nelle ultime finestre: tolgo il tratto centrale
        values = FLAT[:]
        rows = [r for i, r in enumerate(_series("node-1", "cpu", values)) if not 12 <= i <= 22]
        result = _run(_rule([_cond(window=60)]), rows)
        self.assertEqual(result["decision"], "abstain")
        self.assertIn(ex.CAUSE_NO_SAMPLES, result["unknown_by_cause"])

    def test_window_starting_before_loaded_history_is_unknown(self):
        rows = _series("node-1", "cpu", FLAT)
        result = _run(_rule([_cond(window=3600, aggregation="mean")]), rows)
        self.assertEqual(result["decision"], "abstain")
        self.assertIn(ex.CAUSE_HISTORY, result["unknown_by_cause"])

    def test_all_vs_any_with_one_unknown_condition(self):
        # "mem" ha campioni solo all'inizio della finestra: poi la condizione e' sconosciuta.
        rows = (_series("node-1", "cpu", [95.0] * 30)
                + _series("node-1", "mem", [0.0] * 3, first_ts=START))
        conds = [_cond("cpu"), _cond("mem", threshold=1)]
        levels = {"cpu": "node", "mem": "node"}
        # all: falso o sconosciuto, mai vero -> abstain; any: "cpu" vera basta -> positive
        self.assertEqual(_run(_rule(conds, "all"), rows, kpi_levels=levels)["decision"], "abstain")
        self.assertEqual(_run(_rule(conds, "any"), rows, kpi_levels=levels)["decision"], "positive")


class LevelAndSafetyTests(unittest.TestCase):
    def test_container_level_is_detected(self):
        rows = _series("node-1.svc-0", "ctr_cpu", FLAT)
        result = _run(_rule([_cond("ctr_cpu")]), rows, level="container")
        self.assertEqual(result["level"], "container")
        self.assertEqual(result["decision"], "negative")

    def test_metric_absent_everywhere_abstains_with_reason(self):
        rows = _series("node-1", "cpu", FLAT)
        result = _run(_rule([_cond("inesistente")]), rows)
        self.assertEqual(result["decision"], "abstain")
        self.assertEqual(result["reason"]["code"], "metric_absent")

    def test_mixed_levels_are_not_supported(self):
        telemetry = {"node": _frame(_series("node-1", "n_cpu", FLAT)),
                     "container": _frame(_series("node-1.svc-0", "c_cpu", FLAT))}
        rule = _rule([_cond("n_cpu"), _cond("c_cpu")])
        result = ex.execute_rule(rule, telemetry, start_unix=START, end_unix=END,
                                 history_start_unix=HISTORY,
                                 kpi_levels={"n_cpu": "node", "c_cpu": "container"})
        self.assertEqual(result["decision"], "abstain")
        self.assertEqual(result["reason"]["code"], "mixed_levels")

    def test_level_is_fixed_by_the_catalog_not_by_the_loaded_data(self):
        # Il KPI e' di container per il catalogo ma la finestra caricata non ha nessun
        # campione di container: il livello non cambia, i valori sono solo sconosciuti.
        telemetry = {"node": _frame(_series("node-1", "n_cpu", FLAT)),
                     "container": pd.DataFrame(columns=["timestamp", "cmdb_id", "kpi_name", "value"])}
        result = ex.execute_rule(_rule([_cond("c_cpu")]), telemetry, start_unix=START,
                                 end_unix=END, history_start_unix=HISTORY,
                                 kpi_levels={"n_cpu": "node", "c_cpu": "container"})
        self.assertEqual(result["level"], "container")
        self.assertEqual(result["decision"], "abstain")
        self.assertEqual(result["reason"]["code"], "empty_population")
        self.assertEqual(result["components_total"], 0)

    def test_kpi_not_in_the_catalog_is_metric_absent_even_if_data_has_it(self):
        rows = _series("node-1", "cpu", FLAT)
        result = _run(_rule([_cond("cpu")]), rows, kpi_levels={"altro": "node"})
        self.assertEqual(result["reason"]["code"], "metric_absent")

    def test_invalid_level_in_the_map_is_refused(self):
        with self.assertRaises(ex.RuleExecutionError):
            _run(_rule([_cond("cpu")]), _series("node-1", "cpu", FLAT), kpi_levels={"cpu": "service"})

    def test_pseudocode_is_never_used(self):
        rows = _series("node-1", "cpu", [95.0] * 30)
        a = _run(_rule([_cond()], pseudocode="return False"), rows)
        b = _run(_rule([_cond()], pseudocode="__import__('os').system('x')"), rows)
        self.assertEqual(a, b)

    def test_rejects_conditions_outside_the_closed_sets(self):
        rows = _series("node-1", "cpu", FLAT)
        for bad in (_cond(operator="!="), _cond(aggregation="median"), _cond(window=0),
                    _cond(window=86401), _cond(threshold=float("inf"))):
            with self.assertRaises(ex.RuleExecutionError):
                _run(_rule([bad]), rows)
        with self.assertRaises(ex.RuleExecutionError):
            _run({"status": "insufficient_evidence", "conditions": []}, rows)

    def test_no_parameter_can_carry_labels(self):
        names = list(inspect.signature(ex.execute_rule).parameters)
        self.assertEqual(names, ["rule", "telemetry", "start_unix", "end_unix",
                                 "history_start_unix", "kpi_levels", "grid_seconds"])

    def test_non_finite_samples_are_dropped_not_treated_as_zero(self):
        rows = _series("node-1", "cpu", [float("nan")] * 30)
        result = _run(_rule([_cond(operator="<", threshold=1)]), rows)
        self.assertEqual(result["decision"], "abstain")        # niente campioni validi


if __name__ == "__main__":
    unittest.main()
