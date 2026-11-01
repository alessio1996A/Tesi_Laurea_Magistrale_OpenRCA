"""Test offline della verifica cross-layer: soli dati sintetici, nessun LLM."""
import copy
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from harness.structural_temporal_verifier import (
    verifica_relazioni_strutturali_temporali,
)
from output.openrca_contract import RootCause


TIME = "2022-03-20 13:00:00"
T = int(
    datetime.strptime(TIME, "%Y-%m-%d %H:%M:%S")
    .replace(tzinfo=ZoneInfo("Asia/Shanghai")).timestamp()
)
START, END = T - 600, T + 1200

CLASSES = {
    "R01": "container CPU load",
    "R02": "container memory load",
    "R06": "container read I/O load",
    "R07": "node CPU load",
    "R08": "node memory consumption",
    "R09": "node disk read I/O consumption",
    "R10": "node disk write I/O consumption",
    "R11": "node disk space consumption",
}


def cand(rule, component, first=T, last=None):
    return {
        "regola": rule,
        "classe_candidata": CLASSES[rule],
        "componente_telemetria": component,
        "timestamp_primo_segnale_unix": first,
        "timestamp_ultimo_segnale_unix": first + 30 if last is None else last,
    }


def report(candidates=None, *, include_rules=True, omitted=0):
    result = {
        "versione": "unified_evidence_v2",
        "caso": {"start_unix": START, "end_unix": END},
        "evidenze": [],
    }
    if include_rules:
        result["regole_diagnostiche_v0"] = {
            "versione": "rule_based_A1_R_v1",
            "finestra": {"start_unix": START, "end_unix": END},
            "candidati_riportati": [] if candidates is None else candidates,
            "candidati_omessi_per_budget": omitted,
        }
    return result


def verify(root, data, *, tolerance=60):
    return verifica_relazioni_strutturali_temporali(
        root,
        data,
        start_unix=START,
        end_unix=END,
        tolleranza_secondi=tolerance,
    )


