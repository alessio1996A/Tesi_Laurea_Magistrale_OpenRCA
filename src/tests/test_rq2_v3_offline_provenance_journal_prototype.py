"""OFFLINE ONLY tests of isolated V3 C/K provenance journal prototype.

All writes occur in the journal's internally owned TemporaryDirectory.
No data_dir/repo_dir/Drive parameters, real release, SDK or HTTP.
Stage IDs refer to frozen V2 plan only as *synthetic fixtures*.
"""
from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage

import evaluation.rq2_v2_ck_provider_transport_candidate as transport
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_v2_unified_provider_result_adapter import normalize_d_run
from evaluation.rq2_v2_unified_scientific_ledger import _canonical, _sha
from evaluation.rq2_v3_ck_provenance_receipt_candidate import (
    candidate_ck_record_receipt,
)
from evaluation.rq2_v3_offline_provenance_journal_prototype import (
    OfflineProvenanceJournal,
    OfflineProvenanceJournalBlocked,
    PROTOCOL,
)
from test_rq2_v2_unified_provider_result_adapter_offline import run
from test_rq2_v2_unified_scientific_ledger_offline import sid
from test_rq2_v2_unified_synthetic_journal import cause, model_id, rule


USAGE = {"input_tokens": 100, "output_tokens": 30, "total_tokens": 130}


class FakeChat:
    def __init__(self, content):
        self.content = content
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        return AIMessage(
            content=self.content, usage_metadata=USAGE,
            response_metadata={"finish_reason": "stop"},
        )


def fragmented(raw: str, split_at: str):
    a, b = raw.split(split_at, 1)
    return [
        {"type": "text", "text": a},
        {"type": "text", "text": split_at + b},
    ]


