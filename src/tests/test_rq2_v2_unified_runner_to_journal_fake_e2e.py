"""G3B: vero run_experiment/ToolNode -> journal UNIFICATO; tutto FAKE.

Questa e' una prova E2E della CONTINUITA' tra i moduli gia' congelati:
RQ1 runner, motori D ReAct-V2 e verify_graph, provenance, C/K adapter,
parser JSON e claim/record create-only. Le risposte LLM sono create
esplicitamente nel test e i tool restituiscono soltanto testo sintetico.

Non legge OpenRCA Market, GT, scorer o log reali; NON invoca provider/SDK.
Non contiene un dispatcher live né autorizza un rilascio scientifico.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import agent.graph_engine as react_graph
import agent.model_factory as model_factory
import evaluation.experiment_runner as runner
import harness.structural_temporal_verifier as structural
from agent.rq2_v2_graph_engine import esegui_grafo_rca_v2
from evaluation.experiment_config import ExperimentConfig
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_evidence_bundle import (
    build_evidence_bundle, evidence_ids,
)
from evaluation.rq2_output_contracts import (
    validate_cause_probe, validate_candidate_rule,
)
from evaluation.rq2_probe_adapter import (
    prepare_cause_probe, prepare_candidate_rule,
)
from evaluation.rq2_stage_binding import ALLOWED_TOOLS
from evaluation.rq2_v2_artifact_store import MARKER, MARKER_BYTES
from evaluation.rq2_v2_unified_discovery_plan import (
    DISCOVERY, HARNESSES, MODELS, TEST, VERSION,
)
from evaluation.rq2_v2_unified_synthetic_journal import (
    UnifiedRQ2SyntheticJournal, UnifiedRQ2JournalError,
)
from evaluation.rq2_v2_unified_provenance_gate import audit_captured_v2_d

import test_rq2_v2_unified_graph_fake_e2e as fixtures


def sid(model: str, harness: str, stage: str) -> str:
    return f"{VERSION}:{DISCOVERY[0]}:{model}:{harness}:{stage}"


class UnifiedRunnerToJournalFakeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(
            prefix="rq2_v2_unified_runner_to_journal_fake_"
        )
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / MARKER).write_bytes(MARKER_BYTES)
        self.journal = UnifiedRQ2SyntheticJournal(data_dir=self.root)

    @staticmethod
    def _model_id(model: str) -> str:
        return CANDIDATE_MODELS[model]["model_id"]

    def _real_d_with_fake_llm(
        self, model: str, harness: str, *,
        final_json: str = fixtures.FINAL_JSON,
    ) -> dict:
        """La claim D deve gia' esistere PRIMA dell'invocazione."""
        self.assertIsNotNone(
            self.journal.load_claim(stage_id=sid(model, harness, "D"))
        )
        cfg = ExperimentConfig(
            variant=harness,
            case_id=DISCOVERY[0],
            model_name=self._model_id(model),
            model_provider=CANDIDATE_MODELS[model]["provider"],
            max_tool_rounds=6,
            max_verification_checks=2,
            recursion_limit=30,
            variant_scheme="current",
            output_contract_mode="v2_enforce",
            data_dir=self.root,
            repo_dir=self.root,
        )
        planning = harness in ("A1_8R_Planning", "A1_PAVE")
        fake = fixtures.FakeDiagnosisLLM(
            planning=planning, final_json=final_json,
        )
        with (
            patch.object(runner, "prepara_esperimento",
                         side_effect=fixtures.fake_preparation) as prep,
            patch.object(model_factory, "crea_modello",
                         side_effect=AssertionError("SDK CLIENT FORBIDDEN")) as sdk,
            patch.object(react_graph, "esegui_grafo_rca",
                         esegui_grafo_rca_v2),
            patch.object(
                structural, "costruisci_contesto_strutturale_temporale",
                side_effect=fixtures.fake_structural_context,
            ),
        ):
            result = runner.run_experiment(
                cfg, llm=fake, verbose=False, salva=False,
            )
        prep.assert_called_once_with(cfg)
        sdk.assert_not_called()
        self.assertEqual(fake.exploration_calls, 2)
        self.assertEqual(fake.final_calls, 1 if planning else 0)
        self.assertEqual(result["case_id"], DISCOVERY[0])
        self.assertEqual(result["variant"], harness)
        self.assertEqual(result["model"], self._model_id(model))
        self.assertEqual(result["model_provider"], CANDIDATE_MODELS[model]["provider"])
        self.assertEqual(result["metrics"]["tool_calls"], 3 if planning else 2)
        self.assertEqual(result["metrics"]["tool_rounds"], 2 if planning else 1)
        self.assertIsNone(result["error"])
        return result

    def _record_pipeline(
        self, model: str, harness: str, *,
        d_json: str = fixtures.FINAL_JSON,
        c_data: dict | None = None,
        k_data: dict | None = None,
    ) -> dict:
        """Test orchestrator esplicito: D claim -> run -> record -> C -> K.

        NON espone un callback verso SDK/provider e puo' usare soltanto
        fixture controllate dal test. Uno stage fallito blocca le dipendenze.
        """
        model_id = self._model_id(model)
        d_id, c_id, k_id = (
            sid(model, harness, stage) for stage in ("D", "C", "K")
        )

        self.journal.claim_stage(stage_id=d_id, model_id=model_id)
        d = self._real_d_with_fake_llm(model, harness, final_json=d_json)
        d_status = (
            "RECORDED_COMPLETE" if d["json_status"] == "valid_json"
            else "INVALID_OUTPUT"
        )
        self.journal.record_stage(
            stage_id=d_id, model_id=model_id, status=d_status,
            artifact={"diagnostic_run": d},
        )
        if d_status != "RECORDED_COMPLETE":
            for stage_id in (c_id, k_id):
                self.journal.record_stage(
                    stage_id=stage_id, model_id=model_id,
                    status="BLOCKED_DEPENDENCY", artifact={},
                )
            return {"D": d_status, "C": "BLOCKED_DEPENDENCY",
                    "K": "BLOCKED_DEPENDENCY"}

        # Verifica separata della provenance prima di usare gli E###.
        prov = audit_captured_v2_d(
            run=d, case_id=DISCOVERY[0],
            model=model, harness=harness,
        )
        bundle = build_evidence_bundle(
            d["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS,
        )
        self.assertEqual(prov["evidence_bundle_sha256"], bundle["bundle_sha256"])
        self.assertEqual(
            bundle["observations_count"],
            3 if harness in ("A1_8R_Planning", "A1_PAVE") else 2,
        )

        self.journal.claim_stage(stage_id=c_id, model_id=model_id)
        c_pack = prepare_cause_probe(
            original_instruction=fixtures.INSTRUCTION, diagnostic_run=d,
            allowed_tool_names=ALLOWED_TOOLS,
        )
        c_obj = fixtures.synthetic_c() if c_data is None else c_data
        c_raw, c_info, c_fake = fixtures.fake_toolfree_stage(
            model, c_pack, json.dumps(c_obj),
        )
        self.assertEqual(c_fake.calls, 1)
        self.assertEqual(c_info[0], "str" if model == "gemini" else "list")
        try:
            validate_cause_probe(
                c_raw, allowed_evidence_ids=evidence_ids(bundle)
            )
        except (TypeError, ValueError):
            c_status = "INVALID_OUTPUT"
        else:
            c_status = "RECORDED_COMPLETE"
        self.journal.record_stage(
            stage_id=c_id, model_id=model_id, status=c_status,
            artifact={"raw_response": c_raw},
        )
        if c_status != "RECORDED_COMPLETE":
            self.journal.record_stage(
                stage_id=k_id, model_id=model_id,
                status="BLOCKED_DEPENDENCY", artifact={},
            )
            return {"D": d_status, "C": c_status,
                    "K": "BLOCKED_DEPENDENCY"}

        self.journal.claim_stage(stage_id=k_id, model_id=model_id)
        k_pack = prepare_candidate_rule(
            original_instruction=fixtures.INSTRUCTION,
            diagnostic_run=d, cause_raw_json=c_raw,
            phase="discovery", allowed_tool_names=ALLOWED_TOOLS,
        )
        self.assertEqual(c_pack["bundle_sha256"], k_pack["bundle_sha256"])
        k_obj = fixtures.synthetic_k() if k_data is None else k_data
        k_raw, k_info, k_fake = fixtures.fake_toolfree_stage(
            model, k_pack, json.dumps(k_obj),
        )
        self.assertEqual(k_fake.calls, 1)
        self.assertEqual(k_info[0], "str" if model == "gemini" else "list")
        try:
            validate_candidate_rule(
                k_raw, allowed_evidence_ids=evidence_ids(bundle)
            )
        except (TypeError, ValueError):
            k_status = "INVALID_OUTPUT"
        else:
            k_status = "RECORDED_COMPLETE"
        self.journal.record_stage(
            stage_id=k_id, model_id=model_id, status=k_status,
            artifact={"raw_response": k_raw},
        )
        return {"D": d_status, "C": c_status, "K": k_status}

    def test_all_15_real_graph_d_to_common_journal_dck(self):
        # 15 sottotest x 3 stage = 45 record, senza provider, GT o Market.
        expected = {"D": "RECORDED_COMPLETE", "C": "RECORDED_COMPLETE",
                    "K": "RECORDED_COMPLETE"}
        total = 0
        for model in MODELS:
            for harness in HARNESSES:
                with self.subTest(model=model, harness=harness):
                    state = self._record_pipeline(model, harness)
                    self.assertEqual(state, expected)
                    self.assertEqual(
                        self.journal.load_record(
                            stage_id=sid(model, harness, "K")
                        )["status"],
                        "RECORDED_COMPLETE",
                    )
                    total += 3
        self.assertEqual(total, 45)
        audit = UnifiedRQ2SyntheticJournal(data_dir=self.root).audit_restart()
        self.assertEqual(audit["claims"], 45)
        self.assertEqual(audit["stored_stage_records"], 45)
        self.assertEqual(audit["matched_claim_records"], 45)
        self.assertEqual(audit["unresolved_claims_for_manual_review"], 0)
        self.assertFalse(audit["can_execute_api"])
        self.assertFalse(audit["can_run_ood_test"])
        self.assertFalse(audit["automatic_retry_allowed"])
        self.assertFalse((self.root / "Market.zip").exists())
        self.assertFalse((self.root / "data/rq2").exists())
        self.assertFalse((self.root / "data/results").exists())

    def test_planning_and_pave_record_native_planner_origin(self):
        for harness in ("A1_8R_Planning", "A1_PAVE"):
            with self.subTest(harness=harness):
                self._record_pipeline("gemini", harness)
                d = self.journal.load_record(
                    stage_id=sid("gemini", harness, "D")
                )["artifact"]["diagnostic_run"]
                b = build_evidence_bundle(
                    d["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS,
                )
                self.assertEqual(
                    {x["call_origin"] for x in b["evidence"]},
                    {"llm", "planner"},
                )

    def test_real_graph_invalid_d_is_stored_and_c_k_are_blocked(self):
        states = self._record_pipeline(
            "sonnet", "A0", d_json="INTENTIONALLY INVALID D JSON",
        )
        self.assertEqual(states, {
            "D": "INVALID_OUTPUT", "C": "BLOCKED_DEPENDENCY",
            "K": "BLOCKED_DEPENDENCY",
        })
        audit = self.journal.audit_restart()
        self.assertEqual(audit["claims"], 1)
        self.assertEqual(audit["stored_stage_records"], 3)
        self.assertFalse(audit["can_execute_api"])

    def test_c_forged_evidence_blocks_k_without_claim(self):
        bad_c = fixtures.synthetic_c()
        bad_c["evidence_ids"] = ["E999"]
        states = self._record_pipeline(
            "haiku", "A1_8R", c_data=bad_c,
        )
        self.assertEqual(states, {
            "D": "RECORDED_COMPLETE", "C": "INVALID_OUTPUT",
            "K": "BLOCKED_DEPENDENCY",
        })
        self.assertIsNone(
            self.journal.load_claim(stage_id=sid("haiku", "A1_8R", "K"))
        )
        self.assertEqual(self.journal.audit_restart()["claims"], 2)

    def test_invalid_k_reference_is_recorded_without_fake_repair(self):
        invalid_k = fixtures.synthetic_k()
        invalid_k["evidence_ids"] = ["E999"]
        outcome = self._record_pipeline(
            "gemini", "A1_PAVE", k_data=invalid_k,
        )
        self.assertEqual(outcome, {
            "D": "RECORDED_COMPLETE", "C": "RECORDED_COMPLETE",
            "K": "INVALID_OUTPUT",
        })
        rec = self.journal.load_record(
            stage_id=sid("gemini", "A1_PAVE", "K"),
        )
        self.assertEqual(rec["status"], "INVALID_OUTPUT")
        self.assertIn("E999", rec["artifact"]["raw_response"])
        report = self.journal.audit_restart()
        self.assertEqual(report["claims"], 3)
        self.assertEqual(report["stored_stage_records"], 3)

    def test_fake_provider_failure_in_d_blocks_c_k_without_retry(self):
        model, harness = "haiku", "A0"
        name = self._model_id(model)
        d_id, c_id, k_id = (
            sid(model, harness, stage) for stage in ("D", "C", "K")
        )
        # Fallimento artificiale, senza alcuna richiesta al provider.
        self.journal.claim_stage(stage_id=d_id, model_id=name)
        self.journal.record_stage(
            stage_id=d_id, model_id=name, status="PROVIDER_ERROR",
            artifact={"provider_error": "FAKE HTTP 503: no network call"},
        )
        for st_id in (c_id, k_id):
            self.journal.record_stage(
                stage_id=st_id, model_id=name,
                status="BLOCKED_DEPENDENCY", artifact={},
            )
        audit = self.journal.audit_restart()
        self.assertEqual(audit["claims"], 1)
        self.assertEqual(audit["stored_stage_records"], 3)
        self.assertIsNone(self.journal.load_claim(stage_id=c_id))
        self.assertIsNone(self.journal.load_claim(stage_id=k_id))
        self.assertFalse(audit["automatic_retry_allowed"])

    def test_c_abstains_k_insufficient_is_real_valid_outcome(self):
        states = self._record_pipeline(
            "sonnet", "A1_8R_Planning",
            c_data=fixtures.synthetic_c(abstain=True),
            k_data=fixtures.synthetic_k(insufficient=True),
        )
        self.assertEqual(states["K"], "RECORDED_COMPLETE")
        k = self.journal.load_record(
            stage_id=sid("sonnet", "A1_8R_Planning", "K")
        )
        raw = json.loads(k["artifact"]["raw_response"])
        self.assertEqual(raw["status"], "insufficient_evidence")
        self.assertEqual(self.journal.audit_restart()["claims"], 3)

    def test_fake_crash_after_claim_never_automatically_retries(self):
        stage_id = sid("gemini", "A0", "D")
        self.journal.claim_stage(
            stage_id=stage_id, model_id=self._model_id("gemini"),
        )
        # Nessuna richiesta viene effettuata dopo il crash sintetico.
        after_crash = UnifiedRQ2SyntheticJournal(data_dir=self.root)
        self.assertEqual(
            after_crash.audit_restart()["unresolved_claims_for_manual_review"], 1
        )
        with self.assertRaisesRegex(UnifiedRQ2JournalError, "never auto retry"):
            after_crash.claim_stage(
                stage_id=stage_id, model_id=self._model_id("gemini"),
            )
        self.assertIsNone(after_crash.load_record(stage_id=stage_id))

    def test_only_synthetic_root_is_ever_used(self):
        self._record_pipeline("gemini", "A1")
        self.assertTrue((self.root / MARKER).is_file())
        self.assertFalse((self.root / "Market.zip").exists())
        self.assertFalse((self.root / "data/processed").exists())
        self.assertFalse((self.root / "data/results").exists())
        self.assertFalse((self.root / "data/rq2").exists())
        # Gli ID di test sono definiti nel piano, ma non dispatchabili.
        self.assertTrue(set(TEST).isdisjoint({DISCOVERY[0]}))
        self.assertFalse(self.journal.audit_restart()["can_run_ood_test"])


if __name__ == "__main__":
    unittest.main()
