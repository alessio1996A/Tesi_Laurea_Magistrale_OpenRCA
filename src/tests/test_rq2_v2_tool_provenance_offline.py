"""Test deterministici SOLO OFFLINE per provenance RQ2-V2.

Nessuna API, Market.zip, ground truth, archivio o credenziale.
Non autorizzano nuovi esperimenti reali: verificano solo la semantica
della traiettoria e l'invarianza della diagnostica V1.
"""
from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from agent.graph_engine import (
    crea_grafo_rca,
    esegui_grafo_rca as esegui_grafo_rca_v1,
)
from agent.rq2_v2_graph_engine import esegui_grafo_rca_v2
from evaluation.rq2_evidence_bundle import (
    EvidenceBundleError,
    build_evidence_bundle,
)

TOOL = "tool_probe"
USAGE = {
    "input_tokens": 14,
    "output_tokens": 6,
    "total_tokens": 20,
}
FINAL = '{"1":{"root cause reason":"synthetic only"}}'


def _call(query: str, call_id: str | None) -> dict:
    value = {"name": TOOL, "args": {"query": query}}
    if call_id is not None:
        value["id"] = call_id
    return value


def _ai(calls: list[dict]) -> AIMessage:
    return AIMessage(content="", tool_calls=calls, usage_metadata=dict(USAGE))


def _tool_result(query: str, call_id: str | None):
    if call_id is None:
        # La classe usata dal runner non deve dedurre alcun ID inesistente.
        return SimpleNamespace(name=TOOL, content="obs-" + query,
                               tool_call_id=None)
    return ToolMessage(content="obs-" + query, name=TOOL,
                       tool_call_id=call_id)


class _SyntheticGraph:
    """Grafo stream fittizio: replica solo gli eventi LangGraph noti."""

    def __init__(self, calls: list[dict], results: list):
        self.calls = calls
        self.results = results

    def stream(self, state, config, stream_mode):
        assert stream_mode == "updates"
        assert config["recursion_limit"] == 30
        assert state["tool_rounds"] == 0
        if any(call.get("id") is None for call in self.calls):
            # Un messaggio senza id e' un caso degradato: AIMessage
            # puo' normalizzare/scartare tool_calls non conformi.
            # Qui testiamo esplicitamente il comportamento difensivo
            # dell'esecutore, NON il parser Pydantic di LangChain.
            msg = SimpleNamespace(
                tool_calls=copy.deepcopy(self.calls),
                usage_metadata=dict(USAGE),
                content="",
            )
        else:
            # Casi ordinari: usa un vero AIMessage.
            msg = _ai(self.calls)
        yield {"agente": {"messages": [msg], "tool_rounds": 1}}
        yield {"tools": {"messages": self.results}}
        yield {"agente": {
            "messages": [AIMessage(content=FINAL, usage_metadata=dict(USAGE))],
            "tool_rounds": 1,
        }}


@tool(TOOL)
def _synthetic_tool(query: str) -> str:
    """Restituisce una misura puramente sintetica, senza I/O."""
    return "obs-" + query


class _FakeModel:
    """Modello finto che esercita il vero LangGraph e il vero ToolNode."""

    def __init__(self):
        self.round = 0

    def bind_tools(self, tools):
        assert [x.name for x in tools] == [TOOL]
        return self

    def invoke(self, messages):
        self.round += 1
        if self.round == 1:
            return _ai([_call("A", "v2-call-a"),
                        _call("B", "v2-call-b")])
        if self.round == 2:
            return AIMessage(content=FINAL, usage_metadata=dict(USAGE))
        raise AssertionError("Unexpected extra LLM invocation")


