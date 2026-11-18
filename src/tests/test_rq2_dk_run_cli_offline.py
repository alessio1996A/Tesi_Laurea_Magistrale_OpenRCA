"""Test offline della riga di comando dell'ablazione D->K (nessuna API, nessuna chiave)."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from evaluation import rq2_dk_ablation as dk
from evaluation import rq2_dk_run_cli as cli
from evaluation import rq2_v5_matrix_runner as mr
from test_rq2_dk_ablation_offline import _executor, FakeCall, _write_source


class DKCliOfflineTests(unittest.TestCase):
    def test_manifest_is_create_only_and_invariants_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            plan, _ = dk.build_dk_plan()
            manifest = {k: "x" for k in cli.INVARIANTS}
            self.assertEqual(cli.ensure_manifest(root, manifest), "CREATED")
            self.assertEqual(cli.ensure_manifest(root, manifest), "MATCHES")
            with self.assertRaises(SystemExit):
                cli.ensure_manifest(root, {**manifest, "protocol": "altro"})

    def test_invariants_include_the_prompt_hash_and_source_namespace(self):
        self.assertIn("K_no_cause_system_prompt_sha256", cli.INVARIANTS)
        self.assertIn("source_namespace", cli.INVARIANTS)

    def test_new_namespace_differs_from_the_frozen_one(self):
        self.assertNotEqual(dk.NAMESPACE, dk.SOURCE_NAMESPACE)

    def test_summary_and_compare_read_only_and_print(self):
        with tempfile.TemporaryDirectory() as tmp:
            drive = Path(tmp)
            _, rows = dk.build_dk_plan()
            rows = rows[:2]
            _write_source(drive / dk.SOURCE_NAMESPACE, rows)
            store = mr.StageStore(drive / dk.NAMESPACE)
            dk.run_dk_matrix(
                rows, source=dk.SourceDRecords(drive / dk.SOURCE_NAMESPACE),
                store=store, executor=_executor(FakeCall()),
                log=lambda *_: None)
            for command in ("summary", "compare"):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    code = cli.main([command, "--drive-root", str(drive),
                                     "--models", "gemini", "--harnesses", "A0"])
                self.assertEqual(code, 0)
                self.assertTrue(out.getvalue().strip())

    def test_check_and_run_require_repo_dir(self):
        for command in ("check", "run"):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = cli.main([command, "--drive-root", "x"])
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
