"""Test della politica di retry V5 (stdlib, nessuna API)."""
import unittest

from evaluation.rq2_v5_retry import (
    D_MODEL_BEHAVIOR_ERRORS, MAX_ATTEMPTS, RETRY_PAUSE_SECONDS, RETRY_POLICY,
    ck_error_is_transport, d_error_is_transport, error_type,
    run_with_one_retry,
)


class ClassificationTests(unittest.TestCase):
    def test_error_type_keeps_only_the_name(self):
        self.assertEqual(error_type("ServiceUnavailable: 503 chiave=XYZ"),
                         "ServiceUnavailable")
        self.assertIsNone(error_type(None))
        self.assertIsNone(error_type("   "))

    def test_d_model_behavior_errors_are_not_transport(self):
        for name in D_MODEL_BEHAVIOR_ERRORS:
            with self.subTest(name=name):
                self.assertFalse(d_error_is_transport(f"{name}: dettaglio"))

    def test_d_other_exceptions_are_transport(self):
        for text in ("ServiceUnavailable: 503", "APIConnectionError: x",
                     "GoogleAPIError: y", "RateLimitError: z"):
            with self.subTest(text=text):
                self.assertTrue(d_error_is_transport(text))
        self.assertFalse(d_error_is_transport(None))
        self.assertFalse(d_error_is_transport(""))

    def test_ck_only_provider_exceptions_without_output(self):
        base = {"raw_response": None, "provider_error": None}
        self.assertTrue(ck_error_is_transport(
            {**base, "provider_error": "PROVIDER_ERROR:GoogleAPIError"}))
        self.assertTrue(ck_error_is_transport(
            {**base, "provider_error": "PROVIDER_ERROR:APIError:HTTP_529"}))
        for bad in ("PROTOCOL_ERROR:ToolCallsForbidden",
                    "PROTOCOL_ERROR:ContentBlockLimit",
                    "SDK_CONSTRUCTION_ERROR:ValueError", None):
            with self.subTest(bad=bad):
                self.assertFalse(ck_error_is_transport(
                    {**base, "provider_error": bad}))
        self.assertFalse(ck_error_is_transport(
            {"raw_response": "x", "provider_error": "PROVIDER_ERROR:Boom"}))
        self.assertFalse(ck_error_is_transport(None))


class LoopTests(unittest.TestCase):
    def _run(self, steps):
        """steps: lista di (status, retriable) per i tentativi successivi."""
        sleeps, calls = [], []

        def attempt(number):
            calls.append(number)
            status, retriable = steps[number - 1]
            return ({"status": status, "receipt": None, "format": None,
                     "provenance": {"base": 1}}, retriable,
                    {"note": f"t{number}"})

        outcome = run_with_one_retry(attempt, sleep=sleeps.append)
        return outcome, calls, sleeps

    def test_constants_are_the_declared_ones(self):
        self.assertEqual(MAX_ATTEMPTS, 2)
        self.assertEqual(RETRY_POLICY, "rq2_v5_one_transport_retry_v1")
        self.assertGreater(RETRY_PAUSE_SECONDS, 0)

    def test_recovery_on_second_attempt_keeps_the_history(self):
        outcome, calls, sleeps = self._run(
            [("PROVIDER_ERROR", True), ("RECORDED_COMPLETE", False)])
        self.assertEqual((calls, sleeps), ([1, 2], [RETRY_PAUSE_SECONDS]))
        self.assertEqual(outcome["status"], "RECORDED_COMPLETE")
        attempts = outcome["provenance"]["retry"]["attempts"]
        self.assertEqual([a["status"] for a in attempts],
                         ["PROVIDER_ERROR", "RECORDED_COMPLETE"])
        self.assertEqual(outcome["provenance"]["base"], 1)

    def test_at_most_two_attempts(self):
        outcome, calls, _ = self._run(
            [("PROVIDER_ERROR", True), ("PROVIDER_ERROR", True),
             ("RECORDED_COMPLETE", False)])
        self.assertEqual(calls, [1, 2])
        self.assertEqual(outcome["status"], "PROVIDER_ERROR")

    def test_not_retriable_stops_at_once(self):
        outcome, calls, sleeps = self._run([("INVALID_OUTPUT", False)])
        self.assertEqual((calls, sleeps), ([1], []))
        self.assertEqual(len(outcome["provenance"]["retry"]["attempts"]), 1)

    def test_retry_is_only_allowed_for_provider_error(self):
        with self.assertRaises(ValueError):
            self._run([("INVALID_OUTPUT", True), ("RECORDED_COMPLETE", False)])

    def test_input_outcome_is_not_mutated(self):
        original = {"status": "RECORDED_COMPLETE", "receipt": None,
                    "format": None, "provenance": {"base": 1}}
        result = run_with_one_retry(lambda n: (original, False, {}))
        self.assertNotIn("retry", original["provenance"])
        self.assertIn("retry", result["provenance"])


if __name__ == "__main__":
    unittest.main()
