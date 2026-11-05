"""Regression tests for Claude 80-run development campaign. NO API."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation import claude_development_campaign as a
from evaluation import claude_development_freeze as freeze
from evaluation.v2_preregister import EXPECTED_CASES

GIT = "a" * 40
EVIDENCE = "b" * 64
PROMPT = "c" * 64


def save_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class ClaudeCampaignTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / "drive"
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.cases = []
        manifests = []
        splits = []
        variants = ["A0", "A1_V2", "A1", "A1_VERIFY", "A1_VERIFY_ST"]
        for i, cid in enumerate(sorted(EXPECTED_CASES)):
            cb = cid.split("_")[0]
            start = 50000 + i * 4000
            self.cases.append({
                "case_id": cid, "cloudbed": cb, "task_index": "task_1",
                "start_unix": start, "end_unix": start + 1800,
                "requested_fault_count": 1,
                "ordered_variants": variants[i%5:] + variants[:i%5],
            })
            manifests.append({
                "case_id": cid, "cloudbed": cb,
                "task_index": "task_1", "instruction": "Locate failure.",
                "start_unix": start, "end_unix": start + 1800,
            })
            splits.append({
                "case_id": cid, "cloudbed": cb, "split": "development",
                "start_unix": start, "end_unix": start + 1800,
            })
        processed = self.data / "data/processed"
        save_csv(processed / "split_market_v1.csv", splits)
        save_csv(processed / "benchmark_inputs_market.csv", manifests)
        source = {
            "protocol": a.V3_PROTOCOL,
            "status": "PREREGISTERED_NOT_EXECUTED",
            "git_commit": a.V3_SHA,
            "case_count": 8, "run_count": 40,
            "model_provider": "google",
            "model_name": "gemini-3.5-flash-lite",
            "max_tool_rounds": 6, "max_verification_checks": 2,
            "output_contract_mode": "v2_enforce",
            "ground_truth_accessed": False,
            "split_sha256": a._sha(processed / "split_market_v1.csv"),
            "manifest_sha256": a._sha(processed / "benchmark_inputs_market.csv"),
            "cases": self.cases,
        }
        original = self.data / "data/protocols/v2" / f"{a.V3_PROTOCOL}_plan_v1.json"
        original.parent.mkdir(parents=True)
        original.write_text(json.dumps(source), encoding="utf-8")
        self.original_bytes = original.read_bytes()
        self.patchers = [
            patch.object(a, "V3_PLAN_SHA", a._sha(original)),
            patch.object(a, "_git_head", return_value=GIT),
            patch.object(a, "_prompt_sha", return_value=PROMPT),
        ]
        for p in self.patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_exactly_80_with_40_sonnet_then_40_haiku(self):
        path = a.write_plan(self.data, self.repo)
        self.assertTrue(path.exists())
        plan, _ = a.load_plan(self.data, self.repo)
        self.assertEqual(plan["run_count"], 80)
        self.assertEqual(len(plan["runs"]), 80)
        self.assertEqual(len({r["run_id"] for r in plan["runs"]}), 80)
        self.assertEqual(
            [r["model_key"] for r in plan["runs"]],
            ["sonnet"] * 40 + ["haiku"] * 40,
        )
        for r in plan["runs"]:
            self.assertIn(r["variant"], a.VARIANTS)
        self.assertEqual(
            [r["variant"] for r in plan["runs"][:5]],
            list(a.VARIANTS),
        )
        old = (self.data / "data/protocols/v2"
               / f"{a.V3_PROTOCOL}_plan_v1.json")
        self.assertEqual(old.read_bytes(), self.original_bytes)
        with self.assertRaises(FileExistsError):
            a.write_plan(self.data, self.repo)

    def test_preflight_offline_and_no_consent_no_execution(self):
        a.write_plan(self.data, self.repo)
        state = a.preflight(self.data, self.repo)
        self.assertEqual(state["counts"], {"ready": 80})
        self.assertEqual(state["models"]["sonnet"], {"ready": 40})
        self.assertEqual(state["models"]["haiku"], {"ready": 40})
        with self.assertRaises(PermissionError):
            a.run_batch(self.data, self.repo,
                        model_key="sonnet", max_new_runs=2)
        with self.assertRaises(PermissionError):
            a.run_batch(self.data, self.repo,
                        model_key="sonnet", max_new_runs=40,
                        confirm_api=True, approved_budget_usd=2.0)

    def _prepared(self, cfg):
        item = next(x for x in self.cases if x["case_id"] == cfg.case_id)
        return {
            "caso": item,
            "evidence_sha256": (
                None if cfg.variant == "A0" else EVIDENCE
            ),
        }

    def _result(self, cfg, error=None):
        return {
            "case_id": cfg.case_id, "variant": cfg.variant,
            "variant_scheme": "current", "model_provider": "anthropic",
            "model": cfg.model_name,
            "max_tool_rounds": 6,
            "system_prompt_sha256": PROMPT,
            "evidence_sha256": (
                None if cfg.variant == "A0" else EVIDENCE
            ),
            "output_contract_v2": {"status": "valid"},
            "prediction": "{}",
            "raw_response": "{}" if error is None else None,
            "error": error,
            "metrics": {
                "tool_rounds": 2,
                "exploration_tool_rounds": 1,
                "verification_tool_rounds": 1,
                "token_usage_complete": error is None,
                "input_tokens": 100, "output_tokens": 10,
                "total_tokens": 110,
            },
            "verification": {"causa_verificata": False},
            "max_verification_checks": 2,
            "exploration_round_limit": 4,
        }

    def _load_case(self, cfg):
        return next(x for x in self.cases if x["case_id"] == cfg.case_id)

    def test_two_run_batch_persists_hash_and_resumes_without_repeat(self):
        a.write_plan(self.data, self.repo)
        called = []
        def fake_run(cfg):
            called.append(cfg.variant)
            return self._result(cfg)

        with patch("evaluation.experiment_runner.carica_caso",
                   side_effect=self._load_case), patch(
                       "evaluation.experiment_runner.prepara_esperimento",
                       side_effect=self._prepared):
            first = a.run_batch(
                self.data, self.repo, model_key="sonnet",
                max_new_runs=2, confirm_api=True,
                approved_budget_usd=2.0, _runner=fake_run,
            )
            self.assertEqual(first["new_run_count"], 2)
            second = a.run_batch(
                self.data, self.repo, model_key="sonnet",
                max_new_runs=1, confirm_api=True,
                approved_budget_usd=2.0, _runner=fake_run,
            )
            self.assertEqual(second["new_run_count"], 1)
        self.assertEqual(len(called), 3)
        self.assertEqual(a.preflight(self.data, self.repo)["models"]["sonnet"],
                         {"complete": 3, "ready": 37})
        run_id = first["new_runs"][0]
        claim, output, digest = a._paths(self.data, run_id)
        self.assertTrue(claim.exists() and output.exists() and digest.exists())
        self.assertEqual(
            json.loads(digest.read_text())["output_sha256"],
            a._sha(output)
        )

    def test_provider_error_stored_and_no_auto_retry(self):
        a.write_plan(self.data, self.repo)
        first = a.preflight(self.data, self.repo)["runs"][0]
        calls = []
        def fake_failed(cfg):
            calls.append(cfg.variant)
            return self._result(cfg, "APIError: 503 UNAVAILABLE")

        with patch("evaluation.experiment_runner.carica_caso",
                   side_effect=self._load_case), patch(
                       "evaluation.experiment_runner.prepara_esperimento",
                       side_effect=self._prepared):
            with self.assertRaisesRegex(RuntimeError, "MODEL_ERROR_REVIEW_NO_RETRY"):
                a.run_batch(
                    self.data, self.repo, model_key="sonnet",
                    max_new_runs=2, confirm_api=True,
                    approved_budget_usd=2.0, _runner=fake_failed,
                )
        rows = a.preflight(self.data, self.repo)["runs"]
        self.assertEqual(rows[0]["status"], "MODEL_ERROR_REVIEW_NO_RETRY")
        self.assertEqual(len(calls), 1)
        with self.assertRaises(FileExistsError):
            a.run_one(
                self.data, self.repo, run_id=first["run_id"],
                confirm_api=True, approved_budget_usd=2.0,
                _runner=fake_failed,
            )

    def test_tampered_result_is_review_and_not_rerun(self):
        a.write_plan(self.data, self.repo)
        first = a.preflight(self.data, self.repo)["runs"][0]
        with patch("evaluation.experiment_runner.carica_caso",
                   side_effect=self._load_case), patch(
                       "evaluation.experiment_runner.prepara_esperimento",
                       side_effect=self._prepared):
            a.run_one(
                self.data, self.repo, run_id=first["run_id"],
                confirm_api=True, approved_budget_usd=2.0,
                _runner=self._result,
            )
        _, output, _ = a._paths(self.data, first["run_id"])
        with output.open("a", encoding="utf-8") as fp:
            fp.write(" ")
        self.assertEqual(
            a.preflight(self.data, self.repo)["runs"][0]["status"],
            "REVIEW_INTEGRITY",
        )

    def test_freeze_sonnet_after_40_complete_offline(self):
        a.write_plan(self.data, self.repo)
        with self.assertRaisesRegex(ValueError, "40 output"):
            freeze.build_freeze(self.data, self.repo, "sonnet")
        with patch("evaluation.experiment_runner.carica_caso",
                   side_effect=self._load_case), patch(
                       "evaluation.experiment_runner.prepara_esperimento",
                       side_effect=self._prepared):
            for _ in range(5):
                result = a.run_batch(
                    self.data, self.repo, model_key="sonnet",
                    max_new_runs=8, confirm_api=True,
                    approved_budget_usd=2.0, _runner=self._result,
                )
                self.assertEqual(result["new_run_count"], 8)
        statement = freeze.build_freeze(self.data, self.repo, "sonnet")
        self.assertEqual(statement["run_count"], 40)
        self.assertEqual(statement["complete"], 40)
        self.assertEqual(statement["model_errors"], 0)
        self.assertFalse(statement["scoring_performed"])
        self.assertFalse(statement["read_query_csv"])
        path = freeze.freeze_path(self.data, "sonnet")
        a._write_only_new(path, statement)
        with self.assertRaises(FileExistsError):
            a._write_only_new(path, statement)
        with self.assertRaisesRegex(ValueError, "40 output"):
            freeze.build_freeze(self.data, self.repo, "haiku")

    def test_v2_does_not_touch_v1_plan_or_interrupted_claim(self):
        old_plan = (
            self.data / "data/protocols/v2"
            / f"{a.PREVIOUS_PROTOCOL}_plan_v1.json"
        )
        old_plan.write_text("V1 ORIGINAL PLAN SENTINEL", encoding="utf-8")
        v1_result_dir = (
            self.data / "data/results/v2" / a.PREVIOUS_PROTOCOL
        )
        v1_result_dir.mkdir(parents=True, exist_ok=True)
        old_claim = v1_result_dir / (a.PREVIOUS_INTERRUPTED_RUN + ".claim.json")
        old_claim.write_text("V1 CLAIM SENTINEL", encoding="utf-8")

        plan_v1_bytes = old_plan.read_bytes()
        claim_v1_bytes = old_claim.read_bytes()

        new_path = a.write_plan(self.data, self.repo)
        self.assertIn("development_v2", str(new_path))
        self.assertEqual(old_plan.read_bytes(), plan_v1_bytes)
        self.assertEqual(old_claim.read_bytes(), claim_v1_bytes)
        self.assertFalse(
            (v1_result_dir / (a.PREVIOUS_INTERRUPTED_RUN + ".json")).exists()
        )
        plan, _ = a.load_plan(self.data, self.repo)
        self.assertEqual(
            plan["recovery_provenance"]["previous_plan_sha256"],
            a.PREVIOUS_PLAN_SHA,
        )
        self.assertFalse(
            plan["recovery_provenance"]["previous_results_reused"]
        )

    def test_v3_preserves_v2_result_and_plan_exactly(self):
        v2_plan = (
            self.data / "data/protocols/v2"
            / f"{a.V2_PROTOCOL}_plan_v1.json"
        )
        v2_plan.write_text("V2 FROZEN PLAN SENTINEL", encoding="utf-8")
        v2_results = self.data / "data/results/v2" / a.V2_PROTOCOL
        v2_results.mkdir(parents=True, exist_ok=True)
        v2_result = v2_results / (a.V2_INVALID_JSON_RUN + ".json")
        v2_result.write_text("V2 FROZEN RESULT SENTINEL", encoding="utf-8")
        expected_plan = v2_plan.read_bytes()
        expected_output = v2_result.read_bytes()

        new_plan = a.write_plan(self.data, self.repo)
        self.assertIn("development_v3", str(new_plan))
        self.assertEqual(v2_plan.read_bytes(), expected_plan)
        self.assertEqual(v2_result.read_bytes(), expected_output)
        plan, _ = a.load_plan(self.data, self.repo)
        self.assertEqual(plan["recovery_provenance"]["v2_plan_sha256"], a.V2_PLAN_SHA)
        self.assertEqual(
            plan["recovery_provenance"]["v2_infrastructure_output_sha256"],
            a.V2_INVALID_JSON_OUTPUT_SHA,
        )
        self.assertFalse(
            plan["recovery_provenance"]["v2_infrastructure_result_reused"]
        )
        self.assertEqual(
            plan["response_text_extraction"], "text_blocks_only_v1"
        )

    def test_source_rejects_ground_truth_column(self):
        manifest = self.data / "data/processed/benchmark_inputs_market.csv"
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(text.replace("instruction", "reason"),
                            encoding="utf-8")
        with self.assertRaises(ValueError):
            a.build_plan(self.data, GIT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
