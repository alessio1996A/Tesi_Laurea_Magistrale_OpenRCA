"""Rubrica K preregistrata RQ2-V2, SOLO analisi offline e GT-free.

Non modifica il ciclo D/C/K, non legge dataset, non avvia provider, non scrive
ledger, non esegue pseudocodice. E' un audit MECCANICO di una K gia' prodotta.
Le osservazioni dei tool restano dati non fidati: un match letterale di metrica
e unita' NON dimostra misura vera, causalita' o trasferibilita'.
La definizione scientifica e' congelata nel documento
docs/ood/RQ2_V2_K_QUALITY_RUBRIC_PREREG_2026-11-15.md.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection
import re

from evaluation.rq2_evidence_bundle import (
    EvidenceBundleError, FORBIDDEN, build_evidence_bundle, evidence_ids,
)
from evaluation.rq2_output_contracts import ContractError, validate_candidate_rule

VERSION = "rq2_v2_k_quality_rubric_v0"
STATUS = "K_QUALITY_OFFLINE_GT_FREE_MECHANICAL_ONLY"
_WORD_CHAR = r"A-Za-z0-9_"


class KQualityReviewBlocked(ValueError):
    """Traiettoria non affidabile o potenziale contaminazione GT: STOP."""


def _literal_occurs(term: str, observation: str) -> bool:
    """Coincidenza lessicale completa, non corrispondenza semantica."""
    if type(term) is not str or type(observation) is not str:
        return False
    return bool(re.search(
        rf"(?<![{_WORD_CHAR}]){re.escape(term)}(?![{_WORD_CHAR}])",
        observation,
        flags=re.IGNORECASE,
    ))


def _signature(condition: dict) -> tuple:
    return (
        condition["metric"], condition["unit"],
        condition["aggregation"], condition["window_seconds"],
    )


def _contradictory_all(conditions: list, combination: str) -> bool:
    """Rileva SOLO intersezioni numeriche vuote di vincoli su stesso segnale."""
    if combination != "all":
        return False
    by_signal = defaultdict(list)
    for condition in conditions:
        by_signal[_signature(condition)].append(condition)

    for group in by_signal.values():
        equalities = {c["threshold"] for c in group if c["operator"] == "=="}
        if len(equalities) > 1:
            return True
        lower = None  # (value, strict)
        upper = None
        for condition in group:
            value = condition["threshold"]
            operator = condition["operator"]
            if operator in (">", ">="):
                candidate = (value, operator == ">")
                if (lower is None or candidate[0] > lower[0]
                        or candidate[0] == lower[0] and candidate[1]):
                    lower = candidate
            if operator in ("<", "<="):
                candidate = (value, operator == "<")
                if (upper is None or candidate[0] < upper[0]
                        or candidate[0] == upper[0] and candidate[1]):
                    upper = candidate
        if lower is not None and upper is not None:
            if lower[0] > upper[0] or (
                lower[0] == upper[0] and (lower[1] or upper[1])
            ):
                return True
        if equalities:
            equality = next(iter(equalities))
            if lower is not None and (
                equality < lower[0]
                or (equality == lower[0] and lower[1])
            ):
                return True
            if upper is not None and (
                equality > upper[0]
                or (equality == upper[0] and upper[1])
            ):
                return True
    return False


def evaluate_k_quality(
    raw_json: str, *,
    tool_trajectory: list[dict],
    allowed_tool_names: Collection[str],
) -> dict:
    """Valuta una K gia' prodotta; tutte le misure sono SOLO strutturali.

    Categorie di ledger BLOCKED_DEPENDENCY e PROVIDER_ERROR si contano nel
    report esterno, NON si inventa un raw JSON per farle passare qui.
    """
    if type(raw_json) is not str:
        raise KQualityReviewBlocked("Raw K response required")
    if FORBIDDEN.search(raw_json):
        raise KQualityReviewBlocked("Potential scoring/GT contamination")
    try:
        bundle = build_evidence_bundle(
            tool_trajectory, allowed_tool_names=allowed_tool_names,
        )
        ids = evidence_ids(bundle)
    except EvidenceBundleError as exc:
        raise KQualityReviewBlocked("Source D provenance is not auditable") from exc

    base = {
        "version": VERSION,
        "status": STATUS,
        "evidence_bundle_sha256": bundle["bundle_sha256"],
        "k_outcome": None,
        "formalizability_review": "NOT_APPLICABLE",
        "cited_evidence_count": 0,
        "cited_nonempty_observations": 0,
        "cited_truncated_observations": 0,
        "required_signal_count": 0,
        "condition_count": 0,
        "signal_metric_literal_matches": 0,
        "signal_metric_unit_literal_matches": 0,
        "contradictory_all_conditions": False,
        "physical_units_verified": False,
        "thresholds_empirically_validated": False,
        "diagnostic_correctness_verified": False,
        "causal_transfer_verified": False,
        "ood_test_performed": False,
        "api_calls_sent": 0,
        "record_or_files_written": False,
    }

    try:
        rule = validate_candidate_rule(raw_json, allowed_evidence_ids=ids)
    except ContractError:
        return {**base, "k_outcome": "INVALID_OUTPUT"}

    refs = set(rule["evidence_ids"])
    selected = [
        item for item in bundle["evidence"]
        if item["evidence_id"] in refs
    ]
    nonempty = sum(not item["observation_is_empty"] for item in selected)
    truncated = sum(item["truncated"] for item in selected)
    common = {
        **base,
        "cited_evidence_count": len(refs),
        "cited_nonempty_observations": nonempty,
        "cited_truncated_observations": truncated,
    }

    if rule["status"] == "insufficient_evidence":
        return {**common, "k_outcome": "INSUFFICIENT_EVIDENCE"}

    if rule["status"] != "candidate":
        # Defensive: existing strict validator should already reject this.
        raise KQualityReviewBlocked("Unexpected candidate status")

    texts = [
        item["observation_text"] for item in selected
        if not item["observation_is_empty"]
    ]
    metric_hits = 0
    metric_unit_hits = 0
    for signal in rule["required_signals"]:
        metric = signal["metric"]
        unit = signal["unit"]
        if any(_literal_occurs(metric, text) for text in texts):
            metric_hits += 1
        if any(
            _literal_occurs(metric, text) and _literal_occurs(unit, text)
            for text in texts
        ):
            metric_unit_hits += 1

    contradiction = _contradictory_all(
        rule["conditions"], rule["combination"],
    )
    return {
        **common,
        "k_outcome": "CANDIDATE",
        "formalizability_review": (
            "NOT_FORMALIZABLE_CONTRADICTION"
            if contradiction else "REQUIRES_VERIFICATION"
        ),
        "required_signal_count": len(rule["required_signals"]),
        "condition_count": len(rule["conditions"]),
        "signal_metric_literal_matches": metric_hits,
        "signal_metric_unit_literal_matches": metric_unit_hits,
        "contradictory_all_conditions": contradiction,
    }
