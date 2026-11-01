"""Offline safety tests for paired execution. Fake provider: NEVER API/GT."""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.paired_cohort import (
    costruisci_piano_abbinato,
    save_plan_exclusive,
)
from evaluation.paired_runner import (
    PLAN_FILENAME,
    carica_piano_congelato,
    esegui_coppia,
    preflight_paired,
)

HEAD = "a" * 40
SHA = "b" * 64


def _csv(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        w = csv.DictWriter(stream, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


class TestPairedRunner(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.data_dir = self.root / "drive"
        self.repo_dir = self.root / "repo"
        processed = self.data_dir / "data/processed"
        processed.mkdir(parents=True)

        dev = [
            {"case_id": f"cloudbed-1_q{i:03}", "split": "development"}
            for i in range(1, 7)
        ] + [
            {"case_id": f"cloudbed-2_q{i:03}", "split": "development"}
            for i in range(1, 7)
        ]
        self.rows = dev + [
            {"case_id": "cloudbed-1_q095", "split": "evaluation"},
            {"case_id": "cloudbed-2_q096", "split": "ood_holdout"},
            {"case_id": "cloudbed-1_q097", "split": "mixed_quarantine"},
        ]
        self.split = processed / "split_market_v1.csv"
        self.manifest = processed / "benchmark_inputs_market.csv"
        _csv(self.split, ["case_id", "split"], self.rows)
        _csv(
            self.manifest, ["case_id", "instruction"],
            [{"case_id": x["case_id"], "instruction": "Do RCA"}
             for x in self.rows],
        )
        self.plan = costruisci_piano_abbinato(
            self.split, self.manifest, per_cloudbed=2
        )
        self.expected_counts = self.plan["split_counts"]
        plan_dir = self.data_dir / "data/protocols"
        plan_dir.mkdir(parents=True)
        self.plan_file = save_plan_exclusive(
            self.plan, plan_dir / PLAN_FILENAME
        )
        self.patch_git = patch(
            "evaluation.paired_runner._git_sha", return_value=HEAD
        )
        self.patch_git.start()
        self.addCleanup(self.patch_git.stop)
        self.case_id = self.plan["pairs"][0]["case_id"]
        self.calls = []

    def load(self):
        return carica_piano_congelato(
            self.data_dir, expected_counts=self.expected_counts
        )

    def preflight(self):
        return preflight_paired(
            self.data_dir, repo_dir=self.repo_dir,
            expected_counts=self.expected_counts,
        )

    def prepared(self, config):
        return {
            "evidence_sha256": SHA,
            "richiesta": "Investigate using the same deterministic report",
            "caso": {
                "case_id": config.case_id,
                "start_unix": 1000,
                "end_unix": 2000,
            },
        }

    def fake_run(self, config):
        self.calls.append((config.case_id, config.variant))
        result = {
            "case_id": config.case_id,
            "variant": config.variant,
            "evidence_sha256": SHA,
            "model": config.model_name,
            "model_provider": config.model_provider,
            "max_tool_rounds": config.max_tool_rounds,
            "metrics": {"tool_rounds": 1, "llm_calls": 2},
            "prediction": None,
            "raw_response": None,
            "error": "simulated_offline",
            "tool_trajectory": [],
        }
        if config.variant == "A1_VERIFY":
            result["metrics"].update({
                "exploration_tool_rounds": 0,
                "verification_tool_rounds": 1,
            })
            result["verification"] = {"causa_verificata": False}
        return result

    def execute_pair_fixture(self, **kwargs):
        return esegui_coppia(
            self.data_dir,
            repo_dir=self.repo_dir,
            case_id=self.case_id,
            confirm_api=True,
            expected_counts=self.expected_counts,
            _prepare=self.prepared,
            _run=self.fake_run,
            **kwargs,
        )

    def test_preflight_is_completely_read_only(self):
        result = self.preflight()
        self.assertEqual(result["case_count"], 4)
        self.assertEqual(result["run_count"], 8)
        self.assertFalse(result["llm_called"])
        self.assertFalse(result["files_written"])
        self.assertFalse(result["telemetry_loaded"])
        self.assertTrue(all(
            x["status"] == "ready" for x in result["pairs"]
        ))
        self.assertFalse(
            (self.data_dir / "data/results/paired").exists()
        )

    def test_frozen_plan_sha_is_returned(self):
        plan, hash_value = self.load()
        self.assertEqual(plan, self.plan)
        self.assertEqual(len(hash_value), 64)

    def test_explicit_confirmation_required(self):
        with self.assertRaises(PermissionError):
            esegui_coppia(
                self.data_dir, repo_dir=self.repo_dir,
                case_id=self.case_id, confirm_api=False,
                _prepare=self.prepared, _run=self.fake_run,
            )
        self.assertEqual(self.calls, [])

    def test_case_not_in_frozen_cohort_rejected(self):
        with self.assertRaisesRegex(ValueError, "non appartenente"):
            esegui_coppia(
                self.data_dir, repo_dir=self.repo_dir,
                case_id="cloudbed-1_q098", confirm_api=True,
                expected_counts=self.expected_counts,
                _prepare=self.prepared, _run=self.fake_run,
            )
        self.assertEqual(self.calls, [])

    def test_complete_pair_saves_distinct_immutable_results(self):
        result = self.execute_pair_fixture()
        self.assertTrue(result["evidence_sha256_equal"])
        self.assertTrue(result["api_execution_completed"])
        self.assertFalse(result["scoring_performed"])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(
            [variant for _, variant in self.calls],
            self.plan["pairs"][0]["ordered_variants"],
        )
        self.assertEqual(len(result["results_saved"]), 2)
        for file_path in result["results_saved"]:
            doc = json.loads(Path(file_path).read_text("utf-8"))
            self.assertEqual(
                doc["paired_provenance"]["git_commit"], HEAD
            )
            self.assertEqual(
                doc["paired_provenance"]["integrity_issues"], []
            )
            self.assertEqual(
                doc["paired_provenance"]["paired_evidence_sha256"], SHA
            )
        self.assertEqual(
            self.preflight()["pairs"][0]["status"],
            "completed_never_rerun",
        )

    def test_completed_pair_never_reruns(self):
        self.execute_pair_fixture()
        count = len(self.calls)
        with self.assertRaises(FileExistsError):
            self.execute_pair_fixture()
        self.assertEqual(len(self.calls), count)

    def test_sha_mismatch_is_detected_before_api_or_claim(self):
        def wrong_prepare(config):
            result = self.prepared(config)
            if config.variant == "A1_VERIFY":
                result["evidence_sha256"] = "c" * 64
            return result

        with self.assertRaisesRegex(ValueError, "divergono"):
            esegui_coppia(
                self.data_dir, repo_dir=self.repo_dir,
                case_id=self.case_id, confirm_api=True,
                expected_counts=self.expected_counts,
                _prepare=wrong_prepare, _run=self.fake_run,
            )
        self.assertEqual(self.calls, [])
        self.assertEqual(self.preflight()["pairs"][0]["status"], "ready")

    def test_prompt_mismatch_blocks_api_before_claim(self):
        def wrong_prepare(config):
            item = self.prepared(config)
            if config.variant == "A1_VERIFY":
                item["richiesta"] = "different prompt"
            return item

        with self.assertRaisesRegex(ValueError, "Prompt utente"):
            esegui_coppia(
                self.data_dir, repo_dir=self.repo_dir,
                case_id=self.case_id, confirm_api=True,
                expected_counts=self.expected_counts,
                _prepare=wrong_prepare, _run=self.fake_run,
            )
        self.assertEqual(self.calls, [])
        self.assertEqual(self.preflight()["pairs"][0]["status"], "ready")

    def test_window_mismatch_blocks_api_before_claim(self):
        def wrong_prepare(config):
            item = self.prepared(config)
            if config.variant == "A1_VERIFY":
                item["caso"]["end_unix"] = 1950
            return item

        with self.assertRaisesRegex(ValueError, "Contesto ufficiale"):
            esegui_coppia(
                self.data_dir, repo_dir=self.repo_dir,
                case_id=self.case_id, confirm_api=True,
                expected_counts=self.expected_counts,
                _prepare=wrong_prepare, _run=self.fake_run,
            )
        self.assertEqual(self.calls, [])
        self.assertEqual(self.preflight()["pairs"][0]["status"], "ready")

    def test_interrupted_claim_blocks_api_restart(self):
        result = self.execute_pair_fixture()
        Path(result["results_saved"][1]).unlink()
        self.assertEqual(
            self.preflight()["pairs"][0]["status"],
            "interrupted_or_partial_manual_review",
        )
        count = len(self.calls)
        with self.assertRaises(FileExistsError):
            self.execute_pair_fixture()
        self.assertEqual(len(self.calls), count)

    def test_exception_after_first_billed_run_blocks_repeat(self):
        def broken_run(config):
            self.calls.append(config.variant)
            raise RuntimeError("Simulated provider/network failure")

        with self.assertRaisesRegex(RuntimeError, "Simulated"):
            esegui_coppia(
                self.data_dir, repo_dir=self.repo_dir,
                case_id=self.case_id, confirm_api=True,
                expected_counts=self.expected_counts,
                _prepare=self.prepared, _run=broken_run,
            )
        self.assertEqual(self.preflight()["pairs"][0]["status"],
                         "interrupted_or_partial_manual_review")
        with self.assertRaises(FileExistsError):
            self.execute_pair_fixture()

    def test_integrity_fault_preserves_first_run_and_stops_second(self):
        def invalid_run(config):
            result = self.fake_run(config)
            result["metrics"]["tool_rounds"] = 999
            return result

        with self.assertRaisesRegex(RuntimeError, "Integrita"):
            esegui_coppia(
                self.data_dir, repo_dir=self.repo_dir,
                case_id=self.case_id, confirm_api=True,
                expected_counts=self.expected_counts,
                _prepare=self.prepared, _run=invalid_run,
            )
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(
            self.preflight()["pairs"][0]["status"],
            "interrupted_or_partial_manual_review",
        )

    def test_modified_frozen_plan_rejected(self):
        bad = json.loads(self.plan_file.read_text("utf-8"))
        bad["model_name"] = "unexpected"
        self.plan_file.write_text(json.dumps(bad), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "non riproducibile"):
            self.load()

    def test_modified_split_rejected(self):
        modified = [dict(x) for x in self.rows]
        modified[0]["split"] = "evaluation"
        _csv(self.split, ["case_id", "split"], modified)
        with self.assertRaisesRegex(ValueError, "non riproducibile"):
            self.load()

    def test_manifest_change_rejected_even_if_ids_same(self):
        _csv(
            self.manifest, ["case_id", "instruction"],
            [{"case_id": x["case_id"], "instruction": "Changed"}
             for x in self.rows],
        )
        with self.assertRaisesRegex(ValueError, "non riproducibile"):
            self.load()

    def test_code_sha_drift_detected_against_saved_run(self):
        self.execute_pair_fixture()
        with patch(
            "evaluation.paired_runner._git_sha",
            return_value="c" * 40,
        ):
            with self.assertRaisesRegex(ValueError, "Versione codice"):
                self.preflight()

    def test_result_without_claim_is_flagged(self):
        pair = self.plan["pairs"][0]
        base = self.data_dir / "data/results/paired" / self.plan["protocol"]
        base.mkdir(parents=True)
        out = base / f"{pair['run_ids'][0]}.json"
        out.write_text(json.dumps({
            "variant": pair["ordered_variants"][0],
            "case_id": self.case_id,
            "paired_provenance": {
                "git_commit": HEAD,
                "frozen_plan_sha256": self.load()[1],
            },
        }), encoding="utf-8")
        self.assertEqual(
            self.preflight()["pairs"][0]["status"],
            "inconsistent_output_without_pair_claim",
        )

    def test_other_cases_are_not_touched(self):
        self.execute_pair_fixture()
        rows = self.preflight()["pairs"]
        self.assertEqual(rows[0]["status"], "completed_never_rerun")
        self.assertTrue(all(x["status"] == "ready" for x in rows[1:]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
