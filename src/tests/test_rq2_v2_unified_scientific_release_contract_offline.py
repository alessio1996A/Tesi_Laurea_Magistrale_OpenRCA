"""G4E: release contract RQ2-V2 scientifico — SOLTANTO fixture offline.

Questi test simulano G4A/blueprint, un pin di commit e approvazione
puramente inventata. Non forniscono, richiedono o simulano una vera
autorizzazione utente a usare API; il validatore non puo' scrivere claim.
"""
from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from evaluation.rq2_v2_unified_discovery_plan import (
    DISCOVERY, HARNESSES, MODELS, build_offline_discovery_plan,
)
from evaluation.rq2_v2_unified_release_blueprint import (
    build_unified_release_blueprint,
)
from evaluation.rq2_v2_unified_release_preflight import (
    SOURCE_PATHS, VERSION as SOURCE_VERSION,
)
from evaluation.rq2_v2_unified_scientific_release_contract import (
    RELEASE_SCHEMA, RELEASE_NAMESPACE, REQUIRED_KEYS,
    UnifiedReleaseContractError, release_digest, validate_future_release,
)

FAKE_COMMIT = "a" * 40
FAKE_SHA = hashlib.sha256(b"synthetic fixture, never API").hexdigest()


def source_fixture() -> dict:
    p = build_offline_discovery_plan()
    return {
        "version": SOURCE_VERSION,
        "protocol": p["protocol"],
        "status": "OFFLINE_SOURCE_BOUND_NO_RELEASE_NO_API",
        "plan_preview_sha256": p["preview_sha256"],
        "entries_sha256": p["entries_sha256"],
        "source_files_sha256": {path: FAKE_SHA for path in SOURCE_PATHS},
        "source_file_count": len(SOURCE_PATHS),
        "frozen_rq1_source_identity_verified": True,
        "gt_free_source_verified": True,
        "split_sha256": p["split_sha256_expected"],
        "manifest_sha256": p["manifest_sha256_expected"],
        "C_system_prompt_sha256": FAKE_SHA,
        "K_system_prompt_sha256": FAKE_SHA,
        "model_ids": p["model_ids"],
        "harnesses": list(HARNESSES),
        "discovery_cases": list(DISCOVERY),
        "ood_test_cases_locked": 11,
        "stage_counts": {"D": 60, "C": 60, "K": 60},
        "logical_stages": 180,
        "d_max_tool_rounds": 6,
        "planning_checks_reserved": 2,
        "d_output_contract": "v2_enforce",
        "claims_written": 0,
        "data_files_written": False,
        "model_requests_sent": 0,
        "ground_truth_read": False,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "scientific_release_frozen": False,
        "approved_api_budget_exists": False,
        "unified_production_ledger_implemented": False,
        "unified_provider_dispatcher_implemented": False,
        "source_commit_pinned_for_release": False,
    }


def release_fixture(src: dict, blueprint: dict) -> dict:
    p = build_offline_discovery_plan()
    return {
        "schema": RELEASE_SCHEMA,
        "protocol": p["protocol"],
        "phase": "discovery",
        "source_commit": FAKE_COMMIT,
        "blueprint_sha256": blueprint["blueprint_sha256"],
        "source_plan_sha256": p["preview_sha256"],
        "split_sha256": p["split_sha256_expected"],
        "manifest_sha256": p["manifest_sha256_expected"],
        "source_files_sha256": src["source_files_sha256"],
        "C_system_prompt_sha256": src["C_system_prompt_sha256"],
        "K_system_prompt_sha256": src["K_system_prompt_sha256"],
        "logical_models": list(MODELS),
        "model_ids": p["model_ids"],
        "harnesses": list(HARNESSES),
        "discovery_cases": list(DISCOVERY),
        "stage_counts": {"D": 60, "C": 60, "K": 60},
        "logical_stage_count": 180,
        "d_output_contract": "v2_enforce",
        "max_tool_rounds": 6,
        "planning_checks": 2,
        "proposed_scientific_namespace": RELEASE_NAMESPACE,
        "runtime_versions": {"fake-sdk": "0.test"},
        "transport_retries_proven_no_implicit_http_retry": True,
        "per_request_timeout_verified": True,
        "usage_meter_fail_closed": True,
        "single_writer_policy_proven": True,
        "max_graph_invocations_candidate": 492,
        "max_http_attempts_guaranteed": None,
        "api_budget_approved": True,
        "approved_total_usd_limit": "0.20",
        "approval_reference": "SYNTHETIC_APPROVAL_NOT_REAL",
        "ood_test_locked": True,
        "authorization": "approved_option_a_discovery_only",
        "scientific_protocol_frozen": True,
    }


