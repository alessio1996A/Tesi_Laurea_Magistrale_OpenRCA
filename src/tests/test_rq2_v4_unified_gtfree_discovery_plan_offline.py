"""RQ2-V4 plan tests: solo determinismo, identity e protezione OOD."""
from __future__ import annotations

import unittest

from evaluation.rq2_v3_unified_gtfree_discovery_plan import (
    build_offline_v3_discovery_plan,
)
from evaluation.rq2_v4_unified_gtfree_discovery_plan import (
    VERSION, NAMESPACE, RELEASE_FILE, build_offline_v4_discovery_plan,
)


class V4OfflinePlanTests(unittest.TestCase):
    def test_180_stages_and_11_ood_are_strictly_separate(self):
        plan = build_offline_v4_discovery_plan()
        self.assertEqual(plan["status"], "V4_TASK_AWARE_DRAFT_NO_RELEASE_NO_API")
        self.assertEqual(plan["stage_counts"], {"D": 60, "C": 60, "K": 60})
        self.assertEqual(plan["logical_stages"], 180)
        self.assertEqual(len(plan["entries"]), 180)
        self.assertEqual(len(plan["ood_test_cases_locked"]), 11)
        self.assertEqual(len(plan["discovery_cases"]), 4)
        self.assertTrue(
            set(plan["discovery_cases"]).isdisjoint(plan["ood_test_cases_locked"])
        )
        self.assertFalse(plan["can_execute_api"])
        self.assertFalse(plan["can_create_claim"])
        self.assertFalse(plan["can_run_ood_test"])
        self.assertFalse(plan["source_release_frozen"])
        self.assertEqual(plan["files_written"], False)
        self.assertEqual(plan["provider_requests_sent"], 0)

    def test_new_namespace_and_no_historical_stage_ids(self):
        p = build_offline_v4_discovery_plan()
        old = build_offline_v3_discovery_plan()
        self.assertEqual(p["scientific_namespace"], NAMESPACE.as_posix())
        self.assertEqual(p["release_file"], RELEASE_FILE.as_posix())
        self.assertNotEqual(p["scientific_namespace"], old["scientific_namespace_proposed"])
        self.assertTrue(all(r["stage_id"].startswith(VERSION + ":")
                            for r in p["entries"]))
        self.assertTrue(set(r["stage_id"] for r in p["entries"])
                        .isdisjoint(r["stage_id"] for r in old["entries"]))
        self.assertFalse(p["reuse_v3_d_outputs"])
        self.assertFalse(p["reuse_v3_c_or_k_outputs"])
        self.assertFalse(p["reuse_v2_d_or_ck_outputs"])

    def test_unchanged_model_harness_engine_case_identity(self):
        p = build_offline_v4_discovery_plan()
        old = build_offline_v3_discovery_plan()
        self.assertEqual(p["source_plan_sha256"], old["preview_sha256"])
        for a, b in zip(p["entries"], old["entries"]):
            for name in (
                "case_id", "logical_model", "model_id",
                "model_provider", "harness", "stage", "d_engine",
            ):
                self.assertEqual(a[name], b[name])
        self.assertEqual(
            p["preview_sha256"],
            build_offline_v4_discovery_plan()["preview_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
