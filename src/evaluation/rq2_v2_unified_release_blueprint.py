"""RQ2-V2 UNIFICATA — descrizione offline della futura release G4B.

Obiettivo: un solo contratto D/C/K su 4 discovery x 5 harness x 3 LLM.
NON costruisce clienti, chiama modelli, scarica dati o crea claim/file.
NON è un dispatcher e NON autorizza una release/scadenza economica.

L'input deve essere una preview G4A source-bound già verificata dal
chiamante. I limiti invocazioni sono del grafo LangGraph, non HTTP effettive
(ritenti trasporto/SDK sono ancora da certificare nel gate scientifico).
"""
from __future__ import annotations

import hashlib
import json
import re

from evaluation.rq2_v2_unified_discovery_plan import (
    ENGINES, HARNESSES, MODELS, VERSION as PLAN_VERSION,
    build_offline_discovery_plan,
)
from evaluation.rq2_v2_unified_release_preflight import (
    SOURCE_PATHS, VERSION as SOURCE_VERSION,
)

VERSION = "rq2_v2_unified_release_blueprint_v0"
STATUS = "DRAFT_ALL_EXECUTION_BLOCKED_NO_API"
SCIENTIFIC_NAMESPACE_CANDIDATE = "data/rq2_v2_unified_scientific_v1"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
# Bound logico di invoke D: 6 tool round + 1 final ReAct;
# Planning/PAVE: 4 exploration round + 1 final. Non HTTP garanti.
REACT_D_MAX_INVOKES = 7
PLANNER_D_MAX_INVOKES = 5
TOOL_FREE_CK_MAX_INVOKES = 1


class UnifiedRQ2BlueprintError(ValueError):
    """Le condizioni minime della futura release non sono dimostrate."""


def _hash(obj: object) -> str:
    raw = json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _verify_source_preview(source: dict, plan: dict) -> None:
    if type(source) is not dict:
        raise UnifiedRQ2BlueprintError("G4A source report required")
    file_hashes = source.get("source_files_sha256")
    if type(file_hashes) is not dict or set(file_hashes) != set(SOURCE_PATHS):
        raise UnifiedRQ2BlueprintError("Missing/foreign source paths")
    if any(type(value) is not str or not SHA256.fullmatch(value)
           for value in file_hashes.values()):
        raise UnifiedRQ2BlueprintError("Malformed source hash")
    if any(
        type(source.get(field)) is not str
        or not SHA256.fullmatch(source[field])
        for field in ("C_system_prompt_sha256", "K_system_prompt_sha256")
    ):
        raise UnifiedRQ2BlueprintError("Missing prompt hashes")
    exact = {
        "version": SOURCE_VERSION,
        "protocol": PLAN_VERSION,
        "status": "OFFLINE_SOURCE_BOUND_NO_RELEASE_NO_API",
        "plan_preview_sha256": plan["preview_sha256"],
        "entries_sha256": plan["entries_sha256"],
        "source_file_count": len(SOURCE_PATHS),
        "frozen_rq1_source_identity_verified": True,
        "gt_free_source_verified": True,
        "split_sha256": plan["split_sha256_expected"],
        "manifest_sha256": plan["manifest_sha256_expected"],
        "model_ids": plan["model_ids"],
        "harnesses": list(HARNESSES),
        "discovery_cases": plan["discovery_cases"],
        "ood_test_cases_locked": 11,
        "stage_counts": {"D": 60, "C": 60, "K": 60},
        "logical_stages": 180,
        "d_max_tool_rounds": 6,
        "planning_checks_reserved": 2,
        "d_output_contract": "v2_enforce",
        "claims_written": 0,
        "data_files_written": False,
        "model_requests_sent": 0,
        "ground_truth_read": False,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "scientific_release_frozen": False,
        "approved_api_budget_exists": False,
        "unified_production_ledger_implemented": False,
        "unified_provider_dispatcher_implemented": False,
        "source_commit_pinned_for_release": False,
    }
    for key, expected in exact.items():
        if type(source.get(key)) is not type(expected) or source.get(key) != expected:
            raise UnifiedRQ2BlueprintError(
                "Source-bound preview mismatch: " + key
            )


