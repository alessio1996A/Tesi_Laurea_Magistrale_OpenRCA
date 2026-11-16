"""Test offline del retry unico nell'esecutore V5 (serve LangChain: PyCharm/Colab).

Nessuna API, nessuna chiave: trasporto, grafo e normalizzatori sono finti.
Verificano la politica `rq2_v5_one_transport_retry_v1`: al massimo un secondo
tentativo, solo per errori di trasporto senza output del modello, e il primo
tentativo sempre conservato nel record.
"""
from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

HAS_LANGCHAIN = importlib.util.find_spec("langchain_core") is not None

if HAS_LANGCHAIN:
    import evaluation.rq2_v5_stage_executor as ex
    from evaluation.rq2_v5_retry import RETRY_PAUSE_SECONDS, RETRY_POLICY

COMPLETE, PROVIDER_ERROR, INVALID = (
    "RECORDED_COMPLETE", "PROVIDER_ERROR", "INVALID_OUTPUT")
PREFIX = "rq2_v4_task_aware_d_discovery_v0:cloudbed-1_q032:gemini:A0:"


def _row(stage):
    return {"stage_id": PREFIX + stage, "stage": stage,
            "case_id": "cloudbed-1_q032", "logical_model": "gemini",
            "model_id": "gemini-3.5-flash-lite", "model_provider": "google",
            "harness": "A0"}


class _FakeCapture:
    """Sostituisce V5DRunnerCapture: nessun grafo, nessuna patch."""

    def __init__(self, *, harness):
        self.harness = harness

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def build_receipt(self, result):
        return {"result": result}

    def format_record(self):
        return {"deviation": "NONE", "original_response": None}


@unittest.skipUnless(HAS_LANGCHAIN, "serve LangChain (PyCharm/Colab)")
class CKRetryTests(unittest.TestCase):
    PREPARED = {
        "package": {"messages": [{"role": "system", "content": "sys"},
                                 {"role": "user", "content": "usr"}]},
        "diagnostic_run": {"synthetic": True},
        "provenance": {"package_sha256": "a" * 64},
    }
    OK = {"raw_response": '{"a": 1}', "provider_error": None,
          "api_attempts": 1, "usage": {}, "elapsed_seconds": 1.0}
    TRANSPORT = {"raw_response": None,
                 "provider_error": "PROVIDER_ERROR:GoogleAPIError",
                 "api_attempts": 1, "usage": {}, "elapsed_seconds": 2.6}

    def _go(self, calls, *, forced_status=None):
        sleeps = []

        def fake_normalize(**kwargs):
            call = kwargs["call"]
            if forced_status:
                status = forced_status
            else:
                status = PROVIDER_ERROR if call["provider_error"] else COMPLETE
            return {"status": status, "artifact": {}}

        executor = ex.V5StageExecutor(
            data_dir=Path("/tmp"), repo_dir=Path("/tmp"), sleep=sleeps.append)
        with (
            patch.object(ex, "one_ck_call_candidate",
                         side_effect=list(calls)) as transport,
            patch.object(ex, "normalize_v4_ck_call", side_effect=fake_normalize),
        ):
            outcome = executor.run(_row("K"), copy.deepcopy(self.PREPARED))
        return outcome, transport.call_count, sleeps

    def test_transport_error_is_retried_once_and_first_attempt_is_kept(self):
        outcome, calls, sleeps = self._go([self.TRANSPORT, self.OK])
        self.assertEqual(calls, 2)
        self.assertEqual(sleeps, [RETRY_PAUSE_SECONDS])
        self.assertEqual(outcome["status"], COMPLETE)
        retry = outcome["provenance"]["retry"]
        self.assertEqual(retry["policy"], RETRY_POLICY)
        self.assertEqual([a["attempt"] for a in retry["attempts"]], [1, 2])
        self.assertEqual(retry["attempts"][0]["status"], PROVIDER_ERROR)
        self.assertEqual(retry["attempts"][0]["provider_error"],
                         "PROVIDER_ERROR:GoogleAPIError")
        self.assertEqual(retry["attempts"][1]["status"], COMPLETE)

    def test_never_a_third_attempt(self):
        outcome, calls, _ = self._go(
            [self.TRANSPORT, self.TRANSPORT, self.OK])
        self.assertEqual(calls, 2)
        self.assertEqual(outcome["status"], PROVIDER_ERROR)
        self.assertEqual(len(outcome["provenance"]["retry"]["attempts"]), 2)

    def test_success_at_first_attempt_has_no_retry_and_no_sleep(self):
        outcome, calls, sleeps = self._go([self.OK])
        self.assertEqual((calls, sleeps), (1, []))
        self.assertEqual(len(outcome["provenance"]["retry"]["attempts"]), 1)

    def test_model_side_errors_are_never_retried(self):
        protocol = dict(self.TRANSPORT,
                        provider_error="PROTOCOL_ERROR:ToolCallsForbidden")
        construction = dict(self.TRANSPORT,
                            provider_error="SDK_CONSTRUCTION_ERROR:ValueError")
        for name, call, status in (
            ("protocol", protocol, PROVIDER_ERROR),
            ("sdk_construction", construction, PROVIDER_ERROR),
            ("invalid_output", self.OK, INVALID),
        ):
            with self.subTest(case=name):
                _, calls, sleeps = self._go([call, self.OK],
                                            forced_status=status)
                self.assertEqual((calls, sleeps), (1, []))

    def test_error_with_a_model_response_is_not_a_transport_error(self):
        # Se c'e' una risposta del modello non e' (solo) un errore di trasporto.
        with_text = dict(self.TRANSPORT, raw_response="qualcosa")
        _, calls, _ = self._go([with_text, self.OK],
                               forced_status=PROVIDER_ERROR)
        self.assertEqual(calls, 1)


