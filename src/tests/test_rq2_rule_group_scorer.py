"""Offline synthetic tests: no real fault labels, no Market, no providers."""
import copy
import unittest

from evaluation.rq2_rule_group_scorer import (
    GroupScoringError, evaluate_group_decisions,
)


TAXONOMY = ("fault_alpha", "fault_beta", "fault_gamma")


def cases():
    return [
        {"group_id": "G_SHARED", "case_ids": ["synthetic_q001", "synthetic_q002"],
         "fault_types": ["fault_alpha", "fault_beta"], "reference_complete": True},
        {"group_id": "G_BETA", "case_ids": ["synthetic_q003"],
         "fault_types": ["fault_beta"], "reference_complete": True},
        {"group_id": "G_NEG", "case_ids": ["synthetic_q004"],
         "fault_types": [], "reference_complete": True},
        {"group_id": "G_UNKNOWN", "case_ids": ["synthetic_q005"],
         "fault_types": [], "reference_complete": False},
    ]


def decisions():
    return {
        "G_SHARED": "positive", "G_BETA": "negative",
        "G_NEG": "negative", "G_UNKNOWN": "error",
    }


def score(target="fault_alpha", groups=None, predictions=None):
    return evaluate_group_decisions(
        target_fault_type=target, known_fault_types=TAXONOMY,
        group_references=cases() if groups is None else groups,
        group_decisions=decisions() if predictions is None else predictions,
    )


