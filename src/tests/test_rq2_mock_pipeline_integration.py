"""Synthetic-only end-to-end D/C/K integration. Never any LLM or Market."""
import json
import tempfile
import unittest
from pathlib import Path

from test_rq2_dryrun_plan import plan as make_plan
from test_rq2_output_contracts import RQ2OutputContractsTests
from test_rq2_stage_binding import (
    INSTRUCTION, cause, stage_id, synthetic_d,
)
from evaluation.rq2_mock_journal import RQ2MockJournal
from evaluation.rq2_mock_pipeline_integration import (
    MockPipelineError, record_mock_stages, validate_mock_dck_without_io,
)


def k_json():
    return json.dumps(RQ2OutputContractsTests.rule())


def arguments(plan=None, *, cid="cloudbed-1_q003", k=True):
    return {
        "plan": make_plan() if plan is None else plan,
        "c_stage_id": stage_id(cid=cid),
        "original_instruction": INSTRUCTION,
        "synthetic_d": synthetic_d(cid=cid),
        "synthetic_c_json": cause(),
        "synthetic_k_json": k_json() if k else None,
    }


class RQ2MockPipelineIntegrationTests(unittest.TestCase):
    def test_discovery_validated_in_memory_without_writes(self):
        summary = validate_mock_dck_without_io(**arguments())
        self.assertEqual(summary["status"], "MOCK_VALIDATED_NOT_EXECUTABLE")
        self.assertEqual(summary["phase"], "discovery")
        self.assertEqual(len(summary["stage_ids"]), 3)
        self.assertTrue(summary["c_output_contract_valid"])
        self.assertEqual(summary["k_output_contract_status"], "candidate")
        self.assertEqual(summary["k_formalizability_status"], "requires_verification")
        self.assertEqual(summary["observation_count"], 1)
        self.assertFalse(summary["ready_for_test"])
        self.assertEqual(summary["model_api_calls"], 0)
        self.assertFalse(summary["files_written"])

    def test_three_create_only_mock_receipts_with_existing_journal(self):
        p = make_plan()
        with tempfile.TemporaryDirectory() as td:
            journal = RQ2MockJournal(plan=p, root=Path(td))
            report = record_mock_stages(
                journal=journal, **arguments(p),
            )
            self.assertEqual(report["mock_receipts_created"], 3)
            self.assertEqual(journal.resume_audit()["completed_stage_count"], 3)
            self.assertEqual(len(list(Path(td).glob("MOCK_STAGE_*.json"))), 3)
        self.assertEqual(report["model_api_calls"], 0)
        self.assertEqual(report["written_artifact_type"], "disposable_mock_receipt_only")

    def test_create_only_repeated_triplet_is_rejected_without_extra_write(self):
        p = make_plan()
        with tempfile.TemporaryDirectory() as td:
            journal = RQ2MockJournal(plan=p, root=Path(td))
            record_mock_stages(journal=journal, **arguments(p))
            with self.assertRaisesRegex(MockPipelineError, "already completed"):
                record_mock_stages(journal=journal, **arguments(p))
            self.assertEqual(journal.resume_audit()["completed_stage_count"], 3)

    def test_discovery_without_k_is_refused(self):
        params = arguments()
        params["synthetic_k_json"] = None
        with self.assertRaisesRegex(MockPipelineError, "K is required"):
            validate_mock_dck_without_io(**params)

    def test_test_phase_must_not_contain_k(self):
        params = arguments(cid="cloudbed-1_q000")
        with self.assertRaisesRegex(MockPipelineError, "forbidden in test"):
            validate_mock_dck_without_io(**params)

    def test_test_c_preparation_without_k_is_allowed_in_memory(self):
        report = validate_mock_dck_without_io(
            **arguments(cid="cloudbed-1_q000", k=False)
        )
        self.assertEqual(report["phase"], "test")
        self.assertEqual(len(report["stage_ids"]), 2)
        self.assertIsNone(report["k_binding_sha256"])
        self.assertFalse(report["files_written"])

    def test_test_receipts_blocked_before_mock_freeze(self):
        p = make_plan()
        with tempfile.TemporaryDirectory() as td:
            journal = RQ2MockJournal(plan=p, root=Path(td))
            with self.assertRaisesRegex(MockPipelineError, "Test blocked"):
                record_mock_stages(
                    journal=journal,
                    **arguments(p, cid="cloudbed-1_q000", k=False),
                )
            self.assertEqual(journal.resume_audit()["completed_stage_count"], 0)

    def test_test_receipts_after_mock_freeze_not_real_freeze(self):
        p = make_plan()
        with tempfile.TemporaryDirectory() as td:
            journal = RQ2MockJournal(plan=p, root=Path(td))
            for sid in journal.stage_order:
                if journal.entries[sid]["phase"] != "discovery":
                    break
                journal.mark_mock_complete(sid)
            frozen = journal.freeze_mock_discovery()
            self.assertEqual(frozen["status"], "MOCK_ONLY_NOT_RULE_FREEZE")
            outcome = record_mock_stages(
                journal=journal,
                **arguments(p, cid="cloudbed-1_q000", k=False),
            )
            self.assertEqual(outcome["mock_receipts_created"], 2)
            self.assertEqual(journal.resume_audit()["completed_stage_count"], 74)
            self.assertFalse(outcome["can_execute_api"])

    def test_unknown_c_evidence_blocks_entire_triplet_before_writes(self):
        p = make_plan()
        params = arguments(p)
        value = json.loads(params["synthetic_c_json"])
        value["evidence_ids"] = ["E999"]
        params["synthetic_c_json"] = json.dumps(value)
        with tempfile.TemporaryDirectory() as td:
            journal = RQ2MockJournal(plan=p, root=Path(td))
            with self.assertRaises(MockPipelineError):
                record_mock_stages(journal=journal, **params)
            self.assertEqual(journal.resume_audit()["completed_stage_count"], 0)

    def test_unknown_k_evidence_blocks_entire_triplet_before_writes(self):
        p = make_plan()
        params = arguments(p)
        value = json.loads(params["synthetic_k_json"])
        value["evidence_ids"] = ["E999"]
        params["synthetic_k_json"] = json.dumps(value)
        with tempfile.TemporaryDirectory() as td:
            journal = RQ2MockJournal(plan=p, root=Path(td))
            with self.assertRaises(MockPipelineError):
                record_mock_stages(journal=journal, **params)
            self.assertEqual(journal.resume_audit()["completed_stage_count"], 0)

    def test_invalid_k_contract_blocks_every_mock_receipt(self):
        p = make_plan()
        params = arguments(p)
        k = json.loads(params["synthetic_k_json"])
        k["conditions"] = []
        params["synthetic_k_json"] = json.dumps(k)
        with tempfile.TemporaryDirectory() as td:
            journal = RQ2MockJournal(plan=p, root=Path(td))
            with self.assertRaises(MockPipelineError):
                record_mock_stages(journal=journal, **params)
            self.assertEqual(journal.resume_audit()["completed_stage_count"], 0)

    def test_synthetic_provider_error_blocks_c_k(self):
        params = arguments()
        params["synthetic_d"]["error"] = "SYNTHETIC_ERROR"
        with self.assertRaises(MockPipelineError):
            validate_mock_dck_without_io(**params)

    def test_d_case_identity_mismatch(self):
        params = arguments()
        params["synthetic_d"]["case_id"] = "cloudbed-2_q003"
        with self.assertRaises(MockPipelineError):
            validate_mock_dck_without_io(**params)

    def test_pseudocode_is_only_text_and_not_run(self):
        params = arguments()
        k = json.loads(params["synthetic_k_json"])
        k["pseudocode"] = "raise RuntimeError('SHOULD_NOT_EXECUTE')"
        params["synthetic_k_json"] = json.dumps(k)
        report = validate_mock_dck_without_io(**params)
        self.assertEqual(report["k_formalizability_status"], "requires_verification")
        self.assertFalse(report["rule_executed"])
        self.assertNotIn("SHOULD_NOT_EXECUTE", str(report))

    def test_refuse_live_plan_even_with_synthetic_outputs(self):
        params = arguments()
        params["plan"]["can_execute_api"] = True
        with self.assertRaises(MockPipelineError):
            validate_mock_dck_without_io(**params)

    def test_journal_type_cannot_be_replaced_by_provider_dispatch(self):
        with self.assertRaisesRegex(MockPipelineError, "mock-only journal"):
            record_mock_stages(journal=object(), **arguments())


if __name__ == "__main__":
    unittest.main()