@unittest.skipUnless(HAS_LANGCHAIN, "serve LangChain (PyCharm/Colab)")
class DRetryTests(unittest.TestCase):
    PREPARED = {"config": object(), "provenance": {"max_tool_rounds": 6}}

    def _go(self, results):
        sleeps = []

        def fake_normalize(**kwargs):
            result = kwargs["captured"]["result"]
            status = PROVIDER_ERROR if result.get("error") else COMPLETE
            return {"status": status,
                    "artifact": {"stage_meter": {"input_tokens_observed": 7}}}

        executor = ex.V5StageExecutor(
            data_dir=Path("/tmp"), repo_dir=Path("/tmp"), sleep=sleeps.append)
        with (
            patch.object(ex, "crea_modello_rq2", return_value=object()),
            patch.object(ex, "V5DRunnerCapture", _FakeCapture),
            patch.object(ex, "run_experiment",
                         side_effect=list(results)) as run,
            patch.object(ex, "normalize_v4_d_capture", side_effect=fake_normalize),
        ):
            outcome = executor.run(_row("D"), copy.deepcopy(self.PREPARED))
        return outcome, run.call_count, sleeps

    def test_transport_exception_in_the_graph_is_retried_once(self):
        outcome, calls, sleeps = self._go([
            {"error": "ServiceUnavailable: 503 (messaggio con dettagli)",
             "raw_response": None},
            {"error": None, "raw_response": "{}"},
        ])
        self.assertEqual((calls, sleeps), (2, [RETRY_PAUSE_SECONDS]))
        self.assertEqual(outcome["status"], COMPLETE)
        first = outcome["provenance"]["retry"]["attempts"][0]
        self.assertEqual(first["error_type"], "ServiceUnavailable")
        self.assertEqual(len(first["error_message_sha256"]), 64)
        self.assertNotIn("503", str(first))      # il messaggio non e' salvato
        self.assertEqual(first["stage_meter"], {"input_tokens_observed": 7})

    def test_model_behavior_errors_are_never_retried(self):
        for error in ("AgentBudgetExhausted: tool richiesti",
                      "AgentFinalizationEmpty: vuota",
                      "VerifyFinalizationToolCall: x",
                      "VerifyFinalizationEmpty: x",
                      "EmptyFinalResponse: risposta finale vuota.",
                      "GraphRecursionError: limite"):
            with self.subTest(error=error):
                outcome, calls, sleeps = self._go(
                    [{"error": error, "raw_response": None},
                     {"error": None, "raw_response": "{}"}])
                self.assertEqual((calls, sleeps), (1, []))
                self.assertEqual(outcome["status"], PROVIDER_ERROR)

    def test_second_failure_ends_as_provider_error_after_two_runs(self):
        outcome, calls, _ = self._go([
            {"error": "ServiceUnavailable: a", "raw_response": None},
            {"error": "ServiceUnavailable: b", "raw_response": None},
            {"error": None, "raw_response": "{}"},
        ])
        self.assertEqual(calls, 2)
        self.assertEqual(outcome["status"], PROVIDER_ERROR)


if __name__ == "__main__":
    unittest.main()
