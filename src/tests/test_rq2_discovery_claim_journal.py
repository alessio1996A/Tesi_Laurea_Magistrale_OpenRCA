"""Synthetic-only, API-free durable RQ2 discovery claim tests."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluation.rq2_stage_artifact_store as storage
import evaluation.rq2_discovery_claim_journal as claims
import test_rq2_dryrun_plan as fixture
from evaluation.rq2_dryrun_plan import _sha as plan_digest

MODEL = "claude-sonnet-5-5"
PREFIX = "rq2_dryrun_workflow_preview_v0:cloudbed-1_q003:sonnet:A1"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RQ2DiscoveryClaimJournalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        split = self.root / "data/processed/split_market_v1.csv"
        manifest = self.root / "data/processed/benchmark_inputs_market.csv"
        split.parent.mkdir(parents=True, exist_ok=True)
        split.write_text("synthetic split only", encoding="utf-8")
        manifest.write_text("synthetic manifest only", encoding="utf-8")
        self.split = split
        self.manifest = manifest
        self.plan = fixture.plan()
        self.plan["source_verified"] = True  # TRUST MOCK ONLY FOR UNIT TESTS
        self.plan["split_sha256"] = digest(split)
        self.plan["manifest_sha256"] = digest(manifest)
        summary = {k: v for k, v in self.plan.items()
                   if k not in ("entries", "preview_sha256")}
        self.plan["preview_sha256"] = plan_digest({
            "summary": summary, "entries": self.plan["entries"],
        })
        for p in [
            patch.object(storage, "preview_market", return_value=self.plan),
            patch.object(storage, "EXPECTED_SPLIT_SHA256", digest(split)),
            patch.object(storage, "EXPECTED_MANIFEST_SHA256", digest(manifest)),
            patch.object(claims, "EXPECTED_SPLIT_SHA256", digest(split)),
            patch.object(claims, "EXPECTED_MANIFEST_SHA256", digest(manifest)),
        ]:
            p.start()
            self.addCleanup(p.stop)

    def new(self):
        return claims.RQ2DiscoveryClaimJournal(data_dir=self.root)

    def sid(self, stage="D", *, cid=None):
        prefix = PREFIX if cid is None else (
            f"rq2_dryrun_workflow_preview_v0:{cid}:sonnet:A1"
        )
        return prefix + ":" + stage

    def claim(self, obj, stage="D", model=MODEL, cid=None):
        return obj.claim_stage(
            stage_id=self.sid(stage, cid=cid),
            model_id_proposed=model,
        )

    def save(self, obj, stage="D", status="RECORDED_COMPLETE", model=MODEL):
        return obj.store.save_discovery_stage(
            stage_id=self.sid(stage), model_id_proposed=model,
            status=status,
            artifact={} if status == "BLOCKED_DEPENDENCY" else {
                "synthetic_record": stage
            },
        )

    def test_constructor_is_read_only(self):
        journal = self.new()
        self.assertFalse(journal.root.exists())
        self.assertFalse(journal.store.root.exists())
        self.assertEqual(journal.audit_restart()["claims"], 0)

    def test_first_d_claim_immutable_and_no_dispatch(self):
        journal = self.new()
        receipt = self.claim(journal)
        self.assertEqual(receipt["status"], "CLAIM_WITHOUT_ARTIFACT")
        self.assertFalse(receipt["auto_retry"])
        self.assertFalse(receipt["can_execute_api"])
        self.assertFalse(receipt["can_execute_test"])
        self.assertIsNone(receipt["financial_cost_cap"])
        self.assertFalse(journal.store.root.exists())
        self.assertEqual(len(list(journal.root.glob("*.json"))), 1)

    def test_repeated_claim_fails_closed(self):
        journal = self.new()
        self.claim(journal)
        before = next(journal.root.glob("*.json")).read_bytes()
        with self.assertRaisesRegex(claims.RQ2ClaimError, "NEVER auto retry"):
            self.claim(journal)
        self.assertEqual(before, next(journal.root.glob("*.json")).read_bytes())

    def test_colab_crash_simulated_by_restart_still_unresolved(self):
        journal = self.new()
        self.claim(journal)
        restarted = self.new()
        report = restarted.audit_restart()
        self.assertEqual(report["claims"], 1)
        self.assertEqual(report["unresolved_manual_review"], 1)
        self.assertFalse(report["automatic_retry_allowed"])
        with self.assertRaises(claims.RQ2ClaimError):
            self.claim(restarted)

    def test_matching_record_after_claim_resolves_without_claim_deletion(self):
        journal = self.new()
        self.claim(journal)
        self.save(journal)
        audit = self.new().audit_restart()
        self.assertEqual(audit["claims"], 1)
        self.assertEqual(audit["finished_with_matching_result"], 1)
        self.assertEqual(audit["unresolved_manual_review"], 0)
        self.assertEqual(len(list(journal.root.glob("*.json"))), 1)

    def test_already_saved_result_cannot_be_claimed(self):
        journal = self.new()
        self.save(journal)
        with self.assertRaisesRegex(claims.RQ2ClaimError, "already recorded"):
            self.claim(journal)
        self.assertFalse(journal.root.exists())

    def test_c_requires_recorded_d(self):
        journal = self.new()
        with self.assertRaisesRegex(claims.RQ2ClaimError, "before dependency"):
            self.claim(journal, stage="C")
        self.assertFalse(journal.root.exists())

    def test_c_claim_after_d_complete(self):
        journal = self.new()
        self.claim(journal)
        self.save(journal)
        self.claim(journal, stage="C")
        report = journal.audit_restart()
        self.assertEqual(report["claims"], 2)
        self.assertEqual(report["unresolved_manual_review"], 1)

    def test_k_claim_after_c_complete(self):
        journal = self.new()
        self.claim(journal)
        self.save(journal)
        self.claim(journal, stage="C")
        self.save(journal, stage="C")
        self.claim(journal, stage="K")
        self.save(journal, stage="K")
        report = self.new().audit_restart()
        self.assertEqual(report["claims"], 3)
        self.assertEqual(report["finished_with_matching_result"], 3)

    def test_d_provider_error_stops_c_claim(self):
        journal = self.new()
        self.claim(journal)
        self.save(journal, status="PROVIDER_ERROR")
        with self.assertRaisesRegex(claims.RQ2ClaimError, "Dependent stage failed"):
            self.claim(journal, stage="C")
        # Offline C must instead be saved as BLOCKED_DEPENDENCY, with no claim.
        self.save(journal, stage="C", status="BLOCKED_DEPENDENCY")
        self.assertEqual(journal.audit_restart()["claims"], 1)

    def test_wrong_model_id_refused(self):
        journal = self.new()
        with self.assertRaisesRegex(claims.RQ2ClaimError, "model identity"):
            self.claim(journal, model="google-gemini-SYNTHETIC")

    def test_c_model_must_equal_parent(self):
        journal = self.new()
        self.claim(journal)
        self.save(journal)
        with self.assertRaisesRegex(claims.RQ2ClaimError, "differs from stored"):
            self.claim(journal, stage="C", model="claude-sonnet-different")

    def test_test_phase_always_blocked(self):
        journal = self.new()
        with self.assertRaisesRegex(claims.RQ2ClaimError, "TEST stage"):
            self.claim(journal, cid="cloudbed-1_q000")
        self.assertFalse(journal.root.exists())

    def test_unknown_claim_stage_forbidden(self):
        journal = self.new()
        with self.assertRaisesRegex(claims.RQ2ClaimError, "Unplanned"):
            self.claim(journal, stage="X")

    def test_corrupt_claim_detected_on_resume(self):
        journal = self.new()
        self.claim(journal)
        file = next(journal.root.glob("*.json"))
        file.write_bytes(b'{"incomplete":')
        with self.assertRaisesRegex(claims.RQ2ClaimError, "noncanonical claim"):
            self.new().audit_restart()

    def test_claim_checksum_tampering_detected(self):
        journal = self.new()
        self.claim(journal)
        file = next(journal.root.glob("*.json"))
        data = json.loads(file.read_text(encoding="utf-8"))
        data["model_id_proposed"] = "claude-sonnet-corrupt"
        file.write_bytes(storage._encoded(data))
        with self.assertRaisesRegex(claims.RQ2ClaimError, "checksum mismatch"):
            self.new().audit_restart()

    def test_claim_result_different_model_detected(self):
        journal = self.new()
        self.claim(journal)
        self.save(journal, model="claude-sonnet-OTHER")
        with self.assertRaisesRegex(claims.RQ2ClaimError, "model identity differ"):
            self.new().audit_restart()

    def test_unknown_file_causes_audit_failure(self):
        journal = self.new()
        self.claim(journal)
        (journal.root / "unexpected.tmp").write_text("untrusted")
        with self.assertRaisesRegex(claims.RQ2ClaimError, "Foreign"):
            journal.audit_restart()

    def test_changed_source_bytes_block_new_claim(self):
        journal = self.new()
        self.manifest.write_text("tampered source", encoding="utf-8")
        with self.assertRaises(storage.RQ2ArtifactStoreError):
            self.claim(journal)
        self.assertFalse(journal.root.exists())

    def test_no_lease_or_automatic_recovery(self):
        journal = self.new()
        self.claim(journal)
        self.assertFalse(hasattr(journal, "release_claim"))
        self.assertFalse(hasattr(journal, "retry"))
        self.assertFalse(hasattr(journal, "execute"))
        report = journal.audit_restart()
        self.assertFalse(report["automatic_retry_allowed"])
        self.assertIsNone(report["financial_cost_cap"])


if __name__ == "__main__":
    unittest.main()