class TestStructuralTemporalVerifier(unittest.TestCase):
    def test_node_container_cpu_pair(self):
        data = report([
            cand("R07", "node-5", T),
            cand("R01", "node-5.frontend-0", T + 25),
        ])
        result = verify(RootCause(TIME, "frontend-0", "container CPU load"), data)
        self.assertEqual(result["stato"], "relazioni_osservate")
        self.assertEqual(result["host_candidati"], ["node-5"])
        self.assertEqual(result["origine_host"], "host_da_identificativo_telemetria")
        self.assertEqual(result["relazioni_cross_layer"][0]["famiglia"], "cpu")
        self.assertEqual(
            result["relazioni_cross_layer"][0]["ordine_osservato"],
            "segnali_quasi_contemporanei",
        )
        self.assertFalse(result["causa_verificata"])
        self.assertFalse(result["propagazione_verificata"])

    def test_earlier_node_signal_not_causal_proof(self):
        data = report([
            cand("R07", "node-5", T),
            cand("R01", "node-5.frontend-0", T + 180),
        ])
        result = verify(RootCause(TIME, "node-5", "node CPU load"), data)
        self.assertEqual(result["stato"], "relazioni_osservate")
        self.assertEqual(
            result["relazioni_cross_layer"][0]["ordine_osservato"],
            "segnale_nodo_precede_container",
        )
        self.assertFalse(result["propagazione_verificata"])

    def test_earlier_container_signal(self):
        data = report([
            cand("R07", "node-5", T + 180),
            cand("R01", "node-5.frontend-0", T),
        ])
        result = verify(RootCause(TIME, "frontend-0", "container CPU load"), data)
        self.assertEqual(result["stato"], "relazioni_osservate")
        self.assertEqual(
            result["relazioni_cross_layer"][0]["ordine_osservato"],
            "segnale_container_precede_nodo",
        )

    def test_different_hosts_are_not_joined(self):
        data = report([
            cand("R07", "node-6", T),
            cand("R01", "node-5.frontend-0", T),
        ])
        result = verify(RootCause(TIME, "frontend-0", "container CPU load"), data)
        self.assertEqual(result["stato"], "nessuna_relazione_osservata")
        self.assertEqual(result["relazioni_cross_layer"], [])

    def test_different_resources_not_joined(self):
        data = report([
            cand("R08", "node-5", T),
            cand("R01", "node-5.frontend-0", T),
        ])
        result = verify(RootCause(TIME, "frontend-0", "container CPU load"), data)
        self.assertEqual(result["stato"], "nessuna_relazione_osservata")

    def test_only_predicted_family_is_reported(self):
        data = report([
            cand("R07", "node-5", T),
            cand("R01", "node-5.frontend-0", T),
            cand("R08", "node-5", T),
            cand("R02", "node-5.frontend-0", T),
        ])
        result = verify(RootCause(TIME, "frontend-0", "container CPU load"), data)
        self.assertEqual(len(result["relazioni_cross_layer"]), 1)
        self.assertEqual(result["relazioni_cross_layer"][0]["famiglia"], "cpu")

    def test_unqualified_container_multiple_hosts_is_ambiguous(self):
        data = report([
            cand("R01", "node-5.frontend-0", T),
            cand("R01", "node-6.frontend-0", T),
            cand("R07", "node-5", T),
        ])
        result = verify(RootCause(TIME, "frontend-0", "container CPU load"), data)
        self.assertEqual(result["stato"], "host_ambiguo")
        self.assertEqual(result["host_candidati"], ["node-5", "node-6"])

    def test_qualified_container_resolves_host_without_guess(self):
        data = report([
            cand("R01", "node-5.frontend-0", T),
            cand("R01", "node-6.frontend-0", T),
            cand("R07", "node-5", T),
        ])
        result = verify(
            RootCause(TIME, "node-5.frontend-0", "container CPU load"), data
        )
        self.assertEqual(result["stato"], "relazioni_osservate")
        self.assertEqual(result["host_candidati"], ["node-5"])

    def test_node_reason_cannot_be_container_reason(self):
        data = report([
            cand("R01", "node-5.frontend-0", T),
            cand("R07", "node-5", T),
        ])
        result = verify(RootCause(TIME, "node-5", "container CPU load"), data)
        self.assertEqual(result["stato"], "livello_non_verificabile")

    def test_unknown_reason_is_not_mapped_by_synonym(self):
        data = report([
            cand("R01", "node-5.frontend-0", T),
            cand("R07", "node-5", T),
        ])
        result = verify(RootCause(TIME, "frontend-0", "CPU overload"), data)
        self.assertEqual(result["stato"], "classe_non_coperta")

    def test_original_case_q006_like_io_cpu_not_same_family(self):
        data = report([
            cand("R10", "node-5", T),
            cand("R01", "node-5.frontend-0", T),
        ])
        result = verify(
            RootCause(TIME, "node-5", "node disk write I/O consumption"),
            data,
        )
        self.assertEqual(result["stato"], "nessuna_relazione_osservata")

    def test_no_report_is_not_evidence_against_hypothesis(self):
        result = verify(RootCause(TIME, "node-5", "node CPU load"), None)
        self.assertEqual(result["stato"], "non_valutabile")

    def test_no_rules_is_not_evidence_against_hypothesis(self):
        result = verify(
            RootCause(TIME, "node-5", "node CPU load"),
            report(include_rules=False),
        )
        self.assertEqual(result["stato"], "non_valutabile")

    def test_null_rules_are_not_evidence_against_hypothesis(self):
        data = report(include_rules=False)
        data["regole_diagnostiche_v0"] = None
        result = verify(RootCause(TIME, "node-5", "node CPU load"), data)
        self.assertEqual(result["stato"], "non_valutabile")

    def test_no_candidates_not_evidence_of_health(self):
        result = verify(
            RootCause(TIME, "node-5", "node CPU load"), report([])
        )
        self.assertEqual(result["stato"], "nessuna_relazione_osservata")
        self.assertFalse(result["causa_verificata"])

    def test_out_of_window_from_base_checker(self):
        result = verify(
            RootCause("2022-03-20 12:40:00", "node-5", "node CPU load"),
            report([]),
        )
        self.assertEqual(result["stato"], "fuori_finestra")

    def test_unknown_rule_rejected(self):
        candidate = cand("R01", "node-5.frontend-0")
        candidate["regola"] = "R99"
        with self.assertRaisesRegex(ValueError, "Regola sconosciuta"):
            verify(RootCause(TIME, "frontend-0", "container CPU load"),
                   report([candidate]))

    def test_scope_error_rejected(self):
        with self.assertRaisesRegex(ValueError, "nodo malformato"):
            verify(
                RootCause(TIME, "node-5", "node CPU load"),
                report([cand("R07", "node-5.frontend-0")]),
            )

    def test_no_mutation(self):
        data = report([
            cand("R07", "node-5", T),
            cand("R01", "node-5.frontend-0", T),
        ])
        saved = copy.deepcopy(data)
        verify(RootCause(TIME, "frontend-0", "container CPU load"), data)
        self.assertEqual(data, saved)

    def test_report_is_stable_under_candidate_reordering(self):
        candidates = [
            cand("R07", "node-5", T),
            cand("R01", "node-5.frontend-0", T + 25),
            cand("R02", "node-5.frontend-0", T + 60),
        ]
        a = verify(RootCause(TIME, "frontend-0", "container CPU load"),
                   report(candidates))
        b = verify(RootCause(TIME, "frontend-0", "container CPU load"),
                   report(list(reversed(candidates))))
        def core(result):
            return [
                (p["famiglia"], p["ordine_osservato"],
                 p["primo_segnale_nodo_unix"],
                 p["primo_segnale_container_unix"])
                for p in result["relazioni_cross_layer"]
            ]
        self.assertEqual(core(a), core(b))


if __name__ == "__main__":
    unittest.main(verbosity=2)
