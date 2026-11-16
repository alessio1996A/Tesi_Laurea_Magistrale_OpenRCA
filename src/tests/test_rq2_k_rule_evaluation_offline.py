"""Test offline di valutazione e lettura dei record K (dati completamente sintetici).

Nessuna API, nessuna telemetria reale, nessun caso sigillato, nessuna etichetta reale.
"""
import json
import tempfile
import unittest
from pathlib import Path

from evaluation import rq2_k_records as rec
from evaluation import rq2_k_rule_evaluation as ev

CLASSES = ("cls_a", "cls_b", "cls_c")
H_PRE, H = 60, 300


def _group(gid, types, faults=None, complete=True):
    faults = faults if faults is not None else [
        {"component": f"comp-{gid}", "t_gt": 1000, "fault_type": t} for t in types]
    return {"group_id": gid, "case_ids": [f"case-{gid}"], "fault_types": list(types),
            "reference_complete": complete, "faults": faults}


def _hit(component, t):
    return {"decision": "positive", "first_fire_unix_by_component": {component: t}}


NEG = {"decision": "negative", "first_fire_unix_by_component": {}}
ABS = {"decision": "abstain", "first_fire_unix_by_component": {}}


def _evaluate(groups, results, **kw):
    return ev.evaluate_rule(target_fault_type="cls_a", known_fault_types=CLASSES,
                            group_references=groups, group_results=results,
                            h_pre_seconds=H_PRE, h_seconds=H, **kw)


class IntervalTests(unittest.TestCase):
    def test_perfect_results_give_the_documented_lower_bounds(self):
        for n, expected in ((2, 0.1581), (3, 0.2924), (4, 0.3976)):
            lower, upper = ev.clopper_pearson(n, n)
            self.assertAlmostEqual(lower, expected, places=3)
            self.assertEqual(upper, 1.0)

    def test_zero_successes_and_empty_denominator(self):
        lower, upper = ev.clopper_pearson(0, 4)
        self.assertEqual(lower, 0.0)
        self.assertAlmostEqual(upper, 0.6024, places=3)
        self.assertEqual(ev.clopper_pearson(0, 0), (None, None))


class VerdictTests(unittest.TestCase):
    def _base(self):
        groups = [_group("p1", ["cls_a"]), _group("p2", ["cls_a"]),
                  _group("n1", ["cls_b"]), _group("n2", ["cls_c"]), _group("n3", ["cls_b"])]
        results = {"p1": _hit("comp-p1", 1100), "p2": _hit("comp-p2", 1000),
                   "n1": NEG, "n2": NEG, "n3": NEG}
        return groups, results

    def test_verified_on_the_sample(self):
        groups, results = self._base()
        out = _evaluate(groups, results, rules_tested=60)
        self.assertEqual(out["verdict"], ev.VERIFIED)
        self.assertEqual(out["detection"]["tp_localized"], 2)
        self.assertEqual(out["rules_tested"], 60)
        self.assertIn("campione", out["caveat"].lower())

    def test_false_negative(self):
        groups, results = self._base()
        results["p2"] = NEG
        out = _evaluate(groups, results)
        self.assertEqual((out["verdict"], out["reasons"]), (ev.NOT_VERIFIED, ["false_negative"]))

    def test_false_positive_prevails_over_coverage(self):
        groups, results = self._base()
        results["n1"] = _hit("comp-n1", 1000)
        results["n2"] = ABS
        results["n3"] = ABS
        out = _evaluate(groups, results)
        self.assertEqual(out["verdict"], ev.NOT_VERIFIED)
        self.assertIn("false_positive", out["reasons"])

    def test_detected_in_the_wrong_component_is_not_verified(self):
        groups, results = self._base()
        results["p1"] = _hit("altro-componente", 1100)
        out = _evaluate(groups, results)
        self.assertEqual(out["verdict"], ev.NOT_VERIFIED)
        self.assertEqual(out["reasons"], ["detected_but_not_localized_or_timed"])
        self.assertEqual(out["localization_by_group"]["p1"]["outcomes"], ["component_not_firing"])

    def test_time_window_edges(self):
        for first, ok in ((1000 - H_PRE, True), (1000 - H_PRE - 1, False),
                          (1000 + H, True), (1000 + H + 1, False)):
            groups, results = self._base()
            results["p1"] = _hit("comp-p1", first)
            out = _evaluate(groups, results)
            self.assertEqual(out["verdict"] == ev.VERIFIED, ok, first)

    def test_abstention_on_a_positive_is_not_evaluable_not_failed(self):
        groups, results = self._base()
        results["p2"] = ABS
        out = _evaluate(groups, results)
        self.assertEqual(out["verdict"], ev.NOT_EVALUABLE)
        self.assertIn("abstention_or_error_on_positives", out["reasons"])

    def test_systematic_abstention_on_negatives_does_not_pass(self):
        groups, results = self._base()
        results.update({"n1": ABS, "n2": ABS})          # 1 negativo coperto su 3 < 2/3
        out = _evaluate(groups, results)
        self.assertEqual(out["verdict"], ev.NOT_EVALUABLE)
        self.assertAlmostEqual(out["coverage"]["negatives"], 1 / 3)
        self.assertEqual(out["coverage"]["abstain_negative"], 2)

    def test_exactly_two_thirds_negative_coverage_passes_the_exploratory_threshold(self):
        groups, results = self._base()
        results["n3"] = ABS                              # 2 su 3
        self.assertEqual(_evaluate(groups, results)["verdict"], ev.VERIFIED)

    def test_unscorable_group_leaves_the_denominators(self):
        groups, results = self._base()
        groups.append(_group("u1", [], faults=[], complete=False))
        results["u1"] = _hit("x", 1)                     # sarebbe un FP, ma non e' valutabile
        out = _evaluate(groups, results)
        self.assertEqual(out["verdict"], ev.VERIFIED)
        self.assertEqual(out["coverage"]["unscorable_groups"], 1)

    def test_multi_fault_group_is_positive_for_each_class_present(self):
        both = _group("m1", ["cls_a", "cls_b"], faults=[
            {"component": "comp-a", "t_gt": 1000, "fault_type": "cls_a"},
            {"component": "comp-b", "t_gt": 1000, "fault_type": "cls_b"}])
        groups = [both, _group("p2", ["cls_a"]), _group("n1", ["cls_c"]),
                  _group("n2", ["cls_c"]), _group("n3", ["cls_c"])]
        results = {"m1": _hit("comp-a", 1000), "p2": _hit("comp-p2", 1000),
                   "n1": NEG, "n2": NEG, "n3": NEG}
        self.assertEqual(_evaluate(groups, results)["verdict"], ev.VERIFIED)

    def test_missing_result_counts_as_error_not_as_negative(self):
        groups, results = self._base()
        del results["p1"]
        out = _evaluate(groups, results)
        self.assertEqual(out["counts"]["error_positive"], 1)
        self.assertEqual(out["verdict"], ev.NOT_EVALUABLE)

    def test_other_components_firing_is_reported_not_penalised(self):
        groups, results = self._base()
        results["p1"] = {"decision": "positive", "first_fire_unix_by_component":
                         {"comp-p1": 1000, "vicino-1": 1000, "vicino-2": 1010}}
        out = _evaluate(groups, results)
        self.assertEqual(out["verdict"], ev.VERIFIED)
        self.assertEqual(out["localization_by_group"]["p1"]["other_components_firing"], 2)

    def test_parameters_must_be_integer_seconds(self):
        groups, results = self._base()
        with self.assertRaises(ValueError):
            ev.evaluate_rule(target_fault_type="cls_a", known_fault_types=CLASSES,
                             group_references=groups, group_results=results,
                             h_pre_seconds=60, h_seconds=0)


