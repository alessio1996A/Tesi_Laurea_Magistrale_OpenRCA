"""Synthetic-only source-bound D preflight tests. No Market or model calls.

The trusted preview_market function and frozen source hash constants are
mocked ONLY in these unit tests to exercise the binding logic against tiny
synthetic CSV files. These fixtures never establish real source verification.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluation.rq2_source_bound_d_preflight as subject
from evaluation.rq2_dryrun_plan import _sha as canonical_sha
from test_rq2_dryrun_plan import plan as make_synthetic_plan
from test_rq2_dryrun_plan import synthetic_cohort


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RQ2SourceBoundDTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        meta, _, discovery, test = synthetic_cohort()
        self.discovery = discovery
        self.test = test
        self.split = self.root / "data/processed/split_market_v1.csv"
        self.manifest = self.root / "data/processed/benchmark_inputs_market.csv"
        self.split_rows = [
            {
                "case_id": m["case_id"], "cloudbed": m["cloudbed"],
                "start_unix": str(m["start_unix"]),
                "end_unix": str(m["end_unix"]), "split": "ood_holdout",
            } for m in meta
        ]
        self.manifest_rows = [
            {
                "case_id": m["case_id"], "cloudbed": m["cloudbed"],
                "start_unix": str(m["start_unix"]),
                "end_unix": str(m["end_unix"]),
                "task_index": m["task_index"], "query_index": str(i),
                "instruction": "Investigate a purely synthetic incident.",
            } for i, m in enumerate(meta)
        ]
        self._write()
        self.plan = make_synthetic_plan()
        self.plan["source_verified"] = True  # FAKE trusted wrapper in tests
        self._pin()

    def _write(self):
        write_csv(
            self.split,
            ("case_id", "cloudbed", "start_unix", "end_unix", "split"),
            self.split_rows,
        )
        write_csv(
            self.manifest,
            ("case_id", "cloudbed", "query_index", "task_index",
             "instruction", "start_unix", "end_unix"),
            self.manifest_rows,
        )

    def _pin(self):
        self.plan["split_sha256"] = digest(self.split)
        self.plan["manifest_sha256"] = digest(self.manifest)
        body = {
            "summary": {
                key: val for key, val in self.plan.items()
                if key not in ("preview_sha256", "entries")
            },
            "entries": self.plan["entries"],
        }
        self.plan["preview_sha256"] = canonical_sha(body)

    def _run(self, **options):
        args = {
            "data_dir": self.root,
            "case_id": self.discovery[0],
            "logical_model": "sonnet",
            "harness": "A1",
            "proposed_model_name": "claude-sonnet-SYNTHETIC-NOT-FROZEN",
            "output_contract_mode": "v2_enforce",
        }
        args.update(options)
        with (
            patch.object(subject, "preview_market", return_value=self.plan),
            patch.object(subject, "EXPECTED_SPLIT_SHA256", digest_saved(self.plan, "split")),
            patch.object(subject, "EXPECTED_MANIFEST_SHA256", digest_saved(self.plan, "manifest")),
            patch.object(subject, "DISCOVERY", self.discovery),
        ):
            return subject.preview_discovery_d_config(**args)

    def test_valid_discovery_is_still_strictly_blocked(self):
        result = self._run()
        self.assertEqual(result["phase"], "discovery")
        self.assertEqual(result["status"], "SOURCE_BOUND_DISCOVERY_D_PREVIEW_ONLY")
        self.assertTrue(result["source_verified_in_this_function"])
        self.assertFalse(result["can_execute_api"])
        self.assertFalse(result["can_execute_D"])
        self.assertFalse(result["can_execute_test"])
        self.assertFalse(result["scientific_protocol_frozen"])
        self.assertEqual(result["model_api_calls"], 0)
        self.assertFalse(result["files_written"])

    def test_valid_A1_8R_configuration_preview(self):
        result = self._run(harness="A1_8R", output_contract_mode="legacy")
        config = result["experiment_config_proposal"]
        self.assertEqual(config["variant"], "A1_8R")
        self.assertEqual(config["variant_scheme"], "current")
        self.assertEqual(config["model_provider"], "anthropic")
        self.assertEqual(config["max_tool_rounds"], 6)
        self.assertEqual(config["output_contract_mode"], "legacy")
        self.assertFalse(result["output_contract_mode_frozen"])

    def test_no_instruction_raw_content_or_market_data_exported(self):
        result = self._run()
        self.assertEqual(len(result["instruction_sha256"]), 64)
        self.assertNotIn("instruction", result)
        self.assertNotIn("Investigate a purely synthetic", str(result))
        self.assertFalse(result["read_telemetry"])
        self.assertFalse(result["read_ground_truth"])
        self.assertEqual(result["code_execution"], "NO_MODEL_NO_TOOLS_NO_RUN_EXPERIMENT")

    def test_test_case_blocked_before_loading_source(self):
        with patch.object(subject, "preview_market") as loader:
            with patch.object(subject, "DISCOVERY", self.discovery):
                with self.assertRaisesRegex(subject.SourceBoundDError, "Invalid discovery"):
                    subject.preview_discovery_d_config(
                        data_dir=self.root, case_id=self.test[0],
                        logical_model="sonnet", harness="A1",
                        proposed_model_name="claude-sonnet-SYNTHETIC",
                        output_contract_mode="legacy",
                    )
            loader.assert_not_called()

    def test_wrong_harness_not_admitted(self):
        with self.assertRaisesRegex(subject.SourceBoundDError, "Invalid discovery"):
            self._run(harness="A1_PAVE")

    def test_wrong_logical_model_not_admitted(self):
        with self.assertRaisesRegex(subject.SourceBoundDError, "Invalid discovery"):
            self._run(logical_model="unknown_model")

    def test_model_name_must_match_logical_family(self):
        with self.assertRaisesRegex(subject.SourceBoundDError, "Invalid discovery"):
            self._run(proposed_model_name="gemini-SYNTHETIC")

    def test_contract_mode_cannot_be_implicit(self):
        with self.assertRaisesRegex(subject.SourceBoundDError, "Invalid discovery"):
            self._run(output_contract_mode="structured")

    def test_unverified_plan_is_refused(self):
        self.plan["source_verified"] = False
        self._pin()
        with self.assertRaisesRegex(subject.SourceBoundDError, "source-verified"):
            self._run()

    def test_tampered_plan_digest_refused(self):
        self.plan["entries"][0]["task_index"] = "tampered"
        with self.assertRaisesRegex(subject.SourceBoundDError, "preflight"):
            self._run()

    def test_changed_gtfree_split_bytes_refused(self):
        self.split.write_bytes(self.split.read_bytes() + b"\n")
        with self.assertRaisesRegex(subject.SourceBoundDError, "source hash mismatch"):
            self._run()

    def test_manifest_case_window_mismatch_refused(self):
        target = next(x for x in self.manifest_rows if x["case_id"] == self.discovery[0])
        target["start_unix"] = str(int(target["start_unix"]) + 1)
        self._write()
        self._pin()
        with self.assertRaisesRegex(subject.SourceBoundDError, "metadata mismatch"):
            self._run()

    def test_manifest_task_index_mismatch_refused(self):
        target = next(x for x in self.manifest_rows if x["case_id"] == self.discovery[0])
        target["task_index"] = "task_0"
        self._write()
        self._pin()
        with self.assertRaisesRegex(subject.SourceBoundDError, "differs"):
            self._run()

    def test_blank_gtfree_instruction_refused(self):
        target = next(x for x in self.manifest_rows if x["case_id"] == self.discovery[0])
        target["instruction"] = ""
        self._write()
        self._pin()
        with self.assertRaisesRegex(subject.SourceBoundDError, "differs"):
            self._run()

    def test_gt_column_in_split_is_rejected(self):
        with self.split.open("w", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(
                out, fieldnames=("case_id", "cloudbed", "start_unix",
                                 "end_unix", "split", "scoring_points"),
            )
            writer.writeheader()
            for row in self.split_rows:
                writer.writerow({**row, "scoring_points": "synthetic forbidden"})
        self._pin()
        with self.assertRaisesRegex(subject.SourceBoundDError, "preflight"):
            self._run()

    def test_no_implicit_default_provider_name(self):
        with self.assertRaisesRegex(subject.SourceBoundDError, "Invalid discovery"):
            self._run(proposed_model_name="")


def digest_saved(plan: dict, which: str) -> str:
    return plan[f"{which}_sha256"]


if __name__ == "__main__":
    unittest.main()
