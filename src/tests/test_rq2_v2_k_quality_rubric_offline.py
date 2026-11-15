"""Test sintetici della rubrica K preregistrata: nessun dataset/API/GT.

La verifica controlla il comportamento MECCANICO. Non prova che una regola
sintetica sia una vera diagnosi o sia trasferibile agli OOD.
"""
from __future__ import annotations

import json
import unittest

from evaluation.rq2_v2_k_quality_rubric import (
    KQualityReviewBlocked, evaluate_k_quality,
)
from evaluation.rq2_v2_unified_release_preflight import SOURCE_PATHS


TOOL = "tool_metric_query"
ALLOW = {TOOL}


def trajectory(*observations):
    result = []
    for index, text in enumerate(observations, start=1):
        cid = f"synthetic_call_{index}"
        result.extend([
            {
                "tipo": "tool_call", "nome": TOOL,
                "parametri": {"synthetic_index": index},
                "tool_call_id": cid, "origine": "llm",
            },
            {
                "tipo": "tool_result", "nome": TOOL,
                "risposta": text,
                "tool_call_id": cid, "origine": "llm",
            },
        ])
    return result


def rule():
    return {
        "schema_version": "rq2_candidate_rule_v0",
        "status": "candidate",
        "hypothesized_fault_type": "synthetic_unverified_pressure",
        "rule_name": "synthetic_metric_rule",
        "scope": "synthetic",
        "evidence_ids": ["E001"],
        "required_signals": [{
            "metric": "cpu_utilization", "unit": "percent",
            "aggregation": "max", "window_seconds": 300,
        }],
        "conditions": [{
            "metric": "cpu_utilization", "unit": "percent",
            "aggregation": "max", "window_seconds": 300,
            "operator": ">", "threshold": 80,
        }],
        "combination": "all",
        "abstain_when": ["missing metric"],
        "counterexamples": ["synthetic transient spike"],
        "limitations": ["not a proven cause"],
        "pseudocode": "NO_EXECUTION_EVER: IF cpu_utilization > 80",
    }


def evaluate(obj, *texts):
    return evaluate_k_quality(
        json.dumps(obj), tool_trajectory=trajectory(*texts),
        allowed_tool_names=ALLOW,
    )


