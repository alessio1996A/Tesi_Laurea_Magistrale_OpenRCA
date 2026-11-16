"""Test offline del cablaggio CLI V5 (solo libreria standard, nessuna API).

Il modulo esecutore reale e la verifica dello snapshot SDK vengono sostituiti
da finti: si controllano manifest, archivio separato per il pilota, rifiuto con
chiave mancante o checkout sporco, e che un secondo lotto non riesegua nulla.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation import rq2_v5_matrix_runner as mr
from evaluation import rq2_v5_run_cli as cli

NAMESPACE = "data/rq2_v5_pilot_v1"
SELECTION = ["--models", "gemini", "--harnesses", "A0",
             "--cases", "cloudbed-1_q032", "--stages", "D", "C", "K"]


class _FakeExecutor:
    calls: list = []

    def __init__(self, *, data_dir, repo_dir):
        pass

    def prepare(self, row, parents):
        return {}

    def run(self, row, prepared):
        _FakeExecutor.calls.append(row["stage"])
        return {"status": mr.STATUS_COMPLETE,
                "receipt": {"stage_id": row["stage_id"]},
                "format": {"deviation": "NONE"}, "provenance": {}}


def _fake_modules():
    executor = types.ModuleType("evaluation.rq2_v5_stage_executor")
    executor.V5StageExecutor = _FakeExecutor
    executor.D_MAX_ROUNDS, executor.PLANNER_CHECKS = 6, 2
    executor.RECURSION_LIMIT = 30
    executor.prompt_hashes = lambda: {"C_system_prompt_sha256": "c" * 64,
                                      "K_system_prompt_sha256": "d" * 64}
    factory = types.ModuleType("evaluation.rq2_model_factory")
    factory.assert_exact_runtime_snapshot = lambda: None
    return {"evaluation.rq2_v5_stage_executor": executor,
            "evaluation.rq2_model_factory": factory}


def _git_repo(path: Path) -> Path:
    path.mkdir()
    for args in (["init", "-q"], ["config", "user.email", "t@example.org"],
                 ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", str(path), *args], check=True)
    (path / "a.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "init"],
                   check=True)
    return path


class RunCliOfflineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.drive = Path(self._tmp.name) / "drive"
        self.drive.mkdir()
        self.repo = _git_repo(Path(self._tmp.name) / "repo")
        _FakeExecutor.calls = []

    def _main(self, command, *extra, env=None):
        argv = [command, "--drive-root", str(self.drive),
                "--namespace", NAMESPACE, *SELECTION, *extra]
        if command != "summary":
            argv += ["--repo-dir", str(self.repo)]
        environment = {"GOOGLE_API_KEY": "fake-key-123456"} if env is None else env
        out = io.StringIO()
        with (
            patch.dict(sys.modules, _fake_modules()),
            patch.dict(os.environ, environment, clear=True),
            contextlib.redirect_stdout(out),
        ):
            try:
                rc = cli.main(argv)
            except SystemExit as exc:
                rc = exc.code
        return rc, out.getvalue()

    def test_run_writes_manifest_and_three_records_in_separate_namespace(self):
        rc, out = self._main("run")
        self.assertEqual(rc, 0, out)
        root = self.drive / NAMESPACE
        manifest = json.loads((root / "manifest_v1.json").read_text("utf-8"))
        self.assertEqual(manifest["protocol"], mr.PROTOCOL)
        self.assertEqual(manifest["C_system_prompt_sha256"], "c" * 64)
        self.assertEqual(len(list((root / "records").glob("V5_RECORD_*"))), 3)
        self.assertEqual(_FakeExecutor.calls, ["D", "C", "K"])
        # L'archivio scientifico non e' stato toccato dal pilota.
        self.assertFalse((self.drive / mr.NAMESPACE).exists())

    def test_second_batch_matches_manifest_and_reruns_nothing(self):
        self._main("run")
        _FakeExecutor.calls = []
        rc, out = self._main("run")
        self.assertEqual(rc, 0, out)
        self.assertIn("MATCHES", out)
        self.assertEqual(_FakeExecutor.calls, [])

    def test_manifest_drift_between_batches_is_refused(self):
        self._main("run")
        path = self.drive / NAMESPACE / "manifest_v1.json"
        data = json.loads(path.read_text("utf-8"))
        data["format_policy"] = "altra_politica"
        path.write_text(json.dumps(data), encoding="utf-8")
        rc, out = self._main("run")
        self.assertNotEqual(rc, 0)
        self.assertEqual(_FakeExecutor.calls, ["D", "C", "K"])  # solo il 1o lotto

    def test_missing_key_refuses_before_any_write(self):
        rc, out = self._main("run", env={})
        self.assertEqual(rc, 2)
        self.assertFalse((self.drive / NAMESPACE).exists())
        self.assertEqual(_FakeExecutor.calls, [])

    def test_dirty_checkout_refuses_the_run(self):
        (self.repo / "a.txt").write_text("modificato", encoding="utf-8")
        rc, _ = self._main("run")
        self.assertEqual(rc, 2)
        self.assertEqual(_FakeExecutor.calls, [])

    def test_max_stages_limits_the_batch(self):
        rc, _ = self._main("run", "--max-stages", "1")
        self.assertEqual(rc, 0)
        self.assertEqual(_FakeExecutor.calls, ["D"])

    def test_summary_reads_the_namespace_without_keys(self):
        self._main("run")
        rc, out = self._main("summary", env={})
        self.assertEqual(rc, 0)
        self.assertIn("da fare: 0", out)
        self.assertIn("gemini|A0|K: RECORDED_COMPLETE=1", out)


if __name__ == "__main__":
    unittest.main()