class UnifiedScientificReleaseContractTests(unittest.TestCase):
    def setUp(self):
        self.source = source_fixture()
        self.blueprint = build_unified_release_blueprint(
            source_preview=self.source,
        )
        self.release = release_fixture(self.source, self.blueprint)

    def verify(self, value=None, *, sha=None, source=None, blueprint=None,
               expected_commit=FAKE_COMMIT):
        obj = self.release if value is None else value
        digest = release_digest(obj) if sha is None else sha
        return validate_future_release(
            release=obj,
            source_preview=self.source if source is None else source,
            blueprint=self.blueprint if blueprint is None else blueprint,
            externally_approved_sha256=digest,
            expected_source_commit=expected_commit,
        )

    def test_schema_is_complete_for_five_harness_three_llms(self):
        self.assertEqual(set(self.release), REQUIRED_KEYS)
        self.assertEqual(self.release["logical_stage_count"], 180)
        self.assertEqual(self.release["stage_counts"],
                         {"D": 60, "C": 60, "K": 60})
        self.assertEqual(len(self.release["harnesses"]), 5)
        self.assertEqual(len(self.release["model_ids"]), 3)
        self.assertEqual(len(self.release["discovery_cases"]), 4)

    def test_fixture_release_validation_does_not_authorize_execution(self):
        report = self.verify()
        self.assertEqual(
            report["status"], "RELEASE_CONTENT_VALIDATED_NO_EXECUTION_AUTHORITY"
        )
        for key in (
            "can_create_scientific_claim", "can_execute_api",
            "can_run_ood_test", "production_ledger_implemented",
            "production_dispatcher_implemented", "release_file_written",
        ):
            self.assertIs(report[key], False, key)
        self.assertIs(report["usd_hard_cap_guaranteed"], False)
        self.assertIsNone(report["max_http_attempts_guaranteed"])
        self.assertEqual(report["model_calls_sent"], 0)

    def test_external_release_digest_missing_fails_closed(self):
        for pin in (None, "X" * 64, "0" * 63):
            with self.subTest(pin=pin), self.assertRaises(UnifiedReleaseContractError):
                self.verify(sha=pin if pin is not None else "")

    def test_pinned_digest_mismatch_fails_closed(self):
        with self.assertRaisesRegex(
            UnifiedReleaseContractError, "Pinned release SHA",
        ):
            self.verify(sha="0" * 64)

    def test_external_commit_differs_from_release(self):
        with self.assertRaisesRegex(
            UnifiedReleaseContractError, "source_commit"
        ):
            self.verify(expected_commit="b" * 40)

    def test_release_with_extra_or_missing_key_is_refused(self):
        for variant in (
            {**self.release, "unknown": "x"},
            {k: v for k, v in self.release.items() if k != "api_budget_approved"},
        ):
            with self.subTest(keys=len(variant)), self.assertRaises(UnifiedReleaseContractError):
                self.verify(value=variant)

    def test_different_case_or_ood_test_phase_is_rejected(self):
        bad = copy.deepcopy(self.release)
        bad["discovery_cases"][0] = "cloudbed-2_q077"
        with self.assertRaises(UnifiedReleaseContractError):
            self.verify(value=bad)
        bad = copy.deepcopy(self.release)
        bad["phase"] = "test"
        with self.assertRaises(UnifiedReleaseContractError):
            self.verify(value=bad)

    def test_release_keeps_ood_locked(self):
        bad = copy.deepcopy(self.release)
        bad["ood_test_locked"] = False
        with self.assertRaises(UnifiedReleaseContractError):
            self.verify(value=bad)

    def test_approval_is_explicit_not_inferred_from_hash(self):
        for field, value in (
            ("api_budget_approved", False),
            ("approval_reference", ""),
            ("authorization", "approved_for_ood"),
        ):
            bad = copy.deepcopy(self.release)
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(UnifiedReleaseContractError):
                self.verify(value=bad)

    def test_approved_budget_must_be_decimal_string(self):
        for budget in (0.2, None, "0", "-1.00", "NaN",
                       "Infinity", "10000.01", "0.001"):
            bad = copy.deepcopy(self.release)
            bad["approved_total_usd_limit"] = budget
            with self.subTest(value=budget), self.assertRaises(UnifiedReleaseContractError):
                self.verify(value=bad)

    def test_attempt_count_is_not_a_proven_http_limit(self):
        self.assertIsNone(self.release["max_http_attempts_guaranteed"])
        bad = copy.deepcopy(self.release)
        bad["max_http_attempts_guaranteed"] = 492
        with self.assertRaises(UnifiedReleaseContractError):
            self.verify(value=bad)

    def test_transport_retry_and_timeout_proof_required(self):
        for field in (
            "transport_retries_proven_no_implicit_http_retry",
            "per_request_timeout_verified",
            "usage_meter_fail_closed",
            "single_writer_policy_proven",
        ):
            bad = copy.deepcopy(self.release)
            bad[field] = False
            with self.subTest(field=field), self.assertRaises(UnifiedReleaseContractError):
                self.verify(value=bad)

    def test_runtime_versions_cannot_be_empty(self):
        bad = copy.deepcopy(self.release)
        bad["runtime_versions"] = {}
        with self.assertRaises(UnifiedReleaseContractError):
            self.verify(value=bad)

    def test_source_preview_must_stay_non_authorizing(self):
        bad = copy.deepcopy(self.source)
        bad["can_execute_api"] = True
        with self.assertRaises(UnifiedReleaseContractError):
            self.verify(source=bad)

    def test_source_ground_truth_verification_is_necessary(self):
        bad = copy.deepcopy(self.source)
        bad["gt_free_source_verified"] = False
        with self.assertRaises(UnifiedReleaseContractError):
            self.verify(source=bad)

    def test_blueprint_sha_or_plan_mismatch_rejected(self):
        bad = copy.deepcopy(self.blueprint)
        bad["blueprint_sha256"] = "0" * 64
        with self.assertRaises(UnifiedReleaseContractError):
            self.verify(blueprint=bad)

    def test_blueprint_no_api_must_remain_false(self):
        bad = copy.deepcopy(self.blueprint)
        bad["can_execute_api"] = True
        with self.assertRaises(UnifiedReleaseContractError):
            self.verify(blueprint=bad)

    def test_determinism_and_no_file_write(self):
        with tempfile.TemporaryDirectory() as name:
            before = list(Path(name).iterdir())
            report = self.verify()
            self.assertEqual(report, self.verify())
            self.assertEqual(before, list(Path(name).iterdir()))
            self.assertRegex(report["release_sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
