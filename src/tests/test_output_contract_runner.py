"""Test del collegamento non invasivo del contratto al runner.

Nessuna chiamata Gemini, accesso alla ground truth o salvataggio risultati.
"""
import json
import unittest
from unittest.mock import patch, sentinel

from evaluation.experiment_config import ExperimentConfig
from evaluation.experiment_runner import run_experiment


def _fault(component="node-5"):
    return {
        "root cause occurrence datetime": "2022-03-20 13:00:00",
        "root cause component": component,
        "root cause reason": "node CPU load",
    }


def _run(raw_response, mode):
    config = ExperimentConfig(
        variant="A0",
        case_id="cloudbed-1_q009",
        output_contract_mode=mode,
    )
    prepared = {
        "caso": {
            "cloudbed": "cloudbed-1",
            "task_index": "task_5",
            "query_index": 9,
        },
        "tools": [sentinel.tool],
        "richiesta": "Istruzione senza ground truth",
        "evidence_sha256": None,
        "preprocessing_seconds": 0.0,
    }
    execution = {
        "raw_response": raw_response,
        "metrics": {
            "llm_calls": 1,
            "tool_calls": 0,
            "tool_rounds": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "duration_seconds": 0.0,
        },
        "tool_trajectory": [],
        "error": None,
    }

    with (
        patch(
            "evaluation.experiment_runner.prepara_esperimento",
            return_value=prepared,
        ),
        patch(
            "agent.graph_engine.crea_grafo_rca",
            return_value=sentinel.graph,
        ),
        patch(
            "agent.graph_engine.esegui_grafo_rca",
            return_value=execution,
        ),
    ):
        return run_experiment(
            config=config,
            llm=sentinel.fake_llm,
            verbose=False,
            salva=False,
        )


class TestOutputContractAuditRunner(unittest.TestCase):
    def test_default_legacy_non_aggiunge_audit(self):
        raw = json.dumps({"1": _fault()})
        result = _run(raw, "legacy")
        self.assertEqual(result["json_status"], "valid_json")
        self.assertNotIn("output_contract_audit", result)

    def test_audit_valido_non_cambia_predizione(self):
        raw = json.dumps({"1": _fault()})
        legacy = _run(raw, "legacy")
        audit = _run(raw, "audit")
        self.assertEqual(audit["prediction"], legacy["prediction"])
        self.assertEqual(audit["json_status"], legacy["json_status"])
        self.assertEqual(audit["raw_response"], raw)
        self.assertEqual(audit["output_contract_audit"], {
            "status": "valid",
            "fault_count": 1,
            "error": None,
            "cardinality_checked": False,
        })

    def test_campo_extra_audit_invalid_ma_legacy_valido(self):
        raw = json.dumps({
            "1": {**_fault(), "root cause operation": "iowait"}
        })
        legacy = _run(raw, "legacy")
        audit = _run(raw, "audit")
        self.assertEqual(legacy["json_status"], "valid_json")
        self.assertEqual(audit["json_status"], "valid_json")
        self.assertEqual(audit["prediction"], legacy["prediction"])
        self.assertEqual(audit["output_contract_audit"]["status"], "invalid")
        self.assertIn("aggiuntivi", audit["output_contract_audit"]["error"])

    def test_campo_mancante_non_viene_riparato(self):
        fault = _fault()
        fault.pop("root cause reason")
        fault["root cause resource exhaustion"] = "system load increase"
        raw = json.dumps({"1": fault})
        audit = _run(raw, "audit")
        self.assertIsNone(audit["prediction"])
        self.assertTrue(audit["json_status"].startswith("invalid_json:"))
        self.assertEqual(audit["raw_response"], raw)
        self.assertEqual(audit["output_contract_audit"]["status"], "invalid")

    def test_più_guasti_strutturati(self):
        raw = json.dumps({
            "1": _fault("node-5"),
            "2": _fault("frontend-0"),
        })
        audit = _run(raw, "audit")
        self.assertEqual(audit["output_contract_audit"]["fault_count"], 2)
        self.assertFalse(audit["output_contract_audit"]["cardinality_checked"])

    def test_risposta_assente_non_blocca_runner(self):
        audit = _run(None, "audit")
        self.assertIsNone(audit["prediction"])
        self.assertIsNone(audit["json_status"])
        self.assertEqual(audit["output_contract_audit"]["status"], "invalid")

    def test_modalita_sconosciuta_bloccata(self):
        with self.assertRaises(ValueError):
            ExperimentConfig(
                variant="A0",
                case_id="cloudbed-1_q009",
                output_contract_mode="repair",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
