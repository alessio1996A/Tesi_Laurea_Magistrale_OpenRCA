"""Test offline per il piano di verifica: nessun modello, API o GT."""
import copy
import unittest

from harness.investigation_planner import pianifica_verifiche_mirate


START, END = 1000, 2000
CATEGORIES = {
    "R01": "container CPU load",
    "R02": "container memory load",
    "R07": "node CPU load",
    "R10": "node disk write I/O consumption",
}


def candidate(rule, component, *, first=1300, last=1330, kpi=None):
    return {
        "regola": rule,
        "classe_candidata": CATEGORIES[rule],
        "componente_telemetria": component,
        "timestamp_primo_segnale_unix": first,
        "timestamp_ultimo_segnale_unix": last,
        "evidenze": (
            {"kpi_principale": kpi} if kpi is not None else {}
        ),
    }


def report(candidates, omitted=0):
    return {
        "versione": "unified_evidence_v2",
        "caso": {"start_unix": START, "end_unix": END},
        "regole_diagnostiche_v0": {
            "versione": "rule_based_A1_R_v1",
            "finestra": {"start_unix": START, "end_unix": END},
            "totale_candidati": len(candidates) + omitted,
            "candidati_omessi_per_budget": omitted,
            "candidati_riportati": candidates,
        },
    }


def call(tool, component=None, start=START, end=END, kpi=None):
    params = {"start_unix": start, "end_unix": end}
    if component is not None:
        params["cmdb_id"] = component
    if kpi is not None:
        params["kpi_name"] = kpi
    return {
        "tipo": "tool_call",
        "nome": tool,
        "parametri": params,
    }


def plan(data, calls=None, max_checks=2, remaining_rounds=2):
    return pianifica_verifiche_mirate(
        data,
        [] if calls is None else calls,
        start_unix=START,
        end_unix=END,
        max_checks=max_checks,
        remaining_rounds=remaining_rounds,
    )


