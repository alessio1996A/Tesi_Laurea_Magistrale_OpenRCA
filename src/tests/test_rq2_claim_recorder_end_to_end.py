"""Integrated OFFLINE, SYNTHETIC-ONLY claim -> D -> C -> K -> restart tests.

No provider, real OpenRCA dataset, GT, scoring, money or notebook runtime.
We reuse the actual RQ2DiscoveryClaimJournal and RQ2DiscoveryStageRecorder.
No new RCA runner is invented. Source/plan hashes are mocked ONLY here.
"""
from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluation.rq2_stage_artifact_store as storage
import evaluation.rq2_discovery_stage_recorder as recorder
import evaluation.rq2_discovery_claim_journal as claims
from evaluation.rq2_dryrun_plan import _sha as plan_sha
import test_rq2_dryrun_plan as plan_fixtures
import test_rq2_output_contracts as output_fixtures
import test_rq2_stage_binding as binding_fixtures

MODEL = "claude-sonnet-5-5"
CID = "cloudbed-1_q003"   # SYNTHETIC TEST COHORT ONLY, not real RQ2
STEM = f"rq2_dryrun_workflow_preview_v0:{CID}:sonnet:A1"


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RQ2ClaimRecorderEndToEndTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.split = self.root / "data/processed/split_market_v1.csv"
        self.manifest = self.root / "data/processed/benchmark_inputs_market.csv"
        cohort, _, _, _ = plan_fixtures.synthetic_cohort()
        split_rows = [
            {
                "case_id": m["case_id"], "cloudbed": m["cloudbed"],
                "start_unix": str(m["start_unix"]),
                "end_unix": str(m["end_unix"]), "split": "ood_holdout",
            }
            for m in cohort
        ]
        manifest_rows = [
            {
                "case_id": m["case_id"], "cloudbed": m["cloudbed"],
                "query_index": str(i), "task_index": m["task_index"],
                "start_unix": str(m["start_unix"]),
                "end_unix": str(m["end_unix"]),
                "instruction": binding_fixtures.INSTRUCTION,
            }
            for i, m in enumerate(cohort)
        ]
        _write_csv(self.split, (
            "case_id", "cloudbed", "start_unix", "end_unix", "split",
        ), split_rows)
        _write_csv(self.manifest, (
            "case_id", "cloudbed", "query_index", "task_index",
            "instruction", "start_unix", "end_unix",
        ), manifest_rows)
        self.plan = plan_fixtures.plan()
        self.plan["source_verified"] = True  # TEST-ONLY trust mock.
        self.plan["split_sha256"] = _hash_file(self.split)
        self.plan["manifest_sha256"] = _hash_file(self.manifest)
        summary = {
            k: v for k, v in self.plan.items()
            if k not in ("preview_sha256", "entries")
        }
        self.plan["preview_sha256"] = plan_sha({
            "summary": summary, "entries": self.plan["entries"],
        })
        for p in (
            patch.object(storage, "preview_market", return_value=self.plan),
            patch.object(recorder, "preview_market", return_value=self.plan),
            patch.object(storage, "EXPECTED_SPLIT_SHA256", _hash_file(self.split)),
            patch.object(storage, "EXPECTED_MANIFEST_SHA256", _hash_file(self.manifest)),
            patch.object(recorder, "EXPECTED_MANIFEST_SHA256", _hash_file(self.manifest)),
            patch.object(claims, "EXPECTED_SPLIT_SHA256", _hash_file(self.split)),
            patch.object(claims, "EXPECTED_MANIFEST_SHA256", _hash_file(self.manifest)),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.recorder = recorder.RQ2DiscoveryStageRecorder(data_dir=self.root)
        self.journal = claims.RQ2DiscoveryClaimJournal(data_dir=self.root)

    def sid(self, stage: str) -> str:
        return STEM + ":" + stage

    def diagnostic(self, **overrides) -> dict:
        d = binding_fixtures.synthetic_d()
        d.update({
            "model": MODEL, "error": None, "json_status": "valid_json",
        })
        d.update(overrides)
        return d

    def claim(self, stage: str, model: str = MODEL) -> dict:
        return self.journal.claim_stage(
            stage_id=self.sid(stage), model_id_proposed=model,
        )

    def d(self, **overrides) -> dict:
        return self.recorder.record_d(
            stage_id=self.sid("D"), model_id_proposed=MODEL,
            diagnostic_run=self.diagnostic(**overrides),
        )

    def c(self, raw: str | None = None, error: str | None = None) -> dict:
        return self.recorder.record_c(
            stage_id=self.sid("C"), model_id_proposed=MODEL,
            raw_response=binding_fixtures.cause() if raw == "DEFAULT" else raw,
            provider_error=error,
        )

    def k(self, raw: str | None = None, error: str | None = None) -> dict:
        return self.recorder.record_k(
            stage_id=self.sid("K"), model_id_proposed=MODEL,
            raw_response=(
                json.dumps(output_fixtures.RQ2OutputContractsTests.rule())
                if raw == "DEFAULT" else raw
            ),
            provider_error=error,
        )

    def complete(self) -> None:
        self.claim("D")
        self.d()
        self.claim("C")
        self.c("DEFAULT")
        self.claim("K")
        self.k("DEFAULT")

    def test_three_claims_three_artifacts_and_restart(self):
        self.complete()
        restarted = claims.RQ2DiscoveryClaimJournal(data_dir=self.root)
        report = restarted.audit_restart()
        self.assertEqual(report["claims"], 3)
        self.assertEqual(report["finished_with_matching_result"], 3)
        self.assertEqual(report["unresolved_manual_review"], 0)
        self.assertEqual(report["result_archive_discovery_count"], 3)
        self.assertFalse(report["can_execute_api"])
        self.assertFalse(report["can_execute_test"])

    def test_exact_dependency_order_in_claims_and_results(self):
        self.complete()
        for stage in ("C", "K"):
            sid = self.sid(stage)
            claim = self.journal._read_claim(sid)
            record = self.journal.store.load_discovery_stage(stage_id=sid)
            self.assertEqual(claim["dependency_record_hashes"],
                             record["dependency_record_hashes"])
        self.assertIsNone(self.journal.audit_restart()["financial_cost_cap"])

    def test_duplicate_after_complete_never_creates_second_attempt(self):
        self.complete()
        before = len(list(self.journal.root.glob("*.json")))
        for stage in ("D", "C", "K"):
            with self.subTest(stage=stage):
                with self.assertRaises(claims.RQ2ClaimError):
                    self.claim(stage)
        self.assertEqual(len(list(self.journal.root.glob("*.json"))), before)

    def test_claim_without_d_artifact_survives_crash_as_manual_review(self):
        self.claim("D")
        restarted = claims.RQ2DiscoveryClaimJournal(data_dir=self.root)
        self.assertEqual(restarted.audit_restart()["unresolved_manual_review"], 1)
        with self.assertRaisesRegex(claims.RQ2ClaimError, "NEVER auto retry"):
            restarted.claim_stage(
                stage_id=self.sid("D"), model_id_proposed=MODEL,
            )
        self.assertFalse(self.recorder.store.root.exists())

    def test_crash_after_c_claim_blocks_duplicate_and_k(self):
        self.claim("D")
        self.d()
        self.claim("C")
        report = claims.RQ2DiscoveryClaimJournal(
            data_dir=self.root
        ).audit_restart()
        self.assertEqual(report["finished_with_matching_result"], 1)
        self.assertEqual(report["unresolved_manual_review"], 1)
        with self.assertRaises(claims.RQ2ClaimError):
            self.claim("C")
        with self.assertRaisesRegex(claims.RQ2ClaimError, "dependency"):
            self.claim("K")

    def test_provider_error_d_records_failure_and_blocks_c_k_without_claim(self):
        self.claim("D")
        self.d(error="synthetic upstream failure")
        self.c(None)
        self.k(None)
        a = self.journal.audit_restart()
        self.assertEqual(a["claims"], 1)
        self.assertEqual(a["finished_with_matching_result"], 1)
        self.assertEqual(a["result_archive_discovery_count"], 3)
        self.assertEqual(self.recorder.store.audit_restart()["by_status"], {
            "BLOCKED_DEPENDENCY": 2, "PROVIDER_ERROR": 1,
        })

    def test_c_provider_error_blocks_k_without_k_claim(self):
        self.claim("D")
        self.d()
        self.claim("C")
        self.c(None, error="synthetic timeout")
        self.k(None)
        a = self.journal.audit_restart()
        self.assertEqual(a["claims"], 2)
        self.assertEqual(a["finished_with_matching_result"], 2)
        self.assertEqual(a["unresolved_manual_review"], 0)
        self.assertEqual(self.recorder.store.audit_restart()["by_status"], {
            "RECORDED_COMPLETE": 1,
            "PROVIDER_ERROR": 1,
            "BLOCKED_DEPENDENCY": 1,
        })

    def test_invalid_c_json_is_not_repaired_and_k_is_blocked(self):
        self.claim("D")
        self.d()
        self.claim("C")
        self.c("INVALID C JSON")
        self.k(None)
        self.assertEqual(
            self.recorder.store.load_discovery_stage(
                stage_id=self.sid("C")
            )["artifact"]["raw_response"], "INVALID C JSON",
        )
        self.assertEqual(self.journal.audit_restart()["claims"], 2)

    def test_invalid_d_task_json_can_still_supply_observations(self):
        self.claim("D")
        self.d(raw_response="not task JSON",
               json_status="invalid_json: synthetic")
        self.claim("C")
        self.c("DEFAULT")
        c = self.recorder.store.load_discovery_stage(stage_id=self.sid("C"))
        self.assertEqual(c["status"], "RECORDED_COMPLETE")
        self.assertNotIn("not task JSON", json.dumps(c["artifact"]))

    def test_k_insufficient_evidence_is_a_valid_completed_stage(self):
        k = output_fixtures.RQ2OutputContractsTests.rule()
        k.update({
            "status": "insufficient_evidence",
            "rule_name": None, "hypothesized_fault_type": None,
            "combination": None, "pseudocode": None,
            "required_signals": [], "conditions": [],
        })
        self.claim("D")
        self.d()
        self.claim("C")
        self.c("DEFAULT")
        self.claim("K")
        self.k(json.dumps(k))
        rec = self.recorder.store.load_discovery_stage(stage_id=self.sid("K"))
        self.assertEqual(rec["status"], "RECORDED_COMPLETE")
        self.assertEqual(rec["artifact"]["preflight_status"],
                         "insufficient_evidence")
        self.assertFalse(rec["artifact"]["scientific_freeze"])

    def test_c_cannot_be_claimed_without_d_record(self):
        with self.assertRaises(claims.RQ2ClaimError):
            self.claim("C")
        self.assertFalse(self.journal.root.exists())

    def test_k_cannot_be_claimed_without_valid_c_record(self):
        self.claim("D")
        self.d()
        with self.assertRaises(claims.RQ2ClaimError):
            self.claim("K")
        self.assertEqual(self.journal.audit_restart()["claims"], 1)

    def test_unknown_model_cannot_claim_or_record_d(self):
        with self.assertRaises(claims.RQ2ClaimError):
            self.claim("D", model="gemini-synthetic")
        self.assertFalse(self.journal.root.exists())
        with self.assertRaises(recorder.RQ2RecorderError):
            self.recorder.record_d(
                stage_id=self.sid("D"),
                model_id_proposed="claude-sonnet-wrong-version",
                diagnostic_run=self.diagnostic(),
            )

    def test_test_phase_cannot_claim_even_with_unlimited_budget(self):
        test_sid = (
            "rq2_dryrun_workflow_preview_v0:"
            "cloudbed-1_q000:sonnet:A1:D"
        )
        with self.assertRaisesRegex(claims.RQ2ClaimError, "TEST stage"):
            self.journal.claim_stage(
                stage_id=test_sid, model_id_proposed=MODEL,
            )
        self.assertFalse(self.journal.root.exists())

    def test_corrupt_claim_blocks_later_stages_before_any_write(self):
        self.claim("D")
        self.d()
        path = next(self.journal.root.glob("*.json"))
        path.write_bytes(b"{corrupt")
        with self.assertRaises(claims.RQ2ClaimError):
            self.claim("C")
        self.assertEqual(len(list(self.recorder.store.root.glob("*.json"))), 1)

    def test_source_mutation_refuses_claim_after_restart(self):
        self.claim("D")
        self.d()
        self.manifest.write_bytes(self.manifest.read_bytes() + b"\n")
        with self.assertRaises(storage.RQ2ArtifactStoreError):
            self.claim("C")
        self.assertEqual(len(list(self.journal.root.glob("*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
