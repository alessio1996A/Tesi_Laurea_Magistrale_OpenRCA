"""RQ2-V2: opt-in di runtime espliciti e indipendenti, senza provider.

Non attiva il processo, non crea release e non usa API/credenziali.
Le eventuali variabili d'ambiente sono mutate soltanto all'interno
delle fixture con patch.dict e ripristinate al termine del test.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import evaluation.rq2_v2_unified_live_dispatcher as dispatch
import evaluation.rq2_v2_unified_scientific_ledger as ledger


class RQ2V2RuntimeOptInOfflineTests(unittest.TestCase):

    def test_disabled_by_default_in_clean_environment(self):
        # Il test deve funzionare anche se chi lo esegue ha env pregresse.
        with patch.dict(
            os.environ, {
                dispatch.LIVE_OPT_IN_ENV: "",
                ledger.RELEASE_WRITE_OPT_IN_ENV: "",
            },
        ):
            self.assertFalse(dispatch.runtime_live_optin())
            self.assertFalse(ledger.runtime_release_write_optin())

    def test_paid_api_requires_exact_marker(self):
        env = dispatch.LIVE_OPT_IN_ENV
        for value in ("", "true", "1", "EXPLICIT_ONE_STAGE_ONLY", " ", "yes"):
            with self.subTest(value=value), patch.dict(os.environ, {env: value}):
                self.assertFalse(dispatch.runtime_live_optin())
        with patch.dict(os.environ, {env: dispatch.LIVE_OPT_IN_EXACT}):
            self.assertTrue(dispatch.runtime_live_optin())

    def test_release_create_requires_different_exact_marker(self):
        env = ledger.RELEASE_WRITE_OPT_IN_ENV
        for value in ("", "true", "1", "EXPLICIT_CREATE_ONLY", " ", "yes"):
            with self.subTest(value=value), patch.dict(os.environ, {env: value}):
                self.assertFalse(ledger.runtime_release_write_optin())
        with patch.dict(os.environ, {env: ledger.RELEASE_WRITE_OPT_IN_EXACT}):
            self.assertTrue(ledger.runtime_release_write_optin())

    def test_only_release_opt_in_does_not_enable_provider(self):
        with patch.dict(os.environ, {
            ledger.RELEASE_WRITE_OPT_IN_ENV: ledger.RELEASE_WRITE_OPT_IN_EXACT,
            dispatch.LIVE_OPT_IN_ENV: "",
        }):
            self.assertTrue(ledger.runtime_release_write_optin())
            self.assertFalse(dispatch.runtime_live_optin())

    def test_only_provider_opt_in_does_not_enable_release(self):
        with patch.dict(os.environ, {
            dispatch.LIVE_OPT_IN_ENV: dispatch.LIVE_OPT_IN_EXACT,
            ledger.RELEASE_WRITE_OPT_IN_ENV: "",
        }):
            self.assertTrue(dispatch.runtime_live_optin())
            self.assertFalse(ledger.runtime_release_write_optin())

    def test_gate_parameters_remain_required(self):
        # Anche la patch della flag non puo' sostituire per-stage consent.
        with patch.object(dispatch, "LIVE_API_ENABLED", True):
            with self.assertRaisesRegex(
                dispatch.RQ2V2LiveDispatchBlocked, "per-stage paid approval"
            ):
                dispatch._eligibility(
                    confirm_paid_api=False,
                    approved_stage_id="",
                    approved_release_sha256="",
                    expected_commit="",
                    external_approval_reference="",
                )


if __name__ == "__main__":
    unittest.main()
