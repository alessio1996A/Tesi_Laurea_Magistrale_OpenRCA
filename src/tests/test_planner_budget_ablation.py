"""Test offline Fase 1: nessuna API, nessuna ground truth, nessun output V3."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation import planner_budget_ablation as a
from evaluation.v2_preregister import EXPECTED_CASES

GIT = "a" * 40
EVIDENCE = "b" * 64
PROMPT = "c" * 64


def write_csv(path, headers, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


class TestPlannerBudgetAblation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / "data"
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        cases = []
        manifest_rows = []
        split_rows = []
        for i, cid in enumerate(sorted(EXPECTED_CASES)):
            cb = cid.split("_")[0]
            # Synthetic windows, with no overlap within each cloudbed.
            start = 2000 + i * 4000
            cases.append({
                "case_id": cid, "cloudbed": cb, "task_index": "task_1",
                "start_unix": start, "end_unix": start + 1800,
                "requested_fault_count": 1,
            })
            manifest_rows.append({
                "case_id": cid, "cloudbed": cb,
                "start_unix": start, "end_unix": start + 1800,
                "task_index": "task_1", "instruction": "Identify the failure.",
            })
            split_rows.append({
                "case_id": cid, "cloudbed": cb,
                "start_unix": start, "end_unix": start + 1800,
                "split": "development",
            })
        self.cases = cases
        processed = self.data / "data/processed"
        write_csv(processed / "benchmark_inputs_market.csv",
                  list(manifest_rows[0]), manifest_rows)
        write_csv(processed / "split_market_v1.csv",
                  list(split_rows[0]), split_rows)
        source = {
            "protocol": a.V3_PROTOCOL,
            "status": "PREREGISTERED_NOT_EXECUTED",
            "git_commit": "6747eecc77c1b2fff7d581c7284578b5c574b4f7",
            "model_provider": "google",
            "model_name": "gemini-3.5-flash-lite",
            "max_tool_rounds": 6, "max_verification_checks": 2,
            "output_contract_mode": "v2_enforce",
            "case_count": 8, "run_count": 40,
            "ground_truth_accessed": False,
            "split_sha256": a._sha(processed / "split_market_v1.csv"),
            "manifest_sha256": a._sha(processed / "benchmark_inputs_market.csv"),
            "cases": cases,
        }
        old = self.data / "data/protocols/v2" / f"{a.V3_PROTOCOL}_plan_v1.json"
        old.parent.mkdir(parents=True)
        old.write_text(json.dumps(source), encoding="utf-8")
        self.old_bytes = old.read_bytes()
        self.git_patch = patch.object(a, "_git_head", return_value=GIT)
        self.prompt_patch = patch.object(a, "_prompt_hash", return_value=PROMPT)
        self.git_patch.start()
        self.prompt_patch.start()
        self.addCleanup(self.git_patch.stop)
        self.addCleanup(self.prompt_patch.stop)

    def make_plan(self):
        return a.write_plan(self.data, self.repo)

    def test_plan_exclusive_16_same_cases_and_no_v3_change(self):
        self.make_plan()
        plan, digest = a.load_plan(self.data, self.repo)
        self.assertEqual(plan["git_commit"], GIT)
        self.assertEqual(plan["run_count"], 16)
        self.assertEqual(len(plan["cases"]), 8)
        self.assertEqual({c["case_id"] for c in plan["cases"]}, EXPECTED_CASES)
        self.assertEqual(plan["max_verification_checks_by_arm"], {"4p2": 2, "5p1": 1})
        for i, case in enumerate(plan["cases"]):
            self.assertEqual(set(case["arm_order"]), {"4p2", "5p1"})
            self.assertEqual(case["arm_order"][0], "4p2" if i % 2 == 0 else "5p1")
            self.assertEqual(case["system_prompt_sha256"], PROMPT)
        self.assertEqual(len(digest), 64)
        with self.assertRaises(FileExistsError):
            self.make_plan()
        old = self.data / "data/protocols/v2" / f"{a.V3_PROTOCOL}_plan_v1.json"
        self.assertEqual(old.read_bytes(), self.old_bytes)

    def test_preflight_offline_and_explicit_authorization(self):
        self.make_plan()
        state = a.preflight(self.data, self.repo)
        self.assertEqual(state["status_counts"], {
            "blocked_by_previous": 8, "ready": 8,
        })
        self.assertFalse(state["llm_called"])
        run_id = state["runs"][0]["run_id"]
        with self.assertRaises(PermissionError):
            a.run_exactly_one(self.data, self.repo, run_id=run_id)
        self.assertFalse(a._paths(self.data, run_id)[0].exists())

    def _fake_runner(self, config):
        return {
            "case_id": config.case_id, "variant": config.variant,
            "variant_scheme": "current", "model": config.model_name,
            "model_provider": config.model_provider, "max_tool_rounds": 6,
            "max_verification_checks": config.max_verification_checks,
            "exploration_round_limit": 6 - config.max_verification_checks,
            "system_prompt_sha256": PROMPT,
            "evidence_sha256": EVIDENCE, "error": None,
            "output_contract_v2": {"status": "valid"},
            "metrics": {"exploration_tool_rounds": 2,
                        "verification_tool_rounds": 1,
                        "tool_rounds": 3, "input_tokens": 100,
                        "output_tokens": 50, "total_tokens": 150},
        }

    def _fake_preparation(self, config):
        case = next(c for c in self.cases if c["case_id"] == config.case_id)
        return {"caso": case, "evidence_sha256": EVIDENCE}

    def test_one_run_create_only_and_second_arm_unlocked(self):
        self.make_plan()
        calls = []
        def runner(config):
            calls.append(config.max_verification_checks)
            return self._fake_runner(config)
        first = a.preflight(self.data, self.repo)["runs"][0]
        with patch("evaluation.experiment_runner.prepara_esperimento",
                   side_effect=self._fake_preparation):
            reply = a.run_exactly_one(
                self.data, self.repo, run_id=first["run_id"],
                confirm_api=True, approved_budget_usd=1.0,
                _runner=runner,
            )
        self.assertEqual(reply["integrity"], "complete")
        self.assertEqual(calls, [a.ARMS[first["arm"]]])
        state = a.preflight(self.data, self.repo)
        self.assertEqual(
            [x["status"] for x in state["runs"][:2]], ["complete", "ready"]
        )
        with self.assertRaises(FileExistsError):
            a.run_exactly_one(
                self.data, self.repo, run_id=first["run_id"],
                confirm_api=True, approved_budget_usd=1.0, _runner=runner,
            )
        self.assertEqual(len(calls), 1)

    def test_orphan_and_claim_are_never_retried(self):
        self.make_plan()
        state = a.preflight(self.data, self.repo)
        first, other = state["runs"][0], state["runs"][2]
        claim, _ = a._paths(self.data, first["run_id"])
        a._exclusive_json(claim, {"status": "PENDING"})
        _, output = a._paths(self.data, other["run_id"])
        a._exclusive_json(output, {"status": "ORPHAN"})
        counts = a.preflight(self.data, self.repo)["status_counts"]
        self.assertEqual(counts["CLAIM_PENDING_NO_AUTO_RETRY"], 1)
        self.assertEqual(counts["ORPHAN_OUTPUT_REVIEW"], 1)
        self.assertEqual(counts["blocked_by_previous"], 8)

    def test_corrupted_source_fails_before_run(self):
        self.make_plan()
        old = self.data / "data/protocols/v2" / f"{a.V3_PROTOCOL}_plan_v1.json"
        old.write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            a.preflight(self.data, self.repo)

    def test_no_ground_truth_columns(self):
        manifest = self.data / "data/processed/benchmark_inputs_market.csv"
        contents = manifest.read_text(encoding="utf-8")
        manifest.write_text(contents.replace(
            "instruction", "scoring_points"
        ), encoding="utf-8")
        with self.assertRaises(ValueError):
            a.build_plan(self.data, GIT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
