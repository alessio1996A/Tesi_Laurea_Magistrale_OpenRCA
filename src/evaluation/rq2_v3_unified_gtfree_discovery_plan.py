"""Successor RQ2 V3 GT-free discovery plan; PRE-RELEASE, NO API/CLAIM.

The only experimental change planned relative to RQ2 V2 is the C/K
transport's provider-neutral exact text extraction plus auditable text
provenance. D configuration, C/K prompts, model IDs, cohort and harnesses
remain identical. No V2 D/C/K result may be silently imported or replayed
under a V3 stage ID.

This module builds identities and a deterministic plan only. It does NOT
read source datasets, release files, any GT/Market, or any historical record.
It has no filesystem writes, SDKs or provider dispatcher.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from evaluation.rq2_v2_unified_discovery_plan import (
    VERSION as V2_PROTOCOL,
    DISCOVERY, TEST, MODELS, HARNESSES, ENGINES,
    MAX_TOOL_ROUNDS, MAX_VERIFICATION_CHECKS, RECURSION_LIMIT,
    build_offline_discovery_plan,
)
from evaluation.rq2_v2_ck_text_extraction_candidate import POLICY as CK_POLICY

VERSION = "rq2_v3_unified_equal_ck_extraction_discovery_v0"
STATUS = "V3_GT_FREE_DRAFT_NO_RELEASE_NO_API"
NAMESPACE = Path("data/rq2_v3_unified_scientific_v1")
RELEASE_FILE = NAMESPACE / "release_v1.json"
STAGES = ("D", "C", "K")
CK_PROVENANCE_SCHEMA = "rq2_v3_ck_text_extraction_meta_v0"


class RQ2V3PlanBlocked(ValueError):
    """Stop when successor discovery identities or invariants drift."""


def _canonical(data: object) -> bytes:
    return json.dumps(
        data, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _v3_stage_id(v2_id: str) -> str:
    if type(v2_id) is not str or not v2_id.startswith(V2_PROTOCOL + ":"):
        raise RQ2V3PlanBlocked("Unexpected original V2 stage ID")
    return VERSION + v2_id[len(V2_PROTOCOL):]


def build_offline_v3_discovery_plan() -> dict:
    """Create a unique 4 cases x 3 models x 5 harnesses x 3 stages plan."""
    v2 = build_offline_discovery_plan()
    entries = v2.get("entries")
    if (
        v2.get("protocol") != V2_PROTOCOL
        or v2.get("logical_stages") != 180
        or type(entries) is not list
        or len(entries) != 180
        or len(DISCOVERY) != 4
        or len(TEST) != 11
        or set(DISCOVERY) & set(TEST)
        or tuple(MODELS) != ("gemini", "sonnet", "haiku")
        or tuple(HARNESSES) != (
            "A0", "A1", "A1_8R", "A1_8R_Planning", "A1_PAVE"
        )
        or tuple(ENGINES) != tuple(HARNESSES)
        or V2_PROTOCOL == VERSION
    ):
        raise RQ2V3PlanBlocked("Baseline cohort/model/harness drift")

    if (
        v2.get("entries_sha256") != _sha(entries)
        or v2.get("preview_sha256") != _sha({
            key: value for key, value in v2.items() if key != "preview_sha256"
        })
    ):
        raise RQ2V3PlanBlocked("V2 preview or entries SHA drift")

    rows = []
    for old in entries:
        if type(old) is not dict or old.get("stage") not in STAGES:
            raise RQ2V3PlanBlocked("Malformed baseline entry")
        if (
            old.get("case_id") not in DISCOVERY
            or old.get("logical_model") not in MODELS
            or old.get("harness") not in HARNESSES
            or old.get("model_id") != v2["model_ids"].get(old["logical_model"])
            or old.get("d_engine") != ENGINES.get(old["harness"])
        ):
            raise RQ2V3PlanBlocked("Baseline arm identity drift")
        prefix = (
            f"{V2_PROTOCOL}:{old['case_id']}:"
            f"{old['logical_model']}:{old['harness']}"
        )
        expected_deps = (
            [] if old["stage"] == "D" else
            [prefix + ":D"] if old["stage"] == "C" else [prefix + ":C"]
        )
        if old["stage_id"] != prefix + ":" + old["stage"] or (
            old.get("depends_on") != expected_deps
        ):
            raise RQ2V3PlanBlocked("Baseline D/C/K dependency drift")
        row = {
            "stage_id": _v3_stage_id(old["stage_id"]),
            "case_id": old["case_id"],
            "logical_model": old["logical_model"],
            "model_id": old["model_id"],
            "model_provider": old["model_provider"],
            "harness": old["harness"],
            "stage": old["stage"],
            "depends_on": [
                _v3_stage_id(parent) for parent in old["depends_on"]
            ],
            "d_engine": old["d_engine"],
            "execution_status": "BLOCKED_NO_V3_RELEASE",
        }
        rows.append(row)

    ids = [r["stage_id"] for r in rows]
    positions = {stage_id: i for i, stage_id in enumerate(ids)}
    if len(rows) != 180 or len(positions) != 180 or any(
        dep not in positions or positions[dep] >= idx
        for idx, r in enumerate(rows) for dep in r["depends_on"]
    ):
        raise RQ2V3PlanBlocked("Invalid ordering, duplicates, or dependency")
    for old, new in zip(entries, rows):
        if (
            new["case_id"] != old["case_id"]
            or new["harness"] != old["harness"]
            or new["logical_model"] != old["logical_model"]
            or new["model_id"] != old["model_id"]
            or new["model_provider"] != old["model_provider"]
            or new["d_engine"] != old["d_engine"]
            or new["stage"] != old["stage"]
            or new["stage_id"] == old["stage_id"]
            or any(dep.startswith(V2_PROTOCOL + ":") for dep in new["depends_on"])
        ):
            raise RQ2V3PlanBlocked("Changed analysis arm or V2 identity leakage")

    core = {
        "protocol": VERSION,
        "status": STATUS,
        "base_v2_protocol": V2_PROTOCOL,
        "base_v2_plan_sha256": v2["preview_sha256"],
        "base_v2_entries_sha256": v2["entries_sha256"],
        "mode": "GT_FREE_PLAN_ONLY",
        "scientific_namespace_proposed": NAMESPACE.as_posix(),
        "release_relative_path_proposed": RELEASE_FILE.as_posix(),
        "discovery_cases": list(DISCOVERY),
        "ood_test_cases_locked": list(TEST),
        "models": list(MODELS),
        "model_ids": dict(v2["model_ids"]),
        "harnesses": list(HARNESSES),
        "stage_counts": {"D": 60, "C": 60, "K": 60},
        "logical_stages": 180,
        "max_tool_rounds_D": MAX_TOOL_ROUNDS,
        "max_verification_checks_planning": MAX_VERIFICATION_CHECKS,
        "max_recursion_depth_D": RECURSION_LIMIT,
        "d_output_contract": "v2_enforce",
        "c_and_k_prompts": "rq2_probe_adapter_v0_unchanged",
        "ck_text_extraction_policy": CK_POLICY,
        "ck_text_provenance_schema": CK_PROVENANCE_SCHEMA,
        "reuse_v2_d_outputs": False,
        "reuse_v2_c_or_k_outputs": False,
        "comparison_policy": (
            "paired by the same four discovery cases; model/harness "
            "results within one V3 release only; report provider errors, "
            "JSON validity, abstentions, K blocked, cost and causality separately"
        ),
        "analysis_unit": "incident_case_within_model_and_harness",
        "release_frozen": False,
        "source_commit_pinned": False,
        "model_api_calls": 0,
        "can_execute_api": False,
        "can_write_scientific_claims": False,
        "can_run_ood_test": False,
        "ground_truth_read": False,
        "telemetry_read": False,
        "historical_results_read": False,
        "files_written": False,
        "entries_sha256": _sha(rows),
        "entries": rows,
    }
    return {**core, "preview_sha256": _sha(core)}
