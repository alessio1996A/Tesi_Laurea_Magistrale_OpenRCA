"""Synthetic-only tests for GT-free RQ2 evidence bundling from RQ1 trajectories."""
import copy
import json
import unittest

from evaluation.rq2_evidence_bundle import (
    EvidenceBundleError, build_evidence_bundle, evidence_ids,
)
from evaluation.rq2_output_contracts import validate_cause_probe

TOOLS = ("tool_get_node_metrics", "tool_get_container_metrics")


def legacy_sample():
    return [
        {"tipo": "tool_call", "nome": "tool_get_node_metrics",
         "parametri": {"cmdb_id": "node-1", "start_unix": 100, "end_unix": 200}},
        {"tipo": "tool_result", "nome": "tool_get_node_metrics",
         "risposta": "cpu=0.72 [synthetic observation]"},
        {"tipo": "tool_call", "nome": "tool_get_node_metrics",
         "parametri": {"cmdb_id": "node-2"}},
        {"tipo": "tool_result", "nome": "tool_get_node_metrics",
         "risposta": "cpu=0.18 [synthetic observation]"},
    ]


class RQ2EvidenceBundleTests(unittest.TestCase):
    def test_legacy_sequential_repeated_tool_name(self):
        trajectory = legacy_sample()
        a = build_evidence_bundle(trajectory, allowed_tool_names=TOOLS)
        b = build_evidence_bundle(copy.deepcopy(trajectory), allowed_tool_names=TOOLS)
        self.assertEqual(a, b)
        self.assertEqual(a["observations_count"], 2)
        self.assertEqual(evidence_ids(a), {"E001", "E002"})
        self.assertEqual(a["evidence"][0]["arguments"]["cmdb_id"], "node-1")
        self.assertEqual(a["evidence"][1]["arguments"]["cmdb_id"], "node-2")
        self.assertEqual(a["evidence"][0]["call_origin"], "unknown")
        self.assertFalse(a["evidence"][0]["units_verified"])
        self.assertEqual(len(a["bundle_sha256"]), 64)

    def test_parallel_calls_with_ids_match_results_in_result_order(self):
        trajectory = [
            {"tipo": "tool_call", "nome": TOOLS[0], "parametri": {"cmdb_id": "A"},
             "origine": "llm", "tool_call_id": "call-1"},
            {"tipo": "tool_call", "nome": TOOLS[0], "parametri": {"cmdb_id": "B"},
             "origine": "llm", "tool_call_id": "call-2"},
            {"tipo": "tool_result", "nome": TOOLS[0], "risposta": "obs B",
             "origine": "llm", "tool_call_id": "call-2"},
            {"tipo": "tool_result", "nome": TOOLS[0], "risposta": "obs A",
             "origine": "llm", "tool_call_id": "call-1"},
        ]
        bundle = build_evidence_bundle(trajectory, allowed_tool_names=TOOLS)
        self.assertEqual(
            [x["arguments"]["cmdb_id"] for x in bundle["evidence"]],
            ["B", "A"]
        )
        self.assertEqual(bundle["evidence"][0]["tool_call_id"], "call-2")
        self.assertEqual(bundle["evidence"][0]["call_origin"], "llm")

    def test_ambiguous_legacy_parallel_same_tool_refused(self):
        events = [
            {"tipo": "tool_call", "nome": TOOLS[0], "parametri": {"cmdb_id": "A"}},
            {"tipo": "tool_call", "nome": TOOLS[0], "parametri": {"cmdb_id": "B"}},
            {"tipo": "tool_result", "nome": TOOLS[0], "risposta": "A or B?"},
            {"tipo": "tool_result", "nome": TOOLS[0], "risposta": "A or B?"},
        ]
        with self.assertRaisesRegex(EvidenceBundleError, "Ambiguous"):
            build_evidence_bundle(events, allowed_tool_names=TOOLS)

    def test_missing_result_or_unmatched_result_is_rejected(self):
        for events in (
            legacy_sample()[:-1],
            [{"tipo": "tool_result", "nome": TOOLS[0], "risposta": "orphan"}],
        ):
            with self.subTest(events=len(events)), self.assertRaises(
                EvidenceBundleError
            ):
                build_evidence_bundle(events, allowed_tool_names=TOOLS)

    def test_call_result_id_disagreement_rejected(self):
        events = [
            {"tipo": "tool_call", "nome": TOOLS[0], "parametri": {},
             "tool_call_id": "a"},
            {"tipo": "tool_result", "nome": TOOLS[0], "risposta": "measurement",
             "tool_call_id": "b"},
        ]
        with self.assertRaisesRegex(EvidenceBundleError, "Unmatched"):
            build_evidence_bundle(events, allowed_tool_names=TOOLS)

    def test_other_telemetry_tool_not_in_allowlist_rejected(self):
        events = [
            {"tipo": "tool_call", "nome": "tool_read_ground_truth",
             "parametri": {}}
        ]
        with self.assertRaisesRegex(EvidenceBundleError, "allowlist"):
            build_evidence_bundle(events, allowed_tool_names=TOOLS)

    def test_sensitive_scoring_in_arguments_and_observations_refused(self):
        for location in ("params", "observation"):
            events = legacy_sample()
            if location == "params":
                events[0]["parametri"]["path"] = "record.csv"
            else:
                events[1]["risposta"] = '{"scoring_points":"leaked"}'
            with self.subTest(location=location), self.assertRaisesRegex(
                EvidenceBundleError, "ground-truth"
            ):
                build_evidence_bundle(events, allowed_tool_names=TOOLS)

    def test_known_and_unknown_origin_modes(self):
        events = [
            {"tipo": "tool_call", "nome": TOOLS[0], "parametri": {},
             "origine": "planner", "tool_call_id": "plan-1"},
            {"tipo": "tool_result", "nome": TOOLS[0], "risposta": "obs",
             "origine": "llm", "tool_call_id": "plan-1"},
        ]
        with self.assertRaisesRegex(EvidenceBundleError, "origin mismatch"):
            build_evidence_bundle(events, allowed_tool_names=TOOLS)

    def test_empty_trace_yields_no_allowed_evidence(self):
        bundle = build_evidence_bundle([], allowed_tool_names=TOOLS)
        self.assertEqual(bundle["observations_count"], 0)
        self.assertEqual(evidence_ids(bundle), set())

    def test_explicit_middle_truncation_and_sha(self):
        long_text = "A" * 4000 + "B" * 4000
        events = [
            {"tipo": "tool_call", "nome": TOOLS[0], "parametri": {}},
            {"tipo": "tool_result", "nome": TOOLS[0], "risposta": long_text},
        ]
        bundle = build_evidence_bundle(events, allowed_tool_names=TOOLS)
        observation = bundle["evidence"][0]
        self.assertTrue(observation["truncated"])
        self.assertIn("TRUNCATED_MIDDLE_BY_RQ2_BUNDLE", observation["observation_text"])
        self.assertLessEqual(len(observation["observation_text"]), 2400)
        self.assertEqual(observation["observation_chars"], 8000)
        self.assertEqual(bundle["truncated_count"], 1)

    def test_nan_argument_must_fail(self):
        events = [
            {"tipo": "tool_call", "nome": TOOLS[0], "parametri": {"x": float("nan")}},
        ]
        with self.assertRaises(EvidenceBundleError):
            build_evidence_bundle(events, allowed_tool_names=TOOLS)

    def test_integration_with_cause_probe_allowed_evidence_ids(self):
        bundle = build_evidence_bundle(legacy_sample(), allowed_tool_names=TOOLS)
        candidate = {
            "schema_version": "rq2_cause_probe_v0",
            "decision": "diagnosis",
            "predicted_fault_type": "synthetic failure",
            "predicted_component": "node-1",
            "confidence": "unassessed",
            "evidence_ids": ["E001"],
            "alternatives": [],
            "limitations": [],
        }
        self.assertEqual(
            validate_cause_probe(json.dumps(candidate),
                                 allowed_evidence_ids=evidence_ids(bundle)),
            candidate,
        )

    def test_duplicate_tool_call_id_fails(self):
        events = [
            {"tipo": "tool_call", "nome": TOOLS[0], "parametri": {},
             "tool_call_id": "call-1"},
            {"tipo": "tool_call", "nome": TOOLS[1], "parametri": {},
             "tool_call_id": "call-1"},
        ]
        with self.assertRaisesRegex(EvidenceBundleError, "Duplicate"):
            build_evidence_bundle(events, allowed_tool_names=TOOLS)

    def test_reject_unexpected_trajectory_fields(self):
        events = copy.deepcopy(legacy_sample())
        events[1]["raw_response"] = '{"some":"model guess"}'
        with self.assertRaisesRegex(EvidenceBundleError, "Unknown trajectory fields"):
            build_evidence_bundle(events, allowed_tool_names=TOOLS)


if __name__ == "__main__":
    unittest.main()
