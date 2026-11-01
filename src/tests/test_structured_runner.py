"""Test del runner in modalita' structured: nessuna API reale, nessun GT."""
import json
import unittest
from unittest.mock import patch, sentinel

from evaluation.experiment_config import ExperimentConfig
from evaluation.experiment_runner import run_experiment
from output.structured_finalizer import (
    StructuredFinalization,
    StructuredOutputError,
)


def _fake_run(output_mode, raw_response, finalizer_result=None, error=None):
    config = ExperimentConfig(
        variant="A1",
        case_id="cloudbed-1_q009",
        output_contract_mode=output_mode,
    )
    prepared = {
        "caso": {
            "cloudbed": "cloudbed-1",
            "task_index": "task_5",
            "query_index": 9,
        },
        "tools": [sentinel.tool],
        "richiesta": "Solo istruzione visibile all'agente",
        "evidence_sha256": "abc",
        "preprocessing_seconds": 0.0,
    }
    execution = {
        "raw_response": raw_response,
        "metrics": {
            "llm_calls": 2,
            "tool_calls": 1,
            "tool_rounds": 1,
            "input_tokens": 110,
            "output_tokens": 22,
            "total_tokens": 132,
            "duration_seconds": 0.0,
        },
        "tool_trajectory": [],
        "error": None,
    }

    with (
        patch("evaluation.experiment_runner.prepara_esperimento", return_value=prepared),
        patch("agent.graph_engine.crea_grafo_rca", return_value=sentinel.graph),
        patch("agent.graph_engine.esegui_grafo_rca", return_value=execution),
        patch("output.structured_finalizer.formatta_diagnosi_strutturata") as formatter,
    ):
        if error is not None:
            formatter.side_effect = error
        else:
            formatter.return_value = finalizer_result

        result = run_experiment(
            config=config,
            llm=sentinel.fake_llm,
            verbose=False,
            salva=False,
        )
        return result, formatter


def _raw_missing_reason():
    return json.dumps({
        "1": {
            "root cause occurrence datetime": "2022-03-20 13:00:00",
            "root cause component": "node-4",
            "root cause resource exhaustion": "system load increase",
        }
    })


def _canonical():
    return json.dumps({
        "1": {
            "root cause occurrence datetime": "2022-03-20 13:00:00",
            "root cause component": "node-4",
            "root cause reason": "system load increase",
        }
    })


class TestStructuredModeRunner(unittest.TestCase):
    def test_structured_separata_e_contabilizzata(self):
        raw = _raw_missing_reason()
        structured = StructuredFinalization(
            prediction=_canonical(),
            input_tokens=40,
            output_tokens=10,
            total_tokens=50,
            elapsed_seconds=0.125,
        )
        result, formatter = _fake_run(
            "structured", raw, finalizer_result=structured
        )
        formatter.assert_called_once_with(
            llm=sentinel.fake_llm,
            raw_response=raw,
            expected_faults=None,
        )
        self.assertEqual(result["raw_response"], raw)
        self.assertEqual(result["json_status"], "valid_json")
        self.assertEqual(json.loads(result["prediction"]), json.loads(_canonical()))
        self.assertEqual(result["structured_output"]["status"], "valid")
        self.assertTrue(
            result["structured_output"]["original_json_status"].startswith("invalid_json:")
        )
        self.assertEqual(result["metrics"]["llm_calls"], 3)
        self.assertEqual(result["metrics"]["input_tokens"], 150)
        self.assertEqual(result["metrics"]["output_tokens"], 32)
        self.assertEqual(result["metrics"]["total_tokens"], 182)
        self.assertEqual(result["metrics"]["structured_output_tokens"], 50)
        self.assertTrue(result["metrics"]["structured_usage_complete"])

    def test_errore_non_genera_fallback(self):
        raw = _raw_missing_reason()
        result, formatter = _fake_run(
            "structured",
            raw,
            error=StructuredOutputError("finalizer offline failed"),
        )
        formatter.assert_called_once()
        self.assertEqual(result["raw_response"], raw)
        self.assertIsNone(result["prediction"])
        self.assertTrue(
            result["json_status"].startswith("invalid_structured_output:")
        )
        self.assertEqual(result["structured_output"]["status"], "invalid")
        self.assertIsNone(result["metrics"]["structured_output_tokens"])
        self.assertFalse(result["metrics"]["structured_usage_complete"])
        self.assertEqual(result["metrics"]["total_tokens"], 132)

    def test_legacy_non_usa_finalizer(self):
        raw = _canonical()
        result, formatter = _fake_run("legacy", raw)
        formatter.assert_not_called()
        self.assertEqual(result["json_status"], "valid_json")
        self.assertEqual(result["metrics"]["llm_calls"], 2)
        self.assertEqual(result["metrics"]["total_tokens"], 132)
        self.assertNotIn("structured_output", result)

    def test_audit_non_usa_finalizer(self):
        raw = _canonical()
        result, formatter = _fake_run("audit", raw)
        formatter.assert_not_called()
        self.assertEqual(result["json_status"], "valid_json")
        self.assertEqual(result["output_contract_audit"]["status"], "valid")
        self.assertNotIn("structured_output", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
