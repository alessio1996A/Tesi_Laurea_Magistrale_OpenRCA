"""G3A: journal RQ2-V2 comune ai 15 arm, solo TemporaryDirectory.

Non chiama SDK, Market, real source, scorer, GT. Le risposte JSON sono
fixture costruite qui per validare contratti e invarianti, non diagnosi.
"""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.rq2_v2_artifact_store import (
    MARKER, MARKER_BYTES, RQ2V2StoreError, read_canonical,
)
from evaluation.rq2_v2_unified_discovery_plan import (
    DISCOVERY, HARNESSES, MODELS, TEST, VERSION,
    build_offline_discovery_plan,
)
from evaluation.rq2_v2_unified_synthetic_journal import (
    UnifiedRQ2JournalError, UnifiedRQ2SyntheticJournal,
    _stage_path, CLAIMS, RECORDS,
)
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS


def sid(model="gemini", harness="A0", stage="D", case_id=None):
    return f"{VERSION}:{case_id or DISCOVERY[0]}:{model}:{harness}:{stage}"


def model_id(model):
    return CANDIDATE_MODELS[model]["model_id"]


def fake_run(model="gemini", harness="A0", *, json_valid=True):
    # Il grafo verify_graph emette sempre una provenienza esplicita:
    # queste fixture devono rispettarne lo stesso contratto tecnico.
    run = {
        "case_id": DISCOVERY[0],
        "variant": harness,
        "variant_scheme": "current",
        "model": model_id(model),
        "model_provider": CANDIDATE_MODELS[model]["provider"],
        "output_contract_mode": "v2_enforce",
        "max_tool_rounds": 6,
        "json_status": "valid_json" if json_valid else "invalid_v2_task_output",
        "raw_response": (
            json.dumps({"1": {
                "root cause occurrence datetime": "1970-01-01 00:20:00",
                "root cause component": "synthetic-node-1",
                "root cause reason": "synthetic hypothesis, not GT",
            }}) if json_valid else "INVALID SYNTHETIC JSON"
        ),
        "output_contract_v2": {"valid": json_valid},
        "error": None,
        "metrics": {"token_usage_complete": True},
        "tool_trajectory": [
            {"tipo": "tool_call", "nome": "tool_get_node_metrics",
             "parametri": {"cmdb_id": "synthetic-node-1"},
             "tool_call_id": "synthetic-1"},
            {"tipo": "tool_result", "nome": "tool_get_node_metrics",
             "risposta": "synthetic metric value 3",
             "tool_call_id": "synthetic-1"},
        ],
    }
    if harness in ("A1_8R_Planning", "A1_PAVE"):
        for event in run["tool_trajectory"]:
            event["origine"] = "llm"
    return run


def cause(*, invalid_ref=False, abstain=False):
    return json.dumps({
        "schema_version": "rq2_cause_probe_v0",
        "decision": "abstain" if abstain else "diagnosis",
        "predicted_fault_type": None if abstain else "synthetic hypothetical fault",
        "predicted_component": None if abstain else "synthetic-node-1",
        "confidence": "unassessed" if abstain else "low",
        "evidence_ids": ["E999"] if invalid_ref else (
            [] if abstain else ["E001"]
        ),
        "alternatives": [],
        "limitations": ["No empirical verification"],
    })


def rule(*, insufficient=False):
    return json.dumps({
        "schema_version": "rq2_candidate_rule_v0",
        "status": "insufficient_evidence" if insufficient else "candidate",
        "hypothesized_fault_type": (
            None if insufficient else "synthetic hypothetical fault"
        ),
        "rule_name": None if insufficient else "synthetic_rule",
        "scope": None if insufficient else "synthetic-node-1",
        "evidence_ids": [] if insufficient else ["E001"],
        "required_signals": [] if insufficient else [
            {"metric": "synthetic.metric", "unit": "count",
             "aggregation": "max", "window_seconds": 60},
        ],
        "conditions": [] if insufficient else [
            {"metric": "synthetic.metric", "unit": "count",
             "aggregation": "max", "window_seconds": 60,
             "operator": ">", "threshold": 1.0},
        ],
        "combination": None if insufficient else "all",
        "abstain_when": ["Unverified completeness"],
        "counterexamples": ["Unrelated synthetic anomaly"],
        "limitations": ["This is only a fixture"],
        "pseudocode": None if insufficient else "IF synthetic > 1 THEN candidate",
    })


