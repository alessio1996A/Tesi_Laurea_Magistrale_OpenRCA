"""G4F — Ledger scientifico RQ2-V2 create-only con release FITTIZIA.

Il data_dir e il repository sono esclusivamente TemporaryDirectory.
Le identita' GT-free/source e Git sono simulate, ma il codice vero
del ledger, SHA-256, O_EXCL, lock OS, validatori D/C/K e readback girano
davvero sul filesystem locale. NESSUN SDK, HTTP, Market, GT, Drive o API.

La finta approvazione 'SYNTHETIC_APPROVAL_NOT_REAL' e' costruita qui
per testare lo schema, NON e' una autorizzazione utente.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluation.rq2_v2_unified_scientific_ledger as ledger
from evaluation.rq2_v2_unified_scientific_release_contract import (
    canonical_release, release_digest,
)
from evaluation.rq2_v2_unified_release_blueprint import (
    build_unified_release_blueprint,
)
from evaluation.rq2_v2_unified_discovery_plan import (
    DISCOVERY, HARNESSES, MODELS, TEST, VERSION,
)
from test_rq2_v2_unified_scientific_release_contract_offline import (
    FAKE_COMMIT, release_fixture, source_fixture,
)
from test_rq2_v2_unified_synthetic_journal import (
    fake_run, cause, model_id, rule,
)


def sid(model="gemini", harness="A0", stage="D", case=None):
    return f"{VERSION}:{case or DISCOVERY[0]}:{model}:{harness}:{stage}"


def meter(*, requests=1, usage=True, estimate="0.001000"):
    return {
        "schema": "rq2_v2_unified_stage_meter_v0",
        "observed_model_requests": requests,
        "input_tokens_observed": 125 if requests else 0,
        "output_tokens_observed": 16 if requests else 0,
        "usage_complete": usage,
        "cost_estimate_usd_not_invoice": estimate,
        "usd_hard_cap_guaranteed": False,
    }


class ScientificLedgerFixtureTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory(
            prefix="rq2_v2_release_scientific_ledger_fake_"
        )
        self.addCleanup(td.cleanup)
        self.temp = Path(td.name)
        self.data = self.temp / "DATA_FIXTURE"
        self.repo = self.temp / "REPO_FIXTURE"
        self.data.mkdir()
        (self.repo / "src").mkdir(parents=True)
        self.source = source_fixture()
        self.blueprint = build_unified_release_blueprint(
            source_preview=self.source,
        )
        self.release = release_fixture(self.source, self.blueprint)
        self.approved_sha = release_digest(self.release)
        release_path = self.data / ledger.RELEASE_FILE
        release_path.parent.mkdir(parents=True)
        release_path.write_bytes(canonical_release(self.release))

        git_patch = patch.object(
            ledger, "_repository_commit", return_value=(FAKE_COMMIT, ""),
        )
        source_patch = patch.object(
            ledger, "preview_unified_source_bound",
            return_value=self.source,
        )
        self.addCleanup(git_patch.stop)
        self.addCleanup(source_patch.stop)
        git_patch.start()
        source_patch.start()
        self.j = self.new_ledger()

    def new_ledger(self):
        return ledger.UnifiedScientificLedger(
            data_dir=self.data, repo_dir=self.repo,
            expected_commit=FAKE_COMMIT,
            approved_release_sha256=self.approved_sha,
        )

    def save_d(self, model="gemini", harness="A0", *,
               status="RECORDED_COMPLETE", run=None):
        stage_id = sid(model, harness, "D")
        self.j.claim_stage(stage_id=stage_id, model_id=model_id(model))
        if status == "PROVIDER_ERROR":
            artifact = {
                "provider_error": "synthetic provider transport failure",
                "stage_meter": meter(requests=0, usage=False, estimate="UNKNOWN"),
            }
        else:
            artifact = {
                "diagnostic_run": run or fake_run(model, harness),
                "stage_meter": meter(),
            }
        return self.j.record_stage(
            stage_id=stage_id, model_id=model_id(model),
            status=status, artifact=artifact,
        )

    def save_c(self, model="gemini", harness="A0", *,
               status="RECORDED_COMPLETE", raw=None):
        stage_id = sid(model, harness, "C")
        self.j.claim_stage(stage_id=stage_id, model_id=model_id(model))
        return self.j.record_stage(
            stage_id=stage_id, model_id=model_id(model),
            status=status,
            artifact={
                "raw_response": cause() if raw is None else raw,
                "stage_meter": meter(),
            },
        )

    def save_k(self, model="gemini", harness="A0", *,
               status="RECORDED_COMPLETE", raw=None):
        stage_id = sid(model, harness, "K")
        self.j.claim_stage(stage_id=stage_id, model_id=model_id(model))
        return self.j.record_stage(
            stage_id=stage_id, model_id=model_id(model),
            status=status,
            artifact={
                "raw_response": rule() if raw is None else raw,
                "stage_meter": meter(),
            },
        )

    def test_frozen_release_bound_constructor_readonly(self):
        report = self.j.audit_restart()
        self.assertEqual(report["claims"], 0)
        self.assertEqual(report["records"], 0)
        self.assertEqual(report["orphan_claims"], 0)
        self.assertFalse(report["can_execute_api"])
        self.assertFalse(report["can_run_ood_test"])
        self.assertFalse((self.data / ledger.CLAIMS).exists())
        self.assertFalse((self.data / ledger.RECORDS).exists())

    def test_all_fifteen_arms_dck_with_real_sha_and_readback(self):
        n = 0
        for model in MODELS:
            for harness in HARNESSES:
                with self.subTest(model=model, harness=harness):
                    self.save_d(model, harness)
                    self.save_c(model, harness)
                    self.save_k(model, harness)
                    n += 3
        self.assertEqual(n, 45)
        r = self.new_ledger().audit_restart()
        self.assertEqual((r["claims"], r["records"]), (45, 45))
        self.assertEqual(r["orphan_claims"], 0)
        self.assertFalse(r["automatic_retry_allowed"])
        self.assertTrue((self.data / ledger.LOCK_FILE).is_file())
        self.assertFalse((self.data / "Market.zip").exists())
        self.assertFalse((self.data / "data/rq2").exists())
        self.assertFalse((self.data / "data/results").exists())

    def test_ood_case_cannot_be_claimed(self):
        with self.assertRaisesRegex(
            ledger.UnifiedScientificLedgerBlocked, "OOD/unknown"
        ):
            self.j.claim_stage(
                stage_id=sid(case=TEST[0]),
                model_id=model_id("gemini"),
            )

    def test_model_identity_cannot_be_changed(self):
        with self.assertRaises(ledger.UnifiedScientificLedgerBlocked):
            self.j.claim_stage(
                stage_id=sid(model="sonnet"), model_id=model_id("haiku"),
            )

    def test_claim_must_precede_any_attempted_record(self):
        with self.assertRaisesRegex(
            ledger.UnifiedScientificLedgerBlocked, "no claim",
        ):
            self.j.record_stage(
                stage_id=sid(), model_id=model_id("gemini"),
                status="RECORDED_COMPLETE",
                artifact={"diagnostic_run": fake_run(), "stage_meter": meter()},
            )

    def test_orphan_claim_blocks_second_stage_or_retry(self):
        stage = sid()
        self.j.claim_stage(stage_id=stage, model_id=model_id("gemini"))
        again = self.new_ledger()
        self.assertEqual(again.audit_restart()["orphan_claims"], 1)
        with self.assertRaisesRegex(
            ledger.UnifiedScientificLedgerBlocked, "Unresolved claim",
        ):
            again.claim_stage(stage_id=stage, model_id=model_id("gemini"))
        with self.assertRaisesRegex(
            ledger.UnifiedScientificLedgerBlocked, "Unresolved claim",
        ):
            again.claim_stage(
                stage_id=sid(harness="A1"), model_id=model_id("gemini"),
            )
        self.assertIsNone(again.load_record(stage_id=stage))

    def test_completed_d_c_k_do_not_auto_retry(self):
        self.save_d()
        self.save_c()
        self.save_k()
        with self.assertRaises(ledger.UnifiedScientificLedgerBlocked):
            self.j.claim_stage(
                stage_id=sid(), model_id=model_id("gemini"),
            )
        with self.assertRaises(ledger.UnifiedScientificLedgerBlocked):
            self.j.record_stage(
                stage_id=sid(), model_id=model_id("gemini"),
                status="RECORDED_COMPLETE",
                artifact={"diagnostic_run": fake_run(), "stage_meter": meter()},
            )

    def test_pre_request_provider_error_keeps_unknown_cost(self):
        self.save_d(status="PROVIDER_ERROR")
        for stage in ("C", "K"):
            self.j.record_stage(
                stage_id=sid(stage=stage), model_id=model_id("gemini"),
                status="BLOCKED_DEPENDENCY", artifact={},
            )
        audit = self.j.audit_restart()
        self.assertEqual((audit["claims"], audit["records"]), (1, 3))
        m = self.j.load_record(stage_id=sid())["artifact"]["stage_meter"]
        self.assertEqual(m["observed_model_requests"], 0)
        self.assertFalse(m["usage_complete"])
        self.assertEqual(m["cost_estimate_usd_not_invoice"], "UNKNOWN")
        self.assertIsNone(self.j.load_claim(stage_id=sid(stage="C")))
        self.assertIsNone(self.j.load_claim(stage_id=sid(stage="K")))

    def test_invalid_d_output_blocks_c_and_k(self):
        self.save_d(
            status="INVALID_OUTPUT", run=fake_run(json_valid=False),
        )
        for stage in ("C", "K"):
            self.j.record_stage(
                stage_id=sid(stage=stage), model_id=model_id("gemini"),
                status="BLOCKED_DEPENDENCY", artifact={},
            )
        self.assertEqual(self.j.audit_restart()["records"], 3)

    def test_invalid_c_forged_evidence_blocks_k(self):
        self.save_d()
        forged = json.loads(cause())
        forged["evidence_ids"] = ["E999"]
        self.save_c(status="INVALID_OUTPUT", raw=json.dumps(forged))
        self.j.record_stage(
            stage_id=sid(stage="K"), model_id=model_id("gemini"),
            status="BLOCKED_DEPENDENCY", artifact={},
        )
        self.assertEqual(self.j.audit_restart()["records"], 3)

    def test_invalid_k_is_archived_not_repaired(self):
        self.save_d()
        self.save_c()
        forged = json.loads(rule())
        forged["evidence_ids"] = ["E999"]
        self.save_k(status="INVALID_OUTPUT", raw=json.dumps(forged))
        self.assertEqual(
            self.j.load_record(stage_id=sid(stage="K"))["status"],
            "INVALID_OUTPUT",
        )

    def test_abstain_c_and_insufficient_k_are_valid(self):
        self.save_d()
        self.save_c(raw=cause(abstain=True))
        self.save_k(raw=rule(insufficient=True))
        k = self.j.load_record(stage_id=sid(stage="K"))
        self.assertEqual(k["status"], "RECORDED_COMPLETE")
        self.assertEqual(
            json.loads(k["artifact"]["raw_response"])["status"],
            "insufficient_evidence",
        )

    def test_gt_in_d_run_fails_closed_no_record_written(self):
        run = fake_run()
        run["ground_truth"] = "FAKE_LABEL_SHOULD_NOT_APPEAR"
        self.j.claim_stage(stage_id=sid(), model_id=model_id("gemini"))
        with self.assertRaisesRegex(
            ledger.UnifiedScientificLedgerBlocked, "Forbidden GT",
        ):
            self.j.record_stage(
                stage_id=sid(), model_id=model_id("gemini"),
                status="RECORDED_COMPLETE",
                artifact={"diagnostic_run": run, "stage_meter": meter()},
            )
        self.assertEqual(self.j.audit_restart()["orphan_claims"], 1)

    def test_wrong_meter_zero_requests_with_valid_result_rejected(self):
        self.j.claim_stage(stage_id=sid(), model_id=model_id("gemini"))
        with self.assertRaisesRegex(
            ledger.UnifiedScientificLedgerBlocked, "stage meter",
        ):
            self.j.record_stage(
                stage_id=sid(), model_id=model_id("gemini"),
                status="RECORDED_COMPLETE",
                artifact={
                    "diagnostic_run": fake_run(),
                    "stage_meter": meter(requests=0),
                },
            )
        self.assertEqual(self.j.audit_restart()["records"], 0)

    def test_wrong_meter_nan_and_unverified_usage_rejected(self):
        for cost in ("NaN", "Infinity", "-1.00", "garbage"):
            with self.subTest(cost=cost):
                m = meter(estimate=cost)
                with self.assertRaises(ledger.UnifiedScientificLedgerBlocked):
                    ledger._meter(m, allow_zero_requests=False)

    def test_later_audit_detects_tampering_after_success(self):
        self.save_d()
        self.save_c()
        self.save_k()
        self.assertEqual(self.j.audit_restart()["records"], 3)
        p = self.j._path(sid(stage="D"), claim=False)
        data = p.read_bytes()
        self.assertIn(b"synthetic", data)
        p.write_bytes(data.replace(b"synthetic", b"TAMPERED", 1))
        with self.assertRaises(ledger.UnifiedScientificLedgerBlocked):
            self.j.audit_restart()

    def test_release_file_drift_fails_before_new_claim(self):
        self.save_d()
        path = self.data / ledger.RELEASE_FILE
        before = path.read_bytes()
        path.write_bytes(before.replace(
            b"SYNTHETIC_APPROVAL_NOT_REAL",
            b"FORGED_APPROVAL_NOT_REAL", 1,
        ))
        with self.assertRaises(ledger.UnifiedScientificLedgerBlocked):
            self.j.claim_stage(
                stage_id=sid(harness="A1"), model_id=model_id("gemini"),
            )

    def test_dirty_git_or_wrong_commit_blocks_writes(self):
        with patch.object(
            ledger, "_repository_commit",
            return_value=(FAKE_COMMIT, " M src/agent/model_factory.py"),
        ):
            with self.assertRaisesRegex(
                ledger.UnifiedScientificLedgerBlocked, "dirty|Dirty",
            ):
                self.j.claim_stage(
                    stage_id=sid(), model_id=model_id("gemini"),
                )

    def test_missing_release_always_blocks_constructor(self):
        (self.data / ledger.RELEASE_FILE).unlink()
        with self.assertRaises(ledger.UnifiedScientificLedgerBlocked):
            self.new_ledger()

    def test_lock_contention_rejected_without_overwrite(self):
        # Impedisce anche una lock path non sicura: non toccare claim.
        bad = self.data / ledger.LOCK_FILE
        bad.mkdir()
        with self.assertRaisesRegex(
            ledger.UnifiedScientificLedgerBlocked, "lock path",
        ):
            self.j.claim_stage(
                stage_id=sid(), model_id=model_id("gemini"),
            )
        self.assertFalse((self.data / ledger.CLAIMS).exists())

    def test_wrong_scientific_status_never_creates_file(self):
        with self.assertRaises(ledger.UnifiedScientificLedgerBlocked):
            self.j.record_stage(
                stage_id=sid(), model_id=model_id("gemini"),
                status="RUNNING", artifact={},
            )
        self.assertFalse((self.data / ledger.RECORDS).exists())


if __name__ == "__main__":
    unittest.main()
