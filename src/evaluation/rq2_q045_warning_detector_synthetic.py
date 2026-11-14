"""Pure synthetic-only prototype for one *unverified* Gemini RQ2-K candidate.

This is NOT a scientific rule freeze, live detector, or OOD test runner.
No Market, dataset, GT, scorer, network, provider, model pseudocode or file I/O.

K provenance (frozen Gemini V1): cloudbed-2_q045 / Gemini / A1 / K.
The K JSON hypothesizes service_log_warnings sum > 0 in 60 s for
productcatalogservice-*; it does NOT specify a canonical warning extractor.
The literal severity-marker extractor here is an EXPLORATORY choice made
AFTER inspecting discovery evidence. It cannot establish DNS specificity.

All real-data use is deliberately REFUSED. A different source-bound,
preregistered adapter must verify development-only sources and explicitly
approve an operational contract before real-data evaluation is considered.
"""
from __future__ import annotations

import re

VERSION = "rq2_q045_warning_detector_synthetic_v0"
K_RECORD_SHA256 = "32ddf6815e4216f0a46070950252852cec984f4456a0bb3758c86b16d1296add"
RULE_NAME = "productcatalogservice_dns_timeout_detector"
DERIVED_METRIC = "service_log_warnings"
WINDOW_SECONDS = 60
THRESHOLD = 0
MAX_ROWS = 100_000
MAX_WINDOWS = 1440
MAX_LOG_CHARS = 20_000

# Fixed, explicit post-hoc extraction; NOT validated DNS/physical semantics.
WARNING_RE = re.compile(r"\bseverity\s*:\s*warning\b", re.IGNORECASE)
SCOPE_RE = re.compile(r"productcatalogservice-[A-Za-z0-9_.-]+\Z")


class SyntheticWarningDetectorError(ValueError):
    """Reject ambiguous input or any non-synthetic execution."""


def inspect_synthetic_warning_windows(
    *, rows: list[dict], start_unix: int, end_unix: int,
    complete_windows: tuple[bool, ...], phase: str,
) -> dict:
    """Count distinct log events by UTC epoch-aligned, non-overlapping 60s bin.

    Strict input row: {timestamp:int, cmdb_id:str, log_id:str, value:str}.
    Only scoped service instances count; other components are ignored.
    Deduplicate exact (log_id, timestamp, component, message) repeats;
    conflicting reuse of one scoped log_id is an error.

    A complete_windows[i] = True is a *caller assertion* that logging
    coverage is complete for bucket i. It is NOT independently verified:
    this prototype permits only phase='synthetic' to avoid accidental
    promotion to an OOD/development predictor.

    An incomplete window always yields abstain, even if warnings are seen.
    Empty complete windows yield negative; this is valid ONLY for synthetic
    exercises where completeness is stipulated by the fixture.
    """
    if phase != "synthetic":
        raise SyntheticWarningDetectorError(
            "Only synthetic fixtures; development/OOD source gate unavailable"
        )
    if (type(start_unix) is not int or type(end_unix) is not int
            or start_unix < 0 or end_unix <= start_unix
            or start_unix % WINDOW_SECONDS != 0
            or end_unix % WINDOW_SECONDS != 0):
        raise SyntheticWarningDetectorError("Invalid or unaligned UTC epoch interval")
    count_windows = (end_unix - start_unix) // WINDOW_SECONDS
    if count_windows > MAX_WINDOWS:
        raise SyntheticWarningDetectorError("Window count exceeds bound")
    if (type(complete_windows) is not tuple
            or len(complete_windows) != count_windows
            or any(type(flag) is not bool for flag in complete_windows)):
        raise SyntheticWarningDetectorError("Completeness must be explicit per window")
    if type(rows) is not list or len(rows) > MAX_ROWS:
        raise SyntheticWarningDetectorError("Expected bounded list of log rows")

    counts = [0] * count_windows
    seen: dict[str, tuple[int, str, str]] = {}
    ignored_other_scope = 0
    repeated_identical = 0

    for item in rows:
        if type(item) is not dict or set(item) != {
            "timestamp", "cmdb_id", "log_id", "value",
        }:
            raise SyntheticWarningDetectorError("Unexpected log row schema")
        timestamp = item["timestamp"]
        component = item["cmdb_id"]
        log_id = item["log_id"]
        message = item["value"]
        if (type(timestamp) is not int
                or not start_unix <= timestamp < end_unix):
            raise SyntheticWarningDetectorError("Log timestamp outside input window")
        if (type(component) is not str or not component
                or len(component) > 128
                or type(log_id) is not str or not log_id or len(log_id) > 256
                or type(message) is not str or not message
                or len(message) > MAX_LOG_CHARS):
            raise SyntheticWarningDetectorError("Malformed log event")
        if SCOPE_RE.fullmatch(component) is None:
            ignored_other_scope += 1
            continue

        signature = (timestamp, component, message)
        previous = seen.get(log_id)
        if previous is not None:
            if previous != signature:
                raise SyntheticWarningDetectorError(
                    "Conflicting duplicate log_id; cannot count reliably"
                )
            repeated_identical += 1
            continue
        seen[log_id] = signature

        if WARNING_RE.search(message):
            offset = (timestamp - start_unix) // WINDOW_SECONDS
            counts[offset] += 1

    buckets = []
    for i, warning_count in enumerate(counts):
        decision = (
            "abstain" if not complete_windows[i] else
            "positive" if warning_count > THRESHOLD else "negative"
        )
        buckets.append({
            "start_unix": start_unix + i * WINDOW_SECONDS,
            "end_unix": start_unix + (i + 1) * WINDOW_SECONDS,
            "warning_count": warning_count,
            "coverage_complete_asserted": complete_windows[i],
            "decision": decision,
        })

    return {
        "version": VERSION,
        "status": "SYNTHETIC_EXPLORATORY_NOT_FROZEN",
        "candidate_origin_k_record_sha256": K_RECORD_SHA256,
        "rule_name": RULE_NAME,
        "derived_metric": DERIVED_METRIC,
        "aggregation": "sum",
        "threshold_operator": ">",
        "threshold": THRESHOLD,
        "window_seconds": WINDOW_SECONDS,
        "scope": "productcatalogservice-*",
        "warning_marker": "case-insensitive literal severity: warning",
        "window_policy": "nonoverlapping epoch-aligned UTC 60s",
        "instance_policy": "pooled warning count across scoped instances",
        "input_phase": phase,
        "ignored_other_scope_rows": ignored_other_scope,
        "deduplicated_identical_rows": repeated_identical,
        "buckets": buckets,
        "scientific_freeze": False,
        "ready_for_ood_test": False,
        "dns_causality_verified": False,
        "ground_truth_read": False,
        "reads_files": False,
        "model_api_calls": 0,
        "files_written": False,
        "model_pseudocode_executed": False,
        "caveat": (
            "Post-hoc literal-warning extraction is not equivalent to a "
            "validated DNS rule. No real-data use without separate source gate."
        ),
    }
