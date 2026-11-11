"""OFFLINE-only binding of RQ2 C/K prompt packages to draft workflow stages.

No model clients, file I/O, scoring, telemetry or ground truth. This is an
integrity *preflight* over a DRAFT_NOT_EXECUTABLE plan, NOT authorization to
run any stage. It accepts only a recorded D run dict supplied by its caller;
it never calls the historical run_experiment function.

A matching SHA of supplied bytes proves internal consistency only, not that
the GT-free source manifest was actually read/verified. A future RQ2 runner
MUST enforce frozen model IDs, source byte hashes, cost approval, create-only
persistence, and a scientifically valid discovery-to-test rule freeze.
"""
from __future__ import annotations

import hashlib
import json

from evaluation.rq2_dryrun_plan import (
    HARNESSES, MODELS, PLAN_STATUS, VERSION, MAX_TOOL_ROUNDS,
)
from evaluation.rq2_probe_adapter import (
    prepare_cause_probe, prepare_candidate_rule, ProbeInputError,
)

VERSION_BIND = "rq2_offline_stage_binding_v0"
ALLOWED_TOOLS = (
    "tool_get_service_metrics", "tool_get_container_metrics",
    "tool_get_node_metrics", "tool_get_logs", "tool_get_traces",
)
MODEL_PROVIDERS = {
    "gemini": "google",
    "sonnet": "anthropic",
    "haiku": "anthropic",
}
REQUIRED_RUN_KEYS = {
    "case_id", "variant", "variant_scheme", "model",
    "model_provider", "max_tool_rounds", "raw_response",
    "tool_trajectory", "error",
}
PLAN_KEYS = {
    "protocol", "status", "preview_only", "source_verified",
    "split_sha256", "manifest_sha256", "partition",
    "logical_models", "harnesses", "provider_model_versions_frozen",
    "api_budget_approved", "can_execute_api", "cross_phase_gate",
    "stages", "total_stage_entries", "model_api_calls",
    "files_written", "reads_ground_truth", "reads_predictions",
    "reads_telemetry", "limitations", "preview_sha256", "entries",
}
ENTRY_KEYS = {
    "stage_id", "case_id", "cloudbed", "task_index",
    "start_unix", "end_unix", "phase", "logical_model",
    "harness", "max_tool_rounds_for_D", "stage", "dependencies",
    "execution_status",
}
PARTITION_KEYS = {
    "discovery_case_ids", "test_case_ids", "discovery_cases",
    "test_cases", "discovery_windows", "test_windows",
    "min_cross_phase_same_cloudbed_gap_seconds",
    "discovery_by_cloudbed", "test_by_cloudbed",
}


