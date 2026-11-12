"""RQ2 discovery D source/freeze gate -> claim -> unchanged runner adapter.

All tests use synthetic CSVs in a temp directory, fake release ONLY in
unittest via monkeypatch, and replace run_experiment with an in-memory
function. NO genuine provider, Market telemetry, scoring or GT is used.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from unittest.mock import patch

import evaluation.rq2_discovery_d_provider_transport as subject
import evaluation.rq2_ck_provider_transport as ck
import evaluation.rq2_source_bound_d_preflight as preflight
import test_rq2_ck_provider_transport as ck_fixture
from evaluation.rq2_discovery_claim_journal import RQ2ClaimError


class RQ2DiscoveryDActualRunnerAdapterOfflineTests(unittest.TestCase):
    def setUp(self):
        parent = ck_fixture.RQ2ActualCKProviderAdapterOfflineTests(
            methodName="test_confirmation_required_before_source_or_provider"
        )
        parent.setUp()
        self.addCleanup(parent.doCleanups)
        self.p = parent
        self.root = parent.root
        self.sid = parent.parent.sid("D")
        self.market = self.root / "Market.zip"
        self.market.write_bytes(b"SYNTHETIC PLACEHOLDER, NEVER OPEN AS ZIP")
        self.release = json.loads(
            parent.release_path.read_text(encoding="utf-8")
        )
        self.release["enable_discovery_D"] = True
        self._pin()
        self.frozen_identity = {
            "rq1_source_blob_sha1_match": True,
            "rq1_D_output_contract_mode_verified": "v2_enforce",
            "C_system_prompt_sha256": self.release["C_system_prompt_sha256"],
            "K_system_prompt_sha256": self.release["K_system_prompt_sha256"],
        }
        self.patches = (
            patch.object(subject, "preview_protocol_identity",
                         return_value=self.frozen_identity),
            patch.object(preflight, "preview_market",
                         return_value=parent.parent.plan),
            patch.object(preflight, "EXPECTED_SPLIT_SHA256",
                         parent.parent.plan["split_sha256"]),
            patch.object(preflight, "EXPECTED_MANIFEST_SHA256",
                         parent.parent.plan["manifest_sha256"]),
            patch.object(preflight, "DISCOVERY",
                         tuple(parent.parent.plan["partition"]["discovery_case_ids"])),
        )
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def _pin(self):
        self.p.release_path.write_bytes(
            json.dumps(self.release).encode("utf-8")
        )
        digest = hashlib.sha256(
            self.p.release_path.read_bytes()
        ).hexdigest()
        # Original release patch from CK fixture stays underneath this one.
        if hasattr(self, "_repin"):
            self._repin.stop()
        self._repin = patch.object(ck, "RELEASE_SHA256", digest)
        self._repin.start()
        if not hasattr(self, "_cleanup_repin"):
            self.addCleanup(self._repin_cleanup)
            self._cleanup_repin = True

    def _repin_cleanup(self):
        self._repin.stop()

    def synthetic_result(self, **updates):
        run = self.p.parent.diagnostic(
            output_contract_mode="v2_enforce",
            metrics={
                "input_tokens": 141, "output_tokens": 20,
                "total_tokens": 161, "llm_calls": 2,
                "token_usage_complete": True,
            },
        )
        run.update(updates)
        return run

    def run_fake(self, result=None, exc=None):
        if result is None:
            result = self.synthetic_result()
        seen = []
        fake_llm = object()
        def original_runner(config, *, llm, verbose, salva):
            self.assertIs(llm, fake_llm)
            seen.append((config, verbose, salva,
                         self.p.parent.journal._read_claim(self.sid) is not None))
            if exc is not None:
                raise exc
            return result
        with patch.object(subject, "crea_modello_rq2", return_value=fake_llm) as factory:
            with patch.object(subject, "run_experiment",
                              side_effect=original_runner):
                receipt = subject.run_one_claimed_discovery_d(
                    data_dir=self.root, repo_dir=self.root,
                    stage_id=self.sid, confirm_paid_api=True,
                )
            factory.assert_called_once_with("anthropic", "claude-sonnet-5-5")
        return receipt, seen

    def test_live_path_reuses_frozen_RQ1_config_and_writes_one_d_artifact(self):
        receipt, calls = self.run_fake()
        self.assertEqual(len(calls), 1)
        cfg, verbose, salva, was_claimed = calls[0]
        self.assertTrue(was_claimed)
        self.assertFalse(verbose)
        self.assertFalse(salva)
        self.assertEqual(cfg.case_id, "cloudbed-1_q003")
        self.assertEqual(cfg.variant, "A1")
        self.assertEqual(cfg.model_name, "claude-sonnet-5-5")
        self.assertEqual(cfg.model_provider, "anthropic")
        self.assertEqual(cfg.output_contract_mode, "v2_enforce")
        self.assertEqual(cfg.max_tool_rounds, 6)
        self.assertEqual(cfg.recursion_limit, 30)
        self.assertEqual(cfg.variant_scheme, "current")
        self.assertEqual(receipt["status"], "RECORDED_COMPLETE")
        self.assertFalse(receipt["can_execute_test"])
        self.assertFalse(receipt["automatic_retry"])
        self.assertIsNone(receipt["financial_cost_ceiling"])
        self.assertEqual(
            receipt["transport_version"],
            "rq2_discovery_d_provider_transport_v1_rq2_only_factory",
        )
        stored = self.p.parent.recorder.store.load_discovery_stage(
            stage_id=self.sid
        )
        self.assertEqual(stored["artifact"]["diagnostic_run"]["metrics"][
            "total_tokens"], 161)
        self.assertEqual(self.p.parent.journal.audit_restart()["claims"], 1)

    def test_missing_explicit_confirmation_rejected_before_claim_and_runner(self):
        with patch.object(subject, "run_experiment") as runner:
            with self.assertRaisesRegex(subject.RQ2LiveDBlocked,
                                        "confirmation required"):
                subject.run_one_claimed_discovery_d(
                    data_dir=self.root, repo_dir=self.root,
                    stage_id=self.sid,
                )
            runner.assert_not_called()
        self.assertFalse(self.p.parent.journal.root.exists())

    def test_without_scientific_release_never_runs(self):
        with patch.object(ck, "RELEASE_SHA256", None):
            with patch.object(subject, "run_experiment") as runner:
                with self.assertRaises(ck.RQ2LiveCKBlocked):
                    subject.run_one_claimed_discovery_d(
                        data_dir=self.root, repo_dir=self.root,
                        stage_id=self.sid, confirm_paid_api=True,
                    )
                runner.assert_not_called()
        self.assertFalse(self.p.parent.journal.root.exists())

    def test_release_must_enable_D_explicitly(self):
        self.release.pop("enable_discovery_D")
        self._pin()
        with patch.object(subject, "run_experiment") as runner:
            with self.assertRaisesRegex(subject.RQ2LiveDBlocked,
                                        "does not enable D"):
                subject.run_one_claimed_discovery_d(
                    data_dir=self.root, repo_dir=self.root,
                    stage_id=self.sid, confirm_paid_api=True,
                )
            runner.assert_not_called()

    def test_test_stage_rejected_before_any_runner_invoke(self):
        test_sid = self.sid.rsplit(":", 2)[0].replace(
            "cloudbed-1_q003", "cloudbed-1_q000"
        ) + ":A1:D"
        with patch.object(subject, "run_experiment") as runner:
            with self.assertRaisesRegex(subject.RQ2LiveDBlocked,
                                        "Only planned discovery"):
                subject.run_one_claimed_discovery_d(
                    data_dir=self.root, repo_dir=self.root,
                    stage_id=test_sid, confirm_paid_api=True,
                )
            runner.assert_not_called()

    def test_missing_market_is_refused_before_claim(self):
        self.market.unlink()
        with patch.object(subject, "run_experiment") as runner:
            with self.assertRaisesRegex(subject.RQ2LiveDBlocked,
                                        "Market.zip missing"):
                subject.run_one_claimed_discovery_d(
                    data_dir=self.root, repo_dir=self.root,
                    stage_id=self.sid, confirm_paid_api=True,
                )
            runner.assert_not_called()
        self.assertFalse(self.p.parent.journal.root.exists())

    def test_changed_manifest_fails_source_bound_preflight(self):
        self.p.parent.manifest.write_bytes(
            self.p.parent.manifest.read_bytes() + b"\n"
        )
        with patch.object(subject, "run_experiment") as runner:
            with self.assertRaises(Exception):
                subject.run_one_claimed_discovery_d(
                    data_dir=self.root, repo_dir=self.root,
                    stage_id=self.sid, confirm_paid_api=True,
                )
            runner.assert_not_called()
        self.assertFalse(self.p.parent.journal.root.exists())

    def test_rq1_source_identity_drift_blocks_before_claim(self):
        wrong = dict(self.frozen_identity)
        wrong["rq1_source_blob_sha1_match"] = False
        with patch.object(subject, "preview_protocol_identity",
                          return_value=wrong):
            with patch.object(subject, "run_experiment") as runner:
                with self.assertRaisesRegex(subject.RQ2LiveDBlocked,
                                            "source provenance mismatch"):
                    subject.run_one_claimed_discovery_d(
                        data_dir=self.root, repo_dir=self.root,
                        stage_id=self.sid, confirm_paid_api=True,
                    )
                runner.assert_not_called()

    def test_wrong_RQ1_output_mode_leaves_claim_unresolved(self):
        with self.assertRaisesRegex(subject.RQ2LiveDBlocked,
                                    "mismatched provenance"):
            self.run_fake(result=self.synthetic_result(
                output_contract_mode="legacy"
            ))
        audit = self.p.parent.journal.audit_restart()
        self.assertEqual(audit["unresolved_manual_review"], 1)
        self.assertEqual(audit["result_archive_discovery_count"], 0)

    def test_original_runner_exception_is_never_auto_retried(self):
        with self.assertRaisesRegex(RuntimeError, "synthetic crash"):
            self.run_fake(exc=RuntimeError("synthetic crash"))
        audit = self.p.parent.journal.audit_restart()
        self.assertEqual(audit["unresolved_manual_review"], 1)
        self.assertEqual(audit["claims"], 1)
        self.assertEqual(audit["result_archive_discovery_count"], 0)

    def test_completed_D_is_not_rerun(self):
        self.run_fake()
        with patch.object(subject, "run_experiment") as runner:
            with self.assertRaises(subject.RQ2LiveDBlocked):
                subject.run_one_claimed_discovery_d(
                    data_dir=self.root, repo_dir=self.root,
                    stage_id=self.sid, confirm_paid_api=True,
                )
            runner.assert_not_called()

    def test_original_runner_error_recorded_with_tool_evidence_blocked(self):
        receipt, _ = self.run_fake(
            result=self.synthetic_result(
                error="synthetic upstream provider error",
                raw_response=None,
            )
        )
        self.assertEqual(receipt["status"], "PROVIDER_ERROR")
        stored = self.p.parent.recorder.store.load_discovery_stage(
            stage_id=self.sid
        )
        self.assertEqual(stored["status"], "PROVIDER_ERROR")
        self.assertEqual(
            self.p.parent.journal.audit_restart()["unresolved_manual_review"], 0
        )


if __name__ == "__main__":
    unittest.main()
