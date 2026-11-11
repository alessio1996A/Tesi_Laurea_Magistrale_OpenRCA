"""OFFLINE EVALUATION-ONLY RQ2 allocation preview. Never import into agent.

A deterministic, stratified allocation: one SINGLETON-window discovery query
per held-out class, rest test; shared windows are indivisible and tested.
Uses GT only within this offline module to stratify; emits no case->class map.
NO files written, NO inference, NO scorer. DRAFT status is not executable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from evaluation.ood_class_inventory import (
    SCHEMAS, TARGET_REASONS, TARGETS, _load_member, _normalized,
    aggregate_ood_classes,
)
from evaluation.ood_holdout_preflight import inventory_ood
from evaluation.v2_case_window_audit import MANIFEST_COLUMNS, SPLIT_COLUMNS, _read_csv

# The value is a public, versioned tie-breaker, NOT a secret or proof of randomness.
SALT = "openrca-rq2-singleton-stratified-preview-v0-2026-11-11"


def _rank(case_id: str) -> str:
    return hashlib.sha256(f"{SALT}\0{case_id}".encode("utf-8")).hexdigest()


def propose_partition(
    data_dir: Path, *, verify_original_hashes: bool = True,
) -> dict:
    """Preview a deterministic group-safe allocation, no records persisted."""
    root = Path(data_dir)
    classified = aggregate_ood_classes(
        root, verify_original_hashes=verify_original_hashes
    )
    if classified["classification_status"] != "complete":
        raise ValueError("Unrecognized OOD class: cannot stratify")
    audit = inventory_ood(root, verify_original_hashes=verify_original_hashes)
    split = _read_csv(root / "data/processed/split_market_v1.csv", SPLIT_COLUMNS)
    manifest = _read_csv(
        root / "data/processed/benchmark_inputs_market.csv", MANIFEST_COLUMNS
    )

    # Evaluation-only transient labels, never exported or stored.
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
            bed = row["cloudbed"]
            index = int(manifest[case_id]["query_index"])
            reason = TARGET_REASONS.get(
                _normalized(records[bed][index]["reason"])
            )
            if reason is None:
                raise ValueError("Unknown target in OOD label")
            labels[case_id] = reason

    groups = audit["ood_window_groups"]
    if len(groups) != audit["ood_window_groups_count"]:
        raise ValueError("Inconsistent OOD window-group count")
    if set(labels) != {cid for group in groups for cid in group}:
        raise ValueError("GT group and split case IDs do not match")
    eligible = {name: [] for name in TARGETS}
    for group in groups:
        if len(group) == 1:
            case_id = group[0]
            eligible[labels[case_id]].append(case_id)

    discovery = set()
    for name in TARGETS:
        if not eligible[name]:
            raise ValueError("No singleton discovery window for a target class")
        chosen = min(eligible[name], key=lambda cid: (_rank(cid), cid))
        discovery.add(chosen)
    if len(discovery) != len(TARGETS):
        raise ValueError("Discovery case IDs duplicated across target classes")

    preview_groups = []
    seen = set()
    for group in groups:
        ids = sorted(group)
        phase = "discovery" if any(cid in discovery for cid in ids) else "test"
        if phase == "discovery" and (len(ids) != 1 or ids[0] not in discovery):
            raise ValueError("Shared window crossed discovery boundary")
        if not seen.isdisjoint(ids):
            raise ValueError("Case ID occurs in multiple groups")
        seen.update(ids)
        preview_groups.append({"phase": phase, "case_ids": ids})
    all_ood = {cid for cid, row in split.items() if row["split"] == "ood_holdout"}
    if seen != all_ood:
        raise ValueError("Partition does not cover all OOD cases")

    test = all_ood - discovery
    balance = {
        name: {
            "discovery_query_count": sum(labels[cid] == name for cid in discovery),
            "test_query_count": sum(labels[cid] == name for cid in test),
        }
        for name in TARGETS
    }
    if any(x["discovery_query_count"] != 1 for x in balance.values()):
        raise ValueError("Discovery one-per-class invariant failed")

    return {
        "audit": "rq2_stratified_partition_preview_v0",
        "status": "DRAFT_NOT_EXECUTABLE",
        "source_verified": verify_original_hashes,
        "split_sha256": audit["split_sha256"],
        "manifest_sha256": audit["manifest_sha256"],
        "selection_salt": SALT,
        "selection_method": "min_sha256_over_singleton_windows_per_gt_class",
        "discovery_query_count": len(discovery),
        "test_query_count": len(test),
        "discovery_window_groups": sum(
            item["phase"] == "discovery" for item in preview_groups
        ),
        "test_window_groups": sum(
            item["phase"] == "test" for item in preview_groups
        ),
        "class_balance_aggregate_only": balance,
        "discovery_case_ids": sorted(discovery),
        "test_case_ids": sorted(test),
        "window_groups": preview_groups,
        "read_ground_truth": True,
        "emits_case_label_mapping": False,
        "read_telemetry": False,
        "read_predictions": False,
        "model_api_calls": 0,
        "files_written": False,
        "limitations": [
            "THIS IS ONLY A PREVIEW; it is not a frozen plan or API authorization.",
            "GT used offline for allocation; never pass labels to an agent.",
            "One discovery sample per class is too small for rule tuning.",
            "No independent fault-injection identity has been verified.",
            "Shared-window and multi-fault records require group-level negative controls.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parsed = parser.parse_args()
    print(json.dumps(propose_partition(parsed.data_dir), indent=2,
                     ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
