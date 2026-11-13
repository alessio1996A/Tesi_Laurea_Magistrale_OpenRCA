"""Gate offline per il pilot Sonnet V2: nessun dataset, GT, Drive o provider.

Le patch rendono sintetici ONLY sorgenti, release e modello. Il runner
LangGraph, esecutore V2, bundle e ledger sono quelli veri.
"""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluation.experiment_runner as runner
import evaluation.rq2_v2_sonnet_pilot_driver as driver
import evaluation.rq2_v2_sonnet_pilot_ledger as pilot
from evaluation.rq2_provider_policy_source_audit import EXPECTED_COLAB_VERSIONS
from test_rq2_v2_runner_fake_e2e import (
    FINAL_JSON, INSTRUCTION, ParallelSameNameFakeLLM, fake_node_metrics,
)

FAKE_BINDING = {
    "code_commit": "a" * 40,
    "source_binding_sha256": "c" * 64,
}
FAKE_RELEASE = {
    "code_commit": FAKE_BINDING["code_commit"],
    "runtime_versions": dict(EXPECTED_COLAB_VERSIONS),
    "approved_usd_limit": 1.0,
}


def fake_preparation(config):
    # Il case_id q050 e' solo una CHIAVE; tutto il resto e' inventato.
    if config.case_id != "cloudbed-1_q050" or config.canonical_variant != "A1":
        raise AssertionError("Solo arm synthetic q050/A1")
    return {
        "caso": {
            "case_id": "cloudbed-1_q050", "cloudbed": "cloudbed-1",
            "task_index": "task_7", "query_index": 50,
            "instruction": INSTRUCTION,
            "start_unix": 1_700_000_000, "end_unix": 1_700_001_000,
        },
        "tools": [fake_node_metrics],
        "richiesta": "Synthetic q050 fixture only: " + INSTRUCTION,
        "evidence_report": {"synthetic": True},
        "evidence_sha256": "f" * 64,
        "preprocessing_seconds": 0.0,
    }


