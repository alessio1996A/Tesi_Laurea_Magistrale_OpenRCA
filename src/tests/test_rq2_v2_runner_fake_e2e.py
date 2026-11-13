"""Integrazione RQ2-V2 end-to-end SINTETICA; nessun dispatcher production.

Usa run_experiment V1 INALTERATO, con LLM/tool finti e una sostituzione
temporanea del solo esecutore durante i test. Il preparatore e' simulato
per evitare Market, telemetry, GT, claim, API e il Drive scientifico.
Non implica che un reale dispatcher RQ2-V2 sia pronto o autorizzato.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

import agent.graph_engine as original_graph
import agent.model_factory as model_factory
import evaluation.experiment_runner as runner
from agent.rq2_v2_graph_engine import esegui_grafo_rca_v2
from evaluation.experiment_config import ExperimentConfig
from evaluation.rq2_evidence_bundle import (
    EvidenceBundleError, build_evidence_bundle, evidence_ids,
)
from evaluation.rq2_probe_adapter import prepare_cause_probe

CASE_ID = "cloudbed-1_q999"  # Fittizio: fuori dallo split RQ2.
INSTRUCTION = "Synthetic service issue: no ground labels available."
FINAL_JSON = json.dumps({
    "1": {
        "root cause occurrence datetime": "2023-11-15 06:13:20",
        "root cause component": "synthetic-component",
        "root cause reason": "hypothetical explanation from fake LLM",
    }
})
TOOL_NAME = "tool_get_node_metrics"
USAGE = {"input_tokens": 30, "output_tokens": 10, "total_tokens": 40}


@tool(TOOL_NAME)
def fake_node_metrics(node: str) -> str:
    """Restituisce una osservazione sintetica non dipendente dal benchmark."""
    return "synthetic node observation: " + node


class ParallelSameNameFakeLLM:
    """Emette due call allo stesso tool nello stesso round, poi il JSON D."""

    def __init__(self):
        self.invocations = 0

    def bind_tools(self, tools):
        assert [t.name for t in tools] == [TOOL_NAME]
        return self

    def invoke(self, messages):
        self.invocations += 1
        if self.invocations == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {"name": TOOL_NAME, "args": {"node": "A"}, "id": "fake-id-A"},
                    {"name": TOOL_NAME, "args": {"node": "B"}, "id": "fake-id-B"},
                ],
                usage_metadata=dict(USAGE),
            )
        if self.invocations == 2:
            return AIMessage(content=FINAL_JSON, usage_metadata=dict(USAGE))
        raise AssertionError("Terza invocazione LLM inattesa")


def fake_preparation(config: ExperimentConfig) -> dict:
    if config.case_id != CASE_ID or config.canonical_variant not in ("A1", "A1_8R"):
        raise AssertionError("Solo caso e harness sintetici ammessi")
    return {
        "caso": {
            "case_id": CASE_ID,
            "cloudbed": "cloudbed-1",
            "task_index": "task_7",
            "query_index": 999,
            "instruction": INSTRUCTION,
            "start_unix": 1_700_000_000,
            "end_unix": 1_700_001_000,
        },
        "tools": [fake_node_metrics],
        "richiesta": "Synthetic RCA instruction: " + INSTRUCTION,
        "evidence_report": {
            "versione": "unified_evidence_v2",
            "synthetic": True,
        },
        "evidence_sha256": "f" * 64,
        "preprocessing_seconds": 0.0,
    }


class RQ2V2RunnerFakeE2ETests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)

    def _run(self, *, harness="A1", v2=True):
        fake_llm = ParallelSameNameFakeLLM()
        config = ExperimentConfig(
            variant=harness,
            case_id=CASE_ID,
            model_name="claude-sonnet-5-5",
            model_provider="anthropic",
            max_tool_rounds=6,
            recursion_limit=30,
            output_contract_mode="v2_enforce",
            variant_scheme="current",
            data_dir=self.root,
            repo_dir=self.root,
        )
        with (
            patch.object(
                runner, "prepara_esperimento",
                side_effect=fake_preparation,
            ) as prep,
            patch.object(
                model_factory, "crea_modello",
                side_effect=AssertionError("Nessun client provider nel test"),
            ) as provider,
        ):
            if v2:
                # Intervento SOLO temporaneo nella memoria del test,
                # mai in un sorgente o nel runner scientifico V1.
                with patch.object(
                    original_graph, "esegui_grafo_rca", esegui_grafo_rca_v2
                ):
                    result = runner.run_experiment(
                        config, llm=fake_llm, verbose=False, salva=False,
                    )
            else:
                result = runner.run_experiment(
                    config, llm=fake_llm, verbose=False, salva=False,
                )
        prep.assert_called_once_with(config)
        provider.assert_not_called()
        self.assertEqual(fake_llm.invocations, 2)
        self.assertEqual(list(self.root.iterdir()), [])
        return result

    def test_real_runner_v2_A1_and_A1_8R_build_strict_c_probe(self):
        for harness in ("A1", "A1_8R"):
            with self.subTest(harness=harness):
                result = self._run(harness=harness, v2=True)
                self.assertIsNone(result["error"])
                self.assertEqual(result["json_status"], "valid_json")
                self.assertEqual(result["raw_response"], FINAL_JSON)
                self.assertEqual(result["variant"], harness)
                self.assertEqual(result["metrics"]["llm_calls"], 2)
                self.assertEqual(result["metrics"]["tool_rounds"], 1)
                self.assertEqual(result["metrics"]["tool_calls"], 2)
                self.assertEqual(result["metrics"]["total_tokens"], 80)
                self.assertTrue(result["metrics"]["token_usage_complete"])

                trace = result["tool_trajectory"]
                self.assertEqual(
                    [e["tipo"] for e in trace],
                    ["tool_call", "tool_call", "tool_result", "tool_result"],
                )
                self.assertEqual(
                    {e["tool_call_id"] for e in trace[:2]},
                    {"fake-id-A", "fake-id-B"},
                )
                self.assertEqual(
                    {e["tool_call_id"] for e in trace[2:]},
                    {"fake-id-A", "fake-id-B"},
                )
                bundle = build_evidence_bundle(
                    trace, allowed_tool_names={TOOL_NAME}
                )
                self.assertEqual(bundle["observations_count"], 2)
                pairs = {
                    item["tool_call_id"]: (
                        item["arguments"]["node"], item["observation_text"]
                    )
                    for item in bundle["evidence"]
                }
                self.assertEqual(pairs, {
                    "fake-id-A": ("A", "synthetic node observation: A"),
                    "fake-id-B": ("B", "synthetic node observation: B"),
                })
                package = prepare_cause_probe(
                    original_instruction=INSTRUCTION,
                    diagnostic_run=result,
                    allowed_tool_names={TOOL_NAME},
                )
                self.assertEqual(package["stage"], "C_cause_probe")
                self.assertEqual(package["bundle_sha256"], bundle["bundle_sha256"])
                self.assertFalse(package["ready_for_api"])
                self.assertEqual(package["model_api_calls"], 0)
                self.assertNotIn(FINAL_JSON, package["messages"][1]["content"])
                self.assertEqual(evidence_ids(bundle), {"E001", "E002"})

    def test_v1_vs_v2_only_trajectory_id_fields_differ(self):
        v1 = self._run(v2=False)
        v2 = self._run(v2=True)
        for key in ("raw_response", "json_status", "prediction", "error",
                    "variant", "output_contract_v2"):
            self.assertEqual(v1[key], v2[key])
        metrics_v1 = {k: v for k, v in v1["metrics"].items()
                      if k not in ("duration_seconds", "end_to_end_seconds")}
        metrics_v2 = {k: v for k, v in v2["metrics"].items()
                      if k not in ("duration_seconds", "end_to_end_seconds")}
        self.assertEqual(metrics_v1, metrics_v2)
        self.assertEqual(
            v1["tool_trajectory"],
            [{k: v for k, v in event.items() if k != "tool_call_id"}
             for event in v2["tool_trajectory"]],
        )
        with self.assertRaisesRegex(EvidenceBundleError, "Ambiguous"):
            build_evidence_bundle(
                v1["tool_trajectory"], allowed_tool_names={TOOL_NAME}
            )
        self.assertEqual(
            build_evidence_bundle(
                v2["tool_trajectory"], allowed_tool_names={TOOL_NAME}
            )["observations_count"], 2
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
