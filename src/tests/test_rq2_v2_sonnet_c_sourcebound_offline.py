"""Test offline della prima C reale RQ2 V2: nessun provider/Drive/dataset/GT.

I gate vengono alimentati con identità parent e pacchetti sintetici, ma
claim, record, parser RQ2 e invocazione LangChain col fake sono reali.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage
import evaluation.rq2_v2_sonnet_c_sourcebound as c
from evaluation.rq2_provider_policy_source_audit import EXPECTED_COLAB_VERSIONS
from evaluation.rq2_evidence_bundle import VERSION as EVIDENCE_BUNDLE_VERSION

FAKE_BINDING = {
    "protocol": c.PROTOCOL,
    "stage_id": c.STAGE_ID,
    "code_commit": "a" * 40,
    "c_binding_sha256": "b" * 64,
    "parent_record_sha256": c.PARENT_RECORD_SHA256,
    "c_package_sha256": c.C_PACKAGE_SHA256,
}
FAKE_PACKAGE = {
    "stage": "C_cause_probe",
    "bundle_sha256": c.PARENT_BUNDLE_SHA256,
    "package_sha256": c.C_PACKAGE_SHA256,
    "system_prompt_sha256": c.C_SYSTEM_SHA256,
    "model_api_calls": 0,
    "ready_for_api": False,
    "messages": [
        {"role": "system", "content": "a" * 10000},
        {"role": "user", "content": "b" * 8084},
    ],
}
FAKE_RELEASE = {
    "schema": c.VERSION + "_release",
    "protocol": c.PROTOCOL,
    "stage_id": c.STAGE_ID,
    "code_commit": FAKE_BINDING["code_commit"],
    "c_binding_sha256": FAKE_BINDING["c_binding_sha256"],
    "parent_record_sha256": c.PARENT_RECORD_SHA256,
    "c_package_sha256": c.C_PACKAGE_SHA256,
    "provider": "anthropic", "model_id": c.MODEL_ID,
    "stage": "C", "harness": "A1",
    "max_llm_requests": 1, "max_retries": 0,
    "max_tokens": 4096, "timeout_seconds": 300,
    "approved_usd_limit": 5.0,
    "authorization": "approved_for_one_c",
    "api_budget_approved": True,
    "runtime_versions": dict(EXPECTED_COLAB_VERSIONS),
    "ood_test_locked": True,
}
VALID_DIAGNOSIS = json.dumps({
    "schema_version": "rq2_cause_probe_v0",
    "decision": "diagnosis",
    "predicted_fault_type": "synthetic anomaly",
    "predicted_component": None,
    "confidence": "low",
    "evidence_ids": ["E001"],
    "alternatives": [],
    "limitations": ["Synthetic fixture only"],
})
VALID_ABSTAIN = json.dumps({
    "schema_version": "rq2_cause_probe_v0",
    "decision": "abstain",
    "predicted_fault_type": None,
    "predicted_component": None,
    "confidence": "unassessed",
    "evidence_ids": [],
    "alternatives": [],
    "limitations": ["Insufficient evidence"],
})


class FakeLLM:
    def __init__(self, text=VALID_DIAGNOSIS, usage=True, error=None):
        self.calls = 0
        self.text, self.usage, self.error = text, usage, error

    def invoke(self, messages):
        self.calls += 1
        assert len(messages) == 2
        assert messages[0].type == "system"
        assert messages[1].type == "human"
        if self.error:
            raise self.error
        return AIMessage(
            content=self.text,
            usage_metadata=(
                {"input_tokens": 300, "output_tokens": 60, "total_tokens": 360}
                if self.usage else None
            ),
        )


class RQ2V2SonnetCOfflineTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.pin = "e" * 64

    def _mock_gate(self):
        p1 = patch.object(c, "preview_c", return_value=(FAKE_BINDING, FAKE_PACKAGE))
        p2 = patch.object(c, "read_c_release", return_value=FAKE_RELEASE)
        for p in (p1, p2):
            p.start()
            self.addCleanup(p.stop)

    def _ledger(self):
        return c.CauseLedger(
            data_dir=self.root, repo_dir=self.repo, release_sha256=self.pin,
        )

    def _run(self, fake):
        self._mock_gate()
        with (
            patch.object(c, "assert_exact_runtime_snapshot"),
            patch.object(
                c.metadata, "version",
                side_effect=lambda n: EXPECTED_COLAB_VERSIONS[n],
            ),
            patch.object(c, "crea_modello_rq2", return_value=fake) as factory,
        ):
            outcome = c.run_one_c(
                data_dir=self.root, repo_dir=self.repo,
                release_sha256=self.pin, confirm_paid_api=True,
            )
        factory.assert_called_once_with("anthropic", c.MODEL_ID)
        self.assertEqual(fake.calls, 1)
        return outcome

    def test_no_consent_blocks_provider_before_any_claim(self):
        with patch.object(c, "crea_modello_rq2") as provider:
            with self.assertRaisesRegex(c.CauseStageBlocked, "confirmation"):
                c.run_one_c(data_dir=self.root, repo_dir=self.repo)
            provider.assert_not_called()
        self.assertFalse((self.root / c.C_ROOT).exists())

    def test_missing_release_pin_blocks_claim(self):
        binding = FAKE_BINDING
        with patch.object(c, "preview_c", return_value=(binding, FAKE_PACKAGE)):
            with self.assertRaisesRegex(c.CauseStageBlocked, "NO_API"):
                c.CauseLedger(data_dir=self.root, repo_dir=self.repo).claim_stage()

    def test_preview_validates_parent_bundle_package_and_hashes(self):
        # La fixture deve rispettare lo schema reale controllato da evidence_ids().
        fake_bundle = {
            "schema_version": EVIDENCE_BUNDLE_VERSION,
            "bundle_sha256": c.PARENT_BUNDLE_SHA256,
            "observations_count": 8, "truncated_count": 3,
            "evidence": [{"evidence_id": f"E{i:03d}"} for i in range(1, 9)],
        }
        mock_base = {
            "code_commit": "a" * 40,
            "source_binding_sha256": "f" * 64,
            "instruction_sha256": "d" * 64,
        }
        with (
            patch.object(c, "source_binding", return_value=mock_base),
            patch.object(c, "_read_parent", return_value={"tool_trajectory": []}),
            patch.object(c, "_original_instruction", return_value="synthetic"),
            patch.object(c, "build_evidence_bundle", return_value=fake_bundle),
            patch.object(c, "prepare_cause_probe", return_value=FAKE_PACKAGE),
        ):
            binding, package = c.preview_c(data_dir=self.root, repo_dir=self.repo)
        self.assertEqual(binding["parent_record_sha256"], c.PARENT_RECORD_SHA256)
        self.assertEqual(binding["c_package_sha256"], c.C_PACKAGE_SHA256)
        self.assertEqual(package["package_sha256"], c.C_PACKAGE_SHA256)
        self.assertEqual(len(binding["c_binding_sha256"]), 64)

    def test_preview_rejects_wrong_bundle(self):
        fake_bundle = {"bundle_sha256": "a" * 64,
                       "observations_count": 8, "truncated_count": 3}
        with (
            patch.object(c, "source_binding", return_value={
                "code_commit": "a" * 40, "source_binding_sha256": "f" * 64,
            }),
            patch.object(c, "_read_parent", return_value={"tool_trajectory": []}),
            patch.object(c, "_original_instruction", return_value="synthetic"),
            patch.object(c, "build_evidence_bundle", return_value=fake_bundle),
        ):
            with self.assertRaisesRegex(c.CauseStageBlocked, "evidence differs"):
                c.preview_c(data_dir=self.root, repo_dir=self.repo)

    def test_claim_restart_no_retry(self):
        self._mock_gate()
        ledger = self._ledger()
        first = ledger.claim_stage()
        self.assertEqual(first["attempt_number"], 1)
        self.assertTrue(self._ledger().audit_restart()["unresolved_claim"])
        with self.assertRaisesRegex(c.CauseStageBlocked, "No retry"):
            ledger.claim_stage()

    def test_real_fake_llm_valid_diagnosis_and_readback(self):
        out = self._run(FakeLLM())
        self.assertEqual(out["status"], "RECORDED_COMPLETE")
        self.assertEqual(out["decision"], "diagnosis")
        self.assertEqual(out["model_requests"], 1)
        self.assertEqual(out["input_tokens"], 300)
        self.assertEqual(out["output_tokens"], 60)
        self.assertEqual(out["estimated_cost_usd_not_invoice"], "0.0012")
        audit = self._ledger().audit_restart()
        self.assertEqual(audit["status"], "RECORDED_COMPLETE")
        self.assertFalse(audit["unresolved_claim"])
        self.assertFalse((self.root / "data/rq2").exists())

    def test_abstention_is_not_invented_diagnosis(self):
        out = self._run(FakeLLM(VALID_ABSTAIN))
        self.assertEqual(out["status"], "RECORDED_COMPLETE")
        self.assertEqual(out["decision"], "abstain")
        self.assertFalse((self.root / "data/rq2").exists())

    def test_invalid_json_retained_as_invalid_output(self):
        out = self._run(FakeLLM("not a JSON"))
        self.assertEqual(out["status"], "INVALID_OUTPUT")
        self.assertEqual(out["issue"], "C_JSON_CONTRACT")
        self.assertIsNone(out["decision"])
        with self.assertRaisesRegex(c.CauseStageBlocked, "No retry"):
            self._ledger().claim_stage()

    def test_missing_usage_is_explicit_error(self):
        out = self._run(FakeLLM(usage=False))
        self.assertEqual(out["status"], "EXECUTION_ERROR_REVIEW")
        self.assertEqual(out["issue"], "MISSING_USAGE")
        self.assertFalse(out["usage_complete"])
        self.assertTrue(self._ledger().audit_restart()["record_exists"])

    def test_provider_exception_keeps_one_claim_without_retry(self):
        out = self._run(FakeLLM(error=TimeoutError("synthetic secret")))
        self.assertEqual(out["status"], "EXECUTION_ERROR_REVIEW")
        self.assertEqual(out["issue"], "PROVIDER_ERROR")
        record = c._read_json(self._ledger().record_path)
        self.assertEqual(record["execution_error"], "TimeoutError")
        self.assertNotIn("synthetic secret", json.dumps(record))
        with self.assertRaisesRegex(c.CauseStageBlocked, "No retry"):
            self._ledger().claim_stage()

    def test_tampered_record_detected(self):
        self._run(FakeLLM())
        ledger = self._ledger()
        rec = c._read_json(ledger.record_path)
        rec["status"] = "INVALID_OUTPUT"
        ledger.record_path.write_bytes(c._canonical(rec))
        with self.assertRaisesRegex(c.CauseStageBlocked, "C record corrupt"):
            ledger.audit_restart()

    def test_rehashed_forged_cost_is_still_rejected(self):
        self._run(FakeLLM())
        ledger = self._ledger()
        rec = c._read_json(ledger.record_path)
        rec["cost_estimate_usd_not_invoice"] = "0"
        rec["record_sha256"] = c._digest({
            k: v for k, v in rec.items() if k != "record_sha256"
        })
        ledger.record_path.write_bytes(c._canonical(rec))
        with self.assertRaisesRegex(c.CauseStageBlocked, "cost estimate"):
            ledger.audit_restart()

    def test_c_source_and_repo_must_be_distinct(self):
        with self.assertRaisesRegex(c.CauseStageBlocked, "Separate Drive"):
            c.preview_c(data_dir=self.root, repo_dir=self.root)

    def test_source_drift_after_claim_detected(self):
        self._mock_gate()
        ledger = self._ledger()
        ledger.claim_stage()
        changed = dict(FAKE_BINDING, c_binding_sha256="c" * 64)
        with patch.object(
            c, "preview_c", return_value=(changed, FAKE_PACKAGE),
        ):
            with self.assertRaisesRegex(c.CauseStageBlocked, "source drift"):
                ledger.audit_restart()

    def test_release_canonical_reader_and_tamper(self):
        path = self.root / c.C_RELEASE
        path.parent.mkdir(parents=True)
        data = c._canonical(FAKE_RELEASE)
        path.write_bytes(data)
        pin = c._hash(data)
        self.assertEqual(
            c.read_c_release(
                data_dir=self.root, binding=FAKE_BINDING,
                release_sha256=pin,
            )["stage"], "C"
        )
        bad = dict(FAKE_RELEASE, stage="K")
        path.write_bytes(c._canonical(bad))
        with self.assertRaisesRegex(c.CauseStageBlocked, "SHA mismatch"):
            c.read_c_release(
                data_dir=self.root, binding=FAKE_BINDING,
                release_sha256=pin,
            )

    def test_parent_release_hash_rejected_without_mutation(self):
        p = self.root / c.D_RELEASE_RELATIVE
        p.parent.mkdir(parents=True)
        p.write_bytes(c._canonical({
            "code_commit": c.PARENT_CODE_COMMIT, "stage": "D",
            "source_binding_sha256": c.PARENT_SOURCE_SHA256,
        }))
        with self.assertRaisesRegex(c.CauseStageBlocked, "release mismatch"):
            c._read_parent(self.root)
        self.assertFalse((self.root / c.C_ROOT).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
