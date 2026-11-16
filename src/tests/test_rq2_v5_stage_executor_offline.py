"""Test offline dell'esecutore V5 reale (serve LangChain: PyCharm/Colab).

Esegue il VERO run_experiment con grafo finto (stessa impalcatura del test V3
di cattura D) e dimostra che la politica di formato V5 vale per tutti e cinque
gli harness, senza toccare parser/contratti V4. Nessuna API, nessuna chiave.
Dove manca LangChain (es. sandbox senza pacchetti) i test vengono saltati.
"""
from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

HAS_LANGCHAIN = importlib.util.find_spec("langchain_core") is not None

if HAS_LANGCHAIN:
    import agent.graph_engine as react
    import agent.verify_graph as verify
    import evaluation.experiment_runner as runner
    import evaluation.rq2_v5_stage_executor as executor_module
    from evaluation.experiment_config import ExperimentConfig
    from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
    from evaluation.rq2_v3_d_runner_capture_candidate import V3DRunnerCapture
    from evaluation.rq2_v5_matrix_runner import STATUS_COMPLETE
    from evaluation.rq2_v5_stage_executor import (
        V5DRunnerCapture, V5StageExecutor,
    )
    from test_rq2_v3_d_contentblock_audit_offline import VALID_D
    from test_rq2_v3_d_runner_capture_candidate_offline import (
        FakeGraph, _fragments, _prepared_fixture,
    )

HARNESSES = ("A0", "A1", "A1_8R", "A1_8R_Planning", "A1_PAVE")
FENCED = "```json\n" + (VALID_D if HAS_LANGCHAIN else "") + "\n```"


@unittest.skipUnless(HAS_LANGCHAIN, "serve LangChain (PyCharm/Colab)")
class V5DCaptureOfflineTests(unittest.TestCase):
    def _run(self, raw, *, harness="A0", model="gemini", capture_cls=None):
        spec = CANDIDATE_MODELS[model]
        config = ExperimentConfig(
            variant=harness, case_id="cloudbed-1_q032",
            model_name=spec["model_id"], model_provider=spec["provider"],
            output_contract_mode="v2_enforce", max_tool_rounds=6,
            max_verification_checks=2, recursion_limit=30,
            variant_scheme="current",
        )
        graphs = []

        def make(engine):
            def build(**kwargs):
                graph = FakeGraph(engine, _fragments(raw))
                graphs.append(graph)
                return graph
            return build

        with (
            patch.object(runner, "prepara_esperimento",
                         side_effect=_prepared_fixture),
            patch.object(runner, "get_system_prompt",
                         return_value="Synthetic system prompt"),
            patch.object(react, "crea_grafo_rca", side_effect=make("react")),
            patch.object(verify, "crea_grafo_rca_verify",
                         side_effect=make("verify")),
            patch("harness.structural_temporal_verifier."
                  "costruisci_contesto_strutturale_temporale",
                  return_value={"schema": "synthetic_observation"}),
        ):
            capture = (capture_cls or V5DRunnerCapture)(harness=harness)
            with capture:
                result = runner.run_experiment(
                    config, llm=object(), verbose=False, salva=False)
            receipt = capture.build_receipt(result)
        self.assertEqual(len(graphs), 1)
        # Il messaggio originale del provider non viene mai modificato.
        self.assertEqual(graphs[0].original.content, graphs[0].original_copy)
        return receipt, capture, graphs[0]

    def test_single_json_fence_is_valid_for_all_five_harnesses(self):
        for harness in HARNESSES:
            with self.subTest(harness=harness):
                receipt, capture, _ = self._run(FENCED, harness=harness)
                run = receipt["diagnostic_run"]
                self.assertEqual(run["raw_response"], VALID_D)
                self.assertEqual(run["json_status"], "valid_json")
                self.assertTrue(run["output_contract_v2"]["valid"])
                fmt = capture.format_record()
                self.assertEqual(fmt["deviation"], "SINGLE_JSON_FENCE")
                self.assertEqual(fmt["original_response"], FENCED)
                meta = receipt["d_final_text_extraction"]
                self.assertEqual((meta["text_blocks"], meta["nontext_blocks"]),
                                 (2, 0))

    def test_same_policy_for_all_three_models(self):
        for model in ("gemini", "sonnet", "haiku"):
            with self.subTest(model=model):
                receipt, capture, _ = self._run(FENCED, model=model)
                self.assertEqual(receipt["diagnostic_run"]["json_status"],
                                 "valid_json")
                self.assertEqual(capture.format_record()["deviation"],
                                 "SINGLE_JSON_FENCE")

    def test_plain_json_is_unchanged_and_marked_none(self):
        receipt, capture, _ = self._run(VALID_D)
        self.assertEqual(receipt["diagnostic_run"]["raw_response"], VALID_D)
        self.assertEqual(capture.format_record()["deviation"], "NONE")

    def test_prose_around_fence_stays_invalid_with_the_real_contract(self):
        raw = "Ecco la diagnosi:\n" + FENCED
        receipt, capture, _ = self._run(raw)
        run = receipt["diagnostic_run"]
        self.assertEqual(run["raw_response"], raw)
        self.assertFalse(run["output_contract_v2"]["valid"])
        self.assertIsNone(run["prediction"])
        self.assertEqual(capture.format_record()["deviation"],
                         "REJECTED_WRAPPER")

    def test_without_v5_policy_the_fence_is_invalid_as_in_v4(self):
        receipt, _, _ = self._run(FENCED, capture_cls=V3DRunnerCapture)
        run = receipt["diagnostic_run"]
        self.assertEqual(run["raw_response"], FENCED)
        self.assertFalse(run["output_contract_v2"]["valid"])

    def test_patch_is_removed_after_the_run(self):
        original = executor_module.d_stream.extract_visible_ck_text
        self._run(FENCED)
        self.assertIs(executor_module.d_stream.extract_visible_ck_text,
                      original)


