"""REAL GT-free, READ-ONLY pre-registration readiness check for RQ2.

This is a preflight on the ORIGINAL two GT-free CSVs and CURRENT source
tree, NOT an API release generator. No Market.zip, record.csv, ground truth,
model output, tool telemetry, scorer or provider request is read/sent.

No call to run_experiment, no claim, no file writes and no SDK constructor.
All API/test permissions are unconditionally false. Read this JSON output
before independently signing an immutable scientific discovery release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_ck_provider_transport import RELEASE_SHA256
from evaluation.rq2_dryrun_plan import (
    DISCOVERY, HARNESSES, MODELS, TEST, preview_market,
)
from evaluation.rq2_kpi_formalizability_preflight import known_code_kpi_catalog
from evaluation.rq2_protocol_identity_preflight import preview_protocol_identity

VERSION = "rq2_discovery_prereg_readiness_v0"
PKGS = (
    "langchain-core", "langgraph", "langchain-anthropic",
    "langchain-google-genai", "anthropic", "google-genai",
)


class RQ2ReadinessError(ValueError):
    """Original GT-free data, partition, source or runtime provenance drift."""


def _json_bytes(value: dict) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _hash(value: dict) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _packages() -> dict[str, str | None]:
    available = {}
    for package in PKGS:
        try:
            available[package] = version(package)
        except PackageNotFoundError:
            available[package] = None
    return available


def preview_discovery_preregistration(
    *, data_dir: Path, repo_dir: Path,
) -> dict:
    """Read the *original* GT-free files and frozen RQ1 source, no dispatch."""
    root = Path(repo_dir)
    data = Path(data_dir)
    if root.is_symlink() or not (root / "src").is_dir():
        raise RQ2ReadinessError("Expected repository root with src directory")

    # preview_market verifies both original CSV SHA256 values, full 15-case
    # split and group isolation; DOES NOT open Market.zip or original GT.
    plan = preview_market(data)
    identity = preview_protocol_identity(src_root=root / "src")
    catalog = known_code_kpi_catalog()

    partition = plan.get("partition", {})
    stages = plan.get("stages")
    if (
        plan.get("status") != "DRAFT_NOT_EXECUTABLE"
        or plan.get("source_verified") is not True
        or plan.get("can_execute_api") is not False
        or plan.get("cross_phase_gate") != (
            "TEST_BLOCKED_UNTIL_DISCOVERY_RULES_FREEZE"
        )
        or plan.get("total_stage_entries") != 204
        or stages != {"C": 90, "D": 90, "K": 24}
        or plan.get("logical_models") != list(MODELS)
        or plan.get("harnesses") != list(HARNESSES)
        or partition.get("discovery_case_ids") != sorted(DISCOVERY)
        or partition.get("test_case_ids") != sorted(TEST)
        or partition.get("discovery_cases") != 4
        or partition.get("test_cases") != 11
        or partition.get("discovery_windows") != 4
        or partition.get("test_windows") != 10
        or partition.get("min_cross_phase_same_cloudbed_gap_seconds") is None
        or partition["min_cross_phase_same_cloudbed_gap_seconds"] <= 3600
    ):
        raise RQ2ReadinessError("Unacceptable RQ2 cohort or stage plan")
    discovery_stages = [
        item for item in plan["entries"] if item["phase"] == "discovery"
    ]
    test_stages = [
        item for item in plan["entries"] if item["phase"] == "test"
    ]
    if (
        len(discovery_stages) != 72 or len(test_stages) != 132
        or {item["stage"] for item in discovery_stages} != {"D", "C", "K"}
        or {item["stage"] for item in test_stages} != {"D", "C"}
    ):
        raise RQ2ReadinessError("Inconsistent discovery/test stage enumeration")
    if (
        identity.get("rq1_source_blob_sha1_match") is not True
        or identity.get("rq1_D_output_contract_mode_verified") != "v2_enforce"
        or identity.get("source_split_sha256_expected") != plan["split_sha256"]
        or identity.get("source_manifest_sha256_expected") != plan["manifest_sha256"]
        or identity.get("rq2_discovery_api_enabled") is not False
        or identity.get("rq2_test_unlocked") is not False
        or identity.get("C_K_tool_calls_allowed") is not False
    ):
        raise RQ2ReadinessError("Original RQ1/source/prompt identity drift")
    if (
        catalog.get("can_certify_formalizability") is not False
        or catalog.get("ground_truth_access") is not False
        or catalog.get("physical_units_verified") != 0
        or catalog.get("metric_semantics_verified") != 0
    ):
        raise RQ2ReadinessError("KPI catalog assumptions changed; review first")

    body = {
        "version": VERSION,
        "status": "REAL_GT_FREE_SOURCE_CHECKED_PREFREEZE_NOT_EXECUTABLE",
        "data_source_checks": "ORIGINAL_GT_FREE_HASH_AND_PHASE_AUDIT",
        "rq1_frozen_reference_commit": identity["rq1_reference_commit"],
        "rq1_13_blob_match": identity["rq1_source_blob_sha1_match"],
        "rq1_D_output_contract_mode": "v2_enforce",
        "D_variant_scheme": "current",
        "D_max_tool_rounds": 6,
        "D_recursion_limit": 30,
        "model_ids_proposed": {
            name: CANDIDATE_MODELS[name]["model_id"] for name in MODELS
        },
        "harnesses": list(HARNESSES),
        "plan_preview_sha256": plan["preview_sha256"],
        "source_split_sha256": plan["split_sha256"],
        "source_manifest_sha256": plan["manifest_sha256"],
        "discovery_case_ids": list(DISCOVERY),
        "test_case_ids": list(TEST),
        "discovery_window_groups": 4,
        "test_window_groups": 10,
        "discovery_stages": 72,
        "test_stages_locked": 132,
        "total_stages": 204,
        "C_system_prompt_sha256": identity["C_system_prompt_sha256"],
        "K_system_prompt_sha256": identity["K_system_prompt_sha256"],
        "rq2_code_sha256": identity["rq2_code_sha256"],
        "kpi_source_catalog_sha256": catalog["catalog_sha256"],
        "kpi_count_known_in_source_only": len(catalog["metrics"]),
        "kpi_units_semantics_certified": False,
        "python_version": platform.python_version(),
        "runtime_package_versions_observed": _packages(),
        "release_sha256_pinned_in_production": RELEASE_SHA256 is not None,
        "no_cost_ceiling_required": True,
        "requested_policy_no_automatic_retry": True,
        "effective_Google_SDK_retry_timeout_verified": False,
        "effective_Anthropic_SDK_retry_timeout_verified": False,
        "provider_calls_executed": 0,
        "read_ground_truth": False,
        "read_market_telemetry": False,
        "read_llm_predictions": False,
        "files_written": False,
        "scientific_discovery_release_signed": False,
        "can_execute_D": False,
        "can_execute_CK": False,
        "can_execute_test": False,
        "next_gate": [
            "Independent GT-isolated confirmation of 1 discovery per class",
            "Freeze runtime package versions and Google/Anthropic retries/timeouts",
            "Freeze C/K schema and alias scoring policy before inference",
            "Document conservative KPI formalizability + preregister RQ2-C arm",
            "Sign immutable discovery release, pin its hash and read back",
            "Explicit authorization of first single paid discovery stage",
        ],
    }
    return {**body, "preview_sha256": _hash(body)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--repo-dir", type=Path, required=True)
    args = parser.parse_args()
    report = preview_discovery_preregistration(
        data_dir=args.data_dir, repo_dir=args.repo_dir,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
