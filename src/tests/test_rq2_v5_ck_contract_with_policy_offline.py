"""Politica di formato V5 + VERI contratti C/K (solo libreria standard).

Dimostra, senza LangChain e senza API, che:
- il contratto C/K strict resta invariato (un fence e' rifiutato);
- dopo la politica V5 un singolo fence JSON produce LO STESSO oggetto
  validato che si avrebbe con JSON puro;
- tutto cio' che la politica non ammette resta rifiutato.
"""
from __future__ import annotations

import json
import unittest

from evaluation.rq2_output_contracts import (
    ContractError, validate_candidate_rule, validate_cause_probe,
)
from evaluation.rq2_v5_response_normalization import (
    DEVIATION_FENCE_WITH_OUTSIDE_TEXT, DEVIATION_NONE,
    DEVIATION_REJECTED_WRAPPER, DEVIATION_SINGLE_JSON_FENCE, POLICY,
    apply_policy,
)
from test_rq2_output_contracts import RQ2OutputContractsTests as Fixtures

CAUSE = Fixtures.cause()
RULE = Fixtures.rule()
ALLOWED = {"E001"}


def _fence(obj, lang="json"):
    return f"```{lang}\n{json.dumps(obj, indent=2)}\n```"


class CKContractWithPolicyTests(unittest.TestCase):
    def test_strict_contract_still_rejects_fence_for_c_and_k(self):
        with self.assertRaises(ContractError):
            validate_cause_probe(_fence(CAUSE), allowed_evidence_ids=ALLOWED)
        with self.assertRaises(ContractError):
            validate_candidate_rule(_fence(RULE), allowed_evidence_ids=ALLOWED)

    def test_single_json_fence_becomes_identical_validated_object(self):
        for lang in ("json", ""):
            with self.subTest(lang=lang):
                text, fmt = apply_policy(_fence(CAUSE, lang))
                self.assertEqual(fmt["deviation"], DEVIATION_SINGLE_JSON_FENCE)
                self.assertEqual(
                    validate_cause_probe(text, allowed_evidence_ids=ALLOWED),
                    validate_cause_probe(json.dumps(CAUSE),
                                         allowed_evidence_ids=ALLOWED))
                text, fmt = apply_policy(_fence(RULE, lang))
                self.assertEqual(
                    validate_candidate_rule(text, allowed_evidence_ids=ALLOWED),
                    RULE)

    def test_plain_json_is_untouched_and_marked_none(self):
        raw = json.dumps(CAUSE)
        text, fmt = apply_policy(raw)
        self.assertEqual(text, raw)
        self.assertEqual(fmt["deviation"], DEVIATION_NONE)
        self.assertEqual(fmt["original_response"], raw)

    def test_everything_else_stays_rejected_by_the_strict_contract(self):
        bad_cases = {
            "testo sulla riga della fence": "Ecco: " + _fence(CAUSE),
            "due fence": _fence(CAUSE) + "\n" + _fence(CAUSE),
            "lingua diversa": _fence(CAUSE, "python"),
            "fence non chiuso": "```json\n" + json.dumps(CAUSE),
        }
        for label, raw in bad_cases.items():
            with self.subTest(case=label):
                text, fmt = apply_policy(raw)
                self.assertNotEqual(fmt["deviation"],
                                    DEVIATION_SINGLE_JSON_FENCE)
                with self.assertRaises(ContractError):
                    validate_cause_probe(text, allowed_evidence_ids=ALLOWED)

    def test_fence_with_outside_text_is_unwrapped_for_c_and_k(self):
        # V5.1: caso reale del pilota (blocco valido + commento del modello).
        cases = {
            "testo dopo": _fence(CAUSE) + "\n\nQuesta e' un'inferenza.",
            "testo prima": "Ecco il risultato:\n" + _fence(CAUSE),
        }
        for label, raw in cases.items():
            with self.subTest(case=label):
                text, fmt = apply_policy(raw)
                self.assertEqual(fmt["deviation"],
                                 DEVIATION_FENCE_WITH_OUTSIDE_TEXT)
                self.assertEqual(
                    validate_cause_probe(text, allowed_evidence_ids=ALLOWED),
                    validate_cause_probe(json.dumps(CAUSE),
                                         allowed_evidence_ids=ALLOWED))
                self.assertEqual(fmt["original_response"], raw)

    def test_policy_removes_the_wrapper_but_never_repairs_the_json(self):
        broken = _fence(CAUSE).replace("}", "", 1)  # JSON interno troncato
        text, fmt = apply_policy(broken)
        self.assertEqual(fmt["deviation"], DEVIATION_SINGLE_JSON_FENCE)
        with self.assertRaises(ContractError):
            validate_cause_probe(text, allowed_evidence_ids=ALLOWED)

    def test_rejected_wrapper_keeps_original_text(self):
        raw = "Ecco: " + _fence(CAUSE)
        text, fmt = apply_policy(raw)
        self.assertEqual(text, raw)
        self.assertEqual(fmt["deviation"], DEVIATION_REJECTED_WRAPPER)

    def test_original_response_and_hashes_are_always_recorded(self):
        raw = _fence(RULE)
        text, fmt = apply_policy(raw)
        self.assertEqual(fmt["original_response"], raw)
        self.assertNotEqual(fmt["raw_sha256"], fmt["text_sha256"])
        self.assertEqual(fmt["policy"], POLICY)


if __name__ == "__main__":
    unittest.main()
