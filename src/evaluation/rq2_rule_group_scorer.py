"""RQ2-C offline-only GROUP-LEVEL rule outcome scorer (proposal V0).

Runs AFTER a scientific rule freeze and offline detector application.
It is NOT imported by agents or a live experiment runner. It is a pure
function: no files, provider, telemetry, model outputs or network access.

GROUND TRUTH BOUNDARY:
The caller (separate, evaluation-only process) must supply authoritative
group-level fault labels. NEVER pass this reference mapping to an LLM, tool,
discovery prompt, C or K stage. The scorer does not retrieve or export labels.
This module must never become a provider-side dependency.

One output per WHOLE time-window group (not per query). A two-fault group is
POSITIVE for each fault class present, even if two different query IDs are
attached. If reference completeness is uncertain, the group is explicitly
unscorable; it is not a "negative" by default.

This cannot determine whether a proposed rule is grounded, implementable,
causal, or frozen. It only scores already-frozen external detector outcomes.
"""
from __future__ import annotations

from collections import Counter

VERSION = "rq2_rule_window_group_scoring_v0"
DECISIONS = frozenset(("positive", "negative", "abstain", "error"))
MAX_GROUPS = 10_000
MAX_CLASSES = 100


class GroupScoringError(ValueError):
    """An isolated evaluation input is ambiguous or not properly grouped."""


def _check_id(value: object, label: str) -> str:
    if type(value) is not str or not value.strip() or len(value) > 256:
        raise GroupScoringError("Invalid " + label)
    return value


def evaluate_group_decisions(
    *,
    target_fault_type: str,
    known_fault_types: tuple[str, ...],
    group_references: list[dict],
    group_decisions: dict[str, str],
) -> dict:
    """Aggregate a single FROZEN detector's results by window group.

    group_references (GT-only, evaluation process):
        {
          "group_id": "G01",
          "case_ids": ["cloudbed-1_q..."],
          "fault_types": ["normalized-fault-type", ...],
          "reference_complete": true | false
        }
    group_decisions (NO labels, generated from frozen offline detector):
        {"G01": "positive" | "negative" | "abstain" | "error", ...}

    Labels and case IDs are deliberately NOT returned. Groups with unverified
    reference completeness are excluded from TP/TN/FP/FN denominators.
    """
    target = _check_id(target_fault_type, "target fault type")
    if type(known_fault_types) is not tuple or not (
        1 <= len(known_fault_types) <= MAX_CLASSES
    ):
        raise GroupScoringError("Closed evaluation taxonomy required")
    if any(type(x) is not str or not x.strip() for x in known_fault_types):
        raise GroupScoringError("Invalid evaluation taxonomy")
    if len(set(known_fault_types)) != len(known_fault_types):
        raise GroupScoringError("Duplicate evaluation taxonomy class")
    allowed = set(known_fault_types)
    if target not in allowed:
        raise GroupScoringError("Target not in frozen evaluation taxonomy")
    if type(group_references) is not list or not (
        1 <= len(group_references) <= MAX_GROUPS
    ):
        raise GroupScoringError("Expected nonempty bounded group list")
    if type(group_decisions) is not dict:
        raise GroupScoringError("Expected explicit group decisions mapping")

    groups = {}
    case_ids = set()
    for record in group_references:
        if type(record) is not dict or set(record) != {
            "group_id", "case_ids", "fault_types", "reference_complete"
        }:
            raise GroupScoringError("Unrecognized GT-only window-group schema")
        group_id = _check_id(record["group_id"], "group ID")
        if group_id in groups:
            raise GroupScoringError("Duplicate group ID")
        ids = record["case_ids"]
        if type(ids) is not list or not ids or any(
            type(cid) is not str or not cid.strip() for cid in ids
        ):
            raise GroupScoringError("Missing/non-string group case IDs")
        if len(set(ids)) != len(ids) or set(ids) & case_ids:
            raise GroupScoringError("Duplicate or cross-group case IDs")
        case_ids.update(ids)
        labels = record["fault_types"]
        if type(labels) is not list or any(
            type(label) is not str or label not in allowed for label in labels
        ) or len(set(labels)) != len(labels):
            raise GroupScoringError("Unsupported/duplicate group fault types")
        # Empty label list is legal for a verified healthy/other-control group.
        if type(record["reference_complete"]) is not bool:
            raise GroupScoringError("Reference completeness must be boolean")
        groups[group_id] = {
            "labels": set(labels),
            "reference_complete": record["reference_complete"],
        }

    if set(group_decisions) != set(groups) or any(
        type(decision) is not str or decision not in DECISIONS
        for decision in group_decisions.values()
    ):
        raise GroupScoringError("Missing/extra/invalid group decision")

    counts = Counter({
        "tp": 0, "fn": 0, "tn": 0, "fp": 0,
        "abstain_positive": 0, "abstain_negative": 0,
        "error_positive": 0, "error_negative": 0,
        "reference_unscorable_groups": 0,
        "complete_positive_groups": 0, "complete_negative_groups": 0,
        "multi_fault_groups": 0,
    })
    for group_id, reference in groups.items():
        if len(reference["labels"]) > 1:
            counts["multi_fault_groups"] += 1
        if not reference["reference_complete"]:
            counts["reference_unscorable_groups"] += 1
            continue
        positive = target in reference["labels"]
        counts[
            "complete_positive_groups" if positive else
            "complete_negative_groups"
        ] += 1
        decision = group_decisions[group_id]
        if decision == "abstain":
            counts["abstain_positive" if positive else "abstain_negative"] += 1
        elif decision == "error":
            counts["error_positive" if positive else "error_negative"] += 1
        elif decision == "positive":
            counts["tp" if positive else "fp"] += 1
        else:
            counts["fn" if positive else "tn"] += 1

    evaluated = sum(counts[name] for name in ("tp", "fn", "fp", "tn"))
    eligible = sum(counts[name] for name in (
        "complete_positive_groups", "complete_negative_groups"
    ))
    predicted_positive = counts["tp"] + counts["fp"]
    actual_positive = counts["tp"] + counts["fn"]
    actual_negative = counts["tn"] + counts["fp"]
    # Do not silently make abstentions/errors false negatives: return their
    # denominators, and leave rates undefined when no hard decisions exist.
    return {
        "scorer_version": VERSION,
        "status": "OFFLINE_EVALUATION_ONLY",
        "target_fault_type": target,
        "total_window_groups": len(groups),
        "counts": dict(sorted(counts.items())),
        "hard_decisions": evaluated,
        "reference_complete_groups": eligible,
        "decision_coverage": evaluated / eligible if eligible else None,
        "precision_on_hard_decisions": (
            counts["tp"] / predicted_positive if predicted_positive else None
        ),
        "recall_on_hard_decisions": (
            counts["tp"] / actual_positive if actual_positive else None
        ),
        "specificity_on_hard_decisions": (
            counts["tn"] / actual_negative if actual_negative else None
        ),
        "scoring_unit": "temporal_window_group",
        "reads_ground_truth_from_caller": True,
        "reads_files": False,
        "model_api_calls": 0,
        "files_written": False,
        "caveats": [
            "This is a scoring metric, not a detector or an implementation of LLM pseudocode.",
            "The reference mapping must be held only by an offline evaluation process.",
            "Rates conditional on hard decisions exclude abstentions and errors; examine coverage.",
            "Multi-fault groups are positive for every target class present in the group.",
            "A window-group is not necessarily a physically independent fault injection.",
            "No model/protocol/rule freeze, independence or scientific generalization is certified.",
        ],
    }
