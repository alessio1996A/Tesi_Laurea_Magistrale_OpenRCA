"""RQ2 V1 DRAFT partition: group-safe, cloudbed-balanced, adjacency-aware.

Offline EVALUATION ONLY. GT is needed for per-class stratification but never
exported as case -> label. The generated plan is NOT executable or frozen.
No model calls, telemetry reads, writes, or scoring. Never import into agents.

Predeclared selection priorities (lexicographic):
1. One singleton discovery per OOD class, shared-window group stays in test;
2. Preserve at least one TEST example on every originally represented cloudbed
   for each class; forbid any discovery whose window TOUCHES another OOD window;
3. Balance discovery cloudbeds (2/2) as closely as possible;
4. Minimize discovery/test same-cloudbed window proximity <= 1 hour;
5. Fixed SHA256 tiebreaker, not provider outcomes or test accuracy.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from evaluation.ood_class_inventory import (
    SCHEMAS, TARGET_REASONS, TARGETS, _load_member, _normalized,
    aggregate_ood_classes,
)
from evaluation.ood_holdout_preflight import inventory_ood
from evaluation.v2_case_window_audit import (
    MANIFEST_COLUMNS, SPLIT_COLUMNS, _read_csv, _window
)

SALT = "openrca-rq2-ood-balanced-group-safe-v1-2026-11-11"
NEAR_TEST_SECONDS = 3600


def _gap(a: dict, b: dict) -> int | None:
    """Seconds between non-overlapping windows; 0 for touching/overlapping.

    Different cloudbeds have no defined temporal proximity in this protocol.
    """
    if a["cloudbed"] != b["cloudbed"]:
        return None
    a0, a1 = _window(a)
    b0, b1 = _window(b)
    return max(0, a0 - b1, b0 - a1)


def _rank(ids: tuple[str, ...]) -> str:
    return hashlib.sha256(
        (SALT + "\0" + "\0".join(sorted(ids))).encode("utf-8")
    ).hexdigest()


def propose_partition_v1(
    data_dir: Path, *, verify_original_hashes: bool = True,
) -> dict:
    """A fully deterministic, GT-isolated candidate split, never runnable."""
    root = Path(data_dir)
    classified = aggregate_ood_classes(
        root, verify_original_hashes=verify_original_hashes
    )
    if classified["classification_status"] != "complete":
        raise ValueError("Unrecognized classes: cannot select discovery")
    audit = inventory_ood(root, verify_original_hashes=verify_original_hashes)
    split = _read_csv(root / "data/processed/split_market_v1.csv", SPLIT_COLUMNS)
    manifest = _read_csv(
        root / "data/processed/benchmark_inputs_market.csv", MANIFEST_COLUMNS
    )

    # Transient GT mapping exists ONLY inside this evaluation function.
    labels = {}
    with ZipFile(root / "Market.zip", "r") as z:
        records = {}
        for bed in ("cloudbed-1", "cloudbed-2"):
            records[bed], _ = _load_member(
                z, f"Market/{bed}/record.csv", SCHEMAS["record"]
            )
        for case_id, row in split.items():
            if row["split"] != "ood_holdout":
                continue
            record = records[row["cloudbed"]][int(manifest[case_id]["query_index"])]
            label = TARGET_REASONS.get(_normalized(record["reason"]))
            if label is None:
                raise ValueError("Unknown OOD class during selection")
            labels[case_id] = label

    groups = audit["ood_window_groups"]
    if len(groups) != audit["ood_window_groups_count"]:
        raise ValueError("Unexpected group count")
    all_ids = set(labels)
    if all_ids != {cid for group in groups for cid in group}:
        raise ValueError("Window groups differ from OOD cohort")
    if len(all_ids) != 15 and verify_original_hashes:
        raise ValueError("Original OOD cohort must have 15 queries")

    # By construction only singleton groups can become discovery.
    # Additionally reject windows touching ANY other OOD window, including
    # distinct-class adjacent events, even if the matching group is in test.
    eligible = {name: [] for name in TARGETS}
    for group in groups:
        if len(group) != 1:
            continue
        cid = group[0]
        if any(
            other != cid and _gap(split[cid], split[other]) == 0
            for other in all_ids
        ):
            continue
        eligible[labels[cid]].append(cid)
    for name in TARGETS:
        if not eligible[name]:
            raise ValueError("No isolated singleton discovery for a target class")

    by_class_bed = {
        name: Counter(
            split[cid]["cloudbed"] for cid in all_ids if labels[cid] == name
        )
        for name in TARGETS
    }

    # Search space at most 15^4; in real Market cohort it is far smaller.
    # All decisions use only reference class for stratification, cloudbed,
    # window metadata and a fixed salt. Never LLM predictions or scores.
    valid = []
    for proposed in itertools.product(*(sorted(eligible[n]) for n in TARGETS)):
        discovery = set(proposed)
        if len(discovery) != len(TARGETS):
            continue
        # Preserve at least one test example on each bed where a class exists.
        preserve_test_bed_coverage = all(
            count > sum(
                cid in discovery and labels[cid] == name
                and split[cid]["cloudbed"] == bed
                for cid in all_ids
            )
            for name, bed_counts in by_class_bed.items()
            for bed, count in bed_counts.items()
        )
        if not preserve_test_bed_coverage:
            continue

        test = all_ids - discovery
        c1 = sum(split[cid]["cloudbed"] == "cloudbed-1" for cid in discovery)
        imbalance = abs(len(discovery) - 2 * c1)
        near_cross_phase_pairs = sum(
            gap is not None and gap <= NEAR_TEST_SECONDS
            for cid in discovery for other in test
            for gap in [_gap(split[cid], split[other])]
        )
        # Select balanced, less proximate, then hash-tied candidates.
        rank = (imbalance, near_cross_phase_pairs, _rank(tuple(proposed)))
        valid.append((rank, tuple(proposed)))
    if not valid:
        raise ValueError("No split preserves per-cloudbed TEST class coverage")
    rank, chosen = min(valid)
    discovery = set(chosen)
    test = all_ids - discovery
    phase_groups = [
        {"phase": "discovery" if group[0] in discovery else "test",
         "case_ids": sorted(group)}
        for group in groups
    ]
    for item in phase_groups:
        ids = item["case_ids"]
        if item["phase"] == "discovery" and (
            len(ids) != 1 or ids[0] not in discovery
        ):
            raise ValueError("Inseparable window group crossed phase")
    if len(discovery) != 4 or len(test) != 11:
        raise ValueError("Unexpected partition size")
    if not all(
        sum(labels[cid] == name for cid in discovery) == 1 for name in TARGETS
    ):
        raise ValueError("One discovery per class invariant violated")

    min_cross_phase_gap = min(
        (gap for cid in discovery for other in test
         if (gap := _gap(split[cid], split[other])) is not None),
        default=None,
    )
    counts = {
        name: {
            "discovery_queries": 1,
            "test_queries": sum(labels[cid] == name for cid in test),
            "cloudbeds_represented_in_test": sum(
                any(labels[cid] == name and split[cid]["cloudbed"] == bed
                    for cid in test)
                for bed in ("cloudbed-1", "cloudbed-2")
            ),
        }
        for name in TARGETS
    }
    return {
        "audit": "rq2_partition_preview_balanced_v1",
        "status": "DRAFT_NOT_EXECUTABLE",
        "source_verified": verify_original_hashes,
        "split_sha256": audit["split_sha256"],
        "manifest_sha256": audit["manifest_sha256"],
        "selection_salt": SALT,
        "selection_objective": [
            "one isolated singleton discovery per OOD class",
            "never split shared windows; preserve per-cloudbed test coverage",
            "minimize discovery cloudbed imbalance",
            "minimize discovery-test near pairs within 3600s across same cloudbed",
            "break ties using SHA256 of sorted discovery IDs and fixed salt",
        ],
        "eligible_candidate_count_aggregate": sum(map(len, eligible.values())),
        "valid_candidate_partitions_count": len(valid),
        "discovery_query_count": len(discovery),
        "test_query_count": len(test),
        "discovery_window_groups": sum(
            item["phase"] == "discovery" for item in phase_groups
        ),
        "test_window_groups": sum(
            item["phase"] == "test" for item in phase_groups
        ),
        "discovery_by_cloudbed": dict(sorted(Counter(
            split[cid]["cloudbed"] for cid in discovery
        ).items())),
        "test_by_cloudbed": dict(sorted(Counter(
            split[cid]["cloudbed"] for cid in test
        ).items())),
        "class_balance_aggregate_only": counts,
        "cross_phase_near_pairs_3600s": rank[1],
        "min_discovery_test_gap_same_cloudbed_seconds": min_cross_phase_gap,
        "discovery_case_ids": sorted(discovery),
        "test_case_ids": sorted(test),
        "window_groups": phase_groups,
        "read_ground_truth": True,
        "read_telemetry": False,
        "read_predictions": False,
        "model_api_calls": 0,
        "files_written": False,
        "emits_case_label_mapping": False,
        "limitations": [
            "NOT FROZEN or runnable. V0 preview remains preserved.",
            "Balancing cloudbeds does not prove independent injections.",
            "No predictor outcomes used; GT held only in evaluation-side memory.",
            "One discovery per class and tiny test positives: feasibility only.",
            "Multi-fault group must use all-window GT for negative controls.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(propose_partition_v1(args.data_dir),
                     indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
