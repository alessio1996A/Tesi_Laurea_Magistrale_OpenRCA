"""GT-free Market KPI presence audit on DEVELOPMENT windows only.

Reads a SHA-verified split and GT-free instruction manifest, then *only*
metric_node.csv / metric_container.csv archive members for development
windows. Daily CSV members can PHYSICALLY contain rows of other splits;
we must stream those bytes to filter them but NEVER include their rows
in metrics/statistics or output. No record.csv, query.csv, scorer, target
labels, prediction files, model responses, or file writes are allowed.

Audits a UNION of official development time windows: rows overlapping more
than one development window are counted ONCE (not as independent replicates).
Numeric sample availability does NOT establish physical units or causality.

RUNTIME: read-only Colab preflight only, not an LLM agent or provider runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zipfile import ZipFile
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from evaluation.rq2_kpi_formalizability_preflight import known_code_kpi_catalog
from evaluation.v2_case_window_audit import (
    MANIFEST_COLUMNS, MANIFEST_SHA256, SPLIT_COLUMNS, SPLIT_SHA256,
    _read_csv, _window,
)

VERSION = "rq2_development_kpi_presence_audit_v0"
TZ = ZoneInfo("Asia/Shanghai")
LAYERS = ("node", "container")
CSV_COLUMNS = ("timestamp", "cmdb_id", "kpi_name", "value")
EXPECTED_SPLITS = {
    "development": 92,
    "evaluation": 23,
    "mixed_quarantine": 18,
    "ood_holdout": 15,
}
MAX_WINDOW_SECONDS = 86400
MAX_UNKNOWN_NAMES_IN_REPORT = 60


class KPIAuditError(ValueError):
    """Source integrity or development telemetry isolation not proven."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _days(start: int, end: int):
    if not (0 < start < end and end - start <= MAX_WINDOW_SECONDS):
        raise KPIAuditError("Invalid or excessive development window")
    first = datetime.fromtimestamp(start, tz=timezone.utc).astimezone(TZ).date()
    last = datetime.fromtimestamp(end - 1, tz=timezone.utc).astimezone(TZ).date()
    day = first
    while day <= last:
        yield day.strftime("%Y_%m_%d")
        day += timedelta(days=1)


