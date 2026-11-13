"""RQ2-V2: unico percorso offline da run_experiment al NUOVO ledger V2.

Questo test combina il VERO runner RQ1 con il nuovo esecutore V2,
LangGraph e ToolNode reali, fake LLM/tool, preparazione del caso mock
e il NUOVO claim journal/store V2 SOLO in TemporaryDirectory.

Il case ID corrisponde a un identificativo discovery consentito dalla
policy, ma l'istruzione, i dati, le risposte C/K e le osservazioni
sono SOLO SINTETICI. Nessun Market, manifest, GT, Drive, provider o API.
Nessun dispatcher o run scientifico V2 e' implementato da questo file.
"""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import agent.graph_engine as original_graph
import agent.model_factory as model_factory
import evaluation.experiment_runner as runner
from agent.rq2_v2_graph_engine import esegui_grafo_rca_v2
from evaluation.experiment_config import ExperimentConfig
from evaluation.rq2_evidence_bundle import build_evidence_bundle, evidence_ids
from evaluation.rq2_probe_adapter import (
    prepare_candidate_rule, prepare_cause_probe,
)
from evaluation.rq2_v2_artifact_store import (
    MARKER, MARKER_BYTES, RQ2V2StoreError,
)
from evaluation.rq2_v2_claim_journal import (
    RQ2V2ClaimError, RQ2V2SyntheticClaimJournal,
)
from evaluation.rq2_v2_isolation_policy import DRAFT_PROTOCOL
from output.v2_contract import infer_requested_faults

from test_rq2_output_contracts import RQ2OutputContractsTests
from test_rq2_v2_runner_fake_e2e import (
    FINAL_JSON, ParallelSameNameFakeLLM, TOOL_NAME, fake_node_metrics,
)

# L'ID serve SOLO a soddisfare l'allowlist della policy di isolamento.
# La sorgente reale corrispondente NON viene mai letta.
FAKE_DISCOVERY_ID = "cloudbed-1_q032"
MODEL = "claude-sonnet-5-5"
INSTRUCTION = (
    "The wholly synthetic service experienced one failure "
    "during the synthetic observation window."
)


def sid(harness: str, stage: str) -> str:
    return (
        f"{DRAFT_PROTOCOL}:{FAKE_DISCOVERY_ID}:"
        f"sonnet:{harness}:{stage}"
    )


def fake_preparation(config: ExperimentConfig) -> dict:
    """I dati RCA sono inventati in questa funzione, non importati."""
    if (
        config.case_id != FAKE_DISCOVERY_ID
        or config.canonical_variant not in ("A1", "A1_8R")
        or infer_requested_faults(INSTRUCTION) != 1
    ):
        raise AssertionError("Solo la preparazione sintetica e' consentita")
    return {
        "caso": {
            "case_id": FAKE_DISCOVERY_ID,
            "cloudbed": "cloudbed-1",
            "task_index": "task_7",
            "query_index": 32,
            "instruction": INSTRUCTION,
            "start_unix": 1_700_000_000,
            "end_unix": 1_700_001_000,
        },
        "tools": [fake_node_metrics],
        "richiesta": "Synthetic only RCA request: " + INSTRUCTION,
        "evidence_report": {
            "versione": "unified_evidence_v2",
            "synthetic_observation_only": True,
        },
        "evidence_sha256": "f" * 64,
        "preprocessing_seconds": 0.0,
    }


