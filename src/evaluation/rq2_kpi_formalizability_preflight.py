"""GT-free offline-only KPI inventory and RQ2-K formalizability preflight.

This is NOT an executable detector, scientific rule freeze, dataset inventory
or provider runner. Uses only KPI names mentioned in existing source code,
not any RQ2 discovery/test telemetry or target fault labels.

- Known in source does not prove availability in a particular Market window.
- A suggestive name does not verify physical units or counter semantics.
- A syntactically valid K JSON is not an implementable detector.
- The preflight never marks a rule as executable or test-ready.

R01/R06 references below are OLD, known-rule metric names, not new rules.
"""
from __future__ import annotations

import hashlib
import json

from harness.signal_catalog import GAUGE_CONTAINER, GAUGE_NODI
from evaluation.rq2_output_contracts import (
    ContractError, validate_candidate_rule,
)

VERSION = "rq2_kpi_formalizability_preflight_v0"
CATALOG_VERSION = "rq2_kpi_known_in_code_v0"
CATALOG_ORIGIN = "existing_RQ1_source_only"
CANDIDATE_SEMANTIC = "candidate_not_verified"

# Existing eight-rule code references, not held-out target label names.
# Especially, reads_MB must not be converted into a physical MB/s rate.
_EXTRA_CODE_REFERENCES = (
    ("container_cpu_usage_seconds", "container", "src/harness/rules/rule_container_cpu.py"),
    ("container_fs_reads_MB./dev/vda", "container", "src/harness/rules/rule_container_read_io.py"),
    ("container_fs_reads./dev/vda", "container", "src/harness/rules/rule_container_read_io.py"),
)


def _json_bytes(obj: object) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _digest(obj: object) -> str:
    return hashlib.sha256(_json_bytes(obj)).hexdigest()


def _add(
    catalog: dict[str, dict], *, name: str, source: str,
    family: str, location: str,
) -> None:
    if type(name) is not str or not name.strip() or name in catalog:
        raise ValueError("Duplicate or invalid source KPI")
    if source not in ("node", "container"):
        raise ValueError("Unsupported source KPI layer")
    catalog[name] = {
        "metric": name,
        "telemetry_layer": source,
        "tool": (
            "tool_get_node_metrics" if source == "node"
            else "tool_get_container_metrics"
        ),
        "family": family,
        "provenance_source_file": location,
        "presence_status": "known_in_code_only",
        "market_presence_verified": False,
        "physical_unit": None,
        "physical_unit_verified": False,
        "metric_semantics": CANDIDATE_SEMANTIC,
        "metric_semantics_verified": False,
        "allowed_rule_aggregations": [],
        "rule_aggregation_verified": False,
    }


def known_code_kpi_catalog() -> dict:
    """Deterministic conservative inventory of metrics already in RQ1 code.

    Does not scan Market.zip, CSVs, GT, API results or OOD incidents.
    Existing source constants are not automatic physical-unit approval.
    """
    catalog: dict[str, dict] = {}
    for metric, (family, _direction) in sorted(GAUGE_NODI.items()):
        _add(
            catalog, name=metric, source="node", family=family,
            location="src/harness/signal_catalog.py",
        )
    for metric, (family, _direction) in sorted(GAUGE_CONTAINER.items()):
        _add(
            catalog, name=metric, source="container", family=family,
            location="src/harness/signal_catalog.py",
        )
    for metric, source, location in _EXTRA_CODE_REFERENCES:
        _add(
            catalog, name=metric, source=source,
            family="pre_existing_rule_reference", location=location,
        )
    body = {
        "catalog_version": CATALOG_VERSION,
        "origin": CATALOG_ORIGIN,
        "source_code_references_only": True,
        "ground_truth_access": False,
        "reads_market": False,
        "reads_ood_cases": False,
        "physical_units_verified": 0,
        "metric_semantics_verified": 0,
        "can_certify_formalizability": False,
        "metrics": [catalog[name] for name in sorted(catalog)],
    }
    return {**body, "catalog_sha256": _digest(body)}


def evaluate_k_formalizability(
    raw_json: str, *, allowed_evidence_ids: tuple[str, ...],
) -> dict:
    """Check a candidate K against known-source KPI names.

    Output requires verification for any otherwise valid candidate because
    the current source-code inventory certifies NO physical units/semantics.
    A future plan-bound orchestrator must permit K only on discovery; this
    function is NOT a source of stage/phase authority.
    """
    catalog = known_code_kpi_catalog()
    metadata = {
        "preflight_version": VERSION,
        "catalog_sha256": catalog["catalog_sha256"],
        "only_source_code_references": True,
        "read_ground_truth": False,
        "reads_market": False,
        "model_api_calls": 0,
        "files_written": False,
        "rule_executed": False,
        "ready_for_test": False,
        "catalog_frozen_for_science": False,
    }
    try:
        candidate = validate_candidate_rule(
            raw_json, allowed_evidence_ids=allowed_evidence_ids,
        )
    except ContractError:
        return {
            **metadata,
            "status": "invalid_contract",
            "reasons": ["invalid_k_contract"],
            "declared_signal_count": None,
            "recognized_in_source_count": None,
        }
    if candidate["status"] == "insufficient_evidence":
        return {
            **metadata,
            "status": "insufficient_evidence",
            "reasons": ["model_abstained_from_rule"],
            "declared_signal_count": 0,
            "recognized_in_source_count": 0,
        }

    known = {item["metric"]: item for item in catalog["metrics"]}
    recognized = 0
    reasons: set[str] = set()
    for signal in candidate["required_signals"]:
        entry = known.get(signal["metric"])
        if entry is None:
            reasons.add("metric_not_in_source_catalog")
            continue
        recognized += 1
        if not entry["market_presence_verified"]:
            reasons.add("market_presence_unverified")
        if not entry["physical_unit_verified"]:
            reasons.add("physical_unit_unverified")
        elif signal["unit"] != entry["physical_unit"]:
            reasons.add("physical_unit_mismatch")
        if not entry["metric_semantics_verified"]:
            reasons.add("metric_semantics_unverified")
        if not entry["rule_aggregation_verified"]:
            reasons.add("aggregation_semantics_unverified")
        elif signal["aggregation"] not in entry["allowed_rule_aggregations"]:
            reasons.add("unsupported_aggregation")

    if not reasons:
        reasons.add("scientific_catalog_and_rule_freeze_missing")
    return {
        **metadata,
        "status": "requires_verification",
        "reasons": sorted(reasons),
        "declared_signal_count": len(candidate["required_signals"]),
        "recognized_in_source_count": recognized,
    }
