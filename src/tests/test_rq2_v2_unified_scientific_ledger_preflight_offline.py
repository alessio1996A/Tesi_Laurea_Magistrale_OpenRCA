"""G4D: solo guardia scientifico/namespace, con sorgenti MOCKATE.

Non viene generato nessun claim, nessuna release, nessun modello reale.
La preview GT-free e i report Git dei test sono esclusivamente fixture,
non sostituiscono l'audit su Colab dei due CSV originali.
"""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import evaluation.rq2_v2_unified_scientific_ledger_preflight as gate


COMMIT = "a" * 40
SHA = "1" * 64


def valid_source() -> dict:
    return {
        "plan_preview_sha256": SHA,
        "source_files_sha256": {"evaluation/experiment_runner.py": SHA},
        "split_sha256": "2" * 64,
        "manifest_sha256": "3" * 64,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "scientific_release_frozen": False,
        "ground_truth_read": False,
        "gt_free_source_verified": True,
    }


def valid_blueprint() -> dict:
    return {
        "status": "DRAFT_ALL_EXECUTION_BLOCKED_NO_API",
        "logical_stage_count": 180,
        "can_execute_api": False,
        "can_write_scientific_claims": False,
        "can_run_ood_test": False,
        "scientific_release_frozen": False,
        "blueprint_sha256": "4" * 64,
        "source_plan_sha256": SHA,
        "max_graph_invocations_if_all_stages_reached_candidate": 492,
    }


class UnifiedLedgerNamespaceGateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="rq2_v2_ledger_g4d_")
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "repo"
        self.data = Path(tmp.name) / "data"
        self.repo.mkdir()
        self.data.mkdir()
        (self.repo / ".git").mkdir()
        (self.repo / "src").mkdir()

    def _preview(self, *, git_head=COMMIT, git_status="",
                 source=None, blueprint=None, expected=COMMIT):
        source = valid_source() if source is None else source
        blueprint = valid_blueprint() if blueprint is None else blueprint

        def fake_git(args, **kwargs):
            self.assertEqual(args[:3], ["git", "-C", str(self.repo)])
            if args[3:] == ["rev-parse", "HEAD"]:
                return SimpleNamespace(stdout=git_head + "\n")
            if args[3:] == ["status", "--porcelain", "--untracked-files=normal"]:
                return SimpleNamespace(stdout=git_status)
            self.fail("Unknown git command")

        with (
            patch.object(gate.subprocess, "run", side_effect=fake_git) as git,
            patch.object(
                gate, "preview_unified_source_bound", return_value=source,
            ) as preflight,
            patch.object(
                gate, "build_unified_release_blueprint",
                return_value=blueprint,
            ) as planner,
        ):
            result = gate.preview_scientific_ledger_gate(
                data_dir=self.data, repo_dir=self.repo,
                expected_commit=expected,
            )
            self.assertEqual(git.call_count, 2)
            preflight.assert_called_once_with(
                data_dir=self.data, src_root=self.repo / "src",
            )
            planner.assert_called_once_with(source_preview=source)
        return result

    def test_valid_reports_and_commit_yield_blocked_readonly_preview(self):
        report = self._preview()
        self.assertEqual(report["status"],
                         "LEDGER_NAMESPACE_PREFLIGHT_PASS_BUT_NO_RELEASE")
        self.assertEqual(report["source_commit"], COMMIT)
        self.assertEqual(report["logical_stages"], 180)
        self.assertEqual(report["logical_model_invocation_bound_candidate"], 492)
        self.assertEqual(report["ood_test_cases_locked"], 11)
        self.assertTrue(report["new_namespace_absent"])
        self.assertTrue(report["source_verified"])

    def test_authorization_is_always_false(self):
        report = self._preview()
        for key in (
            "scientific_release_signed", "api_budget_approved",
            "production_ledger_implemented", "production_dispatcher_implemented",
            "can_create_scientific_claim", "can_execute_api",
            "can_run_ood_test", "historical_paths_touched", "files_written",
        ):
            self.assertIs(report[key], False, key)
        self.assertEqual(report["model_requests_sent"], 0)

    def test_draft_does_not_create_file_or_data_directory(self):
        before = sorted(str(x.relative_to(self.data)) for x in self.data.rglob("*"))
        self._preview()
        after = sorted(str(x.relative_to(self.data)) for x in self.data.rglob("*"))
        self.assertEqual(after, before)
        self.assertFalse((self.data / gate.NAMESPACE).exists())

    def test_git_must_match_external_pin(self):
        with self.assertRaisesRegex(
            gate.UnifiedScientificLedgerBlocked, "mismatch",
        ):
            self._preview(git_head="b" * 40)

    def test_git_dirty_fails_before_data_checks(self):
        with self.assertRaisesRegex(
            gate.UnifiedScientificLedgerBlocked, "dirty",
        ):
            self._preview(git_status=" M src/agent/graph_engine.py\n")

    def test_invalid_or_missing_external_pin_fails_before_any_git_call(self):
        for candidate in (None, "", "a" * 39, "A" * 40):
            with self.subTest(candidate=candidate):
                with patch.object(gate.subprocess, "run") as git:
                    with self.assertRaises(gate.UnifiedScientificLedgerBlocked):
                        gate.preview_scientific_ledger_gate(
                            data_dir=self.data, repo_dir=self.repo,
                            expected_commit=candidate,
                        )
                    git.assert_not_called()

    def test_missing_git_checkout_is_rejected(self):
        (self.repo / ".git").rmdir()
        with self.assertRaisesRegex(
            gate.UnifiedScientificLedgerBlocked, "Git checkout",
        ):
            self._preview()

    def test_scientific_namespace_already_occupied_is_rejected(self):
        target = self.data / gate.NAMESPACE
        target.mkdir(parents=True)
        (target / "existing_claim.json").write_text("do not overwrite")
        with self.assertRaisesRegex(
            gate.UnifiedScientificLedgerBlocked, "occupied",
        ):
            self._preview()
        self.assertTrue((target / "existing_claim.json").is_file())

    def test_scientific_namespace_symlink_is_rejected(self):
        link = self.data / gate.NAMESPACE
        link.parent.mkdir(parents=True)
        try:
            link.symlink_to(self.repo, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Windows symlink privilege unavailable")
        with self.assertRaisesRegex(
            gate.UnifiedScientificLedgerBlocked, "occupied",
        ):
            self._preview()

    def test_historical_symlink_is_rejected(self):
        path = self.data / "data/rq2"
        path.parent.mkdir(parents=True)
        try:
            path.symlink_to(self.repo, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Windows symlink privilege unavailable")
        with self.assertRaisesRegex(
            gate.UnifiedScientificLedgerBlocked, "Symlink",
        ):
            self._preview()

    def test_unlocking_provider_in_source_report_is_refused(self):
        bad = valid_source()
        bad["can_execute_api"] = True
        with self.assertRaisesRegex(
            gate.UnifiedScientificLedgerBlocked, "mismatch",
        ):
            self._preview(source=bad)

    def test_ground_truth_leak_flag_is_rejected(self):
        bad = valid_source()
        bad["ground_truth_read"] = True
        with self.assertRaises(gate.UnifiedScientificLedgerBlocked):
            self._preview(source=bad)

    def test_unlocking_ood_in_blueprint_is_refused(self):
        bad = valid_blueprint()
        bad["can_run_ood_test"] = True
        with self.assertRaises(gate.UnifiedScientificLedgerBlocked):
            self._preview(blueprint=bad)

    def test_blueprint_hash_mismatch_is_rejected(self):
        bad = valid_blueprint()
        bad["source_plan_sha256"] = "f" * 64
        with self.assertRaises(gate.UnifiedScientificLedgerBlocked):
            self._preview(blueprint=bad)

    def test_blueprint_missing_digest_is_rejected(self):
        bad = valid_blueprint()
        bad.pop("blueprint_sha256")
        with self.assertRaises(gate.UnifiedScientificLedgerBlocked):
            self._preview(blueprint=bad)

    def test_invalid_data_root_is_rejected(self):
        with self.assertRaises(gate.UnifiedScientificLedgerBlocked):
            gate.preview_scientific_ledger_gate(
                data_dir=self.data / "nonexistent",
                repo_dir=self.repo, expected_commit=COMMIT,
            )

    def test_relative_repo_root_is_rejected(self):
        with self.assertRaises(gate.UnifiedScientificLedgerBlocked):
            gate.preview_scientific_ledger_gate(
                data_dir=self.data, repo_dir=Path("repo"),
                expected_commit=COMMIT,
            )

    def test_git_error_is_fail_closed(self):
        with patch.object(
            gate.subprocess, "run", side_effect=OSError("git unavailable"),
        ):
            with self.assertRaisesRegex(
                gate.UnifiedScientificLedgerBlocked, "cannot be proven",
            ):
                gate.preview_scientific_ledger_gate(
                    data_dir=self.data, repo_dir=self.repo,
                    expected_commit=COMMIT,
                )

    def test_deterministic_preview(self):
        self.assertEqual(self._preview(), self._preview())


if __name__ == "__main__":
    unittest.main()
