"""Synthetic D/C/K stage recording end to end: zero API, Market or GT."""
from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluation.rq2_stage_artifact_store as storage
import evaluation.rq2_discovery_stage_recorder as recorder
from evaluation.rq2_dryrun_plan import _sha as plan_sha
import test_rq2_dryrun_plan as plan_fixture
import test_rq2_output_contracts as contract_fixture
import test_rq2_stage_binding as binding_fixture

MODEL = "claude-sonnet-5.5"
CID = "cloudbed-1_q003"
PREFIX = f"rq2_dryrun_workflow_preview_v0:{CID}:sonnet:A1"


def _write(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RQ2DiscoveryRecorderTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.split = self.root / "data/processed/split_market_v1.csv"
        self.manifest = self.root / "data/processed/benchmark_inputs_market.csv"
        cohort, _, _, _ = plan_fixture.synthetic_cohort()
        split_rows = [
            { "case_id": m["case_id"], "cloudbed": m["cloudbed"],
              "start_unix": str(m["start_unix"]), "end_unix": str(m["end_unix"]),
              "split": "ood_holdout" } for m in cohort
        ]
        manifest_rows = [
            { "case_id": m["case_id"], "cloudbed": m["cloudbed"],
              "start_unix": str(m["start_unix"]), "end_unix": str(m["end_unix"]),
              "query_index": str(i), "task_index": m["task_index"],
              "instruction": binding_fixture.INSTRUCTION }
            for i, m in enumerate(cohort)
        ]
        _write(self.split, ("case_id", "cloudbed", "start_unix",
                            "end_unix", "split"), split_rows)
        _write(self.manifest, ("case_id", "cloudbed", "query_index",
                               "task_index", "instruction",
                               "start_unix", "end_unix"), manifest_rows)
        self.plan = plan_fixture.plan()
        self.plan["source_verified"] = True  # only inside this unit test
        self.plan["split_sha256"] = _digest(self.split)
        self.plan["manifest_sha256"] = _digest(self.manifest)
        summary = {k: v for k, v in self.plan.items()
                   if k not in ("entries", "preview_sha256")}
        self.plan["preview_sha256"] = plan_sha({
            "summary": summary, "entries": self.plan["entries"],
        })
        for p in [
            patch.object(storage, "preview_market", return_value=self.plan),
            patch.object(recorder, "preview_market", return_value=self.plan),
            patch.object(storage, "EXPECTED_SPLIT_SHA256", _digest(self.split)),
            patch.object(storage, "EXPECTED_MANIFEST_SHA256", _digest(self.manifest)),
            patch.object(recorder, "EXPECTED_MANIFEST_SHA256", _digest(self.manifest)),
        ]:
            p.start()
            self.addCleanup(p.stop)

    def make(self):
        return recorder.RQ2DiscoveryStageRecorder(data_dir=self.root)

    def sid(self, stage):
        return PREFIX + ":" + stage

    def d(self, *, error=None, json_status="valid_json", raw="{}"):
        value = binding_fixture.synthetic_d()
        value.update({
            "model": MODEL,
            "error": error,
            "json_status": json_status,
            "raw_response": raw,
        })
        return value

    def k(self):
        return json.dumps(contract_fixture.RQ2OutputContractsTests.rule())

    def save_d(self, obj, **changes):
        return obj.record_d(
            stage_id=self.sid("D"), model_id_proposed=MODEL,
            diagnostic_run=self.d(**changes),
        )

    def save_c(self, obj, **changes):
        args = {"stage_id": self.sid("C"), "model_id_proposed": MODEL,
                "raw_response": binding_fixture.cause()}
        args.update(changes)
        return obj.record_c(**args)

    def save_k(self, obj, **changes):
        args = {"stage_id": self.sid("K"), "model_id_proposed": MODEL,
                "raw_response": self.k()}
        args.update(changes)
        return obj.record_k(**args)

    def test_constructor_does_not_create_files_or_dispatch(self):
        obj = self.make()
        self.assertFalse(obj.store.root.exists())
        self.assertFalse(hasattr(obj, "run_agent"))
        self.assertFalse(hasattr(obj, "call_model"))

    def test_complete_d_c_k_chain_and_restart(self):
        obj = self.make()
        self.assertEqual(self.save_d(obj)["status"], "RECORDED_COMPLETE")
        self.assertEqual(self.save_c(obj)["status"], "RECORDED_COMPLETE")
        self.assertEqual(self.save_k(obj)["status"], "RECORDED_COMPLETE")
        report = self.make().store.audit_restart()
        self.assertEqual(report["stored_discovery_stages"], 3)
        self.assertEqual(report["by_status"], {"RECORDED_COMPLETE": 3})
        self.assertFalse(report["test_phase_unlocked"])
        self.assertEqual(report["model_api_calls"], 0)

    def test_k_is_not_scientifically_frozen(self):
        obj = self.make()
        self.save_d(obj)
        self.save_c(obj)
        self.save_k(obj)
        record = obj.store.load_discovery_stage(stage_id=self.sid("K"))
        self.assertEqual(record["artifact"]["preflight_status"],
                         "requires_verification")
        self.assertFalse(record["artifact"]["scientific_freeze"])
        self.assertEqual(record["authorization"], "NO_API_AUTHORITY")

    def test_invalid_d_task_json_does_not_destroy_valid_tool_evidence(self):
        obj = self.make()
        self.save_d(obj, json_status="invalid_json: synthetic",
                    raw="INVALID D RESPONSE")
        self.assertEqual(obj.store.load_discovery_stage(
            stage_id=self.sid("D")
        )["status"], "RECORDED_COMPLETE")
        self.assertEqual(self.save_c(obj)["status"], "RECORDED_COMPLETE")
        c_record = obj.store.load_discovery_stage(stage_id=self.sid("C"))
        self.assertNotIn("INVALID D RESPONSE", json.dumps(c_record["artifact"]))

    def test_d_provider_error_blocks_c_and_k(self):
        obj = self.make()
        self.save_d(obj, error="synthetic 503")
        self.save_c(obj, raw_response=None)
        self.save_k(obj, raw_response=None)
        self.assertEqual(obj.store.audit_restart()["by_status"], {
            "PROVIDER_ERROR": 1, "BLOCKED_DEPENDENCY": 2,
        })

    def test_invalid_d_trajectory_blocks_downstream(self):
        obj = self.make()
        value = self.d()
        value["tool_trajectory"] = "not a trajectory"
        result = obj.record_d(
            stage_id=self.sid("D"), model_id_proposed=MODEL,
            diagnostic_run=value,
        )
        self.assertEqual(result["status"], "INVALID_OUTPUT")
        self.save_c(obj, raw_response=None)
        self.assertEqual(obj.store.audit_restart()["by_status"], {
            "INVALID_OUTPUT": 1, "BLOCKED_DEPENDENCY": 1,
        })

    def test_invalid_c_json_retained_and_k_blocked(self):
        obj = self.make()
        self.save_d(obj)
        self.assertEqual(self.save_c(
            obj, raw_response="INVALID C JSON"
        )["status"], "INVALID_OUTPUT")
        self.save_k(obj, raw_response=None)
        c = obj.store.load_discovery_stage(stage_id=self.sid("C"))
        self.assertEqual(c["artifact"]["raw_response"], "INVALID C JSON")
        self.assertEqual(obj.store.audit_restart()["by_status"], {
            "RECORDED_COMPLETE": 1, "INVALID_OUTPUT": 1,
            "BLOCKED_DEPENDENCY": 1,
        })

    def test_c_provider_error_distinct_from_invalid_json(self):
        obj = self.make()
        self.save_d(obj)
        self.assertEqual(self.save_c(
            obj, raw_response=None, provider_error="synthetic timeout"
        )["status"], "PROVIDER_ERROR")
        self.save_k(obj, raw_response=None)
        self.assertEqual(obj.store.audit_restart()["by_status"], {
            "RECORDED_COMPLETE": 1, "PROVIDER_ERROR": 1,
            "BLOCKED_DEPENDENCY": 1,
        })

    def test_invalid_k_json_stored_without_repair(self):
        obj = self.make()
        self.save_d(obj)
        self.save_c(obj)
        self.assertEqual(self.save_k(
            obj, raw_response="INVALID K JSON"
        )["status"], "INVALID_OUTPUT")
        k = obj.store.load_discovery_stage(stage_id=self.sid("K"))
        self.assertEqual(k["artifact"]["raw_response"], "INVALID K JSON")

    def test_missing_prior_d_blocks_c(self):
        obj = self.make()
        with self.assertRaisesRegex(recorder.RQ2RecorderError, "previous stage"):
            self.save_c(obj)
        self.assertFalse(obj.store.root.exists())

    def test_missing_prior_c_blocks_k(self):
        obj = self.make()
        self.save_d(obj)
        with self.assertRaisesRegex(recorder.RQ2RecorderError, "previous stage"):
            self.save_k(obj)
        self.assertEqual(obj.store.audit_restart()["stored_discovery_stages"], 1)

    def test_test_stage_is_forbidden(self):
        obj = self.make()
        sid = "rq2_dryrun_workflow_preview_v0:cloudbed-1_q000:sonnet:A1:D"
        with self.assertRaisesRegex(recorder.RQ2RecorderError,
                                    "Only planned discovery"):
            obj.record_d(
                stage_id=sid, model_id_proposed=MODEL,
                diagnostic_run=self.d(),
            )
        self.assertFalse(obj.store.root.exists())

    def test_d_wrong_case_rejected_before_write(self):
        obj = self.make()
        run = self.d()
        run["case_id"] = "cloudbed-2_q003"
        with self.assertRaisesRegex(recorder.RQ2RecorderError, "identity"):
            obj.record_d(stage_id=self.sid("D"),
                         model_id_proposed=MODEL, diagnostic_run=run)
        self.assertFalse(obj.store.root.exists())

    def test_model_id_exact_equality_not_just_substring(self):
        obj = self.make()
        with self.assertRaisesRegex(recorder.RQ2RecorderError, "model ID"):
            obj.record_d(stage_id=self.sid("D"),
                         model_id_proposed="claude-sonnet-different",
                         diagnostic_run=self.d())
        self.save_d(obj)
        with self.assertRaisesRegex(recorder.RQ2RecorderError, "model ID differs"):
            self.save_c(obj, model_id_proposed="claude-sonnet-different")

    def test_gt_key_in_caller_d_metadata_rejected(self):
        obj = self.make()
        d = self.d()
        d["evaluation"] = {"scoring_points": 1}
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "Forbidden"):
            obj.record_d(stage_id=self.sid("D"),
                         model_id_proposed=MODEL, diagnostic_run=d)
        self.assertFalse(obj.store.root.exists())

    def test_double_record_d_is_create_only(self):
        obj = self.make()
        self.save_d(obj)
        before = next(obj.store.root.glob("*.json")).read_bytes()
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "Create-only"):
            self.save_d(obj)
        self.assertEqual(before, next(obj.store.root.glob("*.json")).read_bytes())

    def test_source_mutation_blocks_followup(self):
        obj = self.make()
        self.save_d(obj)
        self.manifest.write_bytes(self.manifest.read_bytes() + b"\n")
        with self.assertRaisesRegex(storage.RQ2ArtifactStoreError, "sources changed"):
            self.save_c(obj)

    def test_provider_error_and_raw_c_are_mutually_exclusive(self):
        obj = self.make()
        self.save_d(obj)
        with self.assertRaisesRegex(recorder.RQ2RecorderError, "Invalid C"):
            self.save_c(obj, provider_error="synthetic",
                        raw_response="two outcomes")
        self.assertEqual(obj.store.audit_restart()["stored_discovery_stages"], 1)

    def test_k_abstention_is_valid_completed_output_not_provider_failure(self):
        obj = self.make()
        self.save_d(obj)
        self.save_c(obj)
        k = contract_fixture.RQ2OutputContractsTests.rule()
        k.update({
            "status": "insufficient_evidence",
            "hypothesized_fault_type": None,
            "rule_name": None, "combination": None,
            "pseudocode": None, "required_signals": [], "conditions": [],
        })
        result = self.save_k(obj, raw_response=json.dumps(k))
        self.assertEqual(result["status"], "RECORDED_COMPLETE")
        stored = obj.store.load_discovery_stage(stage_id=self.sid("K"))
        self.assertEqual(stored["artifact"]["preflight_status"],
                         "insufficient_evidence")

    def test_restart_can_load_d_and_continue_to_c(self):
        obj = self.make()
        self.save_d(obj)
        obj = self.make()
        self.assertEqual(self.save_c(obj)["status"], "RECORDED_COMPLETE")
        self.assertEqual(obj.store.audit_restart()["stored_discovery_stages"], 2)


if __name__ == "__main__":
    unittest.main()