class UnifiedJournalG3Tests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        (self.root / MARKER).write_bytes(MARKER_BYTES)
        self.journal = UnifiedRQ2SyntheticJournal(data_dir=self.root)

    def save_d(self, *, model="gemini", harness="A0",
               status="RECORDED_COMPLETE", run=None):
        stage_id = sid(model, harness, "D")
        self.journal.claim_stage(stage_id=stage_id, model_id=model_id(model))
        if status == "PROVIDER_ERROR":
            artifact = {"provider_error": "synthetic HTTP 503"}
        else:
            artifact = {"diagnostic_run": run or fake_run(model, harness)}
        return self.journal.record_stage(
            stage_id=stage_id, model_id=model_id(model),
            status=status, artifact=artifact,
        )

    def save_c(self, *, model="gemini", harness="A0",
               status="RECORDED_COMPLETE", raw=None):
        stage_id = sid(model, harness, "C")
        self.journal.claim_stage(stage_id=stage_id, model_id=model_id(model))
        return self.journal.record_stage(
            stage_id=stage_id, model_id=model_id(model),
            status=status, artifact={"raw_response": cause() if raw is None else raw},
        )

    def save_k(self, *, model="gemini", harness="A0",
               status="RECORDED_COMPLETE", raw=None):
        stage_id = sid(model, harness, "K")
        self.journal.claim_stage(stage_id=stage_id, model_id=model_id(model))
        return self.journal.record_stage(
            stage_id=stage_id, model_id=model_id(model),
            status=status, artifact={"raw_response": rule() if raw is None else raw},
        )

    def test_constructor_is_read_only(self):
        self.assertEqual(
            sorted(p.name for p in self.root.iterdir()), [MARKER]
        )
        report = self.journal.audit_restart()
        self.assertEqual(report["claims"], 0)
        self.assertEqual(report["stored_stage_records"], 0)
        self.assertFalse(report["can_execute_api"])

    def test_all_15_arm_dck_claims_and_restart(self):
        n = 0
        for model in MODELS:
            for harness in HARNESSES:
                with self.subTest(model=model, harness=harness):
                    self.save_d(model=model, harness=harness)
                    self.save_c(model=model, harness=harness)
                    self.save_k(model=model, harness=harness)
                    n += 3
        self.assertEqual(n, 45)
        audit = UnifiedRQ2SyntheticJournal(data_dir=self.root).audit_restart()
        self.assertEqual(audit["claims"], 45)
        self.assertEqual(audit["stored_stage_records"], 45)
        self.assertEqual(audit["matched_claim_records"], 45)
        self.assertEqual(audit["unresolved_claims_for_manual_review"], 0)
        self.assertFalse(audit["can_execute_api"])
        self.assertFalse(audit["can_access_market"])
        self.assertFalse(audit["can_run_ood_test"])
        self.assertFalse(audit["automatic_retry_allowed"])
        self.assertFalse((self.root / "data/rq2").exists())
        self.assertFalse((self.root / "data/results").exists())
        self.assertFalse((self.root / "Market.zip").exists())

    def test_planning_missing_origin_is_rejected_fail_closed(self):
        # Il controllo deve continuare a rifiutare dati privi di origine,
        # non attribuire automaticamente un tool al modello/planner.
        for harness in ("A1_8R_Planning", "A1_PAVE"):
            with self.subTest(harness=harness):
                stage_id = sid(harness=harness)
                run = fake_run(harness=harness)
                for event in run["tool_trajectory"]:
                    event.pop("origine")
                self.journal.claim_stage(
                    stage_id=stage_id, model_id=model_id("gemini"),
                )
                with self.assertRaisesRegex(
                    UnifiedRQ2JournalError, "D status/provenance/output mismatch"
                ):
                    self.journal.record_stage(
                        stage_id=stage_id,
                        model_id=model_id("gemini"),
                        status="RECORDED_COMPLETE",
                        artifact={"diagnostic_run": run},
                    )
        report = self.journal.audit_restart()
        self.assertEqual(report["claims"], 2)
        self.assertEqual(report["stored_stage_records"], 0)
        self.assertEqual(report["unresolved_claims_for_manual_review"], 2)

    def test_audit_reads_each_stored_file_bounded_times(self):
        # Regressione prestazionale strutturale: NO soglia temporale flaky.
        # Tre stage per un arm producono esattamente sei file (claim/record);
        # l'audit deve convalidarli tutti senza rileggerli ricorsivamente.
        self.save_d()
        self.save_c()
        self.save_k()
        with patch(
            "evaluation.rq2_v2_unified_synthetic_journal.read_canonical",
            wraps=read_canonical,
        ) as reader:
            audit = self.journal.audit_restart()
        self.assertEqual(audit["claims"], 3)
        self.assertEqual(audit["stored_stage_records"], 3)
        self.assertLessEqual(reader.call_count, 18)

    def test_new_audit_detects_disk_corruption_after_previous_pass(self):
        # La memoization e' locale al singolo audit: mai oltre il confine
        # di una operazione o di un riavvio.
        self.save_d()
        self.save_c()
        self.save_k()
        self.assertEqual(self.journal.audit_restart()["matched_claim_records"], 3)
        path = _stage_path(self.root, sid(stage="D"), RECORDS, "V2U_RECORD_")
        original = path.read_bytes()
        self.assertIn(b"synthetic", original)
        path.write_bytes(original.replace(b"synthetic", b"tampered", 1))
        with self.assertRaises(UnifiedRQ2JournalError):
            self.journal.audit_restart()

    def test_new_audit_detects_claim_corruption_after_previous_pass(self):
        self.save_d()
        self.assertEqual(self.journal.audit_restart()["matched_claim_records"], 1)
        path = _stage_path(self.root, sid(), CLAIMS, "V2U_CLAIM_")
        original = path.read_bytes()
        self.assertIn(b"SYNTHETIC_NO_API_AUTHORITY", original)
        path.write_bytes(original.replace(
            b"SYNTHETIC_NO_API_AUTHORITY", b"FORGED_API_AUTHORITY", 1,
        ))
        with self.assertRaises(UnifiedRQ2JournalError):
            self.journal.audit_restart()

    def test_ood_stage_is_rejected(self):
        with self.assertRaises(UnifiedRQ2JournalError):
            self.journal.claim_stage(
                stage_id=sid(case_id=TEST[0]), model_id=model_id("gemini"),
            )

    def test_wrong_model_id_is_rejected_without_claim(self):
        with self.assertRaisesRegex(UnifiedRQ2JournalError, "model ID"):
            self.journal.claim_stage(
                stage_id=sid("sonnet"), model_id=model_id("haiku"),
            )
        self.assertEqual(self.journal.audit_restart()["claims"], 0)

    def test_c_and_k_cannot_claim_without_complete_parent(self):
        for stage in ("C", "K"):
            with self.subTest(stage=stage):
                with self.assertRaises(UnifiedRQ2JournalError):
                    self.journal.claim_stage(
                        stage_id=sid(stage=stage), model_id=model_id("gemini"),
                    )
        self.assertEqual(self.journal.audit_restart()["claims"], 0)

    def test_orphan_claim_stays_unresolved_and_never_retried(self):
        stage_id = sid()
        self.journal.claim_stage(stage_id=stage_id, model_id=model_id("gemini"))
        fresh = UnifiedRQ2SyntheticJournal(data_dir=self.root)
        self.assertEqual(
            fresh.audit_restart()["unresolved_claims_for_manual_review"], 1
        )
        with self.assertRaisesRegex(UnifiedRQ2JournalError, "never auto retry"):
            fresh.claim_stage(stage_id=stage_id, model_id=model_id("gemini"))
        self.assertIsNone(fresh.load_record(stage_id=stage_id))

    def test_failure_in_d_blocks_c_and_k_without_claims(self):
        self.save_d(status="PROVIDER_ERROR")
        for stage in ("C", "K"):
            self.journal.record_stage(
                stage_id=sid(stage=stage), model_id=model_id("gemini"),
                status="BLOCKED_DEPENDENCY", artifact={},
            )
        out = self.journal.audit_restart()
        self.assertEqual(out["claims"], 1)
        self.assertEqual(out["stored_stage_records"], 3)
        self.assertEqual(out["unresolved_claims_for_manual_review"], 0)
        self.assertIsNone(self.journal.load_claim(stage_id=sid(stage="C")))
        self.assertIsNone(self.journal.load_claim(stage_id=sid(stage="K")))

    def test_invalid_d_json_blocks_dependent_stages(self):
        self.save_d(status="INVALID_OUTPUT", run=fake_run(json_valid=False))
        for stage in ("C", "K"):
            self.journal.record_stage(
                stage_id=sid(stage=stage), model_id=model_id("gemini"),
                status="BLOCKED_DEPENDENCY", artifact={},
            )
        self.assertEqual(self.journal.audit_restart()["stored_stage_records"], 3)

    def test_invalid_c_reference_blocks_k(self):
        self.save_d()
        self.save_c(status="INVALID_OUTPUT", raw=cause(invalid_ref=True))
        self.journal.record_stage(
            stage_id=sid(stage="K"), model_id=model_id("gemini"),
            status="BLOCKED_DEPENDENCY", artifact={},
        )
        self.assertEqual(
            self.journal.load_record(stage_id=sid(stage="C"))["status"],
            "INVALID_OUTPUT",
        )
        self.assertEqual(self.journal.audit_restart()["stored_stage_records"], 3)

    def test_valid_c_abstention_and_k_insufficient_are_recorded(self):
        self.save_d()
        self.save_c(raw=cause(abstain=True))
        self.save_k(raw=rule(insufficient=True))
        self.assertEqual(
            self.journal.load_record(stage_id=sid(stage="K"))["status"],
            "RECORDED_COMPLETE",
        )
        self.assertEqual(self.journal.audit_restart()["claims"], 3)

    def test_repeat_claim_or_result_is_rejected(self):
        self.save_d()
        with self.assertRaises(UnifiedRQ2JournalError):
            self.journal.claim_stage(stage_id=sid(), model_id=model_id("gemini"))
        with self.assertRaises(UnifiedRQ2JournalError):
            self.journal.record_stage(
                stage_id=sid(), model_id=model_id("gemini"),
                status="RECORDED_COMPLETE",
                artifact={"diagnostic_run": fake_run()},
            )

    def test_inconsistent_status_is_not_stored(self):
        self.journal.claim_stage(stage_id=sid(), model_id=model_id("gemini"))
        with self.assertRaisesRegex(UnifiedRQ2JournalError, "status"):
            self.journal.record_stage(
                stage_id=sid(), model_id=model_id("gemini"),
                status="RECORDED_COMPLETE",
                artifact={"diagnostic_run": fake_run(json_valid=False)},
            )
        self.assertEqual(
            self.journal.audit_restart()["unresolved_claims_for_manual_review"], 1
        )

    def test_forged_gt_key_fails_closed(self):
        self.journal.claim_stage(stage_id=sid(), model_id=model_id("gemini"))
        run = fake_run()
        run["ground_truth"] = "MUST NOT PERSIST"
        with self.assertRaises(UnifiedRQ2JournalError):
            self.journal.record_stage(
                stage_id=sid(), model_id=model_id("gemini"),
                status="RECORDED_COMPLETE",
                artifact={"diagnostic_run": run},
            )
        self.assertFalse((self.root / RECORDS).exists())

    def test_corrupted_record_prevents_restart(self):
        self.save_d()
        path = _stage_path(self.root, sid(), RECORDS, "V2U_RECORD_")
        raw = path.read_bytes()
        path.write_bytes(raw.replace(b"synthetic", b"forged", 1))
        with self.assertRaises(UnifiedRQ2JournalError):
            UnifiedRQ2SyntheticJournal(data_dir=self.root)

    def test_real_market_root_is_rejected(self):
        (self.root / "Market.zip").write_bytes(b"not the real archive")
        with self.assertRaises(RQ2V2StoreError):
            UnifiedRQ2SyntheticJournal(data_dir=self.root)

    def test_write_failure_preserves_claim_and_no_retry(self):
        self.journal.claim_stage(stage_id=sid(), model_id=model_id("gemini"))
        with patch(
            "evaluation.rq2_v2_unified_synthetic_journal.write_exclusive",
            side_effect=RQ2V2StoreError("simulated write failure"),
        ):
            with self.assertRaises(UnifiedRQ2JournalError):
                self.journal.record_stage(
                    stage_id=sid(), model_id=model_id("gemini"),
                    status="RECORDED_COMPLETE",
                    artifact={"diagnostic_run": fake_run()},
                )
        self.assertEqual(
            self.journal.audit_restart()["unresolved_claims_for_manual_review"], 1
        )
        with self.assertRaises(UnifiedRQ2JournalError):
            self.journal.claim_stage(stage_id=sid(), model_id=model_id("gemini"))

    def test_cannot_claim_blocked_stage_after_invalid_parent(self):
        self.save_d(status="PROVIDER_ERROR")
        with self.assertRaises(UnifiedRQ2JournalError):
            self.journal.claim_stage(
                stage_id=sid(stage="C"), model_id=model_id("gemini"),
            )

    def test_mismatched_invalid_c_cannot_be_reported_complete(self):
        self.save_d()
        self.journal.claim_stage(
            stage_id=sid(stage="C"), model_id=model_id("gemini"),
        )
        with self.assertRaisesRegex(UnifiedRQ2JournalError, "status"):
            self.journal.record_stage(
                stage_id=sid(stage="C"), model_id=model_id("gemini"),
                status="RECORDED_COMPLETE", artifact={"raw_response": "bad-json"},
            )
        self.assertEqual(
            self.journal.audit_restart()["unresolved_claims_for_manual_review"], 1
        )

    def test_blocked_stage_cannot_have_provider_claim(self):
        self.save_d()
        self.save_c(status="INVALID_OUTPUT", raw="bad-json")
        self.journal.record_stage(
            stage_id=sid(stage="K"), model_id=model_id("gemini"),
            status="BLOCKED_DEPENDENCY", artifact={},
        )
        with self.assertRaises(UnifiedRQ2JournalError):
            self.journal.claim_stage(
                stage_id=sid(stage="K"), model_id=model_id("gemini"),
            )


if __name__ == "__main__":
    unittest.main()
