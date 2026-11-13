"""Unit test offline di sintesi Gemini V1 senza filesystem scientifico.

Importa unicamente la funzione pura e simula l'API read-only:
nessun accesso a dataset reale, OOD, provider o GT.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.rq2_dryrun_plan import VERSION
from evaluation.rq2_v1_gemini_readonly_audit import (
    GeminiReadOnlyAuditError, audit_real_gemini_discovery,
    expected_gemini_ids, summarize_verified_gemini,
)


def synthetic_records():
    records = []
    for sid in expected_gemini_ids():
        case, model, harness, stage = sid.split(":")[1:]
        artifact = {}
        if stage == "C":
            artifact = {"validated_c": {"decision": "diagnosis"}}
        if stage == "K":
            artifact = {
                "validated_k": {"status": "candidate"},
                "preflight_status": "requires_verification",
                "scientific_freeze": False,
            }
        status = "RECORDED_COMPLETE"
        if case == "cloudbed-1_q032" and harness == "A1_8R":
            if stage == "C":
                status = "INVALID_OUTPUT"
                artifact = {"contract_error_type": "ContractError"}
            if stage == "K":
                status = "BLOCKED_DEPENDENCY"
                artifact = {}
        records.append({
            "stage_id": sid, "case_id": case,
            "logical_model": model, "phase": "discovery",
            "harness": harness, "stage": stage,
            "status": status, "artifact": artifact,
            "model_id_proposed": "gemini-3.5-flash-lite",
            "dependency_record_hashes": {},
        })
    return records


class V1GeminiReadOnlySummaryTests(unittest.TestCase):
    def test_exact_24_record_summary_distinguishes_all_outcomes(self):
        records = synthetic_records()
        self.assertEqual(len(records), 24)
        result = summarize_verified_gemini(records)
        self.assertEqual(result["planned_stages"], 24)
        self.assertEqual(result["by_record_status"], {
            "RECORDED_COMPLETE": 22,
            "INVALID_OUTPUT": 1,
            "BLOCKED_DEPENDENCY": 1,
        })
        self.assertEqual(result["K_contract_statuses"], {
            "blocked_dependency": 1, "candidate": 7,
        })
        self.assertEqual(result["K_preflight_statuses"],
                         {"requires_verification": 7})
        self.assertEqual(result["C_decisions"], {
            "diagnosis": 7, "invalid_output": 1,
        })
        self.assertFalse(result["can_run_ood_test"])
        self.assertFalse(result["read_ground_truth"])
        self.assertFalse(result["changed_v1_records"])
        self.assertEqual(result["model_api_calls"], 0)
        self.assertEqual(result["files_written"], 0)
        self.assertEqual(result["scientific_k_rules_frozen"], 0)
        self.assertEqual(len(result["cases"]), 8)
        self.assertNotIn("ground_truth", result)
        for case_summary in result["cases"]:
            self.assertNotIn("ground_truth", case_summary)
        self.assertNotIn("predicted_fault_type", str(result))

    def test_missing_gemini_stage_fails_closed(self):
        with self.assertRaises(GeminiReadOnlyAuditError):
            summarize_verified_gemini(synthetic_records()[:-1])

    def test_wrong_provider_stage_fails_closed(self):
        records = synthetic_records()
        records[0]["logical_model"] = "haiku"
        with self.assertRaises(GeminiReadOnlyAuditError):
            summarize_verified_gemini(records)

    def test_duplicate_record_and_missing_companion_fails_closed(self):
        records = synthetic_records()
        records[-1] = records[0].copy()
        with self.assertRaises(GeminiReadOnlyAuditError):
            summarize_verified_gemini(records)

    def test_fake_promoted_K_fails_without_scientific_freeze(self):
        records = synthetic_records()
        for record in records:
            if record["stage"] == "K" and record["status"] == "RECORDED_COMPLETE":
                record["artifact"]["scientific_freeze"] = True
                break
        with self.assertRaises(GeminiReadOnlyAuditError):
            summarize_verified_gemini(records)

    def test_synthetic_all_complete_cannot_overwrite_frozen_outcomes(self):
        records = synthetic_records()
        for record in records:
            if record["status"] != "RECORDED_COMPLETE":
                record["status"] = "RECORDED_COMPLETE"
        with self.assertRaises(GeminiReadOnlyAuditError):
            summarize_verified_gemini(records)

    def test_readonly_journal_with_fake_records_makes_no_files(self):
        records = synthetic_records()
        by_id = {x["stage_id"]: x for x in records}
        class FakeStore:
            def load_discovery_stage(self, *, stage_id):
                return by_id[stage_id]
        class FakeJournal:
            store = FakeStore()
            def __init__(self, *, data_dir):
                self.data_dir = data_dir
            def audit_restart(self):
                return {
                    "claims": 23,
                    "result_archive_discovery_count": 24,
                    "unresolved_manual_review": 0,
                    "automatic_retry_allowed": False,
                    "can_execute_api": False,
                    "can_execute_test": False,
                }
            def _read_claim(self, sid):
                record = by_id[sid]
                if record["status"] == "BLOCKED_DEPENDENCY":
                    return None
                return {
                    "model_id_proposed": record["model_id_proposed"],
                    "dependency_record_hashes": record["dependency_record_hashes"],
                }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch(
                "evaluation.rq2_v1_gemini_readonly_audit.RQ2DiscoveryClaimJournal",
                FakeJournal,
            ):
                result = audit_real_gemini_discovery(data_dir=root)
            self.assertEqual(list(root.iterdir()), [])
        self.assertEqual(result["v1_total_claims_all_providers"], 23)
        self.assertTrue(result["source_verified_by_v1_store"])
        self.assertEqual(result["observed_stages"], 24)

    def test_unresolved_claim_blocks_readonly_summary(self):
        class FakeJournal:
            def __init__(self, *, data_dir):
                pass
            def audit_restart(self):
                return {
                    "unresolved_manual_review": 1,
                    "automatic_retry_allowed": False,
                    "can_execute_api": False,
                    "can_execute_test": False,
                }
        with tempfile.TemporaryDirectory() as temp:
            with patch(
                "evaluation.rq2_v1_gemini_readonly_audit.RQ2DiscoveryClaimJournal",
                FakeJournal,
            ):
                with self.assertRaisesRegex(GeminiReadOnlyAuditError,
                                            "integrity gate"):
                    audit_real_gemini_discovery(data_dir=Path(temp))
            self.assertEqual(list(Path(temp).iterdir()), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
