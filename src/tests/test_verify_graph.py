"""A1_VERIFY tests: synthetic candidates, local fake tools/model, no API/GT."""
import json
import unittest
from unittest.mock import patch, sentinel

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from agent.verify_graph import (
    crea_grafo_rca_verify,
    esegui_grafo_rca_verify,
)
from evaluation.experiment_config import ExperimentConfig
from evaluation.experiment_runner import run_experiment

START, END = 1000, 2000
CANONICAL = json.dumps({
    "1": {
        "root cause occurrence datetime": "2022-03-20 13:00:00",
        "root cause component": "node-5",
        "root cause reason": "node CPU load",
    }
})


@tool("tool_get_node_metrics")
def node_metrics(start_unix: int, end_unix: int, cmdb_id: str = "",
                 kpi_name: str = "") -> str:
    """Fake node metrics: no external access."""
    return f"NODE {cmdb_id} {start_unix}:{end_unix}"


@tool("tool_get_container_metrics")
def container_metrics(start_unix: int, end_unix: int, cmdb_id: str = "",
                      kpi_name: str = "") -> str:
    """Fake container metrics: no external access."""
    return f"CONTAINER {cmdb_id} {start_unix}:{end_unix}"


TOOLS = [node_metrics, container_metrics]


def report(items):
    return {
        "versione": "unified_evidence_v2",
        "caso": {"start_unix": START, "end_unix": END},
        "regole_diagnostiche_v0": {
            "versione": "rule_based_A1_R_v1",
            "finestra": {"start_unix": START, "end_unix": END},
            "totale_candidati": len(items),
            "candidati_omessi_per_budget": 0,
            "candidati_riportati": items,
        },
    }


def candidate(rule="R07", component="node-5", category="node CPU load",
              kpi=None):
    return {
        "regola": rule,
        "componente_telemetria": component,
        "classe_candidata": category,
        "timestamp_primo_segnale_unix": 1300,
        "timestamp_ultimo_segnale_unix": 1330,
        "evidenze": {"kpi_principale": kpi} if kpi else {},
    }


def msg(content="", calls=None, metadata=True):
    kwargs = {"content": content}
    if calls:
        kwargs["tool_calls"] = calls
    if metadata:
        kwargs["usage_metadata"] = {
            "input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
        }
    return AIMessage(**kwargs)


def call(tool_name, component, call_id):
    return {
        "name": tool_name,
        "args": {
            "start_unix": START, "end_unix": END, "cmdb_id": component,
        },
        "id": call_id,
        "type": "tool_call",
    }


class FakeModel:
    def __init__(self, exploration_replies, final_reply=None):
        self.replies = list(exploration_replies)
        self.final_reply = final_reply or msg(CANONICAL)
        self.calls = []
        self.tools_bound = False

    def bind_tools(self, tools):
        self.tools_bound = True
        return self

    def invoke(self, messages):
        is_final = (
            "INVESTIGATION VERIFICATION POLICY" in messages[0].content
        )
        self.calls.append(("final" if is_final else "explore", messages))
        if is_final:
            return self.final_reply
        if not self.replies:
            raise AssertionError("Exploration called too many times")
        return self.replies.pop(0)


def execute(model, data, *, budget=4, checks=2, recursion_limit=30):
    graph = crea_grafo_rca_verify(
        llm=model, tools=TOOLS,
        system_prompt="You are an RCA agent",
        max_tool_rounds=budget,
        max_verification_checks=checks,
        evidence_report=data,
        start_unix=START, end_unix=END,
    )
    return esegui_grafo_rca_verify(
        graph, richiesta="Investigate using this report",
        recursion_limit=recursion_limit, verbose=False,
    )


