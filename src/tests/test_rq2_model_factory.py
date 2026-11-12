"""RQ2-only candidate factory: stdlib offline, synthetic SDK constructors."""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import evaluation.rq2_model_factory as subject


class RQ2ModelFactoryOfflineTests(unittest.TestCase):
    def test_google_kwargs_are_exact(self):
        called = []
        fake_google = types.ModuleType("langchain_google_genai")
        fake_google.ChatGoogleGenerativeAI = lambda **kwargs: called.append(kwargs) or object()
        with patch.object(subject, "assert_exact_runtime_snapshot"):
            with patch.dict("sys.modules", {"langchain_google_genai": fake_google}):
                subject.crea_modello_rq2("google", "gemini-3.5-flash-lite")
        self.assertEqual(called, [{
            "model": "gemini-3.5-flash-lite", "max_retries": 1, "timeout": 300.0,
        }])

    def test_both_anthropic_models_kwargs_exact(self):
        called = []
        fake_anthropic = types.ModuleType("langchain_anthropic")
        fake_anthropic.ChatAnthropic = lambda **kwargs: called.append(kwargs) or object()
        with patch.object(subject, "assert_exact_runtime_snapshot"):
            with patch.dict("sys.modules", {"langchain_anthropic": fake_anthropic}):
                for model_id in ("claude-sonnet-5-5", "claude-haiku-5-5"):
                    subject.crea_modello_rq2("anthropic", model_id)
        self.assertEqual(len(called), 2)
        self.assertEqual([x["model"] for x in called],
                         ["claude-sonnet-5-5", "claude-haiku-5-5"])
        for kwargs in called:
            self.assertEqual(kwargs["max_retries"], 0)
            self.assertEqual(kwargs["timeout"], 300.0)
            self.assertEqual(kwargs["max_tokens"], 4096)
            self.assertNotIn("temperature", kwargs)

    def test_unknown_models_blocked_before_import_or_audit(self):
        for pair in (("google", "gemini-unknown"),
                     ("anthropic", "claude-other"),
                     ("other", "claude-sonnet-5-5"),
                     ("Google", "gemini-3.5-flash-lite")):
            with self.subTest(pair=pair):
                with patch.object(subject, "assert_exact_runtime_snapshot") as audit:
                    with self.assertRaises(subject.RQ2ModelPolicyBlocked):
                        subject.crea_modello_rq2(*pair)
                    audit.assert_not_called()

    def test_nonstring_inputs_blocked(self):
        for pair in ((None, "gemini-3.5-flash-lite"),
                     ("google", None), (123, 4)):
            with self.subTest(pair=pair):
                with self.assertRaises(subject.RQ2ModelPolicyBlocked):
                    subject.crea_modello_rq2(*pair)

    def test_runtime_package_drift_blocks(self):
        versions = dict(subject.EXPECTED_COLAB_VERSIONS)
        with patch.object(subject.metadata, "version",
                          side_effect=lambda key: (
                              "0.0.0" if key == "google-genai" else versions[key]
                          )):
            with self.assertRaisesRegex(subject.RQ2ModelPolicyBlocked, "package drift"):
                subject.assert_exact_runtime_snapshot()

    def test_missing_package_blocks(self):
        with patch.object(subject.metadata, "version",
                          side_effect=subject.metadata.PackageNotFoundError("missing")):
            with self.assertRaisesRegex(subject.RQ2ModelPolicyBlocked, "Missing pinned"):
                subject.assert_exact_runtime_snapshot()

    def test_known_source_digest_mismatch_blocks(self):
        versions = dict(subject.EXPECTED_COLAB_VERSIONS)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "source.py"
            path.write_bytes(b"altered synthetic content")
            fake = types.SimpleNamespace(locate_file=lambda _file: path)
            with patch.object(subject.metadata, "version",
                              side_effect=lambda k: versions[k]):
                with patch.object(subject.metadata, "distribution", return_value=fake):
                    with self.assertRaisesRegex(subject.RQ2ModelPolicyBlocked,
                                                "provider source drift"):
                        subject.assert_exact_runtime_snapshot()

    def test_complete_pinned_source_harness_with_synthetic_bytes(self):
        versions = dict(subject.EXPECTED_COLAB_VERSIONS)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "source.py"
            path.write_bytes(b"synthetic pinned source")
            h = hashlib.sha256(path.read_bytes()).hexdigest()
            fake = types.SimpleNamespace(locate_file=lambda _file: path)
            hashes = {key: h for key in subject.EXPECTED_SOURCE_DIGESTS}
            with patch.object(subject, "EXPECTED_SOURCE_DIGESTS", hashes):
                with patch.object(subject.metadata, "version",
                                  side_effect=lambda k: versions[k]):
                    with patch.object(subject.metadata, "distribution", return_value=fake):
                        self.assertIsNone(subject.assert_exact_runtime_snapshot())

    def test_sdk_import_follows_source_integrity_check(self):
        with patch.object(subject, "assert_exact_runtime_snapshot",
                          side_effect=subject.RQ2ModelPolicyBlocked("bad sha")):
            with self.assertRaisesRegex(subject.RQ2ModelPolicyBlocked, "bad sha"):
                subject.crea_modello_rq2("google", "gemini-3.5-flash-lite")

    def test_no_live_model_in_constructor_module(self):
        self.assertEqual(subject.TIMEOUT_SECONDS, 300.0)
        self.assertEqual(subject.GOOGLE_HTTP_ATTEMPTS, 1)
        self.assertEqual(subject.ANTHROPIC_MAX_RETRIES, 0)
        self.assertEqual(subject.ANTHROPIC_MAX_TOKENS, 4096)


if __name__ == "__main__":
    unittest.main()
