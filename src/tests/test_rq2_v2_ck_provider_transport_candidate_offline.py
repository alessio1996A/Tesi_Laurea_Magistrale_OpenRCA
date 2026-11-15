"""Offline C/K transport successor audit (all providers with fake model SDK).

No live dispatch, no model API, no ground truth and no ledger mutation.
Validates the *actual candidate transport*, not a monkeypatch of the frozen
one, including contract behavior, metering, error/no-retry and safe metadata.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

import evaluation.rq2_ck_provider_transport as frozen
import evaluation.rq2_v2_ck_provider_transport_candidate as subject
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_output_contracts import (
    ContractError,
    validate_candidate_rule,
    validate_cause_probe,
)
from evaluation.rq2_v2_ck_text_extraction_candidate import POLICY


MODELS = ("gemini", "sonnet", "haiku")
USAGE = {"input_tokens": 222, "output_tokens": 38, "total_tokens": 260}
C = json.dumps({
    "schema_version": "rq2_cause_probe_v0",
    "decision": "abstain",
    "predicted_fault_type": None,
    "predicted_component": None,
    "confidence": "low",
    "evidence_ids": ["E001"],
    "alternatives": ["A possible latency issue"],
    "limitations": ["Not enough synthetic evidence"],
})
K = json.dumps({
    "schema_version": "rq2_candidate_rule_v0",
    "status": "insufficient_evidence",
    "hypothesized_fault_type": None,
    "rule_name": None,
    "scope": None,
    "evidence_ids": ["E001"],
    "required_signals": [],
    "conditions": [],
    "combination": None,
    "abstain_when": ["Data unavailable"],
    "counterexamples": [],
    "limitations": ["Insufficient evidence to formulate a detector"],
    "pseudocode": None,
})


class FakeModel:
    def __init__(self, content, *, exception=None, tool_calls=None, usage=USAGE):
        self.content = content
        self.exception = exception
        self.tool_calls = tool_calls
        self.usage = usage
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        assert len(messages) == 2
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)
        if self.exception is not None:
            raise self.exception
        return AIMessage(
            content=self.content,
            usage_metadata=self.usage,
            tool_calls=self.tool_calls or [],
            response_metadata={"finish_reason": "stop", "model_name": "fake-model"},
        )


MESSAGES = [SystemMessage(content="synthetic system"),
            HumanMessage(content="synthetic evidence")]


def blocks(raw: str, fragment: str):
    head, tail = raw.split(fragment, 1)
    return [{"type": "text", "text": head},
            {"type": "text", "text": fragment + tail}]


class CandidateTransportOfflineTests(unittest.TestCase):
    def invoke_mock(self, model: str, content, **kwargs):
        spec = CANDIDATE_MODELS[model]
        fake = FakeModel(content, **kwargs)
        with patch.object(subject, "crea_modello", return_value=fake) as factory:
            result = subject.one_ck_call_candidate(
                spec["provider"], spec["model_id"], MESSAGES
            )
        factory.assert_called_once_with(spec["provider"], spec["model_id"])
        self.assertEqual(fake.calls, 1)
        self.assertEqual(result["api_attempts"], 1)  # fake invoke only; zero HTTP
        return result

    def test_split_c_is_valid_and_metered_for_all_models(self):
        for name in MODELS:
            with self.subTest(model=name):
                result = self.invoke_mock(name, blocks(C, "_probe_v0"))
                self.assertIsNone(result["provider_error"])
                self.assertEqual(result["raw_response"], C)
                self.assertEqual(result["response_content_kind"], "list")
                self.assertEqual(result["text_blocks_observed"], 2)
                self.assertEqual(result["nontext_blocks_observed"], 0)
                self.assertEqual(result["content_extraction_policy"], POLICY)
                self.assertTrue(result["usage"]["complete"])
                self.assertEqual(result["usage"]["total_tokens"], 260)
                self.assertEqual(
                    validate_cause_probe(C, allowed_evidence_ids=["E001"])["decision"],
                    "abstain",
                )

    def test_split_k_is_valid_for_all_models(self):
        for name in MODELS:
            with self.subTest(model=name):
                result = self.invoke_mock(name, blocks(K, "_rule_v0"))
                self.assertEqual(result["raw_response"], K)
                self.assertEqual(
                    validate_candidate_rule(
                        result["raw_response"],
                        allowed_evidence_ids=["E001"],
                    )["status"],
                    "insufficient_evidence",
                )

    def test_thinking_and_signature_are_not_persisted(self):
        content = [
            {"type": "thinking", "thinking": "SECRET_SYNTHETIC_THOUGHT",
             "signature": "SECRET_SYNTHETIC_SIGNATURE"},
            {"type": "text", "text": C},
        ]
        for name in MODELS:
            with self.subTest(model=name):
                r = self.invoke_mock(name, content)
                self.assertEqual(r["raw_response"], C)
                self.assertEqual(r["text_blocks_observed"], 1)
                self.assertEqual(r["nontext_blocks_observed"], 1)
                self.assertNotIn("SECRET_SYNTHETIC", str(r))

    def test_invalid_json_is_not_repaired(self):
        corrupted = C.replace("rq2_cause_probe_v0", "rq2_cause\n_probe_v0")
        for name in MODELS:
            with self.subTest(model=name):
                r = self.invoke_mock(
                    name, [{"type": "text", "text": corrupted}]
                )
                self.assertEqual(r["raw_response"], corrupted)
                with self.assertRaises(ContractError):
                    validate_cause_probe(
                        r["raw_response"], allowed_evidence_ids=["E001"]
                    )

    def test_frozen_and_candidate_receipts_agree_on_single_string(self):
        for name in MODELS:
            with self.subTest(model=name):
                spec = CANDIDATE_MODELS[name]
                original = FakeModel(C)
                newer = FakeModel(C)
                with patch.object(
                    frozen, "crea_modello", return_value=original
                ):
                    old = frozen._one_call(
                        spec["provider"], spec["model_id"], MESSAGES
                    )
                with patch.object(
                    subject, "crea_modello", return_value=newer
                ):
                    new = subject.one_ck_call_candidate(
                        spec["provider"], spec["model_id"], MESSAGES
                    )
                self.assertEqual(original.calls, 1)
                self.assertEqual(newer.calls, 1)
                for key in (
                    "raw_response", "provider_error", "api_attempts", "usage",
                    "finish_reason", "provider_response_model",
                ):
                    self.assertEqual(old[key], new[key], key)
                self.assertEqual(new["response_content_kind"], "str")

    def test_provider_error_redacted_and_no_retry(self):
        for name in MODELS:
            with self.subTest(model=name):
                r = self.invoke_mock(
                    name, C, exception=TimeoutError("SECRET_FAKE_API_KEY"),
                )
                self.assertEqual(r["provider_error"], "PROVIDER_ERROR:TimeoutError")
                self.assertIsNone(r["raw_response"])
                self.assertNotIn("SECRET_FAKE_API_KEY", str(r))
                self.assertEqual(r["api_attempts"], 1)

    def test_sdk_construction_error_before_invoke(self):
        for name in MODELS:
            with self.subTest(model=name):
                spec = CANDIDATE_MODELS[name]
                with patch.object(
                    subject, "crea_modello",
                    side_effect=RuntimeError("SECRET_SYNTHETIC"),
                ) as factory:
                    r = subject.one_ck_call_candidate(
                        spec["provider"], spec["model_id"], MESSAGES
                    )
                factory.assert_called_once()
                self.assertEqual(
                    r["provider_error"], "SDK_CONSTRUCTION_ERROR:RuntimeError"
                )
                self.assertEqual(r["api_attempts"], 0)
                self.assertNotIn("SECRET_SYNTHETIC", str(r))

    def test_too_many_content_blocks_is_recordable_protocol_error(self):
        for name in MODELS:
            with self.subTest(model=name):
                r = self.invoke_mock(name, ["x"] * 257)
                self.assertEqual(
                    r["provider_error"], "PROTOCOL_ERROR:ContentBlockLimit"
                )
                self.assertIsNone(r["raw_response"])
                self.assertEqual(r["api_attempts"], 1)
                self.assertEqual(r["usage"]["total_tokens"], 260)

    def test_tool_calls_disallowed(self):
        for name in MODELS:
            with self.subTest(model=name):
                r = self.invoke_mock(
                    name, C, tool_calls=[{
                        "name": "fictional_tool", "args": {}, "id": "call_1",
                    }],
                )
                self.assertEqual(
                    r["provider_error"], "PROTOCOL_ERROR:ToolCallsForbidden"
                )
                self.assertIsNone(r["raw_response"])
                self.assertEqual(r["usage"]["total_tokens"], 260)


if __name__ == "__main__":
    unittest.main()
