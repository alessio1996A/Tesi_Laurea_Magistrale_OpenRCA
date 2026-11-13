"""Offline-only tests for source-bound K preview after real Sonnet C.

Tutte le fixture sono sintetiche. Nessuna API, nessun file reale Drive,
nessuna ground truth, nessuna scrittura di release o claim K.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import evaluation.rq2_v2_sonnet_k_sourcebound_preview as k
from evaluation.rq2_evidence_bundle import VERSION as EVIDENCE_BUNDLE_VERSION
from evaluation.rq2_output_contracts import (
    ContractError, validate_candidate_rule,
)

CAUSE = json.dumps({
    "schema_version": "rq2_cause_probe_v0",
    "decision": "diagnosis",
    "predicted_fault_type": "synthetic high CPU",
    "predicted_component": "synthetic-node",
    "confidence": "low",
    "evidence_ids": ["E001", "E008"],
    "alternatives": ["synthetic alternative"],
    "limitations": ["No proven causal mechanism"],
})
FAKE_BASE = {
    "code_commit": "a" * 40,
    "source_binding_sha256": "b" * 64,
}
FAKE_BUNDLE = {
    "schema_version": EVIDENCE_BUNDLE_VERSION,
    "bundle_sha256": k.PARENT_D_BUNDLE_SHA256,
    "observations_count": 8,
    "truncated_count": 3,
    "evidence": [{"evidence_id": f"E{i:03d}"} for i in range(1, 9)],
}
FAKE_C_PACKAGE = {
    "package_sha256": k.PARENT_C_PACKAGE_SHA256,
    "system_prompt_sha256": k.PARENT_C_SYSTEM_SHA256,
    "bundle_sha256": k.PARENT_D_BUNDLE_SHA256,
    "model_api_calls": 0,
    "ready_for_api": False,
}
FAKE_K_PACKAGE = {
    "stage": "K_candidate_rule",
    "bundle_sha256": k.PARENT_D_BUNDLE_SHA256,
    "package_sha256": "c" * 64,
    "system_prompt_sha256": "d" * 64,
    "model_api_calls": 0,
    "ready_for_api": False,
    "messages": [
        {"role": "system", "content": "only valid JSON"},
        {"role": "user", "content": "synthetic observed evidence"},
    ],
}
FAKE_C_RELEASE = {
    "code_commit": k.C_SOURCE_COMMIT,
    "c_binding_sha256": k.C_BINDING_SHA256,
    "parent_record_sha256": k.PARENT_D_RECORD_SHA256,
    "c_package_sha256": k.PARENT_C_PACKAGE_SHA256,
    "content_extraction_policy": "text_blocks_only_v1",
    "model_id": k.MODEL_ID,
    "stage": "C", "harness": "A1",
}
FAKE_C_CLAIM = {
    "claim_sha256": k.C_CLAIM_SHA256,
    "c_binding_sha256": k.C_BINDING_SHA256,
}
FAKE_C_RECORD = {
    "record_sha256": k.C_RECORD_SHA256,
    "status": "RECORDED_COMPLETE",
    "c_decision": "diagnosis",
    "issue": None,
    "parent_record_sha256": k.PARENT_D_RECORD_SHA256,
    "c_package_sha256": k.PARENT_C_PACKAGE_SHA256,
    "response_content_kind": "list",
    "text_blocks_observed": 1,
    "nontext_blocks_observed": 1,
    "observed_model_requests": 1,
    "raw_response": CAUSE,
}


class KSourceboundPreviewOfflineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()

    def fake_preview(self, *, bundle=None, c_package=None,
                     k_package=None, parent_record=None):
        patches = [
            patch.object(k, "source_binding", return_value=FAKE_BASE),
            patch.object(k.parent_c, "_read_parent", return_value={
                "tool_trajectory": [], "error": None,
            }),
            patch.object(k.parent_c, "_original_instruction",
                         return_value="Synthetic discovery incident"),
            patch.object(k, "build_evidence_bundle",
                         return_value=FAKE_BUNDLE if bundle is None else bundle),
            patch.object(k, "prepare_cause_probe",
                         return_value=FAKE_C_PACKAGE if c_package is None else c_package),
            patch.object(k, "_validated_c_parent", return_value=(
                {"raw_response": CAUSE} if parent_record is None else parent_record
            )),
            patch.object(k, "_assert_unchanged_invalid_c"),
            patch.object(k, "prepare_candidate_rule",
                         return_value=FAKE_K_PACKAGE if k_package is None else k_package),
        ]
        with ExitStack() as stack:
            mocks = [stack.enter_context(p) for p in patches]
            result = k.preview_k(data_dir=self.root, repo_dir=self.repo)
            return result, mocks

    def test_k_preview_is_readonly_sourcebound_and_not_authorized(self):
        (binding, package), mocks = self.fake_preview()
        self.assertEqual(binding["parent_c_record_sha256"], k.C_RECORD_SHA256)
        self.assertEqual(binding["parent_c_claim_sha256"], k.C_CLAIM_SHA256)
        self.assertEqual(binding["parent_c_release_sha256"], k.C_RELEASE_SHA256)
        self.assertEqual(binding["parent_d_record_sha256"], k.PARENT_D_RECORD_SHA256)
        self.assertEqual(binding["k_package_sha256"], FAKE_K_PACKAGE["package_sha256"])
        self.assertEqual(binding["code_commit"], FAKE_BASE["code_commit"])
        self.assertEqual(len(binding["k_binding_sha256"]), 64)
        self.assertEqual(binding["phase"], "discovery")
        self.assertTrue(binding["ood_test_locked"])
        self.assertFalse(binding["k_execution_authorized"])
        self.assertEqual(package["model_api_calls"], 0)
        self.assertFalse((self.root / k.K_ROOT).exists())
        self.assertEqual(mocks[-1].call_args.kwargs["phase"], "discovery")
        self.assertEqual(mocks[-1].call_args.kwargs["cause_raw_json"], CAUSE)

    def test_refuses_same_repo_and_data_dir(self):
        with self.assertRaisesRegex(k.KPreviewBlocked, "Separate"):
            k.preview_k(data_dir=self.root, repo_dir=self.root)

    def test_refuses_wrong_d_bundle_hash(self):
        bad = dict(FAKE_BUNDLE, bundle_sha256="f" * 64)
        with self.assertRaisesRegex(k.KPreviewBlocked, "D evidence drift"):
            self.fake_preview(bundle=bad)

    def test_refuses_wrong_evidence_count(self):
        bad = dict(FAKE_BUNDLE, observations_count=7)
        with self.assertRaisesRegex(k.KPreviewBlocked, "D evidence drift"):
            self.fake_preview(bundle=bad)

    def test_refuses_wrong_c_package_hash(self):
        bad = dict(FAKE_C_PACKAGE, package_sha256="f" * 64)
        with self.assertRaisesRegex(k.KPreviewBlocked, "C prompt package drift"):
            self.fake_preview(c_package=bad)

    def test_refuses_invalid_or_absent_c_payload(self):
        with self.assertRaises(ContractError):
            self.fake_preview(parent_record={"raw_response": ""})

    def test_refuses_wrong_evidence_refs_in_c(self):
        cause = json.loads(CAUSE)
        cause["evidence_ids"] = ["E999"]
        with self.assertRaises(ContractError):
            self.fake_preview(parent_record={"raw_response": json.dumps(cause)})

    def test_refuses_malformed_k_package(self):
        bad = dict(FAKE_K_PACKAGE, ready_for_api=True)
        with self.assertRaisesRegex(k.KPreviewBlocked, "K package"):
            self.fake_preview(k_package=bad)

    def test_refuses_k_package_wrong_bundle(self):
        bad = dict(FAKE_K_PACKAGE, bundle_sha256="f" * 64)
        with self.assertRaisesRegex(k.KPreviewBlocked, "K package"):
            self.fake_preview(k_package=bad)

    def test_old_namespace_cannot_be_written_by_preview(self):
        self.fake_preview()
        self.assertFalse((self.root / k.K_ROOT).exists())
        self.assertFalse((self.root / k.parent_c.C_ROOT).exists())

    def test_fresh_namespace_rejects_existing_claim_release_or_root(self):
        k.require_fresh_k_namespace(data_dir=self.root)
        root = self.root / k.K_ROOT
        root.mkdir(parents=True)
        with self.assertRaisesRegex(k.KPreviewBlocked, "already exists"):
            k.require_fresh_k_namespace(data_dir=self.root)

    def test_parent_release_hash_tampering_blocks(self):
        with patch.object(k, "_read_json", return_value=FAKE_C_RELEASE), \
             patch.object(k, "_hash", return_value="0" * 64):
            with self.assertRaisesRegex(k.KPreviewBlocked, "release mismatch"):
                k._validated_c_parent(self.root, c_package=FAKE_C_PACKAGE)

    def test_parent_c_claim_tampering_blocks(self):
        reader = MagicMock()
        reader._verify_claim.return_value = dict(FAKE_C_CLAIM, claim_sha256="f" * 64)
        with patch.object(k, "_read_json", return_value=FAKE_C_RELEASE), \
             patch.object(k, "_hash", return_value=k.C_RELEASE_SHA256), \
             patch.object(k.parent_c, "CauseLedger", return_value=reader):
            with self.assertRaisesRegex(k.KPreviewBlocked, "claim mismatch"):
                k._validated_c_parent(self.root, c_package=FAKE_C_PACKAGE)

    def test_parent_c_record_tampering_blocks(self):
        reader = MagicMock()
        reader._verify_claim.return_value = FAKE_C_CLAIM
        reader._verify_record.return_value = dict(
            FAKE_C_RECORD, status="INVALID_OUTPUT"
        )
        with patch.object(k, "_read_json", return_value=FAKE_C_RELEASE), \
             patch.object(k, "_hash", return_value=k.C_RELEASE_SHA256), \
             patch.object(k.parent_c, "CauseLedger", return_value=reader):
            with self.assertRaisesRegex(k.KPreviewBlocked, "record mismatch"):
                k._validated_c_parent(self.root, c_package=FAKE_C_PACKAGE)

    def test_parent_c_validates_record_against_c_package(self):
        reader = MagicMock()
        reader._verify_claim.return_value = FAKE_C_CLAIM
        reader._verify_record.return_value = FAKE_C_RECORD
        with patch.object(k, "_read_json", return_value=FAKE_C_RELEASE), \
             patch.object(k, "_hash", return_value=k.C_RELEASE_SHA256), \
             patch.object(k.parent_c, "CauseLedger", return_value=reader):
            self.assertEqual(
                k._validated_c_parent(self.root, c_package=FAKE_C_PACKAGE),
                FAKE_C_RECORD,
            )
        reader._verify_record.assert_called_once_with(
            FAKE_C_CLAIM, FAKE_C_PACKAGE,
        )

    def test_old_invalid_c_cannot_be_reclassified(self):
        core = {"status": "INVALID_OUTPUT", "raw_response": ""}
        old = {**core, "record_sha256": k.INVALID_C_RECORD_SHA256}
        with patch.object(k, "_read_json", return_value=old), \
             patch.object(k, "_digest", return_value=k.INVALID_C_RECORD_SHA256):
            k._assert_unchanged_invalid_c(self.root)
        changed = dict(old, status="RECORDED_COMPLETE")
        with patch.object(k, "_read_json", return_value=changed), \
             patch.object(k, "_digest", return_value=k.INVALID_C_RECORD_SHA256):
            with self.assertRaisesRegex(k.KPreviewBlocked, "changed"):
                k._assert_unchanged_invalid_c(self.root)

    def test_low_confidence_can_correctly_abstain_in_k(self):
        # K non è tenuta a produrre un candidato perché C dice diagnosis.
        abstain = {
            "schema_version": "rq2_candidate_rule_v0",
            "status": "insufficient_evidence",
            "hypothesized_fault_type": "synthetic high CPU",
            "rule_name": None, "scope": None,
            "evidence_ids": ["E001", "E008"],
            "required_signals": [], "conditions": [],
            "combination": None,
            "abstain_when": ["Cannot verify causal link from two observations"],
            "counterexamples": [],
            "limitations": ["Cannot justify thresholds from available observations"],
            "pseudocode": None,
        }
        result = validate_candidate_rule(
            json.dumps(abstain), allowed_evidence_ids={
                f"E{i:03d}" for i in range(1, 9)
            },
        )
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertIsNone(result["rule_name"])
        self.assertEqual(result["conditions"], [])

    def test_k_cannot_invent_threshold_nan(self):
        candidate = {
            "schema_version": "rq2_candidate_rule_v0",
            "status": "candidate", "hypothesized_fault_type": "synthetic CPU",
            "rule_name": "synthetic", "scope": "test",
            "evidence_ids": ["E001"],
            "required_signals": [{
                "metric": "cpu", "unit": "%", "aggregation": "max",
                "window_seconds": 30,
            }],
            "conditions": [{
                "metric": "cpu", "unit": "%", "aggregation": "max",
                "window_seconds": 30, "operator": ">", "threshold": float("nan"),
            }],
            "combination": "all", "abstain_when": ["no signal"],
            "counterexamples": ["synthetic baseline normal"],
            "limitations": ["synthetic only"], "pseudocode": "do not execute",
        }
        with self.assertRaises(ContractError):
            validate_candidate_rule(
                json.dumps(candidate), allowed_evidence_ids={"E001"},
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
