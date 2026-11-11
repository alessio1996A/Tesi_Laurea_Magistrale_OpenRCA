"""Offline RQ2 compatibility audit for already-frozen V3 tool trajectories.

Read-only. Uses ONLY a known RQ1 results directory, NOT Market.zip, the
ground-truth file, scorer outputs, or any current discovery/test data.
No model/tool calls; no files written; never prints content or per-case IDs.

This is a FEASIBILITY audit only. Historical V3 cases are NOT RQ2 OOD
training data and their results must not be transferred into the candidate
pseudorule-generation prompts. Do not tune rules on V3 trajectories.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from evaluation.rq2_evidence_bundle import (
    EvidenceBundleError, build_evidence_bundle,
)

PROTOCOL = "openrca_harness_v2_five_agents_development_v3"
SUBDIR = Path("data/results/v2") / PROTOCOL
ALLOWED_TOOLS = (
    "tool_get_service_metrics",
    "tool_get_container_metrics",
    "tool_get_node_metrics",
    "tool_get_logs",
    "tool_get_traces",
)
MAX_JSON_FILES = 400
MAX_FILE_BYTES = 25_000_000
VERSION = "rq2_historical_trajectory_feasibility_v0"


class HistoryAuditError(ValueError):
    """Known V3 directory not safely inspectable; no inference attempted."""


def audit_history(root: Path) -> dict:
    """Read only existing RQ1 V3 JSON files; report aggregate compatibility."""
    root = Path(root)
    source = root / SUBDIR
    if source.is_symlink() or not source.is_dir():
        raise HistoryAuditError("Original frozen V3 results directory missing or unsafe")
    # Do not follow nested symlinks, and never traverse the scoring directory.
    files = sorted(p for p in source.rglob("*.json") if p.is_file())
    if len(files) > MAX_JSON_FILES:
        raise HistoryAuditError("Unexpectedly large V3 results directory")
    counts = Counter()
    reasons = Counter()
    for path in files:
        if path.is_symlink():
            raise HistoryAuditError("Result path is symlink")
        if any(parent.is_symlink() for parent in path.parents if parent != root):
            raise HistoryAuditError("Symlink directory inside result tree")
        if not path.resolve().is_relative_to(source.resolve()):
            raise HistoryAuditError("Result escaped frozen V3 directory")
        counts["json_files"] += 1
        try:
            size = path.stat().st_size
            if size > MAX_FILE_BYTES:
                raise HistoryAuditError("Oversized historical result file")
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, ValueError, RecursionError) as exc:
            counts["unparseable_files"] += 1
            continue
        if type(doc) is not dict:
            counts["other_json_files"] += 1
            continue
        # Do not inspect files that look like scorer output or GT. The V3
        # folder is supposed to be pure results; abort on a safety anomaly.
        if {"scoring_points", "ground_truth", "ground_truth_reason"} & set(doc):
            raise HistoryAuditError("Unexpected scoring/GT fields in V3 result root")
        # Runner implementations can save envelopes; inspect only a plain
        # result object or one directly nested under a 'result' key.
        record = doc
        if "tool_trajectory" not in record and type(record.get("result")) is dict:
            record = record["result"]
        if "tool_trajectory" not in record:
            counts["other_json_files"] += 1
            continue
        counts["result_records_with_trajectory"] += 1
        if "tool_trajectory" in doc and "result" in doc:
            counts["mixed_envelope"] += 1
        if record.get("error") is not None:
            counts["runner_error_results"] += 1
            # Trajectory can still be inspected for provenance.
        trajectory = record["tool_trajectory"]
        try:
            bundle = build_evidence_bundle(
                trajectory, allowed_tool_names=ALLOWED_TOOLS
            )
        except EvidenceBundleError as exc:
            # No raw observation, parameters or case ID ever logged.
            reasons[type(exc).__name__ + ":" + str(exc)] += 1
            counts["bundle_not_usable"] += 1
            continue
        counts["bundle_structurally_usable"] += 1
        counts["observations"] += bundle["observations_count"]
        counts["truncated_observations"] += bundle["truncated_count"]
        if bundle["observations_count"] == 0:
            counts["empty_bundles"] += 1

    return {
        "audit": VERSION,
        "status": "HISTORICAL_COMPATIBILITY_ONLY",
        "source": str(SUBDIR).replace(os.sep, "/"),
        "read_only": True,
        "read_ground_truth": False,
        "read_scoring": False,
        "read_ood_cases": False,
        "read_model_predictions_for_tuning": False,
        "model_api_calls": 0,
        "files_written": False,
        "counts": dict(sorted(counts.items())),
        "incompatibility_reasons": dict(sorted(reasons.items())),
        "caveats": [
            "Original V3 paths only; no OOD data opened or pseudorules generated.",
            "Evidence IDs demonstrate recorded tool provenance, not factual correctness.",
            "Legacy parallel same-name tool calls without IDs are ambiguous.",
            "No model performance or target fault labels are inspected.",
            "Historical prompt/model outputs must not be incorporated into RQ2 discovery.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    report = audit_history(args.data_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
