"""Test sintetici dell'audit di copertura, mai ground truth o API."""
import copy
import unittest

from harness.hypothesis_coverage_audit import verifica_copertura_ipotesi
from output.openrca_contract import Diagnosis, RootCause


TIME = "2022-03-20 11:00:00"
CLASSES = {
    "R01": "container CPU load",
    "R02": "container memory load",
    "R07": "node CPU load",
    "R10": "node disk write I/O consumption",
}


def fault(component, reason):
    return RootCause(TIME, component, reason)


def candidate(rule, component):
    return {
        "regola": rule,
        "componente_telemetria": component,
        "classe_candidata": CLASSES[rule],
    }


def report(candidates, omitted=0):
    return {
        "versione": "unified_evidence_v2",
        "regole_diagnostiche_v0": {
            "versione": "rule_based_A1_R_v1",
            "candidati_riportati": candidates,
            "totale_candidati": len(candidates) + omitted,
            "candidati_omessi_per_budget": omitted,
        },
    }


def tool(name, cmdb=None, *, params=None):
    args = params if params is not None else {}
    if cmdb is not None:
        args["cmdb_id"] = cmdb
    return {
        "tipo": "tool_call",
        "nome": name,
        "parametri": args,
    }


class TestHypothesisCoverageAudit(unittest.TestCase):
    def test_ripresa_stessa_classe_e_tool_mirato(self):
        result = verifica_copertura_ipotesi(
            Diagnosis((fault("node-5", CLASSES["R07"]),)),
            report([candidate("R07", "node-5")]),
            [tool("tool_get_node_metrics", "node-5")],
        )
        row = result["candidati"][0]
        self.assertEqual(
            row["stato_nella_diagnosi"],
            "componente_e_classe_canonica_ripresi",
        )
        self.assertTrue(row["indagine_mirata_documentata"])
        self.assertEqual(result["candidati_con_metriche_mirate"], 1)
        self.assertFalse(result["causa_verificata"])

    def test_reason_composta_non_e_uguaglianza_canonica(self):
        result = verifica_copertura_ipotesi(
            Diagnosis((fault(
                "node-5",
                "disk write I/O consumption spike and frontend memory pressure",
            ),)),
            report([candidate("R10", "node-5")]),
            [],
        )
        row = result["candidati"][0]
        self.assertEqual(
            row["stato_nella_diagnosi"],
            "componente_ripreso_classe_non_canonica",
        )
        self.assertFalse(row["indagine_mirata_documentata"])

    def test_non_ripreso_non_significa_falso(self):
        result = verifica_copertura_ipotesi(
            Diagnosis((fault("node-6", "node CPU load"),)),
            report([candidate("R01", "node-5.frontend-0")]),
            [],
        )
        self.assertEqual(
            result["candidati"][0]["stato_nella_diagnosi"],
            "candidato_non_ripreso_nella_diagnosi",
        )
        self.assertFalse(result["causa_verificata"])

    def test_traccia_q006_like_logs_and_service_not_metric_target(self):
        result = verifica_copertura_ipotesi(
            Diagnosis((fault("node-6", "unconfirmed resource pressure"),)),
            report([
                candidate("R01", "node-5.frontend-0"),
                candidate("R02", "node-5.frontend-0"),
                candidate("R10", "node-5"),
            ]),
            [
                tool("tool_get_service_metrics"),
                tool("tool_get_logs", params={"log_type": "service"}),
                {"tipo": "tool_result", "nome": "tool_get_logs", "risposta": "x"},
            ],
        )
        self.assertEqual(result["candidati_con_metriche_mirate"], 0)
        self.assertEqual(result["candidati_ripresi_stessa_classe"], 0)

    def test_container_id_exact_required_for_targeted_metric(self):
        result = verifica_copertura_ipotesi(
            Diagnosis((fault("frontend-0", "container CPU load"),)),
            report([candidate("R01", "node-5.frontend-0")]),
            [tool("tool_get_container_metrics", "frontend-0")],
        )
        self.assertEqual(result["candidati_ripresi_stessa_classe"], 1)
        self.assertFalse(result["candidati"][0]["indagine_mirata_documentata"])

    def test_unique_container_alias_is_recognized_in_diagnosis(self):
        result = verifica_copertura_ipotesi(
            Diagnosis((fault("frontend-0", "container CPU load"),)),
            report([candidate("R01", "node-5.frontend-0")]),
            [],
        )
        self.assertEqual(result["candidati_ripresi_stessa_classe"], 1)

    def test_ambiguous_container_alias_not_resolved(self):
        result = verifica_copertura_ipotesi(
            Diagnosis((fault("frontend-0", "container CPU load"),)),
            report([
                candidate("R01", "node-5.frontend-0"),
                candidate("R01", "node-6.frontend-0"),
            ]),
            [],
        )
        self.assertEqual(result["candidati_ripresi_stessa_classe"], 0)

    def test_node_not_alias_of_container(self):
        result = verifica_copertura_ipotesi(
            Diagnosis((fault("node-5", "node CPU load"),)),
            report([candidate("R01", "node-5.frontend-0")]),
            [],
        )
        self.assertEqual(result["candidati_ripresi_stessa_classe"], 0)

    def test_generic_metrics_call_not_specific_coverage(self):
        result = verifica_copertura_ipotesi(
            Diagnosis((fault("node-5", "node CPU load"),)),
            report([candidate("R07", "node-5")]),
            [tool("tool_get_node_metrics")],
        )
        row = result["candidati"][0]
        self.assertEqual(row["chiamate_metriche_generiche_stesso_livello"], [0])
        self.assertFalse(row["indagine_mirata_documentata"])

    def test_wrong_scope_tool_not_specific_coverage(self):
        result = verifica_copertura_ipotesi(
            Diagnosis((fault("node-5", "node CPU load"),)),
            report([candidate("R07", "node-5")]),
            [tool("tool_get_container_metrics", "node-5")],
        )
        self.assertFalse(result["candidati"][0]["indagine_mirata_documentata"])

    def test_budget_omission_is_explicit(self):
        result = verifica_copertura_ipotesi(
            Diagnosis((fault("node-5", "node CPU load"),)),
            report([candidate("R07", "node-5")], omitted=2),
            [],
        )
        self.assertEqual(result["candidati_omessi_per_budget"], 2)
        self.assertFalse(result["copertura_lista_completa"])

    def test_inconsistent_counts_rejected(self):
        data = report([candidate("R07", "node-5")])
        data["regole_diagnostiche_v0"]["totale_candidati"] = 2
        with self.assertRaisesRegex(ValueError, "Conteggi"):
            verifica_copertura_ipotesi(
                Diagnosis((fault("node-5", "node CPU load"),)),
                data, [],
            )

    def test_invalid_rule_class_pair_rejected(self):
        item = candidate("R01", "node-5.frontend-0")
        item["classe_candidata"] = "node CPU load"
        with self.assertRaisesRegex(ValueError, "classe incoerente"):
            verifica_copertura_ipotesi(
                Diagnosis((fault("frontend-0", "container CPU load"),)),
                report([item]), [],
            )

    def test_absence_of_candidates_is_not_causal_conclusion(self):
        result = verifica_copertura_ipotesi(
            Diagnosis((fault("node-5", "node CPU load"),)),
            report([]), [],
        )
        self.assertEqual(result["candidati"], [])
        self.assertFalse(result["causa_verificata"])

    def test_does_not_mutate_inputs(self):
        data = report([candidate("R07", "node-5")])
        trajectory = [tool("tool_get_node_metrics", "node-5")]
        before = copy.deepcopy((data, trajectory))
        verifica_copertura_ipotesi(
            Diagnosis((fault("node-5", "node CPU load"),)), data, trajectory
        )
        self.assertEqual((data, trajectory), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