class KQualityPreregdOfflineTests(unittest.TestCase):

    def test_new_rubric_is_in_source_fingerprint(self):
        self.assertIn(
            "evaluation/rq2_v2_k_quality_rubric.py", SOURCE_PATHS,
        )
        self.assertEqual(len(SOURCE_PATHS), len(set(SOURCE_PATHS)))

    def test_candidate_with_literal_metric_and_unit_requires_verification(self):
        result = evaluate(rule(), "cpu_utilization=92 percent at t=1")
        self.assertEqual(result["k_outcome"], "CANDIDATE")
        self.assertEqual(result["formalizability_review"], "REQUIRES_VERIFICATION")
        self.assertEqual(result["cited_evidence_count"], 1)
        self.assertEqual(result["cited_nonempty_observations"], 1)
        self.assertEqual(result["signal_metric_literal_matches"], 1)
        self.assertEqual(result["signal_metric_unit_literal_matches"], 1)
        self.assertFalse(result["diagnostic_correctness_verified"])
        self.assertFalse(result["causal_transfer_verified"])
        self.assertFalse(result["physical_units_verified"])
        self.assertFalse(result["thresholds_empirically_validated"])
        self.assertFalse(result["ood_test_performed"])

    def test_valid_schema_does_not_imply_good_evidence(self):
        result = evaluate(rule(), "no metric measurements")
        self.assertEqual(result["k_outcome"], "CANDIDATE")
        self.assertEqual(result["signal_metric_literal_matches"], 0)
        self.assertEqual(result["signal_metric_unit_literal_matches"], 0)
        self.assertEqual(result["formalizability_review"], "REQUIRES_VERIFICATION")

    def test_literal_match_is_not_substring_match(self):
        result = evaluate(rule(), "my_cpu_utilization_extra=99 percent")
        self.assertEqual(result["signal_metric_literal_matches"], 0)
        self.assertEqual(result["signal_metric_unit_literal_matches"], 0)

    def test_unit_must_match_in_same_cited_observation_as_metric(self):
        item = rule()
        item["evidence_ids"] = ["E001", "E002"]
        result = evaluate(item, "cpu_utilization=92", "unit is percent")
        self.assertEqual(result["signal_metric_literal_matches"], 1)
        self.assertEqual(result["signal_metric_unit_literal_matches"], 0)
        self.assertEqual(result["cited_evidence_count"], 2)

    def test_non_cited_observation_does_not_provide_signal_support(self):
        result = evaluate(rule(), "synthetic log without measurements",
                          "cpu_utilization=92 percent")
        self.assertEqual(result["signal_metric_literal_matches"], 0)

    def test_empty_observation_does_not_count_as_support(self):
        result = evaluate(rule(), "")
        self.assertEqual(result["cited_nonempty_observations"], 0)
        self.assertEqual(result["signal_metric_literal_matches"], 0)

    def test_truncated_evidence_is_not_silently_complete(self):
        result = evaluate(rule(), "cpu_utilization=92 percent " + "z" * 5000)
        self.assertEqual(result["cited_truncated_observations"], 1)

    def test_all_impossible_strict_bounds_not_formalizable(self):
        item = rule()
        item["conditions"].append({
            **item["conditions"][0], "operator": "<=", "threshold": 80,
        })
        result = evaluate(item, "cpu_utilization=92 percent")
        self.assertTrue(result["contradictory_all_conditions"])
        self.assertEqual(
            result["formalizability_review"],
            "NOT_FORMALIZABLE_CONTRADICTION",
        )

    def test_two_different_equalities_are_contradictory(self):
        item = rule()
        item["conditions"] = [
            {**item["conditions"][0], "operator": "==", "threshold": x}
            for x in (3, 4)
        ]
        result = evaluate(item, "cpu_utilization=92 percent")
        self.assertTrue(result["contradictory_all_conditions"])

    def test_any_alternatives_not_false_contradiction(self):
        item = rule()
        item["combination"] = "any"
        item["conditions"].append({
            **item["conditions"][0], "operator": "<=", "threshold": 80,
        })
        result = evaluate(item, "cpu_utilization=92 percent")
        self.assertFalse(result["contradictory_all_conditions"])
        self.assertEqual(result["formalizability_review"], "REQUIRES_VERIFICATION")

    def test_different_signals_do_not_make_all_contradictory(self):
        item = rule()
        another = {
            "metric": "error_rate", "unit": "percent",
            "aggregation": "max", "window_seconds": 300,
        }
        item["required_signals"].append(another)
        item["conditions"].append({
            **another, "operator": "<=", "threshold": 10,
        })
        result = evaluate(item, "cpu_utilization=92 percent, error_rate=3 percent")
        self.assertFalse(result["contradictory_all_conditions"])
        self.assertEqual(result["required_signal_count"], 2)

    def test_insufficient_evidence_is_not_invalid(self):
        item = rule()
        item.update({
            "status": "insufficient_evidence", "rule_name": None,
            "pseudocode": None, "combination": None, "required_signals": [],
            "conditions": [], "evidence_ids": [],
        })
        result = evaluate(item, "no measured signal")
        self.assertEqual(result["k_outcome"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(result["formalizability_review"], "NOT_APPLICABLE")

    def test_invalid_output_is_not_repaired(self):
        result = evaluate_k_quality(
            "invalid-not-json",
            tool_trajectory=trajectory("cpu_utilization=92 percent"),
            allowed_tool_names=ALLOW,
        )
        self.assertEqual(result["k_outcome"], "INVALID_OUTPUT")
        self.assertEqual(result["formalizability_review"], "NOT_APPLICABLE")

    def test_unknown_evidence_is_invalid_not_success(self):
        item = rule()
        item["evidence_ids"] = ["E999"]
        result = evaluate(item, "cpu_utilization=92 percent")
        self.assertEqual(result["k_outcome"], "INVALID_OUTPUT")

    def test_ambiguous_or_unmatched_d_provenance_blocks_review(self):
        items = trajectory("cpu_utilization=92 percent")
        items[1]["tool_call_id"] = "different"
        with self.assertRaises(KQualityReviewBlocked):
            evaluate_k_quality(
                json.dumps(rule()), tool_trajectory=items,
                allowed_tool_names=ALLOW,
            )

    def test_scoring_reference_in_k_blocks_instead_of_leaking_gt(self):
        item = rule()
        item["limitations"].append("see ground_truth labels")
        with self.assertRaises(KQualityReviewBlocked):
            evaluate(item, "cpu_utilization=92 percent")

    def test_pseudocode_not_evaluated_and_no_api_or_file_writes(self):
        item = rule()
        item["pseudocode"] = "__import__('os').system('THIS_MUST_NOT_EXECUTE')"
        result = evaluate(item, "cpu_utilization=92 percent")
        self.assertFalse(result["record_or_files_written"])
        self.assertEqual(result["api_calls_sent"], 0)
        self.assertNotIn("pseudocode", result)
        self.assertNotIn("raw_response", result)


if __name__ == "__main__":
    unittest.main()
