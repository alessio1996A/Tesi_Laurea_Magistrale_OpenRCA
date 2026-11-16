"""Test offline gate scientifico V4: nessun Colab, API, release o dataset reale.

I casi positivi usano solo mock di source/runtime e JSON sintetici su
TemporaryDirectory. Una release reale richiederà i byte GT-free e i
probe SDK/Drive; questo test NON li certifica.
"""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.rq2_v2_unified_scientific_ledger import _sha
from evaluation.rq2_provider_policy_source_audit import EXPECTED_COLAB_VERSIONS
import evaluation.rq2_v4_scientific_source_release_gate as gate
from evaluation.rq2_v4_scientific_source_inventory import (
    VERSION as INV_VERSION, STATUS as INV_STATUS,
    V4_SOURCE_PATHS, FUTURE_REQUIRED_PATHS,
)
from evaluation.rq2_v4_unified_gtfree_discovery_plan import (
    VERSION as PROTOCOL, NAMESPACE, build_offline_v4_discovery_plan,
)
from evaluation.rq2_v4_d_task_aware_contract import VERSION as D_CONTRACT

COMMIT = "a" * 40
FUTURE_BYTES = b"SYNTHETIC FUTURE DISPATCHER NO API"
FUTURE_SHA = hashlib.sha256(FUTURE_BYTES).hexdigest()