class RQ2RuleGroupScorerTests(unittest.TestCase):
    def test_multifault_group_is_positive_for_both_actual_labels(self):
        alpha = score("fault_alpha")
        beta = score("fault_beta")
        self.assertEqual(alpha["counts"]["tp"], 1)
        self.assertEqual(beta["counts"]["tp"], 1)
        self.assertEqual(alpha["counts"]["multi_fault_groups"], 1)
        self.assertEqual(beta["counts"]["multi_fault_groups"], 1)
        self.assertEqual(beta["counts"]["fn"], 1)
        self.assertEqual(alpha["counts"]["fn"], 0)

    def test_multifault_other_query_never_makes_negative(self):
        beta = score("fault_beta")
        self.assertEqual(beta["counts"]["complete_positive_groups"], 2)
        self.assertEqual(beta["counts"]["complete_negative_groups"], 1)
        self.assertEqual(beta["counts"]["tn"], 1)
        self.assertEqual(beta["counts"]["fp"], 0)

    def test_unknown_reference_is_not_assumed_healthy_negative(self):
        result = score()
        self.assertEqual(result["counts"]["reference_unscorable_groups"], 1)
        self.assertEqual(result["reference_complete_groups"], 3)
        self.assertEqual(result["hard_decisions"], 3)

    def test_abstention_is_not_falsely_converted_to_fn(self):
        guesses = decisions()
        guesses["G_SHARED"] = "abstain"
        report = score(predictions=guesses)
        self.assertEqual(report["counts"]["abstain_positive"], 1)
        self.assertEqual(report["counts"]["fn"], 0)
        self.assertEqual(report["hard_decisions"], 2)
        self.assertAlmostEqual(report["decision_coverage"], 2 / 3)

    def test_error_is_not_falsely_converted_to_fn(self):
        guesses = decisions()
        guesses["G_SHARED"] = "error"
        report = score(predictions=guesses)
        self.assertEqual(report["counts"]["error_positive"], 1)
        self.assertEqual(report["counts"]["fn"], 0)
        self.assertEqual(report["hard_decisions"], 2)

    def test_conditional_rates_are_undefined_if_no_hard_decisions(self):
        guesses = {k:"abstain" for k in decisions()}
        report = score(predictions=guesses)
        self.assertEqual(report["hard_decisions"], 0)
        self.assertEqual(report["decision_coverage"], 0.0)
        self.assertIsNone(report["recall_on_hard_decisions"])
        self.assertIsNone(report["precision_on_hard_decisions"])
        self.assertIsNone(report["specificity_on_hard_decisions"])

    def test_confusion_counts_are_per_group_not_per_query(self):
        report = score()
        self.assertEqual(report["total_window_groups"], 4)
        self.assertEqual(report["hard_decisions"], 3)
        self.assertEqual(report["counts"]["complete_positive_groups"], 1)
        self.assertEqual(report["counts"]["complete_negative_groups"], 2)
        self.assertNotIn("case_ids", report)
        self.assertNotIn("group_references", report)

    def test_invalid_duplicate_case_across_groups_rejected(self):
        groups = cases()
        groups[2]["case_ids"].append("synthetic_q001")
        with self.assertRaisesRegex(GroupScoringError, "cross-group"):
            score(groups=groups)

    def test_missing_or_extra_group_prediction_rejected(self):
        values = decisions()
        values.pop("G_SHARED")
        with self.assertRaisesRegex(GroupScoringError, "Missing/extra"):
            score(predictions=values)
        values = decisions()
        values["G_UNKNOWN_ADDED"] = "positive"
        with self.assertRaisesRegex(GroupScoringError, "Missing/extra"):
            score(predictions=values)

    def test_duplicate_group_id_rejected(self):
        groups = cases()
        groups[1]["group_id"] = "G_SHARED"
        with self.assertRaisesRegex(GroupScoringError, "Duplicate group"):
            score(groups=groups)

    def test_reference_mapping_with_unexpected_field_rejected(self):
        groups = cases()
        groups[0]["source_gt_file"] = "synthetic_source"
        with self.assertRaisesRegex(GroupScoringError, "Unrecognized"):
            score(groups=groups)

    def test_malformed_completeness_rejected(self):
        groups = cases()
        groups[0]["reference_complete"] = "false"
        with self.assertRaisesRegex(GroupScoringError, "boolean"):
            score(groups=groups)

    def test_fault_type_outside_taxonomy_rejected(self):
        groups = cases()
        groups[0]["fault_types"] = ["invented_fault_type"]
        with self.assertRaisesRegex(GroupScoringError, "Unsupported"):
            score(groups=groups)

    def test_target_not_in_taxonomy_rejected(self):
        with self.assertRaisesRegex(GroupScoringError, "Target not"):
            score("unknown_target")

    def test_decision_outside_closed_vocabulary_rejected(self):
        values = decisions()
        values["G_SHARED"] = "I THINK POSITIVE"
        with self.assertRaisesRegex(GroupScoringError, "invalid group decision"):
            score(predictions=values)

    def test_false_positive_counts_against_other_faults(self):
        guesses = decisions()
        guesses["G_SHARED"] = "negative"
        guesses["G_BETA"] = "positive"
        report = score(predictions=guesses)
        self.assertEqual(report["counts"]["fn"], 1)
        self.assertEqual(report["counts"]["fp"], 1)
        self.assertEqual(report["counts"]["tn"], 1)
        self.assertEqual(report["counts"]["tp"], 0)

    def test_healthy_control_group_is_negative_when_complete(self):
        groups = [{
            "group_id": "G_HEALTHY", "case_ids": ["synthetic_healthy"],
            "fault_types": [], "reference_complete": True,
        }]
        report = score(groups=groups, predictions={"G_HEALTHY": "negative"})
        self.assertEqual(report["counts"]["tn"], 1)
        self.assertEqual(report["reference_complete_groups"], 1)

    def test_unscorable_only_groups_have_undefined_coverage(self):
        groups = [{
            "group_id": "G_AMBIG", "case_ids": ["synthetic_ambiguous"],
            "fault_types": ["fault_alpha"], "reference_complete": False
        }]
        report = score(groups=groups, predictions={"G_AMBIG": "positive"})
        self.assertIsNone(report["decision_coverage"])
        self.assertEqual(report["counts"]["reference_unscorable_groups"], 1)

    def test_report_does_not_export_per_case_labels(self):
        report = score()
        string = str(report)
        self.assertNotIn("synthetic_q001", string)
        self.assertNotIn("G_SHARED", string)
        self.assertFalse(report["files_written"])
        self.assertEqual(report["model_api_calls"], 0)
        self.assertTrue(report["reads_ground_truth_from_caller"])

    def test_empty_taxonomy_and_bad_group_list_refused(self):
        with self.assertRaises(GroupScoringError):
            evaluate_group_decisions(
                target_fault_type="fault_alpha", known_fault_types=(),
                group_references=cases(), group_decisions=decisions(),
            )
        with self.assertRaises(GroupScoringError):
            score(groups=[])


if __name__ == "__main__":
    unittest.main()
