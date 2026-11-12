"""Synthetic-only RQ2 artifact persistence tests. No real Market/provider/GT.

We mock ONLY the source-verification entrypoint (preview_market) and use
isolated temporary CSV bytes. The actual source-bound preflight was tested
separately. These tests never establish source authenticity for real Market.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_rq2_dryrun_plan import plan as synthetic_plan
from evaluation.rq2_dryrun_plan import _sha as plan_sha
import evaluation.rq2_stage_artifact_store as storage


class RQ2StageArtifactStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        split = self.root / "data/processed/split_market_v1.csv"
        manifest = self.root / "data/processed/benchmark_inputs_market.csv"
        split.parent.mkdir(parents=True, exist_ok=True)
        split.write_text("synthetic split bytes", encoding="utf-8")
        manifest.write_text("synthetic manifest bytes", encoding="utf-8")
        self.split = split
        self.manifest = manifest
        self.split_hash = storage._sha(split.read_bytes())
        self.manifest_hash = storage._sha(manifest.read_bytes())
        self.plan = synthetic_plan()
        self.plan["source_verified"] = True  # fake trusted wrapper IN TEST ONLY
        self.plan["split_sha256"] = self.split_hash
        self.plan["manifest_sha256"] = self.manifest_hash
        self._rehash_plan()
        self._patches = [
            patch.object(storage, "preview_market", return_value=self.plan),
            patch.object(storage, "EXPECTED_SPLIT_SHA256", self.split_hash),
            patch.object(storage, "EXPECTED_MANIFEST_SHA256", self.manifest_hash),
        ]
        for mock in self._patches:
            mock.start()
            self.addCleanup(mock.stop)
        self.artifacts = self.root / storage.STORE_SUBDIRECTORY

    def _rehash_plan(self):
        summary = {
            k: v for k, v in self.plan.items()
            if k not in ("entries", "preview_sha256")
        }
        self.plan["preview_sha256"] = plan_sha({
            "summary": summary, "entries": self.plan["entries"],
        })

    def make(self):
        return storage.RQ2StageArtifactStore(data_dir=self.root)

    def stage(self, *, case="cloudbed-1_q003", model="sonnet",
              harness="A1", step="D"):
        return (
            "rq2_dryrun_workflow_preview_v0:"
            f"{case}:{model}:{harness}:{step}"
        )

    def save(self, journal, *, step="D", status="RECORDED_COMPLETE",
             artifact=None, case="cloudbed-1_q003", model="sonnet",
             harness="A1", model_id="claude-sonnet-SYNTHETIC"):
        if artifact is None:
            artifact = {"synthetic_stage_output": step}
        return journal.save_discovery_stage(
            stage_id=self.stage(
                case=case, model=model, harness=harness, step=step,
            ),
            model_id_proposed=model_id, status=status, artifact=artifact,
        )

    def test_constructor_and_empty_audit_are_read_only(self):
        journal = self.make()
        result = journal.audit_restart()
        self.assertEqual(result["stored_discovery_stages"], 0)
        self.assertEqual(result["status"], "SOURCE_VERIFIED_NO_ARTIFACTS")
        self.assertFalse(result["can_execute_api"])
        self.assertFalse(self.artifacts.exists())

    def test_one_stage_persists_opaque_content_in_rq2_only(self):
        journal = self.make()
        receipt = self.save(journal, artifact={
            "raw_response": "synthetic RCA JSON", "tool_trajectory": [
                {"tool": "synthetic", "returned": "data"}
            ],
        })
        self.assertTrue(receipt["files_written"])
        self.assertEqual(len(list(self.artifacts.glob("RQ2_STAGE_*.json"))), 1)
        self.assertFalse((self.root / "data/results").exists())
        report = journal.audit_restart()
        self.assertEqual(report["by_status"], {"RECORDED_COMPLETE": 1})
        self.assertEqual(report["stored_discovery_stages"], 1)

    def test_all_three_discovery_steps_persist_in_order(self):
        journal = self.make()
        for step in ("D", "C", "K"):
            self.save(journal, step=step)
        report = self.make().audit_restart()
        self.assertEqual(report["stored_discovery_stages"], 3)
        self.assertEqual(report["by_status"], {"RECORDED_COMPLETE": 3})

    def test_missing_previous_stage_refuses_c_with_no_file_created(self):
        journal = self.make()
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "Missing prior"):
            self.save(journal, step="C")
        self.assertFalse(self.artifacts.exists())

    def test_provider_error_preserved_and_next_c_marked_blocked(self):
        journal = self.make()
        self.save(journal, status="PROVIDER_ERROR",
                  artifact={"error": {"code": "503", "message": "synthetic"}})
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "dependency outcome"):
            self.save(journal, step="C")
        self.save(journal, step="C", status="BLOCKED_DEPENDENCY", artifact={})
        self.save(journal, step="K", status="BLOCKED_DEPENDENCY", artifact={})
        self.assertEqual(self.make().audit_restart()["by_status"], {
            "BLOCKED_DEPENDENCY": 2, "PROVIDER_ERROR": 1,
        })

    def test_invalid_output_is_recorded_not_rewritten(self):
        journal = self.make()
        self.save(journal, status="INVALID_OUTPUT",
                  artifact={"raw_response": "synthetic invalid JSON"})
        self.assertEqual(journal.audit_restart()["by_status"]["INVALID_OUTPUT"], 1)
        with self.assertRaises(storage.RQ2ArtifactStoreError):
            self.save(journal, step="C")

    def test_successful_parent_does_not_allow_blocked_child(self):
        journal = self.make()
        self.save(journal)
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "dependency outcome"):
            self.save(journal, step="C", status="BLOCKED_DEPENDENCY", artifact={})

    def test_test_stage_is_never_allowed(self):
        journal = self.make()
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "TEST results blocked"):
            self.save(journal, case="cloudbed-1_q000")
        self.assertFalse(self.artifacts.exists())

    def test_test_k_even_if_invalid_stage_id_is_rejected(self):
        journal = self.make()
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "Unplanned stage"):
            self.save(journal, case="cloudbed-1_q000", step="K")

    def test_duplicate_stage_cannot_replace_original_content(self):
        journal = self.make()
        self.save(journal)
        before = next(self.artifacts.glob("*.json")).read_bytes()
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "Create-only"):
            self.save(journal, artifact={"synthetic_stage_output": "MODIFIED"})
        after = next(self.artifacts.glob("*.json")).read_bytes()
        self.assertEqual(before, after)

    def test_resume_detects_modified_content_without_digest(self):
        journal = self.make()
        self.save(journal)
        path = next(self.artifacts.glob("*.json"))
        obj = json.loads(path.read_text(encoding="utf-8"))
        obj["artifact"]["synthetic_stage_output"] = "TAMPER"
        path.write_bytes(storage._encoded(obj))
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "digest mismatch"):
            self.make().audit_restart()

    def test_resume_rejects_partial_crash_file(self):
        journal = self.make()
        self.save(journal)
        path = next(self.artifacts.glob("*.json"))
        path.write_bytes(b'{"partial":')
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "Corrupt"):
            journal.audit_restart()

    def test_unknown_file_refuses_restart(self):
        journal = self.make()
        self.save(journal)
        (self.artifacts / "unexpected.json").write_text("no", encoding="utf-8")
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "Unknown"):
            self.make().audit_restart()

    def test_changed_manifest_after_init_refuses_save(self):
        journal = self.make()
        self.manifest.write_text("tampered manifest", encoding="utf-8")
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "sources changed"):
            self.save(journal)
        self.assertFalse(self.artifacts.exists())

    def test_changed_split_after_init_refuses_resume(self):
        journal = self.make()
        self.save(journal)
        self.split.write_text("tampered split", encoding="utf-8")
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "sources changed"):
            journal.audit_restart()

    def test_foreign_plan_cannot_open_existing_receipts(self):
        journal = self.make()
        self.save(journal)
        self.plan["limitations"].append("synthetic altered plan")
        self._rehash_plan()
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "source mismatch"):
            self.make().audit_restart()

    def test_nonfinite_numeric_output_fails_closed(self):
        journal = self.make()
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "Noncanonical"):
            self.save(journal, artifact={"bad": float("nan")})
        self.assertFalse(self.artifacts.exists())

    def test_evaluation_ground_truth_keys_refused_recursively(self):
        journal = self.make()
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "Forbidden"):
            self.save(journal, artifact={
                "tool_output": [{"reference_fault_types": ["synthetic"]}]
            })
        self.assertFalse(self.artifacts.exists())

    def test_wrong_model_identity_and_dep_identity_refused(self):
        journal = self.make()
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "metadata"):
            self.save(journal, model_id="google-gemini-SYNTHETIC")
        self.save(journal)
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "model identity"):
            self.save(journal, step="C", model_id="claude-sonnet-DIFFERENT")

    def test_empty_nonblocked_artifact_refused(self):
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "empty"):
            self.save(self.make(), artifact={})

    def test_blocked_stage_cannot_be_D(self):
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "dependent stages"):
            self.save(self.make(), status="BLOCKED_DEPENDENCY", artifact={})

    def test_sized_artifact_cap_enforced_without_large_allocation(self):
        journal = self.make()
        with patch.object(storage, "MAX_ARTIFACT_BYTES", 60):
            with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "bounded"):
                self.save(journal, artifact={"sample": "x" * 200})
        self.assertFalse(self.artifacts.exists())

    def test_artifact_archive_cannot_be_executable_or_freeze(self):
        journal = self.make()
        self.save(journal)
        audit = journal.audit_restart()
        self.assertFalse(audit["test_phase_unlocked"])
        self.assertFalse(audit["can_execute_api"])
        self.assertEqual(audit["model_api_calls"], 0)
        self.assertFalse(hasattr(journal, "execute"))
        self.assertFalse(hasattr(journal, "run_agent"))
        self.assertFalse(hasattr(journal, "freeze_discovery"))


if __name__ == "__main__":
    unittest.main()
