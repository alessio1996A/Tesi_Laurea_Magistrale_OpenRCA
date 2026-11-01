"""Test offline della Model Factory e del percorso runner -> LangGraph.

Non utilizza dati OpenRCA, Google Drive, chiavi API o chiamate a Gemini.
"""

import json
import unittest
from unittest.mock import Mock, patch, sentinel

from agent.model_factory import crea_modello
from evaluation.experiment_config import ExperimentConfig
from evaluation.experiment_runner import run_experiment


class TestModelFactory(unittest.TestCase):
    @patch("agent.model_factory._crea_modello_google")
    def test_google_usa_il_modello_configurato(self, builder):
        builder.return_value = sentinel.llm
        llm = crea_modello("google", "gemini-3.5-flash-lite")
        self.assertIs(llm, sentinel.llm)
        builder.assert_called_once_with("gemini-3.5-flash-lite")

    @patch("agent.model_factory._crea_modello_google")
    def test_provider_normalizzato(self, builder):
        builder.return_value = sentinel.llm
        self.assertIs(
            crea_modello(" GOOGLE ", "gemini-3.5-flash-lite"),
            sentinel.llm
        )
        builder.assert_called_once_with("gemini-3.5-flash-lite")

    def test_provider_non_implementato_bloccato(self):
        with self.assertRaisesRegex(ValueError, "non ancora implementato"):
            crea_modello("openai", "modello-esempio")

    def test_config_mantiene_default_storico(self):
        config = ExperimentConfig(
            variant="A0",
            case_id="cloudbed-1_q009",
        )
        self.assertEqual(config.model_provider, "google")
        self.assertEqual(config.model_name, "gemini-3.5-flash-lite")
        self.assertEqual(config.max_tool_rounds, 6)
        self.assertEqual(config.recursion_limit, 30)

    def test_input_non_validi(self):
        with self.assertRaises(ValueError):
            crea_modello("", "gemini-3.5-flash-lite")
        with self.assertRaises(ValueError):
            crea_modello("google", " ")
        with self.assertRaises(ValueError):
            ExperimentConfig(
                variant="A0",
                case_id="cloudbed-1_q009",
                model_provider="",
            )


class TestRunnerModelAgnostic(unittest.TestCase):
    def setUp(self):
        self.config = ExperimentConfig(
            variant="A0",
            case_id="cloudbed-1_q009",
        )
        self.preparato = {
            "caso": {
                "cloudbed": "cloudbed-1",
                "task_index": "task_5",
                "query_index": 9,
            },
            "tools": [sentinel.tool],
            "richiesta": "Istruzione offline",
            "preprocessing_seconds": 0.0,
            "evidence_sha256": None,
        }
        self.esecuzione = {
            "raw_response": json.dumps({
                "1": {
                    "root cause occurrence datetime": "2022-03-20 13:00:00",
                    "root cause component": "node-5",
                    "root cause reason": "node CPU load",
                }
            }),
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

    @patch("agent.graph_engine.esegui_grafo_rca")
    @patch("agent.graph_engine.crea_grafo_rca")
    @patch("agent.model_factory.crea_modello")
    @patch("evaluation.experiment_runner.prepara_esperimento")
    def test_runner_crea_modello_attraverso_factory(
        self, prepara, factory, crea_grafo, esegui_grafo
    ):
        prepara.return_value = self.preparato
        factory.return_value = sentinel.llm
        crea_grafo.return_value = sentinel.grafo
        esegui_grafo.return_value = self.esecuzione

        risultato = run_experiment(
            config=self.config, verbose=False, salva=False
        )

        factory.assert_called_once_with(
            provider="google", model_name="gemini-3.5-flash-lite"
        )
        self.assertIs(crea_grafo.call_args.kwargs["llm"], sentinel.llm)
        self.assertEqual(risultato["model_provider"], "google")
        self.assertEqual(risultato["json_status"], "valid_json")
        self.assertEqual(risultato["variant"], "A0")

    @patch("agent.graph_engine.esegui_grafo_rca")
    @patch("agent.graph_engine.crea_grafo_rca")
    @patch("agent.model_factory.crea_modello")
    @patch("evaluation.experiment_runner.prepara_esperimento")
    def test_llm_iniettato_bypassa_factory(
        self, prepara, factory, crea_grafo, esegui_grafo
    ):
        prepara.return_value = self.preparato
        crea_grafo.return_value = sentinel.grafo
        esegui_grafo.return_value = self.esecuzione

        risultato = run_experiment(
            config=self.config,
            llm=sentinel.llm_di_test,
            verbose=False,
            salva=False,
        )

        factory.assert_not_called()
        self.assertIs(
            crea_grafo.call_args.kwargs["llm"],
            sentinel.llm_di_test
        )
        self.assertEqual(risultato["json_status"], "valid_json")


if __name__ == "__main__":
    unittest.main(verbosity=2)
