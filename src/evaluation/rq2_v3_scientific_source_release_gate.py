"""RQ2-V3 strict GT-free scientific source/release gate: NO API, NO CLAIM.

Production can verify only a pre-existing, canonically serialized V3
release whose SHA256 and clean source commit were pinned externally.
It re-runs the REAL GT-free inventory, freezes the V2 and V3 source
hashes, independently hashes the future runtime/dispatcher modules, and
requires an independent runtime/Drive SDK verifier.

Until that runtime gate and dispatcher exist, the verifier FAILS CLOSED.
Synthetic tests can mock the missing dependency, never real campaign data.
An integrity proof never conveys authorization to spend money, execute
models, inspect GT, or create claims; a separate user-approved per-stage
gate is required.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re

from evaluation.rq2_v2_unified_scientific_ledger import (
    UnifiedScientificLedgerBlocked, _read, _sha as _sha_original,
)
from evaluation.rq2_v2_unified_scientific_ledger_preflight import (
    _repository_commit, _strict_absolute,
)
from evaluation.rq2_v3_scientific_source_inventory import (
    VERSION as INVENTORY_VERSION, STATUS as INVENTORY_STATUS,
    V3_SOURCE_PATHS, FUTURE_REQUIRED_PATHS,
    V3SourceInventoryBlocked, _source_bytes,
    preview_v3_scientific_source_inventory,
)
from evaluation.rq2_v3_unified_gtfree_discovery_plan import (
    VERSION as PROTOCOL, NAMESPACE, RELEASE_FILE,
    build_offline_v3_discovery_plan,
)

VERSION = "rq2_v3_scientific_source_release_gate_v0"
RELEASE_SCHEMA = "rq2_v3_scientific_release_v1"
SHA1 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED_RELEASE_KEYS = frozenset((
    "schema", "protocol", "phase", "source_commit", "plan_sha256",
    "scientific_namespace", "source_inventory_sha256",
    "v2_source_files_sha256", "v3_source_files_sha256",
    "future_source_files_sha256",
    "C_system_prompt_sha256", "K_system_prompt_sha256",
    "split_sha256", "manifest_sha256", "model_ids", "harnesses",
    "discovery_cases", "ood_test_cases_locked", "stage_counts",
    "logical_stages", "text_extraction_policy", "runtime_versions",
    "runtime_attestation_sha256", "single_writer_policy",
    "automatic_retry_allowed", "use_previous_v2_outputs",
    "source_protocol_frozen", "can_run_ood_test", "can_execute_api",
    "api_budget_approved",
))


class V3SourceReleaseBlocked(ValueError):
    """Source/release/runtime cannot be proven: no V3 execution."""


def _digest(value: object) -> str:
    try:
        return _sha_original(value)
    except (UnifiedScientificLedgerBlocked, TypeError, ValueError) as exc:
        raise V3SourceReleaseBlocked("Noncanonical release/inventory") from exc


def _runtime_attestation(*, data_dir: Path, repo_dir: Path,
                         expected_commit: str, release_sha256: str,
                         runtime_versions: dict) -> dict:
    """Mandatory future SDK+Drive verifier; absence is intentional NO-GO."""
    try:
        from evaluation.rq2_v3_scientific_live_stage_preflight import (
            verify_v3_live_runtime_gate,
        )
    except ImportError as exc:
        raise V3SourceReleaseBlocked(
            "V3 SDK/Drive runtime verifier not implemented: NO-GO"
        ) from exc
    return verify_v3_live_runtime_gate(
        data_dir=data_dir, repo_dir=repo_dir,
        expected_source_commit=expected_commit,
        expected_release_sha256=release_sha256,
        expected_runtime_versions=runtime_versions,
    )


def verify_v3_source_release(*, data_dir: Path, repo_dir: Path,
                             release: dict, expected_commit: str,
                             approved_release_sha256: str) -> dict:
    """Verify a future externally pinned V3 release without API or writes."""
    if (
        type(expected_commit) is not str or not SHA1.fullmatch(expected_commit)
        or type(approved_release_sha256) is not str
        or not SHA256.fullmatch(approved_release_sha256)
    ):
        raise V3SourceReleaseBlocked("External clean commit/release pins needed")
    try:
        data = _strict_absolute(data_dir, "data root")
        repo = _strict_absolute(repo_dir, "repository root")
        head, status = _repository_commit(repo)
    except UnifiedScientificLedgerBlocked as exc:
        raise V3SourceReleaseBlocked("Unsafe data/repo or unavailable Git identity") from exc
    if head != expected_commit or status:
        raise V3SourceReleaseBlocked("Source commit drift or dirty Git checkout")

    if type(release) is not dict or set(release) != REQUIRED_RELEASE_KEYS:
        raise V3SourceReleaseBlocked("Missing/foreign release fields")
    try:
        disk_release = _read(data / RELEASE_FILE)
    except UnifiedScientificLedgerBlocked as exc:
        raise V3SourceReleaseBlocked("Unsafe/noncanonical V3 release file") from exc
    if (disk_release is None or disk_release != release
            or _digest(release) != approved_release_sha256):
        raise V3SourceReleaseBlocked("Unpinned or altered release bytes")
    plan = build_offline_v3_discovery_plan()
    basic = {
        "schema": RELEASE_SCHEMA,
        "protocol": PROTOCOL,
        "phase": "discovery",
        "source_commit": expected_commit,
        "plan_sha256": plan["preview_sha256"],
        "scientific_namespace": NAMESPACE.as_posix(),
        "model_ids": plan["model_ids"],
        "harnesses": plan["harnesses"],
        "discovery_cases": plan["discovery_cases"],
        "ood_test_cases_locked": plan["ood_test_cases_locked"],
        "stage_counts": {"D": 60, "C": 60, "K": 60},
        "logical_stages": 180,
        "single_writer_policy": "ONE_WRITER_LOCK_AND_DRIVE_PROOF",
        "automatic_retry_allowed": False,
        "use_previous_v2_outputs": False,
        "source_protocol_frozen": True,
        "can_run_ood_test": False,
        "can_execute_api": False,
        "api_budget_approved": False,
    }
    if any(type(release.get(k)) is not type(v) or release[k] != v
           for k, v in basic.items()):
        raise V3SourceReleaseBlocked("Release plan/OOD/authorization drift")
    if (len(plan["entries"]) != 180
            or len(plan["ood_test_cases_locked"]) != 11
            or plan.get("can_execute_api") is not False
            or plan.get("reuse_v2_d_outputs") is not False
            or plan.get("reuse_v2_c_or_k_outputs") is not False):
        raise V3SourceReleaseBlocked("V3 plan invariants compromised")
    runtime = release["runtime_versions"]
    if (
        type(runtime) is not dict or not runtime
        or any(type(k) is not str or not k or len(k) > 80
               or type(v) is not str or not v or len(v) > 100
               for k, v in runtime.items())
        or type(release["runtime_attestation_sha256"]) is not str
        or not SHA256.fullmatch(release["runtime_attestation_sha256"])
    ):
        raise V3SourceReleaseBlocked("Runtime pin/attestation is malformed")

    try:
        inventory = preview_v3_scientific_source_inventory(
            data_dir=data, src_root=repo / "src",
        )
    except V3SourceInventoryBlocked as exc:
        raise V3SourceReleaseBlocked("Actual GT-free source inventory failed") from exc
    if (
        type(inventory) is not dict
        or inventory.get("version") != INVENTORY_VERSION
        or inventory.get("status") != INVENTORY_STATUS
        or inventory.get("protocol") != PROTOCOL
        or inventory.get("v3_plan_sha256") != plan["preview_sha256"]
        or inventory.get("future_required_paths") != list(FUTURE_REQUIRED_PATHS)
        or inventory.get("missing_future_paths") != []
        or inventory.get("gt_free_source_verified") is not True
        or inventory.get("frozen_rq1_source_identity_verified") is not True
        or inventory.get("can_execute_api") is not False
        or inventory.get("can_create_claim") is not False
        or inventory.get("can_run_ood_test") is not False
        or inventory.get("ground_truth_read") is not False
        or inventory.get("candidate_inventory_sha256") != _digest({
            k: v for k, v in inventory.items()
            if k != "candidate_inventory_sha256"
        })
        or inventory["candidate_inventory_sha256"]
            != release["source_inventory_sha256"]
    ):
        raise V3SourceReleaseBlocked("Inventory incomplete or SHA drift")
    bindings = {
        "v2_source_files_sha256": "v2_source_files_sha256",
        "v3_source_files_sha256": "v3_source_files_sha256",
        "C_system_prompt_sha256": "C_system_prompt_sha256",
        "K_system_prompt_sha256": "K_system_prompt_sha256",
        "split_sha256": "split_sha256",
        "manifest_sha256": "manifest_sha256",
        "model_ids": "model_ids",
        "harnesses": "harnesses",
        "discovery_cases": "discovery_cases",
        "ood_test_cases_locked": "ood_test_cases_locked",
        "stage_counts": "stage_counts",
        "logical_stages": "logical_stages",
        "text_extraction_policy": "text_extraction_policy",
    }
    for rel_key, preview_key in bindings.items():
        if type(release[rel_key]) is not type(inventory.get(preview_key)) or (
            release[rel_key] != inventory[preview_key]
        ):
            raise V3SourceReleaseBlocked("Inventory/release identity mismatch")
    if (type(release["v3_source_files_sha256"]) is not dict
            or set(release["v3_source_files_sha256"]) != set(V3_SOURCE_PATHS)):
        raise V3SourceReleaseBlocked("Unknown/missing V3 source hash")
    # The preview only checks existence of future files. Bind their exact
    # actual source BYTES here, including this module and the dispatcher.
    try:
        actual_future = {
            name: hashlib.sha256(_source_bytes(repo / "src", name)).hexdigest()
            for name in FUTURE_REQUIRED_PATHS
        }
    except V3SourceInventoryBlocked as exc:
        raise V3SourceReleaseBlocked("Missing/symlink future source") from exc
    if (type(release["future_source_files_sha256"]) is not dict
            or release["future_source_files_sha256"] != actual_future):
        raise V3SourceReleaseBlocked("Future dispatcher/runtime source SHA drift")
    if (set(release["future_source_files_sha256"]) != set(FUTURE_REQUIRED_PATHS)
            or any(type(v) is not str or not SHA256.fullmatch(v)
                   for v in actual_future.values())):
        raise V3SourceReleaseBlocked("Missing/unknown future source hash")

    receipt = _runtime_attestation(
        data_dir=data, repo_dir=repo,
        expected_commit=expected_commit,
        release_sha256=approved_release_sha256,
        runtime_versions=runtime,
    )
    required = {
        "status": "V3_SDK_DRIVE_RUNTIME_GATE_VERIFIED",
        "source_commit": expected_commit,
        "release_sha256": approved_release_sha256,
        "runtime_versions": runtime,
        "sdk_retries_disabled_verified": True,
        "per_request_timeout_verified": True,
        "usage_meter_fail_closed": True,
        "single_writer_drive_verified": True,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "model_requests_sent": 0,
    }
    if (type(receipt) is not dict
            or any(type(receipt.get(k)) is not type(v) or receipt[k] != v
                   for k, v in required.items())
            or receipt.get("attestation_sha256") != _digest({
                k: v for k, v in receipt.items()
                if k != "attestation_sha256"
            })
            or receipt["attestation_sha256"] != release["runtime_attestation_sha256"]):
        raise V3SourceReleaseBlocked("SDK/runtime/Drive proof missing or changed")
    return {
        "status": "V3_SOURCE_BOUND_RELEASE_VERIFIED",
        "source_commit": expected_commit,
        "release_sha256": approved_release_sha256,
        "source_inventory_sha256": release["source_inventory_sha256"],
        "plan_sha256": plan["preview_sha256"],
        "can_execute_api": False,
        "can_create_claim": False,
        "can_run_ood_test": False,
        "model_requests_sent": 0,
    }