class RQ2V2RunnerToLedgerFakeE2ETests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / MARKER).write_bytes(MARKER_BYTES)
        self.journal = RQ2V2SyntheticClaimJournal(data_dir=self.root)

    def _run_real_runner_with_fakes(self, *, harness: str) -> dict:
        llm = ParallelSameNameFakeLLM()
        config = ExperimentConfig(
            variant=harness,
            case_id=FAKE_DISCOVERY_ID,
            model_name=MODEL,
            model_provider="anthropic",
            max_tool_rounds=6,
            recursion_limit=30,
            output_contract_mode="v2_enforce",
            variant_scheme="current",
            data_dir=self.root,
            repo_dir=self.root,
        )
        with (
            patch.object(
                runner, "prepara_esperimento",
                side_effect=fake_preparation,
            ) as prep,
            patch.object(
                model_factory, "crea_modello",
                side_effect=AssertionError("PROVIDER CLIENT NOT ALLOWED"),
            ) as provider,
            patch.object(
                original_graph, "esegui_grafo_rca", esegui_grafo_rca_v2,
            ),
        ):
            result = runner.run_experiment(
                config, llm=llm, verbose=False, salva=False,
            )
        prep.assert_called_once_with(config)
        provider.assert_not_called()
        self.assertEqual(llm.invocations, 2)
        self.assertEqual(result["case_id"], FAKE_DISCOVERY_ID)
        self.assertEqual(result["variant"], harness)
        self.assertEqual(result["raw_response"], FINAL_JSON)
        self.assertEqual(result["json_status"], "valid_json")
        self.assertIsNone(result["error"])
        self.assertEqual(result["metrics"]["tool_calls"], 2)
        self.assertEqual(result["metrics"]["llm_calls"], 2)
        self.assertTrue(result["metrics"]["token_usage_complete"])
        return result

    def _record_d(self, *, harness: str) -> dict:
        # Claim PRIMA del runner, che rimane comunque solo fake.
        self.journal.claim_stage(
            stage_id=sid(harness, "D"), model_id=MODEL,
        )
        result = self._run_real_runner_with_fakes(harness=harness)
        return result

    def test_fake_runner_to_separate_dck_store_with_two_harnesses(self):
        for harness in ("A1", "A1_8R"):
            with self.subTest(harness=harness):
                d = self._record_d(harness=harness)
                bundle = build_evidence_bundle(
                    d["tool_trajectory"], allowed_tool_names={TOOL_NAME},
                )
                self.assertEqual(bundle["observations_count"], 2)
                self.assertEqual(evidence_ids(bundle), {"E001", "E002"})
                pair = {
                    e["tool_call_id"]: (
                        e["arguments"]["node"], e["observation_text"]
                    )
                    for e in bundle["evidence"]
                }
                self.assertEqual(pair, {
                    "fake-id-A": ("A", "synthetic node observation: A"),
                    "fake-id-B": ("B", "synthetic node observation: B"),
                })
                d_saved = self.journal.record_stage(
                    stage_id=sid(harness, "D"), model_id=MODEL,
                    status="RECORDED_COMPLETE",
                    artifact={"diagnostic_run": d},
                )
                self.assertEqual(d_saved["status"], "RECORDED_COMPLETE")

                c_package = prepare_cause_probe(
                    original_instruction=INSTRUCTION,
                    diagnostic_run=d,
                    allowed_tool_names={TOOL_NAME},
                )
                self.assertEqual(c_package["stage"], "C_cause_probe")
                self.assertEqual(
                    c_package["bundle_sha256"], bundle["bundle_sha256"]
                )
                self.assertFalse(c_package["ready_for_api"])
                self.assertEqual(c_package["model_api_calls"], 0)
                self.assertNotIn(
                    FINAL_JSON, c_package["messages"][1]["content"]
                )
                self.journal.claim_stage(
                    stage_id=sid(harness, "C"), model_id=MODEL,
                )
                # Il contenuto C proviene da fixture, NON da un secondo LLM.
                c_raw = json.dumps(RQ2OutputContractsTests.cause())
                self.journal.record_stage(
                    stage_id=sid(harness, "C"), model_id=MODEL,
                    status="RECORDED_COMPLETE",
                    artifact={"raw_response": c_raw},
                )
                k_package = prepare_candidate_rule(
                    original_instruction=INSTRUCTION,
                    diagnostic_run=d,
                    cause_raw_json=c_raw,
                    phase="discovery",
                    allowed_tool_names={TOOL_NAME},
                )
                self.assertEqual(k_package["stage"], "K_candidate_rule")
                self.assertEqual(
                    k_package["bundle_sha256"], bundle["bundle_sha256"]
                )
                self.assertFalse(k_package["ready_for_api"])
                self.assertEqual(k_package["model_api_calls"], 0)
                self.assertNotIn(
                    FINAL_JSON, k_package["messages"][1]["content"]
                )
                self.journal.claim_stage(
                    stage_id=sid(harness, "K"), model_id=MODEL,
                )
                self.journal.record_stage(
                    stage_id=sid(harness, "K"), model_id=MODEL,
                    status="RECORDED_COMPLETE",
                    artifact={
                        "raw_response": json.dumps(
                            RQ2OutputContractsTests.rule()
                        )
                    },
                )
                original = self.journal.store.load(
                    stage_id=sid(harness, "D"),
                )
                stored_c = self.journal.store.load(
                    stage_id=sid(harness, "C"),
                )
                stored_k = self.journal.store.load(
                    stage_id=sid(harness, "K"),
                )
                self.assertEqual(
                    stored_c["dependencies"],
                    {sid(harness, "D"): original["record_sha256"]},
                )
                self.assertEqual(
                    stored_k["dependencies"],
                    {sid(harness, "C"): stored_c["record_sha256"]},
                )
                self.assertEqual(
                    original["artifact"]["diagnostic_run"]["metrics"],
                    d["metrics"],
                )
                with self.assertRaisesRegex(
                    RQ2V2ClaimError, "NEVER auto retry"
                ):
                    self.journal.claim_stage(
                        stage_id=sid(harness, "D"), model_id=MODEL
                    )
        report = RQ2V2SyntheticClaimJournal(
            data_dir=self.root
        ).audit_restart()
        self.assertEqual(report["claims"], 6)
        self.assertEqual(report["finished_with_matching_result"], 6)
        self.assertEqual(report["stored_stage_records"], 6)
        self.assertEqual(report["unresolved_manual_review"], 0)
        self.assertFalse(report["can_execute_api"])
        self.assertFalse(report["can_execute_test"])
        self.assertFalse(report["automatic_retry_allowed"])
        self.assertFalse((self.root / "data/rq2").exists())
        self.assertFalse((self.root / "data/results").exists())
        self.assertFalse((self.root / "Market.zip").exists())
        self.assertFalse((self.root / "data/processed").exists())

    def test_corrupt_result_id_invalidates_d_and_blocks_c_k(self):
        d = self._record_d(harness="A1")
        bad = copy.deepcopy(d)
        for event in bad["tool_trajectory"]:
            if event["tipo"] == "tool_result":
                event["tool_call_id"] = "not-a-call-id"
                break
        self.journal.record_stage(
            stage_id=sid("A1", "D"), model_id=MODEL,
            status="INVALID_OUTPUT", artifact={"diagnostic_run": bad},
        )
        with self.assertRaises(RQ2V2ClaimError):
            self.journal.claim_stage(
                stage_id=sid("A1", "C"), model_id=MODEL,
            )
        for stage in ("C", "K"):
            self.journal.record_stage(
                stage_id=sid("A1", stage), model_id=MODEL,
                status="BLOCKED_DEPENDENCY", artifact={},
            )
            self.assertIsNone(self.journal.load_claim(
                stage_id=sid("A1", stage)
            ))
        report = self.journal.audit_restart()
        self.assertEqual(report["claims"], 1)
        self.assertEqual(report["stored_stage_records"], 3)
        self.assertEqual(report["finished_with_matching_result"], 1)
        self.assertEqual(report["unresolved_manual_review"], 0)

    def test_invalid_c_evidence_ref_fails_closed_and_k_is_blocked(self):
        d = self._record_d(harness="A1")
        self.journal.record_stage(
            stage_id=sid("A1", "D"), model_id=MODEL,
            status="RECORDED_COMPLETE", artifact={"diagnostic_run": d},
        )
        self.journal.claim_stage(
            stage_id=sid("A1", "C"), model_id=MODEL,
        )
        bad_c = RQ2OutputContractsTests.cause()
        bad_c["evidence_ids"] = ["E999"]
        raw = json.dumps(bad_c)
        with self.assertRaisesRegex(
            RQ2V2StoreError, "status/contract mismatch"
        ):
            self.journal.record_stage(
                stage_id=sid("A1", "C"), model_id=MODEL,
                status="RECORDED_COMPLETE",
                artifact={"raw_response": raw},
            )
        # Conserviamo il tentativo non valido; non riscriviamo come completo.
        self.journal.record_stage(
            stage_id=sid("A1", "C"), model_id=MODEL,
            status="INVALID_OUTPUT",
            artifact={"raw_response": raw},
        )
        self.journal.record_stage(
            stage_id=sid("A1", "K"), model_id=MODEL,
            status="BLOCKED_DEPENDENCY", artifact={},
        )
        self.assertIsNone(
            self.journal.load_claim(stage_id=sid("A1", "K"))
        )
        report = self.journal.audit_restart()
        self.assertEqual(report["claims"], 2)
        self.assertEqual(report["stored_stage_records"], 3)
        self.assertEqual(report["unresolved_manual_review"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
