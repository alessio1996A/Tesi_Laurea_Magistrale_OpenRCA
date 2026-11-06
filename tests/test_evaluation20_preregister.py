"""Test fake/GT-free preregistro EVALUATION20, nessuna API."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from evaluation.evaluation20_preregister import (
    EXPECTED_IDS, MODELS, VARIANTS, PROTOCOL,
    build_plan, create_only, destination, render,
)
from evaluation.evaluation20_preflight import (
    SEED, SPLIT_SHA256, MANIFEST_SHA256, V3_PLAN_SHA,
)


def fake_audit():
    cases = []
    for i, case_id in enumerate(EXPECTED_IDS):
        cb = case_id.split("_")[0]
        start = 1647700000 + i * 1900
        task = f"task_{(i % 7) + 1}"
        cases.append({
            "case_id": case_id,
            "cloudbed": cb,
            "start_unix": start,
            "end_unix": start + 1800,
            "task_index": task,
            "requested_fault_count": 2 if i in (2, 11) else 1,
        })
    return {
        "status": "PROPOSED_GT_FREE_NOT_FROZEN_NOT_EXECUTED",
        "target_new_cases": 20,
        "evaluation_rows_checked": 23,
        "strict_candidate_count": 23,
        "split_sha256": SPLIT_SHA256,
        "manifest_sha256": MANIFEST_SHA256,
        "development_v3_plan_sha256": V3_PLAN_SHA,
        "selection_seed": SEED,
        "read_ground_truth": False,
        "read_query_csv": False,
        "read_record_csv": False,
        "read_telemetry": False,
        "read_predictions": False,
        "scoring_performed": False,
        "model_api_calls": 0,
        "files_written": False,
        "proposed_cases": cases,
    }


class Evaluation20PreregistrationTests(unittest.TestCase):
    def test_three_hundred_run_matrix(self):
        plan = build_plan(fake_audit(), commit="1" * 40)
        self.assertEqual(plan["status"], "PREREGISTERED_NOT_EXECUTED")
        self.assertEqual(plan["case_count"], 20)
        self.assertEqual(plan["run_count"], 300)
        self.assertEqual(len(plan["runs"]), 300)
        self.assertEqual(len({r["run_id"] for r in plan["runs"]}), 300)
        self.assertEqual(set(r["model_key"] for r in plan["runs"]), set(MODELS))
        self.assertEqual(set(r["variant"] for r in plan["runs"]), set(VARIANTS))
        self.assertEqual(plan["protocol"], PROTOCOL)
        for row in plan["cases"]:
            self.assertEqual(len(row["ordered_run_ids"]), 15)
        self.assertFalse(plan["authorization_granted"])

    def test_reproducible(self):
        a = fake_audit()
        self.assertEqual(
            render(build_plan(a, commit="1" * 40)),
            render(build_plan(a, commit="1" * 40)),
        )

    def test_different_selected_id_is_rejected(self):
        a = fake_audit()
        a["proposed_cases"][0]["case_id"] = "cloudbed-1_q999"
        with self.assertRaises(ValueError):
            build_plan(a, commit="1" * 40)

    def test_no_ground_truth_flags(self):
        a = fake_audit()
        a["read_ground_truth"] = True
        with self.assertRaises(ValueError):
            build_plan(a, commit="1" * 40)

    def test_bad_sha_rejected(self):
        a = fake_audit()
        a["split_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            build_plan(a, commit="1" * 40)

    def test_bad_commit_rejected(self):
        with self.assertRaises(ValueError):
            build_plan(fake_audit(), commit="x")

    def test_create_only_never_overwrites(self):
        with TemporaryDirectory() as td:
            dest = destination(Path(td))
            payload = render(build_plan(fake_audit(), commit="1" * 40))
            sha = create_only(dest, payload)
            self.assertEqual(dest.read_bytes(), payload)
            self.assertEqual(len(sha), 64)
            with self.assertRaises(FileExistsError):
                create_only(dest, payload)
            self.assertEqual(dest.read_bytes(), payload)

    def test_no_api_or_scorer_in_plan(self):
        plan = build_plan(fake_audit(), commit="1" * 40)
        self.assertFalse(plan["api_calls_performed"])
        self.assertFalse(plan["scoring_performed"])
        self.assertFalse(plan["read_ground_truth"])


if __name__ == "__main__":
    unittest.main()
