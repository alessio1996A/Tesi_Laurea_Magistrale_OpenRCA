"""Offline candidate C/K receipt contract: all models, strict provenance.

No API, no scientific ledger writes, no release or ground truth. Validates
new versioned artifact without changing frozen V2 artifact/receipt contracts.
"""
from __future__ import annotations

import copy
import hashlib
import json
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

import evaluation.rq2_v2_ck_provider_transport_candidate as transport
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_v2_ck_text_extraction_candidate import POLICY
from evaluation.rq2_v2_unified_provider_result_adapter import normalize_ck_call
from evaluation.rq2_v2_unified_scientific_ledger import (
    UnifiedScientificLedgerBlocked,
    _validate_artifact,
)
from evaluation.rq2_v3_ck_provenance_receipt_candidate import (
    CKProvenanceReceiptBlocked, META_SCHEMA,
    candidate_ck_record_receipt, validate_candidate_ck_artifact,
)
from test_rq2_v2_unified_provider_result_adapter_offline import run
from test_rq2_v2_unified_scientific_ledger_offline import sid
from test_rq2_v2_unified_synthetic_journal import cause, rule
from evaluation.rq2_v2_unified_provider_result_adapter import _row


USAGE = {"input_tokens": 117, "output_tokens": 23, "total_tokens": 140}
MESSAGES = [
    SystemMessage(content="synthetic system"),
    HumanMessage(content="synthetic evidence"),
]


def fragmented(raw, marker):
    a, b = raw.split(marker, 1)
    return [
        {"type": "text", "text": a},
        {"type": "text", "text": marker + b},
    ]


class StubLLM:
    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        assert len(messages) == 2
        if self.error is not None:
            raise self.error
        return AIMessage(
            content=self.content,
            usage_metadata=USAGE,
            response_metadata={"finish_reason": "stop"},
        )


