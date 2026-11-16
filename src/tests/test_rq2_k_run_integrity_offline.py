"""Test sintetici del verificatore di integrita' (nessun dato reale, nessuna API)."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from evaluation import rq2_k_run_integrity as integ
from evaluation import rq2_v5_matrix_runner as mr

COMMIT = integ.FROZEN_COMMIT
OTHER = "0" * 40
PREVIEW = "p" * 64


def _row(stem, stage, deps):
    return {"stage_id": f"{stem}:{stage}", "stage": stage, "case_id": "case-1",
            "logical_model": "m1", "model_id": "model-x", "model_provider": "google",
            "harness": "A0", "depends_on": [f"{stem}:{d}" for d in deps],
            "d_engine": "x", "execution_status": "planned"}


def _plan():
    rows = []
    for stem in ("plan:case-1:m1:A0", "plan:case-1:m1:A1"):
        rows += [_row(stem, "D", []), _row(stem, "C", ["D"]), _row(stem, "K", ["D", "C"])]
    return rows


def _executed(store, row, status=mr.STATUS_COMPLETE, commit=COMMIT):
    claim = store.claim(row["stage_id"], {**mr._identity(row), "source_commit": commit})
    return store.write_record(row["stage_id"], {
        **mr._identity(row), "status": status, "receipt": {"x": 1}, "format": None,
        "provenance": None, "error_summary": None, "blocked_by": None,
        "claim_sha256": claim["claim_sha256"], "started_at_utc": "t", "finished_at_utc": "t",
        "elapsed_seconds": 1.0, "source_commit": commit})


def _build(root: Path, *, a1_d_status=mr.STATUS_COMPLETE):
    """A0 tutto completo; A1: D con `a1_d_status`, C e K bloccati se D non e' completo."""
    store = mr.StageStore(root)
    rows = _plan()
    by_id = {r["stage_id"]: r for r in rows}
    for row in rows:
        if row["stage_id"].startswith("plan:case-1:m1:A0"):
            _executed(store, row)
    d1 = by_id["plan:case-1:m1:A1:D"]
    _executed(store, d1, status=a1_d_status)
    for stage in ("C", "K"):
        row = by_id[f"plan:case-1:m1:A1:{stage}"]
        if a1_d_status == mr.STATUS_COMPLETE:
            _executed(store, row)
        else:
            mr._blocked_record(store, row, d1["stage_id"], a1_d_status)
    manifest = {"protocol": mr.PROTOCOL, "plan_preview_sha256": PREVIEW,
                "created_commit": COMMIT}
    (Path(root) / integ.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    return store, rows


def _checks(report):
    return sorted({v["check"] for v in report["violations"]})


def _rewrite(path: Path, mutate, *, rehash: str | None = None):
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    if rehash:
        core = {k: v for k, v in payload.items() if k != rehash}
        payload[rehash] = mr._sha(core)
    path.write_text(json.dumps(payload), encoding="utf-8")


class CleanStoreTests(unittest.TestCase):
    def test_clean_store_is_ok_with_blocked_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, rows = _build(Path(tmp), a1_d_status=mr.STATUS_INVALID)
            report = integ.check_integrity(Path(tmp), rows, plan_preview_sha256=PREVIEW)
            self.assertTrue(report["ok"], report["violations"])
            self.assertEqual(report["records_valid"], 6)
            self.assertEqual(report["claims_valid"], 4)         # i 2 bloccati non hanno claim
            self.assertEqual(report["status_counts"][mr.STATUS_BLOCKED], 2)
            self.assertEqual(report["orphans"], [])
            self.assertIn("None", report["source_commit_counts"])   # i bloccati

    def test_fingerprint_is_stable_and_depends_on_content(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            _, rows = _build(Path(a))
            first = integ.check_integrity(Path(a), rows)["records_fingerprint_sha256"]
            self.assertEqual(first, integ.check_integrity(Path(a), rows)["records_fingerprint_sha256"])
            _build(Path(b), a1_d_status=mr.STATUS_INVALID)
            self.assertNotEqual(first, integ.check_integrity(Path(b), rows)["records_fingerprint_sha256"])

    def test_render_mentions_the_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, rows = _build(Path(tmp))
            text = integ.render(integ.check_integrity(Path(tmp), rows))
            self.assertIn("ESITO: OK", text)
            self.assertIn(COMMIT, text)


class TamperingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store, self.rows = _build(self.root)
        self.sid = "plan:case-1:m1:A0:K"

    def tearDown(self):
        self.tmp.cleanup()

    def _record_path(self):
        return self.store._record_path(self.sid)

    def test_edited_record_without_rehash_is_detected(self):
        _rewrite(self._record_path(), lambda p: p.__setitem__("status", "PROVIDER_ERROR"))
        report = integ.check_integrity(self.root, self.rows)
        self.assertIn("record_hash_non_coerente", _checks(report))
        self.assertFalse(report["ok"])

    def test_edited_claim_without_rehash_is_detected(self):
        path = self.store._claim_path(self.sid)
        _rewrite(path, lambda p: p.__setitem__("source_commit", OTHER))
        self.assertIn("claim_hash_non_coerente", _checks(integ.check_integrity(self.root, self.rows)))

    def test_wrong_source_commit_is_detected_even_if_hashes_are_consistent(self):
        _rewrite(self._record_path(), lambda p: p.__setitem__("source_commit", OTHER),
                 rehash="record_sha256")
        report = integ.check_integrity(self.root, self.rows)
        self.assertEqual(_checks(report), ["record_source_commit_diverso"])

    def test_record_pointing_to_another_claim_is_detected(self):
        _rewrite(self._record_path(), lambda p: p.__setitem__("claim_sha256", "f" * 64),
                 rehash="record_sha256")
        self.assertIn("claim_sha256_del_record_diverso_dal_claim",
                      _checks(integ.check_integrity(self.root, self.rows)))

    def test_identity_mismatch_with_the_plan_is_detected(self):
        _rewrite(self._record_path(), lambda p: p.__setitem__("logical_model", "altro"),
                 rehash="record_sha256")
        self.assertIn("record_logical_model_diverso",
                      _checks(integ.check_integrity(self.root, self.rows)))

    def test_unreadable_record_is_a_violation_not_an_exception(self):
        self._record_path().write_text("{non json", encoding="utf-8")
        self.assertIn("record_non_leggibile", _checks(integ.check_integrity(self.root, self.rows)))

    def test_orphan_claim_is_detected(self):
        self._record_path().unlink()
        report = integ.check_integrity(self.root, self.rows)
        self.assertEqual(report["orphans"], [self.sid])
        self.assertIn("orfano_claim_senza_record", _checks(report))

    def test_missing_record_without_claim_is_detected(self):
        self._record_path().unlink()
        self.store._claim_path(self.sid).unlink()
        self.assertIn("record_mancante", _checks(integ.check_integrity(self.root, self.rows)))

    def test_stray_files_are_reported(self):
        (self.root / "records" / "V5_RECORD_estraneo.json").write_text("{}", encoding="utf-8")
        (self.root / "claims" / "V5_CLAIM_estraneo.json").write_text("{}", encoding="utf-8")
        checks = _checks(integ.check_integrity(self.root, self.rows))
        self.assertIn("file_record_estraneo", checks)
        self.assertIn("file_claim_estraneo", checks)

    def test_executed_without_claim_is_detected(self):
        self.store._claim_path(self.sid).unlink()
        self.assertIn("eseguito_senza_claim", _checks(integ.check_integrity(self.root, self.rows)))


class DependencyAndBlockedTests(unittest.TestCase):
    def test_executed_stage_with_a_parent_not_complete_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, rows = _build(Path(tmp))
            path = store._record_path("plan:case-1:m1:A0:D")
            _rewrite(path, lambda p: p.__setitem__("status", mr.STATUS_INVALID),
                     rehash="record_sha256")
            self.assertIn("eseguito_con_genitore_non_completo",
                          _checks(integ.check_integrity(Path(tmp), rows)))

    def test_blocked_by_a_complete_parent_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, rows = _build(Path(tmp), a1_d_status=mr.STATUS_INVALID)
            path = store._record_path("plan:case-1:m1:A1:D")
            _rewrite(path, lambda p: p.__setitem__("status", mr.STATUS_COMPLETE),
                     rehash="record_sha256")
            self.assertIn("bloccato_da_genitore_completo_o_assente",
                          _checks(integ.check_integrity(Path(tmp), rows)))

    def test_blocked_record_carrying_a_commit_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, rows = _build(Path(tmp), a1_d_status=mr.STATUS_INVALID)
            path = store._record_path("plan:case-1:m1:A1:K")
            _rewrite(path, lambda p: p.__setitem__("source_commit", COMMIT), rehash="record_sha256")
            self.assertIn("bloccato_con_source_commit",
                          _checks(integ.check_integrity(Path(tmp), rows)))


class ManifestAndReleasedTests(unittest.TestCase):
    def test_manifest_absent_and_plan_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, rows = _build(Path(tmp))
            report = integ.check_integrity(Path(tmp), rows, plan_preview_sha256="x" * 64)
            self.assertIn("manifest_piano_diverso", _checks(report))
            (Path(tmp) / integ.MANIFEST).unlink()
            self.assertIn("manifest_assente", _checks(integ.check_integrity(Path(tmp), rows)))

    def test_manifest_commit_differs_is_a_note_not_a_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, rows = _build(Path(tmp))
            _rewrite(Path(tmp) / integ.MANIFEST, lambda p: p.__setitem__("created_commit", OTHER))
            report = integ.check_integrity(Path(tmp), rows, plan_preview_sha256=PREVIEW)
            self.assertTrue(report["ok"])
            self.assertTrue(any("manifest" in n for n in report["notes"]))

    def test_released_claims_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, rows = _build(Path(tmp))
            (store.released / "log.jsonl").write_text(
                json.dumps({"stage_id": "x", "reason": "prova di rilascio"}) + "\n", encoding="utf-8")
            report = integ.check_integrity(Path(tmp), rows, plan_preview_sha256=PREVIEW)
            self.assertEqual(len(report["released_claims"]), 1)
            self.assertTrue(any("rilasciati" in n for n in report["notes"]))


class ReadOnlyTests(unittest.TestCase):
    def test_check_does_not_create_or_change_anything(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, rows = _build(Path(tmp))

            def snapshot():
                return {str(p.relative_to(tmp)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in sorted(Path(tmp).rglob("*")) if p.is_file()}, \
                       sorted(str(p.relative_to(tmp)) for p in Path(tmp).rglob("*") if p.is_dir())
            before = snapshot()
            integ.check_integrity(Path(tmp), rows, plan_preview_sha256=PREVIEW)
            self.assertEqual(before, snapshot())

    def test_missing_root_is_reported_and_not_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "non_esiste"
            report = integ.check_integrity(root, _plan())
            self.assertFalse(report["ok"])
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
