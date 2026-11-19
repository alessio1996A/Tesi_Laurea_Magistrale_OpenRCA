"""Test offline e sintetici della normalizzazione RQ1 (nessuna GT, nessun modello, nessuna rete)."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from functools import partial
from io import StringIO
from pathlib import Path
from unittest import mock

from evaluation import rq1_coverage_stratification as strat
from evaluation import rq1_normalization as m

CASES = ("cloudbed-1_q010", "cloudbed-1_q011")


def make_plan(data_dir, score_of, metrics_of=None, usage_complete=None):
    """Piano 2 incidenti x 3 modelli x 5 varianti = 30 run, con risultati (metrics) e punteggi congelati.

    score_of(model, case, variant) -> float | "error"
    metrics_of(model, case, variant) -> (total_tokens, end_to_end_seconds, duration_seconds)
    usage_complete(model, case, variant) -> bool (default True)
    """
    metrics_of = metrics_of or (lambda model, case, variant: (1000, 50.0, 40.0))
    usage_complete = usage_complete or (lambda model, case, variant: True)
    runs, frozen = [], []
    cases = [{"case_id": c, "task_index": "task_2", "requested_fault_count": 1} for c in CASES]
    folder = Path(data_dir) / "data/results/evaluation20" / strat.PROTOCOL
    folder.mkdir(parents=True)
    for case in CASES:
        for model in strat.MODELS:
            for variant in strat.VARIANTS:
                run_id = f"{strat.PROTOCOL}__{model}__{case}__{variant.lower()}__r01"
                runs.append({"run_id": run_id, "case_id": case, "model_key": model, "variant": variant})
                score = score_of(model, case, variant)
                tokens, e2e, dur = metrics_of(model, case, variant)
                out = folder / (run_id + ".json")
                out.write_text(json.dumps({
                    "case_id": case, "variant": variant, "prediction": None, "raw_response": "x",
                    "metrics": {"input_tokens": tokens - 10, "output_tokens": 10, "total_tokens": tokens,
                                "llm_calls": 1, "tool_calls": 0, "tool_rounds": 0,
                                "token_usage_complete": usage_complete(model, case, variant),
                                "end_to_end_seconds": e2e, "duration_seconds": dur,
                                "preprocessing_seconds": e2e - dur}}), encoding="utf-8")
                frozen.append({
                    "run_id": run_id, "case_id": case, "model_key": model, "variant": variant,
                    "status": "MODEL_ERROR_REVIEW_NO_RETRY" if score == "error" else "complete",
                    "official_raw_score": None if score == "error" else score,
                    "source_result_sha256": hashlib.sha256(out.read_bytes()).hexdigest()})
    plan_dir = Path(data_dir) / "data/protocols/evaluation20"
    plan_dir.mkdir(parents=True)
    plan_file = plan_dir / (strat.PROTOCOL + "_plan_v1.json")
    plan_file.write_text(json.dumps({"runs": runs, "cases": cases}), encoding="utf-8")
    scoring_dir = Path(data_dir) / "data/scoring"
    scoring_dir.mkdir(parents=True)
    report = {"protocol": strat.PROTOCOL, "prediction_field": "raw_response",
              "official_scorer_commit": strat.OFFICIAL_COMMIT,
              "official_scorer_source_sha256": strat.OFFICIAL_EVALUATE_SHA256,
              "plan_sha256": hashlib.sha256(plan_file.read_bytes()).hexdigest(), "runs": frozen}
    path = scoring_dir / (strat.PROTOCOL + "_official_raw_scoring_v1.json")
    path.write_text(json.dumps(report), encoding="utf-8")
    (scoring_dir / (strat.PROTOCOL + "_official_raw_scoring_v1.sha256.json")).write_text(
        json.dumps({"scoring_report_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}),
        encoding="utf-8")
    return runs


# Punteggi per (modello, variante) e incidente: [primo incidente, secondo incidente]
SCORES = {
    "sonnet": {"A0": (0.1, 0.3), "A1": (0.4, 0.4), "A1_8R": (0.5, 0.5),
               "A1_8R_Planning": (0.3, 0.3), "A1_PAVE": (0.6, 0.6)},
    "haiku": {"A0": (0.0, 0.0), "A1": (0.2, 0.2), "A1_8R": (0.2, 0.2),
              "A1_8R_Planning": (0.2, 0.2), "A1_PAVE": (0.2, 0.2)},
    "gemini": {"A0": (0.2, 0.2), "A1": (0.2, 0.2), "A1_8R": (0.2, 0.2),
               "A1_8R_Planning": (0.2, 0.2), "A1_PAVE": (0.2, 0.2)},
}


def score_of(model, case, variant):
    return SCORES[model][variant][CASES.index(case)]


class NormalizationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def run_norm(self, score=score_of, metrics=None, usage=None, reported=None, draws=200):
        make_plan(self.dir, score, metrics, usage)
        return m.run_normalization(self.dir, expected_runs=30, expected_cases=2,
                                   reported=reported, draws=draws)

    def test_ratio_and_difference_vs_a0_same_model(self):
        report = self.run_norm()
        s = report["summaries"]["score"]["sonnet"]
        self.assertAlmostEqual(s["A0"]["mean"], 0.2)
        self.assertAlmostEqual(s["A0"]["difference_vs_A0"], 0.0)   # A0 e' il riferimento
        self.assertAlmostEqual(s["A0"]["ratio_vs_A0"], 1.0)
        self.assertAlmostEqual(s["A1"]["ratio_vs_A0"], 2.0)
        self.assertAlmostEqual(s["A1"]["difference_vs_A0"], 0.2)
        self.assertAlmostEqual(s["A1_8R"]["ratio_vs_A0"], 2.5)
        self.assertAlmostEqual(s["A1_8R_Planning"]["ratio_vs_A0"], 1.5)
        self.assertAlmostEqual(s["A1_PAVE"]["ratio_vs_A0"], 3.0)
        self.assertEqual(s["A1"]["n"], 2)

    def test_reference_is_a0_of_the_same_model_not_of_others(self):
        report = self.run_norm()
        g = report["summaries"]["score"]["gemini"]
        self.assertAlmostEqual(g["A1"]["ratio_vs_A0"], 1.0)   # 0.2/0.2, indipendente da sonnet

    def test_ratio_undefined_when_a0_is_zero_absolute_kept(self):
        report = self.run_norm()
        h = report["summaries"]["score"]["haiku"]
        self.assertIsNone(h["A1"]["ratio_vs_A0"])
        self.assertAlmostEqual(h["A1"]["mean"], 0.2)
        self.assertAlmostEqual(h["A1"]["difference_vs_A0"], 0.2)
        ci = report["intervals"]["score"]["haiku"]["A1"]
        self.assertIsNone(ci["ratio_ci95"])
        self.assertEqual(ci["draws_ratio_defined"], 0)
        self.assertEqual(ci["draws_ratio_undefined"], ci["draws_total"])
        self.assertIsNotNone(ci["difference_ci95"])

    def test_unscored_runs_are_excluded_from_score_tokens_and_time(self):
        def with_error(model, case, variant):
            if (model, case, variant) == ("gemini", CASES[0], "A1_8R"):
                return "error"
            return score_of(model, case, variant)
        report = self.run_norm(score=with_error)
        for name in ("score", "total_tokens", "end_to_end_seconds"):
            self.assertEqual(report["summaries"][name]["gemini"]["A1_8R"]["n"], 1)
            self.assertEqual(report["summaries"][name]["gemini"]["A1"]["n"], 2)
        self.assertEqual(report["runs_not_scored"], 1)
        self.assertEqual(report["runs_scored"], 29)

    def test_tokens_and_time_ratios(self):
        def metrics(model, case, variant):
            tokens = {"A0": 1000, "A1": 2000, "A1_8R": 3000, "A1_8R_Planning": 2400, "A1_PAVE": 4000}[variant]
            return tokens, tokens / 100, tokens / 125
        report = self.run_norm(metrics=metrics)
        t = report["summaries"]["total_tokens"]["sonnet"]
        self.assertAlmostEqual(t["A1"]["ratio_vs_A0"], 2.0)
        self.assertAlmostEqual(t["A1_PAVE"]["ratio_vs_A0"], 4.0)
        e = report["summaries"]["end_to_end_seconds"]["sonnet"]
        self.assertAlmostEqual(e["A1_8R"]["mean"], 30.0)
        d = report["summaries"]["duration_seconds"]["sonnet"]
        self.assertAlmostEqual(d["A1_8R"]["mean"], 24.0)

    def test_efficiency_check_matches_when_definition_is_the_reported_one(self):
        def metrics(model, case, variant):
            tokens = {"A1_8R": 1000, "A1_8R_Planning": 721}.get(variant, 1000)
            seconds = {"A1_8R": 100.0, "A1_8R_Planning": 77.9}.get(variant, 100.0)
            return tokens, seconds, seconds
        with mock.patch.object(m, "REPORTED_EFFICIENCY",
                               {"sonnet": (-27.9, -22.1), "haiku": (-27.9, -22.1), "gemini": (-27.9, -22.1)}):
            report = self.run_norm(metrics=metrics)
        entry = report["efficiency_vs_report_of_9_nov"]["mean|end_to_end_seconds"]
        self.assertTrue(entry["tokens_all_match"])
        self.assertTrue(entry["time_all_match"])
        self.assertAlmostEqual(entry["cells"]["sonnet"]["tokens_pct"], -27.9)

    def test_efficiency_check_reports_mismatch_without_stopping(self):
        report = self.run_norm()   # token e tempi costanti: variazione 0% != relazione
        entry = report["efficiency_vs_report_of_9_nov"]["mean|end_to_end_seconds"]
        self.assertFalse(entry["tokens_all_match"])
        self.assertFalse(entry["time_all_match"])
        self.assertAlmostEqual(entry["cells"]["sonnet"]["tokens_pct"], 0.0)

    def test_stops_when_reported_means_are_not_reproduced(self):
        wrong = {(model, variant): (2, 0.5) for model in strat.MODELS for variant in strat.VARIANTS}
        with self.assertRaises(strat.ScoringError) as ctx:
            self.run_norm(reported=wrong)
        self.assertIn("nessun numero e' usabile", str(ctx.exception))

    def test_passes_when_reported_means_are_reproduced(self):
        reported = {(model, variant): (2, sum(SCORES[model][variant]) / 2)
                    for model in strat.MODELS for variant in strat.VARIANTS}
        report = self.run_norm(reported=reported)
        self.assertTrue(report["reproduction_of_reported_means"]["all_match"])

    def test_stops_when_n_differs_from_reported(self):
        reported = {(model, variant): (3, sum(SCORES[model][variant]) / 2)
                    for model in strat.MODELS for variant in strat.VARIANTS}
        with self.assertRaises(strat.ScoringError):
            self.run_norm(reported=reported)

    def test_incomplete_token_usage_on_scored_run_stops(self):
        with self.assertRaises(strat.ScoringError):
            self.run_norm(usage=lambda model, case, variant: not (model == "sonnet" and variant == "A1"))

    def test_source_hash_mismatch_is_counted_not_fatal(self):
        make_plan(self.dir, score_of)
        victim = next((self.dir / "data/results/evaluation20" / strat.PROTOCOL).glob("*sonnet*a1__r01.json"))
        victim.write_text(victim.read_text(encoding="utf-8") + " ", encoding="utf-8")
        report = m.run_normalization(self.dir, expected_runs=30, expected_cases=2, reported=None, draws=50)
        self.assertEqual(report["source_result_hash_mismatches"], 1)

    def snapshot(self):
        return {str(p.relative_to(self.dir)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(self.dir.rglob("*")) if p.is_file()}

    def test_frozen_inputs_stay_byte_identical_and_only_one_new_file_appears(self):
        make_plan(self.dir, score_of)
        before = self.snapshot()
        out = self.dir / "data" / "rq1_normalization_v1" / "normalization.json"
        runner = partial(m.run_normalization, expected_runs=30, expected_cases=2, reported=None, draws=50)
        with mock.patch.object(m, "run_normalization", runner), redirect_stdout(StringIO()):
            self.assertEqual(m.main(["--data-dir", str(self.dir), "--out", str(out)]), 0)
        after = self.snapshot()
        new = set(after) - set(before)
        self.assertEqual(new, {"data/rq1_normalization_v1/normalization.json"})
        self.assertEqual({k: after[k] for k in before}, before)   # nulla di preesistente e' cambiato

    def test_report_keeps_original_means_beside_the_normalized_values(self):
        report = self.run_norm()
        cell = report["summaries"]["score"]["sonnet"]["A1"]
        self.assertAlmostEqual(cell["mean"], 0.4)          # valore assoluto originale
        self.assertAlmostEqual(cell["ratio_vs_A0"], 2.0)   # normalizzato, nello stesso record
        self.assertEqual(cell["n"], 2)

    def test_bootstrap_is_deterministic_and_contains_point_estimate(self):
        a = self.run_norm(draws=300)["intervals"]["score"]["sonnet"]["A1"]
        shutil_dir = tempfile.TemporaryDirectory()
        self.addCleanup(shutil_dir.cleanup)
        self.dir = Path(shutil_dir.name)
        b = self.run_norm(draws=300)["intervals"]["score"]["sonnet"]["A1"]
        self.assertEqual(a, b)
        low, high = a["ratio_ci95"]
        self.assertLessEqual(low, 2.0)
        self.assertGreaterEqual(high, 2.0)
        self.assertLessEqual(a["difference_ci95"][0], 0.2)
        self.assertGreaterEqual(a["difference_ci95"][1], 0.2)

    def test_bootstrap_of_constant_scores_is_a_point(self):
        g = self.run_norm()["intervals"]["score"]["gemini"]["A1"]
        self.assertEqual(g["ratio_ci95"], [1.0, 1.0])
        self.assertEqual(g["difference_ci95"], [0.0, 0.0])

    def test_samples_are_fixed_by_seed(self):
        self.assertEqual(m.make_samples(list(CASES), 7, 5), m.make_samples(list(CASES), 7, 5))
        self.assertNotEqual(m.make_samples(list(CASES), 7, 20), m.make_samples(list(CASES), 8, 20))

    def test_no_ground_truth_and_no_provider_calls(self):
        report = self.run_norm()
        self.assertEqual(report["provider_calls"], 0)
        self.assertFalse(report["ground_truth_accessed"])
        self.assertFalse(any(self.dir.glob("*.zip")))   # nessun Market.zip: il modulo non lo apre

    def test_median_even_and_odd(self):
        self.assertEqual(m._median([3.0, 1.0, 2.0]), 2.0)
        self.assertEqual(m._median([4.0, 1.0, 2.0, 3.0]), 2.5)
        self.assertIsNone(m._median([]))

    def test_format_uses_decimal_comma_and_reports_n(self):
        text = m.format_report(self.run_norm())
        self.assertIn("0,200 (n=2) rif.", text)
        self.assertIn("2,00x", text)
        self.assertIn("Limiti:", text)

    def test_cli_is_create_only(self):
        make_plan(self.dir, score_of)
        out = self.dir / "out" / "normalization.json"
        runner = partial(m.run_normalization, expected_runs=30, expected_cases=2, reported=None, draws=50)
        with mock.patch.object(m, "run_normalization", runner):
            with redirect_stdout(StringIO()):
                self.assertEqual(m.main(["--data-dir", str(self.dir), "--out", str(out)]), 0)
            self.assertTrue(out.is_file())
            first = out.read_bytes()
            err = StringIO()
            with redirect_stdout(StringIO()), redirect_stderr(err):
                self.assertEqual(m.main(["--data-dir", str(self.dir), "--out", str(out)]), 2)
            self.assertEqual(out.read_bytes(), first)
            self.assertIn("STOP", err.getvalue())


if __name__ == "__main__":
    unittest.main()
