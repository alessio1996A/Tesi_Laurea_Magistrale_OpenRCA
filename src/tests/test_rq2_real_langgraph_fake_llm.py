"""Real RQ1 LangGraph + RQ1 experiment_runner with a fake LLM and fake tool.

SYNTHETIC ONLY. Patches ONLY experiment preparation to avoid ALL Market,
manifest, tools/telemetry I/O. Calls the UNCHANGED original
run_experiment(config, llm=<fake>, salva=False) and actual graph_engine.
No network, API/SDK provider instantiation, scoring, GT or file output.

This tests the real graph/runtime path, NOT genuine A1/A1_8R preprocessing
and NOT the actual model remote endpoints or prompt execution quality.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

import agent.model_factory as factory
from evaluation.experiment_config import ExperimentConfig
import evaluation.experiment_runner as runner
from output.v2_task_contract import task_output_instruction


INSTRUCTION = "The cloud service experienced one failure in the observed time window."
FINAL_JSON = json.dumps({
    "1": {
        "root cause occurrence datetime": "2023-11-15 06:13:20",
        "root cause component": "synthetic-component",
        "root cause reason": "synthetic reason from synthetic telemetry",
    }
})
VALID_USAGE = {"input_tokens": 30, "output_tokens": 10, "total_tokens": 40}
FAKE_CASE_ID = "cloudbed-1_q999"  # intentionally not an actual RQ2 case
FAKE_START = 1_700_000_000
FAKE_END = 1_700_001_000

TOOL_USE_COUNT = []


@tool
def synthetic_probe(query: str) -> str:
    """Return a wholly synthetic observation without opening any file."""
    TOOL_USE_COUNT.append(query)
    return "synthetic observation, not real OpenRCA evidence"


def fake_experiment_preparation(config: ExperimentConfig) -> dict:
    """Synthetic case and tool, no original dataset/manifest accessed."""
    if config.case_id != FAKE_CASE_ID:
        raise AssertionError("Only fake case may enter this test")
    if config.canonical_variant not in ("A1", "A1_8R"):
        raise AssertionError("Only real selected graph variants may be tested")
    return {
        "caso": {
            "case_id": FAKE_CASE_ID,
            "cloudbed": "cloudbed-1",
            "task_index": "task_7",
            "query_index": 0,
            "instruction": INSTRUCTION,
            "start_unix": FAKE_START,
            "end_unix": FAKE_END,
        },
        "tools": [synthetic_probe],
        "richiesta": (
            "Official OpenRCA instruction:\n" + INSTRUCTION
            + "\nSynthetic diagnostic context, no access to real telemetry."
        ),
        "evidence_report": {
            "versione": "unified_evidence_v2",
            "synthetic_observation_only": True,
        },
        "evidence_sha256": "f" * 64,
        "preprocessing_seconds": 0.0,
    }


class FakeLangGraphLLM:
    """Minimal chat-like object implementing bind_tools and invoke only.

    First N bound calls request one fake tool. All subsequent calls answer
    with the prescribed synthetic task JSON (or a controlled error). Real
    graph does the routing/tool invocation and token accounting.
    """

    def __init__(
        self, *, tool_rounds: int = 1, final_content: str = FINAL_JSON,
        final_tool_call: bool = False, missing_usage: bool = False,
    ):
        self.tool_rounds = tool_rounds
        self.final_content = final_content
        self.final_tool_call = final_tool_call
        self.missing_usage = missing_usage
        self.bound_calls = 0
        self.invocations = []
        self.tools_bound = False

    def bind_tools(self, tools):
        self.tools_bound = True
        self.bound_tool_names = [t.name for t in tools]
        return self

    def invoke(self, messages):
        self.invocations.append(messages)
        call_index = len(self.invocations)
        usage = None if self.missing_usage else dict(VALID_USAGE)
        if call_index <= self.tool_rounds:
            self.bound_calls += 1
            return AIMessage(
                content="",
                tool_calls=[{
                    "name": "synthetic_probe",
                    "args": {"query": f"fake-round-{call_index}"},
                    "id": f"synthetic-call-{call_index}",
                }],
                usage_metadata=usage,
            )
        if self.final_tool_call:
            return AIMessage(
                content="",
                tool_calls=[{
                    "name": "synthetic_probe",
                    "args": {"query": "forbidden finalization call"},
                    "id": "forbidden-finalization",
                }],
                usage_metadata=usage,
            )
        return AIMessage(content=self.final_content, usage_metadata=usage)


class RQ2RealLangGraphFakeTests(unittest.TestCase):
    def setUp(self):
        TOOL_USE_COUNT.clear()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def _run(self, model=None, *, variant="A1", provider="anthropic",
             tool_rounds=1, max_tool_rounds=6,
             output_mode="v2_enforce"):
        model = model or FakeLangGraphLLM(tool_rounds=tool_rounds)
        cfg = ExperimentConfig(
            variant=variant, case_id=FAKE_CASE_ID,
            model_name=(
                "claude-sonnet-5-5" if provider == "anthropic"
                else "gemini-3.5-flash-lite"
            ),
            model_provider=provider, max_tool_rounds=max_tool_rounds,
            recursion_limit=30, output_contract_mode=output_mode,
            variant_scheme="current", data_dir=self.root, repo_dir=self.root,
        )
        with (
            patch.object(
                runner, "prepara_esperimento",
                side_effect=fake_experiment_preparation,
            ) as prep,
            patch.object(
                factory, "crea_modello",
                side_effect=AssertionError("NO PROVIDER CLIENT"),
            ) as provider_factory,
        ):
            result = runner.run_experiment(
                cfg, llm=model, verbose=False, salva=False,
            )
        prep.assert_called_once_with(cfg)
        provider_factory.assert_not_called()
        return result, model, cfg

    def test_original_a1_graph_executes_real_toolnode_on_fake_evidence(self):
        result, fake, _ = self._run()
        self.assertEqual(TOOL_USE_COUNT, ["fake-round-1"])
        self.assertEqual(fake.bound_tool_names, ["synthetic_probe"])
        self.assertEqual(result["metrics"]["tool_rounds"], 1)
        self.assertEqual(result["metrics"]["tool_calls"], 1)
        self.assertEqual(result["metrics"]["llm_calls"], 2)
        self.assertIsNone(result["error"])

    def test_original_a1_8r_uses_same_graph_and_fake_tool(self):
        result, fake, _ = self._run(variant="A1_8R")
        self.assertEqual(result["variant"], "A1_8R")
        self.assertEqual(result["variant_scheme"], "current")
        self.assertEqual(result["metrics"]["tool_calls"], 1)
        self.assertEqual(fake.bound_calls, 1)
        self.assertIsNone(result["error"])

    def test_uses_v2_task_aware_contract_not_legacy_default(self):
        result, fake, cfg = self._run()
        self.assertEqual(result["output_contract_mode"], "v2_enforce")
        self.assertEqual(cfg.output_contract_mode, "v2_enforce")
        self.assertEqual(result["json_status"], "valid_json")
        self.assertTrue(result["output_contract_v2"]["valid"])
        self.assertEqual(result["prediction"], FINAL_JSON)
        self.assertEqual(json.loads(result["raw_response"]), json.loads(FINAL_JSON))

    def test_v2_enforce_prompt_appends_original_task_instruction(self):
        _, fake, cfg = self._run()
        first_system = fake.invocations[0][0].content
        expected = task_output_instruction(
            task_index="task_7", instruction=INSTRUCTION,
        )
        self.assertIn(expected, first_system)
        self.assertIn("V2 TASK-SPECIFIC OUTPUT CONTRACT", first_system)

    def test_tool_calls_and_tool_results_present_in_RQ1_trajectory(self):
        result, _, _ = self._run()
        trajectory = result["tool_trajectory"]
        self.assertEqual([e["tipo"] for e in trajectory],
                         ["tool_call", "tool_result"])
        self.assertEqual(trajectory[0]["nome"], "synthetic_probe")
        self.assertEqual(trajectory[1]["nome"], "synthetic_probe")
        self.assertIn("synthetic observation", trajectory[1]["risposta"])

    def test_token_usage_sums_actual_fake_ai_messages(self):
        result, _, _ = self._run()
        self.assertEqual(result["metrics"]["input_tokens"], 60)
        self.assertEqual(result["metrics"]["output_tokens"], 20)
        self.assertEqual(result["metrics"]["total_tokens"], 80)
        self.assertTrue(result["metrics"]["token_usage_complete"])

    def test_full_six_tool_round_budget_then_one_finalization(self):
        result, fake, _ = self._run(tool_rounds=6)
        self.assertEqual(result["metrics"]["tool_rounds"], 6)
        self.assertEqual(result["metrics"]["tool_calls"], 6)
        self.assertEqual(result["metrics"]["llm_calls"], 7)
        self.assertEqual(len(TOOL_USE_COUNT), 6)
        self.assertEqual(len(fake.invocations), 7)
        self.assertTrue(result["output_contract_v2"]["valid"])

    def test_finalization_tool_request_after_budget_is_not_executed(self):
        fake = FakeLangGraphLLM(tool_rounds=6, final_tool_call=True)
        result, _, _ = self._run(model=fake)
        self.assertEqual(len(TOOL_USE_COUNT), 6)
        self.assertEqual(result["metrics"]["tool_rounds"], 6)
        self.assertIn("AgentBudgetExhausted", result["error"])
        self.assertIsNone(result["raw_response"])
        self.assertIsNone(result["prediction"])

    def test_finalization_empty_after_budget_is_explicit_error(self):
        fake = FakeLangGraphLLM(tool_rounds=6, final_content="")
        result, _, _ = self._run(model=fake)
        self.assertEqual(len(TOOL_USE_COUNT), 6)
        self.assertIn("AgentFinalizationEmpty", result["error"])
        self.assertIsNone(result["raw_response"])

    def test_invalid_v2_output_is_preserved_as_invalid(self):
        fake = FakeLangGraphLLM(final_content="NOT VALID JSON")
        result, _, _ = self._run(model=fake)
        self.assertTrue(result["json_status"].startswith("invalid_v2_task_output"))
        self.assertEqual(result["raw_response"], "NOT VALID JSON")
        self.assertIsNone(result["prediction"])
        self.assertFalse(result["output_contract_v2"]["valid"])

    def test_missing_llm_token_usage_is_not_fabricated(self):
        fake = FakeLangGraphLLM(missing_usage=True)
        result, _, _ = self._run(model=fake)
        self.assertFalse(result["metrics"]["token_usage_complete"])
        self.assertEqual(result["metrics"]["input_tokens"], 0)
        self.assertEqual(result["metrics"]["output_tokens"], 0)

    def test_google_provider_string_does_not_create_google_client(self):
        result, _, _ = self._run(provider="google")
        self.assertEqual(result["model_provider"], "google")
        self.assertEqual(result["model"], "gemini-3.5-flash-lite")
        self.assertEqual(result["json_status"], "valid_json")

    def test_no_original_result_or_market_files_written(self):
        result, _, cfg = self._run()
        self.assertFalse(cfg.output_path.exists())
        self.assertFalse(cfg.market_zip_path.exists())
        self.assertFalse(cfg.manifest_path.exists())
        self.assertFalse((self.root / "data/results").exists())
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(result["case_id"], FAKE_CASE_ID)


if __name__ == "__main__":
    unittest.main()
