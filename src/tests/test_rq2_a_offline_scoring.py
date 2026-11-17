"""Test offline e sintetici di RQ2-A (nessuna GT reale, nessun modello, nessuna rete)."""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from evaluation import rq2_a_offline_scoring as s

CASES = s.DISCOVERY_CASES
LABELS = dict(zip(CASES, s.fault_policy.CANONICAL))


def _sha(core):
    return s._sha(core)


def make_record(case, model, harness, stage, status="RECORDED_COMPLETE", **art):
    stage_id = f"plan:{case}:{model}:{harness}:{stage}"
    receipt = {"artifact": art} if status == "RECORDED_COMPLETE" else None
    core = {"stage_id": stage_id, "stage": stage, "status": status,
            "receipt": receipt}
    return {**core, "record_sha256": _sha(core)}


def d_art(case, task="task_3", prediction='{"1": {"root cause component": "x"}}'):
    row = int(case.split("_q")[1])
    return {"diagnostic_run": {"prediction": prediction, "task_index": task,
                               "query_index": row}}


def c_art(decision="diagnosis", label=None):
    body = {"schema_version": "rq2_cause_probe_v0", "decision": decision,
            "predicted_fault_type": label}
    return {"raw_response": json.dumps(body)}


def write_all(folder, d_status=None, c_label=None):
    d_status = d_status or {}
    for case in CASES:
        for model in s.MODELS:
            for harness in s.HARNESSES:
                key = (case, model, harness)
                st = d_status.get(key, "RECORDED_COMPLETE")
                rec = make_record(case, model, harness, "D", st, **d_art(case))
                name = f"V5_RECORD_{abs(hash(rec['stage_id']))}.json"
                (Path(folder) / name).write_text(json.dumps(rec), encoding="utf-8")
                label = (c_label or {}).get(key, LABELS[case])
                crec = make_record(case, model, harness, "C",
                                   "RECORDED_COMPLETE", **c_art("diagnosis", label))
                (Path(folder) / f"V5_RECORD_C{abs(hash(crec['stage_id']))}.json"
                 ).write_text(json.dumps(crec), encoding="utf-8")


def make_zip(path):
    def csv_text(rows, header):
        out = [",".join(header)]
        out += [",".join(r) for r in rows]
        return "\n".join(out) + "\n"
    with ZipFile(path, "w") as zf:
        for bed in ("cloudbed-1", "cloudbed-2"):
            q_rows, r_rows = [], []
            for i in range(100):
                label = "container packet loss"
                for case, lab in LABELS.items():
                    if case == f"{bed}_q{i:03d}":
                        label = lab
                q_rows.append([f"task_3", f"instr{i}", f'"The only predicted root cause component is c{i}"'])
                r_rows.append(["1", "info", f"c{i}", label, "2022-03-20 00:00:00"])
            zf.writestr(f"Market/{bed}/query.csv",
                        csv_text(q_rows, ["task_index", "instruction", "scoring_points"]))
            zf.writestr(f"Market/{bed}/record.csv",
                        csv_text(r_rows, ["timestamp", "level", "component", "reason", "datetime"]))


def fake_evaluate(prediction, scoring_points):
    ok = "x" in prediction
    return (["c"] if ok else []), ([] if ok else ["c"]), (1.0 if ok else 0.0)


