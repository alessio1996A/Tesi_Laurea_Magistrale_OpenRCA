"""Test offline dello store/journal V2 separati dalla V1.

SOLO TemporaryDirectory e marker sintetico; nessun file Market,
provider API, ground truth o data_dir della tesi.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.rq2_v2_artifact_store import (
    MARKER, MARKER_BYTES, RQ2V2StoreError,
    RQ2V2SyntheticArtifactStore,
)
from evaluation.rq2_v2_claim_journal import (
    RQ2V2ClaimError, RQ2V2SyntheticClaimJournal,
)
from evaluation.rq2_v2_isolation_policy import (
    CLAIMS_RELATIVE, DRAFT_PROTOCOL, preview_v2_destination,
)

MODEL = "claude-sonnet-5-5"
TOOL = "tool_get_node_metrics"


def stage_id(stage="D", *, case="cloudbed-1_q032", model="sonnet"):
    return f"{DRAFT_PROTOCOL}:{case}:{model}:A1:{stage}"


def diagnostic(*, valid=True):
    events = [
        {"tipo": "tool_call", "nome": TOOL,
         "parametri": {"cmdb_id": "A"}},
        {"tipo": "tool_call", "nome": TOOL,
         "parametri": {"cmdb_id": "B"}},
        {"tipo": "tool_result", "nome": TOOL,
         "risposta": "synthetic metric A"},
        {"tipo": "tool_result", "nome": TOOL,
         "risposta": "synthetic metric B"},
    ]
    if valid:
        for item, ref in zip(events, ("id-A", "id-B", "id-A", "id-B")):
            item["tool_call_id"] = ref
    return {"error": None, "raw_response": '{"1":{"synthetic":"only"}}',
            "tool_trajectory": events, "model": MODEL}


def cause():
    return json.dumps({
        "schema_version": "rq2_cause_probe_v0",
        "decision": "diagnosis",
        "predicted_fault_type": "synthetic fault",
        "predicted_component": "node-A",
        "confidence": "low",
        "evidence_ids": ["E001"],
        "alternatives": [],
        "limitations": ["Synthetic observations are not ground truth"],
    })


def rule():
    return json.dumps({
        "schema_version": "rq2_candidate_rule_v0",
        "status": "candidate",
        "hypothesized_fault_type": "synthetic fault",
        "rule_name": "synthetic example",
        "scope": "synthetic node",
        "evidence_ids": ["E001"],
        "required_signals": [
            {"metric": "synthetic.metric", "unit": "units",
             "aggregation": "max", "window_seconds": 300},
        ],
        "conditions": [
            {"metric": "synthetic.metric", "operator": ">",
             "threshold": 1.0, "unit": "units",
             "aggregation": "max", "window_seconds": 300},
        ],
        "combination": "all",
        "abstain_when": ["measurement missing"],
        "counterexamples": ["measurement from other node"],
        "limitations": ["synthetic only; units unverified"],
        "pseudocode": "IF synthetic_metric > 1 THEN propose",
    })


class RQ2V2SyntheticLedgerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / MARKER).write_bytes(MARKER_BYTES)
        self.journal = RQ2V2SyntheticClaimJournal(data_dir=self.root)

    def _record_d(self, *, valid=True, status="RECORDED_COMPLETE"):
        claim = self.journal.claim_stage(stage_id=stage_id("D"), model_id=MODEL)
        record = self.journal.record_stage(
            stage_id=stage_id("D"), model_id=MODEL,
            status=status, artifact={"diagnostic_run": diagnostic(valid=valid)},
        )
        self.assertEqual(claim["status"], "CLAIM_WITHOUT_ARTIFACT")
        return record

    def _record_complete_triplet(self):
        self._record_d()
        for stage, raw in (("C", cause()), ("K", rule())):
            self.journal.claim_stage(stage_id=stage_id(stage), model_id=MODEL)
            self.journal.record_stage(
                stage_id=stage_id(stage), model_id=MODEL,
                status="RECORDED_COMPLETE",
                artifact={"raw_response": raw},
            )

    def test_complete_dck_records_and_claims_are_separate_and_auditable(self):
        self._record_complete_triplet()
        restart = RQ2V2SyntheticClaimJournal(data_dir=self.root).audit_restart()
        self.assertEqual(restart["claims"], 3)
        self.assertEqual(restart["finished_with_matching_result"], 3)
        self.assertEqual(restart["stored_stage_records"], 3)
        self.assertEqual(restart["unresolved_manual_review"], 0)
        self.assertFalse(restart["can_execute_api"])
        self.assertFalse(restart["can_execute_test"])
        self.assertFalse(restart["automatic_retry_allowed"])
        self.assertFalse((self.root / "data/rq2").exists())
        self.assertFalse((self.root / "data/results").exists())
        d = self.journal.store.load(stage_id=stage_id("D"))
        c = self.journal.store.load(stage_id=stage_id("C"))
        k = self.journal.store.load(stage_id=stage_id("K"))
        self.assertEqual(c["dependencies"], {stage_id("D"): d["record_sha256"]})
        self.assertEqual(k["dependencies"], {stage_id("C"): c["record_sha256"]})

    def test_parallel_without_ids_invalid_d_blocks_c_k_without_claim(self):
        self._record_d(valid=False, status="INVALID_OUTPUT")
        with self.assertRaises(RQ2V2ClaimError):
            self.journal.claim_stage(stage_id=stage_id("C"), model_id=MODEL)
        for stage in ("C", "K"):
            self.journal.record_stage(
                stage_id=stage_id(stage), model_id=MODEL,
                status="BLOCKED_DEPENDENCY", artifact={},
            )
            self.assertIsNone(self.journal.load_claim(stage_id=stage_id(stage)))
        audit = self.journal.audit_restart()
        self.assertEqual(audit["claims"], 1)
        self.assertEqual(audit["stored_stage_records"], 3)
        self.assertEqual(audit["finished_with_matching_result"], 1)

    def test_claim_without_result_survives_restart_and_refuses_retry(self):
        self.journal.claim_stage(stage_id=stage_id("D"), model_id=MODEL)
        restarted = RQ2V2SyntheticClaimJournal(data_dir=self.root)
        self.assertEqual(restarted.audit_restart()["unresolved_manual_review"], 1)
        with self.assertRaisesRegex(RQ2V2ClaimError, "NEVER auto retry"):
            restarted.claim_stage(stage_id=stage_id("D"), model_id=MODEL)
        self.assertEqual(restarted.audit_restart()["stored_stage_records"], 0)

    def test_duplicate_record_and_second_claim_are_refused(self):
        self._record_d()
        with self.assertRaises(RQ2V2ClaimError):
            self.journal.claim_stage(stage_id=stage_id("D"), model_id=MODEL)
        with self.assertRaises(RQ2V2StoreError):
            self.journal.record_stage(
                stage_id=stage_id("D"), model_id=MODEL,
                status="RECORDED_COMPLETE",
                artifact={"diagnostic_run": diagnostic()},
            )
        self.assertEqual(self.journal.audit_restart()["claims"], 1)

    def test_invalid_c_blocks_k_without_provider_claim(self):
        self._record_d()
        self.journal.claim_stage(stage_id=stage_id("C"), model_id=MODEL)
        self.journal.record_stage(
            stage_id=stage_id("C"), model_id=MODEL,
            status="INVALID_OUTPUT", artifact={"raw_response": "{broken"},
        )
        with self.assertRaises(RQ2V2ClaimError):
            self.journal.claim_stage(stage_id=stage_id("K"), model_id=MODEL)
        self.journal.record_stage(
            stage_id=stage_id("K"), model_id=MODEL,
            status="BLOCKED_DEPENDENCY", artifact={},
        )
        report = self.journal.audit_restart()
        self.assertEqual(report["claims"], 2)
        self.assertEqual(report["stored_stage_records"], 3)

    def test_complete_d_with_ambiguous_tool_trace_rejected(self):
        self.journal.claim_stage(stage_id=stage_id("D"), model_id=MODEL)
        with self.assertRaisesRegex(RQ2V2StoreError, "provenance"):
            self.journal.record_stage(
                stage_id=stage_id("D"), model_id=MODEL,
                status="RECORDED_COMPLETE",
                artifact={"diagnostic_run": diagnostic(valid=False)},
            )
        self.assertEqual(self.journal.audit_restart()["unresolved_manual_review"], 1)

    def test_forbidden_gt_field_rejected_without_result(self):
        self.journal.claim_stage(stage_id=stage_id("D"), model_id=MODEL)
        with self.assertRaisesRegex(RQ2V2StoreError, "scoring/GT"):
            self.journal.record_stage(
                stage_id=stage_id("D"), model_id=MODEL,
                status="RECORDED_COMPLETE",
                artifact={"diagnostic_run": diagnostic(),
                          "ground_truth": "NOT ALLOWED"},
            )
        self.assertEqual(self.journal.audit_restart()["unresolved_manual_review"], 1)

    def test_corrupt_existing_record_blocks_restart(self):
        self._record_d()
        destination = preview_v2_destination(
            data_dir=self.root, stage_id=stage_id("D")
        )
        p = Path(destination["artifact_path_preview"])
        p.write_bytes(b"{}")
        with self.assertRaises(RQ2V2StoreError):
            RQ2V2SyntheticClaimJournal(data_dir=self.root)
        # Il file corrotto non e' stato automaticamente cancellato.
        self.assertEqual(p.read_bytes(), b"{}")

    def test_no_synthetic_marker_or_real_v1_path_is_refused(self):
        (self.root / MARKER).unlink()
        with self.assertRaisesRegex(RQ2V2StoreError, "marker"):
            RQ2V2SyntheticClaimJournal(data_dir=self.root)
        (self.root / MARKER).write_bytes(MARKER_BYTES)
        (self.root / "data/rq2").mkdir(parents=True, exist_ok=True)
        with self.assertRaisesRegex(RQ2V2StoreError, "Real benchmark"):
            RQ2V2SyntheticClaimJournal(data_dir=self.root)

    def test_ood_test_case_stage_cannot_be_claimed(self):
        with self.assertRaisesRegex(RQ2V2ClaimError, "locked"):
            self.journal.claim_stage(
                stage_id=stage_id("D", case="cloudbed-1_q014"),
                model_id=MODEL,
            )
        self.assertEqual(self.journal.audit_restart()["claims"], 0)

    def test_symlink_namespace_rejected_without_following(self):
        target = self.root / CLAIMS_RELATIVE
        original = Path.is_symlink
        def fake_is_symlink(path):
            return path == target or original(path)
        with patch.object(Path, "is_symlink", fake_is_symlink):
            with self.assertRaisesRegex(RQ2V2StoreError, "Symlink"):
                self.journal.claim_stage(stage_id=stage_id("D"), model_id=MODEL)
        self.assertFalse(target.exists())

    def test_d_invalid_status_with_valid_provenance_is_refused(self):
        self.journal.claim_stage(stage_id=stage_id("D"), model_id=MODEL)
        with self.assertRaisesRegex(RQ2V2StoreError, "status/provenance"):
            self.journal.record_stage(
                stage_id=stage_id("D"), model_id=MODEL,
                status="INVALID_OUTPUT",
                artifact={"diagnostic_run": diagnostic(valid=True)},
            )
        self.assertEqual(self.journal.audit_restart()["unresolved_manual_review"], 1)

    def test_c_complete_status_with_invalid_json_is_refused(self):
        self._record_d()
        self.journal.claim_stage(stage_id=stage_id("C"), model_id=MODEL)
        with self.assertRaisesRegex(RQ2V2StoreError, "status/contract"):
            self.journal.record_stage(
                stage_id=stage_id("C"), model_id=MODEL,
                status="RECORDED_COMPLETE", artifact={"raw_response": "{broken"},
            )
        self.assertEqual(self.journal.audit_restart()["unresolved_manual_review"], 1)

    def test_d_provider_error_is_preserved_and_blocks_children(self):
        self.journal.claim_stage(stage_id=stage_id("D"), model_id=MODEL)
        run = diagnostic()
        run["error"] = "synthetic upstream 503"
        self.journal.record_stage(
            stage_id=stage_id("D"), model_id=MODEL,
            status="PROVIDER_ERROR", artifact={"diagnostic_run": run},
        )
        for stage in ("C", "K"):
            self.journal.record_stage(
                stage_id=stage_id(stage), model_id=MODEL,
                status="BLOCKED_DEPENDENCY", artifact={},
            )
        audit = self.journal.audit_restart()
        self.assertEqual(audit["claims"], 1)
        self.assertEqual(audit["stored_stage_records"], 3)
        self.assertEqual(audit["unresolved_manual_review"], 0)

    def test_c_provider_error_requires_error_text_and_blocks_k(self):
        self._record_d()
        self.journal.claim_stage(stage_id=stage_id("C"), model_id=MODEL)
        with self.assertRaisesRegex(RQ2V2StoreError, "Provider failure"):
            self.journal.record_stage(
                stage_id=stage_id("C"), model_id=MODEL,
                status="PROVIDER_ERROR", artifact={"raw_response": None},
            )
        self.journal.record_stage(
            stage_id=stage_id("C"), model_id=MODEL,
            status="PROVIDER_ERROR",
            artifact={"raw_response": None, "provider_error": "synthetic timeout"},
        )
        self.journal.record_stage(
            stage_id=stage_id("K"), model_id=MODEL,
            status="BLOCKED_DEPENDENCY", artifact={},
        )
        audit = self.journal.audit_restart()
        self.assertEqual(audit["claims"], 2)
        self.assertEqual(audit["stored_stage_records"], 3)
        self.assertEqual(audit["unresolved_manual_review"], 0)

    def test_claim_model_mismatch_rejected_without_files(self):
        with self.assertRaisesRegex(RQ2V2ClaimError, "model"):
            self.journal.claim_stage(
                stage_id=stage_id("D"), model_id="claude-haiku-5-5",
            )
        self.assertFalse((self.root / CLAIMS_RELATIVE).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