def _merge(windows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(windows):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            left, prior_end = merged[-1]
            merged[-1] = (left, max(prior_end, end))
    return merged


def _development_intervals(split: dict, manifest: dict, *, synthetic: bool):
    if set(split) != set(manifest):
        raise KPIAuditError("GT-free manifest/split case IDs mismatch")
    counts = Counter(row["split"] for row in split.values())
    if set(counts) - set(EXPECTED_SPLITS):
        raise KPIAuditError("Unknown split value")
    if not synthetic and dict(counts) != EXPECTED_SPLITS:
        raise KPIAuditError("Original frozen cohort counts differ")

    # Explicit GT-free overlap guard: if any development window intersects
    # an OOD holdout window, a development-only numeric audit is impossible
    # without also aggregating holdout observations. Fail closed.
    development = [r for r in split.values() if r["split"] == "development"]
    ood = [r for r in split.values() if r["split"] == "ood_holdout"]
    for dev in development:
        a, b = _window(dev)
        for heldout in ood:
            if dev["cloudbed"] != heldout["cloudbed"]:
                continue
            c, d = _window(heldout)
            if a < d and c < b:
                raise KPIAuditError("Development/holdout windows intersect")
    
    per_member: dict[str, list[tuple[int, int]]] = defaultdict(list)
    dev_ids = 0
    for cid, row in split.items():
        other = manifest[cid]
        if any(row[key] != other[key] for key in ("cloudbed", "start_unix", "end_unix")):
            raise KPIAuditError("GT-free sources disagree on window")
        if row["cloudbed"] not in ("cloudbed-1", "cloudbed-2"):
            raise KPIAuditError("Unexpected cloudbed")
        if not cid.startswith(row["cloudbed"] + "_q"):
            raise KPIAuditError("Inconsistent case identifier")
        start, end = _window(row)
        if row["split"] != "development":
            continue
        dev_ids += 1
        for day in _days(start, end):
            for layer in LAYERS:
                member = (
                    f"Market/{row['cloudbed']}/telemetry/{day}/metric/"
                    f"metric_{layer}.csv"
                )
                per_member[member].append((start, end))

    if dev_ids == 0:
        raise KPIAuditError("No development cases")
    if not synthetic and dev_ids != EXPECTED_SPLITS["development"]:
        raise KPIAuditError("Unexpected development case count")
    return {
        member: _merge(windows)
        for member, windows in sorted(per_member.items())
    }, dev_ids


def audit_development_kpis(
    root: Path, *, _synthetic_test_fixture: bool = False,
) -> dict:
    """Read aggregate numeric KPI availability from development windows.

    Synthetic-mode bypasses only official input hashes/cohort counts for unit
    testing. The CLI NEVER enables it. Test results in this mode explicitly
    state source_verified=False. The real audit always validates both hashes.
    """
    root = Path(root)
    split_path = root / "data/processed/split_market_v1.csv"
    manifest_path = root / "data/processed/benchmark_inputs_market.csv"
    split_hash, manifest_hash = _sha(split_path), _sha(manifest_path)
    if not _synthetic_test_fixture and (
        split_hash != SPLIT_SHA256 or manifest_hash != MANIFEST_SHA256
    ):
        raise KPIAuditError("Frozen GT-free split/manifest SHA-256 mismatch")

    split = _read_csv(split_path, SPLIT_COLUMNS)
    manifest = _read_csv(manifest_path, MANIFEST_COLUMNS)
    members, n_development = _development_intervals(
        split, manifest, synthetic=_synthetic_test_fixture,
    )

    numeric_counts: Counter[tuple[str, str]] = Counter()
    observed_counts: Counter[tuple[str, str]] = Counter()
    total_rows_in_dev_windows = 0
    total_valid_numeric_rows = 0

    zip_path = root / "Market.zip"
    with ZipFile(zip_path, "r") as archive:
        available = Counter(archive.namelist())
        if any(available.get(name) != 1 for name in members):
            raise KPIAuditError("Missing/ambiguous exact development metrics member")
        for member, time_ranges in members.items():
            # No user-supplied archive member path. Only exact allowlisted
            # strings constructed above are ever opened.
            if not member.startswith(("Market/cloudbed-1/telemetry/",
                                       "Market/cloudbed-2/telemetry/")):
                raise KPIAuditError("Telemetry path escaped allowlist")
            if not member.endswith(("/metric/metric_node.csv",
                                    "/metric/metric_container.csv")):
                raise KPIAuditError("Only node/container metrics may be read")
            layer = "node" if member.endswith("metric_node.csv") else "container"
            starts = np.array([start for start, _ in time_ranges], dtype=np.int64)
            ends = np.array([end for _, end in time_ranges], dtype=np.int64)
            with archive.open(member) as stream:
                for chunk in pd.read_csv(
                    stream, usecols=list(CSV_COLUMNS), chunksize=100_000,
                ):
                    # numpy.searchsorted assumes merged intervals are sorted,
                    # disjoint. Each physical CSV row is counted at most once.
                    timestamp = pd.to_numeric(chunk["timestamp"], errors="coerce")
                    t = timestamp.to_numpy(dtype=float)
                    idx = np.searchsorted(starts, t, side="right") - 1
                    valid_idx = idx >= 0
                    idx = np.clip(idx, 0, len(starts) - 1)
                    in_window = valid_idx & (t < ends[idx]) & np.isfinite(t)
                    if not bool(in_window.any()):
                        continue
                    selected = chunk.loc[in_window, ["kpi_name", "value"]]
                    names = selected["kpi_name"]
                    values = pd.to_numeric(selected["value"], errors="coerce")
                    name_present = names.notna() & names.astype(str).str.strip().ne("")
                    # Count valid KPI names, including nonnumeric observations.
                    present_names = names[name_present].astype(str)
                    observed_counts.update({
                        (layer, str(name)): int(count)
                        for name, count in present_names.value_counts(sort=False).items()
                    })
                    numeric = name_present & values.notna() & np.isfinite(
                        values.to_numpy(dtype=float)
                    )
                    numeric_names = names[numeric].astype(str)
                    numeric_counts.update({
                        (layer, str(name)): int(count)
                        for name, count in numeric_names.value_counts(sort=False).items()
                    })
                    total_rows_in_dev_windows += len(selected)
                    total_valid_numeric_rows += len(numeric_names)

    inventory = known_code_kpi_catalog()
    known = {
        (item["telemetry_layer"], item["metric"]): item
        for item in inventory["metrics"]
    }
    known_summaries = [
        {
            "layer": layer,
            "metric": name,
            "present_with_numeric_values": numeric_counts[(layer, name)] > 0,
            "numeric_rows_in_union_of_development_windows": numeric_counts[(layer, name)],
            "market_unit_verified": False,
            "counter_or_rate_semantics_verified": False,
        }
        for (layer, name) in sorted(known)
    ]
    unknown = sorted(set(observed_counts) - set(known))
    by_layer = {}
    for layer in LAYERS:
        by_layer[layer] = {
            "code_catalog_names": sum(k[0] == layer for k in known),
            "code_catalog_names_observed_numeric": sum(
                k[0] == layer and numeric_counts[k] > 0 for k in known
            ),
            "other_names_seen_in_development": sum(
                k[0] == layer for k in unknown
            ),
            "numeric_rows_in_development": sum(
                count for (src, _), count in numeric_counts.items()
                if src == layer
            ),
        }

    return {
        "audit": VERSION,
        "status": "DEVELOPMENT_ONLY_GT_FREE_NUMERIC_PRESENCE",
        "source_verified": not _synthetic_test_fixture,
        "verified_gtfree_csv_input_hashes": not _synthetic_test_fixture,
        "market_archive_sha256_checked": False,
        "split_sha256": split_hash,
        "manifest_sha256": manifest_hash,
        "catalog_sha256": inventory["catalog_sha256"],
        "development_cases": n_development,
        "metrics_archive_members_read": len(members),
        "rows_in_union_of_development_windows": total_rows_in_dev_windows,
        "valid_numeric_rows": total_valid_numeric_rows,
        "observed_distinct_metrics": len(observed_counts),
        "numeric_distinct_metrics": sum(n > 0 for n in numeric_counts.values()),
        "catalog_known_metrics": known_summaries,
        "other_source_metric_names_count": len(unknown),
        "other_source_metric_names_sample": [
            {"layer": layer, "metric": name}
            for layer, name in unknown[:MAX_UNKNOWN_NAMES_IN_REPORT]
        ],
        "other_source_metric_names_omitted": max(
            0, len(unknown) - MAX_UNKNOWN_NAMES_IN_REPORT
        ),
        "by_layer": by_layer,
        "statistics_only_development_windows": True,
        "full_daily_metric_csv_members_streamed": True,
        "non_development_rows_filtered_before_aggregation": True,
        "possible_non_development_rows_decoded_from_shared_csv": True,
        "read_ground_truth": False,
        "read_record_csv": False,
        "read_scoring": False,
        "read_ood_telemetry_for_analysis": False,
        "read_model_predictions": False,
        "model_api_calls": 0,
        "files_written": False,
        "can_execute_rule": False,
        "catalog_physically_verified": False,
        "caveats": [
            "Numeric KPI presence in development does not prove presence in OOD.",
            "Rows in overlapping development windows are counted once.",
            "Presence in Market does not verify unit, counter/rate semantics, or cause.",
            "source_verified applies to the two GT-free CSVs, not a full Market.zip SHA-256.",
            "Full daily CSV members may contain other-split rows: these are decoded but filtered before any aggregation.",
            "Development-only KPI names must not be used to infer OOD target labels.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    result = audit_development_kpis(args.data_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
