"""Test offline del freeze V2, senza Gemini o file del benchmark."""
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from evaluation.v2_cohort_selector import PROTOCOL, VARIANTS
from evaluation.v2_preregister import (
    EXPECTED_CASES, build_preregistered_plan, write_plan_exclusive,
)

COMMIT = "a" * 40


def proposal_fixture():
    cases = [
        ("cloudbed-1_q005", "task_2", 1),
        ("cloudbed-1_q066", "task_6", 1),
        ("cloudbed-1_q027", "task_7", 2),
        ("cloudbed-1_q013", "task_5", 1),
        ("cloudbed-2_q071", "task_4", 2),
        ("cloudbed-2_q020", "task_6", 1),
        ("cloudbed-2_q034", "task_1", 1),
        ("cloudbed-2_q024", "task_3", 1),
    ]
    result = []
    for i, (case_id, task, n) in enumerate(cases):
        start = 1600000000 + i * 3600
        result.append({
            "case_id": case_id,
            "cloudbed": case_id.split("_")[0],
            "start_unix": start,
            "end_unix": start + 1800,
            "task_index": task,
            "requested_fault_count": n,
        })
    return {
        "status": "PROPOSED_NOT_FROZEN_NOT_EXECUTED",
        "protocol": PROTOCOL,
        "output_contract_mode": "v2_enforce",
        "case_count": 8,
        "planned_runs": 40,
        "replicas_per_case_variant": 1,
        "gemini_calls": 0,
        "read_ground_truth": False,
        "read_predictions": False,
        "read_scorer": False,
        "selected_cases": result,
        "variant_order": list(VARIANTS),
        "seed": "synthetic-fixed-seed",
        "selection_policy": "seven_tasks_and_multifault_per_cloudbed_v1",
        "split_sha256": "b" * 64,
        "manifest_sha256": "c" * 64,
        "network_inventory_sha256": "d" * 64,
    }


class V2PreregisterTests(unittest.TestCase):
    def test_40_unique_run_ids_and_rotated_execution_order(self):
        plan = build_preregistered_plan(proposal_fixture(), code_commit=COMMIT)
        self.assertEqual(plan["run_count"], 40)
        self.assertEqual(len(plan["cases"]), 8)
        self.assertEqual(plan["git_commit"], COMMIT)
        self.assertEqual(
            {r["case_id"] for r in plan["cases"]}, EXPECTED_CASES
        )
        run_ids = [r for case in plan["cases"] for r in case["run_ids"]]
        self.assertEqual(len(set(run_ids)), 40)
        for i, case in enumerate(plan["cases"]):
            self.assertEqual(
                case["ordered_variants"],
                list(VARIANTS[i % 5:] + VARIANTS[:i % 5]),
            )
            self.assertEqual(len(case["run_ids"]), 5)
        self.assertFalse(plan["scoring_performed"])
        self.assertFalse(plan["ground_truth_accessed"])
        self.assertEqual(plan["gemini_calls"], 0)

    def test_fail_closed_if_eight_ids_change(self):
        proposal = proposal_fixture()
        proposal["selected_cases"][0]["case_id"] = "cloudbed-1_q099"
        with self.assertRaisesRegex(ValueError, "otto casi"):
            build_preregistered_plan(proposal, code_commit=COMMIT)

    def test_fail_closed_on_overlap(self):
        proposal = proposal_fixture()
        proposal["selected_cases"][1]["start_unix"] = (
            proposal["selected_cases"][0]["start_unix"]
        )
        proposal["selected_cases"][1]["end_unix"] = (
            proposal["selected_cases"][0]["end_unix"]
        )
        with self.assertRaisesRegex(ValueError, "sovrapposte"):
            build_preregistered_plan(proposal, code_commit=COMMIT)

    def test_fail_closed_if_task_or_multifault_coverage_broken(self):
        proposal = proposal_fixture()
        proposal["selected_cases"][6]["task_index"] = "task_6"
        with self.assertRaisesRegex(ValueError, "Sette task"):
            build_preregistered_plan(proposal, code_commit=COMMIT)
        proposal = proposal_fixture()
        proposal["selected_cases"][2]["requested_fault_count"] = 1
        with self.assertRaisesRegex(ValueError, "Guasti multipli"):
            build_preregistered_plan(proposal, code_commit=COMMIT)

    def test_create_only_never_overwrites(self):
        plan = build_preregistered_plan(proposal_fixture(), code_commit=COMMIT)
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "data/protocols/v2/protocol.json"
            write_plan_exclusive(plan, target)
            original = target.read_bytes()
            with self.assertRaises(FileExistsError):
                write_plan_exclusive(plan, target)
            self.assertEqual(target.read_bytes(), original)

    def test_invalid_commit_or_proposal_rejected(self):
        with self.assertRaisesRegex(ValueError, "Commit"):
            build_preregistered_plan(proposal_fixture(), code_commit="main")
        p = proposal_fixture()
        p["read_ground_truth"] = True
        with self.assertRaisesRegex(ValueError, "prerequisiti"):
            build_preregistered_plan(p, code_commit=COMMIT)


if __name__ == "__main__":
    unittest.main()
