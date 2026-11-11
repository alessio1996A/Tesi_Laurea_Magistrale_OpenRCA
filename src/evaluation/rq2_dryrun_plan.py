"""RQ2 non-executable, GT-free stage-plan preview.

This module never invokes models, telemetry, tools or a scorer.  It only reads
the FROZEN split and GT-free input manifest via the existing preflight and
matches a candidate V1 discovery/test allocation observed in Colab.  Phase
allocation is STATIC and is NEVER inferred from benchmark labels by this
module.  V1 selection remains proposed, not protocol-frozen.

The preview deliberately has no execution/dispatch functions, credentials,
retry logic or writable paths.  It cannot approve any paid model request.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from evaluation.ood_holdout_preflight import inventory_ood

VERSION = "rq2_dryrun_workflow_preview_v0"
PLAN_STATUS = "DRAFT_NOT_EXECUTABLE"
DISCOVERY = (
    "cloudbed-1_q032", "cloudbed-1_q050",
    "cloudbed-2_q026", "cloudbed-2_q045",
)
TEST = (
    "cloudbed-1_q014", "cloudbed-1_q021", "cloudbed-1_q030",
    "cloudbed-1_q059", "cloudbed-2_q014", "cloudbed-2_q021",
    "cloudbed-2_q040", "cloudbed-2_q041", "cloudbed-2_q058",
    "cloudbed-2_q076", "cloudbed-2_q077",
)
HARNESSES = ("A1", "A1_8R")
MODELS = ("gemini", "sonnet", "haiku")
MAX_TOOL_ROUNDS = 6
MIN_CROSS_PHASE_GAP_SECONDS = 3600
EXPECTED_SPLIT_SHA256 = "c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724"
EXPECTED_MANIFEST_SHA256 = "5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13"


class RQ2PlanError(ValueError):
    """GT-free plan preflight failed; absolutely no run may be dispatched."""


def _canonical(obj: object) -> bytes:
    try:
        return json.dumps(
            obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as exc:
        raise RQ2PlanError("Plan contains noncanonical data") from exc


def _sha(obj: object) -> str:
    return hashlib.sha256(_canonical(obj)).hexdigest()


def _gap(a: dict, b: dict) -> int | None:
    if a["cloudbed"] != b["cloudbed"]:
        return None
    a0, a1 = a["start_unix"], a["end_unix"]
    b0, b1 = b["start_unix"], b["end_unix"]
    return max(0, a0 - b1, b0 - a1)


def verify_candidate_allocation(
    metadata: list[dict], groups: list[list[str]],
    *, discovery=DISCOVERY, test=TEST,
    enforce_real_size: bool = True,
) -> dict:
    """Verify phase split using only ID/cloudbed/window/task metadata.

    No class label, scoring_points, record.csv or source query CSV is read.
    """
    if type(metadata) is not list or type(groups) is not list:
        raise RQ2PlanError("Expected metadata and groups lists")
    if type(discovery) not in (tuple, list) or type(test) not in (tuple, list):
        raise RQ2PlanError("Discovery/test must be explicit ordered sequences")
    if any(type(x) is not str for x in (*discovery, *test)):
        raise RQ2PlanError("Non-string case ID in candidate allocation")
    if len(set(discovery)) != len(discovery) or len(set(test)) != len(test):
        raise RQ2PlanError("Duplicate case ID in allocation")
    if set(discovery) & set(test):
        raise RQ2PlanError("Discovery/test share a case ID")
    if enforce_real_size and (len(discovery) != 4 or len(test) != 11):
        raise RQ2PlanError("Expected V1 4 discovery + 11 test")
    if not metadata or len({m.get("case_id") for m in metadata}) != len(metadata):
        raise RQ2PlanError("Empty or duplicate metadata")
    by_id = {}
    for item in metadata:
        if type(item) is not dict or set(item) != {
            "case_id", "cloudbed", "task_index", "start_unix", "end_unix"
        }:
            raise RQ2PlanError("Unexpected GT-free case metadata schema")
        cid = item["case_id"]
        bed = item["cloudbed"]
        if (type(cid) is not str or type(bed) is not str
                or bed not in ("cloudbed-1", "cloudbed-2")
                or not cid.startswith(bed + "_q")):
            raise RQ2PlanError("Malformed case ID/cloudbed")
        if type(item["task_index"]) is not str or not item["task_index"].startswith("task_"):
            raise RQ2PlanError("Malformed task index")
        if (type(item["start_unix"]) is not int
                or type(item["end_unix"]) is not int
                or item["start_unix"] >= item["end_unix"]):
            raise RQ2PlanError("Malformed case window")
        by_id[cid] = item

    all_ids = set(by_id)
    if set(discovery) | set(test) != all_ids:
        raise RQ2PlanError("Allocation must cover exactly the OOD cohort")
    seen = set()
    for group in groups:
        if type(group) is not list or not group or any(
            type(cid) is not str or cid not in by_id for cid in group
        ):
            raise RQ2PlanError("Malformed window group")
        if len(group) != len(set(group)) or seen & set(group):
            raise RQ2PlanError("Duplicated case in temporal groups")
        seen.update(group)
        if not (set(group) <= set(discovery) or set(group) <= set(test)):
            raise RQ2PlanError("Overlapping-window group split across phases")
    if seen != all_ids:
        raise RQ2PlanError("Temporal groups do not cover OOD cohort")
    # Do not relax the GT-free temporal separation validated in V1.
    gaps = [
        _gap(by_id[d], by_id[t]) for d in discovery for t in test
    ]
    real_gaps = [gap for gap in gaps if gap is not None]
    if real_gaps and min(real_gaps) <= MIN_CROSS_PHASE_GAP_SECONDS:
        raise RQ2PlanError("Discovery/test temporal proximity <= 1 hour")
    return {
        "discovery_case_ids": sorted(discovery),
        "test_case_ids": sorted(test),
        "discovery_cases": len(discovery),
        "test_cases": len(test),
        "discovery_windows": sum(set(group) <= set(discovery) for group in groups),
        "test_windows": sum(set(group) <= set(test) for group in groups),
        "min_cross_phase_same_cloudbed_gap_seconds": (
            min(real_gaps) if real_gaps else None
        ),
        "discovery_by_cloudbed": dict(sorted(Counter(
            by_id[cid]["cloudbed"] for cid in discovery
        ).items())),
        "test_by_cloudbed": dict(sorted(Counter(
            by_id[cid]["cloudbed"] for cid in test
        ).items())),
    }


def make_workflow_preview(
    metadata: list[dict], groups: list[list[str]], *,
    split_sha256: str, manifest_sha256: str,
    discovery=DISCOVERY, test=TEST,
    enforce_real_size: bool = True,
    _source_sha_checked: bool = False,
) -> dict:
    """Build D/C/K dependency graph, never execution permissions.

    Source is considered verified ONLY by the trusted preview_market wrapper.
    Plain callers can supply matching hash strings without file verification.
    """
    if (split_sha256 != EXPECTED_SPLIT_SHA256
            or manifest_sha256 != EXPECTED_MANIFEST_SHA256):
        raise RQ2PlanError("Frozen GT-free data hash mismatch")
    audit = verify_candidate_allocation(
        metadata, groups, discovery=discovery, test=test,
        enforce_real_size=enforce_real_size,
    )
    by_id = {item["case_id"]: item for item in metadata}
    phase_map = {
        **{cid: "discovery" for cid in discovery},
        **{cid: "test" for cid in test},
    }
    entries = []
    for phase in ("discovery", "test"):
        for cid in sorted(phase_map):
            if phase_map[cid] != phase:
                continue
            row = by_id[cid]
            for model in MODELS:
                for harness in HARNESSES:
                    prefix = f"{VERSION}:{cid}:{model}:{harness}"
                    for stage in ("D", "C", "K") if phase == "discovery" else ("D", "C"):
                        dependencies = (
                            [] if stage == "D" else
                            [prefix + ":D"] if stage == "C" else
                            [prefix + ":C"]
                        )
                        entries.append({
                            "stage_id": prefix + ":" + stage,
                            "case_id": cid,
                            "cloudbed": row["cloudbed"],
                            "task_index": row["task_index"],
                            "start_unix": row["start_unix"],
                            "end_unix": row["end_unix"],
                            "phase": phase,
                            "logical_model": model,
                            "harness": harness,
                            "max_tool_rounds_for_D": MAX_TOOL_ROUNDS,
                            "stage": stage,
                            "dependencies": dependencies,
                            "execution_status": "BLOCKED_DRAFT",
                        })
    ids = {item["stage_id"] for item in entries}
    if len(ids) != len(entries):
        raise RQ2PlanError("Duplicate stage IDs")
    position = {item["stage_id"]: i for i, item in enumerate(entries)}
    if any(
        dep not in position or position[dep] >= position[item["stage_id"]]
        for item in entries for dep in item["dependencies"]
    ):
        raise RQ2PlanError("Unknown or forward stage dependencies")
    # Cross-phase gate: no test D/C before discovery K candidates frozen.
    stage_counts = dict(sorted(Counter(item["stage"] for item in entries).items()))
    if enforce_real_size and stage_counts != {"C": 90, "D": 90, "K": 24}:
        raise RQ2PlanError("Unexpected plan stage totals")
    summary = {
        "protocol": VERSION,
        "status": PLAN_STATUS,
        "preview_only": True,
        "source_verified": _source_sha_checked,
        "split_sha256": split_sha256,
        "manifest_sha256": manifest_sha256,
        "partition": audit,
        "logical_models": list(MODELS),
        "harnesses": list(HARNESSES),
        "provider_model_versions_frozen": False,
        "api_budget_approved": False,
        "can_execute_api": False,
        "cross_phase_gate": "TEST_BLOCKED_UNTIL_DISCOVERY_RULES_FREEZE",
        "stages": stage_counts,
        "total_stage_entries": len(entries),
        "model_api_calls": 0,
        "files_written": False,
        "reads_ground_truth": False,
        "reads_predictions": False,
        "reads_telemetry": False,
        "limitations": [
            "This is a draft preview, not an executable or create-only persisted plan.",
            "Stage C and K are additional LLM calls, while D comprises multiple LLM invocations.",
            "K applies only to the four discovery queries, never to test.",
            "No score or rule knowledge is available to choose or change test cases.",
            "Test phase must remain locked until candidate-rule freeze by a separate verified runner.",
            "Versioned provider IDs, budgets, prompt/bundle validity and user consent still pending.",
        ],
    }
    return {
        **summary,
        "preview_sha256": _sha({"summary": summary, "entries": entries}),
        "entries": entries,
    }


def preview_market(data_dir: Path) -> dict:
    """Real Market preflight: reads frozen GT-free CSVs ONLY."""
    audit = inventory_ood(data_dir, verify_original_hashes=True)
    if audit["ood_cross_split_overlaps"]:
        raise RQ2PlanError("Cross-split OOD overlap found")
    return make_workflow_preview(
        audit["ood_cases_metadata_only"],
        audit["ood_window_groups"],
        split_sha256=audit["split_sha256"],
        manifest_sha256=audit["manifest_sha256"],
        _source_sha_checked=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    plan = preview_market(args.data_dir)
    # Summary only, never the full work-order list or a persisted runnable plan.
    print(json.dumps({key: value for key, value in plan.items() if key != "entries"},
                     ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
