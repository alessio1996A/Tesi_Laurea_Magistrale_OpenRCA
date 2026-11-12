"""Offline, synthetic-only tests of RQ2 pre-freeze KPI evidence semantics."""
import copy
import json
import unittest

from evaluation.rq2_kpi_formalizability_preflight import (
    VERSION, known_code_kpi_catalog, evaluate_k_formalizability,
)


def example_k(
    metric="system.cpu.pct_usage", unit="percent_unverified",
    aggregation="max", evidence_ids=None,
):
    evidence_ids = ["E001"] if evidence_ids is None else evidence_ids
    return {
        "schema_version": "rq2_candidate_rule_v0",
        "status": "candidate",
        "hypothesized_fault_type": "synthetic hypothetical fault",
        "rule_name": "synthetic proposed rule",
        "scope": "node: synthetic",
        "evidence_ids": evidence_ids,
        "required_signals": [{
            "metric": metric, "unit": unit, "aggregation": aggregation,
            "window_seconds": 180,
        }],
        "conditions": [{
            "metric": metric, "unit": unit, "aggregation": aggregation,
            "window_seconds": 180, "operator": ">", "threshold": 80.0,
        }],
        "combination": "all",
        "abstain_when": ["Missing numeric samples"],
        "counterexamples": ["External synthetic load"],
        "limitations": ["Unit not verified"],
        "pseudocode": "If threshold exceeded, propose only",
    }


def run(candidate, *, allowed=("E001",)):
    return evaluate_k_formalizability(
        json.dumps(candidate), allowed_evidence_ids=allowed,
    )