@unittest.skipUnless(HAS_LANGCHAIN, "serve LangChain (PyCharm/Colab)")
class V5CKGlueOfflineTests(unittest.TestCase):
    ROW = {
        "stage_id": "rq2_v4_task_aware_d_discovery_v0:cloudbed-1_q032:"
                    "gemini:A0:C",
        "stage": "C", "case_id": "cloudbed-1_q032",
        "logical_model": "gemini", "model_id": "gemini-3.5-flash-lite",
        "model_provider": "google", "harness": "A0",
    }
    PREPARED = {
        "package": {"messages": [{"role": "system", "content": "sys"},
                                 {"role": "user", "content": "usr"}]},
        "diagnostic_run": {"synthetic": True},
        "provenance": {"package_sha256": "a" * 64},
    }

    def _go(self, call):
        seen = {}

        def fake_normalize(**kwargs):
            seen.update(kwargs)
            return {"status": STATUS_COMPLETE, "artifact": {}}

        executor = V5StageExecutor(data_dir=Path("/tmp"), repo_dir=Path("/tmp"))
        with (
            patch.object(executor_module, "one_ck_call_candidate",
                         return_value=call) as transport,
            patch.object(executor_module, "normalize_v4_ck_call",
                         side_effect=fake_normalize),
        ):
            outcome = executor.run(self.ROW, copy.deepcopy(self.PREPARED))
        self.assertEqual(transport.call_count, 1)  # una sola chiamata
        return outcome, seen

    def test_fenced_response_reaches_the_strict_normalizer_unwrapped(self):
        fenced = '```json\n{"a": 1}\n```'
        outcome, seen = self._go({"raw_response": fenced,
                                  "provider_error": None, "api_attempts": 1})
        self.assertEqual(seen["call"]["raw_response"], '{"a": 1}')
        self.assertEqual(outcome["format"]["deviation"], "SINGLE_JSON_FENCE")
        self.assertEqual(outcome["format"]["original_response"], fenced)

    def test_plain_and_rejected_responses_are_passed_unchanged(self):
        for raw, expected in (('{"a": 1}', "NONE"),
                              ('Ecco:\n```json\n{"a": 1}\n```',
                               "REJECTED_WRAPPER")):
            with self.subTest(raw=raw):
                outcome, seen = self._go({"raw_response": raw,
                                          "provider_error": None,
                                          "api_attempts": 1})
                self.assertEqual(seen["call"]["raw_response"], raw)
                self.assertEqual(outcome["format"]["deviation"], expected)

    def test_provider_error_is_passed_through_without_text(self):
        outcome, seen = self._go({"raw_response": None,
                                  "provider_error": "PROVIDER_ERROR:Boom",
                                  "api_attempts": 1})
        self.assertIsNone(seen["call"]["raw_response"])
        self.assertIsNone(outcome["format"]["original_response"])

    def test_prepare_rejects_a_package_with_a_foreign_prompt(self):
        executor = V5StageExecutor(data_dir=Path("/tmp"), repo_dir=Path("/tmp"))
        row = dict(self.ROW)
        parents = {row["stage_id"].rsplit(":", 1)[0] + ":D": {
            "receipt": {"artifact": {"diagnostic_run": {"synthetic": True}}}}}
        bad_package = {"messages": self.PREPARED["package"]["messages"],
                       "system_prompt_sha256": "0" * 64,
                       "model_api_calls": 0, "package_sha256": "b" * 64}
        with (
            patch.object(executor_module, "_source_instruction",
                         return_value="istruzione"),
            patch.object(executor_module, "prepare_cause_probe",
                         return_value=bad_package),
        ):
            with self.assertRaises(ValueError):
                executor.prepare(row, parents)

    def test_prepare_builds_the_frozen_d_budgets(self):
        executor = V5StageExecutor(data_dir=Path("/tmp"), repo_dir=Path("/tmp"))
        row = {**self.ROW, "stage": "D",
               "stage_id": self.ROW["stage_id"][:-1] + "D"}
        with patch.object(executor_module, "_source_instruction",
                          return_value="istruzione"):
            prepared = executor.prepare(row, {})
        config = prepared["config"]
        self.assertEqual((config.max_tool_rounds, config.recursion_limit), (6, 30))
        self.assertEqual(config.output_contract_mode, "v2_enforce")


if __name__ == "__main__":
    unittest.main()