def build_unified_release_blueprint(*, source_preview: dict) -> dict:
    """Descrizione auditabile e NON eseguibile dei 180 stage della Opzione A."""
    plan = build_offline_discovery_plan()
    _verify_source_preview(source_preview, plan)
    stages = []
    for row in plan["entries"]:
        stage = row["stage"]
        harness = row["harness"]
        is_planner = harness in ("A1_8R_Planning", "A1_PAVE")
        if stage == "D":
            invocations = (
                PLANNER_D_MAX_INVOKES if is_planner
                else REACT_D_MAX_INVOKES
            )
        else:
            invocations = TOOL_FREE_CK_MAX_INVOKES
        stages.append({
            "stage_id": row["stage_id"],
            "case_id": row["case_id"],
            "logical_model": row["logical_model"],
            "model_id": row["model_id"],
            "provider": row["model_provider"],
            "harness": harness,
            "d_engine": ENGINES[harness],
            "stage": stage,
            "depends_on": list(row["depends_on"]),
            "max_logical_model_invocations_candidate": invocations,
            "tool_calls_allowed": stage == "D",
            "d_tool_rounds_cap": 6 if stage == "D" else 0,
            "d_planner_checks_reserved": (
                2 if stage == "D" and is_planner else 0
            ),
            "candidate_transport_retries_verified": False,
            "stage_execution_permission": "BLOCKED_NO_RELEASE",
        })
    if len(stages) != 180 or len({x["stage_id"] for x in stages}) != 180:
        raise UnifiedRQ2BlueprintError("Not the complete 180-stage matrix")
    per_model = {
        model: {
            "D": sum(x["logical_model"] == model and x["stage"] == "D"
                     for x in stages),
            "C": sum(x["logical_model"] == model and x["stage"] == "C"
                     for x in stages),
            "K": sum(x["logical_model"] == model and x["stage"] == "K"
                     for x in stages),
        }
        for model in MODELS
    }
    if any(counts != {"D": 20, "C": 20, "K": 20}
           for counts in per_model.values()):
        raise UnifiedRQ2BlueprintError("Unbalanced provider stage counts")
    total_graph_invocations_upper = sum(
        row["max_logical_model_invocations_candidate"] for row in stages
    )
    # 3 ReAct harness * 4 cases * 3 models * 7 invocations D=252
    # 2 planner harness * 4 cases * 3 models * 5 D = 120
    # C/K 60+60 = 120; invocations <=492 if all stages reached.
    if total_graph_invocations_upper != 492:
        raise UnifiedRQ2BlueprintError("Graph-level budget calculation drift")
    core = {
        "version": VERSION,
        "status": STATUS,
        "source_preflight_version": SOURCE_VERSION,
        "source_plan_sha256": plan["preview_sha256"],
        "source_files_sha256": dict(source_preview["source_files_sha256"]),
        "split_sha256": source_preview["split_sha256"],
        "manifest_sha256": source_preview["manifest_sha256"],
        "prompt_sha256": {
            "C": source_preview["C_system_prompt_sha256"],
            "K": source_preview["K_system_prompt_sha256"],
        },
        "proposed_scientific_namespace": SCIENTIFIC_NAMESPACE_CANDIDATE,
        "no_synthetic_store_reuse": True,
        "frozen_historical_v1_and_rq1_untouched": True,
        "discovery_case_count": 4,
        "ood_test_cases_locked": 11,
        "harness_model_arms": 15,
        "logical_stage_count": 180,
        "per_model_stage_counts": per_model,
        "max_graph_invocations_if_all_stages_reached_candidate": (
            total_graph_invocations_upper
        ),
        "max_http_requests_guaranteed": None,
        "max_billed_usd_guaranteed": None,
        "transport_policy_effective_retries_certified": False,
        "sample_size_per_harness_model": 4,
        "scientific_interpretation": (
            "K is a candidate hypothesis, not a proven deterministic "
            "detector, fault type, or generalization result"
        ),
        "missing_release_prerequisites": [
            "A real GT-free source-bound preflight on actual split and manifest",
            "One non-synthetic scientific create-only ledger with readback",
            "Single source-bound D/C/K dispatcher tested end-to-end with fake SDK",
            "Strict model-level request/usage meter across D/C/K",
            "Exact LangChain to SDK retry and timeout policy proven offline",
            "Explicit provider quotas, price refresh and operational stop policy",
            "Single writer/concurrency and interrupted-claim recovery policy",
            "Clean Git commit, pinned source/runtime hashes and immutable release",
            "Explicit paid API authorization for an approved pilot/batch",
        ],
        "can_write_scientific_claims": False,
        "can_create_provider_client": False,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "api_authorization": "NOT_REQUESTED",
        "scientific_release_frozen": False,
        "entries": stages,
    }
    return {**core, "blueprint_sha256": _hash(core)}
