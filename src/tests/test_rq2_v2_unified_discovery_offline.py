"""Test puramente sintetici della nuova matrice RQ2-V2, senza API e GT."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation import rq2_v2_unified_discovery_plan as plan
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_v2_unified_provenance_gate import (
    UnifiedRQ2ProvenanceError, audit_captured_v2_d,
)


def fake_d(model="gemini", harness="A0", case_id=None, *,
           origin=None, call_id="synthetic-tool-123"):
    cid = case_id or plan.DISCOVERY[0]
    row = {
        "case_id": cid,
        "variant": harness,
        "variant_scheme": "current",
        "model": CANDIDATE_MODELS[model]["model_id"],
        "model_provider": CANDIDATE_MODELS[model]["provider"],
        "output_contract_mode": "v2_enforce",
        "max_tool_rounds": 6,
        "raw_response": None,
        "json_status": "invalid_json: synthetic",
        "error": None,
        "metrics": {"token_usage_complete": True},
        "tool_trajectory": [
            {"tipo": "tool_call", "nome": "tool_get_node_metrics",
             "parametri": {"cmdb_id": "synthetic-node-1"},
             "tool_call_id": call_id},
            {"tipo": "tool_result", "nome": "tool_get_node_metrics",
             "risposta": "synthetic CPU statistic",
             "tool_call_id": call_id},
        ],
    }
    if origin is not None:
        for event in row["tool_trajectory"]:
            event["origine"] = origin
    return row


def verified_preview():
    return {
        "source_verified": True,
        "split_sha256": plan.EXPECTED_SPLIT_SHA256,
        "manifest_sha256": plan.EXPECTED_MANIFEST_SHA256,
        "partition": {
            "discovery_case_ids": sorted(plan.DISCOVERY),
            "test_case_ids": sorted(plan.TEST),
        },
        "stages": {"D": 90, "C": 90, "K": 24},
        "total_stage_entries": 204,
        "can_execute_api": False,
    }


class UnifiedRQ2PlanTests(unittest.TestCase):
    def test_exact_180_stage_matrix(self):
        p = plan.build_offline_discovery_plan()
        self.assertEqual(len(p["entries"]), 180)
        self.assertEqual(p["logical_stages"], 180)
        self.assertEqual(p["stage_counts"], {"D": 60, "C": 60, "K": 60})
        self.assertEqual(p["discovery_arm_cases"], 60)
        self.assertEqual(p["harness_model_arms"], 15)
        self.assertEqual(p["discovery_case_count"], 4)

    def test_all_five_harnesses_and_three_models_covered(self):
        p = plan.build_offline_discovery_plan()
        expected = {
            (cid, model, harness, stage)
            for cid in plan.DISCOVERY
            for model in plan.MODELS
            for harness in plan.HARNESSES
            for stage in plan.STAGES
        }
        actual = {
            (x["case_id"], x["logical_model"], x["harness"], x["stage"])
            for x in p["entries"]
        }
        self.assertEqual(actual, expected)

    def test_no_ood_stage_is_in_discovery_plan(self):
        p = plan.build_offline_discovery_plan()
        self.assertFalse(
            {r["case_id"] for r in p["entries"]} & set(plan.TEST)
        )
        self.assertEqual(len(p["ood_test_cases_locked"]), 11)
        self.assertFalse(p["can_run_ood_test"])

    def test_immutable_d_c_k_dependencies(self):
        p = plan.build_offline_discovery_plan()
        by_id = {row["stage_id"]: i for i, row in enumerate(p["entries"])}
        for row in p["entries"]:
            deps = row["depends_on"]
            self.assertEqual(len(deps), 0 if row["stage"] == "D" else 1)
            self.assertTrue(all(by_id[x] < by_id[row["stage_id"]] for x in deps))
            self.assertEqual(row["execution_status"], "BLOCKED_DRAFT")

    def test_engines_are_correct_for_harness(self):
        p = plan.build_offline_discovery_plan()
        for row in p["entries"]:
            expected = (
                "verify_graph" if row["harness"] in
                ("A1_8R_Planning", "A1_PAVE")
                else "rq2_v2_graph_engine"
            )
            self.assertEqual(row["d_engine"], expected)

    def test_model_ids_match_existing_model_catalog(self):
        p = plan.build_offline_discovery_plan()
        for row in p["entries"]:
            entry = CANDIDATE_MODELS[row["logical_model"]]
            self.assertEqual(row["model_id"], entry["model_id"])
            self.assertEqual(row["model_provider"], entry["provider"])

    def test_plan_does_not_grant_api_release_or_science(self):
        p = plan.build_offline_discovery_plan()
        for key in (
            "signed_release_exists", "scientific_release_frozen",
            "api_budget_approved", "can_call_model_api", "can_write_real_claims",
            "can_run_ood_test", "ground_truth_read", "telemetry_read",
            "historical_records_read", "files_written",
            "split_manifest_source_verified",
        ):
            self.assertFalse(p[key], key)
        self.assertEqual(p["model_api_calls"], 0)
        self.assertIsNone(p["planned_llm_http_calls"])

    def test_plan_is_stable_and_sha_changes_if_entries_modified(self):
        p = plan.build_offline_discovery_plan()
        self.assertEqual(p, plan.build_offline_discovery_plan())
        self.assertEqual(len(p["preview_sha256"]), 64)
        self.assertEqual(len(p["entries_sha256"]), 64)
        q = copy.deepcopy(p)
        q["entries"][0]["harness"] = "wrong"
        self.assertNotEqual(plan._sha({k: v for k,v in q.items()
                                       if k != "preview_sha256"}),
                            p["preview_sha256"])

    def test_original_v1_stage_ids_not_reused(self):
        p = plan.build_offline_discovery_plan()
        ids = {row["stage_id"] for row in p["entries"]}
        self.assertEqual(len(ids), 180)
        self.assertTrue(all(s.startswith(plan.VERSION + ":") for s in ids))
        self.assertFalse(any("rq2_dryrun_workflow_preview_v0:" in s for s in ids))

    def test_source_verified_only_after_original_source_check(self):
        source = verified_preview()
        with patch.object(plan, "preview_market", return_value=source) as check:
            out = plan.preview_gt_free_sources(Path("/tmp/synthetic"))
        self.assertTrue(check.called)
        self.assertTrue(out["split_manifest_source_verified"])
        self.assertFalse(out["scientific_release_frozen"])
        self.assertFalse(out["can_call_model_api"])
        self.assertFalse(out["can_run_ood_test"])
        self.assertFalse(out["ground_truth_read"])
        self.assertEqual(out["logical_stages"], 180)

    def test_source_drift_fail_closed(self):
        for mutation in (
            ("split_sha256", "wrong"),
            ("source_verified", False),
            ("total_stage_entries", 999),
            ("can_execute_api", True),
        ):
            with self.subTest(mutation=mutation):
                source = verified_preview()
                source[mutation[0]] = mutation[1]
                with patch.object(plan, "preview_market", return_value=source):
                    with self.assertRaises(plan.UnifiedRQ2PlanError):
                        plan.preview_gt_free_sources(Path("/tmp/synthetic"))

    def test_rejects_relative_source_path(self):
        with self.assertRaises(plan.UnifiedRQ2PlanError):
            plan.preview_gt_free_sources(Path("relative"))


class UnifiedRQ2ProvenanceTests(unittest.TestCase):
    def test_realistic_synthetic_react_run_is_auditable(self):
        a = audit_captured_v2_d(
            run=fake_d(), case_id=plan.DISCOVERY[0],
            model="gemini", harness="A0",
        )
        self.assertEqual(a["tool_result_pairs_matched"], 1)
        self.assertTrue(a["capture_has_native_tool_call_ids"])
        self.assertEqual(a["d_engine_required"], "rq2_v2_graph_engine")
        self.assertFalse(a["can_execute_api"])
        self.assertFalse(a["can_run_ood_test"])

    def test_three_nonplanner_harnesses_all_share_gate(self):
        for harness in ("A0", "A1", "A1_8R"):
            with self.subTest(harness=harness):
                out = audit_captured_v2_d(
                    run=fake_d(harness=harness),
                    case_id=plan.DISCOVERY[0],
                    model="gemini", harness=harness,
                )
                self.assertEqual(out["tool_result_pairs_matched"], 1)

    def test_all_three_models_allowed_with_exact_ids(self):
        for model in plan.MODELS:
            with self.subTest(model=model):
                out = audit_captured_v2_d(
                    run=fake_d(model=model),
                    case_id=plan.DISCOVERY[0],
                    model=model, harness="A0",
                )
                self.assertEqual(out["logical_model"], model)

    def test_planner_and_pave_preserve_origin(self):
        for harness in ("A1_8R_Planning", "A1_PAVE"):
            for origin in ("llm", "planner"):
                with self.subTest(harness=harness, origin=origin):
                    out = audit_captured_v2_d(
                        run=fake_d(harness=harness, origin=origin),
                        case_id=plan.DISCOVERY[0],
                        model="gemini", harness=harness,
                    )
                    self.assertEqual(out["tool_call_origins"], [origin])
                    self.assertEqual(out["d_engine_required"], "verify_graph")

    def test_missing_native_id_is_rejected(self):
        run = fake_d()
        del run["tool_trajectory"][1]["tool_call_id"]
        with self.assertRaisesRegex(UnifiedRQ2ProvenanceError, "native"):
            audit_captured_v2_d(
                run=run, case_id=plan.DISCOVERY[0], model="gemini", harness="A0"
            )

    def test_mismatched_native_id_is_rejected(self):
        run = fake_d()
        run["tool_trajectory"][1]["tool_call_id"] = "wrong"
        with self.assertRaisesRegex(UnifiedRQ2ProvenanceError, "Unpaired"):
            audit_captured_v2_d(
                run=run, case_id=plan.DISCOVERY[0], model="gemini", harness="A0"
            )

    def test_parallel_same_named_tools_are_matched_by_id(self):
        run = fake_d()
        run["tool_trajectory"] = [
            {"tipo": "tool_call", "nome": "tool_get_node_metrics",
             "parametri": {"cmdb_id": "synthetic-node-1"},
             "tool_call_id": "call-1"},
            {"tipo": "tool_call", "nome": "tool_get_node_metrics",
             "parametri": {"cmdb_id": "synthetic-node-2"},
             "tool_call_id": "call-2"},
            {"tipo": "tool_result", "nome": "tool_get_node_metrics",
             "risposta": "second result", "tool_call_id": "call-2"},
            {"tipo": "tool_result", "nome": "tool_get_node_metrics",
             "risposta": "first result", "tool_call_id": "call-1"},
        ]
        out = audit_captured_v2_d(
            run=run, case_id=plan.DISCOVERY[0], model="gemini", harness="A0"
        )
        self.assertEqual(out["tool_result_pairs_matched"], 2)

    def test_unknown_origin_is_rejected_for_planner(self):
        run = fake_d(harness="A1_PAVE", origin="unknown")
        with self.assertRaisesRegex(UnifiedRQ2ProvenanceError, "explicit"):
            audit_captured_v2_d(
                run=run, case_id=plan.DISCOVERY[0],
                model="gemini", harness="A1_PAVE",
            )

    def test_spoofed_planner_origin_rejected_for_react(self):
        run = fake_d(origin="planner")
        with self.assertRaisesRegex(UnifiedRQ2ProvenanceError, "ReAct"):
            audit_captured_v2_d(
                run=run, case_id=plan.DISCOVERY[0], model="gemini", harness="A0"
            )

    def test_source_identity_mismatch_refused(self):
        run = fake_d()
        run["model"] = "different"
        with self.assertRaises(UnifiedRQ2ProvenanceError):
            audit_captured_v2_d(
                run=run, case_id=plan.DISCOVERY[0], model="gemini", harness="A0"
            )

    def test_ood_test_identity_is_refused(self):
        with self.assertRaises(UnifiedRQ2ProvenanceError):
            audit_captured_v2_d(
                run=fake_d(), case_id=plan.TEST[0],
                model="gemini", harness="A0",
            )

    def test_no_evidence_allows_abstention_input_not_a_diagnosis(self):
        run = fake_d()
        run["tool_trajectory"] = []
        report = audit_captured_v2_d(
            run=run, case_id=plan.DISCOVERY[0], model="gemini", harness="A0",
        )
        self.assertEqual(report["tool_result_pairs_matched"], 0)
        self.assertFalse(report["scientific_release_frozen"])
        self.assertNotIn("candidate_rule", report)

    def test_partial_metering_not_falsely_claimed_complete(self):
        run = fake_d()
        run["metrics"]["token_usage_complete"] = False
        report = audit_captured_v2_d(
            run=run, case_id=plan.DISCOVERY[0], model="gemini", harness="A0",
        )
        self.assertFalse(report["token_usage_complete"])


if __name__ == "__main__":
    unittest.main()
