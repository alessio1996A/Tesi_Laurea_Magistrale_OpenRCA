"""Test sintetici RQ2 K live: no API, no Drive reale, no GT, no OOD."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage

import evaluation.rq2_v2_sonnet_k_single_live as k
from evaluation.rq2_provider_policy_source_audit import EXPECTED_COLAB_VERSIONS


def valid_insufficient():
    return json.dumps({
        "schema_version": "rq2_candidate_rule_v0",
        "status": "insufficient_evidence",
        "hypothesized_fault_type": "synthetic CPU anomaly",
        "rule_name": None, "scope": None,
        "evidence_ids": ["E001", "E008"],
        "required_signals": [], "conditions": [], "combination": None,
        "abstain_when": ["No defensible threshold from available observations"],
        "counterexamples": [],
        "limitations": ["Synthetic evidence does not prove causality"],
        "pseudocode": None,
    })


def valid_candidate():
    return json.dumps({
        "schema_version": "rq2_candidate_rule_v0",
        "status": "candidate",
        "hypothesized_fault_type": "synthetic CPU anomaly",
        "rule_name": "synthetic_node_cpu_anomaly",
        "scope": "synthetic_node_only",
        "evidence_ids": ["E001"],
        "required_signals": [{
            "metric": "synthetic_cpu_user", "unit": "%",
            "aggregation": "max", "window_seconds": 60,
        }],
        "conditions": [{
            "metric": "synthetic_cpu_user", "unit": "%",
            "aggregation": "max", "window_seconds": 60,
            "operator": ">", "threshold": 80,
        }],
        "combination": "all",
        "abstain_when": ["Metrics missing"],
        "counterexamples": ["Synthetic scheduled CPU stress test"],
        "limitations": ["Threshold synthetic and not calibrated"],
        "pseudocode": "DO NOT EXECUTE: if synthetic signal exceeds threshold",
    })


BINDING = {
    "stage_id": k.STAGE_ID, "code_commit": "a" * 40,
    "k_binding_sha256": "b" * 64,
    "parent_d_record_sha256": k.PARENT_D_RECORD_SHA256,
    "parent_d_bundle_sha256": k.PARENT_D_BUNDLE_SHA256,
    "parent_c_record_sha256": k.C_RECORD_SHA256,
    "k_package_sha256": "c" * 64,
    "phase": "discovery", "ood_test_locked": True,
    "k_execution_authorized": False,
}
PACKAGE = {
    "stage": "K_candidate_rule", "bundle_sha256": k.PARENT_D_BUNDLE_SHA256,
    "package_sha256": BINDING["k_package_sha256"],
    "ready_for_api": False, "model_api_calls": 0,
    "messages": [
        {"role": "system", "content": "Synthetic system prompt"},
        {"role": "user", "content": "Synthetic observed data"},
    ],
}
RELEASE = {
    "schema": k.VERSION + "_release",
    "protocol": k.PROTOCOL, "stage_id": k.STAGE_ID,
    "code_commit": BINDING["code_commit"],
    "k_binding_sha256": BINDING["k_binding_sha256"],
    "parent_d_record_sha256": k.PARENT_D_RECORD_SHA256,
    "parent_c_record_sha256": k.C_RECORD_SHA256,
    "k_package_sha256": PACKAGE["package_sha256"],
    "provider": "anthropic", "model_id": k.MODEL_ID,
    "stage": "K", "harness": "A1",
    "max_llm_requests": 1, "max_retries": 0,
    "max_tokens": 4096, "timeout_seconds": 300,
    "approved_usd_limit": 5.0,
    "authorization": "approved_for_one_k",
    "api_budget_approved": True,
    "runtime_versions": dict(EXPECTED_COLAB_VERSIONS),
    "ood_test_locked": True,
    "content_extraction_policy": k.CONTENT_EXTRACTION_POLICY,
}


class FakeLLM:
    def __init__(self, content=None, error=None, usage=True):
        self.content = valid_insufficient() if content is None else content
        self.error = error
        self.usage = usage
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        assert len(messages) == 2
        assert messages[0].type == "system"
        assert messages[1].type == "human"
        if self.error:
            raise self.error
        return AIMessage(
            content=self.content,
            usage_metadata=(
                {"input_tokens": 300, "output_tokens": 60, "total_tokens": 360}
                if self.usage else None
            ),
        )


class KSingleLiveOfflineTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root = Path(d.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.pin = "f" * 64

    def _mock_gate(self):
        for p in (
            patch.object(k, "preview_k", return_value=(BINDING, PACKAGE)),
            patch.object(k, "read_k_release", return_value=RELEASE),
        ):
            p.start()
            self.addCleanup(p.stop)

    def _ledger(self):
        return k.KLedger(
            data_dir=self.root, repo_dir=self.repo,
            release_sha256=self.pin,
        )

    def _run(self, fake):
        self._mock_gate()
        with (
            patch.object(k, "assert_exact_runtime_snapshot"),
            patch.object(
                k.metadata, "version",
                side_effect=lambda name: EXPECTED_COLAB_VERSIONS[name],
            ),
            patch.object(k, "crea_modello_rq2", return_value=fake) as factory,
        ):
            out = k.run_one_k(
                data_dir=self.root, repo_dir=self.repo,
                release_sha256=self.pin, confirm_paid_api=True,
            )
        factory.assert_called_once_with("anthropic", k.MODEL_ID)
        self.assertEqual(fake.calls, 1)
        return out

    def test_no_explicit_consent_no_api_or_claim(self):
        with patch.object(k, "crea_modello_rq2") as model:
            with self.assertRaisesRegex(k.KStageBlocked, "confirmation"):
                k.run_one_k(data_dir=self.root, repo_dir=self.repo)
        model.assert_not_called()
        self.assertFalse((self.root / k.K_ROOT).exists())

    def test_absent_release_pin_rejects(self):
        with patch.object(k, "preview_k", return_value=(BINDING, PACKAGE)):
            with self.assertRaisesRegex(k.KStageBlocked, "NO_API"):
                k.KLedger(data_dir=self.root, repo_dir=self.repo).claim_stage()

    def test_insufficient_evidence_is_success_not_forced_candidate(self):
        out = self._run(FakeLLM())
        self.assertEqual(out["status"], "RECORDED_COMPLETE")
        self.assertEqual(out["decision"], "insufficient_evidence")
        self.assertFalse(out["rule_executed"])
        self.assertTrue(out["ood_test_locked"])
        self.assertEqual(out["estimated_cost_usd_not_invoice"], "0.0012")
        self.assertEqual(self._ledger().audit_restart()["k_decision"],
                         "insufficient_evidence")

    def test_candidate_is_structurally_valid_only(self):
        out = self._run(FakeLLM(content=valid_candidate()))
        self.assertEqual(out["status"], "RECORDED_COMPLETE")
        self.assertEqual(out["decision"], "candidate")
        self.assertFalse(out["rule_executed"])
        self.assertEqual(self._ledger().audit_restart()["status"],
                         "RECORDED_COMPLETE")

    def test_content_blocks_preserve_text_discard_thinking(self):
        llm = FakeLLM(content=[
            {"type": "thinking", "thinking": "", "signature": "synthetic-secret"},
            {"type": "text", "text": valid_insufficient()},
        ])
        out = self._run(llm)
        self.assertEqual(out["status"], "RECORDED_COMPLETE")
        self.assertEqual(out["response_content_kind"], "list")
        self.assertEqual(out["text_blocks_observed"], 1)
        self.assertEqual(out["nontext_blocks_observed"], 1)
        saved = k._read_json(self._ledger().record_path)
        self.assertEqual(saved["raw_response"], valid_insufficient())
        self.assertNotIn("synthetic-secret", json.dumps(saved))

    def test_only_nontext_blocks_is_invalid_no_fabrication(self):
        out = self._run(FakeLLM(content=[
            {"type": "thinking", "thinking": "", "signature": "fake"}
        ]))
        self.assertEqual(out["status"], "INVALID_OUTPUT")
        self.assertEqual(out["issue"], "K_JSON_CONTRACT")
        self.assertIsNone(out["decision"])

    def test_malformed_json_is_invalid_and_not_retried(self):
        out = self._run(FakeLLM(content="not-json"))
        self.assertEqual(out["status"], "INVALID_OUTPUT")
        with self.assertRaisesRegex(k.KStageBlocked, "No retry"):
            self._ledger().claim_stage()

    def test_provider_error_is_frozen_no_retry(self):
        out = self._run(FakeLLM(error=TimeoutError("synthetic-key")))
        self.assertEqual(out["status"], "EXECUTION_ERROR_REVIEW")
        self.assertEqual(out["issue"], "PROVIDER_ERROR")
        rec = k._read_json(self._ledger().record_path)
        self.assertEqual(rec["execution_error"], "TimeoutError")
        self.assertNotIn("synthetic-key", json.dumps(rec))

    def test_missing_usage_produces_error_record(self):
        out = self._run(FakeLLM(usage=False))
        self.assertEqual(out["status"], "EXECUTION_ERROR_REVIEW")
        self.assertEqual(out["issue"], "MISSING_USAGE")
        self.assertFalse(out["usage_complete"])

    def test_claim_without_record_is_no_retry(self):
        self._mock_gate()
        ledger = self._ledger()
        claim = ledger.claim_stage()
        self.assertEqual(claim["attempt_number"], 1)
        self.assertTrue(ledger.audit_restart()["unresolved_claim"])
        with self.assertRaisesRegex(k.KStageBlocked, "No retry"):
            ledger.claim_stage()

    def test_tampered_record_rejected(self):
        self._run(FakeLLM())
        ledger = self._ledger()
        rec = k._read_json(ledger.record_path)
        rec["k_decision"] = "candidate"
        ledger.record_path.write_bytes(k._canonical(rec))
        with self.assertRaisesRegex(k.KStageBlocked, "record corrupt"):
            ledger.audit_restart()

    def test_rehashed_forged_cost_rejected(self):
        self._run(FakeLLM())
        ledger = self._ledger()
        rec = k._read_json(ledger.record_path)
        rec["cost_estimate_usd_not_invoice"] = "0"
        rec["record_sha256"] = k._digest({
            key: val for key, val in rec.items() if key != "record_sha256"
        })
        ledger.record_path.write_bytes(k._canonical(rec))
        with self.assertRaisesRegex(k.KStageBlocked, "cost estimate"):
            ledger.audit_restart()

    def test_changed_source_binding_after_claim_rejected(self):
        self._mock_gate()
        ledger = self._ledger()
        ledger.claim_stage()
        changed = dict(BINDING, k_binding_sha256="0" * 64)
        with patch.object(k, "preview_k",
                          return_value=(changed, PACKAGE)):
            with self.assertRaisesRegex(k.KStageBlocked, "source binding"):
                ledger.audit_restart()

    def test_frozen_k_release_roundtrip_and_tampering(self):
        path = self.root / k.K_RELEASE
        path.parent.mkdir(parents=True)
        data = k._canonical(RELEASE)
        path.write_bytes(data)
        sha = k._hash(data)
        result = k.read_k_release(
            data_dir=self.root, binding=BINDING, release_sha256=sha,
        )
        self.assertEqual(result["stage"], "K")
        altered = dict(RELEASE, stage="C")
        path.write_bytes(k._canonical(altered))
        with self.assertRaisesRegex(k.KStageBlocked, "SHA mismatch"):
            k.read_k_release(
                data_dir=self.root, binding=BINDING, release_sha256=sha,
            )

    def test_release_wrong_binding_rejected_even_if_rehashed(self):
        path = self.root / k.K_RELEASE
        path.parent.mkdir(parents=True)
        altered = dict(RELEASE, k_binding_sha256="0" * 64)
        data = k._canonical(altered)
        path.write_bytes(data)
        with self.assertRaisesRegex(k.KStageBlocked, "Unapproved K"):
            k.read_k_release(
                data_dir=self.root, binding=BINDING,
                release_sha256=k._hash(data),
            )

    def test_preflight_rejects_wrong_parent(self):
        wrong = dict(BINDING, parent_c_record_sha256="0" * 64)
        with patch.object(k, "preview_k", return_value=(wrong, PACKAGE)):
            with self.assertRaisesRegex(k.KStageBlocked, "preflight drift"):
                self._ledger()._gate()

    def test_record_claim_hash_links_are_independent_from_c(self):
        out = self._run(FakeLLM())
        saved = k._read_json(self._ledger().record_path)
        self.assertEqual(saved["parent_c_record_sha256"], k.C_RECORD_SHA256)
        self.assertEqual(saved["parent_d_record_sha256"],
                         k.PARENT_D_RECORD_SHA256)
        self.assertEqual(saved["k_package_sha256"], PACKAGE["package_sha256"])
        self.assertEqual(saved["record_sha256"], out["record_sha256"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
