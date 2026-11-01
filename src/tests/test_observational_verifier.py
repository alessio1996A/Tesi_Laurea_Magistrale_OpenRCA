"""Test offline del primo gate osservativo: no API, GT o file OpenRCA."""
import copy
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from harness.observational_verifier import verifica_coerenza_osservativa
from output.openrca_contract import RootCause


TIME = "2022-03-20 13:00:00"
SIGNAL = int(datetime.strptime(TIME, "%Y-%m-%d %H:%M:%S")
             .replace(tzinfo=ZoneInfo("Asia/Shanghai")).timestamp())
START, END = SIGNAL - 600, SIGNAL + 1200


def _root(component="frontend-0", reason="container CPU load", time=TIME):
    return RootCause(time, component, reason)


def _candidate(component="node-5.frontend-0", reason="container CPU load",
               first=SIGNAL, last=SIGNAL + 30, rule="R01"):
    return {
        "regola": rule,
        "componente_telemetria": component,
        "classe_candidata": reason,
        "timestamp_primo_segnale_unix": first,
        "timestamp_ultimo_segnale_unix": last,
    }


def _report(candidates=None, *, omitted=0, include_rules=True):
    report = {
        "versione": "unified_evidence_v2",
        "caso": {"start_unix": START, "end_unix": END},
        "evidenze": [],
    }
    if include_rules:
        report["regole_diagnostiche_v0"] = {
            "versione": "rule_based_A1_R_v1",
            "finestra": {"start_unix": START, "end_unix": END},
            "candidati_riportati": candidates if candidates is not None else [],
            "candidati_omessi_per_budget": omitted,
        }
    return report


def _check(root=None, report=None, *, tolerance=60):
    return verifica_coerenza_osservativa(
        root if root is not None else _root(),
        report,
        start_unix=START,
        end_unix=END,
        tolleranza_secondi=tolerance,
    )


class TestObservationalVerifier(unittest.TestCase):
    def test_corrispondenza_container_con_host_prefix(self):
        response = _check(report=_report([_candidate()]))
        self.assertEqual(response["stato"], "coerente_con_segnale")
        self.assertEqual(len(response["matches"]), 1)
        self.assertEqual(response["matches"][0]["regola"], "R01")
        self.assertFalse(response["causa_verificata"])

    def test_node_non_e_alias_del_container(self):
        response = _check(
            root=_root("node-5", "container CPU load"),
            report=_report([_candidate()]),
        )
        self.assertEqual(response["stato"], "nessuna_corrispondenza")
        self.assertEqual(response["componenti_con_candidati"], 0)

    def test_node_rule_corrispondenza_esatta(self):
        response = _check(
            root=_root("node-5", "node CPU load"),
            report=_report([_candidate(
                component="node-5", reason="node CPU load", rule="R07"
            )]),
        )
        self.assertEqual(response["stato"], "coerente_con_segnale")

    def test_reason_diversa_non_e_corroborata(self):
        response = _check(
            root=_root(reason="container memory load"),
            report=_report([_candidate()]),
        )
        self.assertEqual(response["stato"], "nessuna_corrispondenza")
        self.assertEqual(response["componenti_con_candidati"], 1)

    def test_no_heuristic_synonyms(self):
        response = _check(
            root=_root(reason="CPU overload"),
            report=_report([_candidate()]),
        )
        self.assertEqual(response["stato"], "nessuna_corrispondenza")

    def test_reason_normalization_is_lexical_only(self):
        response = _check(
            root=_root(reason="  CONTAINER   cpu load  "),
            report=_report([_candidate()]),
        )
        self.assertEqual(response["stato"], "coerente_con_segnale")

    def test_mancata_corrispondenza_temporale_non_nega_guasto(self):
        response = _check(
            report=_report([_candidate(first=SIGNAL + 300, last=SIGNAL + 330)])
        )
        self.assertEqual(response["stato"], "tempo_non_corroborato")
        self.assertFalse(response["matches"][0]["vicinanza_temporale"])
        self.assertFalse(response["causa_verificata"])

    def test_temporal_tolerance_is_explicit(self):
        root = _root()
        report = _report([_candidate(first=SIGNAL + 70, last=SIGNAL + 100)])
        self.assertEqual(
            _check(root, report, tolerance=60)["stato"],
            "tempo_non_corroborato",
        )
        self.assertEqual(
            _check(root, report, tolerance=70)["stato"],
            "coerente_con_segnale",
        )

    def test_predicted_time_outside_case(self):
        response = _check(
            root=_root(time="2022-03-20 12:45:00"),
            report=_report([_candidate()]),
        )
        self.assertEqual(response["stato"], "fuori_finestra")

    def test_no_report_means_unknown(self):
        response = _check()
        self.assertEqual(response["stato"], "non_valutabile")

    def test_a1_v2_no_rules_means_unknown(self):
        response = _check(report=_report(include_rules=False))
        self.assertEqual(response["stato"], "non_valutabile")

    def test_no_candidates_does_not_mean_healthy(self):
        response = _check(report=_report([]))
        self.assertEqual(response["stato"], "nessuna_corrispondenza")
        self.assertFalse(response["causa_verificata"])

    def test_omitted_budget_reported(self):
        response = _check(report=_report([], omitted=4))
        self.assertFalse(response["copertura_candidati_completa"])
        self.assertEqual(response["candidati_omessi_per_budget"], 4)

    def test_mismatch_report_window_fails_closed(self):
        report = _report([_candidate()])
        report["regole_diagnostiche_v0"]["finestra"]["start_unix"] += 1
        with self.assertRaisesRegex(ValueError, "Finestra"):
            _check(report=report)

    def test_outside_candidate_window_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "malformato"):
            _check(report=_report([
                _candidate(first=START - 1, last=SIGNAL)
            ]))

    def test_does_not_modify_inputs(self):
        report = _report([_candidate()])
        before = copy.deepcopy(report)
        _check(report=report)
        self.assertEqual(report, before)

    def test_rejects_negative_tolerance(self):
        with self.assertRaisesRegex(ValueError, "Tolleranza"):
            _check(report=_report([]), tolerance=-1)

    def test_no_free_causal_promotion(self):
        response = _check(report=_report([_candidate()]))
        self.assertFalse(response["causa_verificata"])
        self.assertIn("non prova", response["nota"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
