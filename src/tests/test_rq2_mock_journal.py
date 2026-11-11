"""Synthetic-only RQ2 mock journal tests in disposable local temp dirs.

No real Market input, telemetry, provider, or scientific rule freeze.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import test_rq2_dryrun_plan as fixture_module
from evaluation.rq2_mock_journal import (
    FREEZE_NAME, RQ2MockJournal, MockJournalError,
    _record_name, _serialized, _sha,
)


def sample_plan():
    return fixture_module.plan()


def make(tmp):
    return RQ2MockJournal(plan=sample_plan(), root=Path(tmp))


def stages(journal, *, phase=None, stage=None):
    return [
        sid for sid in journal.stage_order
        if (phase is None or journal.entries[sid]["phase"] == phase)
        and (stage is None or journal.entries[sid]["stage"] == stage)
    ]


def finish_discovery(journal):
    count = 0
    for sid in stages(journal, phase="discovery"):
        journal.mark_mock_complete(sid)
        count += 1
    return count


class RQ2MockJournalTests(unittest.TestCase):
    def test_empty_journal_is_safe_and_never_live(self):
        with tempfile.TemporaryDirectory() as td:
            journal = make(td)
            result = journal.resume_audit()
        self.assertEqual(result["status"], "MOCK_ONLY_NEVER_API")
        self.assertEqual(result["completed_stage_count"], 0)
        self.assertFalse(result["discovery_mock_frozen"])
        self.assertFalse(result["can_execute_api"])
        self.assertFalse(result["ground_truth_read"])
        self.assertEqual(result["model_api_calls"], 0)

    def test_one_discovery_d_c_k_flow(self):
        with tempfile.TemporaryDirectory() as td:
            journal = make(td)
            d = stages(journal, phase="discovery", stage="D")[0]
            c = d[:-1] + "C"
            k = d[:-1] + "K"
            for sid in (d, c, k):
                receipt = journal.mark_mock_complete(sid)
                self.assertEqual(receipt["mock_outcome"], "MOCK_COMPLETE")
            self.assertEqual(journal.resume_audit()["completed_stage_count"], 3)

    def test_dependencies_reject_skipping_d(self):
        with tempfile.TemporaryDirectory() as td:
            journal = make(td)
            c = stages(journal, phase="discovery", stage="C")[0]
            with self.assertRaisesRegex(MockJournalError, "dependency"):
                journal.mark_mock_complete(c)

    def test_test_phase_blocked_without_mock_freeze(self):
        with tempfile.TemporaryDirectory() as td:
            journal = make(td)
            d = stages(journal, phase="test", stage="D")[0]
            with self.assertRaisesRegex(MockJournalError, "Test stage blocked"):
                journal.mark_mock_complete(d)

    def test_cannot_mock_freeze_incomplete_discovery(self):
        with tempfile.TemporaryDirectory() as td:
            journal = make(td)
            with self.assertRaisesRegex(MockJournalError, "incomplete"):
                journal.freeze_mock_discovery()

    def test_mock_freeze_after_all_24_k_and_test_unlocks(self):
        with tempfile.TemporaryDirectory() as td:
            journal = make(td)
            self.assertEqual(finish_discovery(journal), 72)
            receipt = journal.freeze_mock_discovery()
            self.assertEqual(receipt["status"], "MOCK_ONLY_NOT_RULE_FREEZE")
            self.assertEqual(len(receipt["discovery_k_record_hashes"]), 24)
            self.assertTrue(journal.resume_audit()["discovery_mock_frozen"])
            test_d = stages(journal, phase="test", stage="D")[0]
            journal.mark_mock_complete(test_d)
            self.assertEqual(journal.resume_audit()["completed_stage_count"], 73)

    def test_duplicate_stage_receipt_rejected_create_only(self):
        with tempfile.TemporaryDirectory() as td:
            journal = make(td)
            first = stages(journal, phase="discovery", stage="D")[0]
            journal.mark_mock_complete(first)
            with self.assertRaisesRegex(MockJournalError, "Create-only"):
                journal.mark_mock_complete(first)

    def test_duplicate_freeze_refused(self):
        with tempfile.TemporaryDirectory() as td:
            journal = make(td)
            finish_discovery(journal)
            journal.freeze_mock_discovery()
            with self.assertRaisesRegex(MockJournalError, "Create-only"):
                journal.freeze_mock_discovery()

    def test_restart_resume_validates_existing_receipts(self):
        with tempfile.TemporaryDirectory() as td:
            first = make(td)
            finish_discovery(first)
            first.freeze_mock_discovery()
            second = make(td)
            report = second.resume_audit()
            self.assertEqual(report["completed_stage_count"], 72)
            self.assertTrue(report["discovery_mock_frozen"])
            self.assertEqual(second.plan_sha, first.plan_sha)

    def test_corrupt_record_detected_on_restart(self):
        with tempfile.TemporaryDirectory() as td:
            journal = make(td)
            d = stages(journal, phase="discovery", stage="D")[0]
            journal.mark_mock_complete(d)
            record_path = Path(td) / _record_name(d)
            receipt = json.loads(record_path.read_text(encoding="utf-8"))
            receipt["mock_outcome"] = "SOMETHING_OTHER"
            record_path.write_bytes(_serialized(receipt))
            with self.assertRaisesRegex(MockJournalError, "digest mismatch"):
                make(td).resume_audit()

    def test_corrupt_freeze_detected_on_restart(self):
        with tempfile.TemporaryDirectory() as td:
            journal = make(td)
            finish_discovery(journal)
            journal.freeze_mock_discovery()
            freeze = Path(td) / FREEZE_NAME
            receipt = json.loads(freeze.read_text(encoding="utf-8"))
            receipt["status"] = "LIVE"
            freeze.write_bytes(_serialized(receipt))
            with self.assertRaisesRegex(MockJournalError, "integrity mismatch"):
                make(td).resume_audit()

    def test_unknown_file_in_journal_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            journal = make(td)
            (Path(td) / "unapproved_file.txt").write_text("bad", encoding="utf-8")
            with self.assertRaisesRegex(MockJournalError, "Unknown file"):
                journal.resume_audit()

    def test_plan_digest_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            plan = sample_plan()
            plan["entries"][0]["case_id"] = "tampered"
            with self.assertRaisesRegex(MockJournalError, "hash mismatch"):
                RQ2MockJournal(plan=plan, root=Path(td))

    def test_paid_api_flag_rejected(self):
        for key, value in (
            ("can_execute_api", True), ("api_budget_approved", True),
            ("status", "READY"), ("model_api_calls", 1),
        ):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as td:
                plan = sample_plan()
                plan[key] = value
                with self.assertRaises(MockJournalError):
                    RQ2MockJournal(plan=plan, root=Path(td))

    def test_test_k_stage_injection_rejected_even_if_hash_recomputed(self):
        with tempfile.TemporaryDirectory() as td:
            plan = sample_plan()
            injected = plan["entries"][-1]
            self.assertEqual(injected["phase"], "test")
            injected["stage"] = "K"
            injected["stage_id"] = injected["stage_id"][:-1] + "K"
            plan["preview_sha256"] = _sha(_serialized({
                "summary": {k:v for k,v in plan.items()
                            if k not in ("entries", "preview_sha256")},
                "entries": plan["entries"],
            }))
            with self.assertRaisesRegex(MockJournalError, "K must never"):
                RQ2MockJournal(plan=plan, root=Path(td))

    def test_mock_freeze_wont_hide_modified_discovery_record(self):
        with tempfile.TemporaryDirectory() as td:
            journal = make(td)
            finish_discovery(journal)
            journal.freeze_mock_discovery()
            k = stages(journal, phase="discovery", stage="K")[0]
            path = Path(td) / _record_name(k)
            original = json.loads(path.read_text(encoding="utf-8"))
            core = {k:v for k,v in original.items() if k != "record_sha256"}
            core["mock_outcome"] = "MOCK_COMPLETE"  # Same bytes no change
            # A valid alternative digest would still need a different payload.
            core["dependencies"] = []
            changed = {**core, "record_sha256": _sha(_serialized(core))}
            path.write_bytes(_serialized(changed))
            with self.assertRaises(MockJournalError):
                make(td).resume_audit()

    def test_partial_write_on_crash_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            journal = make(td)
            d = stages(journal, phase="discovery", stage="D")[0]
            (Path(td) / _record_name(d)).write_bytes(b'{"partial":')
            with self.assertRaisesRegex(MockJournalError, "Corrupt"):
                journal.mark_mock_complete(d)

    def test_all_204_mock_stages_can_be_audited_and_never_dispatch(self):
        with tempfile.TemporaryDirectory() as td:
            journal = make(td)
            finish_discovery(journal)
            journal.freeze_mock_discovery()
            for sid in stages(journal, phase="test"):
                journal.mark_mock_complete(sid)
            result = journal.resume_audit()
            self.assertEqual(result["completed_stage_count"], 204)
            self.assertEqual(result["model_api_calls"], 0)
            self.assertEqual(result["status"], "MOCK_ONLY_NEVER_API")


if __name__ == "__main__":
    unittest.main()
