"""OFFLINE successor C/K candidate -> existing V2 adapter -> sandbox ledger audit.

This is a COMPATIBILITY DIAGNOSTIC only. The frozen V2 adapter and ledger
are exercised in isolated TemporaryDirectory with synthetic release/GT-free
source, not the real science namespace. Candidate transport is mocked at its
factory before any HTTP. This test MUST NEVER be used to authorize a live
new release, nor to write into the existing RQ2-V2 ledger. No API or GT.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

import evaluation.rq2_v2_ck_provider_transport_candidate as candidate
import evaluation.rq2_v2_unified_scientific_ledger as ledger
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_v2_ck_text_extraction_candidate import POLICY
from evaluation.rq2_v2_unified_provider_result_adapter import (
    normalize_ck_call,
    normalize_d_run,
)
from evaluation.rq2_v2_unified_release_blueprint import build_unified_release_blueprint
from evaluation.rq2_v2_unified_scientific_release_contract import (
    canonical_release,
    release_digest,
)
from test_rq2_v2_unified_provider_result_adapter_offline import run as fake_run
from test_rq2_v2_unified_scientific_release_contract_offline import (
    FAKE_COMMIT,
    release_fixture,
    source_fixture,
)
from test_rq2_v2_unified_scientific_ledger_offline import sid
from test_rq2_v2_unified_synthetic_journal import cause, model_id, rule


USAGE = {"input_tokens": 203, "output_tokens": 37, "total_tokens": 240}
MESSAGES = [
    SystemMessage(content="Synthetic system prompt, no API"),
    HumanMessage(content="Synthetic incident evidence"),
]


def fragmented(raw: str, marker: str) -> list:
    prefix, suffix = raw.split(marker, 1)
    return [{"type": "text", "text": prefix},
            {"type": "text", "text": marker + suffix}]


class FakeModel:
    def __init__(self, content):
        self.content = content
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        assert len(messages) == 2
        return AIMessage(
            content=self.content,
            usage_metadata=USAGE,
            response_metadata={"finish_reason": "stop"},
        )


class CandidateLedgerCompatibilityOfflineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="rq2_ck_candidate_ledger_OFFLINE_")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.data = root / "DATA_FAKE"
        self.repo = root / "REPO_FAKE"
        self.data.mkdir()
        (self.repo / "src").mkdir(parents=True)

        source = source_fixture()
        blueprint = build_unified_release_blueprint(source_preview=source)
        release = release_fixture(source, blueprint)
        digest = release_digest(release)
        release_path = self.data / ledger.RELEASE_FILE
        release_path.parent.mkdir(parents=True)
        release_path.write_bytes(canonical_release(release))

        git = patch.object(
            ledger, "_repository_commit", return_value=(FAKE_COMMIT, ""),
        )
        source_patch = patch.object(
            ledger, "preview_unified_source_bound", return_value=source,
        )
        git.start()
        source_patch.start()
        self.addCleanup(git.stop)
        self.addCleanup(source_patch.stop)
        self.journal = ledger.UnifiedScientificLedger(
            data_dir=self.data,
            repo_dir=self.repo,
            expected_commit=FAKE_COMMIT,
            approved_release_sha256=digest,
        )

    def _candidate(self, logical_model: str, content):
        spec = CANDIDATE_MODELS[logical_model]
        fake = FakeModel(content)
        with patch.object(candidate, "crea_modello", return_value=fake) as factory:
            call = candidate.one_ck_call_candidate(
                spec["provider"], spec["model_id"], MESSAGES
            )
        factory.assert_called_once_with(spec["provider"], spec["model_id"])
        self.assertEqual(fake.calls, 1)
        self.assertEqual(call["api_attempts"], 1)  # MOCK ONLY
        self.assertIsNone(call["provider_error"])
        self.assertEqual(call["content_extraction_policy"], POLICY)
        return call

    def _save(self, model: str, stage: str, receipt):
        stage_id = sid(model=model, stage=stage)
        mid = model_id(model)
        self.journal.claim_stage(stage_id=stage_id, model_id=mid)
        result = self.journal.record_stage(
            stage_id=stage_id,
            model_id=mid,
            status=receipt["status"],
            artifact=receipt["artifact"],
        )
        saved = self.journal.load_record(stage_id=stage_id)
        self.assertEqual(result["record_sha256"], saved["record_sha256"])
        return saved

    def _save_d(self, model: str):
        diag = fake_run(model=model)
        receipt = normalize_d_run(
            stage_id=sid(model=model, stage="D"),
            logical_model=model,
            run=diag,
        )
        self.assertEqual(receipt["status"], "RECORDED_COMPLETE")
        self._save(model, "D", receipt)
        return diag

    def test_candidate_valid_d_c_k_is_recordable_for_all_three_models(self):
        for model in ("gemini", "sonnet", "haiku"):
            with self.subTest(model=model):
                diag = self._save_d(model)
                for stage, raw, marker in (
                    ("C", cause(), "_probe_v0"),
                    ("K", rule(), "_rule_v0"),
                ):
                    call = self._candidate(model, fragmented(raw, marker))
                    self.assertEqual(call["raw_response"], raw)
                    receipt = normalize_ck_call(
                        stage_id=sid(model=model, stage=stage),
                        logical_model=model,
                        call=call,
                        diagnostic_run=diag,
                    )
                    self.assertEqual(receipt["status"], "RECORDED_COMPLETE")
                    saved = self._save(model, stage, receipt)
                    self.assertEqual(saved["status"], "RECORDED_COMPLETE")
                    self.assertEqual(saved["artifact"]["raw_response"], raw)
                    self.assertEqual(
                        saved["artifact"]["stage_meter"]["observed_model_requests"],
                        1,
                    )
        report = self.journal.audit_restart()
        self.assertEqual(report["claims"], 9)
        self.assertEqual(report["records"], 9)
        self.assertEqual(report["orphan_claims"], 0)
        self.assertFalse(report["can_execute_api"])

    def test_candidate_genuine_invalid_c_leaves_k_blocked_and_no_retry(self):
        model = "gemini"
        diag = self._save_d(model)
        corrupted = cause().replace(
            "rq2_cause_probe_v0", "rq2_cause\n_probe_v0"
        )
        call = self._candidate(model, [{"type": "text", "text": corrupted}])
        receipt = normalize_ck_call(
            stage_id=sid(model=model, stage="C"),
            logical_model=model,
            call=call,
            diagnostic_run=diag,
        )
        self.assertEqual(receipt["status"], "INVALID_OUTPUT")
        self._save(model, "C", receipt)
        blocked = self.journal.record_stage(
            stage_id=sid(model=model, stage="K"),
            model_id=model_id(model),
            status="BLOCKED_DEPENDENCY",
            artifact={},
        )
        self.assertEqual(blocked["status"], "BLOCKED_DEPENDENCY")
        self.assertIsNone(
            self.journal.load_claim(stage_id=sid(model=model, stage="K"))
        )
        report = self.journal.audit_restart()
        self.assertEqual(report["claims"], 2)
        self.assertEqual(report["records"], 3)
        self.assertEqual(report["orphan_claims"], 0)
        with self.assertRaises(ledger.UnifiedScientificLedgerBlocked):
            self.journal.claim_stage(
                stage_id=sid(model=model, stage="C"),
                model_id=model_id(model),
            )

    def test_existing_adapter_discards_candidate_text_block_provenance(self):
        """An observed FAIRNESS GAP, not a GO decision for the successor."""
        model = "gemini"
        diag = self._save_d(model)
        call = self._candidate(
            model, fragmented(cause(), "_probe_v0")
        )
        self.assertEqual(call["text_blocks_observed"], 2)
        self.assertEqual(call["content_extraction_policy"], POLICY)
        receipt = normalize_ck_call(
            stage_id=sid(model=model, stage="C"),
            logical_model=model,
            call=call,
            diagnostic_run=diag,
        )
        self.assertEqual(receipt["status"], "RECORDED_COMPLETE")
        artifact = receipt["artifact"]
        self.assertEqual(set(artifact), {"raw_response", "stage_meter"})
        self.assertNotIn("content_extraction_policy", artifact)
        self.assertNotIn("text_blocks_observed", artifact)
        saved = self._save(model, "C", receipt)
        self.assertNotIn("content_extraction_policy", saved["artifact"])
        self.assertNotIn("text_blocks_observed", saved["artifact"])
        self.assertEqual(self.journal.audit_restart()["orphan_claims"], 0)


if __name__ == "__main__":
    unittest.main()
