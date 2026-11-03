"""Test V2.6 offline: senza rete, API, Market.zip o ground truth."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.v2_campaign_runner import (
    PROTOCOL, _output_paths, execute_exactly_one, preflight_campaign,
)
from output.v2_task_contract import COMPONENT, REASON


def fake_plan():
    case = {
        "case_id": "cloudbed-1_q005",
        "cloudbed": "cloudbed-1",
        "start_unix": 1647747000,
        "end_unix": 1647748800,
        "task_index": "task_2",
        "requested_fault_count": 1,
        "ordered_variants": ["A0", "A1_V2", "A1", "A1_VERIFY", "A1_VERIFY_ST"],
        "run_ids": [
            f"{PROTOCOL}__cloudbed-1_q005__{v.lower()}__r01"
            for v in ("A0", "A1_V2", "A1", "A1_VERIFY", "A1_VERIFY_ST")
        ],
    }
    return {
        "protocol": PROTOCOL,
        "git_commit": "a" * 40,
        "model_name": "gemini-3.5-flash-lite",
        "model_provider": "google",
        "max_tool_rounds": 6,
        "max_verification_checks": 2,
        "recursion_limit": 30,
        "cases": [case],
    }


def fake_result(config):
    return {
        "variant": config.variant,
        "case_id": config.case_id,
        "cloudbed": "cloudbed-1",
        "task_index": "task_2",
        "model": "gemini-3.5-flash-lite",
        "model_provider": "google",
        "max_tool_rounds": 6,
        "output_contract_mode": "v2_enforce",
        "raw_response": json.dumps({
            "1": {REASON: "synthetic fault"}
        }),
        "json_status": "valid_json",
        "output_contract_v2": {"valid": True},
        "evidence_sha256": "b" * 64,
        "metrics": {
            "tool_rounds": 1,
            "exploration_tool_rounds": 1,
            "verification_tool_rounds": 0,
        },
        "verification": {"causa_verificata": False},
    }


class V2CampaignRunnerTests(unittest.TestCase):
    def test_status_read_only_for_all_pending_runs(self):
        plan = fake_plan()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch(
                "evaluation.v2_campaign_runner.load_preregistered",
                return_value=(plan, "c" * 64),
            ):
                status = preflight_campaign(root, root)
            self.assertEqual(status["status_counts"], {"ready": 5})
            self.assertFalse(status["llm_called"])
            self.assertFalse(status["files_written"])
            self.assertFalse((root / "data/results/v2").exists())

    def test_status_claim_and_output_do_not_trigger_retry(self):
        plan = fake_plan()
        run_id = plan["cases"][0]["run_ids"][0]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            claim, output = _output_paths(root, run_id)
            claim.parent.mkdir(parents=True)
            claim.write_text('{"started":true}', encoding="utf-8")
            with patch(
                "evaluation.v2_campaign_runner.load_preregistered",
                return_value=(plan, "c" * 64),
            ):
                status = preflight_campaign(root, root)
            self.assertEqual(
                status["runs"][0]["status"],
                "started_or_interrupted_NO_AUTO_RETRY",
            )
            output.write_text('{"example":"saved"}', encoding="utf-8")
            with patch(
                "evaluation.v2_campaign_runner.load_preregistered",
                return_value=(plan, "c" * 64),
            ):
                status = preflight_campaign(root, root)
            self.assertEqual(status["runs"][0]["status"], "complete")

    def test_execution_without_explicit_api_consent_denied(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(PermissionError):
                execute_exactly_one(
                    root, root, run_id="anything", confirm_api=False,
                )
            self.assertFalse((root / "data/results/v2").exists())

    def test_one_fake_run_saves_with_claim_then_denies_reexecution(self):
        plan = fake_plan()
        run_id = plan["cases"][0]["run_ids"][0]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch(
                    "evaluation.v2_campaign_runner.load_preregistered",
                    return_value=(plan, "c" * 64),
                ),
                patch(
                    "evaluation.experiment_runner.carica_caso",
                    return_value={
                        "case_id": "cloudbed-1_q005",
                        "cloudbed": "cloudbed-1",
                        "task_index": "task_2",
                        "start_unix": 1647747000,
                        "end_unix": 1647748800,
                    },
                ),
                patch(
                    "evaluation.experiment_runner.prepara_esperimento",
                    return_value={
                        "caso": {
                            "case_id": "cloudbed-1_q005",
                            "cloudbed": "cloudbed-1",
                            "task_index": "task_2",
                            "start_unix": 1647747000,
                            "end_unix": 1647748800,
                        },
                        "evidence_sha256": "b" * 64,
                    },
                ),
            ):
                first = execute_exactly_one(
                    root, root, run_id=run_id, confirm_api=True,
                    _runner=fake_result,
                )
                self.assertEqual(first["integrity_issues"], [])
                claim, output = _output_paths(root, run_id)
                self.assertTrue(claim.exists())
                self.assertTrue(output.exists())
                result = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(result["v2_provenance"]["run_id"], run_id)
                with self.assertRaises(FileExistsError):
                    execute_exactly_one(
                        root, root, run_id=run_id, confirm_api=True,
                        _runner=fake_result,
                    )

    def test_fake_runner_error_still_preserves_claim_no_retry(self):
        plan = fake_plan()
        run_id = plan["cases"][0]["run_ids"][0]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch(
                    "evaluation.v2_campaign_runner.load_preregistered",
                    return_value=(plan, "c" * 64),
                ),
                patch(
                    "evaluation.experiment_runner.carica_caso",
                    return_value={
                        "case_id": "cloudbed-1_q005",
                        "cloudbed": "cloudbed-1",
                        "task_index": "task_2",
                        "start_unix": 1647747000,
                        "end_unix": 1647748800,
                    },
                ),
                patch(
                    "evaluation.experiment_runner.prepara_esperimento",
                    return_value={
                        "caso": {
                            "case_id": "cloudbed-1_q005",
                            "cloudbed": "cloudbed-1",
                            "task_index": "task_2",
                            "start_unix": 1647747000,
                            "end_unix": 1647748800,
                        },
                        "evidence_sha256": "b" * 64,
                    },
                ),
            ):
                def crash(_):
                    raise RuntimeError("synthetic interruption")
                with self.assertRaisesRegex(RuntimeError, "interruption"):
                    execute_exactly_one(
                        root, root, run_id=run_id, confirm_api=True,
                        _runner=crash,
                    )
                claim, output = _output_paths(root, run_id)
                self.assertTrue(claim.exists())
                self.assertFalse(output.exists())
                with self.assertRaises(FileExistsError):
                    execute_exactly_one(
                        root, root, run_id=run_id, confirm_api=True,
                        _runner=fake_result,
                    )


if __name__ == "__main__":
    unittest.main()
