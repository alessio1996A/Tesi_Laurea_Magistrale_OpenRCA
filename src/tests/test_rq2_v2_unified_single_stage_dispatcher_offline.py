"""G4I: E2E single-stage scientific ledger with REAL graphs and fake LLMs.

Manifest e release sono inventati in TemporaryDirectory. La verifica GT-free
del codice G4F e' simulata dalla fixture: NON prova dati/Drive reali.
Il gateway reale RQ2 SDK NON viene mai costruito e le socket sono vietate.
"""
from __future__ import annotations

import csv
import hashlib
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluation.rq2_v2_unified_scientific_ledger as ledger_code
import evaluation.rq2_v2_unified_single_stage_dispatcher as dispatcher
from evaluation.rq2_probe_adapter import CAUSE_SYSTEM, RULE_SYSTEM
from evaluation.rq2_v2_unified_discovery_plan import DISCOVERY, TEST
from evaluation.rq2_v2_unified_scientific_release_contract import (
    canonical_release, release_digest,
)
from evaluation.rq2_v2_unified_release_blueprint import (
    build_unified_release_blueprint,
)
from evaluation.rq2_v2_unified_scientific_ledger import (
    UnifiedScientificLedger, UnifiedScientificLedgerBlocked,
)
from evaluation.rq2_v2_unified_single_stage_dispatcher import (
    MARKER, MARKER_BYTES, UnifiedSingleStageBlocked,
    run_one_unified_stage_fake,
)
from test_rq2_v2_unified_live_stage_preflight_offline import (
    CSV_HEADER, FAKE_INSTRUCTION,
)
from test_rq2_v2_unified_dispatcher_offline_e2e import (
    OfflineLangGraphFakeGateway,
)
from test_rq2_v2_unified_scientific_release_contract_offline import (
    FAKE_COMMIT, release_fixture, source_fixture,
)
from test_rq2_v2_unified_scientific_ledger_offline import sid


class SourceBoundSingleStageFakeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(
            prefix="rq2_v2_g4i_fake_stage_"
        )
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.data = self.root / "synthetic_data"
        self.repo = self.root / "synthetic_repo"
        self.data.mkdir()
        (self.repo / "src").mkdir(parents=True)
        (self.data / MARKER).write_bytes(MARKER_BYTES)

        source = source_fixture()
        source["C_system_prompt_sha256"] = hashlib.sha256(
            CAUSE_SYSTEM.encode("utf-8")
        ).hexdigest()
        source["K_system_prompt_sha256"] = hashlib.sha256(
            RULE_SYSTEM.encode("utf-8")
        ).hexdigest()
        blueprint = build_unified_release_blueprint(source_preview=source)
        release = release_fixture(source, blueprint)
        self.approved_sha = release_digest(release)
        release_path = self.data / ledger_code.RELEASE_FILE
        release_path.parent.mkdir(parents=True)
        release_path.write_bytes(canonical_release(release))

        processed = self.data / "data/processed"
        processed.mkdir(parents=True)
        manifest = processed / "benchmark_inputs_market.csv"
        with manifest.open("w", encoding="utf-8", newline="") as stream:
            w = csv.writer(stream)
            w.writerow(CSV_HEADER)
            w.writerow([
                DISCOVERY[0], FAKE_INSTRUCTION, "1",
                "cloudbed-1", 1760000000, 1760000600, 32,
            ])

        git = patch.object(
            ledger_code, "_repository_commit",
            return_value=(FAKE_COMMIT, ""),
        )
        sources = patch.object(
            ledger_code, "preview_unified_source_bound",
            return_value=source,
        )
        git.start()
        sources.start()
        self.addCleanup(git.stop)
        self.addCleanup(sources.stop)
        self.ledger = self.open_ledger()
        self.gateway = OfflineLangGraphFakeGateway(root=self.data)

    def open_ledger(self):
        return UnifiedScientificLedger(
            data_dir=self.data,
            repo_dir=self.repo,
            expected_commit=FAKE_COMMIT,
            approved_release_sha256=self.approved_sha,
        )

    def run_stage(self, stage="D", *, model="gemini", harness="A0",
                  case=None, gateway=None):
        return run_one_unified_stage_fake(
            data_dir=self.data,
            repo_dir=self.repo,
            stage_id=sid(model, harness, stage, case=case),
            expected_commit=FAKE_COMMIT,
            approved_release_sha256=self.approved_sha,
            gateway=self.gateway if gateway is None else gateway,
        )

    def run_dck(self, *, model="gemini", harness="A0"):
        return [
            self.run_stage(stage, model=model, harness=harness)
            for stage in ("D", "C", "K")
        ]

    def test_three_stages_across_three_model_harness_paths(self):
        for model, harness in (
            ("gemini", "A0"),
            ("sonnet", "A1_8R_Planning"),
            ("haiku", "A1_PAVE"),
        ):
            with self.subTest(model=model, harness=harness):
                responses = self.run_dck(model=model, harness=harness)
                self.assertEqual(
                    [r["record_status"] for r in responses],
                    ["RECORDED_COMPLETE"] * 3,
                )
                self.assertTrue(all(
                    r["real_provider_requests"] == 0
                    and r["can_execute_api"] is False
                    and r["can_run_ood_test"] is False
                    and r["downstream_blocked"] == []
                    for r in responses
                ))
                self.assertEqual(
                    responses[0]["simulated_model_invocations"],
                    3 if harness in ("A1_PAVE", "A1_8R_Planning") else 2,
                )
        audit = self.open_ledger().audit_restart()
        self.assertEqual((audit["claims"], audit["records"]), (9, 9))
        self.assertEqual(audit["orphan_claims"], 0)

    def test_d_only_creates_one_record_and_no_ck(self):
        outcome = self.run_stage()
        self.assertEqual(outcome["stage"], "D")
        self.assertEqual(outcome["status"], "FAKE_STAGE_RECORDED_NO_API")
        self.assertEqual(self.open_ledger().audit_restart()["records"], 1)
        self.assertIsNone(self.ledger.load_record(stage_id=sid(stage="C")))
        self.assertIsNone(self.ledger.load_record(stage_id=sid(stage="K")))
        self.assertFalse((self.data / "Market.zip").exists())

    def test_c_requires_completed_d_before_claim(self):
        with self.assertRaises(Exception):
            self.run_stage("C")
        self.assertEqual(self.ledger.audit_restart()["claims"], 0)

    def test_k_requires_completed_c_before_claim(self):
        self.run_stage("D")
        with self.assertRaises(Exception):
            self.run_stage("K")
        self.assertEqual(self.ledger.audit_restart()["claims"], 1)

    def test_ood_case_is_rejected_without_writes(self):
        with self.assertRaises(Exception):
            self.run_stage(case=TEST[0])
        self.assertEqual(self.ledger.audit_restart()["claims"], 0)

    def test_d_failure_archives_c_and_k_as_blocked(self):
        result = self.run_stage(
            gateway=OfflineLangGraphFakeGateway(
                root=self.data, d_json="not-json-synthetic",
            ),
        )
        self.assertEqual(result["record_status"], "INVALID_OUTPUT")
        self.assertEqual(
            [s.rsplit(":", 1)[1] for s in result["downstream_blocked"]],
            ["C", "K"],
        )
        audit = self.open_ledger().audit_restart()
        self.assertEqual((audit["claims"], audit["records"]), (1, 3))
        self.assertFalse(audit["unresolved_claims_require_manual_review"])
        for stage in ("C", "K"):
            record = self.ledger.load_record(stage_id=sid(stage=stage))
            self.assertEqual(record["status"], "BLOCKED_DEPENDENCY")

    def test_c_invalid_evidence_archives_k_as_blocked(self):
        self.run_stage("D")
        invalid = self.gateway.c_data = {
            **__import__("test_rq2_v2_unified_graph_fake_e2e").synthetic_c(),
            "evidence_ids": ["E999"],
        }
        result = self.run_stage("C")
        self.assertEqual(result["record_status"], "INVALID_OUTPUT")
        self.assertEqual(result["downstream_blocked"], [sid(stage="K")])
        self.assertEqual(self.open_ledger().audit_restart()["records"], 3)

    def test_k_invalid_response_kept_without_repair(self):
        self.run_stage("D")
        self.run_stage("C")
        self.gateway.k_data = {
            **__import__("test_rq2_v2_unified_graph_fake_e2e").synthetic_k(),
            "evidence_ids": ["E999"],
        }
        result = self.run_stage("K")
        self.assertEqual(result["record_status"], "INVALID_OUTPUT")
        self.assertEqual(result["downstream_blocked"], [])
        self.assertEqual(self.open_ledger().audit_restart()["records"], 3)

    def test_provider_error_before_fake_request_has_unknown_cost(self):
        gateway = OfflineLangGraphFakeGateway(
            root=self.data, failure="D",
        )
        result = self.run_stage(gateway=gateway)
        self.assertEqual(result["record_status"], "PROVIDER_ERROR")
        self.assertEqual(len(result["downstream_blocked"]), 2)
        meter = self.ledger.load_record(stage_id=sid())[
            "artifact"
        ]["stage_meter"]
        self.assertEqual(meter["observed_model_requests"], 0)
        self.assertEqual(meter["cost_estimate_usd_not_invoice"], "UNKNOWN")
        self.assertEqual(gateway.calls, {"D": 1, "C": 0, "K": 0})

    def test_c_provider_failure_does_not_execute_k(self):
        self.run_stage("D")
        gateway = OfflineLangGraphFakeGateway(root=self.data, failure="C")
        result = self.run_stage("C", gateway=gateway)
        self.assertEqual(result["record_status"], "PROVIDER_ERROR")
        self.assertEqual(result["downstream_blocked"], [sid(stage="K")])
        self.assertEqual(gateway.calls, {"D": 0, "C": 1, "K": 0})

    def test_k_provider_failure_is_recorded_once(self):
        self.run_stage("D")
        self.run_stage("C")
        gateway = OfflineLangGraphFakeGateway(root=self.data, failure="K")
        result = self.run_stage("K", gateway=gateway)
        self.assertEqual(result["record_status"], "PROVIDER_ERROR")
        self.assertEqual(result["downstream_blocked"], [])
        self.assertEqual(self.ledger.audit_restart()["claims"], 3)

    def test_crash_after_claim_remains_orphan_no_auto_retry(self):
        gateway = OfflineLangGraphFakeGateway(
            root=self.data, failure="D_CRASH",
        )
        with self.assertRaises(KeyboardInterrupt):
            self.run_stage(gateway=gateway)
        self.assertEqual(self.ledger.audit_restart()["orphan_claims"], 1)
        with self.assertRaises(Exception):
            self.run_stage(harness="A1")

    def test_malformed_meter_keeps_orphan_and_never_retries(self):
        class BadMeter(OfflineLangGraphFakeGateway):
            def run_d(self, *, case_id, model, harness):
                answer = super().run_d(
                    case_id=case_id, model=model, harness=harness,
                )
                answer.meter["observed_model_requests"] = -1
                return answer

        with self.assertRaises(UnifiedScientificLedgerBlocked):
            self.run_stage(gateway=BadMeter(root=self.data))
        self.assertEqual(self.ledger.audit_restart()["orphan_claims"], 1)

    def test_missing_fake_marker_blocks_before_claim(self):
        (self.data / MARKER).unlink()
        with self.assertRaises(UnifiedSingleStageBlocked):
            self.run_stage()
        self.assertEqual(self.ledger.audit_restart()["claims"], 0)

    def test_nonfake_gateway_rejected_before_claim(self):
        with self.assertRaises(UnifiedSingleStageBlocked):
            self.run_stage(gateway=object())
        self.assertEqual(self.ledger.audit_restart()["claims"], 0)

    def test_root_outside_temp_policy_blocks_before_claim(self):
        with patch.object(
            dispatcher.tempfile, "gettempdir",
            return_value=str(self.root / "definitely_other_temp"),
        ):
            with self.assertRaisesRegex(
                UnifiedSingleStageBlocked, "temporary",
            ):
                self.run_stage()
        self.assertEqual(self.ledger.audit_restart()["claims"], 0)

    def test_real_market_archive_is_forbidden_even_in_fake_root(self):
        (self.data / "Market.zip").write_bytes(b"fake marker for safety test")
        with self.assertRaises(UnifiedSingleStageBlocked):
            self.run_stage()
        self.assertEqual(self.ledger.audit_restart()["claims"], 0)

    def test_extra_processed_file_is_forbidden(self):
        (self.data / "data/processed/record.csv").write_text("fake")
        with self.assertRaises(UnifiedSingleStageBlocked):
            self.run_stage()
        self.assertEqual(self.ledger.audit_restart()["claims"], 0)

    def test_prompt_package_tamper_rejected_preclaim(self):
        self.run_stage("D")
        real_preview = dispatcher.preview_one_unified_stage(
            data_dir=self.data, repo_dir=self.repo,
            stage_id=sid(stage="C"),
            expected_commit=FAKE_COMMIT,
            approved_release_sha256=self.approved_sha,
        )
        tampered = {**real_preview, "prepared_package_sha256": "0" * 64}
        with patch.object(
            dispatcher, "preview_one_unified_stage",
            return_value=tampered,
        ):
            with self.assertRaisesRegex(
                UnifiedSingleStageBlocked, "binding drift",
            ):
                self.run_stage("C")
        self.assertIsNone(self.ledger.load_claim(stage_id=sid(stage="C")))

    def test_repeated_stage_does_not_retry_and_no_duplicate_record(self):
        self.run_stage()
        with self.assertRaises(Exception):
            self.run_stage()
        self.assertEqual((self.ledger.audit_restart()["claims"],
                          self.ledger.audit_restart()["records"]), (1, 1))

    def test_network_attempt_is_blocked_and_orphan_preserved(self):
        class SneakyGateway(OfflineLangGraphFakeGateway):
            def run_d(self, *, case_id, model, harness):
                socket.create_connection(("example.invalid", 443))
                self.fail("Should not reach network")

        with self.assertRaises(Exception):
            self.run_stage(gateway=SneakyGateway(root=self.data))
        self.assertEqual(self.ledger.audit_restart()["orphan_claims"], 1)

    def test_fake_release_required_even_if_marker_exists(self):
        release_path = self.data / ledger_code.RELEASE_FILE
        release_path.write_bytes(
            release_path.read_bytes().replace(
                b"SYNTHETIC_APPROVAL_NOT_REAL",
                b"APPROVAL_FROM_REAL_PERSON",
                1,
            )
        )
        with self.assertRaises(Exception):
            self.run_stage()
        self.assertEqual(self.ledger.audit_restart()["claims"], 0)

    def test_no_ground_truth_or_api_write_outside_scientific_namespace(self):
        self.run_dck(model="sonnet", harness="A1")
        for relative in (
            "Market.zip", "data/results", "data/rq2",
            "data/rq2_v2_provenance", "data/processed/record.csv",
            "data/processed/query.csv",
        ):
            self.assertFalse((self.data / relative).exists())
        self.assertEqual(self.ledger.audit_restart()["records"], 3)


if __name__ == "__main__":
    unittest.main()