class RecordReaderTests(unittest.TestCase):
    def _record(self, stage_id, status="RECORDED_COMPLETE", raw=None):
        art = {} if raw is None else {"raw_response": raw}
        return {"stage_id": stage_id, "status": status, "receipt": {"artifact": art}}

    def test_candidate_is_extracted_and_other_outcomes_are_counted(self):
        cand = json.dumps({"status": "candidate", "conditions": []})
        abst = json.dumps({"status": "insufficient_evidence"})
        plan = "plan_x"
        records = [
            self._record(f"{plan}:cloudbed-1_q032:gemini:A0:K", raw=cand),
            self._record(f"{plan}:cloudbed-1_q032:gemini:A1:K", raw=abst),
            self._record(f"{plan}:cloudbed-1_q032:haiku:A1:K", status="INVALID_OUTPUT"),
            self._record(f"{plan}:cloudbed-1_q032:haiku:A0:K", raw="non json"),
            self._record(f"{plan}:cloudbed-1_q032:sonnet:A0:K"),                 # niente testo
            self._record(f"{plan}:cloudbed-1_q032:gemini:A0:D", raw=cand),       # non e' K
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for i, r in enumerate(records):
                (Path(tmp) / f"V5_RECORD_{i}.json").write_text(json.dumps(r), encoding="utf-8")
            entries = rec.load_k_entries(Path(tmp))
        summary = rec.summarize(entries)
        self.assertEqual(summary["k_stages"], 5)
        self.assertEqual(summary["candidates"], 1)
        outcomes = {e["stage_id"].split(":", 2)[2]: e["outcome"] for e in entries}
        self.assertEqual(outcomes["gemini:A0:K"], "candidate")
        self.assertEqual(outcomes["gemini:A1:K"], "insufficient_evidence")
        self.assertEqual(outcomes["haiku:A1:K"], "not_complete:INVALID_OUTPUT")
        self.assertEqual(outcomes["haiku:A0:K"], "unreadable_json")
        self.assertEqual(outcomes["sonnet:A0:K"], "no_raw_text")
        self.assertIsNotNone(next(e for e in entries if e["outcome"] == "candidate")["rule"])

    def test_bad_stage_id_is_refused(self):
        with self.assertRaises(ValueError):
            rec.parse_stage_id("troppo:corto")

    def test_stage_id_with_and_without_plan_prefix(self):
        expected = {"case_id": "cloudbed-1_q032", "model": "gemini", "harness": "A1_8R", "stage": "K"}
        self.assertEqual(rec.parse_stage_id("cloudbed-1_q032:gemini:A1_8R:K"), expected)
        self.assertEqual(rec.parse_stage_id("plan_v5:cloudbed-1_q032:gemini:A1_8R:K"), expected)


if __name__ == "__main__":
    unittest.main()
