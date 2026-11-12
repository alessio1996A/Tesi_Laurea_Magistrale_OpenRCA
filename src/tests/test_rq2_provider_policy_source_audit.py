"""Offline unit tests of RQ2 provider-policy source provenance; NO provider calls."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.rq2_provider_policy_source_audit import (
    RQ2PolicySourceError, audit_factory_text, preview_provider_policy,
)


FAKE_FACTORY = b"""
def _crea_modello_google(model_name):
    return ChatGoogleGenerativeAI(model=model_name)

def _crea_modello_anthropic(model_name):
    return ChatAnthropic(model=model_name, max_retries=0, max_tokens=4096)
"""


class RQ2ProviderPolicySourceAuditTests(unittest.TestCase):
    def test_factory_ast_recognizes_explicit_claude_zero_not_google_defaults(self):
        got = audit_factory_text(FAKE_FACTORY)
        self.assertFalse(got["frozen_rq1_factory_blob_match"])
        self.assertTrue(got["google_model_argument_explicit"])
        self.assertFalse(got["google_max_retries_explicit"])
        self.assertFalse(got["google_timeout_explicit"])
        self.assertTrue(got["anthropic_max_retries_literal_zero"])
        self.assertTrue(got["anthropic_max_tokens_argument_explicit"])
        self.assertFalse(got["anthropic_timeout_explicit"])

    def test_factory_ast_marks_explicit_google_policy_without_claiming_effect(self):
        source = FAKE_FACTORY.replace(
            b"ChatGoogleGenerativeAI(model=model_name)",
            b"ChatGoogleGenerativeAI(model=model_name, max_retries=1, timeout=60)",
        )
        got = audit_factory_text(source)
        self.assertTrue(got["google_max_retries_explicit"])
        self.assertTrue(got["google_timeout_explicit"])

    def test_factory_ast_rejects_dynamic_provider_kwargs(self):
        source = FAKE_FACTORY.replace(
            b"ChatAnthropic(model=model_name, max_retries=0, max_tokens=4096)",
            b"ChatAnthropic(model=model_name, **params)",
        )
        with self.assertRaises(RQ2PolicySourceError):
            audit_factory_text(source)

    def test_factory_ast_requires_original_constructor(self):
        source = FAKE_FACTORY.replace(b"ChatAnthropic(", b"OtherModel(")
        with self.assertRaises(RQ2PolicySourceError):
            audit_factory_text(source)

    def test_missing_factory_file_fails_without_sdk(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(RQ2PolicySourceError):
                preview_provider_policy(repo_dir=Path(td))

    def test_synthetic_factory_never_grants_any_release_permissions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "src" / "agent" / "model_factory.py"
            target.parent.mkdir(parents=True)
            target.write_bytes(FAKE_FACTORY)
            with patch(
                "evaluation.rq2_provider_policy_source_audit._package_evidence",
                return_value={"version": None, "known_source_sha256": None},
            ):
                report = preview_provider_policy(repo_dir=root)
            self.assertFalse(report["matches_previous_colab_versions"])
            self.assertTrue(report["anthropic_zero_retries_in_factory_source"])
            self.assertTrue(report["gemini_retry_timeout_unspecified_in_factory_source"])
            self.assertEqual(report["api_calls_executed"], 0)
            for name in (
                "effective_google_sdk_retry_timeout_verified",
                "effective_anthropic_sdk_retry_timeout_verified",
                "scientific_release_signed",
                "can_execute_D", "can_execute_CK", "can_execute_test",
            ):
                self.assertFalse(report[name], name)
            self.assertFalse(report["read_ground_truth"])
            self.assertFalse(report["read_market"])
            self.assertFalse(report["files_written"])

    def test_real_local_rq1_factory_remains_frozen_source(self):
        root = Path(__file__).resolve().parents[2]
        report = preview_provider_policy(repo_dir=root)
        self.assertTrue(report["original_factory_unchanged"])
        self.assertTrue(report["anthropic_zero_retries_in_factory_source"])
        self.assertTrue(report["gemini_retry_timeout_unspecified_in_factory_source"])
        self.assertEqual(report["api_calls_executed"], 0)
        self.assertFalse(report["can_execute_test"])


if __name__ == "__main__":
    unittest.main()
