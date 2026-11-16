"""Test offline del runner a matrice V5: solo libreria standard, nessuna API.

Un esecutore finto sostituisce D/C/K: si verificano archivio create-only,
nessuna riesecuzione, dipendenze D->C->K, orfani, eccezioni, riepilogo e
conformita' strict/tollerante.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evaluation import rq2_v5_matrix_runner as mr

MODEL = "gemini"
CASE = "cloudbed-1_q032"
STEM = f"rq2_v4_task_aware_d_discovery_v0:{CASE}:{MODEL}:A0"


def _row(stage, depends):
    return {
        "stage_id": f"{STEM}:{stage}", "stage": stage, "case_id": CASE,
        "logical_model": MODEL, "model_id": "gemini-3.5-flash-lite",
        "model_provider": "google", "harness": "A0", "d_engine": "react",
        "depends_on": [f"{STEM}:{d}" for d in depends],
    }


def _plan():
    return [_row("D", []), _row("C", ["D"]), _row("K", ["C"])]


class FakeExecutor:
    """Esito deciso dal test; conta le chiamate (nessuna rete)."""

    def __init__(self, outcomes=None, prepare_error=None, run_error=None):
        self.outcomes = outcomes or {}
        self.prepare_error = prepare_error
        self.run_error = run_error
        self.prepared, self.ran = [], []

    def prepare(self, row, parents):
        if self.prepare_error is not None:
            raise self.prepare_error
        self.prepared.append(row["stage"])
        return {"stage": row["stage"], "parents": sorted(parents)}

    def run(self, row, prepared):
        self.ran.append(row["stage"])
        if self.run_error is not None:
            raise self.run_error
        status = self.outcomes.get(row["stage"], mr.STATUS_COMPLETE)
        deviation = self.outcomes.get(row["stage"] + ":dev", "NONE")
        return {
            "status": status,
            "receipt": {"stage_id": row["stage_id"], "status": status},
            "format": {"deviation": deviation},
            "provenance": {"note": "finto"},
        }


class MatrixRunnerOfflineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = mr.StageStore(Path(self._tmp.name) / "v5")
        self.plan = _plan()
        self.logs = []

    def _run(self, executor, rows=None, **kw):
        return mr.run_matrix(
            self.plan if rows is None else rows, plan=self.plan,
            store=self.store, executor=executor, log=self.logs.append, **kw)

    # -- ciclo completo e idempotenza
    def test_full_cycle_records_three_stages(self):
        ex = FakeExecutor()
        out = self._run(ex)
        self.assertEqual(ex.ran, ["D", "C", "K"])
        self.assertEqual(out["executed"], 3)
        for row in self.plan:
            rec = self.store.load_record(row["stage_id"])
            self.assertEqual(rec["status"], mr.STATUS_COMPLETE)
            self.assertIsNotNone(self.store.load_claim(row["stage_id"]))
            self.assertEqual(rec["protocol"], mr.PROTOCOL)

    def test_second_run_never_calls_the_model_again(self):
        self._run(FakeExecutor())
        ex2 = FakeExecutor()
        out = self._run(ex2)
        self.assertEqual(ex2.ran, [])
        self.assertEqual(out["actions"], {mr.ACTION_ALREADY: 3})

    # -- dipendenze
    def test_failed_d_blocks_c_and_k_without_claim_or_call(self):
        ex = FakeExecutor({"D": mr.STATUS_INVALID})
        self._run(ex)
        self.assertEqual(ex.ran, ["D"])
        for stage in ("C", "K"):
            sid = f"{STEM}:{stage}"
            rec = self.store.load_record(sid)
            self.assertEqual(rec["status"], mr.STATUS_BLOCKED)
            self.assertEqual(rec["blocked_by"]["stage_id"], f"{STEM}:D")
            self.assertIsNone(self.store.load_claim(sid))

    def test_failed_c_blocks_only_k(self):
        ex = FakeExecutor({"C": mr.STATUS_PROVIDER_ERROR})
        self._run(ex)
        self.assertEqual(ex.ran, ["D", "C"])
        self.assertEqual(self.store.load_record(f"{STEM}:K")["status"],
                         mr.STATUS_BLOCKED)
        self.assertEqual(self.store.load_record(f"{STEM}:D")["status"],
                         mr.STATUS_COMPLETE)

    def test_child_waits_when_parent_not_run_yet(self):
        ex = FakeExecutor()
        out = self._run(ex, rows=[self.plan[1]])
        self.assertEqual(out["actions"], {mr.ACTION_WAITING: 1})
        self.assertEqual(ex.ran, [])
        self.assertIsNone(self.store.load_claim(self.plan[1]["stage_id"]))

    # -- orfani
    def test_orphan_claim_is_never_rerun_until_explicit_release(self):
        sid = self.plan[0]["stage_id"]
        self.store.claim(sid, {"note": "run interrotto"})
        ex = FakeExecutor()
        out = self._run(ex, rows=[self.plan[0]])
        self.assertEqual(out["actions"], {mr.ACTION_ORPHAN: 1})
        self.assertEqual(ex.ran, [])
        self.assertEqual(self.store.orphans([r["stage_id"] for r in self.plan]),
                         [sid])
        with self.assertRaises(mr.StoreError):
            self.store.release_orphan(sid, "corto")
        entry = self.store.release_orphan(
            sid, "Colab disconnesso, nessun record scritto")
        self.assertEqual(entry["stage_id"], sid)
        out = self._run(ex, rows=[self.plan[0]])
        self.assertEqual(out["executed"], 1)

    def test_release_refuses_when_record_exists(self):
        self._run(FakeExecutor())
        with self.assertRaises(mr.StoreError):
            self.store.release_orphan(
                self.plan[0]["stage_id"], "motivazione abbastanza lunga")

    # -- errori
    def test_exception_after_claim_becomes_provider_error_and_is_redacted(self):
        secret = "sk-test-SECRETVALUE-123456"
        ex = FakeExecutor(run_error=RuntimeError("boom " + secret))
        self._run(ex, secrets=[secret])
        rec = self.store.load_record(self.plan[0]["stage_id"])
        self.assertEqual(rec["status"], mr.STATUS_PROVIDER_ERROR)
        self.assertEqual(rec["error_summary"]["code"],
                         "EXECUTOR_EXCEPTION:RuntimeError")
        self.assertNotIn(secret, json.dumps(rec))
        self.assertNotIn(secret, "\n".join(self.logs))
        self.assertEqual(self.store.load_record(self.plan[1]["stage_id"])
                         ["status"], mr.STATUS_BLOCKED)

    def test_prepare_failure_makes_no_claim_and_stops_the_batch(self):
        ex = FakeExecutor(prepare_error=ValueError("dati mancanti"))
        out = self._run(ex)
        self.assertEqual(out["stopped"], "prepare_failed")
        self.assertEqual(ex.ran, [])
        self.assertIsNone(self.store.load_claim(self.plan[0]["stage_id"]))
        self.assertIsNone(self.store.load_record(self.plan[0]["stage_id"]))

    def test_unserializable_outcome_is_not_lost(self):
        class Bad(FakeExecutor):
            def run(self, row, prepared):
                out = super().run(row, prepared)
                out["receipt"] = {"x": {1, 2}}  # un set non e' JSON
                return out
        self._run(Bad(), rows=[self.plan[0]])
        rec = self.store.load_record(self.plan[0]["stage_id"])
        self.assertEqual(rec["status"], mr.STATUS_RECEIPT_REJECTED)
        self.assertTrue(rec["error_summary"]["code"].startswith(
            "RECORD_SERIALIZATION_ERROR"))

    def test_invalid_executor_status_is_recorded_as_error(self):
        class Bad(FakeExecutor):
            def run(self, row, prepared):
                return {"status": "SUCCESS!"}
        self._run(Bad(), rows=[self.plan[0]])
        rec = self.store.load_record(self.plan[0]["stage_id"])
        self.assertEqual(rec["status"], mr.STATUS_PROVIDER_ERROR)

    # -- archivio
    def test_records_and_claims_are_create_only(self):
        sid = self.plan[0]["stage_id"]
        self.store.claim(sid, {})
        with self.assertRaises(mr.ClaimExists):
            self.store.claim(sid, {})
        self.store.write_record(sid, {"status": mr.STATUS_COMPLETE})
        with self.assertRaises(mr.RecordExists):
            self.store.write_record(sid, {"status": mr.STATUS_COMPLETE})

    def test_tampered_record_is_detected(self):
        self._run(FakeExecutor(), rows=[self.plan[0]])
        path = next(self.store.records.glob("V5_RECORD_*.json"))
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = mr.STATUS_INVALID
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(mr.StoreCorrupt):
            self.store.load_record(self.plan[0]["stage_id"])

    # -- limiti di lotto
    def test_max_stages_counts_only_executed_stages(self):
        ex = FakeExecutor()
        out = self._run(ex, max_stages=2)
        self.assertEqual(ex.ran, ["D", "C"])
        self.assertEqual(out["stopped"], "max_stages")
        out = self._run(ex, max_stages=2)
        self.assertEqual(ex.ran, ["D", "C", "K"])
        self.assertEqual(out["executed"], 1)

    # -- riepilogo e conformita'
    def test_conformity_strict_vs_tolerant(self):
        ex = FakeExecutor({"D:dev": "SINGLE_JSON_FENCE",
                           "C:dev": "NONE", "K": mr.STATUS_INVALID,
                           "K:dev": "REJECTED_WRAPPER"})
        self._run(ex)
        summary = mr.summarize(self.plan, self.store)
        m = summary["conformity_by_model"][MODEL]
        self.assertEqual(m["with_output"], 3)
        self.assertEqual(m["tolerant_ok"], 2)   # D (con fence) e C
        self.assertEqual(m["strict_ok"], 1)     # solo C, senza deviazione
        self.assertEqual(m["fence"], 1)
        self.assertEqual(m["rejected_wrapper"], 1)
        self.assertIn("strict=  1", mr.format_summary(summary))

    def test_summary_counts_pending_and_orphans(self):
        self.store.claim(self.plan[0]["stage_id"], {})
        summary = mr.summarize(self.plan, self.store)
        self.assertEqual(summary["orphan"], 1)
        self.assertEqual(summary["pending"], 2)

    # -- piano reale V4 (solo costruzione offline, nessun file dati)
    def test_real_v4_plan_is_valid_and_selectable(self):
        from evaluation.rq2_v4_unified_gtfree_discovery_plan import (
            build_offline_v4_discovery_plan,
        )
        rows = build_offline_v4_discovery_plan()["entries"]
        mr.validate_plan(rows)
        self.assertEqual(len(rows), 180)
        self.assertEqual(len(mr.select_rows(rows, models=["gemini"])), 60)
        self.assertEqual(len(mr.select_rows(rows, stages=["D"])), 60)
        one = mr.select_rows(rows, models=["gemini"], harnesses=["A0"],
                             cases=["cloudbed-1_q032"])
        self.assertEqual([r["stage"] for r in one], ["D", "C", "K"])
        with self.assertRaises(mr.PlanMismatch):
            mr.select_rows(rows, models=["gpt"])
        with self.assertRaises(mr.PlanMismatch):
            mr.select_rows(rows, cases=["cloudbed-1_q014"])  # OOD sigillato

    def test_plan_with_wrong_dependencies_is_rejected(self):
        bad = _plan()
        bad[2]["depends_on"] = [f"{STEM}:K"]
        with self.assertRaises(mr.PlanMismatch):
            mr.validate_plan(bad)


if __name__ == "__main__":
    unittest.main()
