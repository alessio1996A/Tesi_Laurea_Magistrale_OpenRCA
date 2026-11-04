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
    # Il protocollo V3 congelato deve usare sempre gli ID originali.
    assert config.variant_scheme == "historic_v3"
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
        "evidence_sha256": None if config.variant == "A0" else "b" * 64,
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
            self.assertEqual(status["status_counts"], {
                "ready": 1,
                "waiting_for_previous_variant": 4,
            })
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

    def test_second_variant_waits_for_first_without_api(self):
        plan = fake_plan()
        next_id = plan["cases"][0]["run_ids"][1]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch(
                "evaluation.v2_campaign_runner.load_preregistered",
                return_value=(plan, "c" * 64),
            ):
                status = preflight_campaign(root, root)
                self.assertEqual(
                    status["runs"][1]["status"],
                    "waiting_for_previous_variant",
                )
                with self.assertRaises(FileExistsError):
                    execute_exactly_one(
                        root, root, run_id=next_id,
                        confirm_api=True, _runner=fake_result,
                    )
                next_claim, next_output = _output_paths(root, next_id)
                self.assertFalse(next_claim.exists())
                self.assertFalse(next_output.exists())

    def test_second_variant_checks_predecessor_provenance(self):
        plan = fake_plan()
        first_id, next_id = plan["cases"][0]["run_ids"][:2]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old_claim, old_output = _output_paths(root, first_id)
            old_claim.parent.mkdir(parents=True)
            old_claim.write_text(json.dumps({
                "run_id": first_id, "plan_sha256": "c" * 64,
            }), encoding="utf-8")
            old_output.write_text(json.dumps({
                "v2_provenance": {
                    "run_id": first_id,
                    "plan_sha256": "tampered",
                    "git_commit": plan["git_commit"],
                    "integrity_issues": [],
                }
            }), encoding="utf-8")
            with patch(
                "evaluation.v2_campaign_runner.load_preregistered",
                return_value=(plan, "c" * 64),
            ):
                status = preflight_campaign(root, root)
                self.assertEqual(status["runs"][1]["status"], "ready")
                with self.assertRaisesRegex(ValueError, "Provenienza"):
                    execute_exactly_one(
                        root, root, run_id=next_id,
                        confirm_api=True, _runner=fake_result,
                    )
                next_claim, _ = _output_paths(root, next_id)
                self.assertFalse(next_claim.exists())

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
                        "evidence_sha256": None,
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
                self.assertIsNone(result["evidence_sha256"])
                self.assertIsNone(
                    json.loads(claim.read_text(encoding="utf-8"))[
                        "evidence_sha256_before_api"
                    ]
                )
                with self.assertRaises(FileExistsError):
                    execute_exactly_one(
                        root, root, run_id=run_id, confirm_api=True,
                        _runner=fake_result,
                    )

    def test_non_a0_missing_evidence_preclaim_fails_without_file(self):
        plan = fake_plan()
        plan["cases"][0]["ordered_variants"] = [
            "A1_V2", "A0", "A1", "A1_VERIFY", "A1_VERIFY_ST"
        ]
        plan["cases"][0]["run_ids"] = [
            f"{PROTOCOL}__cloudbed-1_q005__{v.lower()}__r01"
            for v in plan["cases"][0]["ordered_variants"]
        ]
        run_id = plan["cases"][0]["run_ids"][0]
        case = {
            "case_id": "cloudbed-1_q005", "cloudbed": "cloudbed-1",
            "task_index": "task_2",
            "start_unix": 1647747000, "end_unix": 1647748800,
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch(
                    "evaluation.v2_campaign_runner.load_preregistered",
                    return_value=(plan, "c" * 64),
                ),
                patch(
                    "evaluation.experiment_runner.carica_caso",
                    return_value=case,
                ),
                patch(
                    "evaluation.experiment_runner.prepara_esperimento",
                    return_value={
                        "caso": case, "evidence_sha256": None,
                    },
                ),
            ):
                with self.assertRaisesRegex(ValueError, "SHA delle evidenze"):
                    execute_exactly_one(
                        root, root, run_id=run_id,
                        confirm_api=True, _runner=fake_result,
                    )
                claim, output = _output_paths(root, run_id)
                self.assertFalse(claim.exists())
                self.assertFalse(output.exists())

    def test_a0_unexpected_evidence_preclaim_fails(self):
        plan = fake_plan()
        run_id = plan["cases"][0]["run_ids"][0]
        case = {
            "case_id": "cloudbed-1_q005", "cloudbed": "cloudbed-1",
            "task_index": "task_2",
            "start_unix": 1647747000, "end_unix": 1647748800,
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch(
                    "evaluation.v2_campaign_runner.load_preregistered",
                    return_value=(plan, "c" * 64),
                ),
                patch(
                    "evaluation.experiment_runner.carica_caso",
                    return_value=case,
                ),
                patch(
                    "evaluation.experiment_runner.prepara_esperimento",
                    return_value={
                        "caso": case, "evidence_sha256": "b" * 64,
                    },
                ),
            ):
                with self.assertRaisesRegex(
                    ValueError, "A0 non deve generare",
                ):
                    execute_exactly_one(
                        root, root, run_id=run_id,
                        confirm_api=True, _runner=fake_result,
                    )
                claim, output = _output_paths(root, run_id)
                self.assertFalse(claim.exists())
                self.assertFalse(output.exists())


    def test_dependency_failure_preclaim_preserves_run_ready(self):
        plan = fake_plan()
        run_id = plan["cases"][0]["run_ids"][0]
        case = {
            "case_id": "cloudbed-1_q005", "cloudbed": "cloudbed-1",
            "task_index": "task_2",
            "start_unix": 1647747000, "end_unix": 1647748800,
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with (
                patch(
                    "evaluation.v2_campaign_runner.load_preregistered",
                    return_value=(plan, "c" * 64),
                ),
                patch(
                    "evaluation.experiment_runner.carica_caso",
                    return_value=case,
                ),
                patch(
                    "evaluation.experiment_runner.prepara_esperimento",
                    return_value={"caso": case, "evidence_sha256": None},
                ),
                patch(
                    "evaluation.v2_campaign_runner._ensure_runtime_ready",
                    side_effect=RuntimeError(
                        "Dipendenza runtime mancante/incompatibile"
                    ),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "Dipendenza runtime"):
                    execute_exactly_one(
                        root, root, run_id=run_id, confirm_api=True,
                    )
                claim, output = _output_paths(root, run_id)
                self.assertFalse(claim.exists())
                self.assertFalse(output.exists())
                status = preflight_campaign(root, root)
                self.assertEqual(status["runs"][0]["status"], "ready")

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
                        "evidence_sha256": None,
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
