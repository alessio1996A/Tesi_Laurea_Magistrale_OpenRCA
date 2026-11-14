"""Read-only, GT-free audit of q045-style WARNING signals on DEVELOPMENT logs.

This is a source-isolated descriptive telemetry audit, NOT a detector, K
revision, scientific rule freeze, inference, or OOD test. It does not read
model output, ground truth, queries, scoring, or held-out case telemetry for
analysis. Daily log CSVs may physically contain other splits; the code
filters by verified DEVELOPMENT windows before inspecting log text.

The post-hoc marker 'severity: warning' is exploratory and cannot be called
a validated DNS signature or a verified operational KPI. The report provides
no per-incident predictions, test decisions or case-label mapping.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

from evaluation.rq2_development_kpi_audit import (
    _development_intervals,
)
from evaluation.rq2_q045_warning_detector_synthetic import (
    SCOPE_RE, WARNING_RE, WINDOW_SECONDS, K_RECORD_SHA256,
)
from evaluation.v2_case_window_audit import (
    _read_csv, _sha, _window, SPLIT_COLUMNS, MANIFEST_COLUMNS,
    SPLIT_SHA256, MANIFEST_SHA256,
)

VERSION = "rq2_q045_development_service_log_source_audit_v0"
COLS = ["timestamp", "cmdb_id", "log_id", "value"]
MAX_ROWS_PER_CHUNK = 100_000
MAX_SCOPED_ROWS = 5_000_000


class DevelopmentLogAuditError(ValueError):
    """Reject an untrusted source or ambiguous cross-split observation."""


def _verified_log_members(split: dict, manifest: dict, *, synthetic: bool):
    """Derive log file allowlist exclusively from DEVELOPMENT source windows.

    Reuse the established KPI window gate (including development/OOD
    non-overlap) and add strict non-overlap with evaluation/quarantine.
    """
    members, dev_cases = _development_intervals(
        split, manifest, synthetic=synthetic,
    )
    development = [
        row for row in split.values() if row["split"] == "development"
    ]
    other = [
        row for row in split.values() if row["split"] != "development"
    ]
    for d in development:
        a, b = _window(d)
        for row in other:
            if row["cloudbed"] != d["cloudbed"]:
                continue
            x, y = _window(row)
            if a < y and x < b:
                raise DevelopmentLogAuditError(
                    "Development interval overlaps non-development split"
                )

    logs = {}
    for metric_member, intervals in members.items():
        if not metric_member.endswith("/metric/metric_node.csv"):
            continue
        name = metric_member.replace(
            "/metric/metric_node.csv", "/log/log_service.csv",
        )
        if not name.startswith((
            "Market/cloudbed-1/telemetry/",
            "Market/cloudbed-2/telemetry/",
        )) or not name.endswith("/log/log_service.csv"):
            raise DevelopmentLogAuditError("Unexpected archive member path")
        if name in logs:
            raise DevelopmentLogAuditError("Duplicate source log path")
        logs[name] = intervals
    if not logs:
        raise DevelopmentLogAuditError("No allowed DEVELOPMENT service logs")
    return dict(sorted(logs.items())), dev_cases


def audit_development_service_warnings(
    data_dir: Path, *, _synthetic_test_fixture: bool = False,
) -> dict:
    """Return aggregated occurrence counts from verified development windows.

    Does NOT apply the K detector to real data, issue negative decisions,
    assign DNS labels, or infer log-stream completeness.
    _synthetic_test_fixture bypasses ONLY the official hashes/counts for
    unit-test fixtures; the CLI can never enable it.
    """
    root = Path(data_dir)
    if not root.is_dir() or root.is_symlink():
        raise DevelopmentLogAuditError("Existing nonsymlinked data dir required")
    split_path = root / "data/processed/split_market_v1.csv"
    manifest_path = root / "data/processed/benchmark_inputs_market.csv"
    archive_path = root / "Market.zip"
    for file in (split_path, manifest_path, archive_path):
        if not file.is_file() or file.is_symlink():
            raise DevelopmentLogAuditError("Source missing or symlinked")

    actual_split = _sha(split_path)
    actual_manifest = _sha(manifest_path)
    if not _synthetic_test_fixture and (
        actual_split != SPLIT_SHA256
        or actual_manifest != MANIFEST_SHA256
    ):
        raise DevelopmentLogAuditError("GT-free input SHA-256 drift")

    split = _read_csv(split_path, SPLIT_COLUMNS)
    manifest = _read_csv(manifest_path, MANIFEST_COLUMNS)
    members, n_dev = _verified_log_members(
        split, manifest, synthetic=_synthetic_test_fixture,
    )

    scoped_counts: Counter[str] = Counter()
    warning_counts: Counter[str] = Counter()
    empty_message_counts: Counter[str] = Counter()
    missing_log_id_counts: Counter[str] = Counter()
    occupied_minute_bins: set[tuple[str, int]] = set()
    files_by_bed: Counter[str] = Counter()

    with ZipFile(archive_path, "r") as archive:
        available = Counter(archive.namelist())
        if any(available[member] != 1 for member in members):
            raise DevelopmentLogAuditError(
                "Missing or repeated DEVELOPMENT service log archive member"
            )
        for member, windows in members.items():
            bed = member.split("/")[1]
            files_by_bed[bed] += 1
            starts = np.array([s for s, _ in windows], dtype=np.int64)
            ends = np.array([e for _, e in windows], dtype=np.int64)
            with archive.open(member) as reader:
                for chunk in pd.read_csv(
                    reader, usecols=COLS, chunksize=MAX_ROWS_PER_CHUNK,
                ):
                    # The timestamp column must be decoded to apply the
                    # development-only mask. No non-development log value
                    # is parsed or aggregated.
                    seconds = pd.to_numeric(
                        chunk["timestamp"], errors="coerce",
                    ).to_numpy(dtype=float)
                    index = np.searchsorted(starts, seconds, side="right") - 1
                    valid = index >= 0
                    index = np.clip(index, 0, len(starts) - 1)
                    keep = valid & np.isfinite(seconds) & (seconds < ends[index])
                    if not bool(keep.any()):
                        continue
                    selected = chunk.loc[
                        keep, ["timestamp", "cmdb_id", "log_id", "value"]
                    ].copy()
                    selected["timestamp"] = seconds[keep]
                    selected = selected.loc[
                        selected["cmdb_id"].map(
                            lambda x: isinstance(x, str)
                            and SCOPE_RE.fullmatch(x) is not None
                        )
                    ]
                    if selected.empty:
                        continue

                    # No inference from timestamp/data outside development.
                    # Event timestamps must be integral Unix seconds.
                    t = selected["timestamp"].to_numpy(dtype=float)
                    if not bool(np.all(np.isfinite(t) & (t == np.floor(t)))):
                        raise DevelopmentLogAuditError(
                            "Non-integral DEVELOPMENT service-log timestamp"
                        )
                    scoped_counts[bed] += len(selected)
                    if sum(scoped_counts.values()) > MAX_SCOPED_ROWS:
                        raise DevelopmentLogAuditError("Bounded log audit exceeded")

                    empty_message_counts[bed] += int(
                        selected["value"].isna().sum()
                        + selected["value"].astype(str).str.strip().eq("").sum()
                    )
                    missing_log_id_counts[bed] += int(
                        selected["log_id"].isna().sum()
                        + selected["log_id"].astype(str).str.strip().eq("").sum()
                    )

                    warnings = selected["value"].astype(str).str.contains(
                        WARNING_RE, na=False,
                    )
                    found = selected.loc[warnings, "timestamp"]
                    warning_counts[bed] += len(found)
                    occupied_minute_bins.update(
                        (bed, int(x) // WINDOW_SECONDS)
                        for x in found
                    )

    return {
        "version": VERSION,
        "status": "DEVELOPMENT_ONLY_EXPLORATORY_LOG_SIGNAL_PRESENCE",
        "source_verified": not _synthetic_test_fixture,
        "split_sha256": actual_split,
        "manifest_sha256": actual_manifest,
        "reference_k_sha256": K_RECORD_SHA256,
        "development_cases": n_dev,
        "allowed_service_log_files_read": sum(files_by_bed.values()),
        "files_by_cloudbed": dict(sorted(files_by_bed.items())),
        "scoped_log_rows": sum(scoped_counts.values()),
        "explicit_warning_rows": sum(warning_counts.values()),
        "empty_message_rows": sum(empty_message_counts.values()),
        "missing_log_id_rows": sum(missing_log_id_counts.values()),
        "global_60s_bed_buckets_with_warnings": len(occupied_minute_bins),
        "by_cloudbed": {
            bed: {
                "scoped_log_rows": scoped_counts[bed],
                "explicit_warning_rows": warning_counts[bed],
            }
            for bed in ("cloudbed-1", "cloudbed-2")
        },
        "extractor": "case-insensitive severity: warning marker",
        "scope": "productcatalogservice-*",
        "window_policy": "epoch-aligned UTC 60s; occupancy only",
        "event_identity_deduplicated": False,
        "logging_completeness_verified": False,
        "negative_decisions_produced": False,
        "dns_causality_verified": False,
        "scientific_freeze": False,
        "ready_for_ood_test": False,
        "model_pseudocode_executed": False,
        "reads_ground_truth": False,
        "reads_record_csv": False,
        "reads_query_csv": False,
        "reads_scoring": False,
        "reads_model_responses": False,
        "reads_ood_telemetry_for_analysis": False,
        "nondevelopment_rows_filtered_before_log_parsing": True,
        "daily_file_may_contain_decoded_nondevelopment_rows": True,
        "market_zip_sha256_verified": False,
        "model_api_calls": 0,
        "files_written": False,
        "limitations": [
            "Warning marker is post-hoc exploratory, not proven original K metric.",
            "Warning counts in development do not establish DNS specificity.",
            "No log-stream completeness or absence-of-warning negatives certified.",
            "Raw rows are not event-ID deduplicated: counts may include duplicates.",
            "Daily log members may physically contain rows of other splits; timestamps "
            "are decoded for filtering, but content/values are inspected only "
            "within verified development intervals.",
            "Source SHA verification covers GT-free split/manifest, not Market.zip.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(
        audit_development_service_warnings(args.data_dir),
        ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False,
    ))


if __name__ == "__main__":
    main()