class RQ2V2ToolProvenanceOfflineTests(unittest.TestCase):
    def test_v1_v2_same_answer_metrics_and_original_event_fields(self):
        original_calls = [_call("A", "same-tool-A"), _call("B", "same-tool-B")]
        original_results = [
            _tool_result("B", "same-tool-B"),
            _tool_result("A", "same-tool-A"),
        ]
        a = esegui_grafo_rca_v1(
            _SyntheticGraph(copy.deepcopy(original_calls),
                            copy.deepcopy(original_results)),
            richiesta="Synthetic RCA request", verbose=False,
        )
        b = esegui_grafo_rca_v2(
            _SyntheticGraph(copy.deepcopy(original_calls),
                            copy.deepcopy(original_results)),
            richiesta="Synthetic RCA request", verbose=False,
        )
        self.assertIsNone(a["error"])
        self.assertIsNone(b["error"])
        self.assertEqual(a["raw_response"], b["raw_response"])
        self.assertEqual(
            {k: v for k, v in a["metrics"].items() if k != "duration_seconds"},
            {k: v for k, v in b["metrics"].items() if k != "duration_seconds"},
        )
        self.assertEqual(
            a["tool_trajectory"],
            [{k: v for k, v in event.items() if k != "tool_call_id"}
             for event in b["tool_trajectory"]],
        )
        self.assertTrue(all("tool_call_id" not in ev
                            for ev in a["tool_trajectory"]))
        self.assertEqual([e["tool_call_id"] for e in b["tool_trajectory"]],
                         ["same-tool-A", "same-tool-B",
                          "same-tool-B", "same-tool-A"])

    def test_reverse_result_order_maps_exact_original_arguments(self):
        graph = _SyntheticGraph(
            [_call("A", "id-A"), _call("B", "id-B")],
            [_tool_result("B", "id-B"), _tool_result("A", "id-A")],
        )
        output = esegui_grafo_rca_v2(
            graph, richiesta="Synthetic RCA request", verbose=False
        )
        bundle = build_evidence_bundle(
            output["tool_trajectory"], allowed_tool_names={TOOL}
        )
        self.assertEqual(bundle["observations_count"], 2)
        self.assertEqual(
            [(ev["tool_call_id"], ev["arguments"]["query"],
              ev["observation_text"]) for ev in bundle["evidence"]],
            [("id-B", "B", "obs-B"), ("id-A", "A", "obs-A")],
        )

    def test_real_langgraph_toolnode_with_two_parallel_same_name_calls(self):
        fake = _FakeModel()
        graph = crea_grafo_rca(
            fake, [_synthetic_tool], system_prompt="Synthetic only",
            max_tool_rounds=6,
        )
        result = esegui_grafo_rca_v2(
            graph, richiesta="Synthetic tool comparison", verbose=False
        )
        self.assertIsNone(result["error"])
        self.assertEqual(result["raw_response"], FINAL)
        self.assertEqual(result["metrics"]["llm_calls"], 2)
        self.assertEqual(result["metrics"]["tool_calls"], 2)
        self.assertEqual(result["metrics"]["tool_rounds"], 1)
        self.assertEqual(result["metrics"]["total_tokens"], 40)
        bundle = build_evidence_bundle(
            result["tool_trajectory"], allowed_tool_names={TOOL}
        )
        self.assertEqual(bundle["observations_count"], 2)
        paired = {
            ev["tool_call_id"]: (ev["arguments"]["query"],
                                 ev["observation_text"])
            for ev in bundle["evidence"]
        }
        self.assertEqual(paired, {
            "v2-call-a": ("A", "obs-A"),
            "v2-call-b": ("B", "obs-B"),
        })

    def test_missing_ids_are_never_fabricated_and_fail_closed(self):
        result = esegui_grafo_rca_v2(
            _SyntheticGraph(
                [_call("A", None), _call("B", None)],
                [_tool_result("A", None), _tool_result("B", None)],
            ),
            richiesta="Synthetic RCA request", verbose=False,
        )
        self.assertEqual(
            [event["tipo"] for event in result["tool_trajectory"]],
            ["tool_call", "tool_call", "tool_result", "tool_result"],
        )
        self.assertTrue(all("tool_call_id" not in ev
                            for ev in result["tool_trajectory"]))
        with self.assertRaisesRegex(EvidenceBundleError, "Ambiguous"):
            build_evidence_bundle(result["tool_trajectory"],
                                  allowed_tool_names={TOOL})

    def test_wrong_result_id_rejected_not_mapped_by_name(self):
        result = esegui_grafo_rca_v2(
            _SyntheticGraph([_call("A", "id-A")],
                            [_tool_result("A", "id-OTHER")]),
            richiesta="Synthetic RCA request", verbose=False,
        )
        with self.assertRaisesRegex(EvidenceBundleError, "Unmatched"):
            build_evidence_bundle(result["tool_trajectory"],
                                  allowed_tool_names={TOOL})

    def test_duplicate_call_ids_fail_closed(self):
        result = esegui_grafo_rca_v2(
            _SyntheticGraph(
                [_call("A", "duplicate"), _call("B", "duplicate")],
                [_tool_result("A", "duplicate"),
                 _tool_result("B", "duplicate")],
            ),
            richiesta="Synthetic RCA request", verbose=False,
        )
        with self.assertRaisesRegex(EvidenceBundleError, "Duplicate"):
            build_evidence_bundle(result["tool_trajectory"],
                                  allowed_tool_names={TOOL})

    def test_single_legacy_call_remains_supported(self):
        result = esegui_grafo_rca_v2(
            _SyntheticGraph([_call("A", None)],
                            [_tool_result("A", None)]),
            richiesta="Synthetic RCA request", verbose=False,
        )
        self.assertEqual(
            [event["tipo"] for event in result["tool_trajectory"]],
            ["tool_call", "tool_result"],
        )
        bundle = build_evidence_bundle(
            result["tool_trajectory"], allowed_tool_names={TOOL}
        )
        self.assertEqual(bundle["observations_count"], 1)
        self.assertEqual(bundle["evidence"][0]["arguments"]["query"], "A")
        self.assertIsNone(bundle["evidence"][0]["tool_call_id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
