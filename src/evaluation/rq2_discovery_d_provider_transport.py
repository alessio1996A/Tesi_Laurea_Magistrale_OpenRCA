"""Live-capable RQ2 discovery D wrapper around the FROZEN RQ1 runner.

IMPORTANT: production is FAIL-CLOSED because the independent scientific
release SHA in rq2_ck_provider_transport.py is still None. This module does
not import an SDK or make requests at import. No RQ1 file is changed.

After an authentic source/freeze preflight and an exclusive persisted claim,
the only runtime executor is original RQ1 run_experiment(config, llm=..., salva=False),
with explicit RQ2-only provider transport injected through the runner's existing
optional llm parameter. The RQ1 graph, tools and harness code are unchanged. Any raised runner error or identity mismatch after claiming leaves
the claim unresolved for human *operations audit*, NOT an automatic retry.
The human-in-the-loop *diagnosis* feature remains out of scope.

No USD spending cap; retain RQ1 per-call token metrics. NO TEST dispatch.
"""
from __future__ import annotations

from pathlib import Path

from evaluation.experiment_config import ExperimentConfig
from evaluation.experiment_runner import run_experiment
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_model_factory import crea_modello_rq2
from evaluation.rq2_ck_provider_transport import (
    RQ2LiveCKBlocked, _read_release,
)
from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal
from evaluation.rq2_discovery_stage_recorder import RQ2DiscoveryStageRecorder
from evaluation.rq2_protocol_identity_preflight import preview_protocol_identity
from evaluation.rq2_source_bound_d_preflight import (
    preview_discovery_d_config,
)

VERSION = "rq2_discovery_d_provider_transport_v1_rq2_only_factory"


class RQ2LiveDBlocked(RuntimeError):
    """Discovery D cannot execute without frozen provenance and a valid claim."""


