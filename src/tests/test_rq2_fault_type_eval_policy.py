"""Offline-only synthetic RQ2-A cause scoring preregistration tests."""
from __future__ import annotations

import unittest
from evaluation import rq2_fault_type_eval_policy as subject

IDS = ("SYNTHETIC_A", "SYNTHETIC_B", "SYNTHETIC_C", "SYNTHETIC_D")
REF = dict(zip(IDS, subject.CANONICAL))


def diagnosis(i, label):
    return {"case_id": IDS[i], "stage_status": "RECORDED_COMPLETE",
            "decision": "diagnosis", "predicted_fault_type": label}


def abstain(i):
    return {"case_id": IDS[i], "stage_status": "RECORDED_COMPLETE",
            "decision": "abstain", "predicted_fault_type": None}


def failed(i, status):
    return {"case_id": IDS[i], "stage_status": status,
            "decision": None, "predicted_fault_type": None}


class RQ2FaultTypeEvalPolicyOfflineTests(unittest.TestCase):
    def test_official_four_exact_labels(self):
        for label in subject.CANONICAL:
            with self.subTest(label=label):
                self.assertEqual(subject.canonical_fault_type(label), label)

    def test_lexical_case_whitespace_punctuation_variants_only(self):
        self.assertEqual(subject.canonical_fault_type("  NODE---Cpu  SPIKE  "),
                         subject.CANONICAL[0])
        self.assertEqual(subject.canonical_fault_type("container write IO load"),
                         subject.CANONICAL[1])

    def test_no_fuzzy_or_semantic_match(self):
        for label in ("high node cpu", "cpu overload", "network packet drop",
                      "container killed", "process exited", "unknown fault", ""):
            self.assertIsNone(subject.canonical_fault_type(label))

    def test_full_perfect_predictions(self):
        predictions = [diagnosis(i, name) for i, name in enumerate(subject.CANONICAL)]
        report = subject.score_cause_cases(case_ids=IDS, reference_labels=REF,
                                           predictions=predictions)
        self.assertEqual(report["total_planned"], 4)
        self.assertEqual(report["accuracy_planned"], 1)
        self.assertEqual(report["diagnostic_coverage_planned"], 1)
        self.assertEqual(report["counts"]["correct"], 4)
        self.assertFalse(report["reference_labels_exported"])
        self.assertFalse(report["case_label_mapping_exported"])

    def test_error_abstain_missing_and_wrong_all_count_in_planned(self):
        predictions = [
            diagnosis(0, "node CPU spike"),
            abstain(1),
            failed(2, "PROVIDER_ERROR"),
        ]
        report = subject.score_cause_cases(case_ids=IDS, reference_labels=REF,
                                           predictions=predictions)
        self.assertEqual(report["counts"]["correct"], 1)
        self.assertEqual(report["counts"]["abstain"], 1)
        self.assertEqual(report["counts"]["provider_error"], 1)
        self.assertEqual(report["counts"]["missing"], 1)
        self.assertEqual(report["accuracy_planned"], .25)
        self.assertEqual(report["accuracy_among_diagnoses"], 1)
        self.assertEqual(report["accuracy_among_valid_contracts"], .5)

    def test_wrong_known_and_unmatched_are_not_abstentions(self):
        report = subject.score_cause_cases(
            case_ids=IDS, reference_labels=REF,
            predictions=[diagnosis(0, subject.CANONICAL[3]),
                         diagnosis(1, "unknown technical problem")]
        )
        self.assertEqual(report["counts"]["wrong_known_class"], 1)
        self.assertEqual(report["counts"]["unmatched_diagnosis"], 1)
        self.assertEqual(report["counts"]["abstain"], 0)
        self.assertEqual(report["accuracy_among_diagnoses"], 0)

    def test_empty_prediction_list_stays_planned_denominator(self):
        report = subject.score_cause_cases(case_ids=IDS, reference_labels=REF,
                                           predictions=[])
        self.assertEqual(report["counts"]["missing"], 4)
        self.assertEqual(report["accuracy_planned"], 0)
        self.assertIsNone(report["accuracy_among_diagnoses"])

    def test_invalid_status_and_dependency_counts(self):
        report = subject.score_cause_cases(
            case_ids=IDS, reference_labels=REF,
            predictions=[failed(0, "INVALID_OUTPUT"),
                         failed(1, "BLOCKED_DEPENDENCY")]
        )
        self.assertEqual(report["counts"]["invalid_output"], 1)
        self.assertEqual(report["counts"]["blocked_dependency"], 1)

    def test_no_case_gt_mapping_in_results(self):
        report = subject.score_cause_cases(
            case_ids=IDS, reference_labels=REF, predictions=[diagnosis(0, REF[IDS[0]])]
        )
        self.assertFalse(any(cid in str(report) for cid in IDS))

    def test_incomplete_ground_truth_fails_closed(self):
        wrong = {k: v for k, v in REF.items() if k != IDS[3]}
        with self.assertRaises(subject.RQ2FaultEvalError):
            subject.score_cause_cases(case_ids=IDS, reference_labels=wrong, predictions=[])

    def test_unofficial_ground_truth_class_fails_closed(self):
        with self.assertRaises(subject.RQ2FaultEvalError):
            subject.score_cause_cases(
                case_ids=IDS,
                reference_labels={**REF, IDS[0]: "cpu overheating"},
                predictions=[],
            )

    def test_duplicate_predictions_fails_closed(self):
        with self.assertRaises(subject.RQ2FaultEvalError):
            subject.score_cause_cases(
                case_ids=IDS, reference_labels=REF,
                predictions=[diagnosis(0, "node cpu spike"),
                             diagnosis(0, "node cpu spike")],
            )

    def test_failed_stage_cannot_contain_prediction(self):
        with self.assertRaises(subject.RQ2FaultEvalError):
            subject.score_cause_cases(
                case_ids=IDS, reference_labels=REF,
                predictions=[{"case_id": IDS[0], "stage_status": "PROVIDER_ERROR",
                              "decision": "diagnosis",
                              "predicted_fault_type": "node CPU spike"}],
            )

    def test_abstain_cannot_assign_class(self):
        with self.assertRaises(subject.RQ2FaultEvalError):
            subject.score_cause_cases(
                case_ids=IDS, reference_labels=REF,
                predictions=[{"case_id": IDS[0], "stage_status": "RECORDED_COMPLETE",
                              "decision": "abstain",
                              "predicted_fault_type": "node CPU spike"}],
            )

    def test_pairwise_win_loss_and_ties(self):
        a1 = [diagnosis(0, REF[IDS[0]]),
              diagnosis(1, REF[IDS[0]]),
              abstain(2),
              diagnosis(3, REF[IDS[3]])]
        a8 = [diagnosis(0, REF[IDS[0]]),
              diagnosis(1, REF[IDS[1]]),
              failed(2, "INVALID_OUTPUT"),
              diagnosis(3, REF[IDS[0]])]
        report = subject.paired_harness_outcomes(
            case_ids=IDS, reference_labels=REF, a1=a1, a1_8r=a8,
        )
        self.assertEqual(report["counts"]["win_A1_8R"], 1)
        self.assertEqual(report["counts"]["loss_A1_8R"], 1)
        self.assertEqual(report["counts"]["tie"], 2)
        self.assertFalse(report["reference_labels_exported"])

    def test_all_decisions_are_explicitly_scoped_to_offline_evaluation(self):
        self.assertIn("candidate", subject.VERSION)
        self.assertEqual(len(subject.CANONICAL), 4)
        self.assertNotIn("guess", subject._VALID_STATUSES)


if __name__ == "__main__":
    unittest.main()
