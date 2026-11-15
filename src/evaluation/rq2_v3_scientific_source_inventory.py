"""Read-only RQ2-V3 source inventory proposal; NOT a scientific release.

This deliberately reuses the already-verified, frozen V2 GT-free source
preflight without changing V2 or reading GT, Market.zip, telemetry or scorer.
It separately hashes the actual V3 source files and freezes a *candidate*
inventory schema, including prompt/model/policy identities. The result is
not commit-pinned, runtime-verified, authorized or sufficient for ledger use.

The future V3 source-release gate MUST:
  - verify an external clean Git commit and recompute this inventory;
  - incorporate the future dispatcher/gate/runtime modules into the freeze;
  - verify real GT-free sources, SDK retry/timeout and Drive single-writer;
  - independently pin release SHA and enforce per-stage user approval.
This module NEVER creates a release, claim, record, model or API request.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from evaluation.rq2_probe_adapter import CAUSE_SYSTEM, RULE_SYSTEM
from evaluation.rq2_v2_unified_discovery_plan import (
    VERSION as V2_PROTOCOL, DISCOVERY, TEST, HARNESSES, MODELS,
)
from evaluation.rq2_v2_unified_release_preflight import (
    VERSION as V2_SOURCE_VERSION,
    SOURCE_PATHS as V2_SOURCE_PATHS,
    preview_unified_source_bound,
)
from evaluation.rq2_v2_ck_text_extraction_candidate import POLICY
from evaluation.rq2_v3_unified_gtfree_discovery_plan import (
    VERSION as V3_PROTOCOL, NAMESPACE, RELEASE_FILE,
    build_offline_v3_discovery_plan,
)

VERSION = "rq2_v3_scientific_source_inventory_preview_v0"
STATUS = "V3_SOURCE_INVENTORY_PREVIEW_INCOMPLETE_NO_RELEASE"
MAX_SOURCE_BYTES = 5_000_000
SHA256 = re.compile(r"[0-9a-f]{64}\Z")

# V2 files, including shared engines/runner/validators, are independently
# hashed by its frozen source preflight. V3 additions are hashed here.
V3_SOURCE_PATHS = (
    "evaluation/rq2_v2_ck_text_extraction_candidate.py",
    "evaluation/rq2_v2_ck_provider_transport_candidate.py",
    "evaluation/rq2_v3_unified_gtfree_discovery_plan.py",
    "evaluation/rq2_v3_d_final_stream_candidate.py",
    "evaluation/rq2_v3_d_runner_capture_candidate.py",
    "evaluation/rq2_v3_ck_provenance_receipt_candidate.py",
    "evaluation/rq2_v3_scientific_receipt_adapter_candidate.py",
    "evaluation/rq2_v3_scientific_ledger.py",
    "evaluation/rq2_v3_scientific_source_inventory.py",
)

# These files do NOT yet exist. Their absence is disclosed and blocks
# the eventual live release; they are NOT treated as empty files or hashed.
FUTURE_REQUIRED_PATHS = (
    "evaluation/rq2_v3_scientific_source_release_gate.py",
    "evaluation/rq2_v3_scientific_live_stage_preflight.py",
    "evaluation/rq2_v3_scientific_single_stage_dispatcher.py",
)


class V3SourceInventoryBlocked(ValueError):
    """Unsafe or unverified source inventory: fail closed, never dispatch."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise V3SourceInventoryBlocked("Noncanonical inventory") from exc


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _root(path: Path, label: str) -> Path:
    if (
        not isinstance(path, Path) or not path.is_absolute()
        or ".." in path.parts or path.is_symlink() or not path.is_dir()
    ):
        raise V3SourceInventoryBlocked("Unsafe/missing " + label)
    return path


