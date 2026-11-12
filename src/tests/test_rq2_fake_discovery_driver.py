"""SYNTHETIC ONLY: fake coordinator invokes no provider or real Market.

The source-verification monkeypatches belong to the already-tested fixture
class from test_rq2_claim_recorder_end_to_end; imported as a MODULE to avoid
accidentally collecting its TestCase again.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import test_rq2_claim_recorder_end_to_end as fixtures
import test_rq2_output_contracts as contract_fixtures
import test_rq2_stage_binding as binding_fixtures
import evaluation.rq2_fake_discovery_driver as driver
import evaluation.rq2_discovery_claim_journal as claims


class RQ2FakeDriverTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RQ2ClaimRecorderEndToEndTests(
            methodName="test_three_claims_three_artifacts_and_restart",
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        (self.fixture.root / driver.FIXTURE_MARKER).write_bytes(
            driver.FIXTURE_MARKER_BYTES
        )
        self.replies = {
            self.fixture.sid("D"): {
                "diagnostic_run": self.fixture.diagnostic(),
            },
            self.fixture.sid("C"): {
                "raw_response": binding_fixtures.cause(),
                "provider_error": None,
            },
            self.fixture.sid("K"): {
                "raw_response": json.dumps(
                    contract_fixtures.RQ2OutputContractsTests.rule()
                ),
                "provider_error": None,
            },
        }

    def make(self, replies=None):
        backend = driver.DeterministicFakeBackend(
            replies=self.replies if replies is None else replies,
        )
        return driver.RQ2FakeDiscoveryDriver(
            data_dir=self.fixture.root, backend=backend,
        ), backend

    def run_all(self, d):
        return d.run_discovery_triplet(
            case_id=fixtures.CID, logical_model="sonnet", harness="A1",
        )

    def test_complete_three_stage_fake_rehearsal(self):
        fake, backend = self.make()
        summary = self.run_all(fake)
        self.assertEqual(summary["status"], "SYNTHETIC_REHEARSAL_ONLY")
        self.assertEqual(summary["model_api_calls"], 0)
        self.assertFalse(summary["can_execute_api"])
        self.assertFalse(summary["can_execute_test"])
        self.assertFalse(summary["scientific_results_produced"])
        self.assertEqual(len(backend.requested), 3)
        self.assertEqual(
            [stage["record_status"] for stage in summary["stages"]],
            ["RECORDED_COMPLETE"] * 3,
        )
        audit = summary["restart_audit"]
        self.assertEqual(audit["claims"], 3)
        self.assertEqual(audit["finished_with_matching_result"], 3)
        self.assertEqual(audit["unresolved_manual_review"], 0)

    def test_restart_cannot_replay_finished_d(self):
        fake, backend = self.make()
        self.run_all(fake)
        restarted, new_backend = self.make()
        with self.assertRaisesRegex(claims.RQ2ClaimError, "NEVER auto retry"):
            self.run_all(restarted)
        self.assertEqual(new_backend.requested, [])
        self.assertEqual(len(backend.requested), 3)

    def test_provider_error_d_blocks_c_k_without_more_fake_calls(self):
        reply = dict(self.replies)
        failed_d = self.fixture.diagnostic(error="synthetic 503")
        reply[self.fixture.sid("D")] = {"diagnostic_run": failed_d}
        fake, backend = self.make(reply)
        summary = self.run_all(fake)
        self.assertEqual(backend.requested, [self.fixture.sid("D")])
        self.assertEqual(
            [stage["record_status"] for stage in summary["stages"]],
            ["PROVIDER_ERROR", "BLOCKED_DEPENDENCY", "BLOCKED_DEPENDENCY"],
        )
        self.assertEqual(
            [stage["fake_model_invoked"] for stage in summary["stages"]],
            [True, False, False],
        )
        self.assertEqual(summary["restart_audit"]["claims"], 1)

    def test_c_invalid_json_preserved_k_blocked(self):
        reply = dict(self.replies)
        reply[self.fixture.sid("C")] = {
            "raw_response": "INVALID SYNTHETIC C JSON",
            "provider_error": None,
        }
        fake, backend = self.make(reply)
        summary = self.run_all(fake)
        self.assertEqual(len(backend.requested), 2)
        self.assertEqual(
            [item["record_status"] for item in summary["stages"]],
            ["RECORDED_COMPLETE", "INVALID_OUTPUT", "BLOCKED_DEPENDENCY"],
        )
        recorded_c = fake.recorder.store.load_discovery_stage(
            stage_id=self.fixture.sid("C"),
        )
        self.assertEqual(
            recorded_c["artifact"]["raw_response"],
            "INVALID SYNTHETIC C JSON",
        )

    def test_c_provider_error_preserved_k_blocked(self):
        reply = dict(self.replies)
        reply[self.fixture.sid("C")] = {
            "raw_response": None, "provider_error": "synthetic timeout",
        }
        fake, backend = self.make(reply)
        summary = self.run_all(fake)
        self.assertEqual(len(backend.requested), 2)
        self.assertEqual(summary["stages"][1]["record_status"], "PROVIDER_ERROR")
        self.assertEqual(summary["stages"][2]["record_status"], "BLOCKED_DEPENDENCY")
        self.assertEqual(summary["restart_audit"]["claims"], 2)

    def test_abstention_k_is_successful_valid_model_output(self):
        reply = dict(self.replies)
        k = contract_fixtures.RQ2OutputContractsTests.rule()
        k.update({
            "status": "insufficient_evidence",
            "rule_name": None,
            "hypothesized_fault_type": None,
            "combination": None,
            "pseudocode": None,
            "required_signals": [],
            "conditions": [],
        })
        reply[self.fixture.sid("K")] = {
            "raw_response": json.dumps(k), "provider_error": None,
        }
        fake, backend = self.make(reply)
        summary = self.run_all(fake)
        self.assertEqual(len(backend.requested), 3)
        self.assertEqual(summary["stages"][2]["record_status"], "RECORDED_COMPLETE")
        k_record = fake.recorder.store.load_discovery_stage(
            stage_id=self.fixture.sid("K"),
        )
        self.assertEqual(
            k_record["artifact"]["preflight_status"],
            "insufficient_evidence",
        )

    def test_crash_after_claim_before_reply_requires_manual_review(self):
        replies = dict(self.replies)
        del replies[self.fixture.sid("D")]
        fake, backend = self.make(replies)
        with self.assertRaisesRegex(driver.FakeDriverError, "manual review"):
            self.run_all(fake)
        self.assertEqual(backend.requested, [])
        audit = fake.journal.audit_restart()
        self.assertEqual(audit["claims"], 1)
        self.assertEqual(audit["unresolved_manual_review"], 1)
        with self.assertRaises(claims.RQ2ClaimError):
            self.run_all(fake)

    def test_orphaned_claim_blocks_new_fake_backend_after_restart(self):
        fake, _ = self.make()
        fake.journal.claim_stage(
            stage_id=self.fixture.sid("D"), model_id_proposed=fixtures.MODEL,
        )
        new, backend = self.make()
        with self.assertRaises(claims.RQ2ClaimError):
            self.run_all(new)
        self.assertEqual(backend.requested, [])

    def test_no_marker_means_no_driver_or_artifacts(self):
        (self.fixture.root / driver.FIXTURE_MARKER).unlink()
        with self.assertRaisesRegex(driver.FakeDriverError, "marker"):
            self.make()
        self.assertFalse(self.fixture.recorder.store.root.exists())

    def test_real_market_archive_presence_rejected_even_with_marker(self):
        (self.fixture.root / "Market.zip").write_bytes(b"fake")
        with self.assertRaisesRegex(driver.FakeDriverError, "Market.zip"):
            self.make()
        self.assertFalse(self.fixture.recorder.store.root.exists())

    def test_cannot_inject_arbitrary_backend_that_might_call_api(self):
        class DangerousProvider:
            def invoke(self, x):
                raise AssertionError("SHOULD NOT INSTANTIATE OR CALL")

        with self.assertRaisesRegex(driver.FakeDriverError, "deterministic"):
            driver.RQ2FakeDiscoveryDriver(
                data_dir=self.fixture.root, backend=DangerousProvider(),
            )
        self.assertFalse(self.fixture.recorder.store.root.exists())

    def test_test_phase_refused_before_fake_backend_use(self):
        fake, backend = self.make()
        sid = (
            "rq2_dryrun_workflow_preview_v0:"
            "cloudbed-1_q000:sonnet:A1:D"
        )
        with self.assertRaisesRegex(claims.RQ2ClaimError, "TEST stage"):
            fake.run_one(stage_id=sid)
        self.assertEqual(backend.requested, [])

    def test_k_cannot_be_run_before_d_c_claims_and_results(self):
        fake, backend = self.make()
        with self.assertRaisesRegex(driver.FakeDriverError, "Parent not recorded"):
            fake.run_one(stage_id=self.fixture.sid("K"))
        self.assertEqual(backend.requested, [])
        self.assertFalse(fake.journal.root.exists())

    def test_invalid_fake_reply_schema_retains_claim_for_review(self):
        reply = dict(self.replies)
        reply[self.fixture.sid("D")] = {"unexpected": "not a D"}
        fake, backend = self.make(reply)
        with self.assertRaisesRegex(driver.FakeDriverError, "schema"):
            fake.run_one(stage_id=self.fixture.sid("D"))
        self.assertEqual(backend.requested, [])
        self.assertEqual(fake.journal.audit_restart()["unresolved_manual_review"], 1)

    def test_original_d_invalid_json_c_still_from_tool_observations(self):
        reply = dict(self.replies)
        reply[self.fixture.sid("D")] = {
            "diagnostic_run": self.fixture.diagnostic(
                json_status="invalid_json: synthetic",
                raw_response="SYNTHETIC INVALID ORIGINAL D",
            )
        }
        fake, backend = self.make(reply)
        summary = self.run_all(fake)
        self.assertEqual(len(backend.requested), 3)
        self.assertEqual(summary["stages"][1]["record_status"], "RECORDED_COMPLETE")
        c_record = fake.recorder.store.load_discovery_stage(
            stage_id=self.fixture.sid("C")
        )
        self.assertNotIn(
            "SYNTHETIC INVALID ORIGINAL D", json.dumps(c_record["artifact"]),
        )

    def test_no_backend_connection_or_cost_cap_in_fake_driver(self):
        fake, backend = self.make()
        self.assertFalse(hasattr(fake, "run_experiment"))
        self.assertFalse(hasattr(fake, "llm"))
        self.assertFalse(hasattr(backend, "invoke"))
        self.assertFalse(hasattr(backend, "send_request"))
        summary = self.run_all(fake)
        self.assertIsNone(summary["financial_cost_cap"])
        self.assertEqual(summary["model_api_calls"], 0)


if __name__ == "__main__":
    unittest.main()
