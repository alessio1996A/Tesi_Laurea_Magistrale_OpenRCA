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


def _probe_subprocess(*, repo: Path, module: str,
                      expected_commit: str | None = None) -> dict:
    """Execute a pinned, network-disabled synthetic probe, never a provider."""
    import json
    import os
    import subprocess
    import sys

    if module not in {
        "rq2_v2_sync_429_retry_probe",
        "rq2_v2_sync_timeout_loopback_probe",
    }:
        raise V3LiveRuntimeBlocked("Unapproved runtime probe")
    args = [sys.executable, "-m", module, "--repo-dir", str(repo)]
    if expected_commit is not None:
        args += ["--expected-commit", expected_commit]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        (str(repo / "src"), str(repo / "src" / "tests"),
         env.get("PYTHONPATH", ""))
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        completed = subprocess.run(
            args, cwd=repo, env=env, capture_output=True,
            text=True, timeout=60, check=False,
        )
        if completed.returncode != 0 or len(completed.stdout) > 30000:
            raise V3LiveRuntimeBlocked("Pinned synthetic SDK probe failed")
        receipt = json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, ValueError,
            UnicodeError) as exc:
        raise V3LiveRuntimeBlocked("Pinned synthetic SDK probe unavailable") from exc
    if type(receipt) is not dict:
        raise V3LiveRuntimeBlocked("Untrusted synthetic probe result")
    return receipt


def _check_sync_sdk_proofs(*, repo: Path, commit: str) -> dict:
    """Attest only tested sync 429 and loopback timeout, not all transports."""
    fake = _probe_subprocess(
        repo=repo, module="rq2_v2_sync_429_retry_probe",
        expected_commit=commit,
    )
    if (
        fake.get("status") != "SYNC_HTTP_429_MOCK_ONE_SEND_EACH_NO_API_NOT_RELEASED"
        or fake.get("source_commit") != commit
        or fake.get("synthetic_429_http_sends_total") != 4
        or fake.get("external_provider_requests") != 0
        or fake.get("real_credentials_used") is not False
        or fake.get("can_execute_api") is not False
        or fake.get("can_run_ood_test") is not False
        or fake.get("async_streaming_tested") is not False
        or fake.get("usd_hard_cap_guaranteed") is not False
        or type(fake.get("providers")) is not dict
        or set(fake["providers"]) != {"google", "anthropic"}
    ):
        raise V3LiveRuntimeBlocked("Sync 429 evidence missing or overstated")
    for provider in ("google", "anthropic"):
        entries = fake["providers"][provider]
        if (type(entries) is not list or len(entries) != 2
                or [x.get("mode") for x in entries if type(x) is dict]
                    != ["CK_tool_free", "D_bound_tools"]
                or any(type(x) is not dict
                       or x.get("synthetic_429_http_sends") != 1
                       or x.get("http_error_observed") is not True
                       for x in entries)):
            raise V3LiveRuntimeBlocked("Unproven sync 429 provider/mode")
    timeout = _probe_subprocess(
        repo=repo, module="rq2_v2_sync_timeout_loopback_probe",
        expected_commit=commit,
    )
    if (
        timeout.get("status") != "SYNC_LOCAL_STALL_TIMEOUT_CHECKED_NO_API_NO_RELEASE"
        or timeout.get("source_commit") != commit
        or timeout.get("loopback_sends_total") != 4
        or timeout.get("external_api_requests") != 0
        or timeout.get("actual_model_calls") != 0
        or timeout.get("real_credentials_used") is not False
        or timeout.get("can_execute_api") is not False
        or timeout.get("can_run_ood_test") is not False
        or timeout.get("async_streaming_tested") is not False
        or timeout.get("full_stage_timeout_guaranteed") is not False
        or timeout.get("usd_hard_cap_guaranteed") is not False
    ):
        raise V3LiveRuntimeBlocked("Sync loopback proof missing or overstated")
    for provider in ("google", "anthropic"):
        entries = timeout.get(provider)
        if (type(entries) is not list or len(entries) != 2
                or [x.get("mode") for x in entries if type(x) is dict]
                    != ["CK_tool_free", "D_bound_tools"]
                or any(type(x) is not dict
                       or x.get("loopback_http_sends") != 1
                       or x.get("timeout_exception_observed") is not True
                       or type(x.get("elapsed_seconds")) not in (int, float)
                       or not 0 < x["elapsed_seconds"] < 1.5
                       for x in entries)):
            raise V3LiveRuntimeBlocked("Unproven sync loopback provider/mode")
    # Fixed, digestable facts only. Wall-clock probe durations are NOT hashed.
    return {"sync_429_http_sends": 4, "sync_timeout_loopback_sends": 4}


