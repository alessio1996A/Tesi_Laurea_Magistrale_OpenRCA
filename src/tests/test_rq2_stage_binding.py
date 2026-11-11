"""Offline D->C->K plan-binding tests: synthetic D only, zero API/dataset."""
import copy
import json
import unittest

from test_rq2_dryrun_plan import plan as make_plan
from evaluation.rq2_stage_binding import (
    StageBindingError, prepare_bound_c, prepare_bound_k,
)


INSTRUCTION = "Investigate the synthetic service interruption."


def synthetic_d(*, cid="cloudbed-1_q003", variant="A1", model="claude-sonnet-5.5",
                provider="anthropic"):
    return {
        "case_id": cid,
        "variant": variant,
        "variant_scheme": "current",
        "model": model,
        "model_provider": provider,
        "max_tool_rounds": 6,
        "raw_response": "D SECRET ANCHORING ANSWER",
        "error": None,
        "tool_trajectory": [
            {
                "tipo": "tool_call", "nome": "tool_get_node_metrics",
                "parametri": {"start_unix": 32400, "end_unix": 34200,
                             "cmdb_id": "synthetic-node"},
            },
            {
                "tipo": "tool_result", "nome": "tool_get_node_metrics",
                "risposta": "synthetic_load=0.45; units not verified",
            },
        ],
    }


def cause():
    return json.dumps({
        "schema_version": "rq2_cause_probe_v0",
        "decision": "diagnosis",
        "predicted_fault_type": "hypothetical synthetic failure",
        "predicted_component": "synthetic-node",
        "confidence": "low",
        "evidence_ids": ["E001"],
        "alternatives": ["a second explanation"],
        "limitations": ["units are not yet verified"],
    })


def stage_id(cid="cloudbed-1_q003", model="sonnet", harness="A1", stage="C"):
    return f"rq2_dryrun_workflow_preview_v0:{cid}:{model}:{harness}:{stage}"


def make_c(p=None, d=None, instruction=INSTRUCTION):
    return prepare_bound_c(
        plan=make_plan() if p is None else p,
        c_stage_id=stage_id(),
        original_instruction=instruction,
        diagnostic_run=synthetic_d() if d is None else d,
    )


def make_k(p=None, d=None, c=None, cause_json=None,
           instruction=INSTRUCTION, sid=None):
    plan = make_plan() if p is None else p
    run = synthetic_d() if d is None else d
    binding = make_c(plan, run, instruction) if c is None else c
    return prepare_bound_k(
        plan=plan,
        k_stage_id=stage_id(stage="K") if sid is None else sid,
        original_instruction=instruction,
        diagnostic_run=run,
        prior_c_binding=binding,
        cause_raw_json=cause() if cause_json is None else cause_json,
    )