class StageBindingError(ValueError):
    """Stage, source or prior-output provenance cannot be verified offline."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            allow_nan=False, separators=(",", ":"),
        ).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as exc:
        raise StageBindingError("Unserializable package") from exc


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _validate_plan(plan: dict) -> dict[str, dict]:
    if type(plan) is not dict or set(plan) != PLAN_KEYS or (
        plan.get("protocol") != VERSION
        or plan.get("status") != PLAN_STATUS
        or plan.get("preview_only") is not True
        or plan.get("can_execute_api") is not False
        or plan.get("api_budget_approved") is not False
        or plan.get("model_api_calls") != 0
        or plan.get("files_written") is not False
        or plan.get("reads_ground_truth") is not False
        or plan.get("reads_predictions") is not False
        or plan.get("reads_telemetry") is not False
        or plan.get("provider_model_versions_frozen") is not False
        or plan.get("total_stage_entries") != 204
        or plan.get("stages") != {"D": 90, "C": 90, "K": 24}
        or plan.get("logical_models") != list(MODELS)
        or plan.get("harnesses") != list(HARNESSES)
        or plan.get("cross_phase_gate")
        != "TEST_BLOCKED_UNTIL_DISCOVERY_RULES_FREEZE"
    ):
        raise StageBindingError("Only blocked GT-free draft preview is admissible")
    entries = plan.get("entries")
    if type(entries) is not list or len(entries) != 204:
        raise StageBindingError("Expected 204 draft stage entries")
    summary = {
        key: val for key, val in plan.items()
        if key not in ("preview_sha256", "entries")
    }
    expected = _sha({"summary": summary, "entries": entries})
    if plan.get("preview_sha256") != expected:
        raise StageBindingError("Plan preview SHA256 mismatch")
    partitions = plan.get("partition")
    if type(partitions) is not dict or set(partitions) != PARTITION_KEYS:
        raise StageBindingError("Missing/unknown discovery/test partition fields")
    discovery = partitions.get("discovery_case_ids")
    test = partitions.get("test_case_ids")
    if (type(discovery) is not list or type(test) is not list
            or len(discovery) != 4 or len(test) != 11
            or any(type(cid) is not str for cid in discovery + test)
            or len(set(discovery + test)) != 15):
        raise StageBindingError("Invalid phase lists")
    phase_map = {
        **{cid: "discovery" for cid in discovery},
        **{cid: "test" for cid in test},
    }
    by_id = {}
    observed = set()
    for item in entries:
        if type(item) is not dict or set(item) != ENTRY_KEYS:
            raise StageBindingError("Stage must contain only GT-free fields")
        sid = item.get("stage_id")
        cid = item.get("case_id")
        phase = item.get("phase")
        model = item.get("logical_model")
        harness = item.get("harness")
        stage = item.get("stage")
        if (
            type(sid) is not str or sid in by_id
            or cid not in phase_map or phase != phase_map[cid]
            or model not in MODELS or harness not in HARNESSES
            or stage not in ("D", "C", "K")
            or (phase == "test" and stage == "K")
            or item.get("execution_status") != "BLOCKED_DRAFT"
            or item.get("max_tool_rounds_for_D") != MAX_TOOL_ROUNDS
        ):
            raise StageBindingError("Malformed or unauthorized draft stage")
        prefix = f"{VERSION}:{cid}:{model}:{harness}"
        if sid != f"{prefix}:{stage}":
            raise StageBindingError("Stage ID does not match case/model/harness")
        expected_dependency = (
            [] if stage == "D" else
            [prefix + ":D"] if stage == "C" else
            [prefix + ":C"]
        )
        if item.get("dependencies") != expected_dependency:
            raise StageBindingError("Unexpected D/C/K dependencies")
        by_id[sid] = item
        observed.add((cid, model, harness, stage))
    expected_stages = {
        (cid, model, harness, stage)
        for cid, phase in phase_map.items()
        for model in MODELS for harness in HARNESSES
        for stage in (("D", "C", "K") if phase == "discovery" else ("D", "C"))
    }
    if observed != expected_stages or len(by_id) != len(expected_stages):
        raise StageBindingError("Stage set differs from 4+11 draft cohort")
    return by_id


def _run_identity(run: dict, entry: dict) -> None:
    if type(run) is not dict or REQUIRED_RUN_KEYS - set(run):
        raise StageBindingError("Incomplete D run metadata")
    model = run["model"]
    logical = entry["logical_model"]
    if (
        run["case_id"] != entry["case_id"]
        or run["variant"] != entry["harness"]
        or run["variant_scheme"] != "current"
        or run["max_tool_rounds"] != MAX_TOOL_ROUNDS
        or run["model_provider"] != MODEL_PROVIDERS[logical]
        or type(model) is not str
        or logical not in model.lower()
    ):
        raise StageBindingError("D identity inconsistent with planned stage")
    # The exact model versions and temperature are NOT frozen at draft stage.
    # Model substring matching is an early guard, not identity certification.


def _binding(plan: dict, entry: dict, package: dict) -> dict:
    bound = {
        "binding_version": VERSION_BIND,
        "stage_id": entry["stage_id"],
        "phase": entry["phase"],
        "case_id": entry["case_id"],
        "harness": entry["harness"],
        "logical_model": entry["logical_model"],
        "dependency_ids": entry["dependencies"],
        "plan_preview_sha256": plan["preview_sha256"],
        "underlying_package": package,
        "source_verified_in_this_function": False,
        "provider_model_versions_frozen": False,
        "scientific_rules_frozen": False,
        "can_execute_api": False,
        "model_api_calls": 0,
    }
    return {**bound, "binding_sha256": _sha(bound)}


def prepare_bound_c(
    *, plan: dict, c_stage_id: str, original_instruction: str,
    diagnostic_run: dict,
) -> dict:
    """Bind a C prompt to one approved *shape* of draft D/C stage pair."""
    entries = _validate_plan(plan)
    entry = entries.get(c_stage_id)
    if entry is None or entry["stage"] != "C":
        raise StageBindingError("Requested stage is not an existing C stage")
    _run_identity(diagnostic_run, entry)
    try:
        package = prepare_cause_probe(
            original_instruction=original_instruction,
            diagnostic_run=diagnostic_run,
            allowed_tool_names=ALLOWED_TOOLS,
        )
    except ProbeInputError as exc:
        raise StageBindingError("Cannot prepare C input: " + str(exc)) from exc
    return _binding(plan, entry, package)


def prepare_bound_k(
    *, plan: dict, k_stage_id: str, original_instruction: str,
    diagnostic_run: dict, prior_c_binding: dict, cause_raw_json: str,
) -> dict:
    """K is allowed only for discovery, with SAME D input and matching C."""
    entries = _validate_plan(plan)
    entry = entries.get(k_stage_id)
    if entry is None or entry["stage"] != "K" or entry["phase"] != "discovery":
        raise StageBindingError("K stage unavailable outside discovery")
    _run_identity(diagnostic_run, entry)
    c_id = entry["dependencies"][0]
    reference = prepare_bound_c(
        plan=plan, c_stage_id=c_id,
        original_instruction=original_instruction,
        diagnostic_run=diagnostic_run,
    )
    if prior_c_binding != reference:
        raise StageBindingError(
            "C binding is not identical to planned D evidence and instruction"
        )
    try:
        package = prepare_candidate_rule(
            original_instruction=original_instruction,
            diagnostic_run=diagnostic_run,
            cause_raw_json=cause_raw_json,
            phase=entry["phase"],
            allowed_tool_names=ALLOWED_TOOLS,
        )
    except ProbeInputError as exc:
        raise StageBindingError("Cannot prepare K input: " + str(exc)) from exc
    return _binding(plan, entry, package)
