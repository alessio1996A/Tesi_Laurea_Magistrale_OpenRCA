"""G4L: writer scientifico create-only, SOLO fixture offline.

NESSUNA release reale, API, credenziale o autorizzazione dell'utente.
La flag di test viene abilitata SOLO dentro TemporaryDirectory con
preflight, runtime e release completamente sintetici. Il codice di
produzione rimane HARD-DISABLED.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluation.rq2_v2_unified_scientific_ledger as subject
from evaluation.rq2_provider_policy_source_audit import EXPECTED_COLAB_VERSIONS
from evaluation.rq2_v2_unified_release_blueprint import build_unified_release_blueprint
from evaluation.rq2_v2_unified_scientific_release_contract import (
    canonical_release, release_digest,
)
from test_rq2_v2_unified_scientific_release_contract_offline import (
    FAKE_COMMIT, source_fixture, release_fixture,
)

# Non e' consenso economico reale: solo una stringa di fixture.
TEST_ONLY_APPROVAL = "OFFLINE_FIXTURE_NO_EXTERNAL_AUTHORITY"


class ScientificReleaseWriterOfflineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="rq2_v2_g4l_mock_")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.data = self.base / "data_root"
        self.repo = self.base / "fake_checkout"
        self.data.mkdir()
        (self.data / "data").mkdir()
        (self.repo / "src").mkdir(parents=True)

        self.source = source_fixture()
        blueprint = build_unified_release_blueprint(source_preview=self.source)
        self.release = release_fixture(self.source, blueprint)
        self.release["runtime_versions"] = dict(EXPECTED_COLAB_VERSIONS)
        self.release["approval_reference"] = TEST_ONLY_APPROVAL
        self.sha = release_digest(self.release)
        self.dest = self.data / subject.RELEASE_FILE
        self.args = {
            "data_dir": self.data,
            "repo_dir": self.repo,
            "expected_commit": FAKE_COMMIT,
            "approved_release_sha256": self.sha,
            "external_approval_reference": TEST_ONLY_APPROVAL,
            "release": self.release,
        }

    @contextmanager
    def fake_only_context(self):
        gate = {
            "status": "LEDGER_NAMESPACE_PREFLIGHT_PASS_BUT_NO_RELEASE",
            "source_commit": FAKE_COMMIT,
            "new_namespace_absent": True,
            "can_execute_api": False,
            "can_create_scientific_claim": False,
            "can_run_ood_test": False,
        }
        with (
            patch.object(subject, "SCIENTIFIC_RELEASE_WRITE_ENABLED", True),
            patch.object(
                subject, "preview_scientific_ledger_gate", return_value=gate,
            ),
            patch.object(
                subject, "preview_unified_source_bound",
                return_value=self.source,
            ),
            patch(
                "importlib.metadata.version",
                side_effect=lambda name: EXPECTED_COLAB_VERSIONS[name],
            ),
            patch(
                "evaluation.rq2_model_factory.assert_exact_runtime_snapshot",
                return_value=None,
            ),
        ):
            yield

    def test_default_hard_disabled_before_any_preflight_or_write(self):
        self.assertIs(subject.SCIENTIFIC_RELEASE_WRITE_ENABLED, False)
        with (
            patch.object(subject, "preview_scientific_ledger_gate") as preflight,
            patch.object(subject, "_write_once") as writer,
            self.assertRaisesRegex(
                subject.UnifiedScientificLedgerBlocked, "HARD-DISABLED",
            ),
        ):
            subject.create_authorized_scientific_release_once(**self.args)
        preflight.assert_not_called()
        writer.assert_not_called()
        self.assertFalse(self.dest.exists())

    def test_synthetic_ref_rejected_even_in_test_enabled_mode(self):
        bad = dict(self.args)
        bad["external_approval_reference"] = "SYNTHETIC_APPROVAL_NOT_REAL"
        with self.fake_only_context(), self.assertRaises(
            subject.UnifiedScientificLedgerBlocked,
        ):
            subject.create_authorized_scientific_release_once(**bad)
        self.assertFalse(self.dest.exists())

    def test_external_ref_mismatch_fails_without_write(self):
        bad = dict(self.args)
        bad["external_approval_reference"] = "ANOTHER_OFFLINE_REFERENCE"
        with self.fake_only_context(), self.assertRaises(
            subject.UnifiedScientificLedgerBlocked,
        ):
            subject.create_authorized_scientific_release_once(**bad)
        self.assertFalse(self.dest.exists())

    def test_fail_closed_before_write_if_runtime_not_pinned(self):
        altered = copy.deepcopy(self.release)
        altered["runtime_versions"]["anthropic"] = "99.99.99"
        bad = {**self.args, "release": altered,
               "approved_release_sha256": release_digest(altered)}
        with self.fake_only_context(), self.assertRaisesRegex(
            subject.UnifiedScientificLedgerBlocked, "SDK versions",
        ):
            subject.create_authorized_scientific_release_once(**bad)
        self.assertFalse(self.dest.exists())

    def test_release_digest_mismatch_fails_before_write(self):
        bad = {**self.args, "approved_release_sha256": "0" * 64}
        with self.fake_only_context(), self.assertRaises(Exception):
            subject.create_authorized_scientific_release_once(**bad)
        self.assertFalse(self.dest.exists())

    def test_unlock_ood_rejected_before_write(self):
        altered = copy.deepcopy(self.release)
        altered["ood_test_locked"] = False
        bad = {**self.args, "release": altered,
               "approved_release_sha256": release_digest(altered)}
        with self.fake_only_context(), self.assertRaises(Exception):
            subject.create_authorized_scientific_release_once(**bad)
        self.assertFalse(self.dest.exists())

    def test_create_only_mock_release_once_with_canonical_readback(self):
        with self.fake_only_context():
            report = subject.create_authorized_scientific_release_once(
                **self.args,
            )
            self.assertEqual(
                report["status"], "SCIENTIFIC_RELEASE_CREATED_NO_API_NO_CLAIM",
            )
            self.assertEqual(report["release_sha256"], self.sha)
            self.assertFalse(report["can_execute_api"])
            self.assertFalse(report["can_run_ood_test"])
            self.assertEqual(report["provider_requests_sent"], 0)
            self.assertEqual(report["scientific_claims_written"], 0)
            self.assertEqual(self.dest.read_bytes(), canonical_release(self.release))
            self.assertEqual(subject._read(self.dest), self.release)
            self.assertTrue((self.dest.parent / "claims").is_dir())
            self.assertTrue((self.dest.parent / "records").is_dir())
            self.assertFalse(list((self.dest.parent / "claims").iterdir()))
            self.assertFalse(list((self.dest.parent / "records").iterdir()))
        # Terminato il mock: il dispatcher live e il writer restano spenti.
        import evaluation.rq2_v2_unified_live_dispatcher as dispatch
        self.assertIs(dispatch.LIVE_API_ENABLED, False)
        self.assertIs(subject.SCIENTIFIC_RELEASE_WRITE_ENABLED, False)

    def test_duplicate_creation_never_overwrites_mock_release(self):
        with self.fake_only_context():
            subject.create_authorized_scientific_release_once(**self.args)
            before = self.dest.read_bytes()
            with self.assertRaises(subject.UnifiedScientificLedgerBlocked):
                subject.create_authorized_scientific_release_once(**self.args)
        self.assertEqual(self.dest.read_bytes(), before)

    def test_preflight_rejects_occupied_namespace_before_write(self):
        self.dest.parent.mkdir(parents=True)
        with self.fake_only_context(), self.assertRaises(
            subject.UnifiedScientificLedgerBlocked,
        ):
            subject.create_authorized_scientific_release_once(**self.args)
        self.assertFalse(self.dest.exists())


if __name__ == "__main__":
    unittest.main()