class RQ2StageBindingTests(unittest.TestCase):
    def test_c_binding_is_deterministic_and_api_blocked(self):
        a = make_c()
        b = make_c()
        self.assertEqual(a, b)
        self.assertEqual(a["stage_id"], stage_id())
        self.assertEqual(a["phase"], "discovery")
        self.assertEqual(a["dependency_ids"], [stage_id(stage="D")])
        self.assertFalse(a["can_execute_api"])
        self.assertFalse(a["source_verified_in_this_function"])
        self.assertFalse(a["scientific_rules_frozen"])
        self.assertEqual(a["model_api_calls"], 0)
        self.assertNotIn("SECRET ANCHORING", str(a))
        self.assertEqual(len(a["binding_sha256"]), 64)

    def test_k_binding_same_c_and_discovery(self):
        bound = make_k()
        self.assertEqual(bound["stage_id"], stage_id(stage="K"))
        self.assertEqual(bound["dependency_ids"], [stage_id(stage="C")])
        self.assertEqual(bound["phase"], "discovery")
        self.assertFalse(bound["can_execute_api"])
        self.assertEqual(bound["model_api_calls"], 0)

    def test_test_phase_c_is_permitted(self):
        p = make_plan()
        cid = "cloudbed-1_q000"
        d = synthetic_d(cid=cid)
        bound = prepare_bound_c(
            plan=p, c_stage_id=stage_id(cid=cid),
            original_instruction=INSTRUCTION, diagnostic_run=d,
        )
        self.assertEqual(bound["phase"], "test")

    def test_test_phase_has_no_k_even_if_requested(self):
        with self.assertRaisesRegex(StageBindingError, "outside discovery"):
            make_k(sid=stage_id(cid="cloudbed-1_q000",stage="K"))

    def test_d_case_identity_mismatch_fails(self):
        with self.assertRaisesRegex(StageBindingError, "identity"):
            make_c(d=synthetic_d(cid="cloudbed-1_q006"))

    def test_d_harness_identity_mismatch_fails(self):
        with self.assertRaisesRegex(StageBindingError, "identity"):
            make_c(d=synthetic_d(variant="A1_8R"))

    def test_d_model_identity_mismatch_fails(self):
        with self.assertRaisesRegex(StageBindingError, "identity"):
            make_c(d=synthetic_d(model="claude-haiku-5.5"))

    def test_d_provider_identity_mismatch_fails(self):
        with self.assertRaisesRegex(StageBindingError, "identity"):
            make_c(d=synthetic_d(provider="google"))

    def test_d_variant_scheme_historical_fails(self):
        d = synthetic_d()
        d["variant_scheme"] = "historic_v3"
        with self.assertRaisesRegex(StageBindingError, "identity"):
            make_c(d=d)

    def test_d_failed_run_blocks_c(self):
        d = synthetic_d()
        d["error"] = "SYNTHETIC_PROVIDER_ERROR"
        with self.assertRaisesRegex(StageBindingError, "Cannot prepare C"):
            make_c(d=d)

    def test_d_unauthorized_tool_fails(self):
        d = synthetic_d()
        d["tool_trajectory"][0]["nome"] = "tool_read_ground_truth"
        with self.assertRaisesRegex(StageBindingError, "Cannot prepare C"):
            make_c(d=d)

    def test_edited_plan_hash_detected(self):
        p = make_plan()
        p["partition"]["discovery_case_ids"].append("tamper")
        with self.assertRaisesRegex(StageBindingError, "SHA256 mismatch"):
            make_c(p=p)

    def test_plan_cannot_enable_api(self):
        p = make_plan()
        p["can_execute_api"] = True
        with self.assertRaisesRegex(StageBindingError, "blocked"):
            make_c(p=p)

    def test_closed_entry_schema_rejects_label_even_with_rehash(self):
        p = make_plan()
        p["entries"][0]["target_label"] = "synthetic-secret"
        # Hash is recomputed to ensure the closed-schema check, not the hash,
        # is what stops a per-case GT field.
        from evaluation.rq2_stage_binding import _sha
        p["preview_sha256"] = _sha({
            "summary": {k:v for k,v in p.items()
                        if k not in ("preview_sha256", "entries")},
            "entries": p["entries"],
        })
        with self.assertRaisesRegex(StageBindingError, "GT-free fields"):
            make_c(p=p)

    def test_k_rejects_c_from_different_observation(self):
        p = make_plan()
        original = synthetic_d()
        prior = make_c(p, original)
        modified = synthetic_d()
        modified["tool_trajectory"][1]["risposta"] = "DIFFERENT OBSERVATION"
        with self.assertRaisesRegex(StageBindingError, "not identical"):
            make_k(p=p, d=modified, c=prior)

    def test_k_rejects_c_from_different_instruction(self):
        p = make_plan()
        prior = make_c(p)
        with self.assertRaisesRegex(StageBindingError, "not identical"):
            make_k(p=p, c=prior, instruction="Different synthetic instruction.")

    def test_k_rejects_unknown_evidence_id(self):
        cdata = json.loads(cause())
        cdata["evidence_ids"] = ["E777"]
        with self.assertRaisesRegex(StageBindingError, "Cannot prepare K"):
            make_k(cause_json=json.dumps(cdata))

    def test_k_rejects_invalid_c_json(self):
        with self.assertRaisesRegex(StageBindingError, "Cannot prepare K"):
            make_k(cause_json="{not valid")

    def test_bound_c_for_gemini(self):
        p = make_plan()
        d = synthetic_d(model="gemini-3.5-flash-lite", provider="google")
        bound = prepare_bound_c(
            plan=p, c_stage_id=stage_id(model="gemini"),
            original_instruction=INSTRUCTION, diagnostic_run=d,
        )
        self.assertEqual(bound["logical_model"], "gemini")
        self.assertFalse(bound["can_execute_api"])

    def test_no_mock_freeze_can_turn_package_into_api_authorization(self):
        bound = make_k()
        self.assertFalse(bound["provider_model_versions_frozen"])
        self.assertFalse(bound["scientific_rules_frozen"])
        self.assertFalse(bound["underlying_package"]["ready_for_api"])


if __name__ == "__main__":
    unittest.main()
