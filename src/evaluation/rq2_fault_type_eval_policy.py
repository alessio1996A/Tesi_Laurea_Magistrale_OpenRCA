"""RQ2-A frozen-CANDIDATE class normalization and offline-only scoring.

Evaluation process ONLY. NEVER import into agent, inference, prompts, tool
runtime, C/K stage construction, discovery or any provider transport.
Reference labels must be supplied by a separate GT-isolated evaluator.
No files, network, model calls or case->label mappings are emitted.

Taxonomy comes from the four official reason spellings inventoried BEFORE
any RQ2 OOD inference. No fuzzy matching, subjective semantic equivalence,
post-hoc alias additions or use of model predictions to tune this policy.
"""
from __future__ import annotations

import re
from collections import Counter

VERSION = "rq2_fault_type_eval_policy_v1_candidate"
CANONICAL = (
    "node CPU spike",
    "container write I/O load",
    "container process termination",
    "container packet loss",
)
# Lexical normalization only: punctuation, capitalization, space and "IO"
# spelling. NO semantic synonyms, fuzzy substrings or case-specific rules.
_ALIASES = {
    "node cpu spike": CANONICAL[0],
    "container write i o load": CANONICAL[1],
    "container write io load": CANONICAL[1],
    "container process termination": CANONICAL[2],
    "container packet loss": CANONICAL[3],
}
_VALID_STATUSES = frozenset((
    "RECORDED_COMPLETE", "INVALID_OUTPUT", "PROVIDER_ERROR",
    "BLOCKED_DEPENDENCY",
))


class RQ2FaultEvalError(ValueError):
    """Unverifiable offline scoring input; never guess missing references."""


def normalized_text(value: str) -> str:
    """Only lower/case/punctuation/ASCII whitespace normalization."""
    if type(value) is not str or len(value) > 2000:
        raise RQ2FaultEvalError("Invalid prediction label text")
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def canonical_fault_type(predicted_fault_type: str) -> str | None:
    """Strict, preregistered lexical aliases; None means unmatched, not abstain."""
    return _ALIASES.get(normalized_text(predicted_fault_type))


def _validate_reference(case_ids: tuple[str, ...], reference_labels: dict[str, str]):
    if (
        type(case_ids) is not tuple or not case_ids
        or any(type(x) is not str or not x.strip() for x in case_ids)
        or len(set(case_ids)) != len(case_ids)
        or type(reference_labels) is not dict
        or set(case_ids) != set(reference_labels)
        or any(type(label) is not str or label not in CANONICAL
               for label in reference_labels.values())
    ):
        raise RQ2FaultEvalError("Incomplete or noncanonical GT reference")


def _validate_predictions(case_ids: tuple[str, ...], predictions: list[dict]):
    if type(predictions) is not list:
        raise RQ2FaultEvalError("Expected prediction list")
    allowed = set(case_ids)
    seen = set()
    for item in predictions:
        if type(item) is not dict or set(item) != {
            "case_id", "stage_status", "decision", "predicted_fault_type"
        }:
            raise RQ2FaultEvalError("Unexpected prediction schema")
        case_id, status = item["case_id"], item["stage_status"]
        if type(case_id) is not str or case_id not in allowed or case_id in seen:
            raise RQ2FaultEvalError("Unknown or duplicate case in predictions")
        seen.add(case_id)
        if type(status) is not str or status not in _VALID_STATUSES:
            raise RQ2FaultEvalError("Unexpected stage status")
        decision = item["decision"]
        label = item["predicted_fault_type"]
        if status != "RECORDED_COMPLETE":
            if decision is not None or label is not None:
                raise RQ2FaultEvalError("Failed stage cannot contain parsed prediction")
        elif decision == "abstain":
            if label is not None:
                raise RQ2FaultEvalError("Abstention asserted a class")
        elif decision == "diagnosis":
            if type(label) is not str or not label.strip():
                raise RQ2FaultEvalError("Diagnosis without a fault type")
        else:
            raise RQ2FaultEvalError("Invalid C probe decision")


