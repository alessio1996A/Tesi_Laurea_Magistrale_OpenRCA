"""Offline tests for 5+1 campaign orchestrator: no real API/Drive."""
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation import planner_5p1_campaign as campaign


class TestFivePlusOneCampaign(unittest.TestCase):
    def setUp(self):
        self.status = {f"case-{i}": "ready" for i in range(8)}
        self.calls = []
        self.pending = None
        self.plan_sha = "a" * 64
        self.commit = "b" * 40

    def fake_preflight(self, data_dir, repo_dir):
        rows = []
        for i in range(8):
            cid = f"case-{i}"
            rows.append({
                "run_id": f"{cid}-5p1", "case_id": cid, "arm": "5p1",
                "order": 0, "status": self.status[cid],
            })
            rows.append({
                "run_id": f"{cid}-4p2", "case_id": cid, "arm": "4p2",
                "order": 1, "status": "blocked_by_previous",
            })
        return {
            "protocol": "offline-fixture", "git_commit": self.commit,
            "plan_sha256": self.plan_sha, "runs": rows,
        }

    def fake_run_one(self, data_dir, repo_dir, *, run_id, confirm_api,
                     approved_budget_usd):
        self.assertTrue(confirm_api)
        self.assertEqual(approved_budget_usd, 1.5)
        self.assertTrue(run_id.endswith("-5p1"))
        cid = run_id.removesuffix("-5p1")
        self.calls.append(run_id)
        self.status[cid] = "complete"
        return {"run_id": run_id, "integrity": "complete"}

    def test_preflight_only_five_plus_one(self):
        with patch.object(campaign.ablation, "preflight",
                          side_effect=self.fake_preflight):
            result = campaign.preflight_5p1(Path("data"), Path("repo"))
        self.assertEqual(result["planned_runs"], 8)
        self.assertEqual(len(result["runs"]), 8)
        self.assertEqual(result["status_counts"], {"ready": 8})
        self.assertFalse(result["blocked"])
        self.assertFalse(result["llm_called"])

    def test_no_authorization_no_calls(self):
        with self.assertRaises(PermissionError):
            campaign.run_5p1_campaign(
                Path("data"), Path("repo"),
                max_new_runs=2, approved_budget_usd=1.5,
                _run_one=self.fake_run_one,
            )
        with self.assertRaises(PermissionError):
            campaign.run_5p1_campaign(
                Path("data"), Path("repo"), confirm_api=True,
                max_new_runs=9, approved_budget_usd=1.5,
                _run_one=self.fake_run_one,
            )
        self.assertEqual(self.calls, [])

    def test_checkpoint_resume_skips_completed_runs(self):
        with patch.object(campaign.ablation, "preflight",
                          side_effect=self.fake_preflight):
            first = campaign.run_5p1_campaign(
                Path("data"), Path("repo"), confirm_api=True,
                approved_budget_usd=1.5, max_new_runs=3,
                _run_one=self.fake_run_one,
            )
            self.assertEqual(first["new_runs_this_invocation"], 3)
            self.assertEqual(len(self.calls), 3)
            second = campaign.run_5p1_campaign(
                Path("data"), Path("repo"), confirm_api=True,
                approved_budget_usd=1.5, max_new_runs=8,
                _run_one=self.fake_run_one,
            )
        self.assertEqual(second["new_runs_this_invocation"], 5)
        self.assertEqual(len(self.calls), 8)
        self.assertEqual(len(set(self.calls)), 8)
        self.assertEqual(second["status_counts"], {"complete": 8})

    def test_pending_claim_blocks_all_and_no_repeat(self):
        self.status["case-2"] = "CLAIM_PENDING_NO_AUTO_RETRY"
        with patch.object(campaign.ablation, "preflight",
                          side_effect=self.fake_preflight):
            state = campaign.preflight_5p1(Path("data"), Path("repo"))
            self.assertTrue(state["blocked"])
            with self.assertRaises(RuntimeError):
                campaign.run_5p1_campaign(
                    Path("data"), Path("repo"), confirm_api=True,
                    approved_budget_usd=1.5, max_new_runs=8,
                    _run_one=self.fake_run_one,
                )
        self.assertEqual(self.calls, [])

    def test_crash_leaves_claim_and_blocks_resume(self):
        def interrupted(data_dir, repo_dir, *, run_id,
                        confirm_api, approved_budget_usd):
            self.calls.append(run_id)
            cid = run_id.removesuffix("-5p1")
            self.status[cid] = "CLAIM_PENDING_NO_AUTO_RETRY"
            raise ConnectionError("Simulation: connection lost after claim")

        with patch.object(campaign.ablation, "preflight",
                          side_effect=self.fake_preflight):
            with self.assertRaises(ConnectionError):
                campaign.run_5p1_campaign(
                    Path("data"), Path("repo"), confirm_api=True,
                    approved_budget_usd=1.5, max_new_runs=8,
                    _run_one=interrupted,
                )
            with self.assertRaises(RuntimeError):
                campaign.run_5p1_campaign(
                    Path("data"), Path("repo"), confirm_api=True,
                    approved_budget_usd=1.5, max_new_runs=8,
                    _run_one=interrupted,
                )
        self.assertEqual(len(self.calls), 1)

    def test_plan_sha_change_blocks_next_call(self):
        def run_and_change(data_dir, repo_dir, *, run_id,
                           confirm_api, approved_budget_usd):
            self.fake_run_one(data_dir, repo_dir, run_id=run_id,
                              confirm_api=confirm_api,
                              approved_budget_usd=approved_budget_usd)
            self.plan_sha = "d" * 64
            return {"integrity": "complete"}

        with patch.object(campaign.ablation, "preflight",
                          side_effect=self.fake_preflight):
            with self.assertRaises(RuntimeError):
                campaign.run_5p1_campaign(
                    Path("data"), Path("repo"), confirm_api=True,
                    approved_budget_usd=1.5, max_new_runs=8,
                    _run_one=run_and_change,
                )
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
