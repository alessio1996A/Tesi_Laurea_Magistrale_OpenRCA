"""Pure-stdlib RQ2 mocked transport gate tests; no SDK imports or model calls."""
from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

import evaluation.rq2_sdk_retry_mock_probe as subject
from evaluation.rq2_provider_policy_source_audit import EXPECTED_COLAB_VERSIONS


def good_snapshot() -> dict:
    packages = {
        name: {"version": version, "known_source_sha256": None}
        for name, version in EXPECTED_COLAB_VERSIONS.items()
    }
    for name, digest in subject.EXPECTED_SOURCE_DIGESTS.items():
        packages[name]["known_source_sha256"] = digest
    return {
        "original_factory_unchanged": True,
        "matches_previous_colab_versions": True,
        "can_execute_D": False, "can_execute_CK": False,
        "can_execute_test": False,
        "api_calls_executed": 0,
        "packages": packages,
    }


class RQ2SDKRetryMockGateOfflineTests(unittest.TestCase):
    def test_valid_exact_snapshot_is_accepted_without_sdk_import(self):
        self.assertIsNone(subject.validate_sdk_snapshot(good_snapshot()))

    def test_wrong_colab_version_fails_closed(self):
        report = good_snapshot()
        report["packages"]["google-genai"]["version"] = "2.33.0"
        with self.assertRaisesRegex(subject.RQ2MockProbeBlocked, "Unexpected package"):
            subject.validate_sdk_snapshot(report)

    def test_wrong_source_digest_fails_closed(self):
        report = good_snapshot()
        report["packages"]["anthropic"]["known_source_sha256"] = "0" * 64
        with self.assertRaisesRegex(subject.RQ2MockProbeBlocked, "Changed provider"):
            subject.validate_sdk_snapshot(report)

    def test_rq1_factory_must_remain_frozen(self):
        report = good_snapshot()
        report["original_factory_unchanged"] = False
        with self.assertRaisesRegex(subject.RQ2MockProbeBlocked, "Frozen RQ1"):
            subject.validate_sdk_snapshot(report)

    def test_any_production_gate_unlocked_is_refused(self):
        for key in ("can_execute_D", "can_execute_CK", "can_execute_test"):
            with self.subTest(key=key):
                report = good_snapshot()
                report[key] = True
                with self.assertRaises(subject.RQ2MockProbeBlocked):
                    subject.validate_sdk_snapshot(report)

    def test_api_calls_report_must_be_zero(self):
        report = good_snapshot()
        report["api_calls_executed"] = 1
        with self.assertRaisesRegex(subject.RQ2MockProbeBlocked, "API execution"):
            subject.validate_sdk_snapshot(report)

    def test_missing_anthropic_environment_fails_before_any_probes(self):
        report = good_snapshot()
        report["matches_previous_colab_versions"] = False
        with patch.object(subject, "preview_provider_policy", return_value=report):
            with patch.object(subject, "probe_google_retry_args") as google:
                with patch.object(subject, "probe_anthropic_mock_503") as anthropic:
                    with self.assertRaises(subject.RQ2MockProbeBlocked):
                        subject.run_offline_mock_probe(repo_dir=".")
                    google.assert_not_called()
                    anthropic.assert_not_called()

    def test_successful_fake_probes_does_not_unlock_production(self):
        fake_google = {
            "sdk_retry_args_local_attempts": {
                "default_no_options": 1, "explicit_attempts_1": 1,
                "explicit_attempts_2": 2,
            }
        }
        fake_anthropic = {"sdk_mock_503_attempts": 1}
        with patch.object(subject, "preview_provider_policy", return_value=good_snapshot()):
            with patch.object(subject, "probe_google_retry_args", return_value=fake_google):
                with patch.object(
                    subject, "probe_anthropic_mock_503", return_value=fake_anthropic
                ):
                    report = subject.run_offline_mock_probe(repo_dir=".")
        self.assertEqual(report["real_provider_requests"], 0)
        self.assertFalse(report["scientific_release_signed"])
        self.assertFalse(report["can_execute_D"])
        self.assertFalse(report["can_execute_CK"])
        self.assertFalse(report["can_execute_test"])
        self.assertFalse(report["read_ground_truth"])
        self.assertFalse(report["read_market"])
        self.assertFalse(report["files_written"])


if __name__ == "__main__":
    unittest.main()
