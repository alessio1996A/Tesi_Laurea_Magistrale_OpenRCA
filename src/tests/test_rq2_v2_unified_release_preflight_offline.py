"""G4A: source-binding RQ2 unificata, tutto offline con source fake.

I due report di sorgente possono essere simulati; in test separati si
controllano i path locali di fixture. Nessuna chiamata provider/Market/GT,
nessuna release scientifica o autorizzazione API.
"""
from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation import rq2_v2_unified_release_preflight as gate
from evaluation.rq2_probe_adapter import CAUSE_SYSTEM, RULE_SYSTEM
from evaluation.rq2_v2_unified_discovery_plan import (
    build_offline_discovery_plan, EXPECTED_SPLIT_SHA256,
    EXPECTED_MANIFEST_SHA256,
)


FAKE_SOURCE = b"synthetic-only source; never real RQ1 code\n"
FAKE_SHA = hashlib.sha256(FAKE_SOURCE).hexdigest()


def verified_gt_free():
    p = build_offline_discovery_plan()
    return {
        "split_manifest_source_verified": True,
        "split_sha256": EXPECTED_SPLIT_SHA256,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "base_plan_preview_sha256": p["preview_sha256"],
        "logical_stages": 180,
        "can_call_model_api": False,
        "can_run_ood_test": False,
        "ground_truth_read": False,
    }


def verified_rq1():
    p = build_offline_discovery_plan()
    return {
        "rq1_source_blob_sha1_match": True,
        "rq1_D_output_contract_mode_verified": "v2_enforce",
        "rq2_scientific_protocol_frozen": False,
        "rq2_discovery_api_enabled": False,
        "rq2_test_unlocked": False,
        "models_proposed": p["model_ids"],
        "C_system_prompt_sha256": hashlib.sha256(
            CAUSE_SYSTEM.encode("utf-8")
        ).hexdigest(),
        "K_system_prompt_sha256": hashlib.sha256(
            RULE_SYSTEM.encode("utf-8")
        ).hexdigest(),
        "rq1_source_sha256": {
            "evaluation/experiment_runner.py": FAKE_SHA,
            "agent/model_factory.py": FAKE_SHA,
        },
        "probe_adapter_version": gate.ADAPTER_VERSION,
    }


class UnifiedReleaseSourcePreviewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def _preview(self, *, gt=None, rq1=None, source=FAKE_SOURCE):
        with (
            patch.object(
                gate, "preview_gt_free_sources",
                return_value=verified_gt_free() if gt is None else gt,
            ) as source_check,
            patch.object(
                gate, "preview_protocol_identity",
                return_value=verified_rq1() if rq1 is None else rq1,
            ) as rq1_check,
            patch.object(gate, "_source_bytes", return_value=source) as src,
        ):
            result = gate.preview_unified_source_bound(
                data_dir=self.root, src_root=self.root,
            )
        source_check.assert_called_once_with(self.root)
        rq1_check.assert_called_once_with(src_root=self.root)
        self.assertEqual(src.call_count, len(gate.SOURCE_PATHS))
        return result

    def test_five_harness_three_llm_four_cases_exact(self):
        report = self._preview()
        self.assertEqual(report["logical_stages"], 180)
        self.assertEqual(report["stage_counts"], {"D": 60, "C": 60, "K": 60})
        self.assertEqual(report["ood_test_cases_locked"], 11)
        self.assertEqual(len(report["harnesses"]), 5)
        self.assertEqual(len(report["model_ids"]), 3)
        self.assertEqual(len(report["discovery_cases"]), 4)
        self.assertEqual(report["d_max_tool_rounds"], 6)
        self.assertEqual(report["planning_checks_reserved"], 2)

    def test_all_authority_is_blocked_even_after_success(self):
        report = self._preview()
        for field in (
            "can_execute_api", "can_run_ood_test",
            "scientific_release_frozen", "approved_api_budget_exists",
            "unified_production_ledger_implemented",
            "unified_provider_dispatcher_implemented",
            "source_commit_pinned_for_release",
            "ground_truth_read", "data_files_written",
        ):
            self.assertIs(report[field], False, field)
        self.assertEqual(report["model_requests_sent"], 0)
        self.assertEqual(report["claims_written"], 0)

    def test_source_manifest_hashes_and_prompts_recorded(self):
        report = self._preview()
        self.assertEqual(report["split_sha256"], EXPECTED_SPLIT_SHA256)
        self.assertEqual(report["manifest_sha256"], EXPECTED_MANIFEST_SHA256)
        self.assertEqual(report["source_file_count"], len(gate.SOURCE_PATHS))
        self.assertEqual(
            set(report["source_files_sha256"]), set(gate.SOURCE_PATHS)
        )
        self.assertTrue(all(
            x == FAKE_SHA for x in report["source_files_sha256"].values()
        ))
        self.assertEqual(report["C_system_prompt_sha256"],
                         verified_rq1()["C_system_prompt_sha256"])
        self.assertEqual(report["K_system_prompt_sha256"],
                         verified_rq1()["K_system_prompt_sha256"])

    def test_same_inputs_produce_same_preview_and_no_files(self):
        before = list(self.root.iterdir())
        self.assertEqual(self._preview(), self._preview())
        self.assertEqual(list(self.root.iterdir()), before)

    def test_missing_data_source_verification_fails_closed(self):
        bad = verified_gt_free()
        bad["split_manifest_source_verified"] = False
        with self.assertRaisesRegex(
            gate.UnifiedRQ2SourcePreflightError, "GT-free"
        ), patch.object(gate, "preview_gt_free_sources", return_value=bad):
            gate.preview_unified_source_bound(
                data_dir=self.root, src_root=self.root,
            )

    def test_different_plan_sha_is_refused(self):
        bad = verified_gt_free()
        bad["base_plan_preview_sha256"] = "f" * 64
        with self.assertRaisesRegex(
            gate.UnifiedRQ2SourcePreflightError, "GT-free"
        ), patch.object(gate, "preview_gt_free_sources", return_value=bad):
            gate.preview_unified_source_bound(
                data_dir=self.root, src_root=self.root,
            )

    def test_corrupt_manifest_hash_is_refused(self):
        bad = verified_gt_free()
        bad["manifest_sha256"] = "f" * 64
        with self.assertRaisesRegex(
            gate.UnifiedRQ2SourcePreflightError, "GT-free"
        ), patch.object(gate, "preview_gt_free_sources", return_value=bad):
            gate.preview_unified_source_bound(
                data_dir=self.root, src_root=self.root,
            )

    def test_unlocking_test_is_refused_in_source_gate(self):
        bad = verified_gt_free()
        bad["can_run_ood_test"] = True
        with self.assertRaisesRegex(
            gate.UnifiedRQ2SourcePreflightError, "GT-free"
        ), patch.object(gate, "preview_gt_free_sources", return_value=bad):
            gate.preview_unified_source_bound(
                data_dir=self.root, src_root=self.root,
            )

    def test_source_gate_drift_on_prompt_sha_fails_closed(self):
        bad = verified_rq1()
        bad["C_system_prompt_sha256"] = "0" * 64
        with self.assertRaisesRegex(
            gate.UnifiedRQ2SourcePreflightError, "parity"
        ):
            self._preview(rq1=bad)

    def test_source_gate_model_drift_fails_closed(self):
        bad = verified_rq1()
        bad["models_proposed"] = {"gemini": "unrecognized-model"}
        with self.assertRaisesRegex(
            gate.UnifiedRQ2SourcePreflightError, "parity"
        ):
            self._preview(rq1=bad)

    def test_source_gate_rq1_runner_sha_drift_fails_closed(self):
        bad = verified_rq1()
        bad["rq1_source_sha256"]["evaluation/experiment_runner.py"] = "a" * 64
        with self.assertRaisesRegex(
            gate.UnifiedRQ2SourcePreflightError, "parity"
        ):
            self._preview(rq1=bad)

    def test_source_gate_wrong_d_output_mode_fails_closed(self):
        bad = verified_rq1()
        bad["rq1_D_output_contract_mode_verified"] = "legacy"
        with self.assertRaisesRegex(
            gate.UnifiedRQ2SourcePreflightError, "parity"
        ):
            self._preview(rq1=bad)

    def test_rq1_source_audit_failure_not_swallowed(self):
        with (
            patch.object(gate, "preview_gt_free_sources",
                         return_value=verified_gt_free()),
            patch.object(gate, "preview_protocol_identity",
                         side_effect=gate.ProtocolIdentityError("source drift")),
        ):
            with self.assertRaisesRegex(
                gate.UnifiedRQ2SourcePreflightError,
                "Frozen RQ1 source",
            ):
                gate.preview_unified_source_bound(
                    data_dir=self.root, src_root=self.root,
                )

    def test_missing_root_is_refused_before_source_reads(self):
        with self.assertRaises(gate.UnifiedRQ2SourcePreflightError):
            gate.preview_unified_source_bound(
                data_dir=self.root / "missing", src_root=self.root,
            )

    def test_relative_source_root_is_refused(self):
        with self.assertRaises(gate.UnifiedRQ2SourcePreflightError):
            gate.preview_unified_source_bound(
                data_dir=self.root, src_root=Path("src"),
            )

    def test_actual_source_reader_rejects_absent_file(self):
        with self.assertRaisesRegex(
            gate.UnifiedRQ2SourcePreflightError, "Missing"
        ):
            gate._source_bytes(self.root, "agent/missing.py")

    def test_actual_source_reader_normalizes_windows_checkout(self):
        (self.root / "agent").mkdir()
        (self.root / "agent/sample.py").write_bytes(b"line1\r\nline2\r\n")
        self.assertEqual(
            gate._source_bytes(self.root, "agent/sample.py"),
            b"line1\nline2\n",
        )

    def test_synthetic_journal_not_part_of_real_release_source(self):
        self.assertNotIn(
            "evaluation/rq2_v2_unified_synthetic_journal.py",
            gate.SOURCE_PATHS,
        )
        self.assertIn("agent/verify_graph.py", gate.SOURCE_PATHS)
        self.assertIn("agent/rq2_v2_graph_engine.py", gate.SOURCE_PATHS)
        self.assertIn("evaluation/experiment_runner.py", gate.SOURCE_PATHS)


if __name__ == "__main__":
    unittest.main()