def _source_bytes(root: Path, relative: str) -> bytes:
    if (type(relative) is not str or relative.startswith("/")
            or "\" in relative or not relative.endswith(".py")
            or any(p in ("", ".", "..") for p in relative.split("/"))):
        raise V3SourceInventoryBlocked("Unsafe inventory source path")
    path = root
    for component in relative.split("/"):
        path = path / component
        if path.is_symlink():
            raise V3SourceInventoryBlocked("Symlink in V3 source path")
    if not path.is_file() or path.stat().st_size > MAX_SOURCE_BYTES:
        raise V3SourceInventoryBlocked("Missing/oversized V3 source file")
    try:
        return path.read_bytes().replace(b"\r\n", b"\n")
    except OSError as exc:
        raise V3SourceInventoryBlocked("Cannot read V3 source file") from exc


def _check_v2_source_receipt(v2: object, *, plan: dict, src_root: Path) -> dict:
    if type(v2) is not dict:
        raise V3SourceInventoryBlocked("Missing verified V2 GT-free preview")
    hashes = v2.get("source_files_sha256")
    expected = {
        "version": V2_SOURCE_VERSION,
        "status": "OFFLINE_SOURCE_BOUND_NO_RELEASE_NO_API",
        "protocol": V2_PROTOCOL,
        "plan_preview_sha256": plan["base_v2_plan_sha256"],
        "entries_sha256": plan["base_v2_entries_sha256"],
        "source_file_count": len(V2_SOURCE_PATHS),
        "gt_free_source_verified": True,
        "frozen_rq1_source_identity_verified": True,
        "split_sha256": "c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724",
        "manifest_sha256": "5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13",
        "C_system_prompt_sha256": hashlib.sha256(
            CAUSE_SYSTEM.encode("utf-8")
        ).hexdigest(),
        "K_system_prompt_sha256": hashlib.sha256(
            RULE_SYSTEM.encode("utf-8")
        ).hexdigest(),
        "model_ids": plan["model_ids"],
        "harnesses": list(HARNESSES),
        "discovery_cases": list(DISCOVERY),
        "ood_test_cases_locked": 11,
        "stage_counts": {"D": 60, "C": 60, "K": 60},
        "logical_stages": 180,
        "d_max_tool_rounds": 6,
        "planning_checks_reserved": 2,
        "d_output_contract": "v2_enforce",
        "ground_truth_read": False,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "scientific_release_frozen": False,
        "claims_written": 0,
        "data_files_written": False,
        "model_requests_sent": 0,
        "source_commit_pinned_for_release": False,
    }
    if any(type(v2.get(k)) is not type(val) or v2[k] != val
           for k, val in expected.items()):
        raise V3SourceInventoryBlocked("V2 GT-free/source/model/prompt drift")
    if (
        type(hashes) is not dict
        or set(hashes) != set(V2_SOURCE_PATHS)
        or v2.get("source_file_count") != len(hashes)
        or any(type(v) is not str or not SHA256.fullmatch(v)
               for v in hashes.values())
    ):
        raise V3SourceInventoryBlocked("Missing/foreign V2 baseline source hashes")
    # The preflight checked sources; rehash here to detect a stale or
    # invented preview as well as a source file changed during verification.
    current = {
        name: hashlib.sha256(_source_bytes(src_root, name)).hexdigest()
        for name in V2_SOURCE_PATHS
    }
    if current != hashes:
        raise V3SourceInventoryBlocked("V2 source changed since preflight")
    return current


