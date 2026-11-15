"""Offline audit: D final-response extraction in both frozen graph engines.

Uses synthetic graph stream updates; no LLM, tools, telemetry, GT, API,
scientific ledger, or record writing. Patches text extraction ONLY in this
test to preview a future uniform D/C/K response policy. No RQ1/V2 change.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage

import agent.rq2_v2_graph_engine as react_d
import agent.verify_graph as verify_d
from evaluation.rq2_v2_ck_text_extraction_candidate import (
    extract_visible_ck_text,
)


USAGE = {"input_tokens": 50, "output_tokens": 20, "total_tokens": 70}
VALID_D = json.dumps({
    "1": {
        "root cause occurrence datetime": "1970-01-01 00:20:00",
        "root cause component": "synthetic-node-1",
        "root cause reason": "Synthetic fault hypothesis, not benchmark GT",
    }
})


class FakeGraph:
    def __init__(self, *, message, engine):
        self.message = message
        self.engine = engine
        self.calls = 0

    def stream(self, initial_state, *, config, stream_mode):
        self.calls += 1
        assert config == {"recursion_limit": 30}
        assert stream_mode == "updates"
        assert initial_state["messages"]
        if self.engine == "react":
            yield {
                "agente": {
                    "messages": [self.message],
                    "tool_rounds": 0,
                    "finalization_error": None,
                }
            }
        else:
            yield {
                "finale": {
                    "messages": [self.message],
                    "finalization_error": None,
                }
            }


def exact_text(content, *, solo_testo=False):
    if solo_testo is not True:
        raise AssertionError("Candidate only applies to visible final output")
    return extract_visible_ck_text(content).raw_text


def split_d(raw):
    marker = "synthetic-node-1"
    a, b = raw.split(marker, 1)
    return [
        {"type": "text", "text": a},
        {"type": "text", "text": marker + b},
    ]


class DFinalContentBlockAuditOfflineTests(unittest.TestCase):
    def _execute(self, engine, content, *, candidate=False):
        module = react_d if engine == "react" else verify_d
        fn = (react_d.esegui_grafo_rca_v2
              if engine == "react" else verify_d.esegui_grafo_rca_verify)
        message = AIMessage(
            content=content, usage_metadata=USAGE,
            response_metadata={"finish_reason": "stop"},
        )
        graph = FakeGraph(message=message, engine=engine)
        if candidate:
            with patch.object(module, "testo_messaggio", side_effect=exact_text):
                result = fn(graph, "Synthetic original incident", verbose=False)
        else:
            result = fn(graph, "Synthetic original incident", verbose=False)
        self.assertEqual(graph.calls, 1)
        self.assertIsNone(result["error"])
        self.assertEqual(result["metrics"]["llm_calls"], 1)
        self.assertEqual(result["metrics"]["input_tokens"], 50)
        self.assertEqual(result["metrics"]["output_tokens"], 20)
        self.assertEqual(result["metrics"]["total_tokens"], 70)
        self.assertTrue(result["metrics"]["token_usage_complete"])
        return result["raw_response"]

    def test_frozen_d_multi_text_fragments_can_invalidate_json(self):
        for engine in ("react", "verify"):
            with self.subTest(engine=engine):
                result = self._execute(engine, split_d(VALID_D))
                self.assertIn("synthetic-\nnode-1", result)
                with self.assertRaises(json.JSONDecodeError):
                    json.loads(result)

    def test_candidate_exact_fragments_valid_in_both_d_engines(self):
        for engine in ("react", "verify"):
            with self.subTest(engine=engine):
                result = self._execute(engine, split_d(VALID_D), candidate=True)
                self.assertEqual(result, VALID_D)
                self.assertEqual(json.loads(result)["1"]["root cause component"],
                                 "synthetic-node-1")

    def test_candidate_d_excludes_nontext_thinking_and_signature(self):
        for engine in ("react", "verify"):
            with self.subTest(engine=engine):
                content = [
                    {"type": "thinking", "thinking": "SYNTHETIC_PRIVATE_THOUGHT",
                     "signature": "SYNTHETIC_SIGNATURE"},
                    *split_d(VALID_D),
                ]
                result = self._execute(engine, content, candidate=True)
                self.assertEqual(result, VALID_D)
                self.assertNotIn("SYNTHETIC_PRIVATE", result)
                self.assertNotIn("SYNTHETIC_SIGNATURE", result)

    def test_candidate_preserves_valid_single_string_for_both_d_engines(self):
        for engine in ("react", "verify"):
            with self.subTest(engine=engine):
                self.assertEqual(
                    self._execute(engine, VALID_D, candidate=True), VALID_D
                )

    def test_candidate_d_never_repairs_genuinely_malformed_json(self):
        invalid = VALID_D.replace("synthetic-node-1", "synthetic-\nnode-1")
        for engine in ("react", "verify"):
            with self.subTest(engine=engine):
                result = self._execute(
                    engine, [{"type": "text", "text": invalid}], candidate=True
                )
                self.assertEqual(result, invalid)
                with self.assertRaises(json.JSONDecodeError):
                    json.loads(result)


if __name__ == "__main__":
    unittest.main()
