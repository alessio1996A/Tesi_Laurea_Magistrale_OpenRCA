"""Test di integrazione V2 nel runner senza LLM, ZIP o filesystem reale."""
import json
import unittest
from unittest.mock import patch

from evaluation.experiment_config import ExperimentConfig
from evaluation.experiment_runner import run_experiment
from output.v2_task_contract import COMPONENT, REASON, TIME


CASE = {
    "case_id": "cloudbed-1_q001",
    "cloudbed": "cloudbed-1",
    "start_unix": 1647741600,
    "end_unix": 1647743400,
    "instruction": "The system experienced two failures. Identify component and reason.",
    "task_index": "task_6",
    "query_index": 1,
}
TWO = json.dumps({
    "1": {COMPONENT: "node-1", REASON: "node CPU load"},
    "2": {COMPONENT: "node-2", REASON: "node memory consumption"},
})
ONE = json.dumps({"1": {COMPONENT: "node-1", REASON: "node CPU load"}})


def fake_run(response):
    return {
        "raw_response": response,
        "metrics": {
            "llm_calls": 1,
            "tool_calls": 0,
            "tool_rounds": 0,
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
        },
        "tool_trajectory": [],
        "error": None,
        "verification": {
            "piano": [], "stato_piano": "non_eseguito",
            "causa_verificata": False,
        },
    }


class RunnerV2Tests(unittest.TestCase):
    def run_fake(self, variant, raw, mode):
        config = ExperimentConfig(
            variant=variant, case_id=CASE["case_id"],
            output_contract_mode=mode,
        )
        fixture = {
            "caso": dict(CASE), "tools": [],
            "richiesta": "Synthetic incident",
            "evidence_report": {}, "evidence_sha256": "a" * 64,
            "preprocessing_seconds": 0.005,
        }
        with (
            patch("evaluation.experiment_runner.prepara_esperimento", return_value=fixture),
            patch("agent.graph_engine.crea_grafo_rca", return_value=object()),
            patch("agent.graph_engine.esegui_grafo_rca", return_value=fake_run(raw)),
            patch("agent.verify_graph.crea_grafo_rca_verify", return_value=object()),
            patch("agent.verify_graph.esegui_grafo_rca_verify", return_value=fake_run(raw)),
            patch(
                "harness.structural_temporal_verifier."
                "costruisci_contesto_strutturale_temporale",
                return_value={"synthetic_context": True},
            ),
        ):
            return run_experiment(config, llm=object(), verbose=False, salva=False)

    def test_all_five_variants_apply_same_task_contract(self):
        for variant in ("A0", "A1_V2", "A1", "A1_VERIFY", "A1_VERIFY_ST"):
            with self.subTest(variant=variant):
                result = self.run_fake(variant, TWO, "v2_enforce")
                self.assertEqual(result["json_status"], "valid_json")
                self.assertEqual(json.loads(result["prediction"]), json.loads(TWO))
                self.assertEqual(result["raw_response"], TWO)
                self.assertTrue(result["output_contract_v2"]["valid"])
                self.assertEqual(result["output_contract_v2"]["expected_faults"], 2)
                self.assertEqual(result["output_contract_mode"], "v2_enforce")
                self.assertEqual(result["metrics"]["llm_calls"], 1)

    def test_task_aware_enforcement_rejects_wrong_count(self):
        result = self.run_fake("A0", ONE, "v2_enforce")
        self.assertIsNone(result["prediction"])
        self.assertTrue(result["json_status"].startswith("invalid_v2_task_output"))
        self.assertIn("Numero di guasti", result["output_contract_v2"]["error"])

    def test_v2_audit_does_not_modify_legacy_output(self):
        legacy = self.run_fake("A0", TWO, "legacy")
        audit = self.run_fake("A0", TWO, "v2_audit")
        self.assertIsNone(legacy["prediction"])  # manca timestamp richiesto dal parser V1
        self.assertIsNone(audit["prediction"])
        self.assertEqual(audit["json_status"], legacy["json_status"])
        self.assertEqual(audit["raw_response"], legacy["raw_response"])
        self.assertTrue(audit["output_contract_v2"]["valid"])
        self.assertNotIn("output_contract_v2", legacy)

    def test_v2_timestamp_extra_is_not_mandatory(self):
        self.assertEqual(CASE["task_index"], "task_6")
        result = self.run_fake("A1_VERIFY", TWO, "v2_enforce")
        self.assertTrue(result["output_contract_v2"]["valid"])
        self.assertIsNone(result["output_contract_v2"]["timestamp_in_window"])

    def test_v2_new_prompt_differs_from_legacy(self):
        old = self.run_fake("A1", TWO, "legacy")
        new = self.run_fake("A1", TWO, "v2_enforce")
        self.assertNotEqual(old["system_prompt_sha256"], new["system_prompt_sha256"])


if __name__ == "__main__":
    unittest.main()
