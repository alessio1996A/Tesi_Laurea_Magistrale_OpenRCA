"""Test offline e sintetici della stratificazione RQ1 (nessuna GT reale, nessun modello, nessuna rete)."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from evaluation import rq1_coverage_stratification as m

COVERED_CASE = "cloudbed-1_q010"     # riga: container CPU load (classe con regola)
UNCOVERED_CASE = "cloudbed-1_q011"   # riga: node CPU spike (classe tenuta fuori)
CASES = (COVERED_CASE, UNCOVERED_CASE)
ROW_REASON = {10: "container CPU load", 11: "node CPU spike",
              12: "container network latency", 13: "container packet loss"}


def _csv_text(header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue()


def make_zip(path, scoring=None):
    scoring = scoring or {}
    with ZipFile(path, "w") as zf:
        for bed in ("cloudbed-1", "cloudbed-2"):
            q, r = [], []
            for i in range(100):
                reason = ROW_REASON.get(i, "container CPU load")
                text = scoring.get(i, f"The only predicted root cause reason is {reason}")
                q.append(["task_2", f"instr{i}", text])
                r.append(["1", "info", f"c{i}", reason, "2022-03-20 00:00:00"])
            zf.writestr(f"Market/{bed}/query.csv",
                        _csv_text(["task_index", "instruction", "scoring_points"], q))
            zf.writestr(f"Market/{bed}/record.csv",
                        _csv_text(["timestamp", "level", "component", "reason", "datetime"], r))


def make_plan(data_dir, score_of):
    """Piano con 2 casi x 3 modelli x 5 varianti = 30 run; score_of(model, case, variant)."""
    runs, cases = [], [{"case_id": c, "task_index": "task_2", "requested_fault_count": 1}
                       for c in CASES]
    folder = Path(data_dir) / "data/results/evaluation20" / m.PROTOCOL
    folder.mkdir(parents=True)
    for case in CASES:
        for model in m.MODELS:
            for variant in m.VARIANTS:
                run_id = f"{m.PROTOCOL}__{model}__{case}__{variant.lower()}__r01"
                runs.append({"run_id": run_id, "case_id": case,
                             "model_key": model, "variant": variant})
                score = score_of(model, case, variant)
                if score == "missing":
                    continue
                body = {"case_id": case, "variant": variant,
                        "prediction": None if score == "none" else str(score)}
                out = folder / (run_id + ".json")
                out.write_text(json.dumps(body), encoding="utf-8")
                (folder / (run_id + ".sha256.json")).write_text(json.dumps(
                    {"result_sha256": hashlib.sha256(out.read_bytes()).hexdigest()}),
                    encoding="utf-8")
    plan_dir = Path(data_dir) / "data/protocols/evaluation20"
    plan_dir.mkdir(parents=True)
    (plan_dir / (m.PROTOCOL + "_plan_v1.json")).write_text(
        json.dumps({"runs": runs, "cases": cases}), encoding="utf-8")
    return runs


def fake_evaluate(prediction, scoring_points):
    return [], [], float(prediction)


def default_score(model, case, variant):
    base = {"A0": 0.0, "A1": 0.25, "A1_8R": 0.25, "A1_8R_Planning": 0.25, "A1_PAVE": 0.25}[variant]
    if variant == "A1_8R" and case == COVERED_CASE:
        return 0.75          # le regole aiutano solo dove esistono
    return base


class CaseClassTests(unittest.TestCase):
    def test_strata(self):
        covered = m.case_classes({"row_reason": "container CPU load",
                                  "scoring_points": "reason is container CPU load"})
        self.assertEqual(covered["stratum"], "coperta")
        spike = m.case_classes({"row_reason": "node CPU spike", "scoring_points": ""})
        self.assertEqual(spike["stratum"], "non_coperta")
        self.assertEqual(spike["held_out_classes_in_case"], ["node CPU spike"])
        network = m.case_classes({"row_reason": "container network latency", "scoring_points": ""})
        self.assertEqual(network["stratum"], "non_coperta")
        self.assertFalse(network["row_class_known"])
        mixed = m.case_classes({"row_reason": "container CPU load",
                                "scoring_points": "container CPU load and node CPU spike"})
        self.assertEqual(mixed["stratum"], "mista")
        unknown_row_with_covered = m.case_classes({
            "row_reason": "container network latency",
            "scoring_points": "container memory load"})
        self.assertEqual(unknown_row_with_covered["stratum"], "mista")

    def test_node_cpu_load_is_not_node_cpu_spike(self):
        out = m.case_classes({"row_reason": "node CPU load", "scoring_points": ""})
        self.assertEqual(out["labels"], ["node CPU load"])
        self.assertEqual(out["stratum"], "coperta")

    def test_covered_labels_come_from_rule_specs(self):
        self.assertEqual(len(m.COVERED), 8)
        self.assertIn("node CPU load", m.COVERED)
        self.assertNotIn("node CPU spike", m.COVERED)
        self.assertEqual(len(m.HELD_OUT), 4)


class StrataTests(unittest.TestCase):
    def run_strata(self, score_of=default_score, scoring=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        make_plan(tmp.name, score_of)
        make_zip(Path(tmp.name) / "Market.zip", scoring)
        return m.run_strata(Path(tmp.name), Path(tmp.name) / "Market.zip", None,
                            evaluate=fake_evaluate, expected_runs=30, expected_cases=2)

    def test_effect_concentrated_in_covered_stratum(self):
        report = self.run_strata()
        self.assertEqual(report["cases_per_stratum"], {"coperta": 1, "non_coperta": 1})
        paired = report["paired_A1_8R_minus_A1"]
        self.assertAlmostEqual(paired["sonnet|coperta"]["mean_difference"], 0.5)
        self.assertEqual(paired["sonnet|coperta"]["win"], 1)
        self.assertAlmostEqual(paired["sonnet|non_coperta"]["mean_difference"], 0.0)
        self.assertEqual(paired["sonnet|non_coperta"]["tie"], 1)
        evidence = report["paired_A1_minus_A0"]
        self.assertAlmostEqual(evidence["haiku|tutti"]["mean_difference"], 0.25)
        self.assertEqual(report["held_out_classes_found_in_evaluation_cases"], 1)
        self.assertEqual(report["provider_calls"], 0)

    def test_missing_and_empty_runs_leave_the_pair_out(self):
        def score(model, case, variant):
            if (model, case, variant) == ("gemini", COVERED_CASE, "A1"):
                return "missing"
            if (model, case, variant) == ("gemini", UNCOVERED_CASE, "A1_8R"):
                return "none"
            return default_score(model, case, variant)
        report = self.run_strata(score)
        self.assertEqual(report["runs_not_scored"], {"missing": 1, "no_prediction": 1})
        paired = report["paired_A1_8R_minus_A1"]
        self.assertEqual(paired["gemini|coperta"]["pairs"], 0)
        self.assertEqual(paired["gemini|non_coperta"]["pairs"], 0)
        self.assertEqual(paired["sonnet|coperta"]["pairs"], 1)

    def test_altered_result_stops_everything(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = make_plan(tmp, default_score)
            make_zip(Path(tmp) / "Market.zip")
            output, _ = m.result_paths(Path(tmp), runs[0]["run_id"])
            output.write_text(output.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(m.ScoringError):
                m.run_strata(Path(tmp), Path(tmp) / "Market.zip", None, evaluate=fake_evaluate,
                             expected_runs=30, expected_cases=2)

    def test_result_of_another_case_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = make_plan(tmp, default_score)
            output, sidecar = m.result_paths(Path(tmp), runs[0]["run_id"])
            body = json.loads(output.read_text(encoding="utf-8"))
            body["case_id"] = "cloudbed-2_q099"
            output.write_text(json.dumps(body), encoding="utf-8")
            sidecar.write_text(json.dumps(
                {"result_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}), encoding="utf-8")
            with self.assertRaises(m.ScoringError):
                m.load_result(Path(tmp), runs[0])

    def test_missing_sidecar_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = make_plan(tmp, default_score)
            _, sidecar = m.result_paths(Path(tmp), runs[0]["run_id"])
            sidecar.unlink()
            with self.assertRaises(m.ScoringError):
                m.load_result(Path(tmp), runs[0])

    def test_task_mismatch_with_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_zip(Path(tmp) / "Market.zip")
            with self.assertRaises(m.ScoringError):
                m.load_references(Path(tmp) / "Market.zip",
                                  [{"case_id": COVERED_CASE, "task_index": "task_7"}])

    def test_plan_with_wrong_size_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_plan(tmp, default_score)
            with self.assertRaises(m.ScoringError):
                m.load_plan(Path(tmp))          # attesi 300 run, il piano di prova ne ha 30

    def test_reproduction_check(self):
        rows = []
        for (model, variant), (n, mean) in m.REPORTED.items():
            rows += [{"model": model, "variant": variant, "score": mean, "case_id": f"c{i}"}
                     for i in range(n)]
        self.assertTrue(m.reproduction_check(rows)["all_match"])
        rows[0]["score"] += 0.01
        check = m.reproduction_check(rows)
        self.assertFalse(check["all_match"])
        self.assertFalse(check["cells"]["sonnet|A0"]["match"])

    def test_reported_table_has_295_runs(self):
        self.assertEqual(sum(n for n, _ in m.REPORTED.values()), 295)

    def test_format_strata_runs(self):
        text = m.format_strata(self.run_strata())
        self.assertIn("A1_8R - A1", text)


class SeparationTests(unittest.TestCase):
    def build(self, tmp, labels_in_dev=False):
        make_zip(Path(tmp) / "Market.zip")
        (Path(tmp) / "data/processed").mkdir(parents=True)
        entries = [(10, "development"), (11, "ood_holdout"), (12, "evaluation"),
                   (13, "mixed_quarantine" if not labels_in_dev else "development")]
        manifest = [[f"cloudbed-1_q{i:03d}", "cloudbed-1", str(i), "task_2", f"instr{i}",
                     "1647800000", "1647801800"] for i, _ in entries]
        split = [[f"cloudbed-1_q{i:03d}", "cloudbed-1", "1647800000", "1647801800", s]
                 for i, s in entries]
        (Path(tmp) / "data/processed/benchmark_inputs_market.csv").write_text(
            _csv_text(["case_id", "cloudbed", "query_index", "task_index", "instruction",
                       "start_unix", "end_unix"], manifest), encoding="utf-8")
        (Path(tmp) / "data/processed/split_market_v1.csv").write_text(
            _csv_text(["case_id", "cloudbed", "start_unix", "end_unix", "split"], split),
            encoding="utf-8")

    def test_separation_holds_when_four_classes_only_in_ood(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build(tmp)
            # q013 e' "container packet loss" (una delle quattro): lo mettiamo in OOD
            # spostando q013 nel gruppo giusto, qui invece lo lasciamo in quarantena.
            report = m.run_separation(Path(tmp), Path(tmp) / "Market.zip")
            self.assertEqual(report["per_split"]["ood_holdout"]["in_four_classes"], 1)
            self.assertEqual(report["per_split"]["mixed_quarantine"]["in_four_classes"], 1)
            self.assertTrue(report["separation_holds"])      # la quarantena non conta per RQ1
            self.assertEqual(report["four_classes_in_rq1_groups"], 0)
            self.assertEqual(report["four_classes_outside_ood_holdout"], 1)
            self.assertNotIn("cloudbed-1_q0", json.dumps(report))

    def test_violation_in_development_is_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build(tmp, labels_in_dev=True)
            report = m.run_separation(Path(tmp), Path(tmp) / "Market.zip")
            self.assertEqual(report["per_split"]["development"]["in_four_classes"], 1)
            self.assertEqual(report["four_classes_in_rq1_groups"], 1)
            self.assertFalse(report["separation_holds"])

    def test_misaligned_instruction_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build(tmp)
            path = Path(tmp) / "data/processed/benchmark_inputs_market.csv"
            path.write_text(path.read_text(encoding="utf-8").replace("instr10", "altro"),
                            encoding="utf-8")
            with self.assertRaises(m.ScoringError):
                m.run_separation(Path(tmp), Path(tmp) / "Market.zip")

    def test_cli_refuses_to_overwrite_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.build(tmp)
            out = Path(tmp) / "report.json"
            argv = ["separation", "--data-dir", tmp, "--out", str(out)]
            self.assertEqual(m.main(argv), 0)
            self.assertEqual(m.main(argv), 2)


if __name__ == "__main__":
    unittest.main()
