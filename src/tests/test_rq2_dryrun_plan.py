"""Mock-only tests of the non-executable RQ2 dry-run stage workflow.

No real Market content, labels, telemetry, models or disk writes.
"""
import copy
import unittest

from evaluation.rq2_dryrun_plan import (
    EXPECTED_SPLIT_SHA256,
    EXPECTED_MANIFEST_SHA256,
    HARNESSES,
    MODELS,
    RQ2PlanError,
    make_workflow_preview,
    verify_candidate_allocation,
)


def synthetic_cohort():
    metadata = []
    for bed, count in (("cloudbed-1", 8), ("cloudbed-2", 7)):
        for index in range(count):
            start = index * 10800 + (200000 if bed == "cloudbed-2" else 0)
            if bed == "cloudbed-1" and index == 1:
                start = 0  # shared-window pair q000/q001
            metadata.append({
                "case_id": f"{bed}_q{index:03d}",
                "cloudbed": bed,
                "task_index": "task_2",
                "start_unix": start,
                "end_unix": start + 1800,
            })
    groups = [
        ["cloudbed-1_q000", "cloudbed-1_q001"],
        *[[f"cloudbed-1_q{x:03d}"] for x in range(2, 8)],
        *[[f"cloudbed-2_q{x:03d}"] for x in range(7)],
    ]
    discovery = (
        "cloudbed-1_q003", "cloudbed-1_q006",
        "cloudbed-2_q002", "cloudbed-2_q005",
    )
    test = tuple(sorted({x["case_id"] for x in metadata} - set(discovery)))
    return metadata, groups, discovery, test


def plan(**overrides):
    metadata, groups, discovery, test = synthetic_cohort()
    opts = {
        "metadata": metadata,
        "groups": groups,
        "discovery": discovery,
        "test": test,
        "split_sha256": EXPECTED_SPLIT_SHA256,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
    }
    opts.update(overrides)
    return make_workflow_preview(**opts)