class TestVerificationGraph(unittest.TestCase):
    def test_no_early_tools_one_planned_call_before_final(self):
        fake = FakeModel([msg("Potential diagnosis")])
        result = execute(fake, report([candidate()]))
        self.assertIsNone(result["error"])
        self.assertEqual(json.loads(result["raw_response"]),
                         json.loads(CANONICAL))
        self.assertEqual(result["metrics"]["llm_calls"], 2)
        self.assertEqual(result["metrics"]["tool_calls"], 1)
        self.assertEqual(result["metrics"]["verification_tool_calls"], 1)
        self.assertEqual(result["metrics"]["verification_tool_results"], 1)
        self.assertEqual(result["metrics"]["tool_rounds"], 1)
        self.assertEqual(result["metrics"]["total_tokens"], 30)
        self.assertTrue(result["metrics"]["token_usage_complete"])
        self.assertEqual([name for name, _ in fake.calls],
                         ["explore", "final"])
        self.assertEqual(len(result["verification"]["piano"]), 1)

    def test_model_and_planner_calls_are_separately_accounted(self):
        model_call = call("tool_get_node_metrics", "node-4", "llm-1")
        fake = FakeModel([
            msg(calls=[model_call]),
            msg("done exploring"),
        ])
        result = execute(fake, report([candidate()]))
        self.assertIsNone(result["error"])
        self.assertEqual(result["metrics"]["llm_calls"], 3)
        self.assertEqual(result["metrics"]["exploration_tool_rounds"], 1)
        self.assertEqual(result["metrics"]["verification_tool_rounds"], 1)
        self.assertEqual(result["metrics"]["tool_calls"], 2)
        self.assertEqual(result["metrics"]["verification_tool_calls"], 1)
        self.assertEqual(result["metrics"]["tool_rounds"], 2)
        self.assertEqual(result["metrics"]["total_tokens"], 45)
        calls = [x for x in result["tool_trajectory"]
                 if x["tipo"] == "tool_call"]
        self.assertEqual([c["origine"] for c in calls], ["llm", "planner"])

    def test_matching_exploration_call_prevents_duplicate_check(self):
        model_call = call("tool_get_node_metrics", "node-5", "llm-1")
        fake = FakeModel([
            msg(calls=[model_call]),
            msg("done"),
        ])
        result = execute(fake, report([candidate()]))
        self.assertEqual(result["verification"]["piano"], [])
        self.assertEqual(result["metrics"]["verification_tool_calls"], 0)
        self.assertEqual(result["metrics"]["tool_calls"], 1)

    def test_strict_reservation_of_rounds(self):
        fake = FakeModel([
            msg(calls=[call("tool_get_node_metrics", "node-4", "llm-1")]),
            msg(calls=[call("tool_get_node_metrics", "node-6", "llm-2")]),
        ])
        result = execute(
            fake, report([candidate()]), budget=3, checks=1,
        )
        self.assertIsNone(result["error"])
        self.assertEqual([name for name, _ in fake.calls],
                         ["explore", "explore", "final"])
        self.assertEqual(result["metrics"]["exploration_tool_rounds"], 2)
        self.assertEqual(result["metrics"]["verification_tool_rounds"], 1)
        self.assertEqual(result["metrics"]["tool_rounds"], 3)

    def test_two_checks_with_two_rounds_and_no_llm_calls_for_checks(self):
        fake = FakeModel([msg("done")])
        data = report([
            candidate("R01", "node-5.frontend-0", "container CPU load"),
            candidate("R07", "node-5", "node CPU load"),
        ])
        result = execute(fake, data)
        self.assertIsNone(result["error"])
        self.assertEqual(result["metrics"]["verification_tool_calls"], 2)
        self.assertEqual(result["metrics"]["verification_tool_rounds"], 2)
        self.assertEqual(result["metrics"]["llm_calls"], 2)
        self.assertEqual(result["metrics"]["tool_rounds"], 2)

    def test_no_candidates_only_model_finalization(self):
        fake = FakeModel([msg("done")])
        result = execute(fake, report([]))
        self.assertIsNone(result["error"])
        self.assertEqual(result["metrics"]["tool_calls"], 0)
        self.assertEqual(result["metrics"]["llm_calls"], 2)
        self.assertFalse(result["verification"]["causa_verificata"])

    def test_no_planner_checks_when_reserved_budget_zero(self):
        fake = FakeModel([msg("done")])
        result = execute(fake, report([candidate()]), checks=0)
        self.assertIsNone(result["error"])
        self.assertEqual(result["verification"]["piano"], [])
        self.assertEqual(result["metrics"]["verification_tool_calls"], 0)

    def test_missing_provider_usage_is_flagged(self):
        fake = FakeModel([msg("done", metadata=False)])
        result = execute(fake, report([]))
        self.assertFalse(result["metrics"]["token_usage_complete"])
        self.assertEqual(result["metrics"]["llm_calls"], 2)

    def test_tool_call_in_finalization_rejected_without_execution(self):
        fake = FakeModel([
            msg("done"),
        ], final_reply=msg(calls=[
            call("tool_get_node_metrics", "node-5", "forbidden")
        ]))
        result = execute(fake, report([]))
        self.assertIsNone(result["raw_response"])
        self.assertIn("VerifyFinalizationToolCall", result["error"])
        self.assertEqual(result["metrics"]["tool_calls"], 0)

    def test_empty_finalization_fails_explicitly(self):
        fake = FakeModel([msg("done")], final_reply=msg(""))
        result = execute(fake, report([]))
        self.assertIsNone(result["raw_response"])
        self.assertIn("VerifyFinalizationEmpty", result["error"])

    def test_graph_must_not_have_budget_with_no_exploration(self):
        fake = FakeModel([msg("done")])
        with self.assertRaisesRegex(ValueError, "round esplorativo"):
            crea_grafo_rca_verify(
                llm=fake, tools=TOOLS, system_prompt="system",
                max_tool_rounds=2, max_verification_checks=2,
                evidence_report=report([]),
                start_unix=START, end_unix=END,
            )

    def test_config_and_prompt_accept_new_variant(self):
        from agent.prompts import get_system_prompt
        config = ExperimentConfig(
            variant="A1_VERIFY", case_id="cloudbed-1_q009",
            max_tool_rounds=6, max_verification_checks=2,
        )
        self.assertEqual(config.variant, "A1_VERIFY")
        self.assertEqual(
            get_system_prompt("A1_VERIFY"),
            get_system_prompt("A1"),
        )
        self.assertIn("a1_verify", str(config.output_path))

    def test_invalid_config_reservation_fails(self):
        for checks in (-1, 6, True):
            with self.subTest(checks=checks):
                with self.assertRaises(ValueError):
                    ExperimentConfig(
                        variant="A1_VERIFY",
                        case_id="cloudbed-1_q009",
                        max_tool_rounds=6,
                        max_verification_checks=checks,
                    )

    def test_new_runner_calls_only_new_graph(self):
        config = ExperimentConfig(
            variant="A1_VERIFY", case_id="cloudbed-1_q009",
        )
        prepared = {
            "caso": {
                "cloudbed": "cloudbed-1",
                "task_index": "task_5",
                "query_index": 9,
                "start_unix": START,
                "end_unix": END,
            },
            "tools": TOOLS,
            "richiesta": "Investigation",
            "evidence_report": report([candidate()]),
            "evidence_sha256": "some-evidence-hash",
            "preprocessing_seconds": 0,
        }
        fake_execution = {
            "raw_response": CANONICAL,
            "metrics": {
                "llm_calls": 2, "tool_calls": 1,
                "tool_rounds": 1, "input_tokens": 20,
                "output_tokens": 10, "total_tokens": 30,
                "duration_seconds": 0.01,
                "exploration_tool_rounds": 0,
                "verification_tool_rounds": 1,
            },
            "tool_trajectory": [],
            "error": None,
            "verification": {
                "piano": [{"rule_id": "R07"}],
                "causa_verificata": False,
            },
        }

        with (
            patch("evaluation.experiment_runner.prepara_esperimento",
                  return_value=prepared),
            patch("agent.verify_graph.crea_grafo_rca_verify",
                  return_value=sentinel.graph) as factory,
            patch("agent.verify_graph.esegui_grafo_rca_verify",
                  return_value=fake_execution) as executor,
            patch("agent.graph_engine.crea_grafo_rca") as old_factory,
            patch("agent.graph_engine.esegui_grafo_rca") as old_executor,
        ):
            result = run_experiment(
                config=config, llm=sentinel.llm, verbose=False, salva=False,
            )
        factory.assert_called_once()
        executor.assert_called_once()
        old_factory.assert_not_called()
        old_executor.assert_not_called()
        self.assertEqual(result["variant"], "A1_VERIFY")
        self.assertEqual(result["json_status"], "valid_json")
        self.assertEqual(result["verification"]["piano"][0]["rule_id"], "R07")
        self.assertEqual(result["exploration_round_limit"], 4)
        self.assertEqual(result["metrics"]["tool_rounds"], 1)


