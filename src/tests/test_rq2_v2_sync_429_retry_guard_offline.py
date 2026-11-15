"""Offline-only guards for the additional RQ2-V2 HTTP 429 mock.

No SDK, real network, data/GT, or credentials. The provider fake
integration itself is deferred to the exact pinned Colab snapshot.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import rq2_v2_sync_429_retry_probe as subject


def fake_messages_module():
    messages = ModuleType("langchain_core.messages")
    messages.HumanMessage = lambda **kwargs: kwargs
    messages.SystemMessage = lambda **kwargs: kwargs
    return messages


class RQ2V2Sync429RetryGuards(unittest.TestCase):
    def test_429_only_synthetic_status(self):
        self.assertEqual(subject.FAKE_STATUS, 429)

    def test_one_send_is_accepted_for_toolfree_and_bound(self):
        class Model:
            def bind_tools(self, tools):
                self.tools = tools
                return self
            def invoke(self, messages):
                self.seen.append("POST")
                raise RuntimeError("synthetic_429")

        for bound in (False, True):
            with self.subTest(bound=bound):
                model = Model()
                model.seen = []
                with patch.dict(sys.modules, {
                    "langchain_core.messages": fake_messages_module(),
                }):
                    result = subject._single_429_invoke(
                        model, model.seen, bound=bound, provider="test",
                    )
                self.assertEqual(result["synthetic_429_http_sends"], 1)
                self.assertTrue(result["http_error_observed"])

    def test_two_sends_are_rejected(self):
        class Model:
            def invoke(self, messages):
                self.seen.extend(("POST", "POST"))
                raise RuntimeError("synthetic_retry")
        model = Model()
        model.seen = []
        with patch.dict(sys.modules, {
            "langchain_core.messages": fake_messages_module(),
        }):
            with self.assertRaisesRegex(subject.Sync429ProbeBlocked, "implicit retry"):
                subject._single_429_invoke(
                    model, model.seen, bound=False, provider="test",
                )

    def test_error_without_send_is_rejected(self):
        class Model:
            def invoke(self, messages):
                raise RuntimeError("pretransport")
        with patch.dict(sys.modules, {
            "langchain_core.messages": fake_messages_module(),
        }):
            with self.assertRaisesRegex(subject.Sync429ProbeBlocked, "no HTTP"):
                subject._single_429_invoke(
                    Model(), [], bound=False, provider="test",
                )

    def test_bad_commit_rejected_before_sdk_or_network(self):
        with (
            patch.object(subject, "verify_checkout", side_effect=ValueError("bad SHA")),
            patch.object(subject, "_fake_google") as google,
            patch.object(subject, "_fake_anthropic") as anthropic,
        ):
            with self.assertRaisesRegex(ValueError, "bad SHA"):
                subject.run_probe(repo_dir=Path("."), expected_commit="bad")
            google.assert_not_called()
            anthropic.assert_not_called()

    def test_real_dispatcher_source_remains_hard_disabled(self):
        path = Path(__file__).resolve().parents[1] / (
            "evaluation/rq2_v2_unified_live_dispatcher.py"
        )
        tree = ast.parse(path.read_text(encoding="utf-8"))
        flags = [
            node.value.value for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name)
                    and target.id == "LIVE_API_ENABLED"
                    for target in node.targets)
            and isinstance(node.value, ast.Constant)
        ]
        self.assertEqual(flags, [False])


if __name__ == "__main__":
    unittest.main()
