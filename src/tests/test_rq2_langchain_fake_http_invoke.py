"""Only stdlib and synthetic tests for the final RQ2 fake-HTTP invoke gate."""
from __future__ import annotations

import socket
import unittest
from types import ModuleType
from unittest.mock import patch

import evaluation.rq2_langchain_fake_http_invoke as subject


def _fake_messages_module():
    """A module, not a class instance: avoid Python binding a fake 'self'."""
    stub = ModuleType("langchain_core.messages")
    stub.HumanMessage = lambda **kwargs: kwargs
    stub.SystemMessage = lambda **kwargs: kwargs
    return stub


def good_trace():
    return {
        "status": "EXACT_SOURCE_BRIDGE_INSPECTED_FOR_REVIEW_NOT_SDK_HTTP_CERTIFIED",
        "colab_package_versions_match": True,
        "rq1_factory_unchanged": True,
        "rq2_release_sha_unpinned": True,
        "scientific_discovery_release_signed": False,
        "can_execute_D": False,
        "can_execute_CK": False,
        "can_execute_test": False,
        "provider_api_calls": 0,
    }


def fake_provider(name):
    return {
        "backend": "httpx2.MockTransport",
        "fake_total_http_503_sends": 2,
        "sync_invoke_modes": [
            {"style": "CK_tool_free", "fake_http_503_sends": 1,
             "synthetic_tool_executed": False, "external_network_calls": 0},
            {"style": "D_bound_tools", "fake_http_503_sends": 1,
             "synthetic_tool_executed": False, "external_network_calls": 0},
        ],
        "external_provider_requests": 0,
    }


class RQ2FinalFakeHTTPInvokeOfflineTests(unittest.TestCase):
    def test_schema_is_synthetic_and_does_not_call_tool(self):
        self.assertEqual(subject.TOOL_SCHEMA["name"], "synthetic_metric_lookup")
        self.assertIn("metric", subject.TOOL_SCHEMA["parameters"]["properties"])

    def test_no_sdk_import_or_live_model_when_trace_invalid(self):
        bad = good_trace()
        bad["rq1_factory_unchanged"] = False
        with patch.object(subject, "trace_exact_bridge_sources", return_value=bad):
            with patch.object(subject, "_fake_google") as google:
                with patch.object(subject, "_fake_anthropic") as anthropic:
                    with self.assertRaises(subject.RQ2BridgeMockBlocked):
                        subject.run_fake_http_invoke(repo_dir=".")
                    google.assert_not_called()
                    anthropic.assert_not_called()

    def test_release_is_never_unlocked_by_mocked_success(self):
        with patch.object(subject, "trace_exact_bridge_sources", return_value=good_trace()):
            with patch.object(subject, "_fake_google", return_value=fake_provider("google")):
                with patch.object(subject, "_fake_anthropic", return_value=fake_provider("anthropic")):
                    result = subject.run_fake_http_invoke(repo_dir=".")
        self.assertFalse(result["scientific_release_signed"])
        self.assertFalse(result["can_execute_D"])
        self.assertFalse(result["can_execute_CK"])
        self.assertFalse(result["can_execute_test"])
        self.assertEqual(result["api_requests_to_real_providers"], 0)
        self.assertFalse(result["read_market"])
        self.assertFalse(result["read_ground_truth"])
        self.assertEqual(result["model_outputs_generated"], 0)
        self.assertEqual(result["real_tools_executed"], 0)
        self.assertFalse(result["timeout_under_real_network_stall_verified"])

    def test_unexpected_extra_http_send_is_rejected(self):
        google = fake_provider("google")
        google["fake_total_http_503_sends"] = 3
        with patch.object(subject, "trace_exact_bridge_sources", return_value=good_trace()):
            with patch.object(subject, "_fake_google", return_value=google):
                with patch.object(subject, "_fake_anthropic", return_value=fake_provider("anthropic")):
                    with self.assertRaisesRegex(subject.RQ2BridgeMockBlocked, "total fake send"):
                        subject.run_fake_http_invoke(repo_dir=".")

    def test_direct_fake_helpers_still_block_sockets(self):
        @subject._socket_locked
        def attempted_external_send():
            with socket.socket() as client:
                client.connect(("127.0.0.1", 9))
        with self.assertRaises(subject.RQ2BridgeMockBlocked):
            attempted_external_send()

    def test_mocked_503_must_be_observed_once(self):
        class FailingModel:
            def bind_tools(self, _tools):
                return self
            def invoke(self, _messages):
                counters.append({"method": "POST"})
                raise ValueError("FAKE_HTTP_503")
        counters = []
        with patch.dict(
            "sys.modules",
            {"langchain_core.messages": _fake_messages_module()},
        ):
            out = subject._mocked_error_invoke(
                FailingModel(), counters, bound=True, provider="fake"
            )
        self.assertEqual(out["fake_http_503_sends"], 1)
        self.assertEqual(out["style"], "D_bound_tools")

    def test_503_without_http_send_is_rejected(self):
        class FailingModel:
            def invoke(self, _messages):
                raise ValueError("synthetic pretransport failure")
        with patch.dict(
            "sys.modules",
            {"langchain_core.messages": _fake_messages_module()},
        ):
            with self.assertRaisesRegex(subject.RQ2BridgeMockBlocked, "attempts unexpected"):
                subject._mocked_error_invoke(
                    FailingModel(), [], bound=False, provider="fake"
                )

    def test_nonerror_fake_transport_response_is_rejected(self):
        class AcceptedModel:
            def invoke(self, _messages):
                counters.append({"method": "POST"})
                return "unexpected"
        counters = []
        with patch.dict(
            "sys.modules",
            {"langchain_core.messages": _fake_messages_module()},
        ):
            with self.assertRaisesRegex(subject.RQ2BridgeMockBlocked, "silently accepted"):
                subject._mocked_error_invoke(
                    AcceptedModel(), counters, bound=False, provider="fake"
                )


if __name__ == "__main__":
    unittest.main()
