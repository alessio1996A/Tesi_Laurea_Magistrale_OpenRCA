"""G4B RQ2 V2: blueprint offline per 180 stage, zero client/GT/file I/O.

Tutte le sorgenti sono fixture, non si aprono file Market o repository.
La preview di source binding è simulata: questi unittest NON sostituiscono
una verifica reale del manifest e dello split in Colab.
"""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.rq2_v2_unified_discovery_plan import (
    DISCOVERY, TEST, HARNESSES, MODELS, build_offline_discovery_plan,
)
from evaluation.rq2_v2_unified_release_preflight import (
    SOURCE_PATHS, VERSION as SOURCE_VERSION,
)
from evaluation.rq2_v2_unified_release_blueprint import (
    UnifiedRQ2BlueprintError, build_unified_release_blueprint,
)

SYNTHETIC_SHA = hashlib.sha256(b"fixture only").hexdigest()


def fake_verified_g4a() -> dict:
    plan = build_offline_discovery_plan()
    return {
        "version": SOURCE_VERSION,
        "protocol": plan["protocol"],
        "status": "OFFLINE_SOURCE_BOUND_NO_RELEASE_NO_API",
        "plan_preview_sha256": plan["preview_sha256"],
        "entries_sha256": plan["entries_sha256"],
        "source_files_sha256": {p: SYNTHETIC_SHA for p in SOURCE_PATHS},
        "source_file_count": len(SOURCE_PATHS),
        "frozen_rq1_source_identity_verified": True,
        "gt_free_source_verified": True,
        "split_sha256": plan["split_sha256_expected"],
        "manifest_sha256": plan["manifest_sha256_expected"],
        "C_system_prompt_sha256": SYNTHETIC_SHA,
        "K_system_prompt_sha256": SYNTHETIC_SHA,
        "model_ids": plan["model_ids"],
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


class UnifiedReleaseBlueprintOfflineTests(unittest.TestCase):
    def setUp(self):
        self.source = fake_verified_g4a()

    def preview(self):
        return build_unified_release_blueprint(source_preview=self.source)

    def test_all_180_planned_stage_ids_exact(self):
        draft = self.preview()
        expected = build_offline_discovery_plan()
        self.assertEqual(draft["logical_stage_count"], 180)
        self.assertEqual(
            [x["stage_id"] for x in draft["entries"]],
            [x["stage_id"] for x in expected["entries"]],
        )
        self.assertEqual(len({x["stage_id"] for x in draft["entries"]}), 180)

    def test_three_models_have_20_d_20_c_20_k_each(self):
        draft = self.preview()
        self.assertEqual(
            set(draft["per_model_stage_counts"]), set(MODELS),
        )
        for val in draft["per_model_stage_counts"].values():
            self.assertEqual(val, {"D": 20, "C": 20, "K": 20})

    def test_d_invocation_budgets_differ_only_by_harness(self):
        draft = self.preview()
        for row in draft["entries"]:
            if row["stage"] != "D":
                self.assertEqual(row["max_logical_model_invocations_candidate"], 1)
                self.assertFalse(row["tool_calls_allowed"])
                self.assertEqual(row["d_tool_rounds_cap"], 0)
            elif row["harness"] in ("A1_8R_Planning", "A1_PAVE"):
                self.assertEqual(row["max_logical_model_invocations_candidate"], 5)
                self.assertEqual(row["d_planner_checks_reserved"], 2)
                self.assertTrue(row["tool_calls_allowed"])
            else:
                self.assertEqual(row["max_logical_model_invocations_candidate"], 7)
                self.assertEqual(row["d_planner_checks_reserved"], 0)
                self.assertTrue(row["tool_calls_allowed"])
                self.assertEqual(row["d_tool_rounds_cap"], 6)

    def test_max_492_are_graph_invocations_not_http_or_cost_caps(self):
        draft = self.preview()
        self.assertEqual(
            draft["max_graph_invocations_if_all_stages_reached_candidate"], 492
        )
        self.assertIsNone(draft["max_http_requests_guaranteed"])
        self.assertIsNone(draft["max_billed_usd_guaranteed"])
        self.assertFalse(draft["transport_policy_effective_retries_certified"])

    def test_all_dependency_ids_and_stage_order(self):
        draft = self.preview()
        positions = {
            row["stage_id"]: i for i, row in enumerate(draft["entries"])
        }
        for row in draft["entries"]:
            self.assertTrue(all(
                x in positions and positions[x] < positions[row["stage_id"]]
                for x in row["depends_on"]
            ))
            self.assertEqual(len(row["depends_on"]),
                             0 if row["stage"] == "D" else 1)

    def test_only_four_discovery_all_ood_locked(self):
        draft = self.preview()
        self.assertEqual(
            {x["case_id"] for x in draft["entries"]}, set(DISCOVERY)
        )
        self.assertFalse(
            {x["case_id"] for x in draft["entries"]} & set(TEST)
        )
        self.assertEqual(draft["ood_test_cases_locked"], 11)

    def test_all_stages_remain_blocked_even_if_source_verified(self):
        draft = self.preview()
        self.assertEqual({x["stage_execution_permission"]
                          for x in draft["entries"]}, {"BLOCKED_NO_RELEASE"})
        self.assertTrue(all(
            x["candidate_transport_retries_verified"] is False
            for x in draft["entries"]
        ))
        for field in (
            "can_write_scientific_claims", "can_create_provider_client",
            "can_execute_api", "can_run_ood_test",
            "scientific_release_frozen",
        ):
            self.assertIs(draft[field], False, field)
        self.assertEqual(draft["api_authorization"], "NOT_REQUESTED")

    def test_synthetic_archive_not_reused_for_scientific_data(self):
        draft = self.preview()
        self.assertTrue(draft["no_synthetic_store_reuse"])
        self.assertNotIn("synthetic", draft["proposed_scientific_namespace"])
        self.assertNotEqual(draft["proposed_scientific_namespace"],
                            "data/rq2_v2_provenance")

    def test_blueprint_is_deterministic_and_source_untouched(self):
        original = copy.deepcopy(self.source)
        a = self.preview()
        b = self.preview()
        self.assertEqual(a, b)
        self.assertEqual(original, self.source)
        self.assertRegex(a["blueprint_sha256"], r"^[0-9a-f]{64}$")

    def test_no_files_written_on_empty_root(self):
        with tempfile.TemporaryDirectory() as name:
            before = list(Path(name).iterdir())
            self.preview()
            self.assertEqual(list(Path(name).iterdir()), before)

    def test_missing_source_report_is_rejected(self):
        for invalid in (None, {}, []):
            with self.subTest(value=invalid):
                with self.assertRaises(UnifiedRQ2BlueprintError):
                    build_unified_release_blueprint(source_preview=invalid)

    def test_source_lock_cannot_be_undone(self):
        for field in ("can_execute_api", "can_run_ood_test",
                      "approved_api_budget_exists", "scientific_release_frozen"):
            bad = copy.deepcopy(self.source)
            bad[field] = True
            with self.subTest(field=field):
                with self.assertRaises(UnifiedRQ2BlueprintError):
                    build_unified_release_blueprint(source_preview=bad)

    def test_forged_plan_digest_rejected(self):
        for field in ("plan_preview_sha256", "entries_sha256"):
            bad = copy.deepcopy(self.source)
            bad[field] = "0" * 64
            with self.subTest(field=field), self.assertRaises(UnifiedRQ2BlueprintError):
                build_unified_release_blueprint(source_preview=bad)

    def test_wrong_data_sha_rejected(self):
        for field in ("split_sha256", "manifest_sha256"):
            bad = copy.deepcopy(self.source)
            bad[field] = "0" * 64
            with self.subTest(field=field), self.assertRaises(UnifiedRQ2BlueprintError):
                build_unified_release_blueprint(source_preview=bad)

    def test_missing_or_invalid_code_sha_rejected(self):
        for invalid in ({}, {"agent/graph_engine.py": SYNTHETIC_SHA},
                        {p: "NOT-SHA" for p in SOURCE_PATHS}):
            bad = copy.deepcopy(self.source)
            bad["source_files_sha256"] = invalid
            with self.subTest(value=str(invalid)[:40]):
                with self.assertRaises(UnifiedRQ2BlueprintError):
                    build_unified_release_blueprint(source_preview=bad)

    def test_missing_prompt_sha_rejected(self):
        bad = copy.deepcopy(self.source)
        bad["K_system_prompt_sha256"] = "not a SHA"
        with self.assertRaises(UnifiedRQ2BlueprintError):
            build_unified_release_blueprint(source_preview=bad)

    def test_rq1_source_identity_not_optional(self):
        bad = copy.deepcopy(self.source)
        bad["frozen_rq1_source_identity_verified"] = False
        with self.assertRaises(UnifiedRQ2BlueprintError):
            build_unified_release_blueprint(source_preview=bad)

    def test_all_release_prerequisites_explicit(self):
        draft = self.preview()
        missing = draft["missing_release_prerequisites"]
        self.assertGreaterEqual(len(missing), 9)
        self.assertTrue(any("ledger" in x for x in missing))
        self.assertTrue(any("retry" in x for x in missing))
        self.assertTrue(any("authorization" in x for x in missing))
        self.assertTrue(any("GT-free" in x for x in missing))


if __name__ == "__main__":
    unittest.main()
