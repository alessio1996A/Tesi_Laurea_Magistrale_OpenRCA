"""Offline V3 scientific design plan checks; zero model/API/GT/claims.

All V3 D/C/K identities differ from V2, but incident cohort, three
models, five harnesses, per-stage dependencies and prompts are unchanged.
Tests never open the scientific data filesystem or run the benchmark.
"""
from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

import evaluation.rq2_v3_unified_gtfree_discovery_plan as v3
from evaluation.rq2_v2_unified_discovery_plan import (
    VERSION as V2_PROTOCOL,
    build_offline_discovery_plan,
)


class V3GTFreeSuccessorPlanTests(unittest.TestCase):
    def test_frozen_matrix_is_180_new_stages_without_old_ids(self):
        newer = v3.build_offline_v3_discovery_plan()
        older = build_offline_discovery_plan()
        self.assertEqual(newer["logical_stages"], 180)
        self.assertEqual(newer["stage_counts"], {"D": 60, "C": 60, "K": 60})
        self.assertEqual(len(newer["entries"]), 180)
        self.assertEqual(len(set(r["stage_id"] for r in newer["entries"])), 180)
        self.assertTrue(all(r["stage_id"].startswith(v3.VERSION + ":")
                            for r in newer["entries"]))
        self.assertFalse(set(r["stage_id"] for r in newer["entries"]) &
                         set(r["stage_id"] for r in older["entries"]))

    def test_each_arm_case_and_provider_is_unchanged(self):
        newer = v3.build_offline_v3_discovery_plan()
        older = build_offline_discovery_plan()
        fields = (
            "case_id", "logical_model", "model_id", "model_provider",
            "harness", "stage", "d_engine",
        )
        for old, new in zip(older["entries"], newer["entries"]):
            with self.subTest(stage_id=new["stage_id"]):
                for field in fields:
                    self.assertEqual(old[field], new[field])
        self.assertEqual(newer["models"], ["gemini", "sonnet", "haiku"])
        self.assertEqual(len(newer["harnesses"]), 5)
        self.assertEqual(len(newer["discovery_cases"]), 4)

    def test_d_c_k_parent_bindings_only_within_v3(self):
        plan = v3.build_offline_v3_discovery_plan()
        for row in plan["entries"]:
            prefix = row["stage_id"].rsplit(":", 1)[0]
            expected = {
                "D": [], "C": [prefix + ":D"], "K": [prefix + ":C"],
            }[row["stage"]]
            self.assertEqual(row["depends_on"], expected)
            self.assertTrue(all(not x.startswith(V2_PROTOCOL + ":")
                                for x in row["depends_on"]))

    def test_ood_locked_and_all_live_controls_disabled(self):
        plan = v3.build_offline_v3_discovery_plan()
        self.assertEqual(len(plan["ood_test_cases_locked"]), 11)
        self.assertTrue(set(plan["discovery_cases"]).isdisjoint(
            plan["ood_test_cases_locked"]
        ))
        for field in (
            "release_frozen", "source_commit_pinned", "can_execute_api",
            "can_write_scientific_claims", "can_run_ood_test",
            "ground_truth_read", "telemetry_read", "historical_results_read",
            "files_written", "reuse_v2_d_outputs", "reuse_v2_c_or_k_outputs",
        ):
            self.assertIs(plan[field], False, field)
        self.assertEqual(plan["model_api_calls"], 0)

    def test_distinct_namespace_and_uniform_ck_contract(self):
        plan = v3.build_offline_v3_discovery_plan()
        self.assertEqual(
            plan["scientific_namespace_proposed"],
            "data/rq2_v3_unified_scientific_v1",
        )
        self.assertEqual(
            plan["release_relative_path_proposed"],
            "data/rq2_v3_unified_scientific_v1/release_v1.json",
        )
        self.assertEqual(
            plan["ck_text_extraction_policy"],
            "rq2_ck_exact_text_fragments_candidate_v1",
        )
        self.assertEqual(
            plan["ck_text_provenance_schema"],
            "rq2_v3_ck_text_extraction_meta_v0",
        )
        self.assertEqual(plan["c_and_k_prompts"],
                         "rq2_probe_adapter_v0_unchanged")
        self.assertEqual(plan["d_output_contract"], "v2_enforce")

    def test_canonical_hashes_and_read_only_stability(self):
        a = v3.build_offline_v3_discovery_plan()
        b = v3.build_offline_v3_discovery_plan()
        self.assertEqual(a, b)
        self.assertEqual(a["preview_sha256"], v3._sha({
            k: val for k, val in a.items() if k != "preview_sha256"
        }))
        self.assertEqual(a["entries_sha256"], v3._sha(a["entries"]))
        self.assertEqual(a["base_v2_plan_sha256"],
                         build_offline_discovery_plan()["preview_sha256"])
        json.dumps(a, ensure_ascii=False, sort_keys=True, allow_nan=False)

    def test_rejects_tampered_baseline_digest(self):
        old = copy.deepcopy(build_offline_discovery_plan())
        old["entries"][0]["model_id"] = "synthetic-wrong-model-id"
        with patch.object(v3, "build_offline_discovery_plan", return_value=old):
            with self.assertRaises(v3.RQ2V3PlanBlocked):
                v3.build_offline_v3_discovery_plan()

    def test_rejects_changed_legacy_dependency_even_if_rehashed(self):
        old = copy.deepcopy(build_offline_discovery_plan())
        old["entries"][1]["depends_on"] = []
        old["entries_sha256"] = v3._sha(old["entries"])
        old["preview_sha256"] = v3._sha({
            k: val for k, val in old.items() if k != "preview_sha256"
        })
        with patch.object(v3, "build_offline_discovery_plan", return_value=old):
            with self.assertRaises(v3.RQ2V3PlanBlocked):
                v3.build_offline_v3_discovery_plan()


if __name__ == "__main__":
    unittest.main()