def fake_runtime(*, commit, inv_sha, versions):
    core = {
        "status": "V3_SDK_DRIVE_RUNTIME_GATE_VERIFIED",
        "source_commit": commit,
        "source_inventory_sha256": inv_sha,
        "runtime_versions": versions,
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
    return {**core, "attestation_sha256": _sha(core)}


def fixtures():
    p = build_offline_v4_discovery_plan()
    versions = {"python": "3.13.18", **EXPECTED_COLAB_VERSIONS}
    inventory = {
        "version": INV_VERSION,
        "status": INV_STATUS,
        "protocol": PROTOCOL,
        "plan_sha256": p["preview_sha256"],
        "future_required_paths": list(FUTURE_REQUIRED_PATHS),
        "missing_future_paths": [],
        "gt_free_source_verified": True,
        "frozen_rq1_source_identity_verified": True,
        "can_execute_api": False,
        "can_create_claim": False,
        "can_run_ood_test": False,
        "ground_truth_read": False,
        "v2_source_files_sha256": {"synthetic_v2.py": "1" * 64},
        "v3_source_files_sha256": {"synthetic_v3.py": "2" * 64},
        "v3_future_source_files_sha256": {"synthetic_v3_runtime.py": "3" * 64},
        "v4_source_files_sha256": {name: "4" * 64 for name in V4_SOURCE_PATHS},
        "C_system_prompt_sha256": "5" * 64,
        "K_system_prompt_sha256": "6" * 64,
        "split_sha256": "7" * 64,
        "manifest_sha256": "8" * 64,
        "model_ids": p["model_ids"],
        "harnesses": p["harnesses"],
        "discovery_cases": p["discovery_cases"],
        "ood_test_cases_locked": p["ood_test_cases_locked"],
        "stage_counts": p["stage_counts"],
        "logical_stages": 180,
        "text_extraction_policy": "SYNTHETIC_POLICY",
        "v4_task_aware_contract": D_CONTRACT,
    }
    inventory["candidate_inventory_sha256"] = _sha(inventory)
    runtime = fake_runtime(
        commit=COMMIT, inv_sha=inventory["candidate_inventory_sha256"],
        versions=versions,
    )
    release = {
        "schema": gate.RELEASE_SCHEMA,
        "protocol": PROTOCOL,
        "phase": "discovery",
        "source_commit": COMMIT,
        "plan_sha256": p["preview_sha256"],
        "scientific_namespace": NAMESPACE.as_posix(),
        "source_inventory_sha256": inventory["candidate_inventory_sha256"],
        "future_source_files_sha256": {
            name: FUTURE_SHA for name in FUTURE_REQUIRED_PATHS
        },
        "runtime_versions": versions,
        "runtime_attestation_sha256": runtime["attestation_sha256"],
        "single_writer_policy": "ONE_WRITER_LOCK_AND_DRIVE_PROOF",
        "automatic_retry_allowed": False,
        "use_previous_v2_outputs": False,
        "use_previous_v3_outputs": False,
        "source_protocol_frozen": True,
        "can_run_ood_test": False,
        "can_execute_api": False,
        "api_budget_approved": False,
        **{
            key: inventory[key]
            for key in (
                "v2_source_files_sha256", "v3_source_files_sha256",
                "v3_future_source_files_sha256", "v4_source_files_sha256",
                "C_system_prompt_sha256", "K_system_prompt_sha256",
                "split_sha256", "manifest_sha256", "model_ids",
                "harnesses", "discovery_cases", "ood_test_cases_locked",
                "stage_counts", "logical_stages",
                "text_extraction_policy", "v4_task_aware_contract",
            )
        },
    }
    assert set(release) == gate.REQUIRED_RELEASE_KEYS
    return release, inventory, runtime


class V4ReleaseGateOfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name) / "data"
        self.repo = Path(self.tmp.name) / "repo"
        self.data.mkdir()
        self.repo.mkdir()
        self.release, self.inventory, self.runtime = fixtures()
        self.release_sha = _sha(self.release)
        patches = [
            patch.object(gate, "_repository_commit", return_value=(COMMIT, "")),
            patch.object(gate, "_read", return_value=self.release),
            patch.object(gate, "preview_v4_scientific_source_inventory",
                         return_value=self.inventory),
            patch.object(gate, "_source_bytes", return_value=FUTURE_BYTES),
            patch.object(gate, "_runtime_proof", return_value=self.runtime),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def verify(self, *, release=None, commit=COMMIT, release_sha=None):
        return gate.verify_v4_source_release(
            data_dir=self.data, repo_dir=self.repo,
            release=self.release if release is None else release,
            expected_commit=commit,
            approved_release_sha256=(
                self.release_sha if release_sha is None else release_sha
            ),
        )

    def test_synthetic_full_source_release_proof(self):
        result = self.verify()
        self.assertEqual(result["status"], "V4_SOURCE_BOUND_RELEASE_VERIFIED")
        self.assertFalse(result["can_execute_api"])
        self.assertFalse(result["can_create_claim"])
        self.assertFalse(result["can_run_ood_test"])

    def test_missing_release_file_fails_closed(self):
        with patch.object(gate, "_read", return_value=None):
            with self.assertRaises(gate.V4SourceReleaseBlocked):
                self.verify()

    def test_dirty_or_wrong_commit_fails_closed(self):
        for head, dirty in ((COMMIT, "M src/f.py"), ("b" * 40, "")):
            with self.subTest(head=head, dirty=dirty):
                with patch.object(
                    gate, "_repository_commit", return_value=(head, dirty),
                ):
                    with self.assertRaises(gate.V4SourceReleaseBlocked):
                        self.verify()

    def test_source_release_sha_and_schema_fails_closed(self):
        for bad in ("f" * 64, "not-a-sha"):
            with self.subTest(bad=bad):
                with self.assertRaises(gate.V4SourceReleaseBlocked):
                    self.verify(release_sha=bad)
        changed = dict(self.release)
        changed["foreign_field"] = True
        with self.assertRaises(gate.V4SourceReleaseBlocked):
            self.verify(release=changed)

    def test_ood_and_historical_reuse_flags_fail_closed(self):
        for key, value in (
            ("can_run_ood_test", True),
            ("use_previous_v3_outputs", True),
            ("api_budget_approved", True),
            ("use_previous_v2_outputs", True),
        ):
            with self.subTest(key=key):
                changed = dict(self.release)
                changed[key] = value
                with patch.object(gate, "_read", return_value=changed):
                    with self.assertRaises(gate.V4SourceReleaseBlocked):
                        self.verify(release=changed, release_sha=_sha(changed))

    def test_inventory_hash_mismatch_fails_closed(self):
        changed = dict(self.inventory)
        changed["candidate_inventory_sha256"] = "c" * 64
        with patch.object(
            gate, "preview_v4_scientific_source_inventory", return_value=changed,
        ):
            with self.assertRaises(gate.V4SourceReleaseBlocked):
                self.verify()

    def test_missing_future_dispatcher_is_not_accepted(self):
        changed = dict(self.inventory)
        changed["missing_future_paths"] = list(FUTURE_REQUIRED_PATHS)
        changed["candidate_inventory_sha256"] = _sha({
            k: v for k, v in changed.items()
            if k != "candidate_inventory_sha256"
        })
        with patch.object(
            gate, "preview_v4_scientific_source_inventory", return_value=changed,
        ):
            with self.assertRaises(gate.V4SourceReleaseBlocked):
                self.verify()

    def test_future_source_file_must_match_approved_sha(self):
        with patch.object(gate, "_source_bytes", return_value=b"CHANGED"):
            with self.assertRaises(gate.V4SourceReleaseBlocked):
                self.verify()

    def test_runtime_version_and_attestation_must_match(self):
        changed = dict(self.runtime)
        changed["sdk_retries_disabled_verified"] = False
        with patch.object(gate, "_runtime_proof", return_value=changed):
            with self.assertRaises(gate.V4SourceReleaseBlocked):
                self.verify()

    def test_runtime_limits_cannot_be_falsely_strengthened(self):
        changed = dict(self.runtime)
        changed["usd_hard_cap_guaranteed"] = True
        with patch.object(gate, "_runtime_proof", return_value=changed):
            with self.assertRaises(gate.V4SourceReleaseBlocked):
                self.verify()


if __name__ == "__main__":
    unittest.main()
