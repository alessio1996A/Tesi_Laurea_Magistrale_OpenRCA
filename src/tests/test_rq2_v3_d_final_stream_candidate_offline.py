"""Offline D final-output bridge test for both original D runners.

No real models, network, tools, GT, release or ledger. Checks the *actual*
successor D stream candidate rather than a global monkeypatch of V2 code.
"""
from __future__ import annotations

import copy
import json
import unittest

from langchain_core.messages import AIMessage, ToolMessage

from evaluation.rq2_v2_ck_text_extraction_candidate import POLICY
from evaluation.rq2_v3_d_final_stream_candidate import (
    DFinalStreamCandidateBlocked,
    D_META_SCHEMA,
    ExactFinalTextStream,
    run_d_final_candidate,
)
from test_rq2_v3_d_contentblock_audit_offline import VALID_D


USAGE = {"input_tokens": 50, "output_tokens": 20, "total_tokens": 70}


def chunks(raw: str):
    head, tail = raw.split("node-1", 1)
    return [
        {"type": "text", "text": head},
        {"type": "text", "text": "node-1" + tail},
    ]


class FakeGraph:
    def __init__(self, updates):
        self.updates = updates
        self.calls = 0

    def stream(self, initial_state, *, config, stream_mode):
        self.calls += 1
        assert config == {"recursion_limit": 30}
        assert stream_mode == "updates"
        assert len(initial_state["messages"]) == 1
        yield from self.updates


def final_message(content):
    return AIMessage(
        content=content,
        usage_metadata=USAGE,
        response_metadata={"finish_reason": "stop"},
    )


def stream_events(engine, msg, *, error=None):
    if engine == "react":
        return [{
            "agente": {
                "messages": [msg],
                "tool_rounds": 0,
                "finalization_error": error,
            }
        }]
    return [{
        "finale": {"messages": [msg], "finalization_error": error}
    }]


