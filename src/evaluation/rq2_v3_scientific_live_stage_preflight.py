"""Read-only RQ2-V3 runtime/SDK preview: NO SDK CLIENT, NO HTTP, NO CLAIM.

This is a NON-AUTHORIZING preflight on the exact intended Colab checkout.
It verifies pinned package versions and known SDK source digests, the frozen
RQ1 factory, the RQ2-only factory's declared policy, and repository identity.
It cannot certify *effective* LangChain->SDK HTTP retries/timeouts or Google
Drive single-writer semantics: those require separate network-disabled mock
probes and Drive scratch tests. Until then the release gate FAILS CLOSED.

No GT, Market.zip, telemetry, API key, scientific data artifact or historical
prediction is read or written by this module.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import platform
import re

from evaluation.rq2_model_factory import (
    TIMEOUT_SECONDS, GOOGLE_HTTP_ATTEMPTS,
    ANTHROPIC_MAX_RETRIES, ANTHROPIC_MAX_TOKENS,
)
from evaluation.rq2_provider_policy_source_audit import (
    EXPECTED_COLAB_VERSIONS, preview_provider_policy,
)
from evaluation.rq2_sdk_retry_mock_probe import EXPECTED_SOURCE_DIGESTS
from evaluation.rq2_v2_unified_scientific_ledger_preflight import (
    _repository_commit, _strict_absolute,
    UnifiedScientificLedgerBlocked as V2PreflightBlocked,
)

VERSION = "rq2_v3_runtime_policy_preview_v0"
PREVIEW_STATUS = "V3_RUNTIME_PREVIEW_BLOCKED_PENDING_SDK_AND_DRIVE_PROOFS"
SHA1 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
POLICY = {
    "rq2_google_http_attempts_requested": 1,
    "rq2_anthropic_max_retries_requested": 0,
    "rq2_per_request_timeout_seconds_requested": 300.0,
    "rq2_anthropic_max_tokens": 4096,
}
REQUIRED_PACKAGE_KEYS = frozenset({"python", *EXPECTED_COLAB_VERSIONS})


class V3LiveRuntimeBlocked(RuntimeError):
    """Fail-closed; NEVER use this as permission to call any provider."""


def _validate_inputs(*, data_dir: Path, repo_dir: Path,
                     expected_source_commit: str,
                     expected_source_inventory_sha256: str,
                     expected_runtime_versions: dict) -> tuple[Path, Path]:
    if (
        type(expected_source_commit) is not str
        or not SHA1.fullmatch(expected_source_commit)
        or type(expected_source_inventory_sha256) is not str
        or not SHA256.fullmatch(expected_source_inventory_sha256)
        or type(expected_runtime_versions) is not dict
        or set(expected_runtime_versions) != REQUIRED_PACKAGE_KEYS
        or any(type(v) is not str or not v or len(v) > 100
               for v in expected_runtime_versions.values())
    ):
        raise V3LiveRuntimeBlocked("External commit/inventory/runtime pins required")
    try:
        data = _strict_absolute(data_dir, "V3 data root")
        repo = _strict_absolute(repo_dir, "V3 repo root")
        head, status = _repository_commit(repo)
    except (V2PreflightBlocked, OSError) as exc:
        raise V3LiveRuntimeBlocked("Source checkout cannot be proven") from exc
    if head != expected_source_commit or status:
        raise V3LiveRuntimeBlocked("Dirty/drifted source commit")
    return data, repo


def preview_v3_live_runtime(*, data_dir: Path, repo_dir: Path,
                            expected_source_commit: str,
                            expected_source_inventory_sha256: str,
                            expected_runtime_versions: dict) -> dict:
    """Only inspect runtime metadata/source, never construct SDK providers.

    No signed attestation is created. All paid/live flags remain false even
    when package versions, policy constants and source hashes match.
    """
    _, repo = _validate_inputs(
        data_dir=data_dir, repo_dir=repo_dir,
        expected_source_commit=expected_source_commit,
        expected_source_inventory_sha256=expected_source_inventory_sha256,
        expected_runtime_versions=expected_runtime_versions,
    )
    try:
        baseline = preview_provider_policy(repo_dir=repo)
    except Exception as exc:
        raise V3LiveRuntimeBlocked("Frozen provider policy audit failed") from exc
    if (
        type(baseline) is not dict
        or baseline.get("can_execute_D") is not False
        or baseline.get("can_execute_CK") is not False
        or baseline.get("can_execute_test") is not False
        or baseline.get("files_written") is not False
        or baseline.get("api_calls_executed") != 0
        or baseline.get("read_ground_truth") is not False
        or baseline.get("read_market") is not False
        or baseline.get("read_predictions") is not False
        or type(baseline.get("packages")) is not dict
        or set(baseline["packages"]) != set(EXPECTED_COLAB_VERSIONS)
    ):
        raise V3LiveRuntimeBlocked("Untrusted/unsafe provider source preview")

    packages = baseline["packages"]
    observed = {
        "python": platform.python_version(),
        **{name: packages[name].get("version")
           for name in EXPECTED_COLAB_VERSIONS},
    }
    versions_exact = (
        observed == expected_runtime_versions
        and all(observed[name] == version
                for name, version in EXPECTED_COLAB_VERSIONS.items())
        and baseline.get("matches_previous_colab_versions") is True
    )
    source_exact = (
        baseline.get("original_factory_unchanged") is True
        and type(baseline.get("factory")) is dict
        and baseline["factory"].get("frozen_rq1_factory_blob_match") is True
        and all(
            type(packages.get(name)) is dict
            and packages[name].get("known_source_sha256") == digest
            for name, digest in EXPECTED_SOURCE_DIGESTS.items()
        )
    )
    declared = {
        "rq2_google_http_attempts_requested": GOOGLE_HTTP_ATTEMPTS,
        "rq2_anthropic_max_retries_requested": ANTHROPIC_MAX_RETRIES,
        "rq2_per_request_timeout_seconds_requested": TIMEOUT_SECONDS,
        "rq2_anthropic_max_tokens": ANTHROPIC_MAX_TOKENS,
    }
    policy_exact = (
        declared == POLICY
        and all(type(declared[k]) is type(v)
                for k, v in POLICY.items())
    )
    blockers = []
    if not versions_exact:
        blockers.append("PINNED_RUNTIME_VERSION_MISMATCH")
    if not source_exact:
        blockers.append("SDK_OR_FROZEN_RQ1_SOURCE_MISMATCH")
    if not policy_exact:
        blockers.append("RQ2_FACTORY_DECLARED_POLICY_MISMATCH")
    blockers.extend((
        "LANGCHAIN_TO_SDK_EFFECTIVE_RETRY_TIMEOUT_NOT_PROVEN",
        "DRIVE_SINGLE_WRITER_NOT_PROVEN",
        "NO_RELEASE_OR_STAGE_API_PERMISSION",
    ))

    return {
        "version": VERSION,
        "status": PREVIEW_STATUS,
        "source_commit": expected_source_commit,
        "source_inventory_sha256": expected_source_inventory_sha256,
        "expected_runtime_versions": dict(expected_runtime_versions),
        "observed_runtime_versions": observed,
        "packages_exact": versions_exact,
        "sdk_and_rq1_source_exact": source_exact,
        "rq2_declared_policy_exact": policy_exact,
        "declared_policy": declared,
        "blockers": blockers,
        "sdk_retries_disabled_verified": False,
        "per_request_timeout_verified": False,
        "usage_meter_fail_closed": False,
        "single_writer_drive_verified": False,
        "attestation_sha256": None,
        "can_execute_api": False,
        "can_create_claim": False,
        "can_run_ood_test": False,
        "real_provider_requests": 0,
        "read_ground_truth": False,
        "files_written": False,
    }


def verify_v3_live_runtime_gate(*, data_dir: Path, repo_dir: Path,
                                expected_source_commit: str,
                                expected_source_inventory_sha256: str,
                                expected_runtime_versions: dict) -> dict:
    """Definitive gate: must refuse until live SDK/Drive proofs exist.

    Deliberately NO success path at this pre-release stage. A later audited
    implementation must validate actual loopback/Drive proof artifacts; it
    cannot promote a source preview or caller-supplied booleans to an
    independently verified scientific attestation.
    """
    preview = preview_v3_live_runtime(
        data_dir=data_dir, repo_dir=repo_dir,
        expected_source_commit=expected_source_commit,
        expected_source_inventory_sha256=expected_source_inventory_sha256,
        expected_runtime_versions=expected_runtime_versions,
    )
    raise V3LiveRuntimeBlocked(
        "NO-GO: " + ", ".join(preview["blockers"])
    )
