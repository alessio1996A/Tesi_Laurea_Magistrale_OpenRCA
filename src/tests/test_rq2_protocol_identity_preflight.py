"""Offline checks for RQ1 source parity and C/K prompt fingerprint preview.

No benchmark, live models, datasets, ground truth, monetary calls or writes.
One test deliberately scans the real local RQ1 *source code* tree to detect
drift; the remaining tests use synthetic bytes/mocks and standard hashlib.
"""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.rq2_protocol_identity_preflight import (
    RQ1_BLOB_SHA1, RQ1_FROZEN_REFERENCE_COMMIT, RQ1_D_OUTPUT_MODE,
    RQ2_FINGERPRINT_PATHS, ProtocolIdentityError, _check_frozen_blob,
    git_blob_sha1, preview_protocol_identity,
)
import evaluation.rq2_protocol_identity_preflight as subject
from evaluation.rq2_probe_adapter import CAUSE_SYSTEM, RULE_SYSTEM


class RQ2ProtocolIdentityPreflightTests(unittest.TestCase):
    def test_frozen_rq1_source_tree_equals_preregistered_blob_ids(self):
        p = preview_protocol_identity()
        self.assertTrue(p["rq1_source_blob_sha1_match"])
        self.assertEqual(len(p["rq1_source_sha256"]), 13)
        self.assertEqual(p["rq1_reference_commit"], RQ1_FROZEN_REFERENCE_COMMIT)

    def test_d_protocol_mode_reused_from_actual_rq1_code(self):
        p = preview_protocol_identity()
        self.assertEqual(p["rq1_D_output_contract_mode_verified"], "v2_enforce")
        self.assertEqual(
            p["rq2_D_output_contract_mode_proposed_from_RQ1"], RQ1_D_OUTPUT_MODE
        )
        self.assertEqual(p["D_max_tool_rounds"], 6)
        self.assertEqual(p["D_recursion_limit"], 30)
        self.assertEqual(p["D_variant_scheme"], "current")
        self.assertEqual(p["D_harnesses"], ["A1", "A1_8R"])

    def test_model_ids_source_supported_but_not_api_authorized(self):
        p = preview_protocol_identity()
        self.assertEqual(p["models_proposed"], {
            "gemini": "gemini-3.5-flash-lite",
            "sonnet": "claude-sonnet-5-5",
            "haiku": "claude-haiku-5-5",
        })
        self.assertEqual(p["D_anthropic_max_output_tokens_per_request"], 4096)
        self.assertFalse(p["D_anthropic_temperature_top_p_top_k_explicitly_set"])
        self.assertFalse(p["D_google_sampler_explicitly_pinned"])

    def test_cause_and_rule_system_sha256_match_actual_python_strings(self):
        p = preview_protocol_identity()
        self.assertEqual(
            p["C_system_prompt_sha256"],
            hashlib.sha256(CAUSE_SYSTEM.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            p["K_system_prompt_sha256"],
            hashlib.sha256(RULE_SYSTEM.encode("utf-8")).hexdigest(),
        )
        self.assertNotEqual(
            p["C_system_prompt_sha256"], p["K_system_prompt_sha256"],
        )

    def test_code_fingerprints_include_probes_and_validation(self):
        p = preview_protocol_identity()
        self.assertEqual(set(p["rq2_code_sha256"]), set(RQ2_FINGERPRINT_PATHS))
        self.assertTrue(all(len(digest) == 64 for digest in
                            p["rq2_code_sha256"].values()))

    def test_protocol_is_not_frozen_or_executable(self):
        p = preview_protocol_identity()
        self.assertEqual(
            p["status"], "SOURCE_PROVENANCE_CAPTURE_NOT_SCIENTIFIC_FREEZE"
        )
        self.assertFalse(p["rq2_scientific_protocol_frozen"])
        self.assertFalse(p["rq2_discovery_api_enabled"])
        self.assertFalse(p["rq2_test_unlocked"])
        self.assertFalse(p["files_written"])
        self.assertEqual(p["provider_issued_requests"], 0)
        self.assertFalse(p["read_market"])
        self.assertFalse(p["read_ground_truth"])
        self.assertFalse(p["read_model_predictions"])
        self.assertFalse(p["cost_ceiling_required"])

    def test_pins_original_split_and_gtfree_manifest_sha(self):
        p = preview_protocol_identity()
        self.assertEqual(len(p["source_split_sha256_expected"]), 64)
        self.assertEqual(len(p["source_manifest_sha256_expected"]), 64)
        self.assertNotEqual(
            p["source_split_sha256_expected"],
            p["source_manifest_sha256_expected"],
        )

    def test_git_blob_sha1_matches_python_gitrepr_for_abc(self):
        expected = hashlib.sha1(b"blob 3\x00abc").hexdigest()
        self.assertEqual(git_blob_sha1(b"abc"), expected)

    def test_invalid_input_to_gitblob_refused(self):
        for value in ("abc", bytearray(b"abc"), None):
            with self.subTest(value=value):
                with self.assertRaises(ProtocolIdentityError):
                    git_blob_sha1(value)

    def test_synthetic_file_git_hash_matches_and_crlf_normalizes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            file = root / "sample.py"
            file.write_bytes(b"print('a')\r\nprint('b')\r\n")
            normalized = b"print('a')\nprint('b')\n"
            expected = git_blob_sha1(normalized)
            self.assertEqual(
                _check_frozen_blob(root, "sample.py", expected),
                hashlib.sha256(normalized).hexdigest(),
            )

    def test_synthetic_source_tampering_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            file = root / "sample.py"
            file.write_bytes(b"safe = True\n")
            expected = git_blob_sha1(file.read_bytes())
            file.write_bytes(b"safe = False\n")
            with self.assertRaisesRegex(ProtocolIdentityError, "source changed"):
                _check_frozen_blob(root, "sample.py", expected)

    def test_missing_source_tree_fails_without_creating_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaisesRegex(ProtocolIdentityError, "Missing"):
                preview_protocol_identity(src_root=root)
            self.assertEqual(list(root.iterdir()), [])

    def test_monkeypatch_of_rq1_blob_guard_fails_closed(self):
        old = RQ1_BLOB_SHA1["evaluation/evaluation20_preregister.py"]
        with patch.dict(
            subject.RQ1_BLOB_SHA1,
            {"evaluation/evaluation20_preregister.py": "0" * 40},
        ):
            with self.assertRaisesRegex(ProtocolIdentityError, "source changed"):
                preview_protocol_identity()
        self.assertEqual(
            RQ1_BLOB_SHA1["evaluation/evaluation20_preregister.py"], old
        )

    def test_prompt_mutation_reflected_in_capture_not_silent(self):
        original = preview_protocol_identity()
        with patch.object(subject, "CAUSE_SYSTEM", "synthetic changed prompt"):
            changed = preview_protocol_identity()
        self.assertNotEqual(
            original["C_system_prompt_sha256"],
            changed["C_system_prompt_sha256"],
        )
        self.assertEqual(
            original["K_system_prompt_sha256"],
            changed["K_system_prompt_sha256"],
        )
        self.assertFalse(changed["rq2_scientific_protocol_frozen"])


if __name__ == "__main__":
    unittest.main()
