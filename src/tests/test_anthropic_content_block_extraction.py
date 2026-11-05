"""Offline regression tests for mixed Anthropic AIMessage content blocks.

No model calls, no ground truth, no mutation of frozen artifacts.
Thinking/signature and tool-use blocks are protocol metadata and must never
be prepended to the canonical final JSON consumed by OpenRCA validation.
"""
import json
import unittest

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from agent.graph_engine import (
    crea_grafo_rca, esegui_grafo_rca, testo_messaggio,
)


JSON_RESPONSE = '{"1":{"root cause reason":"Packet loss observed on service link"}}'
THINKING_BLOCK = {
    "type": "thinking",
    "thinking": "",
    "signature": "synthetic-signature-offline-test",
}


class MockClaudeWithThinking:
    def bind_tools(self, _tools):
        return self

    def invoke(self, _messages):
        return AIMessage(
            content=[
                THINKING_BLOCK,
                {"type": "text", "text": JSON_RESPONSE},
            ],
            usage_metadata={
                "input_tokens": 123,
                "output_tokens": 30,
                "total_tokens": 153,
            },
        )


@tool
def harmless_tool(text: str) -> str:
    """Return the provided string, without external interactions."""
    return text


class TestAnthropicContentExtraction(unittest.TestCase):
    def test_original_string_unchanged(self):
        self.assertEqual(
            testo_messaggio(JSON_RESPONSE, solo_testo=True), JSON_RESPONSE
        )

    def test_claude_thinking_signature_is_not_in_final_json(self):
        blocks = [
            THINKING_BLOCK,
            {"type": "redacted_thinking", "data": "opaque"},
            {"type": "tool_use", "name": "mock", "input": {}},
            {"type": "text", "text": JSON_RESPONSE},
        ]
        final = testo_messaggio(blocks, solo_testo=True)
        self.assertEqual(final, JSON_RESPONSE)
        self.assertEqual(json.loads(final)["1"]["root cause reason"],
                         "Packet loss observed on service link")
        self.assertNotIn("signature", final)
        self.assertNotIn("thinking", final)
        self.assertNotIn("tool_use", final)

    def test_only_nontext_blocks_is_empty_not_fake_diagnosis(self):
        blocks = [THINKING_BLOCK, {"type": "tool_use", "name": "mock"}]
        self.assertEqual(testo_messaggio(blocks, solo_testo=True), "")

    def test_normal_tool_observation_semantics_preserved(self):
        opaque = {"type": "custom_observation", "foo": 1}
        self.assertEqual(testo_messaggio([opaque]), str(opaque))
        self.assertEqual(
            testo_messaggio([{"type": "text", "text": "ok"}]), "ok"
        )

    def test_graph_end_to_end_no_tools_anthropic_text_only(self):
        graph = crea_grafo_rca(
            llm=MockClaudeWithThinking(),
            tools=[harmless_tool],
            system_prompt="Return only JSON",
            max_tool_rounds=6,
        )
        result = esegui_grafo_rca(
            grafo=graph, richiesta="One root cause reason",
            recursion_limit=30, verbose=False,
        )
        self.assertIsNone(result["error"])
        self.assertEqual(result["raw_response"], JSON_RESPONSE)
        self.assertEqual(result["metrics"]["llm_calls"], 1)
        self.assertEqual(result["metrics"]["tool_rounds"], 0)
        self.assertEqual(result["metrics"]["input_tokens"], 123)
        self.assertEqual(result["metrics"]["output_tokens"], 30)
        self.assertIsInstance(json.loads(result["raw_response"]), dict)


if __name__ == "__main__":
    unittest.main()
