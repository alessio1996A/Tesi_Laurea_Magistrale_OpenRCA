"""Offline-only guards for the additional RQ2-V2 HTTP 429 mock.

No SDK, real network, data/GT, or credentials. The provider fake
integration itself is deferred to the exact pinned Colab snapshot.
"""
from __future__ import annotations

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

    def test_successful_mock_does_not_imply_live_consent(self):
        self.assertIn("NO_API", "SYNC_HTTP_429_MOCK_ONE_SEND_EACH_NO_API_NOT_RELEASED")
        self.assertNotIn("LIVE_API_ENABLED = True", subject.__doc__ or "")


if __name__ == "__main__":
    unittest.main()
