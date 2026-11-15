"""OFFLINE integration audit: actual unmodified experiment_runner -> V3 D capture.

Mocks ONLY the GT-free preparation, graph constructors and SDK model. The
real experiment_runner, original D executors, task-specific output
contract, and V3 exact-text stream bridge execute in-process. No file
dataset, Market, GT, credentials, provider calls, ledger or paid stage.
"""
from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage

import agent.graph_engine as react
import agent.verify_graph as verify
import evaluation.experiment_runner as runner
from evaluation.experiment_config import ExperimentConfig
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_v2_ck_text_extraction_candidate import POLICY
from evaluation.rq2_v3_d_runner_capture_candidate import (
    DRunnerCaptureBlocked,
    V3DRunnerCapture,
)
from test_rq2_v3_d_contentblock_audit_offline import VALID_D


USAGE = {"input_tokens": 50, "output_tokens": 20, "total_tokens": 70}


def _fragments(raw: str) -> list:
    before, after = raw.split("node-1", 1)
    return [
        {"type": "text", "text": before},
        {"type": "text", "text": "node-1" + after},
    ]


def _case_fixture():
    return {
        "cloudbed": "cloudbed-1",
        "task_index": "task_7",
        "query_index": 32,
        "instruction": "Investigate one fault using telemetry evidence.",
        "start_unix": -30000,
        "end_unix": -20000,
    }


def _prepared_fixture(config):
    return {
        "caso": _case_fixture(),
        "tools": [],
        "richiesta": "Synthetic GT-free incident.",
        "preprocessing_seconds": 0.0,
        "evidence_sha256": "f" * 64,
        "evidence_report": {},
    }


class FakeGraph:
    def __init__(self, engine, content):
        self.engine = engine
        self.original = AIMessage(
            content=content,
            usage_metadata=USAGE,
            response_metadata={"finish_reason": "stop"},
        )
        self.original_copy = copy.deepcopy(self.original.content)
        self.calls = 0

    def stream(self, initial_state, *, config, stream_mode):
        self.calls += 1
        assert config == {"recursion_limit": 30}
        assert stream_mode == "updates"
        assert initial_state["messages"]
        if self.engine == "react":
            yield {
                "agente": {
                    "messages": [self.original],
                    "tool_rounds": 0,
                    "finalization_error": None,
                }
            }
        else:
            yield {
                "finale": {
                    "messages": [self.original],
                    "finalization_error": None,
                }
            }


