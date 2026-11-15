"""Isolated V3 runtime-preview tests: no SDK, network, GT or release.

Synthetic provider metadata is injected: these do NOT prove real HTTP
retries, timeouts, Colab dependencies or Google Drive writer locks.
"""
from __future__ import annotations

import copy
from pathlib import Path
import platform
import tempfile
import unittest
from unittest.mock import patch

import evaluation.rq2_v3_scientific_live_stage_preflight as runtime


PIN = "a" * 40
INVENTORY = "b" * 64


class V3LiveRuntimePreviewOfflineTests(unittest.TestCase):
    def setUp(self):
        runtime._RUNTIME_PROOF_CACHE.clear()
        self.addCleanup(runtime._RUNTIME_PROOF_CACHE.clear)
        tmp = tempfile.TemporaryDirectory(prefix="V3_RUNTIME_PREVIEW_ONLY_")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.data = self.root / "data"
        self.repo = self.root / "repo"
        self.data.mkdir()
        self.repo.mkdir()
        self.versions = {
            "python": platform.python_version(),
            **runtime.EXPECTED_COLAB_VERSIONS,
        }
        self.report = {
            "can_execute_D": False,
            "can_execute_CK": False,
            "can_execute_test": False,
            "files_written": False,
            "api_calls_executed": 0,
            "read_ground_truth": False,
            "read_market": False,
            "read_predictions": False,
            "matches_previous_colab_versions": True,
            "original_factory_unchanged": True,
            "factory": {"frozen_rq1_factory_blob_match": True},
            "packages": {
                name: {
                    "version": version,
                    "known_source_sha256":
                        runtime.EXPECTED_SOURCE_DIGESTS.get(name),
                } for name, version
                in runtime.EXPECTED_COLAB_VERSIONS.items()
            },
        }
        gp = patch.object(
            runtime, "_repository_commit", return_value=(PIN, ""),
        )
        self.git = gp.start()
        self.addCleanup(gp.stop)
        pp = patch.object(
            runtime, "preview_provider_policy", return_value=self.report,
        )
        self.policy = pp.start()
        self.addCleanup(pp.stop)

    def preview(self, *, pin=PIN, inventory=INVENTORY, versions=None):
        return runtime.preview_v3_live_runtime(
            data_dir=self.data, repo_dir=self.repo,
            expected_source_commit=pin,
            expected_source_inventory_sha256=inventory,
            expected_runtime_versions=(
                self.versions if versions is None else versions
            ),
        )

    def verify(self):
        return runtime.verify_v3_live_runtime_gate(
            data_dir=self.data, repo_dir=self.repo,
            expected_source_commit=PIN,
            expected_source_inventory_sha256=INVENTORY,
            expected_runtime_versions=self.versions,
        )

    def test_exact_synthetic_source_preview_still_denies_all_live_actions(self):
        result = self.preview()
        self.assertEqual(result["status"], runtime.PREVIEW_STATUS)
        self.assertTrue(result["packages_exact"])
        self.assertTrue(result["sdk_and_rq1_source_exact"])
        self.assertTrue(result["rq2_declared_policy_exact"])
        self.assertEqual(result["source_commit"], PIN)
        self.assertEqual(result["source_inventory_sha256"], INVENTORY)
        for field in ("sdk_retries_disabled_verified",
                      "per_request_timeout_verified", "usage_meter_fail_closed",
                      "single_writer_drive_verified", "can_execute_api",
                      "can_create_claim", "can_run_ood_test",
                      "read_ground_truth", "files_written"):
            self.assertIs(result[field], False)
        self.assertEqual(result["real_provider_requests"], 0)
        self.assertIsNone(result["attestation_sha256"])

    def test_runtime_probe_absence_fails_closed_without_sdk_or_drive(self):
        with patch.object(
            runtime, "_check_sync_sdk_proofs",
            side_effect=runtime.V3LiveRuntimeBlocked("NO_SYNTHETIC_SDK_EVIDENCE"),
        ):
            with patch.object(runtime, "_check_same_runtime_drive_scratch") as drive:
                with self.assertRaisesRegex(
                    runtime.V3LiveRuntimeBlocked, "NO_SYNTHETIC_SDK_EVIDENCE",
                ):
                    self.verify()
                drive.assert_not_called()

    def test_only_scoped_measured_proofs_can_mint_non_authorizing_receipt(self):
        sync = {"sync_429_http_sends": 4, "sync_timeout_loopback_sends": 4}
        drive = {
            "same_runtime_lock_denied_second_writer": True,
            "same_runtime_exclusive_creators": 1,
            "same_runtime_writer_processes": 8,
            "other_colab_sessions_or_vms_verified": False,
        }
        with (
            patch.object(runtime, "_check_sync_sdk_proofs", return_value=sync) as sdk,
            patch.object(runtime, "_check_same_runtime_drive_scratch", return_value=drive) as scratch,
        ):
            result = self.verify()
            second = self.verify()
            self.assertEqual(result, second)
            sdk.assert_called_once()
            scratch.assert_called_once()
        from evaluation.rq2_v2_unified_scientific_ledger import _sha
        self.assertEqual(result["status"], "V3_SDK_DRIVE_RUNTIME_GATE_VERIFIED")
        self.assertEqual(result["source_commit"], PIN)
        self.assertEqual(result["attestation_sha256"], _sha({
            k: v for k, v in result.items() if k != "attestation_sha256"
        }))
        self.assertEqual(result["sync_mock_scope"], "HTTP_429_ONLY_CK_D_ONE_SEND_EACH")
        self.assertEqual(result["drive_scope"], "SAME_COLAB_RUNTIME_ONE_SERIAL_WRITER_ONLY")
        self.assertIs(result["async_streaming_tested"], False)
        self.assertIs(result["full_stage_timeout_guaranteed"], False)
        self.assertIs(result["usd_hard_cap_guaranteed"], False)
        self.assertIs(result["can_execute_api"], False)
        self.assertIs(result["can_run_ood_test"], False)
        self.assertEqual(result["model_requests_sent"], 0)

    def test_bad_commit_inventory_runtime_shape_block_before_provider_audit(self):
        for pin, inventory, versions in (
            ("wrong", INVENTORY, self.versions),
            (PIN, "wrong", self.versions),
            (PIN, INVENTORY, {"python": platform.python_version()}),
            (PIN, INVENTORY, {**self.versions, "unknown": "1.0"}),
        ):
            with self.subTest(pin=pin, inventory=inventory):
                with self.assertRaises(runtime.V3LiveRuntimeBlocked):
                    self.preview(pin=pin, inventory=inventory, versions=versions)
        self.policy.assert_not_called()

    def test_dirty_checkout_and_different_head_block(self):
        for result in ((PIN, " M src/modified.py"), ("c" * 40, "")):
            with self.subTest(result=result):
                self.git.return_value = result
                with self.assertRaises(runtime.V3LiveRuntimeBlocked):
                    self.preview()
        self.policy.assert_not_called()

    def test_runtime_version_mismatch_is_reported_not_certified(self):
        snapshot = copy.deepcopy(self.report)
        snapshot["packages"]["anthropic"]["version"] = "wrong"
        snapshot["matches_previous_colab_versions"] = False
        self.policy.return_value = snapshot
        result = self.preview()
        self.assertFalse(result["packages_exact"])
        self.assertIn("PINNED_RUNTIME_VERSION_MISMATCH", result["blockers"])
        self.assertFalse(result["can_execute_api"])

    def test_sdk_source_hash_drift_is_reported_not_accepted(self):
        snapshot = copy.deepcopy(self.report)
        snapshot["packages"]["google-genai"]["known_source_sha256"] = "0" * 64
        self.policy.return_value = snapshot
        result = self.preview()
        self.assertFalse(result["sdk_and_rq1_source_exact"])
        self.assertIn("SDK_OR_FROZEN_RQ1_SOURCE_MISMATCH", result["blockers"])

    def test_original_rq1_factory_drift_is_reported(self):
        snapshot = copy.deepcopy(self.report)
        snapshot["original_factory_unchanged"] = False
        snapshot["factory"]["frozen_rq1_factory_blob_match"] = False
        self.policy.return_value = snapshot
        result = self.preview()
        self.assertFalse(result["sdk_and_rq1_source_exact"])
        self.assertFalse(result["can_run_ood_test"])

    def test_rq2_declared_policy_drift_is_reported_without_sdk(self):
        with patch.object(runtime, "GOOGLE_HTTP_ATTEMPTS", 2):
            result = self.preview()
        self.assertFalse(result["rq2_declared_policy_exact"])
        self.assertIn("RQ2_FACTORY_DECLARED_POLICY_MISMATCH", result["blockers"])
        self.assertFalse(result["sdk_retries_disabled_verified"])

    def test_policy_preview_claiming_api_access_is_rejected(self):
        tampered = dict(self.report)
        tampered["can_execute_D"] = True
        self.policy.return_value = tampered
        with self.assertRaises(runtime.V3LiveRuntimeBlocked):
            self.preview()

    def test_provider_policy_failure_is_sanitized_and_stops(self):
        self.policy.side_effect = RuntimeError("FAKE_SECRET_NEVER_DISPLAY")
        with self.assertRaisesRegex(
            runtime.V3LiveRuntimeBlocked, "Frozen provider policy audit failed",
        ) as captured:
            self.preview()
        self.assertNotIn("FAKE_SECRET", str(captured.exception))

    def test_readonly_preview_does_not_create_files(self):
        before = set(self.root.rglob("*"))
        self.preview()
        after = set(self.root.rglob("*"))
        self.assertEqual(before, after)

    def test_unavailable_roots_are_rejected(self):
        with self.assertRaises(runtime.V3LiveRuntimeBlocked):
            runtime.preview_v3_live_runtime(
                data_dir=Path("relative"), repo_dir=self.repo,
                expected_source_commit=PIN,
                expected_source_inventory_sha256=INVENTORY,
                expected_runtime_versions=self.versions,
            )


if __name__ == "__main__":
    unittest.main()
