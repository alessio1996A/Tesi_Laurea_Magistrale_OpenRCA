"""Synthetic RQ2 C/K JSON contracts tests. No model, GT or real data."""
import json
import unittest

from evaluation.rq2_output_contracts import (
    ContractError, validate_cause_probe, validate_candidate_rule,
)


class RQ2OutputContractsTests(unittest.TestCase):
    @staticmethod
    def cause():
        return {
            "schema_version": "rq2_cause_probe_v0",
            "decision": "diagnosis",
            "predicted_fault_type": "synthetic arbitrary fault type",
            "predicted_component": "synthetic-container",
            "confidence": "low",
            "evidence_ids": ["E001"],
            "alternatives": ["other possible issue"],
            "limitations": ["correlation not necessarily causation"],
        }

    @staticmethod
    def rule():
        return {
            "schema_version": "rq2_candidate_rule_v0",
            "status": "candidate",
            "hypothesized_fault_type": "synthetic arbitrary fault type",
            "rule_name": "synthetic example",
            "scope": "container: synthetic",
            "evidence_ids": ["E001"],
            "required_signals": [
                {"metric": "synthetic.metric", "unit": "units",
                 "aggregation": "max", "window_seconds": 300},
            ],
            "conditions": [
                {"metric": "synthetic.metric", "operator": ">",
                 "threshold": 1.0, "unit": "units",
                 "aggregation": "max", "window_seconds": 300},
            ],
            "combination": "all",
            "abstain_when": ["no metric observed"],
            "counterexamples": ["unrelated load"],
            "limitations": ["not independently validated"],
            "pseudocode": "IF synthetic_metric > 1 THEN report candidate",
        }

    def test_valid_diagnosis_and_unseen_fault_name(self):
        data = self.cause()
        self.assertEqual(
            validate_cause_probe(json.dumps(data), allowed_evidence_ids={"E001"}),
            data
        )

    def test_valid_abstention_without_evidence(self):
        data = self.cause()
        data.update({
            "decision": "abstain", "predicted_fault_type": None,
            "predicted_component": None, "confidence": "unassessed",
            "evidence_ids": [], "alternatives": [],
        })
        self.assertEqual(
            validate_cause_probe(json.dumps(data), allowed_evidence_ids=set()),
            data
        )

    def test_diagnosis_requires_real_evidence_reference(self):
        data = self.cause()
        data["evidence_ids"] = ["E999"]
        with self.assertRaisesRegex(ContractError, "Unknown/malformed"):
            validate_cause_probe(json.dumps(data), allowed_evidence_ids={"E001"})

    def test_abstention_with_assumed_cause_is_rejected(self):
        data = self.cause()
        data["decision"] = "abstain"
        with self.assertRaisesRegex(ContractError, "Abstention"):
            validate_cause_probe(json.dumps(data), allowed_evidence_ids={"E001"})

    def test_unexpected_gt_field_not_permitted(self):
        data = self.cause()
        data["scoring_points"] = "do not expose benchmark scoring"
        with self.assertRaisesRegex(ContractError, "expected fields"):
            validate_cause_probe(json.dumps(data), allowed_evidence_ids={"E001"})

    def test_duplicate_json_keys_rejected(self):
        raw = json.dumps(self.cause())
        raw = raw.replace('"schema_version":', '"schema_version":"bogus","schema_version":', 1)
        with self.assertRaisesRegex(ContractError, "Duplicate JSON key"):
            validate_cause_probe(raw, allowed_evidence_ids={"E001"})

    def test_markdown_wrapping_rejected(self):
        raw = chr(96) * 3 + "json\n" + json.dumps(self.cause()) + "\n" + chr(96) * 3
        with self.assertRaises(ContractError):
            validate_cause_probe(raw, allowed_evidence_ids={"E001"})

    def test_valid_candidate_rule(self):
        data = self.rule()
        self.assertEqual(
            validate_candidate_rule(json.dumps(data), allowed_evidence_ids=["E001"]),
            data
        )

    def test_valid_insufficient_evidence(self):
        data = self.rule()
        data.update({
            "status": "insufficient_evidence",
            "hypothesized_fault_type": None,
            "rule_name": None, "scope": None, "evidence_ids": [],
            "required_signals": [], "conditions": [], "combination": None,
            "pseudocode": None,
        })
        self.assertEqual(
            validate_candidate_rule(json.dumps(data), allowed_evidence_ids=[]),
            data
        )

    def test_mismatched_signal_and_condition_rejected(self):
        data = self.rule()
        data["conditions"][0]["unit"] = "milliseconds"
        with self.assertRaisesRegex(ContractError, "no matching"):
            validate_candidate_rule(json.dumps(data), allowed_evidence_ids={"E001"})

    def test_boolean_threshold_rejected(self):
        data = self.rule()
        data["conditions"][0]["threshold"] = True
        with self.assertRaisesRegex(ContractError, "finite number"):
            validate_candidate_rule(json.dumps(data), allowed_evidence_ids={"E001"})

    def test_nan_threshold_rejected(self):
        data = self.rule()
        data["conditions"][0]["threshold"] = float("nan")
        with self.assertRaises(ContractError):
            validate_candidate_rule(json.dumps(data), allowed_evidence_ids={"E001"})

    def test_unsupported_operator_rejected(self):
        data = self.rule()
        data["conditions"][0]["operator"] = "exec"
        with self.assertRaisesRegex(ContractError, "Unsupported comparator"):
            validate_candidate_rule(json.dumps(data), allowed_evidence_ids={"E001"})

    def test_insufficient_evidence_cannot_contain_rule(self):
        data = self.rule()
        data["status"] = "insufficient_evidence"
        with self.assertRaises(ContractError):
            validate_candidate_rule(json.dumps(data), allowed_evidence_ids={"E001"})

    def test_pseudocode_is_never_executed(self):
        data = self.rule()
        data["pseudocode"] = "IF not-a-language() THEN ???"
        output = validate_candidate_rule(
            json.dumps(data), allowed_evidence_ids={"E001"}
        )
        self.assertEqual(output["pseudocode"], data["pseudocode"])

    def test_duplicate_or_unknown_evidence_rejected(self):
        for refs in (["E001", "E001"], ["E002"], [123]):
            data = self.cause()
            data["evidence_ids"] = refs
            with self.subTest(refs=refs), self.assertRaises(ContractError):
                validate_cause_probe(json.dumps(data), allowed_evidence_ids={"E001"})


if __name__ == "__main__":
    unittest.main()
