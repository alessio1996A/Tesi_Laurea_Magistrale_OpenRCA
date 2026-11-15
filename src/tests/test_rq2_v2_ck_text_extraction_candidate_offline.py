"""Offline tests for one vendor-neutral candidate C/K text extraction policy.

No API, no GT, no ledger or release mutation. This tests proposed behavior,
not an active change to the frozen scientific dispatcher.
"""
from __future__ import annotations

import json
import unittest

from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_output_contracts import ContractError, validate_cause_probe
from evaluation.rq2_v2_ck_text_extraction_candidate import (
    CKTextExtractionBlocked, MAX_BLOCKS, extract_visible_ck_text,
)


VALID = json.dumps({
    "schema_version": "rq2_cause_probe_v0",
    "decision": "abstain",
    "predicted_fault_type": None,
    "predicted_component": None,
    "confidence": "low",
    "evidence_ids": ["E001"],
    "alternatives": [],
    "limitations": ["Missing telemetry"],
})


class CKTextExtractionCandidateOfflineTests(unittest.TestCase):
    def test_same_string_for_all_three_logical_models(self):
        for logical_model in ("gemini", "sonnet", "haiku"):
            with self.subTest(model=logical_model):
                self.assertIn(logical_model, CANDIDATE_MODELS)
                result = extract_visible_ck_text(VALID)
                self.assertEqual(result.raw_text, VALID)
                self.assertEqual(result.content_kind, "str")
                self.assertEqual(
                    validate_cause_probe(
                        result.raw_text, allowed_evidence_ids=["E001"]
                    )["decision"],
                    "abstain",
                )

    def test_split_json_inside_schema_value_no_added_separator(self):
        prefix, suffix = VALID.split("_probe_v0", 1)
        fragments = [
            {"type": "text", "text": prefix},
            {"type": "text", "text": "_probe_v0" + suffix},
        ]
        result = extract_visible_ck_text(fragments)
        self.assertEqual(result.raw_text, VALID)
        self.assertEqual(result.text_blocks, 2)
        self.assertEqual(result.other_blocks, 0)
        validate_cause_probe(result.raw_text, allowed_evidence_ids=["E001"])

    def test_thinking_signature_and_tool_content_are_not_leaked(self):
        blocks = [
            {"type": "thinking", "thinking": "SENSITIVE_SYNTHETIC_REASONING",
             "signature": "SYNTHETIC_SIGNATURE"},
            {"type": "text", "text": VALID[:12]},
            {"type": "tool_use", "name": "not_allowed",
             "input": {"secret": "SYNTHETIC_SECRET"}},
            {"type": "text_delta", "text": VALID[12:]},
        ]
        result = extract_visible_ck_text(blocks)
        self.assertEqual(result.raw_text, VALID)
        self.assertEqual(result.text_blocks, 2)
        self.assertEqual(result.other_blocks, 2)
        self.assertNotIn("SYNTHETIC_SECRET", result.raw_text)
        self.assertNotIn("SYNTHETIC_SIGNATURE", result.raw_text)

    def test_preserves_existing_unicode_and_whitespace(self):
        content = ["caffè ", {"type": "text", "text": "\ncartservice "},
                   {"type": "text", "text": "✓"}]
        result = extract_visible_ck_text(content)
        self.assertEqual(result.raw_text, "caffè \ncartservice ✓")

    def test_genuinely_malformed_json_not_repaired(self):
        corrupted = VALID.replace("rq2_cause_probe_v0", "rq2_cause\n_probe_v0")
        result = extract_visible_ck_text([{"type": "text", "text": corrupted}])
        self.assertEqual(result.raw_text, corrupted)
        with self.assertRaises(ContractError):
            validate_cause_probe(result.raw_text, allowed_evidence_ids=["E001"])

    def test_independent_json_objects_are_not_repaired_or_merged(self):
        result = extract_visible_ck_text([
            {"type": "text", "text": VALID},
            {"type": "text", "text": VALID},
        ])
        self.assertEqual(result.raw_text, VALID + VALID)
        with self.assertRaises(ContractError):
            validate_cause_probe(result.raw_text, allowed_evidence_ids=["E001"])

    def test_unsupported_envelopes_and_empty_blocks(self):
        self.assertEqual(extract_visible_ck_text({"type": "text", "text": VALID}).raw_text, "")
        self.assertEqual(extract_visible_ck_text(None).content_kind, "unsupported")
        self.assertEqual(extract_visible_ck_text([]).raw_text, "")
        self.assertEqual(extract_visible_ck_text(
            [{"type": "thinking", "thinking": "private"}]
        ).raw_text, "")

    def test_unhashable_block_type_is_treated_as_nontext(self):
        result = extract_visible_ck_text([
            {"type": ["text"], "text": "must-not-appear"},
            {"type": "text", "text": VALID},
        ])
        self.assertEqual(result.raw_text, VALID)
        self.assertEqual(result.other_blocks, 1)

    def test_excessive_blocks_fail_closed(self):
        with self.assertRaises(CKTextExtractionBlocked):
            extract_visible_ck_text(["x"] * (MAX_BLOCKS + 1))


if __name__ == "__main__":
    unittest.main()
