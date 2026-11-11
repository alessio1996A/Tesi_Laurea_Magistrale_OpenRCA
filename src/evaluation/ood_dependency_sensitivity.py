"""GT-controlled, read-only sensitivity audit for possible OOD incident dependencies.

Reads original record.csv ONLY in this evaluation-side tool; validates alignment
using aggregate_ood_classes; never reveals case -> label or component mapping.
It assesses shared time windows and SAME-cloudbed SAME-reason SAME-component
record-time proximity at fixed thresholds. These are risk proxies, not causal
independence proof. No LLM/API/telemetry access, no case allocation, no writes.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from evaluation.ood_class_inventory import (
    SCHEMAS, TARGET_REASONS, _load_member, _normalized,
    aggregate_ood_classes,
)
from evaluation.v2_case_window_audit import (
    MANIFEST_COLUMNS, SPLIT_COLUMNS, _overlap, _read_csv,
)

SECONDS_THRESHOLDS = (0, 1800, 3600, 7200, 14400)


def _cluster(n: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in edges:
        a, b = find(i), find(j)
        if a != b:
            parent[b] = a
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def dependency_sensitivity(
    data_dir: Path, *, verify_original_hashes: bool = True,
) -> dict:
    root = Path(data_dir)
    # FULL upstream verification, including row -> record + scoring fields.
    prior = aggregate_ood_classes(root, verify_original_hashes=verify_original_hashes)
    if prior["classification_status"] != "complete":
        raise ValueError("Unknown OOD labels: resolve naming before dependence audit")
    split = _read_csv(root / "data/processed/split_market_v1.csv", SPLIT_COLUMNS)
    manifest = _read_csv(
        root / "data/processed/benchmark_inputs_market.csv", MANIFEST_COLUMNS
    )
    record_rows = {}
    with ZipFile(root / "Market.zip", "r") as z:
        for bed in ("cloudbed-1", "cloudbed-2"):
            record_rows[bed], _ = _load_member(
                z, f"Market/{bed}/record.csv", SCHEMAS["record"]
            )

    # Key order is private and never emitted. Deliberately do not generate
    # a row-level case/label/result report.
    items = []
    for case_id, row in sorted(split.items()):
        if row["split"] != "ood_holdout":
            continue
        metadata = manifest[case_id]
        bed = row["cloudbed"]
        record_index = int(metadata["query_index"])
        record = record_rows[bed][record_index]
        reason = TARGET_REASONS.get(_normalized(record["reason"]))
        if reason is None:
            raise ValueError("Unrecognized OOD class")
        items.append({
            "bed": bed,
            "reason": reason,
            "component": _normalized(record["component"]),
            "timestamp": int(record["timestamp"]),
            "window": row,
        })

    overlap_edges = []
    for i, a in enumerate(items):
        for j in range(i + 1, len(items)):
            if _overlap(a["window"], items[j]["window"]):
                overlap_edges.append((i, j))

    thresholds = {}
    for threshold in SECONDS_THRESHOLDS:
        near_edges = []
        for i, a in enumerate(items):
            for j in range(i + 1, len(items)):
                b = items[j]
                if (
                    a["bed"] == b["bed"]
                    and a["reason"] == b["reason"]
                    and a["component"] == b["component"]
                    and abs(a["timestamp"] - b["timestamp"]) <= threshold
                ):
                    near_edges.append((i, j))
        base = set(overlap_edges)
        edges = sorted(base | set(near_edges))
        groups = _cluster(len(items), edges)
        per_class_groups = Counter()
        for group in groups:
            present = {items[i]["reason"] for i in group}
            per_class_groups.update(present)
        thresholds[str(threshold)] = {
            "proximity_threshold_seconds": threshold,
            "candidate_dependency_groups": len(groups),
            "group_size_histogram": dict(sorted(Counter(
                len(group) for group in groups
            ).items())),
            "same_reason_component_temporal_pairs": len(near_edges),
            "additional_pairs_beyond_window_overlap": len(
                set(near_edges) - base
            ),
            "groups_containing_class": {
                label: per_class_groups[label]
                for label in TARGET_REASONS.values()
            },
        }

    return {
        "audit": "ood_dependency_sensitivity_controlled_gt_v1",
        "source_verified": verify_original_hashes,
        "split_sha256": prior["split_sha256"],
        "manifest_sha256": prior["manifest_sha256"],
        "ood_query_count": len(items),
        "shared_window_pairs": len(overlap_edges),
        "threshold_sensitivity": thresholds,
        "read_ground_truth": True,
        "read_telemetry": False,
        "read_predictions": False,
        "model_api_calls": 0,
        "files_written": False,
        "emits_case_label_mapping": False,
        "methodological_limitations": [
            "Temporal proximity + identical reason and component is ONLY a proxy for dependence.",
            "Lack of shared reason/component/proximity does NOT prove independent fault injections.",
            "Groups are sensitivity scenarios, NOT preregistered discovery/test cohorts.",
            "Ground truth read only by evaluation tool, not by any agent.",
            "Any candidate discovery/test allocation must keep all shared-window rows together.",
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", type=Path, required=True)
    result = dependency_sensitivity(p.parse_args().data_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
