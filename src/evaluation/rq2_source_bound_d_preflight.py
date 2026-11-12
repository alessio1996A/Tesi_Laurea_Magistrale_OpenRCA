"""Read-only, GT-free RQ2 discovery D preflight on the ORIGINAL manifest.

Only constructs a non-executable ExperimentConfig *description*. Never calls
run_experiment, a model provider, telemetry tools or Market.zip. No writes.
The real preview_market() verifies frozen GT-free split and manifest bytes.
The original RQ1 runner remains unchanged.

Only DISCOVERY stages are eligible for this PREVIEW: the held-out TEST phase
has no release mechanism here. Future live execution needs a NEW, scientifically
frozen protocol, exact model IDs, cost approval, and separate create-only output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from evaluation.experiment_config import ExperimentConfig
from evaluation.rq2_dryrun_plan import (
    DISCOVERY, EXPECTED_MANIFEST_SHA256, EXPECTED_SPLIT_SHA256,
    HARNESSES, MAX_TOOL_ROUNDS, MODELS, PLAN_STATUS, VERSION, preview_market,
)
from evaluation.rq2_stage_binding import (
    MODEL_PROVIDERS, StageBindingError, _validate_plan,
)
from evaluation.v2_case_window_audit import (
    MANIFEST_COLUMNS, SPLIT_COLUMNS, _read_csv, _window,
)

VERSION_PREFLIGHT = "rq2_source_bound_d_preflight_v0"
_SUPPORTED_D_MODES = frozenset(("legacy", "v2_enforce"))


class SourceBoundDError(ValueError):
    """Mismatch between GT-free input, stage, or blocked D configuration."""


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preview_discovery_d_config(
    *,
    data_dir: Path,
    case_id: str,
    logical_model: str,
    harness: str,
    proposed_model_name: str,
    output_contract_mode: str,
) -> dict:
    """Check source-bound D identity; return ONLY blocked serializable metadata.

    This function does not return the ExperimentConfig object and contains
    no dispatch method. Candidate provider IDs and D contract mode remain
    explicitly unapproved/unfrozen.
    """
    if not (
        type(case_id) is str and case_id in DISCOVERY
        and type(logical_model) is str and logical_model in MODELS
        and type(harness) is str and harness in HARNESSES
        and type(proposed_model_name) is str
        and proposed_model_name.strip()
        and logical_model in proposed_model_name.lower()
        and type(output_contract_mode) is str
        and output_contract_mode in _SUPPORTED_D_MODES
    ):
        raise SourceBoundDError("Invalid discovery case, model, harness or D mode")

    root = Path(data_dir)
    split_file = root / "data/processed/split_market_v1.csv"
    manifest_file = root / "data/processed/benchmark_inputs_market.csv"
    try:
        # preview_market verifies ORIGINAL input hashes and all 15 OOD
        # time-window groups; a synthetic plan with a SHA string is not enough.
        plan = preview_market(root)
        entries = _validate_plan(plan)
        if (
            plan["source_verified"] is not True
            or plan["status"] != PLAN_STATUS
            or plan["provider_model_versions_frozen"] is not False
            or plan["can_execute_api"] is not False
            or plan["api_budget_approved"] is not False
        ):
            raise SourceBoundDError("Blocked source-verified plan required")

        sid = f"{VERSION}:{case_id}:{logical_model}:{harness}:D"
        entry = entries.get(sid)
        if (
            entry is None or entry["phase"] != "discovery"
            or entry["stage"] != "D" or entry["dependencies"] != []
            or entry["execution_status"] != "BLOCKED_DRAFT"
            or entry["max_tool_rounds_for_D"] != MAX_TOOL_ROUNDS
        ):
            raise SourceBoundDError("No permitted discovery D stage")

        # Revalidate the bytes at the point where the input is bound. This
        # prevents accidental use of changed files between separate checks.
        split_sha = _file_sha256(split_file)
        manifest_sha = _file_sha256(manifest_file)
        if (
            split_sha != EXPECTED_SPLIT_SHA256
            or manifest_sha != EXPECTED_MANIFEST_SHA256
            or split_sha != plan["split_sha256"]
            or manifest_sha != plan["manifest_sha256"]
        ):
            raise SourceBoundDError("GT-free source hash mismatch")

        split = _read_csv(split_file, SPLIT_COLUMNS)
        manifest = _read_csv(manifest_file, MANIFEST_COLUMNS)
        if set(split) != set(manifest):
            raise SourceBoundDError("Manifest/split IDs differ")
        row = manifest.get(case_id)
        srow = split.get(case_id)
        if row is None or srow is None or srow["split"] != "ood_holdout":
            raise SourceBoundDError("Selected discovery case absent from OOD cohort")
        if any(row[name] != srow[name] for name in (
            "cloudbed", "start_unix", "end_unix",
        )):
            raise SourceBoundDError("Manifest/split case metadata mismatch")
        start, end = _window(row)
        if (
            row["cloudbed"] != entry["cloudbed"]
            or row["task_index"] != entry["task_index"]
            or start != entry["start_unix"]
            or end != entry["end_unix"]
            or type(row["instruction"]) is not str
            or not row["instruction"].strip()
        ):
            raise SourceBoundDError("D stage differs from original GT-free task")
        # Verify original input bytes remain stable during the read.
        if (
            split_sha != _file_sha256(split_file)
            or manifest_sha != _file_sha256(manifest_file)
        ):
            raise SourceBoundDError("GT-free source changed during preflight")

        provider = MODEL_PROVIDERS[logical_model]
        config = ExperimentConfig(
            variant=harness, case_id=case_id,
            model_name=proposed_model_name,
            model_provider=provider,
            max_tool_rounds=MAX_TOOL_ROUNDS,
            variant_scheme="current",
            output_contract_mode=output_contract_mode,
            data_dir=root,
        )
        if (
            config.canonical_variant != harness
            or config.max_tool_rounds != entry["max_tool_rounds_for_D"]
            or config.manifest_path != manifest_file
        ):
            raise SourceBoundDError("Existing RQ1 config differs from stage")
    except SourceBoundDError:
        raise
    except (ValueError, OSError, KeyError, TypeError, StageBindingError) as exc:
        raise SourceBoundDError("GT-free source or draft plan failed preflight") from exc

    return {
        "preflight_version": VERSION_PREFLIGHT,
        "status": "SOURCE_BOUND_DISCOVERY_D_PREVIEW_ONLY",
        "stage_id": sid,
        "phase": "discovery",
        "case_id": case_id,
        "cloudbed": entry["cloudbed"],
        "task_index": entry["task_index"],
        "window": {"start_unix": start, "end_unix": end},
        "instruction_sha256": hashlib.sha256(
            row["instruction"].encode("utf-8")
        ).hexdigest(),
        "plan_preview_sha256": plan["preview_sha256"],
        "split_sha256": split_sha,
        "manifest_sha256": manifest_sha,
        "source_verified_in_this_function": True,
        "experiment_config_proposal": {
            "variant": config.canonical_variant,
            "variant_scheme": config.variant_scheme,
            "model_provider": config.model_provider,
            "model_name": config.model_name,
            "model_logical": logical_model,
            "max_tool_rounds": config.max_tool_rounds,
            "recursion_limit": config.recursion_limit,
            "output_contract_mode": config.output_contract_mode,
        },
        "model_version_frozen": False,
        "output_contract_mode_frozen": False,
        "scientific_protocol_frozen": False,
        "api_budget_approved": False,
        "can_execute_api": False,
        "can_execute_D": False,
        "can_execute_test": False,
        "can_execute_K": False,
        "read_ground_truth": False,
        "read_telemetry": False,
        "read_predictions": False,
        "model_api_calls": 0,
        "files_written": False,
        "code_execution": "NO_MODEL_NO_TOOLS_NO_RUN_EXPERIMENT",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--case-id", required=True, choices=list(DISCOVERY))
    parser.add_argument("--logical-model", required=True, choices=list(MODELS))
    parser.add_argument("--harness", required=True, choices=list(HARNESSES))
    parser.add_argument("--proposed-model-name", required=True)
    parser.add_argument(
        "--output-contract-mode", required=True, choices=sorted(_SUPPORTED_D_MODES),
    )
    args = parser.parse_args()
    report = preview_discovery_d_config(
        data_dir=args.data_dir, case_id=args.case_id,
        logical_model=args.logical_model, harness=args.harness,
        proposed_model_name=args.proposed_model_name,
        output_contract_mode=args.output_contract_mode,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
