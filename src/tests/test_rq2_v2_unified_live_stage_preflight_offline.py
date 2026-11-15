"""G4H: stage scientifico source-bound, READ-ONLY e NO API.

Manifest, release e approvazione sono FAKE su TemporaryDirectory.
Si esercita davvero il ledger G4F, la costruzione dei package C/K e
la lettura CSV stdlib, ma la verifica SHA reale di split/manifest è
sostituita con una fixture nel test. Non certifica file Drive reali.
"""
from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluation.rq2_v2_unified_scientific_ledger as ledger_code
from evaluation.rq2_v2_unified_scientific_release_contract import (
    canonical_release, release_digest,
)
from evaluation.rq2_v2_unified_release_blueprint import (
    build_unified_release_blueprint,
)
from evaluation.rq2_v2_unified_discovery_plan import DISCOVERY, TEST
from evaluation.rq2_probe_adapter import CAUSE_SYSTEM, RULE_SYSTEM
from evaluation.rq2_v2_unified_live_stage_preflight import (
    UnifiedStagePreviewBlocked, preview_one_unified_stage,
    _source_instruction,
)
from test_rq2_v2_unified_scientific_release_contract_offline import (
    FAKE_COMMIT, release_fixture, source_fixture,
)
from test_rq2_v2_unified_scientific_ledger_offline import (
    meter, sid,
)
from test_rq2_v2_unified_synthetic_journal import (
    fake_run, cause, rule, model_id,
)

CSV_HEADER = [
    "case_id", "instruction", "task_index", "cloudbed", "start_unix",
    "end_unix", "query_index",
]
FAKE_INSTRUCTION = "Synthetic GT-free incident instruction, no real telemetry."


class UnifiedStageSourcePreviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(
            prefix="rq2_v2_unified_g4h_stage_fake_"
        )
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "synthetic_data"
        self.repo = self.root / "synthetic_repo"
        self.data.mkdir()
        (self.repo / "src").mkdir(parents=True)
        source = source_fixture()
        # Il fake release deve vincolare i prompt REALMENTE usati dagli
        # adapter C/K, non l'hash fittizio dei file sorgente.
        source["C_system_prompt_sha256"] = hashlib.sha256(
            CAUSE_SYSTEM.encode("utf-8")
        ).hexdigest()
        source["K_system_prompt_sha256"] = hashlib.sha256(
            RULE_SYSTEM.encode("utf-8")
        ).hexdigest()
        blueprint = build_unified_release_blueprint(source_preview=source)
        release = release_fixture(source, blueprint)
        self.sha = release_digest(release)
        release_path = self.data / ledger_code.RELEASE_FILE
        release_path.parent.mkdir(parents=True)
        release_path.write_bytes(canonical_release(release))
        p1 = patch.object(
            ledger_code, "_repository_commit", return_value=(FAKE_COMMIT, ""),
        )
        p2 = patch.object(
            ledger_code, "preview_unified_source_bound", return_value=source,
        )
        p1.start()
        p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)
        self.csv_path = self.data / "data/processed/benchmark_inputs_market.csv"
        self.csv_path.parent.mkdir(parents=True)
        self.write_manifest()
        self.journal = ledger_code.UnifiedScientificLedger(
            data_dir=self.data, repo_dir=self.repo,
            expected_commit=FAKE_COMMIT, approved_release_sha256=self.sha,
        )

    def write_manifest(self, *, rows=None, header=None):
        if rows is None:
            rows = [[
                DISCOVERY[0], FAKE_INSTRUCTION, "1", "cloudbed-1",
                1760000000, 1760000600, 32,
            ]]
        with self.csv_path.open("w", newline="", encoding="utf-8") as out:
            w = csv.writer(out)
            w.writerow(CSV_HEADER if header is None else header)
            w.writerows(rows)

    def preview(self, *, stage="D", model="gemini", harness="A0",
                case=None):
        return preview_one_unified_stage(
            data_dir=self.data, repo_dir=self.repo,
            stage_id=sid(model, harness, stage, case=case),
            expected_commit=FAKE_COMMIT, approved_release_sha256=self.sha,
        )

    def save_d(self, *, status="RECORDED_COMPLETE", run=None):
        stage_id = sid()
        self.journal.claim_stage(
            stage_id=stage_id, model_id=model_id("gemini"),
        )
        self.journal.record_stage(
            stage_id=stage_id, model_id=model_id("gemini"),
            status=status,
            artifact={
                "diagnostic_run": fake_run() if run is None else run,
                "stage_meter": meter(),
            },
        )

    def save_c(self, *, status="RECORDED_COMPLETE", raw=None):
        stage_id = sid(stage="C")
        self.journal.claim_stage(
            stage_id=stage_id, model_id=model_id("gemini"),
        )
        self.journal.record_stage(
            stage_id=stage_id, model_id=model_id("gemini"),
            status=status,
            artifact={
                "raw_response": cause() if raw is None else raw,
                "stage_meter": meter(),
            },
        )

    def test_d_preview_is_source_bound_and_never_creates_claim(self):
        report = self.preview()
        self.assertEqual(report["status"],
                         "STAGE_SOURCE_PREVIEW_READY_BUT_NO_API")
        self.assertEqual(report["stage"], "D")
        self.assertEqual(report["case_id"], DISCOVERY[0])
        self.assertEqual(report["instruction"], FAKE_INSTRUCTION)
        self.assertEqual(report["d_config"]["variant"], "A0")
        self.assertEqual(report["d_config"]["output_contract_mode"], "v2_enforce")
        self.assertEqual(report["d_config"]["max_tool_rounds"], 6)
        self.assertEqual(report["parent_record_sha256"], {})
        self.assertIsNone(report["prepared_package_sha256"])
        self.assertEqual(self.journal.audit_restart()["claims"], 0)

    def test_c_preview_uses_saved_d_evidence_and_frozen_prompt(self):
        self.save_d()
        report = self.preview(stage="C")
        self.assertEqual(report["stage"], "C")
        self.assertRegex(report["prepared_package_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(report["C_K_system_prompt_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(set(report["parent_record_sha256"]), {sid()})
        self.assertEqual(self.journal.audit_restart()["claims"], 1)

    def test_k_preview_requires_valid_saved_d_and_c(self):
        self.save_d()
        self.save_c()
        report = self.preview(stage="K")
        self.assertEqual(report["stage"], "K")
        self.assertRegex(report["prepared_package_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            set(report["parent_record_sha256"]), {sid(stage="C")},
        )
        self.assertEqual(self.journal.audit_restart()["claims"], 2)

    def test_actual_prompt_drift_still_fails_closed_for_both_stages(self):
        # Con la fixture allineata, una modifica REALE al system prompt
        # deve continuare a fallire, senza scrivere nuovi claim.
        self.save_d()
        self.save_c()
        prior_claims = self.journal.audit_restart()["claims"]
        for stage, prompt_name in (
            ("C", "CAUSE_SYSTEM"), ("K", "RULE_SYSTEM"),
        ):
            with self.subTest(stage=stage):
                with patch(
                    "evaluation.rq2_v2_unified_live_stage_preflight."
                    + prompt_name,
                    "ALTERED_SYSTEM_PROMPT_MUST_NOT_BE_ACCEPTED",
                ):
                    with self.assertRaisesRegex(
                        UnifiedStagePreviewBlocked, "prompt SHA drift",
                    ):
                        self.preview(stage=stage)
        self.assertEqual(
            self.journal.audit_restart()["claims"], prior_claims
        )

    def test_each_preview_is_read_only(self):
        before = sorted(
            str(p.relative_to(self.data)) for p in self.data.rglob("*")
        )
        first = self.preview()
        second = self.preview()
        after = sorted(
            str(p.relative_to(self.data)) for p in self.data.rglob("*")
        )
        self.assertEqual(first, second)
        self.assertEqual(before, after)
        for key in (
            "can_create_scientific_claim", "can_construct_provider_client",
            "can_execute_api", "can_run_ood_test", "files_written",
        ):
            self.assertIs(first[key], False, key)
        self.assertEqual(first["model_requests_sent"], 0)

    def test_ood_stage_disallowed_even_if_in_fake_csv(self):
        with self.assertRaises(UnifiedStagePreviewBlocked):
            self.preview(case=TEST[0])
        self.assertEqual(self.journal.audit_restart()["claims"], 0)

    def test_unknown_logical_model_disallowed(self):
        with self.assertRaises(UnifiedStagePreviewBlocked):
            self.preview(model="unknown")

    def test_c_missing_d_parent_is_blocked(self):
        with self.assertRaisesRegex(
            UnifiedStagePreviewBlocked, "parent",
        ):
            self.preview(stage="C")

    def test_k_missing_c_parent_is_blocked(self):
        self.save_d()
        with self.assertRaisesRegex(
            UnifiedStagePreviewBlocked, "parent",
        ):
            self.preview(stage="K")

    def test_invalid_d_parent_cannot_inform_c(self):
        self.save_d(
            status="INVALID_OUTPUT", run=fake_run(json_valid=False),
        )
        with self.assertRaisesRegex(
            UnifiedStagePreviewBlocked, "parent",
        ):
            self.preview(stage="C")

    def test_claimed_stage_cannot_be_prepared_twice(self):
        self.journal.claim_stage(
            stage_id=sid(), model_id=model_id("gemini"),
        )
        with self.assertRaises(UnifiedStagePreviewBlocked):
            self.preview()

    def test_previously_recorded_stage_cannot_be_prepared_again(self):
        self.save_d()
        with self.assertRaises(UnifiedStagePreviewBlocked):
            self.preview()

    def test_orphan_claim_blocks_other_stage_preview(self):
        self.journal.claim_stage(
            stage_id=sid(), model_id=model_id("gemini"),
        )
        with self.assertRaisesRegex(
            UnifiedStagePreviewBlocked, "Orphan",
        ):
            self.preview(harness="A1")

    def test_missing_manifest_disallowed(self):
        self.csv_path.unlink()
        with self.assertRaisesRegex(
            UnifiedStagePreviewBlocked, "manifest",
        ):
            self.preview()

    def test_duplicate_case_in_manifest_disallowed(self):
        row = [
            DISCOVERY[0], FAKE_INSTRUCTION, "1", "cloudbed-1",
            1760000000, 1760000600, 32,
        ]
        self.write_manifest(rows=[row, row])
        with self.assertRaisesRegex(
            UnifiedStagePreviewBlocked, "duplicated",
        ):
            self.preview()

    def test_gt_column_in_manifest_disallowed(self):
        row = [
            DISCOVERY[0], FAKE_INSTRUCTION, "1", "cloudbed-1",
            1760000000, 1760000600, 32, "FAKE_LABEL",
        ]
        self.write_manifest(
            header=CSV_HEADER + ["ground_truth"],
            rows=[row],
        )
        with self.assertRaisesRegex(
            UnifiedStagePreviewBlocked, "not GT-free",
        ):
            self.preview()

    def test_empty_instruction_disallowed(self):
        self.write_manifest(rows=[[
            DISCOVERY[0], "", "1", "cloudbed-1",
            1760000000, 1760000600, 32,
        ]])
        with self.assertRaisesRegex(
            UnifiedStagePreviewBlocked, "instruction",
        ):
            self.preview()

    def test_inverted_time_window_disallowed(self):
        self.write_manifest(rows=[[
            DISCOVERY[0], FAKE_INSTRUCTION, "1", "cloudbed-1",
            1760000900, 1760000000, 32,
        ]])
        with self.assertRaisesRegex(
            UnifiedStagePreviewBlocked, "window",
        ):
            self.preview()

    def test_wrong_release_hash_blocks_before_reading_manifest(self):
        with self.assertRaises(Exception):
            preview_one_unified_stage(
                data_dir=self.data, repo_dir=self.repo,
                stage_id=sid(), expected_commit=FAKE_COMMIT,
                approved_release_sha256="0" * 64,
            )

    def test_source_manifest_uses_only_expected_csv(self):
        self.assertEqual(
            _source_instruction(data_dir=self.data, case_id=DISCOVERY[0]),
            FAKE_INSTRUCTION,
        )
        self.assertFalse((self.data / "Market.zip").exists())
        self.assertFalse((self.data / "data/results").exists())


if __name__ == "__main__":
    unittest.main()