class CandidateProvenanceReceiptTests(unittest.TestCase):
    def _call(self, model, content=None, error=None):
        spec = CANDIDATE_MODELS[model]
        stub = StubLLM(content=content, error=error)
        with patch.object(transport, "crea_modello", return_value=stub) as factory:
            call = transport.one_ck_call_candidate(
                spec["provider"], spec["model_id"], MESSAGES
            )
        factory.assert_called_once_with(spec["provider"], spec["model_id"])
        self.assertEqual(stub.calls, 1)
        self.assertEqual(call["api_attempts"], 1)  # synthetic SDK invoke
        return call

    def _receipt(self, *, model, stage, call, diag=None):
        diag = run(model=model) if diag is None else diag
        stage_id = sid(model=model, stage=stage)
        receipt = candidate_ck_record_receipt(
            stage_id=stage_id, logical_model=model,
            call=call, diagnostic_run=diag,
        )
        validate_candidate_ck_artifact(
            stage_id=stage_id, logical_model=model,
            status=receipt["status"], artifact=receipt["artifact"],
            diagnostic_run=diag,
        )
        return receipt

    def test_valid_fragmented_c_preserves_provenance_for_all_models(self):
        for model in ("gemini", "sonnet", "haiku"):
            with self.subTest(model=model):
                raw = cause()
                call = self._call(model, fragmented(raw, "_probe_v0"))
                receipt = self._receipt(model=model, stage="C", call=call)
                self.assertEqual(receipt["status"], "RECORDED_COMPLETE")
                artifact = receipt["artifact"]
                self.assertEqual(artifact["raw_response"], raw)
                meta = artifact["text_extraction"]
                self.assertEqual(meta["schema"], META_SCHEMA)
                self.assertEqual(meta["policy"], POLICY)
                self.assertEqual(meta["content_kind"], "list")
                self.assertEqual(meta["text_blocks"], 2)
                self.assertEqual(meta["nontext_blocks"], 0)
                self.assertEqual(
                    artifact["stage_meter"]["observed_model_requests"], 1,
                )

    def test_valid_fragmented_k_and_thinking_exclusion_for_all_models(self):
        for model in ("gemini", "sonnet", "haiku"):
            with self.subTest(model=model):
                raw = rule()
                content = [
                    {"type": "thinking", "thinking": "PRIVATE_FAKE_THOUGHT",
                     "signature": "PRIVATE_FAKE_SIGNATURE"},
                    *fragmented(raw, "_rule_v0"),
                ]
                receipt = self._receipt(
                    model=model, stage="K",
                    call=self._call(model, content),
                )
                self.assertEqual(receipt["status"], "RECORDED_COMPLETE")
                artifact = receipt["artifact"]
                self.assertEqual(artifact["raw_response"], raw)
                self.assertEqual(artifact["text_extraction"]["text_blocks"], 2)
                self.assertEqual(artifact["text_extraction"]["nontext_blocks"], 1)
                self.assertNotIn("PRIVATE_FAKE", str(receipt))

    def test_invalid_original_json_is_preserved_not_repaired(self):
        raw = cause().replace(
            "rq2_cause_probe_v0", "rq2_cause\n_probe_v0"
        )
        receipt = self._receipt(
            model="gemini", stage="C",
            call=self._call("gemini", [{"type": "text", "text": raw}]),
        )
        self.assertEqual(receipt["status"], "INVALID_OUTPUT")
        self.assertEqual(receipt["artifact"]["raw_response"], raw)
        self.assertEqual(
            receipt["artifact"]["text_extraction"]["text_blocks"], 1,
        )

    def test_provider_timeout_preserves_error_meter_and_no_content(self):
        for model in ("gemini", "sonnet", "haiku"):
            with self.subTest(model=model):
                call = self._call(
                    model, error=TimeoutError("FAKE_PRIVATE_KEY_SHOULD_NOT_LEAK")
                )
                receipt = self._receipt(model=model, stage="C", call=call)
                self.assertEqual(receipt["status"], "PROVIDER_ERROR")
                self.assertEqual(
                    receipt["artifact"]["provider_error"],
                    "PROVIDER_ERROR:TimeoutError",
                )
                self.assertEqual(
                    receipt["artifact"]["stage_meter"]["observed_model_requests"], 1
                )
                self.assertEqual(
                    receipt["artifact"]["text_extraction"]["content_kind"],
                    "not_observed",
                )
                self.assertNotIn("FAKE_PRIVATE_KEY", str(receipt))

    def test_readback_roundtrip_and_tampered_metadata_rejected(self):
        model = "gemini"
        diag = run(model=model)
        result = self._receipt(
            model=model, stage="C",
            call=self._call(model, fragmented(cause(), "_probe_v0")),
            diag=diag,
        )
        artifact = result["artifact"]
        on_disk = json.loads(json.dumps(artifact, sort_keys=True))
        self.assertEqual(on_disk, artifact)
        stage_id = sid(model=model, stage="C")
        validate_candidate_ck_artifact(
            stage_id=stage_id, logical_model=model,
            status=result["status"], artifact=on_disk,
            diagnostic_run=diag,
        )
        for path, bad in (
            ("policy", "made_up_policy"),
            ("text_blocks", 0),
            ("content_kind", "unknown"),
            ("nontext_blocks", -1),
        ):
            edited = copy.deepcopy(on_disk)
            edited["text_extraction"][path] = bad
            with self.subTest(key=path), self.assertRaises(
                CKProvenanceReceiptBlocked
            ):
                validate_candidate_ck_artifact(
                    stage_id=stage_id, logical_model=model,
                    status=result["status"], artifact=edited,
                    diagnostic_run=diag,
                )
        edited = copy.deepcopy(on_disk)
        edited["text_extraction"]["reasoning"] = "DONOTSTORE"
        with self.assertRaises(CKProvenanceReceiptBlocked):
            validate_candidate_ck_artifact(
                stage_id=stage_id, logical_model=model,
                status=result["status"], artifact=edited,
                diagnostic_run=diag,
            )
        stable = hashlib.sha256(
            json.dumps(on_disk, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.assertEqual(len(stable), 64)

    def test_missing_provenance_never_silently_falls_back(self):
        model = "sonnet"
        raw = cause()
        call = self._call(model, raw)
        call.pop("content_extraction_policy")
        with self.assertRaises(CKProvenanceReceiptBlocked):
            self._receipt(model=model, stage="C", call=call)

    def test_successor_artifact_not_accepted_by_frozen_v2_ledger(self):
        model = "haiku"
        diag = run(model=model)
        receipt = self._receipt(
            model=model, stage="C",
            call=self._call(model, cause()), diag=diag,
        )
        # Confirms a NEW artifact schema must have its own release/ledger.
        row = _row(
            stage_id=sid(model=model, stage="C"),
            logical_model=model, stage="C",
        )
        d_record = {"status": "RECORDED_COMPLETE",
                    "artifact": {"diagnostic_run": diag}}
        with self.assertRaises(UnifiedScientificLedgerBlocked):
            _validate_artifact(
                row, receipt["status"], receipt["artifact"], d_record
            )
        # Old normalization still strips the metadata, by design.
        baseline = normalize_ck_call(
            stage_id=sid(model=model, stage="C"), logical_model=model,
            call=self._call(model, cause()), diagnostic_run=diag,
        )
        self.assertNotIn("text_extraction", baseline["artifact"])


if __name__ == "__main__":
    unittest.main()