class RQ2AScoringTests(unittest.TestCase):
    def test_load_records_and_plan_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_all(tmp)
            report = s.plan_check(tmp)
        self.assertEqual(report["status_counts"]["D"], {"RECORDED_COMPLETE": 60})
        self.assertEqual(report["status_counts"]["C"], {"RECORDED_COMPLETE": 60})
        self.assertFalse(report["reads_ground_truth"])

    def test_missing_record_stays_in_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_all(tmp)
            victim = next(Path(tmp).glob("V5_RECORD_[0-9]*.json"))
            victim.unlink()
            report = s.plan_check(tmp)
        self.assertEqual(report["status_counts"]["D"], {"MISSING": 1, "RECORDED_COMPLETE": 59})

    def test_altered_record_stops_everything(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_all(tmp)
            victim = next(Path(tmp).glob("V5_RECORD_[0-9]*.json"))
            data = json.loads(victim.read_text())
            data["status"] = "INVALID_OUTPUT"
            victim.write_text(json.dumps(data))
            with self.assertRaises(s.ScoringError):
                s.load_records(tmp)

    def test_record_outside_discovery_plan_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec = make_record("cloudbed-1_q014", "sonnet", "A1", "D", **d_art("cloudbed-1_q014"))
            (Path(tmp) / "V5_RECORD_x.json").write_text(json.dumps(rec))
            with self.assertRaises(s.ScoringError):
                s.load_records(tmp)

    def test_full_scoring_with_injected_scorer(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_all(tmp)
            zpath = Path(tmp) / "m.zip"
            make_zip(zpath)
            table = s.index_records(s.load_records(tmp))
            refs = s.load_references(zpath)
            rows = s.score_d(table, refs, fake_evaluate)
            self.assertEqual(len(rows), 60)
            self.assertTrue(all(r["score"] == 1.0 for r in rows))
            summary = s.summarize_d(rows)
            self.assertEqual(summary["arms"]["sonnet|A1"]["mean_planned"], 1.0)
            self.assertEqual(summary["paired_A1_8R_vs_A1"]["haiku"]["tie"], 4)
            c = s.score_c(table, refs)
            self.assertEqual(c["per_arm"]["gemini|A0"]["counts"]["correct"], 4)

    def test_wrong_fault_type_and_not_complete_d_count_against_the_arm(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = {("cloudbed-1_q032", "sonnet", "A1"): "disk full"}
            inv = {("cloudbed-1_q050", "sonnet", "A1"): "INVALID_OUTPUT"}
            write_all(tmp, d_status=inv, c_label=bad)
            zpath = Path(tmp) / "m.zip"
            make_zip(zpath)
            table = s.index_records(s.load_records(tmp))
            refs = s.load_references(zpath)
            rows = s.score_d(table, refs, fake_evaluate)
            summary = s.summarize_d(rows)
            arm = summary["arms"]["sonnet|A1"]
            self.assertEqual(arm["planned"], 4)
            self.assertEqual(arm["scored"], 3)
            self.assertAlmostEqual(arm["mean_planned"], 0.75)
            self.assertEqual(arm["not_scored"], {"INVALID_OUTPUT": 1})
            counts = s.score_c(table, refs)["per_arm"]["sonnet|A1"]["counts"]
            self.assertEqual(counts["correct"], 3)
            self.assertEqual(counts["unmatched_diagnosis"], 1)

    def test_task_mismatch_between_record_and_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_all(tmp)
            zpath = Path(tmp) / "m.zip"
            make_zip(zpath)
            table = s.index_records(s.load_records(tmp))
            refs = s.load_references(zpath)
            refs["cloudbed-1_q032"]["task_index"] = "task_9"
            with self.assertRaises(s.ScoringError):
                s.score_d(table, refs, fake_evaluate)

    def test_reference_rejects_sealed_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            zpath = Path(tmp) / "m.zip"
            make_zip(zpath)
            with self.assertRaises(s.ScoringError):
                s.load_references(zpath, cases=("cloudbed-1_q014",))

    def test_official_evaluate_requires_pinned_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / "main"
            main.mkdir()
            (main / "evaluate.py").write_text("def evaluate(a, b):\n    return [], [], 0.0\n")
            with self.assertRaises(s.ScoringError):
                s.load_official_evaluate(tmp)

    def test_report_is_create_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "r.json"
            s.write_report_create_only({"a": 1}, target)
            with self.assertRaises(FileExistsError):
                s.write_report_create_only({"a": 2}, target)


if __name__ == "__main__":
    unittest.main()