def preview_v3_scientific_source_inventory(*, data_dir: Path,
                                           src_root: Path) -> dict:
    """Read-only candidate inventory from real V2 GT-free preflight.

    src_root is the checkout's 'src' directory, NOT the repo root.
    Does not access any historical outputs, GT, scorer or model API.
    """
    data = _root(data_dir, "GT-free data root")
    src = _root(src_root, "source root")
    plan = build_offline_v3_discovery_plan()
    if (
        plan.get("protocol") != V3_PROTOCOL
        or plan.get("status") != "V3_GT_FREE_DRAFT_NO_RELEASE_NO_API"
        or plan.get("logical_stages") != 180
        or plan.get("stage_counts") != {"D": 60, "C": 60, "K": 60}
        or plan.get("models") != list(MODELS)
        or plan.get("harnesses") != list(HARNESSES)
        or plan.get("discovery_cases") != list(DISCOVERY)
        or plan.get("ood_test_cases_locked") != list(TEST)
        or len(plan.get("ood_test_cases_locked", [])) != 11
        or plan.get("reuse_v2_d_outputs") is not False
        or plan.get("reuse_v2_c_or_k_outputs") is not False
        or plan.get("can_execute_api") is not False
        or plan.get("can_run_ood_test") is not False
        or plan.get("scientific_namespace_proposed") != NAMESPACE.as_posix()
        or plan.get("release_relative_path_proposed") != RELEASE_FILE.as_posix()
        or plan.get("uniform_final_text_extraction_policy_candidate") != POLICY
        or len(plan.get("entries", [])) != 180
    ):
        raise V3SourceInventoryBlocked("V3 180-stage/11-OOD plan drift")

    try:
        v2 = preview_unified_source_bound(data_dir=data, src_root=src)
    except Exception as exc:
        raise V3SourceInventoryBlocked(
            "V2 GT-free source preflight failed"
        ) from exc
    baseline = _check_v2_source_receipt(v2, plan=plan, src_root=src)

    if (len(set(V3_SOURCE_PATHS)) != len(V3_SOURCE_PATHS)
            or set(V3_SOURCE_PATHS) & set(V2_SOURCE_PATHS)
            or set(FUTURE_REQUIRED_PATHS) & (
                set(V3_SOURCE_PATHS) | set(V2_SOURCE_PATHS)
            )):
        raise V3SourceInventoryBlocked("Duplicate/overlapping source paths")

    v3_hashes = {
        name: hashlib.sha256(_source_bytes(src, name)).hexdigest()
        for name in V3_SOURCE_PATHS
    }
    # These are expected holes, not implicit permissions to proceed.
    pending = []
    for path in FUTURE_REQUIRED_PATHS:
        future = src / path
        if future.is_symlink():
            raise V3SourceInventoryBlocked("Unsafe future-source symlink")
        if not future.is_file():
            pending.append(path)

    core = {
        "version": VERSION,
        "status": STATUS,
        "protocol": V3_PROTOCOL,
        "v2_source_version": V2_SOURCE_VERSION,
        "v2_plan_sha256": plan["base_v2_plan_sha256"],
        "v3_plan_sha256": plan["preview_sha256"],
        "v3_entries_sha256": plan["entries_sha256"],
        "scientific_namespace": NAMESPACE.as_posix(),
        "release_path_proposed": RELEASE_FILE.as_posix(),
        "sha256_line_ending_policy": "CRLF_TO_LF_SOURCE_BYTES",
        "v2_source_files_sha256": baseline,
        "v3_source_files_sha256": v3_hashes,
        "C_system_prompt_sha256": v2["C_system_prompt_sha256"],
        "K_system_prompt_sha256": v2["K_system_prompt_sha256"],
        "text_extraction_policy": POLICY,
        "split_sha256": v2["split_sha256"],
        "manifest_sha256": v2["manifest_sha256"],
        "model_ids": dict(plan["model_ids"]),
        "models": list(MODELS),
        "harnesses": list(HARNESSES),
        "discovery_cases": list(DISCOVERY),
        "ood_test_cases_locked": list(TEST),
        "logical_stages": 180,
        "stage_counts": {"D": 60, "C": 60, "K": 60},
        "gt_free_source_verified": True,
        "frozen_rq1_source_identity_verified": True,
        "future_required_paths": list(FUTURE_REQUIRED_PATHS),
        "missing_future_paths": pending,
        "source_commit_pinned": False,
        "runtime_versions_verified": False,
        "single_writer_drive_verified": False,
        "scientific_release_frozen": False,
        "can_create_claim": False,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "ground_truth_read": False,
        "model_requests_sent": 0,
        "files_written": False,
    }
    return {**core, "candidate_inventory_sha256": _sha(core)}
