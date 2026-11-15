"""G4A RQ2-V2 unificata: preview source-bound GT-free, NON una release.

Verifica RQ1 frozen, plan 5x3x4, file sorgenti necessari, hash prompt C/K
e split/manifest V1 da `preview_gt_free_sources`. Non crea output,
client/provider, claim, credenziali, scorer, pseudocodice o HTTP.
Il return non ha alcuna autorizzazione API; anche con sorgenti integre,
mancano il journal scientifico live, una release firmata, budget e runtime.

Questo modulo e' volutamente separato dagli store sintetici: i loro
record di prova non diventeranno mai risultati della campagna reale.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from evaluation.rq2_protocol_identity_preflight import (
    preview_protocol_identity, ProtocolIdentityError,
)
from evaluation.rq2_probe_adapter import (
    CAUSE_SYSTEM, RULE_SYSTEM, VERSION as ADAPTER_VERSION,
)
from evaluation.rq2_v2_unified_discovery_plan import (
    DISCOVERY, TEST, HARNESSES, MODELS, STAGES,
    EXPECTED_SPLIT_SHA256, EXPECTED_MANIFEST_SHA256,
    MAX_TOOL_ROUNDS, MAX_VERIFICATION_CHECKS, RECURSION_LIMIT,
    VERSION as UNIFIED_PROTOCOL,
    build_offline_discovery_plan, preview_gt_free_sources,
)

VERSION = "rq2_v2_unified_release_source_preflight_v0"
# File effettivamente usati dalla infrastruttura di diagnosi e dalla
# preparazione C/K, NON un elenco di futuri componenti ancora da creare.
SOURCE_PATHS = (
    "agent/graph_engine.py",
    "agent/rq2_v2_graph_engine.py",
    "agent/verify_graph.py",
    "agent/model_factory.py",
    "evaluation/experiment_config.py",
    "evaluation/experiment_runner.py",
    "evaluation/rq2_v2_unified_discovery_plan.py",
    "evaluation/rq2_v2_unified_provenance_gate.py",
    "evaluation/rq2_evidence_bundle.py",
    "evaluation/rq2_probe_adapter.py",
    "evaluation/rq2_output_contracts.py",
    "evaluation/rq2_stage_binding.py",
    "harness/investigation_planner.py",
    "harness/structural_temporal_verifier.py",
    "output/v2_task_contract.py",
    # RQ2-V2: componente di release + vera persistenza/dispatch.
    # Le SHA qui sono una PREVIEW: il freeze definitivo sara'
    # associato a un commit clean e approvazione esterna separata.
    "evaluation/rq2_v2_unified_release_preflight.py",
    "evaluation/rq2_v2_unified_release_blueprint.py",
    "evaluation/rq2_v2_unified_scientific_release_contract.py",
    "evaluation/rq2_v2_unified_scientific_ledger_preflight.py",
    "evaluation/rq2_v2_unified_scientific_ledger.py",
    "evaluation/rq2_v2_unified_live_stage_preflight.py",
    "evaluation/rq2_v2_unified_single_stage_dispatcher.py",
    "evaluation/rq2_v2_unified_provider_result_adapter.py",
    "evaluation/rq2_v2_unified_live_dispatcher.py",
    # Factory RQ2-only e trasporto sincrono C/K gia' collaudati.
    "evaluation/rq2_model_factory.py",
    "evaluation/rq2_ck_provider_transport.py",
    "evaluation/rq2_budget_preflight.py",
    "evaluation/rq2_provider_policy_source_audit.py",
    "evaluation/rq2_sdk_retry_mock_probe.py",
)


class UnifiedRQ2SourcePreflightError(ValueError):
    """La preview non puo' certificare le sorgenti o la coorte GT-free."""


def _safe_root(root: Path) -> Path:
    if not isinstance(root, Path) or not root.is_absolute() or ".." in root.parts:
        raise UnifiedRQ2SourcePreflightError(
            "Expected absolute Path without traversal"
        )
    if not root.is_dir() or root.is_symlink():
        raise UnifiedRQ2SourcePreflightError("Missing or symlink root")
    return root


def _source_bytes(root: Path, relative: str) -> bytes:
    # Relative paths statici, non sono argomenti derivati da output del LLM.
    p = root / relative
    if p.is_symlink() or not p.is_file():
        raise UnifiedRQ2SourcePreflightError("Missing/symlink source: " + relative)
    try:
        return p.read_bytes().replace(b"\r\n", b"\n")
    except OSError as exc:
        raise UnifiedRQ2SourcePreflightError("Cannot read source: " + relative) from exc