class V3DRunnerCaptureCandidateOfflineTests(unittest.TestCase):
    def _run(self, harness="A0", model="gemini", *, raw=VALID_D):
        spec = CANDIDATE_MODELS[model]
        config = ExperimentConfig(
            variant=harness,
            case_id="cloudbed-1_q032",
            model_name=spec["model_id"],
            model_provider=spec["provider"],
            output_contract_mode="v2_enforce",
            max_tool_rounds=6,
            max_verification_checks=2,
            recursion_limit=30,
            variant_scheme="current",
        )
        graphs = []

        def react_graph(**kwargs):
            self.assertEqual(kwargs["max_tool_rounds"], 6)
            graph = FakeGraph("react", _fragments(raw))
            graphs.append(graph)
            return graph

        def verify_graph(**kwargs):
            self.assertEqual(kwargs["max_tool_rounds"], 6)
            self.assertEqual(kwargs["max_verification_checks"], 2)
            graph = FakeGraph("verify", _fragments(raw))
            graphs.append(graph)
            return graph

        # The real runner is executed; only external data, graph creation
        # and the paid LLM are replaced with synthetic, inert objects.
        with (
            patch.object(runner, "prepara_esperimento", side_effect=_prepared_fixture),
            patch.object(runner, "get_system_prompt",
                         return_value="Synthetic system prompt"),
            patch.object(react, "crea_grafo_rca", side_effect=react_graph),
            patch.object(verify, "crea_grafo_rca_verify", side_effect=verify_graph),
            patch("harness.structural_temporal_verifier."
                  "costruisci_contesto_strutturale_temporale",
                  return_value={"schema": "synthetic_observation"}),
        ):
            capture = V3DRunnerCapture(harness=harness)
            with capture:
                result = runner.run_experiment(
                    config, llm=object(), verbose=False, salva=False
                )
            receipt = capture.build_receipt(result)

        self.assertEqual(len(graphs), 1)
        self.assertEqual(graphs[0].calls, 1)
        self.assertEqual(graphs[0].original.content, graphs[0].original_copy)
        self.assertFalse(receipt["can_execute_api"])
        self.assertFalse(receipt["scientific_release_frozen"])
        self.assertFalse(receipt["can_write_scientific_records"])
        return receipt

    def test_all_five_harnesses_use_original_runner_and_exact_d_text(self):
        for harness in ("A0", "A1", "A1_8R", "A1_8R_Planning", "A1_PAVE"):
            with self.subTest(harness=harness):
                receipt = self._run(harness)
                result = receipt["diagnostic_run"]
                self.assertEqual(result["variant"], harness)
                self.assertEqual(result["raw_response"], VALID_D)
                self.assertEqual(result["json_status"], "valid_json")
                self.assertTrue(result["output_contract_v2"]["valid"])
                self.assertEqual(result["metrics"]["llm_calls"], 1)
                self.assertEqual(result["metrics"]["input_tokens"], 50)
                self.assertEqual(result["metrics"]["output_tokens"], 20)
                self.assertEqual(result["metrics"]["total_tokens"], 70)
                self.assertTrue(result["metrics"]["token_usage_complete"])
                meta = receipt["d_final_text_extraction"]
                self.assertEqual(meta["policy"], POLICY)
                self.assertEqual(meta["text_blocks"], 2)
                self.assertEqual(meta["nontext_blocks"], 0)
                self.assertEqual(meta["content_kind"], "list")

    def test_same_technical_behavior_for_three_provider_models(self):
        for model in ("gemini", "sonnet", "haiku"):
            with self.subTest(model=model):
                receipt = self._run(model=model)
                result = receipt["diagnostic_run"]
                self.assertEqual(result["model"], CANDIDATE_MODELS[model]["model_id"])
                self.assertEqual(result["model_provider"],
                                 CANDIDATE_MODELS[model]["provider"])
                self.assertEqual(result["raw_response"], VALID_D)
                self.assertEqual(receipt["d_final_text_extraction"]["policy"], POLICY)

    def test_genuinely_malformed_d_remains_invalid_with_real_contract(self):
        bad = VALID_D.replace("synthetic-node-1", "synthetic-\nnode-1")
        for harness in ("A0", "A1_8R_Planning"):
            with self.subTest(harness=harness):
                receipt = self._run(harness=harness, raw=bad)
                result = receipt["diagnostic_run"]
                self.assertEqual(result["raw_response"], bad)
                self.assertTrue(result["json_status"].startswith(
                    "invalid_v2_task_output:"
                ))
                self.assertFalse(result["output_contract_v2"]["valid"])
                self.assertIsNone(result["prediction"])

    def test_pave_context_is_observational_and_preserved(self):
        receipt = self._run(harness="A1_PAVE")
        run = receipt["diagnostic_run"]
        self.assertEqual(
            run["structural_temporal_context"],
            {"schema": "synthetic_observation"},
        )
        self.assertIsInstance(
            run["structural_temporal_context_sha256"], str
        )

    def test_no_extra_invoke_or_model_construction_in_synthetic_runner(self):
        receipt = self._run(harness="A0")
        result = receipt["diagnostic_run"]
        self.assertEqual(result["metrics"]["llm_calls"], 1)
        self.assertEqual(result["metrics"]["tool_calls"], 0)
        self.assertEqual(result["metrics"]["tool_rounds"], 0)

    def test_invalid_harness_blocked_before_patch(self):
        with self.assertRaises(DRunnerCaptureBlocked):
            V3DRunnerCapture(harness="not-a-real-harness")

    def test_capture_cannot_be_reused_or_exported_before_completion(self):
        capture = V3DRunnerCapture(harness="A0")
        with capture:
            with self.assertRaises(DRunnerCaptureBlocked):
                capture.build_receipt({"variant": "A0"})
        with self.assertRaises(DRunnerCaptureBlocked):
            capture.build_receipt({"variant": "A0"})
        with self.assertRaises(DRunnerCaptureBlocked):
            with capture:
                pass


if __name__ == "__main__":
    unittest.main()
