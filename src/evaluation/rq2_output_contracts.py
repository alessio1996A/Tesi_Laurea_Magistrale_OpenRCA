"""Strict RQ2 JSON contracts for offline validation of LLM-produced C/K output.

No ground truth, dataset, provider, telemetry or runner imports.
Structural and reference checks ONLY; no RCA correctness claims.
This module MUST NOT run any LLM-generated pseudocode.
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Collection

SCHEMA_C = "rq2_cause_probe_v0"
SCHEMA_K = "rq2_candidate_rule_v0"
_EVIDENCE_RE = re.compile(r"E[0-9]{3,6}\Z")
_AGGREGATIONS = {"mean", "max", "min", "sum", "count", "p95", "last", "delta"}
_OPERATORS = {">", ">=", "<", "<=", "=="}


class ContractError(ValueError):
    """A syntactically valid JSON response violates the RQ2 schema."""


def _duplicate_key_error(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for name, value in pairs:
        if name in result:
            raise ContractError("Duplicate JSON key: " + name)
        result[name] = value
    return result


def _reject_constant(token: str):
    raise ContractError("Non-JSON numeric constant: " + token)


def _parse(raw: str) -> dict:
    if not isinstance(raw, str) or not raw.strip():
        raise ContractError("Empty/non-text response")
    # markdown wrapping is intentionally invalid (do not repair raw outputs).
    if len(raw) > 40_000:
        raise ContractError("JSON response exceeds maximum length")
    try:
        obj = json.loads(raw, object_pairs_hook=_duplicate_key_error,
                         parse_constant=_reject_constant)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ContractError("Invalid strict JSON response: " + str(exc)) from exc
    if type(obj) is not dict:
        raise ContractError("Expected JSON object")
    return obj


def _keys(obj: dict, names: tuple[str, ...], label: str):
    if set(obj) != set(names):
        raise ContractError(
            f"{label}: expected fields {sorted(names)}, got {sorted(obj)}"
        )


def _text(value: object, name: str, *, nullable: bool = False):
    if value is None and nullable:
        return
    if type(value) is not str or not value.strip():
        raise ContractError(f"{name} must be a nonempty string")
    if len(value) > 2000:
        raise ContractError(f"{name} exceeds 2000 characters")


def _text_list(value: object, name: str, *, max_count: int = 12):
    if type(value) is not list or len(value) > max_count:
        raise ContractError(f"{name} must be a bounded JSON list")
    for item in value:
        _text(item, name + " item")


def _allowed_refs(allowed_evidence_ids: Collection[str]) -> set[str]:
    if isinstance(allowed_evidence_ids, (str, bytes, dict)) or not isinstance(
        allowed_evidence_ids, Collection
    ):
        raise ContractError("Evidence allowlist must be a collection of IDs")
    if len(allowed_evidence_ids) > 5000:
        raise ContractError("Evidence allowlist too large")
    result = set(allowed_evidence_ids)
    if len(result) != len(allowed_evidence_ids) or not all(
        isinstance(v, str) and _EVIDENCE_RE.fullmatch(v) for v in result
    ):
        raise ContractError("Malformed/duplicate allowed evidence IDs")
    return result


def _refs(value: object, allowed: set[str]):
    if type(value) is not list or len(value) > 32:
        raise ContractError("evidence_ids must be a bounded JSON list")
    if len(value) != len(set(v for v in value if type(v) is str)):
        raise ContractError("Duplicate or non-string evidence_ids")
    if any(
        type(ref) is not str or not _EVIDENCE_RE.fullmatch(ref)
        or ref not in allowed for ref in value
    ):
        raise ContractError("Unknown/malformed evidence ID")


def validate_cause_probe(
    raw_json: str, *, allowed_evidence_ids: Collection[str],
) -> dict:
    """Validate probe C. The allowlist must be generated from real tool logs."""
    obj = _parse(raw_json)
    _keys(obj, (
        "schema_version", "decision", "predicted_fault_type",
        "predicted_component", "confidence", "evidence_ids",
        "alternatives", "limitations",
    ), "cause probe")
    if obj["schema_version"] != SCHEMA_C:
        raise ContractError("Wrong cause probe schema version")
    if obj["decision"] not in ("diagnosis", "abstain"):
        raise ContractError("decision must be diagnosis or abstain")
    if obj["confidence"] not in ("low", "medium", "high", "unassessed"):
        raise ContractError("Invalid confidence value")
    _text(obj["predicted_fault_type"], "predicted_fault_type", nullable=True)
    _text(obj["predicted_component"], "predicted_component", nullable=True)
    _refs(obj["evidence_ids"], _allowed_refs(allowed_evidence_ids))
    _text_list(obj["alternatives"], "alternatives")
    _text_list(obj["limitations"], "limitations")
    if obj["decision"] == "diagnosis":
        _text(obj["predicted_fault_type"], "predicted_fault_type")
        if not obj["evidence_ids"]:
            raise ContractError("Diagnosis requires observed evidence IDs")
    else:
        if obj["predicted_fault_type"] is not None:
            raise ContractError("Abstention must not assert a fault type")
        if obj["predicted_component"] is not None:
            raise ContractError("Abstention must not assert a component")
        if not obj["limitations"]:
            raise ContractError("Abstention requires reason in limitations")
    return obj


def _signals(value: object) -> set[tuple[str, str, str, int]]:
    if type(value) is not list or len(value) > 12:
        raise ContractError("required_signals must be a bounded list")
    signatures = set()
    for item in value:
        if type(item) is not dict:
            raise ContractError("Signal must be a JSON object")
        _keys(item, ("metric", "unit", "aggregation", "window_seconds"), "signal")
        for key in ("metric", "unit"):
            _text(item[key], "signal." + key)
        if item["aggregation"] not in _AGGREGATIONS:
            raise ContractError("Unsupported signal aggregation")
        if type(item["window_seconds"]) is not int or not (
            1 <= item["window_seconds"] <= 86400
        ):
            raise ContractError("Invalid signal window_seconds")
        signature = (item["metric"], item["unit"],
                     item["aggregation"], item["window_seconds"])
        if signature in signatures:
            raise ContractError("Duplicate signal definition")
        signatures.add(signature)
    return signatures


def _conditions(value: object, signals: set) -> set:
    if type(value) is not list or len(value) > 24:
        raise ContractError("conditions must be a bounded list")
    used = set()
    for item in value:
        if type(item) is not dict:
            raise ContractError("Condition must be a JSON object")
        _keys(item, (
            "metric", "operator", "threshold", "unit",
            "aggregation", "window_seconds",
        ), "condition")
        for key in ("metric", "unit"):
            _text(item[key], "condition." + key)
        if item["operator"] not in _OPERATORS:
            raise ContractError("Unsupported comparator")
        threshold = item["threshold"]
        if type(threshold) not in (int, float) or not math.isfinite(threshold):
            raise ContractError("Threshold must be a finite number")
        if item["aggregation"] not in _AGGREGATIONS:
            raise ContractError("Unsupported condition aggregation")
        if type(item["window_seconds"]) is not int or not (
            1 <= item["window_seconds"] <= 86400
        ):
            raise ContractError("Invalid condition window_seconds")
        signature = (item["metric"], item["unit"],
                     item["aggregation"], item["window_seconds"])
        if signature not in signals:
            raise ContractError("Condition has no matching required_signal")
        used.add(signature)
    return used


def validate_candidate_rule(
    raw_json: str, *, allowed_evidence_ids: Collection[str],
) -> dict:
    """Validate proposal K, never evaluate its pseudocode or thresholds."""
    obj = _parse(raw_json)
    _keys(obj, (
        "schema_version", "status", "hypothesized_fault_type",
        "rule_name", "scope", "evidence_ids", "required_signals",
        "conditions", "combination", "abstain_when", "counterexamples",
        "limitations", "pseudocode",
    ), "candidate rule")
    if obj["schema_version"] != SCHEMA_K:
        raise ContractError("Wrong candidate rule schema")
    if obj["status"] not in ("candidate", "insufficient_evidence"):
        raise ContractError("Invalid candidate rule status")
    for key in ("hypothesized_fault_type", "rule_name", "scope", "pseudocode"):
        _text(obj[key], key, nullable=True)
    _refs(obj["evidence_ids"], _allowed_refs(allowed_evidence_ids))
    sigs = _signals(obj["required_signals"])
    used = _conditions(obj["conditions"], sigs)
    if obj["combination"] not in ("all", "any", None):
        raise ContractError("Invalid combination")
    _text_list(obj["abstain_when"], "abstain_when")
    _text_list(obj["counterexamples"], "counterexamples")
    _text_list(obj["limitations"], "limitations")
    if obj["status"] == "candidate":
        for key in ("hypothesized_fault_type", "rule_name", "scope", "pseudocode"):
            _text(obj[key], key)
        if not obj["evidence_ids"] or not sigs or not obj["conditions"]:
            raise ContractError("Candidate requires evidence, signals, conditions")
        if sigs != used:
            raise ContractError("All required signals must be used in conditions")
        if obj["combination"] not in ("all", "any"):
            raise ContractError("Candidate requires all/any combination")
        if any(not obj[key] for key in
               ("abstain_when", "counterexamples", "limitations")):
            raise ContractError("Candidate missing abstention, counterexamples or limits")
    else:
        if obj["required_signals"] or obj["conditions"] or obj["pseudocode"] is not None:
            raise ContractError("Insufficient evidence cannot assert detector logic")
        if obj["rule_name"] is not None or obj["combination"] is not None:
            raise ContractError("Insufficient evidence cannot define a rule")
        if not obj["abstain_when"] or not obj["limitations"]:
            raise ContractError("Insufficient evidence must explain abstention")
    return obj