class TestVerifyStructuralIntegration(unittest.TestCase):
    """Il confronto A1_VERIFY/ST isola la sola informazione aggiunta."""

    def test_same_budget_same_planner_more_structural_context(self):
        from harness.structural_temporal_verifier import (
            costruisci_contesto_strutturale_temporale,
        )
        data = report([
            candidate("R07", "node-5", "node CPU load"),
            candidate("R01", "node-5.frontend-0", "container CPU load"),
        ])
        st = costruisci_contesto_strutturale_temporale(
            data, start_unix=START, end_unix=END
        )
        self.assertEqual(st["totale_relazioni"], 1)

        def run_for(structural_context):
            fake = FakeModel([msg("Explore done")])
            graph = crea_grafo_rca_verify(
                llm=fake, tools=TOOLS, system_prompt="You are an RCA agent",
                max_tool_rounds=6, max_verification_checks=2,
                evidence_report=data, start_unix=START, end_unix=END,
                structural_context=structural_context,
            )
            output = esegui_grafo_rca_verify(
                graph, richiesta="Investigate", verbose=False
            )
            last_context = fake.calls[-1][1][-1].content
            return output, last_context

        baseline, baseline_context = run_for(None)
        extended, extended_context = run_for(st)
        self.assertEqual(baseline["raw_response"], extended["raw_response"])
        self.assertEqual(
            baseline["metrics"]["verification_tool_rounds"],
            extended["metrics"]["verification_tool_rounds"]
        )
        self.assertNotIn("STRUCTURAL_CONTEXT_JSON", baseline_context)
        self.assertIn("STRUCTURAL_CONTEXT_JSON", extended_context)
        self.assertIn("segnali_quasi_contemporanei", extended_context)

    def test_new_variant_config_is_4_plus_2(self):
        from agent.prompts import get_system_prompt
        config = ExperimentConfig(
            variant="A1_VERIFY_ST", case_id="cloudbed-1_q009",
            max_tool_rounds=6, max_verification_checks=2,
        )
        self.assertEqual(config.max_tool_rounds - config.max_verification_checks, 4)
        self.assertEqual(
            get_system_prompt("A1_VERIFY_ST"),
            get_system_prompt("A1_VERIFY"),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
