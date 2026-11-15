"""V3 source/release-gate tests: synthetic filesystem, mocked source/runtime.

These tests do NOT certify the real SDKs, GT-free split, Drive locking or a
scientific release. Only a future real preflight can provide these proofs.
No user data, provider calls, live claims, network or source changes.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.rq2_v2_unified_scientific_ledger import _canonical, _sha
from evaluation.rq2_v2_unified_discovery_plan import (
    EXPECTED_SPLIT_SHA256, EXPECTED_MANIFEST_SHA256,
)
import evaluation.rq2_v3_scientific_source_release_gate as gate
from evaluation.rq2_v3_scientific_source_inventory import (
    V3_SOURCE_PATHS, FUTURE_REQUIRED_PATHS,
    VERSION as INVENTORY_VERSION, STATUS as INVENTORY_STATUS,
)
from evaluation.rq2_v3_unified_gtfree_discovery_plan import (
    VERSION as PROTOCOL, RELEASE_FILE, NAMESPACE,
    build_offline_v3_discovery_plan,
)

PIN = "a" * 40
VERSIONS = {"python": "3.test", "google_genai": "synthetic",
            "anthropic": "synthetic", "langchain_core": "synthetic"}


class V3ScientificSourceReleaseGateOfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="V3_RELEASE_GATE_OFFLINE_")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = self.root / "benchmark"
        self.repo = self.root / "source"
        self.src = self.repo / "src"
        self.data.mkdir()
        self.src.mkdir(parents=True)
        self.plan = build_offline_v3_discovery_plan()
        for name in FUTURE_REQUIRED_PATHS:
            path = self.src / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("# test-only " + name + "\n").encode("utf-8"))
        v2_hashes = {"evaluation/mock_baseline.py": "1" * 64}
        v3_hashes = {name: "2" * 64 for name in V3_SOURCE_PATHS}
        core = {
            "version": INVENTORY_VERSION,
            "status": INVENTORY_STATUS,
            "protocol": PROTOCOL,
            "v3_plan_sha256": self.plan["preview_sha256"],
            "future_required_paths": list(FUTURE_REQUIRED_PATHS),
            "missing_future_paths": [],
            "gt_free_source_verified": True,
            "frozen_rq1_source_identity_verified": True,
            "can_execute_api": False,
            "can_create_claim": False,
            "can_run_ood_test": False,
            "ground_truth_read": False,
            "v2_source_files_sha256": v2_hashes,
            "v3_source_files_sha256": v3_hashes,
            "C_system_prompt_sha256": "3" * 64,
            "K_system_prompt_sha256": "4" * 64,
            "split_sha256": EXPECTED_SPLIT_SHA256,
            "manifest_sha256": EXPECTED_MANIFEST_SHA256,
            "model_ids": self.plan["model_ids"],
            "harnesses": self.plan["harnesses"],
            "discovery_cases": self.plan["discovery_cases"],
            "ood_test_cases_locked": self.plan["ood_test_cases_locked"],
            "stage_counts": self.plan["stage_counts"],
            "logical_stages": 180,
            "text_extraction_policy":
                self.plan["uniform_final_text_extraction_policy_candidate"],
        }
        self.inventory = {
            **core, "candidate_inventory_sha256": _sha(core),
        }
        runtime_core = {
            "status": "V3_SDK_DRIVE_RUNTIME_GATE_VERIFIED",
            "source_commit": PIN,
            "source_inventory_sha256": self.inventory["candidate_inventory_sha256"],
            "runtime_versions": dict(VERSIONS),
            "sdk_retries_disabled_verified": True,
            "per_request_timeout_verified": True,
            "usage_meter_fail_closed": True,
            "single_writer_drive_verified": True,
            "sync_mock_scope": "HTTP_429_ONLY_CK_D_ONE_SEND_EACH",
            "timeout_scope": "SYNC_LOOPBACK_READ_TIMEOUT_0P3S_NOT_FULL_STAGE",
            "drive_scope": "SAME_COLAB_RUNTIME_ONE_SERIAL_WRITER_ONLY",
            "usage_scope": "UNKNOWN_PRESERVED_PER_STAGE_CONSENT_NO_HARD_CAP",
            "transport_observed": {
                "sync_429_http_sends": 4,
                "sync_timeout_loopback_sends": 4,
            },
            "drive_observed": {
                "same_runtime_lock_denied_second_writer": True,
                "same_runtime_exclusive_creators": 1,
                "same_runtime_writer_processes": 8,
                "other_colab_sessions_or_vms_verified": False,
            },
            "usage_observed": {
                "missing_usage_cost_recorded_as": "UNKNOWN",
                "stage_budget_is_hard_cap": False,
                "one_stage_approval_required": True,
            },
            "async_streaming_tested": False,
            "full_stage_timeout_guaranteed": False,
            "usd_hard_cap_guaranteed": False,
            "can_execute_api": False,
            "can_run_ood_test": False,
            "model_requests_sent": 0,
        }
        self.attestation = {
            **runtime_core, "attestation_sha256": _sha(runtime_core)
        }
        self.release = {
            "schema": gate.RELEASE_SCHEMA,
            "protocol": PROTOCOL,
            "phase": "discovery",
            "source_commit": PIN,
            "plan_sha256": self.plan["preview_sha256"],
            "scientific_namespace": NAMESPACE.as_posix(),
            "source_inventory_sha256": self.inventory["candidate_inventory_sha256"],
            "v2_source_files_sha256": v2_hashes,
            "v3_source_files_sha256": v3_hashes,
            "future_source_files_sha256": {
                name: hashlib.sha256(
                    (self.src / name).read_bytes()
                ).hexdigest() for name in FUTURE_REQUIRED_PATHS
            },
            "C_system_prompt_sha256": self.inventory["C_system_prompt_sha256"],
            "K_system_prompt_sha256": self.inventory["K_system_prompt_sha256"],
            "split_sha256": EXPECTED_SPLIT_SHA256,
            "manifest_sha256": EXPECTED_MANIFEST_SHA256,
            "model_ids": self.plan["model_ids"],
            "harnesses": self.plan["harnesses"],
            "discovery_cases": self.plan["discovery_cases"],
            "ood_test_cases_locked": self.plan["ood_test_cases_locked"],
            "stage_counts": self.plan["stage_counts"],
            "logical_stages": 180,
            "text_extraction_policy": self.inventory["text_extraction_policy"],
            "runtime_versions": dict(VERSIONS),
            "runtime_attestation_sha256": self.attestation["attestation_sha256"],
            "single_writer_policy": "ONE_WRITER_LOCK_AND_DRIVE_PROOF",
            "automatic_retry_allowed": False,
            "use_previous_v2_outputs": False,
            "source_protocol_frozen": True,
            "can_run_ood_test": False,
            "can_execute_api": False,
            "api_budget_approved": False,
        }
        self.rewrite_release()
        self.git_patcher = patch.object(
            gate, "_repository_commit", return_value=(PIN, ""),
        )
        self.git_mock = self.git_patcher.start()
        self.addCleanup(self.git_patcher.stop)
        self.inventory_patcher = patch.object(
            gate, "preview_v3_scientific_source_inventory",
            return_value=self.inventory,
        )
        self.inventory_mock = self.inventory_patcher.start()
        self.addCleanup(self.inventory_patcher.stop)
        self.runtime_patcher = patch.object(
            gate, "_runtime_attestation", return_value=self.attestation,
        )
        self.runtime_mock = self.runtime_patcher.start()
        self.addCleanup(self.runtime_patcher.stop)

    def rewrite_release(self):
        path = self.data / RELEASE_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_canonical(self.release))
        self.sha = _sha(self.release)

    def verify(self, *, sha=None):
        return gate.verify_v3_source_release(
            data_dir=self.data, repo_dir=self.repo, release=self.release,
            expected_commit=PIN,
            approved_release_sha256=self.sha if sha is None else sha,
        )

    def test_synthetic_full_proof_still_denies_execution_claim_and_ood(self):
        proof = self.verify()
        self.assertEqual(proof["status"], "V3_SOURCE_BOUND_RELEASE_VERIFIED")
        self.assertEqual(proof["release_sha256"], self.sha)
        self.assertEqual(proof["source_commit"], PIN)
        self.assertIs(proof["can_execute_api"], False)
        self.assertIs(proof["can_create_claim"], False)
        self.assertIs(proof["can_run_ood_test"], False)
        self.assertEqual(proof["model_requests_sent"], 0)
        self.assertEqual(self.inventory_mock.call_count, 1)
        self.assertEqual(self.runtime_mock.call_count, 1)

    def test_external_commit_and_release_digest_required(self):
        with self.assertRaises(gate.V3SourceReleaseBlocked):
            self.verify(sha="0" * 64)
        with self.assertRaises(gate.V3SourceReleaseBlocked):
            gate.verify_v3_source_release(
                data_dir=self.data, repo_dir=self.repo, release=self.release,
                expected_commit="wrong", approved_release_sha256=self.sha,
            )
        self.git_mock.return_value = ("b" * 40, "")
        with self.assertRaises(gate.V3SourceReleaseBlocked):
            self.verify()

    def test_dirty_git_checkout_always_blocks(self):
        self.git_mock.return_value = (PIN, " M src/evaluation/foo.py")
        with self.assertRaises(gate.V3SourceReleaseBlocked):
            self.verify()

    def test_missing_noncanonical_or_mismatched_on_disk_release_blocks(self):
        path = self.data / RELEASE_FILE
        path.unlink()
        with self.assertRaises(gate.V3SourceReleaseBlocked):
            self.verify()
        path.write_bytes(_canonical(self.release) + b"\n")
        with self.assertRaises(gate.V3SourceReleaseBlocked):
            self.verify()
        self.rewrite_release()
        bad = copy.deepcopy(self.release)
        bad["single_writer_policy"] = "BAD"
        with self.assertRaises(gate.V3SourceReleaseBlocked):
            gate.verify_v3_source_release(
                data_dir=self.data, repo_dir=self.repo, release=bad,
                expected_commit=PIN, approved_release_sha256=_sha(bad),
            )

    def test_rehashed_release_cannot_unlock_ood_api_or_retry(self):
        for key, value in (
            ("can_execute_api", True),
            ("can_run_ood_test", True),
            ("api_budget_approved", True),
            ("automatic_retry_allowed", True),
            ("use_previous_v2_outputs", True),
            ("source_protocol_frozen", False),
            ("ood_test_cases_locked", ["unlocked"]),
            ("stage_counts", {"D": 1, "C": 1, "K": 1}),
        ):
            with self.subTest(key=key):
                original = self.release[key]
                self.release[key] = value
                self.rewrite_release()
                with self.assertRaises(gate.V3SourceReleaseBlocked):
                    self.verify()
                self.release[key] = original
        self.rewrite_release()

    def test_release_inventory_file_hash_and_prompt_parity_enforced(self):
        for key, bad in (
            ("C_system_prompt_sha256", "e" * 64),
            ("K_system_prompt_sha256", "e" * 64),
            ("model_ids", {"gemini": "wrong"}),
            ("v3_source_files_sha256", {"fake.py": "f" * 64}),
            ("source_inventory_sha256", "e" * 64),
        ):
            with self.subTest(key=key):
                original = self.release[key]
                self.release[key] = bad
                self.rewrite_release()
                with self.assertRaises(gate.V3SourceReleaseBlocked):
                    self.verify()
                self.release[key] = original
        self.rewrite_release()

    def test_missing_future_runtime_dispatcher_modules_blocks(self):
        target = self.src / FUTURE_REQUIRED_PATHS[-1]
        target.unlink()
        with self.assertRaises(gate.V3SourceReleaseBlocked):
            self.verify()

    def test_future_module_tamper_blocks_even_if_inventory_not_recomputed(self):
        target = self.src / FUTURE_REQUIRED_PATHS[0]
        target.write_bytes(target.read_bytes() + b"# changed after freeze\n")
        with self.assertRaises(gate.V3SourceReleaseBlocked):
            self.verify()

    def test_incomplete_or_tampered_inventory_is_no_go(self):
        for key, bad in (
            ("missing_future_paths", ["pending.py"]),
            ("ground_truth_read", True),
            ("can_execute_api", True),
            ("gt_free_source_verified", False),
            ("candidate_inventory_sha256", "0" * 64),
        ):
            with self.subTest(key=key):
                snapshot = copy.deepcopy(self.inventory)
                snapshot[key] = bad
                self.inventory_mock.return_value = snapshot
                with self.assertRaises(gate.V3SourceReleaseBlocked):
                    self.verify()
        self.inventory_mock.return_value = self.inventory

    def test_runtime_attestation_must_be_bound_to_inventory_not_release(self):
        self.assertNotIn("release_sha256", self.attestation)
        self.assertEqual(self.attestation["source_inventory_sha256"],
                         self.release["source_inventory_sha256"])
        for key, bad in (
            ("sdk_retries_disabled_verified", False),
            ("single_writer_drive_verified", False),
            ("source_inventory_sha256", "0" * 64),
            ("attestation_sha256", "0" * 64),
        ):
            with self.subTest(key=key):
                mutated = {**self.attestation, key: bad}
                self.runtime_mock.return_value = mutated
                with self.assertRaises(gate.V3SourceReleaseBlocked):
                    self.verify()
        self.runtime_mock.return_value = self.attestation

    def test_rehashed_overclaims_cannot_become_release_proofs(self):
        baseline_receipt = copy.deepcopy(self.attestation)
        baseline_release = copy.deepcopy(self.release)
        for key, value in (
            ("async_streaming_tested", True),
            ("full_stage_timeout_guaranteed", True),
            ("usd_hard_cap_guaranteed", True),
            ("sync_mock_scope", "ALL_HTTP_STATUSES_PROVEN"),
            ("drive_scope", "ALL_COLAB_VMS_VERIFIED"),
            ("usage_scope", "USD_COST_HARD_CAPPED"),
        ):
            with self.subTest(key=key):
                modified = copy.deepcopy(baseline_receipt)
                modified[key] = value
                modified["attestation_sha256"] = _sha({
                    k: v for k, v in modified.items()
                    if k != "attestation_sha256"
                })
                self.runtime_mock.return_value = modified
                self.release["runtime_attestation_sha256"] = (
                    modified["attestation_sha256"]
                )
                self.rewrite_release()
                with self.assertRaises(gate.V3SourceReleaseBlocked):
                    self.verify()
        self.attestation = baseline_receipt
        self.release = baseline_release
        self.runtime_mock.return_value = self.attestation
        self.rewrite_release()

    def test_runtime_verifier_absence_and_errors_never_fall_back(self):
        self.runtime_mock.side_effect = gate.V3SourceReleaseBlocked(
            "Synthetic SDK and Drive proof absent"
        )
        with self.assertRaises(gate.V3SourceReleaseBlocked):
            self.verify()
        self.runtime_mock.side_effect = None
        self.runtime_patcher.stop()
        with self.assertRaises(gate.V3SourceReleaseBlocked):
            self.verify()

    def test_nonexistent_source_inventory_and_bad_root_block(self):
        self.inventory_mock.side_effect = (
            gate.V3SourceInventoryBlocked("Synthetic GT-free source error")
        )
        with self.assertRaises(gate.V3SourceReleaseBlocked):
            self.verify()
        self.inventory_mock.side_effect = None
        with self.assertRaises(gate.V3SourceReleaseBlocked):
            gate.verify_v3_source_release(
                data_dir=Path("relative"), repo_dir=self.repo,
                release=self.release, expected_commit=PIN,
                approved_release_sha256=self.sha,
            )


if __name__ == "__main__":
    unittest.main()
