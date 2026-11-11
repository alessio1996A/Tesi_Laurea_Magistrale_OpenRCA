"""Controlled label inventory for phase-2 OOD cases. Evaluation-only, NOT agent code.

This module reads OpenRCA ground truth from record.csv and query scoring_points
in the two ORIGINAL Market.zip cloudbeds. Its JSON output is aggregate-only:
NEVER contains case ID -> class, row labels, timestamp/label associations,
prompts, or telemetry. No LLM calls, no file writes, no case selection.

IMPORTANT: unlike prior GT-free preflights, this audit DOES access GT.
Run separately from inference. Do not import into the agent or its tools.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from evaluation.ood_holdout_preflight import inventory_ood
from evaluation.v2_case_window_audit import (
    MANIFEST_COLUMNS, SPLIT_COLUMNS, _read_csv, _window,
)

# Exact normalized benchmark reason values only. No fuzzy substring matches:
# unknown labels are exposed only as AGGREGATES for manual nomenclature review.
TARGET_REASONS = {
    "node cpu spike": "node CPU spike",
    "container write i o load": "container write I/O load",
    "container process termination": "container process termination",
    "container packet loss": "container packet loss",
}
TARGETS = tuple(TARGET_REASONS.values())
SCHEMAS = {
    "query": {"task_index", "instruction", "scoring_points"},
    "record": {"timestamp", "level", "component", "reason", "datetime"},
}
TASKS_REASON = frozenset({"task_2", "task_4", "task_6", "task_7"})
TASKS_COMPONENT = frozenset({"task_3", "task_5", "task_6", "task_7"})
TASKS_TIME = frozenset({"task_1", "task_4", "task_5", "task_7"})


def _normalized(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _load_member(z: ZipFile, member: str, fields: set[str]) -> tuple[list[dict], str]:
    candidates = [name for name in z.namelist() if name == member]
    if len(candidates) != 1:
        raise ValueError(f"Archive source missing/duplicated: {member}")
    raw = z.read(member)  # Only small reference CSVs, never telemetry.
    digest = hashlib.sha256(raw).hexdigest()
    try:
        stream = io.StringIO(raw.decode("utf-8-sig"), newline="")
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)) or set(headers) != fields:
            raise ValueError(f"Unexpected source CSV schema: {member}")
        rows = list(reader)
    except UnicodeDecodeError as exc:
        raise ValueError(f"CSV encoding not UTF-8: {member}") from exc
    if not rows or any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError(f"Empty/malformed source: {member}")
    return rows, digest


def aggregate_ood_classes(
    data_dir: Path, *, verify_original_hashes: bool = True,
) -> dict:
    """Validate record/query alignment, output class-level aggregate counts only."""
    root = Path(data_dir)
    prior = inventory_ood(root, verify_original_hashes=verify_original_hashes)
    split = _read_csv(
        root / "data/processed/split_market_v1.csv", SPLIT_COLUMNS
    )
    manifest = _read_csv(
        root / "data/processed/benchmark_inputs_market.csv", MANIFEST_COLUMNS
    )
    if set(split) != set(manifest):
        raise ValueError("Split and GT-free manifest case IDs differ")

    archive = root / "Market.zip"
    source_sha = {}
    rows_by_bed = {}
    with ZipFile(archive, "r") as z:
        for bed in ("cloudbed-1", "cloudbed-2"):
            base = f"Market/{bed}"
            query_rows, query_sha = _load_member(
                z, base + "/query.csv", SCHEMAS["query"]
            )
            record_rows, record_sha = _load_member(
                z, base + "/record.csv", SCHEMAS["record"]
            )
            if len(query_rows) != len(record_rows):
                raise ValueError(f"Query/record row counts differ: {bed}")
            rows_by_bed[bed] = (query_rows, record_rows)
            source_sha[bed] = {
                "query_csv_sha256": query_sha,
                "record_csv_sha256": record_sha,
                "query_rows": len(query_rows),
                "record_rows": len(record_rows),
            }

    # Verify provenance for ALL manifest cases, not just the OOD selection.
    # The official generator creates one query for each record in row order.
    # Only after these checks may row index be treated as GT record index.
    linked = {}
    for case_id, entry in manifest.items():
        source_split = split[case_id]
        bed = entry["cloudbed"]
        if bed not in rows_by_bed or source_split["cloudbed"] != bed:
            raise ValueError("Inconsistent cloudbed assignment")
        match = re.fullmatch(r"(cloudbed-[12])_q(\d+)", case_id)
        if match is None or match.group(1) != bed:
            raise ValueError("Invalid case ID formatting")
        try:
            row_index = int(entry["query_index"])
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid query_index in manifest") from exc
        if row_index != int(match.group(2)):
            raise ValueError(f"Query index mismatch: {case_id}")
        query, record = rows_by_bed[bed]
        if not 0 <= row_index < len(query):
            raise ValueError(f"Query index outside archive: {case_id}")
        q, rec = query[row_index], record[row_index]
        if q["task_index"] != entry["task_index"]:
            raise ValueError(f"Task mismatch in archived query: {case_id}")
        if q["instruction"] != entry["instruction"]:
            raise ValueError(f"Instruction mismatch in archived query: {case_id}")
        try:
            timestamp = int(rec["timestamp"])
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid record timestamp for {case_id}") from exc
        start, end = _window(entry)
        if not start <= timestamp < end:
            raise ValueError(f"Record outside manifest time window: {case_id}")
        if not rec["reason"].strip() or not rec["component"].strip():
            raise ValueError(f"Missing record cause fields: {case_id}")

        # For multi-failure tasks, the score text may contain OTHER records
        # too; require the current record fields to appear, never infer an
        # episode merely because its timestamp is in a shared window.
        score = q["scoring_points"]
        task = q["task_index"]
        if task in TASKS_REASON and rec["reason"] not in score:
            raise ValueError(f"Record reason absent from scoring points: {case_id}")
        if task in TASKS_COMPONENT and rec["component"] not in score:
            raise ValueError(f"Record component absent from scoring points: {case_id}")
        if task in TASKS_TIME and rec["datetime"] not in score:
            raise ValueError(f"Record datetime absent from scoring points: {case_id}")
        linked[case_id] = {
            "reason": rec["reason"],
            "record_index": row_index,
            "cloudbed": bed,
            "task_index": task,
        }

    # Partition ONLY the OOD cohort using labels in memory; no label map
    # is written to disk or printed.
    ood_ids = [
        case_id for case_id, row in split.items() if row["split"] == "ood_holdout"
    ]
    groups = prior["ood_window_groups"]
    group_class_sets = []
    unknown_labels = Counter()
    counts = Counter()
    per_bed = {bed: Counter() for bed in rows_by_bed}
    per_task_reason = Counter()
    seen_records = set()
    for case_id in ood_ids:
        r = linked[case_id]
        record_key = (r["cloudbed"], r["record_index"])
        if record_key in seen_records:
            raise ValueError("Same original fault record referenced twice")
        seen_records.add(record_key)
        label = TARGET_REASONS.get(_normalized(r["reason"]))
        if label is None:
            unknown_labels[r["reason"]] += 1
        else:
            counts[label] += 1
            per_bed[r["cloudbed"]][label] += 1
            if r["task_index"] in TASKS_REASON:
                per_task_reason[label] += 1
    for group in groups:
        classes = {
            TARGET_REASONS[_normalized(linked[case_id]["reason"])]
            for case_id in group
            if _normalized(linked[case_id]["reason"]) in TARGET_REASONS
        }
        group_class_sets.append(classes)

    counts_by_group = {
        label: sum(label in group for group in group_class_sets)
        for label in TARGETS
    }
    return {
        "audit": "ood_class_inventory_controlled_gt_v1",
        "source_verified": verify_original_hashes,
        "split_sha256": prior["split_sha256"],
        "manifest_sha256": prior["manifest_sha256"],
        "source_csv_sha256": source_sha,
        "alignment_checked_manifest_cases": len(linked),
        "ood_query_count": len(ood_ids),
        "ood_disjoint_window_groups": len(groups),
        "known_target_reason_query_count": sum(counts.values()),
        "unrecognized_reason_query_count": sum(unknown_labels.values()),
        "classification_status": (
            "complete" if not unknown_labels else "requires_nomenclature_review"
        ),
        "target_classes": {
            label: {
                "ood_query_count": counts[label],
                "ood_disjoint_window_groups": counts_by_group[label],
                "task_explicitly_requests_reason_count": per_task_reason[label],
                "by_cloudbed": {
                    bed: per_bed[bed][label] for bed in sorted(rows_by_bed)
                },
            }
            for label in TARGETS
        },
        # Aggregate labels only: never produce case ID / reason pair.
        "unrecognized_reason_labels_aggregated": [
            {"label": name, "ood_query_count": count}
            for name, count in sorted(unknown_labels.items())
        ],
        "read_ground_truth": True,
        "read_query_scoring_points": True,
        "read_telemetry": False,
        "read_predictions": False,
        "model_api_calls": 0,
        "files_written": False,
        "emits_case_label_mapping": False,
        "notes": [
            "GT consulted in separate offline evaluation-only audit; NEVER import this module into agent tools.",
            "Each query row corresponds to a record row only after archive alignment checks.",
            "Number of recorded fault rows is NOT proof of independent fault injections.",
            "Disjoint time windows do not alone ensure causal independence.",
            "Tasks 1/3/5 do not require root cause reason in official Microsoft scoring.",
            "Unknown labels require manual alias review BEFORE any class coverage claim.",
            "No discovery/test cohort assigned and no OOD model inference performed.",
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", required=True, type=Path)
    result = aggregate_ood_classes(p.parse_args().data_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