def _classify(case_id: str, prediction: dict | None, reference: dict[str, str]):
    if prediction is None:
        return "missing", False
    status = prediction["stage_status"]
    if status != "RECORDED_COMPLETE":
        return {
            "INVALID_OUTPUT": "invalid_output",
            "PROVIDER_ERROR": "provider_error",
            "BLOCKED_DEPENDENCY": "blocked_dependency",
        }[status], False
    if prediction["decision"] == "abstain":
        return "abstain", False
    mapped = canonical_fault_type(prediction["predicted_fault_type"])
    if mapped is None:
        return "unmatched_diagnosis", False
    return ("correct" if mapped == reference[case_id] else "wrong_known_class"), (
        mapped == reference[case_id]
    )


def score_cause_cases(
    *, case_ids: tuple[str, ...], reference_labels: dict[str, str],
    predictions: list[dict],
) -> dict:
    """Aggregate a *single* model+harness arm; do not output GT or case IDs.

    The authoritative reference mapping must be created and used ONLY in a
    separate offline evaluation process after test outputs are immutable.
    Missing stage artifacts remain in the planned denominator.
    """
    _validate_reference(case_ids, reference_labels)
    _validate_predictions(case_ids, predictions)
    by_case = {item["case_id"]: item for item in predictions}
    tally = Counter({
        "correct": 0, "wrong_known_class": 0, "unmatched_diagnosis": 0,
        "abstain": 0, "invalid_output": 0, "provider_error": 0,
        "blocked_dependency": 0, "missing": 0,
    })
    for case_id in case_ids:
        category, _ = _classify(case_id, by_case.get(case_id), reference_labels)
        tally[category] += 1
    planned = len(case_ids)
    diagnosed = sum(tally[k] for k in (
        "correct", "wrong_known_class", "unmatched_diagnosis"
    ))
    valid = diagnosed + tally["abstain"]
    return {
        "policy_version": VERSION,
        "evaluation_only": True,
        "total_planned": planned,
        "counts": dict(sorted(tally.items())),
        "accuracy_planned": tally["correct"] / planned,
        "diagnostic_coverage_planned": diagnosed / planned,
        "valid_contract_coverage_planned": valid / planned,
        "accuracy_among_diagnoses": (
            tally["correct"] / diagnosed if diagnosed else None
        ),
        "accuracy_among_valid_contracts": (
            tally["correct"] / valid if valid else None
        ),
        "reference_labels_exported": False,
        "case_label_mapping_exported": False,
        "reads_files": False,
        "provider_calls": 0,
        "caveat": (
            "Small cohort; stages, cases and independent fault injections "
            "are not equivalent. Missing/error/abstain stay in planned denominator."
        ),
    }


def paired_harness_outcomes(
    *, case_ids: tuple[str, ...], reference_labels: dict[str, str],
    a1: list[dict], a1_8r: list[dict],
) -> dict:
    """Win/tie/loss: correct C fault class on identical case+model (not CI)."""
    _validate_reference(case_ids, reference_labels)
    for predictions in (a1, a1_8r):
        _validate_predictions(case_ids, predictions)
    p1 = {v["case_id"]: v for v in a1}
    p8 = {v["case_id"]: v for v in a1_8r}
    counts = Counter({"win_A1_8R": 0, "tie": 0, "loss_A1_8R": 0})
    for case_id in case_ids:
        _, hit1 = _classify(case_id, p1.get(case_id), reference_labels)
        _, hit8 = _classify(case_id, p8.get(case_id), reference_labels)
        counts[
            "win_A1_8R" if hit8 and not hit1
            else "loss_A1_8R" if hit1 and not hit8
            else "tie"
        ] += 1
    return {
        "policy_version": VERSION,
        "paired_cases": len(case_ids),
        "counts": dict(sorted(counts.items())),
        "reference_labels_exported": False,
        "provider_calls": 0,
        "note": (
            "Descriptive paired counts only. Correlated windows must be "
            "clustered if uncertainty intervals are later calculated."
        ),
    }