def preview_unified_source_bound(*, data_dir: Path, src_root: Path) -> dict:
    """Fail-closed: verifica fonti originali; non consente nessuna API.

    src_root: directory `src` nel checkout locale, non la root del repo.
    data_dir: root che contiene i due CSV GT-free di split e manifest.
    """
    source_root = _safe_root(src_root)
    data_root = _safe_root(data_dir)

    plan = build_offline_discovery_plan()
    if (
        plan["logical_stages"] != 180
        or plan["discovery_arm_cases"] != 60
        or plan["stage_counts"] != {"D": 60, "C": 60, "K": 60}
        or len(plan["entries"]) != 180
        or plan["can_call_model_api"] is not False
        or plan["can_run_ood_test"] is not False
    ):
        raise UnifiedRQ2SourcePreflightError("Unified plan drift")

    gt_free = preview_gt_free_sources(data_root)
    if (
        gt_free.get("split_manifest_source_verified") is not True
        or gt_free.get("split_sha256") != EXPECTED_SPLIT_SHA256
        or gt_free.get("manifest_sha256") != EXPECTED_MANIFEST_SHA256
        or gt_free.get("base_plan_preview_sha256") != plan["preview_sha256"]
        or gt_free.get("logical_stages") != 180
        or gt_free.get("can_call_model_api") is not False
        or gt_free.get("can_run_ood_test") is not False
        or gt_free.get("ground_truth_read") is not False
    ):
        raise UnifiedRQ2SourcePreflightError("GT-free source check drift")

    try:
        rq1 = preview_protocol_identity(src_root=source_root)
    except ProtocolIdentityError as exc:
        raise UnifiedRQ2SourcePreflightError(
            "Frozen RQ1 source identity cannot be established"
        ) from exc
    source_sha = {
        p: hashlib.sha256(_source_bytes(source_root, p)).hexdigest()
        for p in SOURCE_PATHS
    }
    prompt_sha = {
        "C": hashlib.sha256(CAUSE_SYSTEM.encode("utf-8")).hexdigest(),
        "K": hashlib.sha256(RULE_SYSTEM.encode("utf-8")).hexdigest(),
    }
    if (
        rq1.get("rq1_source_blob_sha1_match") is not True
        or rq1.get("rq1_D_output_contract_mode_verified") != "v2_enforce"
        or rq1.get("rq2_scientific_protocol_frozen") is not False
        or rq1.get("rq2_discovery_api_enabled") is not False
        or rq1.get("rq2_test_unlocked") is not False
        or rq1.get("models_proposed") != plan["model_ids"]
        or rq1.get("C_system_prompt_sha256") != prompt_sha["C"]
        or rq1.get("K_system_prompt_sha256") != prompt_sha["K"]
        or rq1.get("rq1_source_sha256", {}).get(
            "evaluation/experiment_runner.py"
        ) != source_sha["evaluation/experiment_runner.py"]
        or rq1.get("rq1_source_sha256", {}).get(
            "agent/model_factory.py"
        ) != source_sha["agent/model_factory.py"]
        or tuple(HARNESSES) != tuple(plan["harnesses"])
        or tuple(MODELS) != tuple(plan["models"])
        or tuple(STAGES) != ("D", "C", "K")
        or len(DISCOVERY) != 4 or len(TEST) != 11
        or MAX_TOOL_ROUNDS != 6
        or MAX_VERIFICATION_CHECKS != 2
        or RECURSION_LIMIT != 30
        or ADAPTER_VERSION != rq1.get("probe_adapter_version")
    ):
        raise UnifiedRQ2SourcePreflightError(
            "RQ1/LLM/prompt/source protocol parity mismatch"
        )

    return {
        "version": VERSION,
        "protocol": UNIFIED_PROTOCOL,
        "status": "OFFLINE_SOURCE_BOUND_NO_RELEASE_NO_API",
        "plan_preview_sha256": plan["preview_sha256"],
        "entries_sha256": plan["entries_sha256"],
        "source_files_sha256": source_sha,
        "source_file_count": len(source_sha),
        "frozen_rq1_source_identity_verified": True,
        "gt_free_source_verified": True,
        "split_sha256": gt_free["split_sha256"],
        "manifest_sha256": gt_free["manifest_sha256"],
        "probe_adapter_version": ADAPTER_VERSION,
        "C_system_prompt_sha256": prompt_sha["C"],
        "K_system_prompt_sha256": prompt_sha["K"],
        "model_ids": plan["model_ids"],
        "harnesses": list(HARNESSES),
        "discovery_cases": list(DISCOVERY),
        "ood_test_cases_locked": len(TEST),
        "stage_counts": plan["stage_counts"],
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