class OfflineJournalPrototypeTests(unittest.TestCase):
    def setUp(self):
        self.journal = OfflineProvenanceJournal()
        self.addCleanup(self.journal.close)

    def save_d(self, model="gemini"):
        source = run(model=model)
        receipt = normalize_d_run(
            stage_id=sid(model=model, stage="D"),
            logical_model=model, run=source,
        )
        self.journal.claim_stage(
            stage_id=sid(model=model, stage="D"),
            model_id=model_id(model),
        )
        saved = self.journal.record_stage(
            stage_id=sid(model=model, stage="D"),
            model_id=model_id(model),
            status=receipt["status"], artifact=receipt["artifact"],
        )
        self.assertEqual(saved["status"], "RECORDED_COMPLETE")
        return source

    def save_ck(self, model, stage, source, content):
        spec = CANDIDATE_MODELS[model]
        fake = FakeChat(content)
        from langchain_core.messages import SystemMessage, HumanMessage
        with patch.object(transport, "crea_modello", return_value=fake) as factory:
            call = transport.one_ck_call_candidate(
                spec["provider"], spec["model_id"],
                [SystemMessage(content="offline system"),
                 HumanMessage(content="offline evidence")],
            )
        factory.assert_called_once_with(spec["provider"], spec["model_id"])
        self.assertEqual(fake.calls, 1)
        receipt = candidate_ck_record_receipt(
            stage_id=sid(model=model, stage=stage),
            logical_model=model,
            call=call, diagnostic_run=source,
        )
        self.journal.claim_stage(
            stage_id=sid(model=model, stage=stage),
            model_id=model_id(model),
        )
        record = self.journal.record_stage(
            stage_id=sid(model=model, stage=stage),
            model_id=model_id(model),
            status=receipt["status"], artifact=receipt["artifact"],
        )
        return record

    def test_three_models_complete_d_c_k_create_only_with_readback(self):
        for model in ("gemini", "sonnet", "haiku"):
            with self.subTest(model=model):
                source = self.save_d(model)
                self.save_ck(model, "C", source, fragmented(cause(), "_probe_v0"))
                self.save_ck(model, "K", source, fragmented(rule(), "_rule_v0"))
                for stage in ("C", "K"):
                    saved = self.journal.load_record(
                        stage_id=sid(model=model, stage=stage),
                    )
                    self.assertEqual(saved["status"], "RECORDED_COMPLETE")
                    self.assertEqual(
                        saved["artifact"]["text_extraction"]["text_blocks"], 2,
                    )
                    self.assertEqual(
                        saved["artifact"]["stage_meter"]["observed_model_requests"], 1,
                    )
        counts = self.journal.audit()
        self.assertEqual((counts["claims"], counts["records"]), (9, 9))
        self.assertEqual(counts["orphan_claims"], 0)
        self.assertFalse(counts["can_execute_api"])
        self.assertFalse(counts["scientific_release_exists"])
        self.assertFalse(counts["production_ready"])
        self.assertEqual(counts["protocol"], PROTOCOL)

    def test_invalid_c_yields_unclaimed_blocked_k_and_no_retry(self):
        model = "gemini"
        source = self.save_d(model)
        malformed = cause().replace(
            "rq2_cause_probe_v0", "rq2_cause\n_probe_v0"
        )
        c = self.save_ck(model, "C", source, [{"type": "text", "text": malformed}])
        self.assertEqual(c["status"], "INVALID_OUTPUT")
        blocked = self.journal.record_stage(
            stage_id=sid(model=model, stage="K"),
            model_id=model_id(model), status="BLOCKED_DEPENDENCY", artifact={},
        )
        self.assertEqual(blocked["status"], "BLOCKED_DEPENDENCY")
        self.assertIsNone(
            self.journal.load_claim(stage_id=sid(model=model, stage="K"))
        )
        self.assertEqual(self.journal.audit()["orphan_claims"], 0)
        with self.assertRaises(OfflineProvenanceJournalBlocked):
            self.journal.claim_stage(
                stage_id=sid(model=model, stage="C"),
                model_id=model_id(model),
            )

    def test_orphan_claim_blocks_other_stage_until_reconciled(self):
        self.journal.claim_stage(
            stage_id=sid(model="gemini", stage="D"),
            model_id=model_id("gemini"),
        )
        self.assertEqual(self.journal.audit()["orphan_claims"], 1)
        with self.assertRaises(OfflineProvenanceJournalBlocked):
            self.journal.claim_stage(
                stage_id=sid(model="sonnet", stage="D"),
                model_id=model_id("sonnet"),
            )

    def test_duplicate_record_and_wrong_model_refused(self):
        self.save_d("gemini")
        with self.assertRaises(OfflineProvenanceJournalBlocked):
            self.journal.claim_stage(
                stage_id=sid(model="gemini", stage="D"),
                model_id=model_id("gemini"),
            )
        with self.assertRaises(OfflineProvenanceJournalBlocked):
            self.journal.claim_stage(
                stage_id=sid(model="gemini", stage="D"),
                model_id=model_id("haiku"),
            )
        old = self.journal.load_record(stage_id=sid(model="gemini", stage="D"))
        with self.assertRaises(OfflineProvenanceJournalBlocked):
            self.journal.record_stage(
                stage_id=sid(model="gemini", stage="D"),
                model_id=model_id("gemini"), status=old["status"],
                artifact=old["artifact"],
            )

    def test_provenance_tamper_even_with_recomputed_hash_is_rejected(self):
        model = "gemini"
        source = self.save_d(model)
        self.save_ck(model, "C", source, fragmented(cause(), "_probe_v0"))
        stage_id = sid(model=model, stage="C")
        path = self.journal._path(stage_id, claim=False)
        record = self.journal.load_record(stage_id=stage_id)
        changed = copy.deepcopy(record)
        changed["artifact"]["text_extraction"]["policy"] = "FORGED_POLICY"
        changed["artifact_sha256"] = _sha(changed["artifact"])
        changed["record_sha256"] = _sha({
            k: v for k, v in changed.items() if k != "record_sha256"
        })
        path.write_bytes(_canonical(changed))
        with self.assertRaises(OfflineProvenanceJournalBlocked):
            self.journal.load_record(stage_id=stage_id)

    def test_forbidden_gt_field_rejected_before_record_write(self):
        model = "gemini"
        source = self.save_d(model)
        stage_id = sid(model=model, stage="C")
        self.journal.claim_stage(
            stage_id=stage_id, model_id=model_id(model)
        )
        spec = CANDIDATE_MODELS[model]
        fake = FakeChat(cause())
        from langchain_core.messages import SystemMessage, HumanMessage
        with patch.object(transport, "crea_modello", return_value=fake):
            call = transport.one_ck_call_candidate(
                spec["provider"], spec["model_id"],
                [SystemMessage(content="synthetic"),
                 HumanMessage(content="synthetic")],
            )
        receipt = candidate_ck_record_receipt(
            stage_id=stage_id, logical_model=model,
            call=call, diagnostic_run=source,
        )
        corrupted = copy.deepcopy(receipt["artifact"])
        corrupted["ground_truth"] = "NEVER_ALLOWED"
        with self.assertRaises(Exception):
            self.journal.record_stage(
                stage_id=stage_id, model_id=model_id(model),
                status=receipt["status"], artifact=corrupted,
            )
        self.assertIsNone(self.journal.load_record(stage_id=stage_id))
        self.assertEqual(self.journal.audit()["orphan_claims"], 1)

    def test_cannot_target_external_scientific_paths(self):
        self.assertTrue(self.journal.root.name.startswith(
            "rq2_v3_OFFLINE_ONLY_no_api_"
        ))
        self.assertFalse(hasattr(self.journal, "data_dir"))
        self.assertFalse(hasattr(self.journal, "repo_dir"))
        self.assertFalse(hasattr(self.journal, "run_one_claimed_stage"))
        self.assertEqual(self.journal.audit()["records"], 0)


if __name__ == "__main__":
    unittest.main()
