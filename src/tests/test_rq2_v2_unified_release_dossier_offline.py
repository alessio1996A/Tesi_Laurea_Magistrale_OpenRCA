"""Solo unit test in memoria per dossier prerelease G4E/G4F RQ2-V2.

Nessuna release, approvazione, chiamata SDK, GT, file scientifico o API.
Le fixture del contratto G4E NON sono evidenza di source freeze reale.
"""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import rq2_v2_unified_release_dossier_offline as subject
from evaluation.rq2_provider_policy_source_audit import EXPECTED_COLAB_VERSIONS
from evaluation.rq2_v2_unified_release_blueprint import (
    build_unified_release_blueprint,
)
from test_rq2_v2_unified_scientific_release_contract_offline import source_fixture


class PrereleaseDossierOfflineTests(unittest.TestCase):
    def setUp(self):
        self.source = source_fixture()
        self.blueprint = build_unified_release_blueprint(
            source_preview=self.source,
        )
        self.commit = "a" * 40
        self.versions = dict(EXPECTED_COLAB_VERSIONS)

    def review(self, *, source=None, blueprint=None, commit=None, versions=None):
        return subject.build_prerelease_dossier(
            source_preview=self.source if source is None else source,
            blueprint=self.blueprint if blueprint is None else blueprint,
            expected_commit=self.commit if commit is None else commit,
            runtime_versions=self.versions if versions is None else versions,
        )

    def test_exact_30_source_identity_and_pilot(self):
        review = self.review()
        self.assertEqual(review["source_file_count"], 30)
        self.assertRegex(review["source_inventory_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            review["k_rubric_sha256"],
            self.source["source_files_sha256"][subject.K_RUBRIC_PATH],
        )
        self.assertEqual(review["blueprint_sha256"], self.blueprint["blueprint_sha256"])
        self.assertEqual(review["logical_stages_planned"], 180)
        self.assertEqual(review["ood_test_count_locked"], 11)
        self.assertTrue(
            review["candidate_pilot_stage_id"].endswith(":cloudbed-1_q032:gemini:A0:D")
        )

    def test_no_release_or_paid_authority_from_passing_dossier(self):
        review = self.review()
        for key in (
            "external_release_approval_present", "approved_budget_present",
            "per_stage_paid_api_approval_present",
            "source_commit_frozen_for_live_release", "release_manifest_created",
            "full_stage_timeout_guaranteed", "usd_hard_cap_guaranteed",
            "can_execute_api", "can_run_ood_test", "files_written",
        ):
            self.assertIs(review[key], False, key)
        self.assertIsNone(review["release_sha256"])
        self.assertIsNone(review["max_http_attempts_guaranteed"])
        self.assertEqual(review["real_provider_requests_sent"], 0)
        self.assertEqual(review["scientific_claims_written"], 0)

    def test_dossier_is_deterministic_and_no_disk_created(self):
        with tempfile.TemporaryDirectory() as root:
            before = list(Path(root).iterdir())
            self.assertEqual(self.review(), self.review())
            self.assertEqual(list(Path(root).iterdir()), before)

    def test_missing_commit_pin_fails_closed(self):
        for value in ("", "x" * 40, "a" * 39, "a" * 41):
            with self.subTest(pin=value):
                with self.assertRaises(subject.ReleaseDossierBlocked):
                    self.review(commit=value)

    def test_forged_29_source_inventory_fails_closed(self):
        broken = copy.deepcopy(self.source)
        del broken["source_files_sha256"][subject.K_RUBRIC_PATH]
        broken["source_file_count"] = 29
        with self.assertRaisesRegex(subject.ReleaseDossierBlocked, "30 source"):
            self.review(source=broken)

    def test_forged_extra_source_is_rejected(self):
        broken = copy.deepcopy(self.source)
        broken["source_files_sha256"]["evaluation/fake_extra.py"] = "f" * 64
        broken["source_file_count"] = 31
        with self.assertRaises(subject.ReleaseDossierBlocked):
            self.review(source=broken)

    def test_rubric_source_sha_must_be_well_formed(self):
        broken = copy.deepcopy(self.source)
        broken["source_files_sha256"][subject.K_RUBRIC_PATH] = "not-a-sha"
        with self.assertRaises(subject.ReleaseDossierBlocked):
            self.review(source=broken)

    def test_wrong_sdk_version_fails_closed(self):
        broken = dict(self.versions)
        name = next(iter(broken))
        broken[name] = "99.99.99"
        with self.assertRaisesRegex(subject.ReleaseDossierBlocked, "SDK versions"):
            self.review(versions=broken)

    def test_unexpected_sdk_distribution_fails_closed(self):
        broken = dict(self.versions)
        broken["fake-adapter"] = "1.0"
        with self.assertRaisesRegex(subject.ReleaseDossierBlocked, "Unexpected"):
            self.review(versions=broken)

    def test_source_cannot_self_grant_budget_or_provider_authority(self):
        for key, value in (
            ("can_execute_api", True),
            ("approved_api_budget_exists", True),
            ("scientific_release_frozen", True),
            ("source_commit_pinned_for_release", True),
            ("claims_written", 1),
        ):
            broken = copy.deepcopy(self.source)
            broken[key] = value
            with self.subTest(key=key):
                with self.assertRaises(subject.ReleaseDossierBlocked):
                    self.review(source=broken)

    def test_gt_or_ood_unlocked_rejected(self):
        for key, value in (
            ("ground_truth_read", True),
            ("can_run_ood_test", True),
            ("ood_test_cases_locked", 10),
        ):
            broken = copy.deepcopy(self.source)
            broken[key] = value
            with self.subTest(key=key), self.assertRaises(
                subject.ReleaseDossierBlocked
            ):
                self.review(source=broken)

    def test_blueprint_tampering_rejected(self):
        broken = copy.deepcopy(self.blueprint)
        broken["can_execute_api"] = True
        with self.assertRaisesRegex(subject.ReleaseDossierBlocked, "blueprint mismatch"):
            self.review(blueprint=broken)

    def test_transport_policy_drift_rejected(self):
        with patch.object(subject, "TIMEOUT_SECONDS", 100.0):
            with self.assertRaisesRegex(subject.ReleaseDossierBlocked, "policy drift"):
                self.review()

    def test_not_a_release_even_when_synthetic_fixture_looks_approved(self):
        report = self.review()
        self.assertNotIn("approval_reference", report)
        self.assertNotIn("approved_total_usd_limit", report)
        self.assertNotIn("api_budget_approved", report)
        self.assertNotIn("authorization", report)
        self.assertIn("REVIEW_ONLY", report["status"])


if __name__ == "__main__":
    unittest.main()
