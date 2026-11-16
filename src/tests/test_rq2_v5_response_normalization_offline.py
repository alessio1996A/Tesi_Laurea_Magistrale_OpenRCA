"""Test offline della politica di formato V5: nessuna API, nessun dato reale."""
import json
import unittest

from evaluation.rq2_v5_response_normalization import (
    DEVIATION_NONE, DEVIATION_REJECTED_WRAPPER, DEVIATION_SINGLE_JSON_FENCE,
    normalize_response,
)
from output.v2_task_contract import audit_task_output

PURE = '{"1": {"root cause reason": "disk space consumption"}}'
INSTRUCTION = "One failure occurred; identify its root cause reason."
WINDOW = {"start_unix": 1_600_000_000, "end_unix": 1_600_003_600}


def _audit(text):
    return audit_task_output(
        text, task_index="task_2", instruction=INSTRUCTION, **WINDOW,
    )


class ResponseNormalizationTest(unittest.TestCase):
    def test_pure_json_is_untouched(self):
        result = normalize_response(PURE)
        self.assertEqual(result.deviation, DEVIATION_NONE)
        self.assertIs(result.text, PURE)
        self.assertEqual(result.raw_sha256, result.text_sha256)

    def test_single_json_fence_returns_inner_unchanged(self):
        raw = "```json\n" + PURE + "\n```"
        result = normalize_response(raw)
        self.assertEqual(result.deviation, DEVIATION_SINGLE_JSON_FENCE)
        self.assertEqual(result.text, PURE)
        self.assertEqual(result.language_tag, "json")
        self.assertNotEqual(result.raw_sha256, result.text_sha256)

    def test_fence_without_language_and_uppercase_language(self):
        for opening in ("```\n", "```JSON\n", "```json \n"):
            with self.subTest(opening=opening):
                result = normalize_response(opening + PURE + "\n```")
                self.assertEqual(result.deviation, DEVIATION_SINGLE_JSON_FENCE)
                self.assertEqual(result.text, PURE)

    def test_surrounding_whitespace_and_crlf(self):
        raw = "\n  ```json\r\n" + PURE + "\r\n```  \n"
        result = normalize_response(raw)
        self.assertEqual(result.deviation, DEVIATION_SINGLE_JSON_FENCE)
        self.assertEqual(result.text, PURE)

    def test_inner_whitespace_is_not_stripped(self):
        inner = "  " + PURE + "  "
        result = normalize_response("```json\n" + inner + "\n```")
        self.assertEqual(result.text, inner)

    def test_rejected_wrappers_keep_original_text(self):
        cases = {
            "text_before": "Ecco il risultato:\n```json\n" + PURE + "\n```",
            "text_after": "```json\n" + PURE + "\n```\nSpero sia utile.",
            "two_fences": "```json\n" + PURE + "\n```\n```json\n" + PURE + "\n```",
            "other_language": "```python\n" + PURE + "\n```",
            "unclosed": "```json\n" + PURE,
            "empty_inner": "```json\n\n```",
        }
        for name, raw in cases.items():
            with self.subTest(case=name):
                result = normalize_response(raw)
                self.assertEqual(result.deviation, DEVIATION_REJECTED_WRAPPER)
                self.assertIs(result.text, raw)
                self.assertEqual(result.raw_sha256, result.text_sha256)

    def test_no_repair_of_invalid_inner_json(self):
        broken = '{"1": {"root cause reason": "x",}}'
        result = normalize_response("```json\n" + broken + "\n```")
        self.assertEqual(result.text, broken)
        with self.assertRaises(ValueError):
            json.loads(result.text)

    def test_idempotent(self):
        first = normalize_response("```json\n" + PURE + "\n```")
        second = normalize_response(first.text)
        self.assertEqual(second.deviation, DEVIATION_NONE)
        self.assertEqual(second.text, first.text)

    def test_non_text_input(self):
        for value in (None, 3, b"{}", ["```json"]):
            with self.subTest(value=value):
                result = normalize_response(value)
                self.assertIsNone(result.text)
                self.assertEqual(result.deviation, DEVIATION_NONE)
                self.assertIsNone(result.raw_sha256)

    def test_strict_contract_before_and_after(self):
        fenced = "```json\n" + PURE + "\n```"
        self.assertFalse(_audit(fenced)["valid"])
        self.assertTrue(_audit(normalize_response(fenced).text)["valid"])
        # JSON puro: stesso esito con o senza normalizzazione.
        self.assertTrue(_audit(PURE)["valid"])
        self.assertTrue(_audit(normalize_response(PURE).text)["valid"])
        # Wrapper non ammesso: resta invalido, la politica non lo ripara.
        bad = "Ecco:\n```json\n" + PURE + "\n```"
        self.assertFalse(_audit(normalize_response(bad).text)["valid"])

    def test_policy_has_no_model_parameter(self):
        # Equita': la funzione non riceve il modello e non puo' distinguerlo.
        import inspect
        params = list(inspect.signature(normalize_response).parameters)
        self.assertEqual(params, ["raw"])


if __name__ == "__main__":
    unittest.main()