class V3FinalDStreamCandidateOfflineTests(unittest.TestCase):
    def _execute(self, engine, content, *, error=None):
        original = final_message(content)
        snapshot = copy.deepcopy(original.content)
        graph = FakeGraph(stream_events(engine, original, error=error))
        receipt = run_d_final_candidate(
            graph, "Synthetic incident", engine=engine, verbose=False,
        )
        self.assertEqual(graph.calls, 1)
        self.assertEqual(original.content, snapshot)  # no SDK mutation
        self.assertIs(receipt["can_execute_api"], False)
        self.assertIs(receipt["scientific_release_frozen"], False)
        self.assertIs(receipt["source_bound"], False)
        return receipt

    def test_split_d_json_is_exact_for_both_engines(self):
        for engine in ("react", "verify"):
            with self.subTest(engine=engine):
                receipt = self._execute(engine, chunks(VALID_D))
                run = receipt["diagnostic_run"]
                self.assertIsNone(run["error"])
                self.assertEqual(run["raw_response"], VALID_D)
                self.assertEqual(
                    json.loads(run["raw_response"])["1"]["root cause component"],
                    "synthetic-node-1",
                )
                self.assertEqual(
                    run["metrics"]["input_tokens"], 50,
                )
                self.assertEqual(run["metrics"]["output_tokens"], 20)
                self.assertEqual(run["metrics"]["llm_calls"], 1)
                meta = receipt["d_final_text_extraction"]
                self.assertEqual(meta["schema"], D_META_SCHEMA)
                self.assertEqual(meta["policy"], POLICY)
                self.assertEqual(meta["content_kind"], "list")
                self.assertEqual(meta["text_blocks"], 2)
                self.assertEqual(meta["nontext_blocks"], 0)

    def test_thinking_not_included_or_persisted_for_both_engines(self):
        content = [
            {"type": "thinking", "thinking": "PRIVATE_TEST_REASONING",
             "signature": "PRIVATE_TEST_SIGNATURE"},
            *chunks(VALID_D),
        ]
        for engine in ("react", "verify"):
            with self.subTest(engine=engine):
                receipt = self._execute(engine, content)
                self.assertEqual(
                    receipt["diagnostic_run"]["raw_response"], VALID_D,
                )
                self.assertNotIn("PRIVATE_TEST_REASONING", str(receipt))
                self.assertNotIn("PRIVATE_TEST_SIGNATURE", str(receipt))
                self.assertEqual(
                    receipt["d_final_text_extraction"]["nontext_blocks"], 1
                )

    def test_single_string_unchanged_for_both_engines(self):
        for engine in ("react", "verify"):
            with self.subTest(engine=engine):
                receipt = self._execute(engine, VALID_D)
                self.assertEqual(receipt["diagnostic_run"]["raw_response"], VALID_D)
                self.assertEqual(
                    receipt["d_final_text_extraction"]["content_kind"], "str"
                )

    def test_genuinely_invalid_d_json_remains_invalid(self):
        invalid = VALID_D.replace(
            "synthetic-node-1", "synthetic-\nnode-1"
        )
        for engine in ("react", "verify"):
            with self.subTest(engine=engine):
                receipt = self._execute(
                    engine, [{"type": "text", "text": invalid}]
                )
                self.assertEqual(receipt["diagnostic_run"]["raw_response"], invalid)
                with self.assertRaises(json.JSONDecodeError):
                    json.loads(receipt["diagnostic_run"]["raw_response"])
                self.assertEqual(
                    receipt["d_final_text_extraction"]["text_blocks"], 1
                )

    def test_react_tool_trajectory_preserves_native_call_id(self):
        first = AIMessage(
            content="", usage_metadata=USAGE, tool_calls=[{
                "name": "tool_get_node_metrics",
                "args": {"cmdb_id": "synthetic-node-1"},
                "id": "native-synthetic-1",
            }],
        )
        tool = ToolMessage(
            content="Synthetic metric observation",
            name="tool_get_node_metrics",
            tool_call_id="native-synthetic-1",
        )
        final = final_message(chunks(VALID_D))
        graph = FakeGraph([
            {"agente": {
                "messages": [first],
                "tool_rounds": 1,
                "finalization_error": None,
            }},
            {"tools": {"messages": [tool]}},
            {"agente": {
                "messages": [final],
                "tool_rounds": 1,
                "finalization_error": None,
            }},
        ])
        receipt = run_d_final_candidate(graph, "Synthetic incident",
                                        engine="react", verbose=False)
        out = receipt["diagnostic_run"]
        self.assertEqual(out["raw_response"], VALID_D)
        self.assertEqual(out["metrics"]["llm_calls"], 2)
        self.assertEqual(out["metrics"]["input_tokens"], 100)
        self.assertEqual(out["metrics"]["output_tokens"], 40)
        self.assertEqual(out["metrics"]["tool_calls"], 1)
        self.assertEqual(out["metrics"]["tool_rounds"], 1)
        self.assertEqual(
            [e["tipo"] for e in out["tool_trajectory"]],
            ["tool_call", "tool_result"],
        )
        self.assertEqual(
            [e["tool_call_id"] for e in out["tool_trajectory"]],
            ["native-synthetic-1", "native-synthetic-1"],
        )
        self.assertEqual(first.content, "")
        self.assertEqual(final.content, chunks(VALID_D))

    def test_finalization_error_never_produces_diagnosis(self):
        for engine in ("react", "verify"):
            with self.subTest(engine=engine):
                receipt = self._execute(
                    engine, chunks(VALID_D), error="SYNTHETIC_FINAL_ERROR"
                )
                self.assertIsNone(receipt["diagnostic_run"]["raw_response"])
                self.assertEqual(
                    receipt["diagnostic_run"]["error"], "SYNTHETIC_FINAL_ERROR"
                )
                self.assertEqual(
                    receipt["d_final_text_extraction"]["content_kind"],
                    "not_observed",
                )

    def test_multiple_final_outputs_fail_closed_without_retries(self):
        first = final_message(chunks(VALID_D))
        second = final_message(chunks(VALID_D))
        graph = FakeGraph([
            *stream_events("react", first),
            *stream_events("react", second),
        ])
        receipt = run_d_final_candidate(graph, "Synthetic incident",
                                        engine="react", verbose=False)
        self.assertEqual(graph.calls, 1)
        self.assertIsNone(receipt["diagnostic_run"]["raw_response"])
        self.assertIn(
            "Multiple final model messages",
            receipt["diagnostic_run"]["error"],
        )
        self.assertFalse(
            receipt["diagnostic_run"]["metrics"]["token_usage_complete"]
        )

    def test_excessive_content_blocks_fail_closed(self):
        for engine in ("react", "verify"):
            with self.subTest(engine=engine):
                receipt = self._execute(engine, ["x"] * 257)
                self.assertIsNone(receipt["diagnostic_run"]["raw_response"])
                self.assertIn(
                    "CKTextExtractionBlocked",
                    receipt["diagnostic_run"]["error"],
                )
                self.assertFalse(
                    receipt["diagnostic_run"]["metrics"]["token_usage_complete"]
                )

    def test_stream_wrapper_cannot_be_reused(self):
        graph = FakeGraph(stream_events(
            "react", final_message(chunks(VALID_D))
        ))
        wrapped = ExactFinalTextStream(graph, engine="react")
        one = list(wrapped.stream(
            {"messages": [object()]},
            config={"recursion_limit": 30},
            stream_mode="updates",
        ))
        self.assertEqual(len(one), 1)
        with self.assertRaises(DFinalStreamCandidateBlocked):
            list(wrapped.stream(
                {"messages": [object()]},
                config={"recursion_limit": 30},
                stream_mode="updates",
            ))
        self.assertEqual(graph.calls, 1)


if __name__ == "__main__":
    unittest.main()
