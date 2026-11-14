"""G4G: runner LangGraph vero + fake gateway + ledger scientifico G4F.

TUTTO nella TemporaryDirectory con release/approval FINTI e marker FAKE.
Il codice del dispatcher non costruisce client SDK, non legge benchmark e
non possiede alcun canale live. Gli E### sono dati di tool finti.
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
import evaluation.rq2_v2_unified_scientific_ledger as ledger_code
import harness.structural_temporal_verifier as structural
from agent.rq2_v2_graph_engine import esegui_grafo_rca_v2
from evaluation.experiment_config import ExperimentConfig
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_v2_unified_discovery_plan import (
    DISCOVERY, HARNESSES, MODELS, TEST,
)
from evaluation.rq2_v2_unified_dispatcher_offline import (
    MARKER, MARKER_BYTES, OfflineDispatchBlocked, OfflineFakeGateway,
    OfflineStageResponse, SimulatedProviderFailure, run_offline_fake_triplet,
)
from evaluation.rq2_v2_unified_scientific_ledger import (
    UnifiedScientificLedger, UnifiedScientificLedgerBlocked,
)
from evaluation.rq2_v2_unified_scientific_release_contract import (
    canonical_release, release_digest,
)
from evaluation.rq2_v2_unified_release_blueprint import (
    build_unified_release_blueprint,
)
from test_rq2_v2_unified_scientific_release_contract_offline import (
    FAKE_COMMIT, release_fixture, source_fixture,
)
from test_rq2_v2_unified_scientific_ledger_offline import (
    meter, sid,
)
import test_rq2_v2_unified_graph_fake_e2e as fixtures


class OfflineLangGraphFakeGateway(OfflineFakeGateway):
    def __init__(self, *, root: Path, failure=None, d_json=None,
                 c_data=None, k_data=None):
        self.root = root
        self.failure = failure
        self.d_json = d_json
        self.c_data = c_data
        self.k_data = k_data
        self.calls = {"D": 0, "C": 0, "K": 0}

    def _maybe_fail(self, stage):
        self.calls[stage] += 1
        if self.failure == stage:
            raise SimulatedProviderFailure("simulated no-network 503")
        if self.failure == stage + "_CRASH":
            raise KeyboardInterrupt("simulated process interruption")

    def run_d(self, *, case_id: str, model: str,
              harness: str) -> OfflineStageResponse:
        self._maybe_fail("D")
        model_info = CANDIDATE_MODELS[model]
        config = ExperimentConfig(
            variant=harness, case_id=case_id,
            model_name=model_info["model_id"],
            model_provider=model_info["provider"],
            max_tool_rounds=6, max_verification_checks=2,
            recursion_limit=30, variant_scheme="current",
            output_contract_mode="v2_enforce",
            data_dir=self.root, repo_dir=self.root,
        )
        is_planner = harness in ("A1_8R_Planning", "A1_PAVE")
        fake = fixtures.FakeDiagnosisLLM(
            planning=is_planner,
            final_json=self.d_json if self.d_json is not None
            else fixtures.FINAL_JSON,
        )
        with (
            patch.object(runner, "prepara_esperimento",
                         side_effect=fixtures.fake_preparation) as prepared,
            patch.object(model_factory, "crea_modello",
                         side_effect=AssertionError("NO LIVE SDK")) as sdk,
            patch.object(react_graph, "esegui_grafo_rca",
                         esegui_grafo_rca_v2),
            patch.object(
                structural, "costruisci_contesto_strutturale_temporale",
                side_effect=fixtures.fake_structural_context,
            ),
        ):
            result = runner.run_experiment(
                config, llm=fake, verbose=False, salva=False,
            )
        prepared.assert_called_once_with(config)
        sdk.assert_not_called()
        self.assertEqual_case(result, case_id, model, harness)
        count = fake.exploration_calls + fake.final_calls
        assert count == (3 if is_planner else 2), count
        # Le osservazioni vengono create dal fake LLM; non sono
        # token fatturati o costi reali.
        return OfflineStageResponse(
            output=result, meter=meter(requests=count),
        )

    @staticmethod
    def assert_equal_case(result, case_id, model, harness):
        assert result["case_id"] == case_id
        assert result["variant"] == harness
        assert result["model"] == CANDIDATE_MODELS[model]["model_id"]
        assert result["error"] is None

    def run_c(self, *, package: dict, model: str) -> OfflineStageResponse:
        self._maybe_fail("C")
        payload = self.c_data if self.c_data is not None else fixtures.synthetic_c()
        raw, info, fake = fixtures.fake_toolfree_stage(
            model, package, json.dumps(payload),
        )
        assert fake.calls == 1
        assert info[0] == ("str" if model == "gemini" else "list")
        return OfflineStageResponse(output=raw, meter=meter())

    def run_k(self, *, package: dict, model: str) -> OfflineStageResponse:
        self._maybe_fail("K")
        payload = self.k_data if self.k_data is not None else fixtures.synthetic_k()
        raw, info, fake = fixtures.fake_toolfree_stage(
            model, package, json.dumps(payload),
        )
        assert fake.calls == 1
        assert info[0] == ("str" if model == "gemini" else "list")
        return OfflineStageResponse(output=raw, meter=meter())


class UnifiedFakeDispatcherScientificLedgerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(
            prefix="rq2_v2_fake_dispatch_scientific_"
        )
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "synthetic_data"
        self.repo = self.root / "synthetic_repo"
        self.data.mkdir()
        (self.repo / "src").mkdir(parents=True)
        (self.data / MARKER).write_bytes(MARKER_BYTES)
        self.source = source_fixture()
        self.blueprint = build_unified_release_blueprint(
            source_preview=self.source,
        )
        release = release_fixture(self.source, self.blueprint)
        self.approved_sha = release_digest(release)
        release_path = self.data / ledger_code.RELEASE_FILE
        release_path.parent.mkdir(parents=True)
        release_path.write_bytes(canonical_release(release))
        git = patch.object(
            ledger_code, "_repository_commit", return_value=(FAKE_COMMIT, ""),
        )
        sources = patch.object(
            ledger_code, "preview_unified_source_bound",
            return_value=self.source,
        )
        self.addCleanup(git.stop)
        self.addCleanup(sources.stop)
        git.start()
        sources.start()
        self.ledger = self.reopen()
        self.gateway = OfflineLangGraphFakeGateway(root=self.data)

    def reopen(self):
        return UnifiedScientificLedger(
            data_dir=self.data, repo_dir=self.repo,
            expected_commit=FAKE_COMMIT,
            approved_release_sha256=self.approved_sha,
        )

    def run_one(self, *, case=DISCOVERY[0], model="gemini",
                harness="A0", gateway=None):
        return run_offline_fake_triplet(
            ledger=self.ledger,
            gateway=gateway if gateway is not None else self.gateway,
            case_id=case, model=model, harness=harness,
            original_instruction=fixtures.INSTRUCTION,
        )

    def test_all_15_arms_real_graph_toolnode_to_scientific_ledger(self):
        expected = {
            "D": "RECORDED_COMPLETE", "C": "RECORDED_COMPLETE",
            "K": "RECORDED_COMPLETE",
        }
        for model in MODELS:
            for harness in HARNESSES:
                with self.subTest(model=model, harness=harness):
                    result = self.run_one(
                        model=model, harness=harness,
                        gateway=OfflineLangGraphFakeGateway(root=self.data),
                    )
                    self.assertEqual(result["stage_status"], expected)
                    self.assertFalse(result["can_execute_api"])
                    d = self.ledger.load_record(
                        stage_id=sid(model, harness, "D")
                    )
                    self.assertEqual(d["artifact"]["stage_meter"][
                        "observed_model_requests"
                    ], 3 if harness in ("A1_8R_Planning", "A1_PAVE") else 2)
        restarted = self.reopen().audit_restart()
        self.assertEqual(restarted["claims"], 45)
        self.assertEqual(restarted["records"], 45)
        self.assertEqual(restarted["orphan_claims"], 0)
        self.assertFalse(restarted["automatic_retry_allowed"])
        self.assertFalse(restarted["can_execute_api"])

    def test_fake_d_provider_error_blocks_c_k(self):
        gateway = OfflineLangGraphFakeGateway(root=self.data, failure="D")
        result = self.run_one(gateway=gateway)
        self.assertEqual(result["stage_status"], {
            "D": "PROVIDER_ERROR", "C": "BLOCKED_DEPENDENCY",
            "K": "BLOCKED_DEPENDENCY",
        })
        self.assertEqual(gateway.calls, {"D": 1, "C": 0, "K": 0})
        self.assertEqual(self.ledger.audit_restart()["claims"], 1)
        self.assertEqual(self.ledger.audit_restart()["records"], 3)

    def test_fake_c_provider_error_blocks_k(self):
        gateway = OfflineLangGraphFakeGateway(root=self.data, failure="C")
        result = self.run_one(gateway=gateway)
        self.assertEqual(result["stage_status"], {
            "D": "RECORDED_COMPLETE", "C": "PROVIDER_ERROR",
            "K": "BLOCKED_DEPENDENCY",
        })
        self.assertEqual(gateway.calls, {"D": 1, "C": 1, "K": 0})
        self.assertEqual(self.ledger.audit_restart()["claims"], 2)

    def test_fake_k_provider_error_records_error_without_retry(self):
        gateway = OfflineLangGraphFakeGateway(root=self.data, failure="K")
        result = self.run_one(gateway=gateway)
        self.assertEqual(result["stage_status"]["K"], "PROVIDER_ERROR")
        self.assertEqual(gateway.calls, {"D": 1, "C": 1, "K": 1})
        self.assertEqual(self.ledger.audit_restart()["claims"], 3)

    def test_invalid_d_output_blocks_later_stages(self):
        gateway = OfflineLangGraphFakeGateway(
            root=self.data, d_json="invalid json fake",
        )
        result = self.run_one(gateway=gateway)
        self.assertEqual(result["stage_status"], {
            "D": "INVALID_OUTPUT", "C": "BLOCKED_DEPENDENCY",
            "K": "BLOCKED_DEPENDENCY",
        })
        self.assertEqual(gateway.calls, {"D": 1, "C": 0, "K": 0})

    def test_invalid_c_evidence_blocks_k(self):
        invalid = fixtures.synthetic_c()
        invalid["evidence_ids"] = ["E999"]
        gateway = OfflineLangGraphFakeGateway(
            root=self.data, c_data=invalid,
        )
        result = self.run_one(gateway=gateway)
        self.assertEqual(result["stage_status"], {
            "D": "RECORDED_COMPLETE", "C": "INVALID_OUTPUT",
            "K": "BLOCKED_DEPENDENCY",
        })
        self.assertEqual(gateway.calls, {"D": 1, "C": 1, "K": 0})

    def test_invalid_k_preserves_forged_evidence_as_invalid(self):
        invalid = fixtures.synthetic_k()
        invalid["evidence_ids"] = ["E999"]
        gateway = OfflineLangGraphFakeGateway(root=self.data, k_data=invalid)
        result = self.run_one(gateway=gateway)
        self.assertEqual(result["stage_status"]["K"], "INVALID_OUTPUT")
        record = self.ledger.load_record(stage_id=sid(stage="K"))
        self.assertIn("E999", record["artifact"]["raw_response"])

    def test_c_abstain_k_insufficient_is_valid_outcome(self):
        gateway = OfflineLangGraphFakeGateway(
            root=self.data,
            c_data=fixtures.synthetic_c(abstain=True),
            k_data=fixtures.synthetic_k(insufficient=True),
        )
        result = self.run_one(gateway=gateway)
        self.assertEqual(result["stage_status"]["K"], "RECORDED_COMPLETE")
        self.assertEqual(
            json.loads(self.ledger.load_record(
                stage_id=sid(stage="K")
            )["artifact"]["raw_response"])["status"], "insufficient_evidence",
        )

    def test_crash_after_claim_stays_orphan_and_blocks_new_stage(self):
        gateway = OfflineLangGraphFakeGateway(
            root=self.data, failure="D_CRASH",
        )
        with self.assertRaises(KeyboardInterrupt):
            self.run_one(gateway=gateway)
        self.assertEqual(self.reopen().audit_restart()["orphan_claims"], 1)
        with self.assertRaisesRegex(
            UnifiedScientificLedgerBlocked, "Unresolved claim",
        ):
            self.run_one(gateway=OfflineLangGraphFakeGateway(root=self.data))

    def test_locked_ood_stage_rejected_without_claim(self):
        with self.assertRaises(OfflineDispatchBlocked):
            self.run_one(case=TEST[0])
        self.assertEqual(self.ledger.audit_restart()["claims"], 0)

    def test_missing_fake_marker_rejected_without_claim(self):
        (self.data / MARKER).unlink()
        with self.assertRaisesRegex(OfflineDispatchBlocked, "marker"):
            self.run_one()
        self.assertEqual(self.ledger.audit_restart()["claims"], 0)

    def test_not_a_real_approval_is_explicitly_enforced(self):
        path = self.data / ledger_code.RELEASE_FILE
        source = path.read_bytes()
        path.write_bytes(source.replace(
            b"SYNTHETIC_APPROVAL_NOT_REAL",
            b"APPROVED_BY_A_PERSON", 1,
        ))
        with self.assertRaises(OfflineDispatchBlocked):
            self.run_one()
        self.assertFalse((self.data / ledger_code.CLAIMS).exists())

    def test_duplicate_execution_never_auto_retries(self):
        self.run_one()
        with self.assertRaises(UnifiedScientificLedgerBlocked):
            self.run_one(gateway=OfflineLangGraphFakeGateway(root=self.data))
        self.assertEqual(self.ledger.audit_restart()["claims"], 3)

    def test_no_market_gt_historical_artifacts_or_sdk(self):
        self.run_one(model="sonnet", harness="A1_PAVE")
        for path in (
            "Market.zip", "data/processed", "data/results",
            "data/rq2", "data/rq2_v2_provenance",
            "data/rq2_v2_unified_synthetic_v0",
        ):
            self.assertFalse((self.data / path).exists(), path)
        self.assertTrue((self.data / MARKER).is_file())
        self.assertFalse(self.ledger.audit_restart()["can_execute_api"])


if __name__ == "__main__":
    unittest.main()
