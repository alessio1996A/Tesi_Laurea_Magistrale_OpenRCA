"""Offline audit: symmetric C/K text extraction for all three logical models.

No LLM network calls, no release, no ledger and no ground truth. This test
intentionally documents current frozen behavior; it does not authorize or
implement a new response-repair policy.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

import evaluation.rq2_ck_provider_transport as transport
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_output_contracts import ContractError, validate_cause_probe


VALID_ABSTAIN = json.dumps({
    "schema_version": "rq2_cause_probe_v0",
    "decision": "abstain",
    "predicted_fault_type": None,
    "predicted_component": None,
    "confidence": "low",
    "evidence_ids": ["E001"],
    "alternatives": ["Synthetic cause alternative"],
    "limitations": ["Insufficient synthetic telemetry"],
})
USAGE = {"input_tokens": 120, "output_tokens": 30, "total_tokens": 150}
MODELS = ("gemini", "sonnet", "haiku")


class FakeChatModel:
    def __init__(self, content):
        self.content = content
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        assert len(messages) == 2
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)
        return AIMessage(
            content=self.content,
            usage_metadata=USAGE,
            response_metadata={"finish_reason": "stop"},
        )


class MultiBlockFairnessOfflineTests(unittest.TestCase):
    def _run_mocked_ck(self, logical_model, content):
        spec = CANDIDATE_MODELS[logical_model]
        fake = FakeChatModel(content)
        with patch.object(transport, "crea_modello", return_value=fake) as factory:
            receipt = transport._one_call(
                spec["provider"], spec["model_id"],
                [SystemMessage(content="synthetic system"),
                 HumanMessage(content="synthetic evidence")],
            )
        factory.assert_called_once_with(spec["provider"], spec["model_id"])
        self.assertEqual(fake.calls, 1)
        self.assertIsNone(receipt["provider_error"])
        self.assertEqual(receipt["api_attempts"], 1)  # MOCK invoke only
        self.assertTrue(receipt["usage"]["complete"])
        self.assertEqual(receipt["usage"]["input_tokens"], 120)
        return receipt["raw_response"]

    def test_plain_string_is_valid_for_all_models(self):
        for name in MODELS:
            with self.subTest(model=name):
                raw = self._run_mocked_ck(name, VALID_ABSTAIN)
                self.assertEqual(raw, VALID_ABSTAIN)
                self.assertEqual(
                    validate_cause_probe(raw, allowed_evidence_ids=["E001"])["decision"],
                    "abstain",
                )

    def test_single_text_block_is_valid_for_all_models(self):
        for name in MODELS:
            with self.subTest(model=name):
                raw = self._run_mocked_ck(
                    name, [{"type": "text", "text": VALID_ABSTAIN}]
                )
                self.assertEqual(raw, VALID_ABSTAIN)
                self.assertEqual(
                    validate_cause_probe(raw, allowed_evidence_ids=["E001"])["decision"],
                    "abstain",
                )

    def test_two_fragment_blocks_can_break_valid_json_for_all_models(self):
        assert "_probe_v0" in VALID_ABSTAIN
        prefix, suffix = VALID_ABSTAIN.split("_probe_v0", 1)
        content = [
            {"type": "text", "text": prefix},
            {"type": "text", "text": "_probe_v0" + suffix},
        ]
        original = "".join(b["text"] for b in content)
        self.assertEqual(original, VALID_ABSTAIN)
        for name in MODELS:
            with self.subTest(model=name):
                raw = self._run_mocked_ck(name, content)
                self.assertEqual(raw, prefix + "\n_probe_v0" + suffix)
                with self.assertRaises(ContractError):
                    validate_cause_probe(raw, allowed_evidence_ids=["E001"])
        self.assertEqual(content[0]["text"], prefix)  # inputs unchanged
        self.assertEqual(content[1]["text"], "_probe_v0" + suffix)

    def test_nontext_thinking_is_excluded_for_all_models(self):
        content = [
            {"type": "thinking", "thinking": "PRIVATE_SYNTHETIC_THOUGHT",
             "signature": "SYNTHETIC_SIGNATURE"},
            {"type": "text", "text": VALID_ABSTAIN},
        ]
        for name in MODELS:
            with self.subTest(model=name):
                raw = self._run_mocked_ck(name, content)
                self.assertEqual(raw, VALID_ABSTAIN)
                self.assertNotIn("SYNTHETIC_SIGNATURE", raw)
                self.assertEqual(
                    validate_cause_probe(raw, allowed_evidence_ids=["E001"])["decision"],
                    "abstain",
                )


if __name__ == "__main__":
    unittest.main()
