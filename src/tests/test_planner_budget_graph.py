"""Regression test LangGraph: 4+2 vs 5+1 really changes round allocation.

Synthetic messages and local tools ONLY. Zero Gemini API and zero dataset access.
"""
import unittest
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from agent.verify_graph import crea_grafo_rca_verify, esegui_grafo_rca_verify

START, END = 1000, 2000


@tool("tool_get_node_metrics")
def fake_node_metrics(start_unix: int, end_unix: int,
                      cmdb_id: str = "", kpi_name: str = "") -> str:
    """Return synthetic node data, never access OpenRCA."""
    return "synthetic node metric"


@tool("tool_get_container_metrics")
def fake_container_metrics(start_unix: int, end_unix: int,
                           cmdb_id: str = "", kpi_name: str = "") -> str:
    """Return synthetic container data, never access OpenRCA."""
    return "synthetic container metric"


class FakeModel:
    def __init__(self):
        self.explorations = 0
        self.exploration_prompts = []
        self.finals = 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        if "INVESTIGATION VERIFICATION POLICY" in messages[0].content:
            self.finals += 1
            return AIMessage(content='{"1":{"root cause occurrence datetime":'
                              '"2022-03-20 13:00:00","root cause component":'
                              '"node-5","root cause reason":"node CPU load"}}',
                             usage_metadata={"input_tokens": 10,
                                             "output_tokens": 5,
                                             "total_tokens": 15})
        self.explorations += 1
        self.exploration_prompts.append(messages[0].content)
        n = self.explorations
        return AIMessage(
            content="",
            tool_calls=[{
                "name": "tool_get_node_metrics",
                "args": {"start_unix": START, "end_unix": END,
                         "cmdb_id": f"node-unrelated-{n}"},
                "id": f"llm-{n}", "type": "tool_call",
            }],
            usage_metadata={"input_tokens": 10,
                            "output_tokens": 5, "total_tokens": 15},
        )


def report():
    return {
        "versione": "unified_evidence_v2",
        "caso": {"start_unix": START, "end_unix": END},
        "regole_diagnostiche_v0": {
            "versione": "rule_based_A1_R_v1",
            "finestra": {"start_unix": START, "end_unix": END},
            "candidati_omessi_per_budget": 0,
            "totale_candidati": 2,
            "candidati_riportati": [
                {
                    "regola": "R01",
                    "classe_candidata": "container CPU load",
                    "componente_telemetria": "node-5.frontend-0",
                    "timestamp_primo_segnale_unix": 1300,
                    "timestamp_ultimo_segnale_unix": 1330,
                    "evidenze": {},
                },
                {
                    "regola": "R07",
                    "classe_candidata": "node CPU load",
                    "componente_telemetria": "node-5",
                    "timestamp_primo_segnale_unix": 1300,
                    "timestamp_ultimo_segnale_unix": 1330,
                    "evidenze": {},
                },
            ],
        },
    }


def run(checks):
    fake = FakeModel()
    graph = crea_grafo_rca_verify(
        llm=fake, tools=[fake_node_metrics, fake_container_metrics],
        system_prompt="CONSTANT RCA PROMPT", max_tool_rounds=6,
        max_verification_checks=checks, evidence_report=report(),
        start_unix=START, end_unix=END,
    )
    result = esegui_grafo_rca_verify(
        graph, richiesta="Synthetic investigation", recursion_limit=30,
        verbose=False,
    )
    return fake, result


class TestPlannerBudgetGraph(unittest.TestCase):
    def test_four_two_and_five_one_same_six_round_budget(self):
        control, c = run(2)
        treatment, t = run(1)
        self.assertIsNone(c["error"])
        self.assertIsNone(t["error"])
        self.assertEqual(c["metrics"]["exploration_tool_rounds"], 4)
        self.assertEqual(c["metrics"]["verification_tool_rounds"], 2)
        self.assertEqual(t["metrics"]["exploration_tool_rounds"], 5)
        self.assertEqual(t["metrics"]["verification_tool_rounds"], 1)
        self.assertEqual(c["metrics"]["tool_rounds"], 6)
        self.assertEqual(t["metrics"]["tool_rounds"], 6)
        self.assertEqual(c["metrics"]["verification_tool_calls"], 2)
        self.assertEqual(t["metrics"]["verification_tool_calls"], 1)
        self.assertEqual(control.explorations, 4)
        self.assertEqual(treatment.explorations, 5)
        self.assertEqual(control.finals, treatment.finals)
        self.assertEqual(control.finals, 1)
        self.assertEqual(c["raw_response"], t["raw_response"])
        self.assertEqual(set(control.exploration_prompts),
                         {"CONSTANT RCA PROMPT"})
        self.assertEqual(set(treatment.exploration_prompts),
                         {"CONSTANT RCA PROMPT"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