class TestInvestigationPlanner(unittest.TestCase):
    def test_bounded_two_scope_plan_q006_like(self):
        data = report([
            candidate("R01", "node-5.adservice-2", kpi="cpu"),
            candidate("R01", "node-5.frontend-0", kpi="cpu"),
            candidate("R02", "node-5.frontend-0", kpi="memory"),
            candidate("R10", "node-5", kpi="write"),
        ])
        result = plan(data, max_checks=2, remaining_rounds=4)
        self.assertEqual(result["budget_utilizzato_nel_piano"], 2)
        self.assertEqual(
            [p["scope"] for p in result["verifiche_proposte"]],
            ["container", "node"],
        )
        self.assertFalse(result["strumenti_chiamati"])
        self.assertFalse(result["causa_verificata"])
        self.assertEqual(result["candidati_senza_chiamata_precedente"], 4)

    def test_valid_arguments_always_bound_to_case_window(self):
        data = report([candidate("R07", "node-5", kpi="node_cpu_usage")])
        item = plan(data)["verifiche_proposte"][0]
        self.assertEqual(item["tool"], "tool_get_node_metrics")
        self.assertEqual(item["arguments"], {
            "start_unix": START,
            "end_unix": END,
            "cmdb_id": "node-5",
            "kpi_name": "node_cpu_usage",
        })

    def test_no_extra_tool_round_if_budget_exhausted(self):
        data = report([candidate("R07", "node-5")])
        result = plan(data, remaining_rounds=0)
        self.assertEqual(result["verifiche_proposte"], [])
        self.assertEqual(result["proposte_non_selezionate"], 1)

    def test_existing_targeted_call_skipped(self):
        data = report([candidate("R07", "node-5", kpi="cpu")])
        previous = [call("tool_get_node_metrics", "node-5")]
        result = plan(data, previous)
        self.assertEqual(result["verifiche_proposte"], [])
        self.assertEqual(result["candidati_con_chiamata_precedente"], 1)

    def test_matching_kpi_scoped_call_skipped(self):
        data = report([candidate("R01", "node-5.frontend-0", kpi="cpu")])
        previous = [
            call("tool_get_container_metrics", "node-5.frontend-0", kpi="cpu")
        ]
        self.assertEqual(plan(data, previous)["verifiche_proposte"], [])

    def test_other_kpi_does_not_satisfy_target(self):
        data = report([candidate("R01", "node-5.frontend-0", kpi="cpu")])
        previous = [
            call("tool_get_container_metrics", "node-5.frontend-0", kpi="memory")
        ]
        self.assertEqual(len(plan(data, previous)["verifiche_proposte"]), 1)

    def test_generic_call_does_not_count(self):
        data = report([candidate("R07", "node-5")])
        previous = [call("tool_get_node_metrics")]
        self.assertEqual(len(plan(data, previous)["verifiche_proposte"]), 1)

    def test_tool_call_not_covering_signal_interval_does_not_count(self):
        data = report([candidate("R07", "node-5", first=1600, last=1650)])
        previous = [call("tool_get_node_metrics", "node-5", start=1000, end=1500)]
        self.assertEqual(len(plan(data, previous)["verifiche_proposte"]), 1)

    def test_other_scope_tool_does_not_count(self):
        data = report([candidate("R07", "node-5")])
        previous = [call("tool_get_container_metrics", "node-5")]
        self.assertEqual(len(plan(data, previous)["verifiche_proposte"]), 1)

    def test_same_target_is_not_scheduled_twice(self):
        data = report([
            candidate("R01", "node-5.frontend-0", kpi="cpu"),
            candidate("R01", "node-5.frontend-0", first=1400, last=1430, kpi="cpu"),
        ])
        result = plan(data, max_checks=4, remaining_rounds=4)
        self.assertEqual(len(result["verifiche_proposte"]), 1)
        self.assertEqual(result["proposte_non_selezionate"], 0)

    def test_fairness_across_components_with_same_scope(self):
        data = report([
            candidate("R01", "node-5.frontend-0", kpi="cpu"),
            candidate("R02", "node-5.frontend-0", kpi="memory"),
            candidate("R01", "node-5.adservice-2", kpi="cpu"),
        ])
        result = plan(data, max_checks=2, remaining_rounds=2)
        components = [x["component"] for x in result["verifiche_proposte"]]
        self.assertEqual(len(set(components)), 2)

    def test_source_order_does_not_change_selected_target_set(self):
        cases = [
            candidate("R01", "node-5.frontend-0", kpi="cpu"),
            candidate("R07", "node-5", kpi="cpu"),
            candidate("R01", "node-5.adservice-2", kpi="cpu"),
        ]
        a = plan(report(cases))
        b = plan(report(list(reversed(cases))))
        def targets(x):
            return [(p["tool"], p["component"], p["category"])
                    for p in x["verifiche_proposte"]]
        self.assertEqual(targets(a), targets(b))

    def test_missing_main_kpi_makes_component_targeted_call(self):
        data = report([candidate("R07", "node-5")])
        item = plan(data)["verifiche_proposte"][0]
        self.assertNotIn("kpi_name", item["arguments"])
        self.assertEqual(item["arguments"]["cmdb_id"], "node-5")

    def test_budget_omissions_are_declared(self):
        data = report([candidate("R01", "node-5.frontend-0")], omitted=2)
        result = plan(data)
        self.assertEqual(result["candidati_omessi_per_budget"], 2)

    def test_empty_candidates_is_not_negative_proof(self):
        result = plan(report([]))
        self.assertEqual(result["verifiche_proposte"], [])
        self.assertFalse(result["causa_verificata"])

    def test_malformed_rule_candidate_fails_closed(self):
        data = report([candidate("R01", "node-5.frontend-0")])
        data["regole_diagnostiche_v0"]["candidati_riportati"][0][
            "classe_candidata"
        ] = "node CPU load"
        with self.assertRaisesRegex(ValueError, "metadati incoerenti"):
            plan(data)

    def test_inconsistent_window_fails_closed(self):
        data = report([candidate("R07", "node-5")])
        data["caso"]["start_unix"] += 1
        with self.assertRaisesRegex(ValueError, "Finestra"):
            plan(data)

    def test_negative_and_boolean_budget_rejected(self):
        data = report([])
        for value in (-1, True, 1.2):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    plan(data, max_checks=value)

    def test_no_mutation(self):
        data = report([candidate("R07", "node-5")])
        previous = [call("tool_get_service_metrics")]
        old = copy.deepcopy((data, previous))
        plan(data, previous)
        self.assertEqual(old, (data, previous))


if __name__ == "__main__":
    unittest.main(verbosity=2)