class RQ2DryRunPlanTests(unittest.TestCase):
    def test_counts_and_no_executable_status(self):
        result = plan()
        self.assertEqual(result["status"], "DRAFT_NOT_EXECUTABLE")
        self.assertFalse(result["can_execute_api"])
        self.assertFalse(result["api_budget_approved"])
        self.assertFalse(result["provider_model_versions_frozen"])
        self.assertFalse(result["files_written"])
        self.assertFalse(result["reads_ground_truth"])
        self.assertFalse(result["reads_predictions"])
        self.assertFalse(result["reads_telemetry"])
        self.assertEqual(result["model_api_calls"], 0)
        self.assertEqual(result["stages"], {"C": 90, "D": 90, "K": 24})
        self.assertEqual(result["total_stage_entries"], 204)

    def test_k_is_only_in_discovery_and_test_has_only_d_c(self):
        result = plan()
        self.assertEqual(
            sum(item["stage"] == "K" for item in result["entries"]), 24
        )
        self.assertTrue(all(
            item["phase"] == "discovery"
            for item in result["entries"] if item["stage"] == "K"
        ))
        self.assertTrue(all(
            item["stage"] in ("D", "C")
            for item in result["entries"] if item["phase"] == "test"
        ))
        self.assertTrue(all(
            item["execution_status"] == "BLOCKED_DRAFT"
            for item in result["entries"]
        ))

    def test_every_entry_dependency_refers_to_previous_stage(self):
        result = plan()
        earlier = set()
        for entry in result["entries"]:
            self.assertTrue(set(entry["dependencies"]) <= earlier)
            if entry["stage"] == "D":
                self.assertEqual(entry["dependencies"], [])
            if entry["stage"] in ("C", "K"):
                self.assertEqual(len(entry["dependencies"]), 1)
            earlier.add(entry["stage_id"])

    def test_same_input_produces_same_plan_digest(self):
        a = plan()
        b = plan()
        self.assertEqual(a, b)
        self.assertEqual(len(a["preview_sha256"]), 64)
        self.assertEqual(a["logical_models"], list(MODELS))
        self.assertEqual(a["harnesses"], list(HARNESSES))
        self.assertEqual(a["partition"]["discovery_windows"], 4)
        self.assertEqual(a["partition"]["test_windows"], 10)

    def test_shared_window_group_cannot_cross_phase(self):
        metadata, groups, discovery, test = synthetic_cohort()
        # Move one of shared window cases into discovery; keep 4+11 overall
        new_d = tuple(sorted(
            (set(discovery) - {"cloudbed-1_q003"}) | {"cloudbed-1_q000"}
        ))
        new_t = tuple(sorted(set(test) - {"cloudbed-1_q000"} | {"cloudbed-1_q003"}))
        with self.assertRaisesRegex(RQ2PlanError, "group split"):
            verify_candidate_allocation(
                metadata, groups, discovery=new_d, test=new_t
            )

    def test_nearby_cross_phase_windows_rejected(self):
        metadata, groups, discovery, test = synthetic_cohort()
        altered = copy.deepcopy(metadata)
        for row in altered:
            if row["case_id"] == "cloudbed-1_q002":
                row["start_unix"] = 3 * 10800 + 1800
                row["end_unix"] = row["start_unix"] + 1800
        with self.assertRaisesRegex(RQ2PlanError, "proximity"):
            verify_candidate_allocation(
                altered, groups, discovery=discovery, test=test
            )

    def test_unknown_or_missing_cases_rejected(self):
        metadata, groups, discovery, test = synthetic_cohort()
        with self.assertRaisesRegex(RQ2PlanError, "exactly"):
            verify_candidate_allocation(
                metadata, groups, discovery=discovery, test=test[:-1]
            )

    def test_duplicate_discovery_rejected(self):
        metadata, groups, discovery, test = synthetic_cohort()
        with self.assertRaisesRegex(RQ2PlanError, "Duplicate"):
            verify_candidate_allocation(
                metadata, groups, discovery=discovery + (discovery[0],),
                test=test, enforce_real_size=False
            )

    def test_unexpected_gt_field_in_metadata_rejected(self):
        metadata, groups, discovery, test = synthetic_cohort()
        metadata[0]["reason"] = "synthetic label: never expose"
        with self.assertRaisesRegex(RQ2PlanError, "GT-free"):
            verify_candidate_allocation(
                metadata, groups, discovery=discovery, test=test
            )

    def test_manifest_sha_mismatch_rejected(self):
        with self.assertRaisesRegex(RQ2PlanError, "hash mismatch"):
            plan(manifest_sha256="0" * 64)

    def test_split_sha_mismatch_rejected(self):
        with self.assertRaisesRegex(RQ2PlanError, "hash mismatch"):
            plan(split_sha256="0" * 64)

    def test_no_label_mapping_or_scoring_leak_in_plan(self):
        result = plan()
        forbidden = ("scoring_points", "ground_truth", "target_reason",
                     "fault_label", "label_map", "record.csv")
        text = str(result).lower()
        for term in forbidden:
            with self.subTest(term=term):
                self.assertNotIn(term, text)
        self.assertFalse(any(
            "reason" in item or "label" in item
            for item in result["entries"]
        ))

    def test_invalid_unix_range_rejected(self):
        metadata, groups, discovery, test = synthetic_cohort()
        metadata[0]["end_unix"] = metadata[0]["start_unix"]
        with self.assertRaisesRegex(RQ2PlanError, "window"):
            verify_candidate_allocation(
                metadata, groups, discovery=discovery, test=test
            )

    def test_unexpected_task_or_cloudbed_rejected(self):
        metadata, groups, discovery, test = synthetic_cohort()
        metadata[0]["task_index"] = None
        with self.assertRaisesRegex(RQ2PlanError, "task index"):
            verify_candidate_allocation(
                metadata, groups, discovery=discovery, test=test
            )

    def test_missing_group_rejected(self):
        metadata, groups, discovery, test = synthetic_cohort()
        with self.assertRaisesRegex(RQ2PlanError, "groups do not cover"):
            verify_candidate_allocation(
                metadata, groups[:-1], discovery=discovery, test=test
            )


if __name__ == "__main__":
    unittest.main()