class RQ2V2SonnetPilotOfflineTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()

    def _ledger(self):
        return pilot.RQ2V2SonnetPilotLedger(
            data_dir=self.root, repo_dir=self.repo,
        )

    def _mock_release(self):
        self.addCleanup(patch.stopall)
        p1 = patch.object(pilot, "source_binding", return_value=FAKE_BINDING)
        p2 = patch.object(pilot, "read_frozen_release", return_value=FAKE_RELEASE)
        p3 = patch.object(pilot, "EXPECTED_RELEASE_SHA256", "b" * 64)
        for p in (p1, p2, p3):
            p.start()

    def _run_fake(self):
        cfg = driver.ExperimentConfig(
            variant="A1", case_id="cloudbed-1_q050",
            model_name=pilot.MODEL_ID, model_provider="anthropic",
            max_tool_rounds=6, recursion_limit=30,
            variant_scheme="current", output_contract_mode="v2_enforce",
            data_dir=self.root, repo_dir=self.repo,
        )
        fake = ParallelSameNameFakeLLM()
        with patch.object(runner, "prepara_esperimento", fake_preparation):
            with patch.object(
                driver.graph_v1, "esegui_grafo_rca", driver.esegui_grafo_rca_v2
            ):
                result = runner.run_experiment(
                    cfg, llm=fake, verbose=False, salva=False,
                )
        self.assertEqual(fake.invocations, 2)
        self.assertEqual(result["raw_response"], FINAL_JSON)
        self.assertEqual(result["json_status"], "valid_json")
        self.assertTrue(result["output_contract_v2"]["valid"])
        return result

    def test_release_absent_blocks_before_claim_and_api(self):
        with patch.object(pilot, "source_binding", return_value=FAKE_BINDING):
            with self.assertRaisesRegex(pilot.SonnetPilotBlocked, "NO_API"):
                self._ledger().claim_stage()
        self.assertFalse((self.root / "data").exists())

    def test_driver_requires_explicit_one_shot_consent(self):
        with patch.object(driver, "crea_modello_rq2") as provider:
            with self.assertRaisesRegex(
                pilot.SonnetPilotBlocked, "confirmation"
            ):
                driver.run_one_sonnet_v2_pilot_d(
                    data_dir=self.root, repo_dir=self.repo,
                )
            provider.assert_not_called()

    def test_claim_survives_restart_and_refuses_retry(self):
        self._mock_release()
        ledger = self._ledger()
        first = ledger.claim_stage()
        self.assertEqual(first["status"], "CLAIM_WITHOUT_ARTIFACT")
        audit = self._ledger().audit_restart()
        self.assertTrue(audit["unresolved_claim"])
        self.assertFalse(audit["record_exists"])
        self.assertFalse(audit["automatic_retry_allowed"])
        with self.assertRaisesRegex(pilot.SonnetPilotBlocked, "No retry"):
            self._ledger().claim_stage()
        self.assertFalse((self.root / "data/rq2").exists())

    def test_real_graph_fake_model_parallel_ids_to_sourcebound_record(self):
        self._mock_release()
        ledger = self._ledger()
        ledger.claim_stage()
        run = self._run_fake()
        result = ledger.record_stage(diagnostic_run=run)
        self.assertEqual(result["status"], "RECORDED_COMPLETE")
        self.assertEqual(len(run["tool_trajectory"]), 4)
        ids = [e["tool_call_id"] for e in run["tool_trajectory"]]
        self.assertEqual(ids, ["fake-id-A", "fake-id-B", "fake-id-A", "fake-id-B"])
        self.assertEqual(
            self._ledger().audit_restart()["status"], "RECORDED_COMPLETE"
        )
        self.assertFalse((self.root / "data/rq2").exists())

    def test_corrupt_tool_result_id_preserved_as_invalid_output(self):
        self._mock_release()
        ledger = self._ledger()
        ledger.claim_stage()
        bad = self._run_fake()
        bad["tool_trajectory"][-1]["tool_call_id"] = "unknown-id"
        rec = ledger.record_stage(diagnostic_run=bad)
        self.assertEqual(rec["status"], "INVALID_OUTPUT")
        self.assertEqual(self._ledger().audit_restart()["status"], "INVALID_OUTPUT")
        with self.assertRaisesRegex(pilot.SonnetPilotBlocked, "No retry"):
            ledger.claim_stage()

    def test_valid_provenance_invalid_json_is_not_complete(self):
        self._mock_release()
        ledger = self._ledger()
        ledger.claim_stage()
        bad = self._run_fake()
        bad["raw_response"] = "not-json"
        bad["json_status"] = "invalid_v2_task_output: bad syntax"
        bad["output_contract_v2"] = {"valid": False}
        self.assertEqual(
            ledger.record_stage(diagnostic_run=bad)["status"],
            "INVALID_OUTPUT",
        )

    def test_error_recorded_without_diagnosis_and_no_retry(self):
        self._mock_release()
        ledger = self._ledger()
        ledger.claim_stage()
        bad = self._run_fake()
        bad["error"] = "TimeoutError: synthetic timeout"
        bad["raw_response"] = None
        bad["metrics"]["token_usage_complete"] = False
        self.assertEqual(
            ledger.record_stage(diagnostic_run=bad)["status"],
            "EXECUTION_ERROR_REVIEW",
        )
        self.assertFalse(self._ledger().audit_restart()["unresolved_claim"])

    def test_record_tampering_detected_by_restart(self):
        self._mock_release()
        ledger = self._ledger()
        ledger.claim_stage()
        ledger.record_stage(diagnostic_run=self._run_fake())
        rec = json.loads(ledger.record_path.read_bytes())
        rec["status"] = "INVALID_OUTPUT"
        ledger.record_path.write_bytes(pilot._canonical(rec))
        with self.assertRaisesRegex(
            pilot.SonnetPilotBlocked, "record/readback mismatch"
        ):
            self._ledger().audit_restart()

    def test_full_guarded_driver_with_real_runner_but_fake_provider(self):
        self._mock_release()
        fake_model = ParallelSameNameFakeLLM()
        with (
            patch.object(driver, "assert_exact_runtime_snapshot"),
            patch.object(
                driver.metadata, "version",
                side_effect=lambda package: EXPECTED_COLAB_VERSIONS[package],
            ),
            patch.object(
                driver, "crea_modello_rq2", return_value=fake_model,
            ) as factory,
            patch.object(
                runner, "prepara_esperimento", side_effect=fake_preparation,
            ),
        ):
            outcome = driver.run_one_sonnet_v2_pilot_d(
                data_dir=self.root, repo_dir=self.repo,
                confirm_paid_api=True,
            )
        self.assertEqual(fake_model.invocations, 2)
        factory.assert_called_once_with("anthropic", pilot.MODEL_ID)
        self.assertEqual(outcome["observed_model_requests"], 2)
        self.assertEqual(outcome["status"], "RECORDED_COMPLETE")
        self.assertFalse(outcome["usd_hard_cap_guaranteed"])
        self.assertFalse(outcome["c_k_executed"])
        self.assertFalse(self._ledger().audit_restart()["unresolved_claim"])
        self.assertFalse((self.root / "data/rq2").exists())

    def test_missing_reliable_usage_aborts_next_request_no_retry(self):
        class NoUsageLLM(ParallelSameNameFakeLLM):
            def invoke(self, messages):
                answer = super().invoke(messages)
                answer.usage_metadata = None
                return answer

        limited = driver._LimitedModel(NoUsageLLM(), 1.0)
        with self.assertRaisesRegex(pilot.SonnetPilotBlocked, "token usage"):
            limited.invoke([])
        self.assertEqual(limited.calls, 1)
        self.assertFalse(limited.usage_complete)


    def test_source_drift_after_claim_blocks_restart(self):
        self._mock_release()
        ledger = self._ledger()
        ledger.claim_stage()
        drift = dict(FAKE_BINDING, source_binding_sha256="d" * 64)
        with patch.object(pilot, "source_binding", return_value=drift):
            with self.assertRaisesRegex(
                pilot.SonnetPilotBlocked, "Claim and current input/source drift"
            ):
                ledger.audit_restart()

    def test_real_release_reader_checks_original_digest(self):
        release = {
            "schema": "rq2_v2_sonnet_pilot_release_v1",
            "protocol": pilot.PROTOCOL, "stage_id": pilot.STAGE_ID,
            "source_binding_sha256": FAKE_BINDING["source_binding_sha256"],
            "code_commit": FAKE_BINDING["code_commit"],
            "provider": "anthropic", "model_id": pilot.MODEL_ID,
            "harness": "A1", "stage": "D",
            "output_contract_mode": "v2_enforce",
            "max_tool_rounds": 6, "recursion_limit": 30,
            "max_retries": 0, "max_tokens": 4096,
            "timeout_seconds": 300, "max_llm_requests": 7,
            "authorization": "approved_for_one_pilot",
            "api_budget_approved": True, "approved_usd_limit": 1.0,
            "runtime_versions": dict(EXPECTED_COLAB_VERSIONS),
            "ood_test_locked": True,
        }
        path = self.root / pilot.RELEASE_RELATIVE
        path.parent.mkdir(parents=True)
        original = pilot._canonical(release)
        path.write_bytes(original)
        pin = pilot._hash(original)
        self.assertEqual(
            pilot.read_frozen_release(
                data_dir=self.root, binding=FAKE_BINDING,
                release_sha256=pin,
            )["stage_id"],
            pilot.STAGE_ID,
        )
        release["approved_usd_limit"] = 2.0
        path.write_bytes(pilot._canonical(release))
        with self.assertRaisesRegex(
            pilot.SonnetPilotBlocked, "Frozen release SHA mismatch"
        ):
            pilot.read_frozen_release(
                data_dir=self.root, binding=FAKE_BINDING,
                release_sha256=pin,
            )

    def test_existing_v1_sentinel_remains_byte_identical(self):
        self._mock_release()
        sentinel = self.root / "data/rq2/frozen.txt"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_bytes(b"FROZEN_V1_NO_WRITES")
        ledger = self._ledger()
        ledger.claim_stage()
        ledger.record_stage(diagnostic_run=self._run_fake())
        self.assertEqual(sentinel.read_bytes(), b"FROZEN_V1_NO_WRITES")
        self.assertEqual(sorted(p.name for p in sentinel.parent.iterdir()),
                         ["frozen.txt"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