def run_one_claimed_discovery_d(
    *, data_dir: Path, repo_dir: Path, stage_id: str,
    confirm_paid_api: bool = False,
) -> dict:
    """Guarded D entrypoint; RELEASE SHA=None means NO production execution.

    May be unit-tested only with a fake release hash, source-bound fake CSVs
    and a monkeypatched run_experiment function. Never call with real API
    credentials before committing an independently reviewed release.
    """
    if confirm_paid_api is not True:
        raise RQ2LiveDBlocked("Explicit paid API confirmation required")
    root = Path(data_dir)
    repo_root = Path(repo_dir)
    # Release validation happens BEFORE any source processing, claim or SDK.
    release = _read_release(root)
    if release.get("enable_discovery_D") is not True:
        raise RQ2LiveDBlocked("Scientific release does not enable D")
    if type(stage_id) is not str:
        raise RQ2LiveDBlocked("Stage ID must be a string")
    if repo_root.is_symlink() or not repo_root.is_dir():
        raise RQ2LiveDBlocked("Repository root not found or symlinked")
    market = root / "Market.zip"
    if market.is_symlink() or not market.is_file():
        raise RQ2LiveDBlocked("Real OpenRCA Market.zip missing or symlinked")

    # Exact RQ1 source blobs and source-only C/K SHA, no model calls.
    identity = preview_protocol_identity(src_root=repo_root / "src")
    if (
        identity["rq1_source_blob_sha1_match"] is not True
        or identity["rq1_D_output_contract_mode_verified"] != "v2_enforce"
        or identity["C_system_prompt_sha256"]
        != release["C_system_prompt_sha256"]
        or identity["K_system_prompt_sha256"]
        != release["K_system_prompt_sha256"]
    ):
        raise RQ2LiveDBlocked("RQL/RQ2 source provenance mismatch")

    recorder = RQ2DiscoveryStageRecorder(data_dir=root)
    journal = RQ2DiscoveryClaimJournal(data_dir=root)
    if recorder.store.plan_sha != journal.plan_sha:
        raise RQ2LiveDBlocked("Claim and D recorder plan mismatch")
    for release_key, source_key in (
        ("plan_preview_sha256", "preview_sha256"),
        ("source_manifest_sha256", "manifest_sha256"),
        ("source_split_sha256", "split_sha256"),
    ):
        if release.get(release_key) != recorder.plan[source_key]:
            raise RQ2LiveDBlocked("Released source/plan SHA mismatch")

    entry = recorder.entries.get(stage_id)
    if (
        entry is None or entry["phase"] != "discovery"
        or entry["stage"] != "D" or entry["dependencies"] != []
    ):
        raise RQ2LiveDBlocked("Only planned discovery D is allowed")
    model = CANDIDATE_MODELS[entry["logical_model"]]
    cfg_preview = preview_discovery_d_config(
        data_dir=root,
        case_id=entry["case_id"],
        logical_model=entry["logical_model"],
        harness=entry["harness"],
        proposed_model_name=model["model_id"],
        output_contract_mode="v2_enforce",
    )
    proposal = cfg_preview["experiment_config_proposal"]
    if (
        cfg_preview["stage_id"] != stage_id
        or cfg_preview["source_verified_in_this_function"] is not True
        or proposal["model_name"] != model["model_id"]
        or proposal["model_provider"] != model["provider"]
        or proposal["variant"] != entry["harness"]
        or proposal["variant_scheme"] != "current"
        or proposal["output_contract_mode"] != "v2_enforce"
        or proposal["max_tool_rounds"] != 6
        or proposal["recursion_limit"] != 30
    ):
        raise RQ2LiveDBlocked("Source-bound D config disagrees with release")

    config = ExperimentConfig(
        variant=entry["harness"], case_id=entry["case_id"],
        model_name=model["model_id"], model_provider=model["provider"],
        max_tool_rounds=6, recursion_limit=30,
        output_contract_mode="v2_enforce", variant_scheme="current",
        repo_dir=repo_root, data_dir=root,
    )
    if recorder.store.load_discovery_stage(stage_id=stage_id) is not None:
        raise RQ2LiveDBlocked("Discovery D already recorded")

    # This is the last action BEFORE the real RQ1 runner may use the SDK.
    # The immutable claim prevents accidental retry even after Colab crash.
    journal.claim_stage(stage_id=stage_id, model_id_proposed=model["model_id"])

    # DO NOT catch and rerun exceptions. If this raises, claim remains
    # CLAIM_WITHOUT_ARTIFACT and requires operational audit.
    # RQ1 runner already accepts an optional model; no source change in RQ1.
    llm = crea_modello_rq2(model["provider"], model["model_id"])
    result = run_experiment(config, llm=llm, verbose=False, salva=False)

    # If the runner returns with unrecognized/malformed provenance, do NOT
    # create a fictitious result: retain unresolved claim for audit.
    if (
        type(result) is not dict
        or result.get("case_id") != entry["case_id"]
        or result.get("variant") != entry["harness"]
        or result.get("variant_scheme") != "current"
        or result.get("model") != model["model_id"]
        or result.get("model_provider") != model["provider"]
        or result.get("max_tool_rounds") != 6
        or result.get("output_contract_mode") != "v2_enforce"
        or type(result.get("tool_trajectory")) is not list
        or "error" not in result
        or type(result.get("metrics")) is not dict
    ):
        raise RQ2LiveDBlocked("RQ1 D returned mismatched provenance; claim retained")

    saved = recorder.record_d(
        stage_id=stage_id, model_id_proposed=model["model_id"],
        diagnostic_run=result,
    )
    return {
        "transport_version": VERSION,
        "stage_id": stage_id,
        "status": saved["status"],
        "record_sha256": saved["record_sha256"],
        "model_id": model["model_id"],
        "model_provider": model["provider"],
        "observed_run_metrics": result["metrics"],
        "original_d_json_status": result.get("json_status"),
        "can_execute_test": False,
        "financial_cost_ceiling": None,
        "automatic_retry": False,
    }