class RQ2KPIPreflightTests(unittest.TestCase):
    def test_catalog_deterministic_and_non_executable(self):
        x, y = known_code_kpi_catalog(), known_code_kpi_catalog()
        self.assertEqual(x, y)
        self.assertEqual(len(x["catalog_sha256"]), 64)
        self.assertFalse(x["can_certify_formalizability"])
        self.assertFalse(x["reads_market"])
        self.assertFalse(x["ground_truth_access"])

    def test_existing_node_metric_is_just_known_in_source(self):
        items = {e["metric"]:e for e in known_code_kpi_catalog()["metrics"]}
        self.assertIn("system.cpu.pct_usage", items)
        node = items["system.cpu.pct_usage"]
        self.assertEqual(node["telemetry_layer"], "node")
        self.assertEqual(node["tool"], "tool_get_node_metrics")
        self.assertFalse(node["market_presence_verified"])
        self.assertFalse(node["physical_unit_verified"])

    def test_known_container_r01_metric_is_not_unit_approved(self):
        items = {e["metric"]:e for e in known_code_kpi_catalog()["metrics"]}
        entry = items["container_cpu_usage_seconds"]
        self.assertEqual(entry["telemetry_layer"], "container")
        self.assertFalse(entry["metric_semantics_verified"])
        self.assertIsNone(entry["physical_unit"])

    def test_known_container_r06_metric_is_not_approved_for_throughput(self):
        items = {e["metric"]:e for e in known_code_kpi_catalog()["metrics"]}
        item = items["container_fs_reads_MB./dev/vda"]
        self.assertEqual(item["allowed_rule_aggregations"], [])
        self.assertFalse(item["rule_aggregation_verified"])
        self.assertIsNone(item["physical_unit"])

    def test_catalog_never_claims_any_unit_or_semantics_verified(self):
        catalog = known_code_kpi_catalog()
        for item in catalog["metrics"]:
            self.assertFalse(item["physical_unit_verified"])
            self.assertFalse(item["metric_semantics_verified"])
            self.assertFalse(item["market_presence_verified"])
            self.assertIsNone(item["physical_unit"])
        self.assertEqual(catalog["physical_units_verified"], 0)

    def test_valid_k_needs_verification(self):
        result = run(example_k())
        self.assertEqual(result["preflight_version"], VERSION)
        self.assertEqual(result["status"], "requires_verification")
        self.assertEqual(result["recognized_in_source_count"], 1)
        self.assertEqual(result["declared_signal_count"], 1)
        self.assertIn("physical_unit_unverified", result["reasons"])
        self.assertIn("metric_semantics_unverified", result["reasons"])

    def test_unknown_metric_not_falsely_claimed_missing_from_dataset(self):
        result = run(example_k(metric="unknown_synthetic_kpi"))
        self.assertIn("metric_not_in_source_catalog", result["reasons"])
        self.assertEqual(result["recognized_in_source_count"], 0)
        self.assertNotIn("market_metric_proven_absent", result["reasons"])

    def test_known_name_does_not_prove_unit(self):
        result = run(example_k(unit="%"))
        self.assertIn("physical_unit_unverified", result["reasons"])
        self.assertFalse(result["ready_for_test"])

    def test_known_name_with_raw_value_does_not_prove_semantics(self):
        result = run(example_k(unit="raw_value"))
        self.assertIn("aggregation_semantics_unverified", result["reasons"])
        self.assertFalse(result["ready_for_test"])

    def test_compound_known_and_unknown_metric_recognized_count(self):
        k = example_k()
        k["required_signals"].append({
            "metric": "unknown_synthetic_kpi", "unit": "unverified",
            "aggregation": "mean", "window_seconds": 60,
        })
        k["conditions"].append({
            "metric": "unknown_synthetic_kpi", "unit": "unverified",
            "aggregation": "mean", "window_seconds": 60,
            "operator": "<", "threshold": 30,
        })
        result = run(k)
        self.assertEqual(result["declared_signal_count"], 2)
        self.assertEqual(result["recognized_in_source_count"], 1)
        self.assertIn("metric_not_in_source_catalog", result["reasons"])

    def test_evidence_reference_not_in_trajectory_rejects_k(self):
        k = example_k(evidence_ids=["E999"])
        result = run(k)
        self.assertEqual(result["status"], "invalid_contract")
        self.assertFalse(result["ready_for_test"])

    def test_invalid_json_fails_closed(self):
        result = evaluate_k_formalizability(
            "{not-json", allowed_evidence_ids=("E001",),
        )
        self.assertEqual(result["status"], "invalid_contract")
        self.assertEqual(result["reasons"], ["invalid_k_contract"])

    def test_missing_required_falsifier_fails_closed(self):
        k = example_k()
        k["counterexamples"] = []
        self.assertEqual(run(k)["status"], "invalid_contract")

    def test_unit_or_condition_signature_mismatch_fails_closed(self):
        k = example_k()
        k["conditions"][0]["unit"] = "DIFFERENT"
        self.assertEqual(run(k)["status"], "invalid_contract")

    def test_insufficient_evidence_is_not_treated_as_candidate(self):
        k = example_k()
        k.update({
            "status": "insufficient_evidence",
            "rule_name": None, "combination": None,
            "pseudocode": None, "required_signals": [], "conditions": [],
        })
        result = run(k)
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["declared_signal_count"], 0)
        self.assertFalse(result["ready_for_test"])

    def test_pseudocode_remains_inert_and_result_never_exposes_it(self):
        k = example_k()
        k["pseudocode"] = "raise SystemExit('DO NOT EXECUTE')"
        result = run(k)
        self.assertEqual(result["status"], "requires_verification")
        self.assertNotIn("DO NOT EXECUTE", str(result))
        self.assertFalse(result["rule_executed"])

    def test_all_statuses_prohibit_api_and_test(self):
        candidates = [
            example_k(),
            example_k(evidence_ids=["E999"]),
        ]
        for k in candidates:
            with self.subTest(status=k["status"]):
                result = run(k)
                self.assertFalse(result["ready_for_test"])
                self.assertFalse(result["catalog_frozen_for_science"])
                self.assertFalse(result["read_ground_truth"])
                self.assertEqual(result["model_api_calls"], 0)
                self.assertFalse(result["files_written"])

    def test_catalog_does_not_include_fault_class_to_case_mapping(self):
        text = json.dumps(known_code_kpi_catalog())
        self.assertNotIn("cloudbed-1_q", text)
        self.assertNotIn("cloudbed-2_q", text)
        self.assertNotIn("ground_truth_reason", text)

    def test_source_catalog_does_not_automatically_add_heldout_detector(self):
        items = {e["metric"]:e for e in known_code_kpi_catalog()["metrics"]}
        self.assertNotIn("rule_container_packet_loss", items)
        self.assertNotIn("rule_container_write_io", items)


if __name__ == "__main__":
    unittest.main()
