"""Evaluation20 safe campaign: offline fake runner only, no paid calls."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from evaluation import evaluation20_campaign as camp
from evaluation.evaluation20_preregister import build_plan
from test_evaluation20_preregister import fake_audit

COMMIT = "1" * 40
PLAN_SHA = "a" * 64


def plan_and_run():
    plan = build_plan(fake_audit(), commit=COMMIT)
    return plan, plan["runs"][0]


def fake_prepare(cfg, case):
    assert cfg.case_id == case["case_id"]
    loaded = {
        "case_id": case["case_id"],
        "cloudbed": case["cloudbed"],
        "task_index": case["task_index"],
        "start_unix": case["start_unix"],
        "end_unix": case["end_unix"],
        "instruction": "The cloud service experienced one failure in the observed time window.",
        "query_index": 0,
    }
    return loaded, (None if cfg.canonical_variant == "A0" else "f" * 64)


def fake_output(cfg):
    loaded, ev = fake_prepare(cfg, next(
        c for c in PLAN["cases"] if c["case_id"] == cfg.case_id
    ))
    return {
        "case_id": cfg.case_id,
        "variant": cfg.variant,
        "variant_scheme": "current",
        "model": cfg.model_name,
        "model_provider": cfg.model_provider,
        "max_tool_rounds": 6,
        "output_contract_mode": "v2_enforce",
        "output_contract_v2": {"status": "valid", "error": None},
        "system_prompt_sha256": camp._prompt_sha(
            cfg.variant, loaded["task_index"], loaded["instruction"]
        ),
        "evidence_sha256": ev,
        "raw_response": '{"1": {"root cause component": "mock"}}',
        "prediction": '{"1": {"root cause component": "mock"}}',
        "json_status": "valid_json",
        "error": None,
        "metrics": {
            "input_tokens": 50, "output_tokens": 10, "total_tokens": 60,
            "llm_calls": 1, "tool_calls": 0, "tool_rounds": 0,
            "token_usage_complete": True,
            "duration_seconds": 0.01, "preprocessing_seconds": 0.0,
            "end_to_end_seconds": 0.02,
        },
    }


PLAN, RUN = plan_and_run()


class Evaluation20CampaignOfflineTests(unittest.TestCase):
    def test_preflight_is_read_only_and_300_ready(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            state = camp.preflight(
                root, root, _plan=PLAN, _plan_sha=PLAN_SHA
            )
            self.assertEqual(state["counts"], {"ready": 300})
            self.assertFalse((root / "data").exists())

    def test_no_api_authorization_no_claim(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(PermissionError):
                camp.run_one(
                    root, root, run_id=RUN["run_id"],
                    _runner=fake_output, _prepared=fake_prepare,
                    _plan=PLAN, _plan_sha=PLAN_SHA,
                )
            claim, output, sha = camp.paths(root, RUN["run_id"])
            self.assertFalse(claim.exists())
            self.assertFalse(output.exists())
            self.assertFalse(sha.exists())

    def test_fake_complete_and_no_retry(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            out = camp.run_one(
                root, root, run_id=RUN["run_id"],
                confirm_api=True, approved_budget_usd=0.01,
                _runner=fake_output, _prepared=fake_prepare,
                _plan=PLAN, _plan_sha=PLAN_SHA,
            )
            self.assertEqual(out["status"], "complete")
            claim, output, sha = camp.paths(root, RUN["run_id"])
            self.assertTrue(claim.exists() and output.exists() and sha.exists())
            doc = json.loads(output.read_text())
            self.assertEqual(
                json.loads(sha.read_text())["result_sha256"],
                camp.sha(output),
            )
            self.assertEqual(doc["evaluation20_provenance"]["plan_sha256"], PLAN_SHA)
            with self.assertRaises(FileExistsError):
                camp.run_one(
                    root, root, run_id=RUN["run_id"],
                    confirm_api=True, approved_budget_usd=0.01,
                    _runner=fake_output, _prepared=fake_prepare,
                    _plan=PLAN, _plan_sha=PLAN_SHA,
                )
            self.assertEqual(
                camp.preflight(root, root, _plan=PLAN,
                               _plan_sha=PLAN_SHA)["counts"],
                {"complete": 1, "ready": 299},
            )

    def test_missing_usage_detected_without_retry(self):
        with TemporaryDirectory() as td:
            root = Path(td)

            def incomplete(cfg):
                r = fake_output(cfg)
                r["metrics"]["token_usage_complete"] = False
                return r

            out = camp.run_one(
                root, root, run_id=RUN["run_id"],
                confirm_api=True, approved_budget_usd=0.01,
                _runner=incomplete, _prepared=fake_prepare,
                _plan=PLAN, _plan_sha=PLAN_SHA,
            )
            self.assertEqual(
                out["status"], "USAGE_INCOMPLETE_REVIEW_NO_RETRY"
            )
            self.assertTrue(camp.paths(root, RUN["run_id"])[1].exists())

    def test_claim_survives_exception(self):
        with TemporaryDirectory() as td:
            root = Path(td)

            def fail(cfg):
                raise RuntimeError("fake failure, paid status unknown")

            with self.assertRaisesRegex(RuntimeError, "fake failure"):
                camp.run_one(
                    root, root, run_id=RUN["run_id"],
                    confirm_api=True, approved_budget_usd=0.01,
                    _runner=fail, _prepared=fake_prepare,
                    _plan=PLAN, _plan_sha=PLAN_SHA,
                )
            claim, output, sha = camp.paths(root, RUN["run_id"])
            self.assertTrue(claim.exists())
            self.assertFalse(output.exists())
            self.assertFalse(sha.exists())
            self.assertEqual(
                camp.preflight(root, root, _plan=PLAN,
                               _plan_sha=PLAN_SHA)["counts"],
                {"CLAIM_PENDING_NO_AUTO_RETRY": 1, "ready": 299},
            )


if __name__ == "__main__":
    unittest.main()
