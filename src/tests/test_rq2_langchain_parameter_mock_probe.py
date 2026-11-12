"""Stdlib-only tests: LangChain->SDK mock probe must fail closed."""
from __future__ import annotations

import socket
import unittest
from unittest.mock import patch

import evaluation.rq2_langchain_parameter_mock_probe as subject


def good_trace() -> dict:
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


class RQ2LangChainParameterMockProbeTests(unittest.TestCase):
    def test_valid_trace_accepted_without_sdk_import(self):
        self.assertIsNone(subject.validate_trace(good_trace()))

    def test_refuses_missing_trace_status(self):
        report = good_trace()
        report["status"] = "OTHER"
        with self.assertRaises(subject.RQ2BridgeMockBlocked):
            subject.validate_trace(report)

    def test_refuses_changed_factory_or_release_pin(self):
        for key in ("colab_package_versions_match", "rq1_factory_unchanged",
                    "rq2_release_sha_unpinned"):
            with self.subTest(key=key):
                report = good_trace()
                report[key] = False
                with self.assertRaises(subject.RQ2BridgeMockBlocked):
                    subject.validate_trace(report)

    def test_refuses_any_unlocked_gate(self):
        for key in ("scientific_discovery_release_signed", "can_execute_D",
                    "can_execute_CK", "can_execute_test"):
            with self.subTest(key=key):
                report = good_trace()
                report[key] = True
                with self.assertRaises(subject.RQ2BridgeMockBlocked):
                    subject.validate_trace(report)

    def test_socket_connect_is_blocked(self):
        with subject.network_forbidden():
            with socket.socket() as s:
                with self.assertRaises(subject.RQ2BridgeMockBlocked):
                    s.connect(("127.0.0.1", 9))
            with self.assertRaises(subject.RQ2BridgeMockBlocked):
                socket.create_connection(("127.0.0.1", 9))

    def test_failed_trace_blocks_both_local_client_constructors(self):
        broken = good_trace()
        broken["provider_api_calls"] = 1
        with patch.object(subject, "trace_exact_bridge_sources", return_value=broken):
            with patch.object(subject, "probe_google_langchain_parameters") as google:
                with patch.object(subject, "probe_anthropic_langchain_parameters") as anthropic:
                    with self.assertRaises(subject.RQ2BridgeMockBlocked):
                        subject.run_mock_parameter_probe(repo_dir=".")
                    google.assert_not_called()
                    anthropic.assert_not_called()

    def test_mocked_local_forwarding_stays_non_executable(self):
        google = {"sdk_http_retry_attempts": 1, "client_network_calls": 0}
        claude = {"sdk_max_retries": 0, "client_network_calls": 0}
        with patch.object(subject, "trace_exact_bridge_sources", return_value=good_trace()):
            with patch.object(subject, "probe_google_langchain_parameters", return_value=google):
                with patch.object(subject, "probe_anthropic_langchain_parameters", return_value=claude):
                    report = subject.run_mock_parameter_probe(repo_dir=".")
        self.assertEqual(report["google"], google)
        self.assertEqual(report["anthropic"], claude)
        self.assertEqual(report["external_provider_requests"], 0)
        self.assertFalse(report["real_credentials_used"])
        self.assertFalse(report["sdk_http_transport_exercised"])
        self.assertFalse(report["can_execute_D"])
        self.assertFalse(report["can_execute_CK"])
        self.assertFalse(report["can_execute_test"])
        self.assertFalse(report["scientific_release_signed"])

    def test_sdk_timeout_extractor(self):
        self.assertEqual(subject._sdk_timeout_seconds(300.0), 300.0)
        self.assertIsNone(subject._sdk_timeout_seconds(None))
        class FakeTimeout:
            read = 300.0
        self.assertEqual(subject._sdk_timeout_seconds(FakeTimeout()), 300.0)


if __name__ == "__main__":
    unittest.main()
