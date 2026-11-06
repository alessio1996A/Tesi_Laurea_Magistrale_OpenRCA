"""Token instrumentation of the basic graph, fake events only; no APIs."""
import unittest
from langchain_core.messages import AIMessage
from agent.graph_engine import esegui_grafo_rca


class FakeGraph:
    def __init__(self, messages=None, raise_error=False):
        self.messages = messages or []
        self.raise_error = raise_error

    def stream(self, *args, **kwargs):
        for msg in self.messages:
            yield {"agente": {
                "messages": [msg],
                "tool_rounds": 0,
                "finalization_error": None,
            }}
        if self.raise_error:
            raise RuntimeError("fake interrupted LLM")


class GraphTokenCompletenessTests(unittest.TestCase):
    def test_complete_usage_is_marked_true(self):
        msg = AIMessage(
            content='{"1": {"root cause component": "node-1"}}',
            usage_metadata={
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
            }
        )
        result = esegui_grafo_rca(FakeGraph([msg]), "finto caso", verbose=False)
        m = result["metrics"]
        self.assertTrue(m["token_usage_complete"])
        self.assertEqual(m["llm_calls"], 1)
        self.assertEqual(m["input_tokens"], 100)
        self.assertEqual(m["output_tokens"], 20)
        self.assertEqual(m["total_tokens"], 120)

    def test_missing_usage_is_marked_false(self):
        msg = AIMessage(content='{"1": {"root cause component": "node-1"}}')
        result = esegui_grafo_rca(FakeGraph([msg]), "finto caso", verbose=False)
        self.assertFalse(result["metrics"]["token_usage_complete"])
        self.assertEqual(result["metrics"]["llm_calls"], 1)

    def test_exception_cannot_be_complete(self):
        msg = AIMessage(
            content="fake",
            usage_metadata={"input_tokens": 5, "output_tokens": 2,
                            "total_tokens": 7},
        )
        result = esegui_grafo_rca(
            FakeGraph([msg], raise_error=True), "finto caso", verbose=False
        )
        self.assertFalse(result["metrics"]["token_usage_complete"])
        self.assertIn("RuntimeError", result["error"])


if __name__ == "__main__":
    unittest.main()
