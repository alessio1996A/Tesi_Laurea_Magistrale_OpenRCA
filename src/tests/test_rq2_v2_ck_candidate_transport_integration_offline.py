"""Offline C/K integration audit: same text policy, Gemini/Sonnet/Haiku.

Exercises the frozen _one_call path and real strict C/K validators with a
synthetic ChatModel. The candidate extractor is patched ONLY in this test:
no production dispatcher or scientific release is modified. No API/GT/Drive.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

import evaluation.rq2_ck_provider_transport as transport
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_output_contracts import (
    ContractError, validate_candidate_rule, validate_cause_probe,
)
from evaluation.rq2_v2_ck_text_extraction_candidate import extract_visible_ck_text


MODELS = ("gemini", "sonnet", "haiku")
USAGE = {"input_tokens": 201, "output_tokens": 51, "total_tokens": 252}

VALID_C = json.dumps({
    "schema_version": "rq2_cause_probe_v0",
    "decision": "abstain",
    "predicted_fault_type": None,
    "predicted_component": None,
    "confidence": "low",
    "evidence_ids": ["E001"],
    "alternatives": ["Synthetic possible bottleneck"],
    "limitations": ["Insufficient synthetic observations"],
}, ensure_ascii=False)

VALID_K = json.dumps({
    "schema_version": "rq2_candidate_rule_v0",
    "status": "insufficient_evidence",
    "hypothesized_fault_type": None,
    "rule_name": None,
    "scope": None,
    "evidence_ids": ["E001"],
    "required_signals": [],
    "conditions": [],
    "combination": None,
    "abstain_when": ["No reliable corroborating signal"],
    "counterexamples": [],
    "limitations": ["Synthetic evidence is insufficient"],
    "pseudocode": None,
}, ensure_ascii=False)


class StubChat:
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


def candidate_text(content, *, solo_testo=False):
    if solo_testo is not True:
        raise AssertionError("Only visible C/K text extraction is permitted")
    return extract_visible_ck_text(content).raw_text


def split_text(raw, marker):
    assert marker in raw
    start, end = raw.split(marker, 1)
    return [
        {"type": "text", "text": start},
        {"type": "text", "text": marker + end},
    ]


class CandidateCKTransportIntegrationOfflineTests(unittest.TestCase):
    def _one(self, logical_model, content, *, candidate):
        spec = CANDIDATE_MODELS[logical_model]
        stub = StubChat(content)
        with patch.object(
            transport, "crea_modello", return_value=stub
        ) as factory:
            if candidate:
                with patch.object(transport, "testo_messaggio", side_effect=candidate_text):
                    result = transport._one_call(
                        spec["provider"], spec["model_id"],
                        [SystemMessage(content="offline system"),
                         HumanMessage(content="offline observation")],
                    )
            else:
                result = transport._one_call(
                    spec["provider"], spec["model_id"],
                    [SystemMessage(content="offline system"),
                     HumanMessage(content="offline observation")],
                )
        factory.assert_called_once_with(spec["provider"], spec["model_id"])
        self.assertEqual(stub.calls, 1)
        self.assertEqual(result["api_attempts"], 1)  # synthetic invoke, NOT HTTP
        self.assertIsNone(result["provider_error"])
        self.assertEqual(result["usage"]["complete"], True)
        self.assertEqual(result["usage"]["input_tokens"], 201)
        self.assertEqual(result["usage"]["output_tokens"], 51)
        return result["raw_response"]

    def test_frozen_transport_fragment_risk_remains_observable(self):
        content = split_text(VALID_C, "_probe_v0")
        for model in MODELS:
            with self.subTest(model=model):
                raw = self._one(model, content, candidate=False)
                self.assertIn("rq2_cause\n_probe_v0", raw)
                with self.assertRaises(ContractError):
                    validate_cause_probe(raw, allowed_evidence_ids=["E001"])

    def test_candidate_path_accepts_fragmented_c_for_all_models(self):
        content = split_text(VALID_C, "_probe_v0")
        for model in MODELS:
            with self.subTest(model=model):
                raw = self._one(model, content, candidate=True)
                self.assertEqual(raw, VALID_C)
                parsed = validate_cause_probe(raw, allowed_evidence_ids=["E001"])
                self.assertEqual(parsed["decision"], "abstain")

    def test_candidate_path_accepts_fragmented_k_for_all_models(self):
        content = split_text(VALID_K, "_rule_v0")
        for model in MODELS:
            with self.subTest(model=model):
                raw = self._one(model, content, candidate=True)
                self.assertEqual(raw, VALID_K)
                parsed = validate_candidate_rule(raw, allowed_evidence_ids=["E001"])
                self.assertEqual(parsed["status"], "insufficient_evidence")

    def test_candidate_keeps_malformed_c_invalid_for_all_models(self):
        malformed = VALID_C.replace("rq2_cause_probe_v0", "rq2_cause\n_probe_v0")
        for model in MODELS:
            with self.subTest(model=model):
                raw = self._one(model, [{"type": "text", "text": malformed}], candidate=True)
                self.assertEqual(raw, malformed)
                with self.assertRaises(ContractError):
                    validate_cause_probe(raw, allowed_evidence_ids=["E001"])

    def test_candidate_discards_nontext_content_for_all_models(self):
        content = [
            {"type": "thinking", "thinking": "SECRET_SYNTHETIC_REASONING",
             "signature": "SECRET_SYNTHETIC_SIGNATURE"},
            {"type": "text", "text": VALID_C[:20]},
            {"type": "text", "text": VALID_C[20:]},
        ]
        for model in MODELS:
            with self.subTest(model=model):
                raw = self._one(model, content, candidate=True)
                self.assertEqual(raw, VALID_C)
                self.assertNotIn("SECRET_SYNTHETIC", raw)
                validate_cause_probe(raw, allowed_evidence_ids=["E001"])

    def test_plain_string_is_unchanged_for_all_models(self):
        for model in MODELS:
            with self.subTest(model=model):
                raw = self._one(model, VALID_C, candidate=True)
                self.assertEqual(raw, VALID_C)
                validate_cause_probe(raw, allowed_evidence_ids=["E001"])


if __name__ == "__main__":
    unittest.main()