def _check_same_runtime_drive_scratch(*, data: Path) -> dict:
    """Test writer-lock and O_EXCL on a scratch sibling, never scientific data.

    The proof covers competing processes on THIS mounted runtime only.
    Other Colab VMs/sessions are expressly not certified.
    """
    import os
    import shutil
    import subprocess
    import sys
    import tempfile

    from evaluation.rq2_v2_unified_scientific_ledger import (
        _writer_lock, UnifiedScientificLedgerBlocked,
    )

    scratch = None
    lock_script = (
        "import fcntl,os,sys\n"
        "fd=os.open(sys.argv[1],os.O_RDWR)\n"
        "try:\n"
        " fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)\n"
        "except BlockingIOError:\n"
        " sys.exit(7)\n"
        "sys.exit(0)\n"
    )
    create_script = (
        "import os,sys\n"
        "try:\n"
        " fd=os.open(sys.argv[1],os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)\n"
        "except FileExistsError:\n"
        " sys.exit(7)\n"
        "with os.fdopen(fd,'wb') as f:\n"
        " f.write(b'V3');f.flush();os.fsync(f.fileno())\n"
    )
    try:
        scratch = Path(tempfile.mkdtemp(
            prefix="rq2_v3_runtime_scratch_", dir=data.parent,
        ))
        lock = scratch / ".writer.lock"
        with _writer_lock(lock):
            second = subprocess.run(
                [sys.executable, "-c", lock_script, str(lock)],
                capture_output=True, timeout=15, check=False,
            )
            if second.returncode != 7:
                raise V3LiveRuntimeBlocked("Concurrent Drive writer lock accepted")
        with _writer_lock(lock):
            pass
        destination = scratch / "exclusive.txt"
        writers = [
            subprocess.Popen(
                [sys.executable, "-c", create_script, str(destination)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            for _ in range(8)
        ]
        outcomes = [p.wait(timeout=15) for p in writers]
        if (
            outcomes.count(0) != 1 or outcomes.count(7) != 7
            or destination.read_bytes() != b"V3"
        ):
            raise V3LiveRuntimeBlocked("Concurrent Drive O_EXCL failed")
    except (OSError, subprocess.SubprocessError, UnifiedScientificLedgerBlocked
            ) as exc:
        raise V3LiveRuntimeBlocked("Same-runtime Drive scratch proof failed") from exc
    finally:
        if scratch is not None:
            shutil.rmtree(scratch, ignore_errors=False)
    return {
        "same_runtime_lock_denied_second_writer": True,
        "same_runtime_exclusive_creators": 1,
        "same_runtime_writer_processes": 8,
        "other_colab_sessions_or_vms_verified": False,
    }


def verify_v3_live_runtime_gate(*, data_dir: Path, repo_dir: Path,
                                expected_source_commit: str,
                                expected_source_inventory_sha256: str,
                                expected_runtime_versions: dict) -> dict:
    """Independently exercise pinned sync mock/loopback and Drive scratch.

    This is a source-bound, scope-LIMITED runtime attestation, not a
    guarantee of full-stage timeout, global HTTP cap or USD hard cap.
    A valid receipt STILL cannot create a claim or authorize any API.
    """
    preview = preview_v3_live_runtime(
        data_dir=data_dir, repo_dir=repo_dir,
        expected_source_commit=expected_source_commit,
        expected_source_inventory_sha256=expected_source_inventory_sha256,
        expected_runtime_versions=expected_runtime_versions,
    )
    if not all(
        preview.get(key) is True for key in (
            "packages_exact", "sdk_and_rq1_source_exact",
            "rq2_declared_policy_exact",
        )
    ):
        raise V3LiveRuntimeBlocked("NO-GO: pinned SDK/source/policy mismatch")
    data, repo = _validate_inputs(
        data_dir=data_dir, repo_dir=repo_dir,
        expected_source_commit=expected_source_commit,
        expected_source_inventory_sha256=expected_source_inventory_sha256,
        expected_runtime_versions=expected_runtime_versions,
    )
    # The probes themselves enforce fake credentials/transport and exact pin.
    transport = _check_sync_sdk_proofs(repo=repo, commit=expected_source_commit)
    drive = _check_same_runtime_drive_scratch(data=data)
    # Usage is recorded as UNKNOWN when not measured; it is NEVER a hard cap,
    # and the V3 dispatcher requires a new one-stage approval for every call.
    core = {
        "status": "V3_SDK_DRIVE_RUNTIME_GATE_VERIFIED",
        "source_commit": expected_source_commit,
        "source_inventory_sha256": expected_source_inventory_sha256,
        "runtime_versions": dict(expected_runtime_versions),
        "sdk_retries_disabled_verified": True,
        "per_request_timeout_verified": True,
        "usage_meter_fail_closed": True,
        "single_writer_drive_verified": True,
        "sync_mock_scope": "HTTP_429_ONLY_CK_D_ONE_SEND_EACH",
        "timeout_scope": "SYNC_LOOPBACK_READ_TIMEOUT_0P3S_NOT_FULL_STAGE",
        "drive_scope": "SAME_COLAB_RUNTIME_ONE_SERIAL_WRITER_ONLY",
        "transport_observed": transport,
        "drive_observed": drive,
        "async_streaming_tested": False,
        "full_stage_timeout_guaranteed": False,
        "usd_hard_cap_guaranteed": False,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "model_requests_sent": 0,
    }
    from evaluation.rq2_v2_unified_scientific_ledger import _sha
    return {**core, "attestation_sha256": _sha(core)}
