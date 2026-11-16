"""Gate RQ2-V4 per source, release e runtime: NO MODEL API / NO CLAIM.

Convalida solo una release già creata in modalità esclusiva, con commit e
SHA256 esterni, verificando byte delle sorgenti RQ1/V2/V3/V4, GT-free
manifest/split, identità sperimentali, SDK ed evidenza Drive dello STESSO
runtime. Nessuna autorizzazione a pagamento è derivata da questi controlli.

Il trasporto e le prove SDK/Drive restano quelli congelati V3: si
riutilizza il verificatore V3 con nuovi commit/inventory V4, NON le
release/claim/record/diagnosi V3. La prova include soltanto i percorsi
sincroni osservati, non un hard cap USD o un timeout di stage.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re

from evaluation.rq2_v2_unified_scientific_ledger import (
    _read, _sha, UnifiedScientificLedgerBlocked,
)
from evaluation.rq2_v2_unified_scientific_ledger_preflight import (
    _repository_commit, _strict_absolute,
)
from evaluation.rq2_v3_scientific_source_inventory import (
    _source_bytes, V3SourceInventoryBlocked,
)
from evaluation.rq2_v3_scientific_live_stage_preflight import (
    verify_v3_live_runtime_gate, V3LiveRuntimeBlocked,
)
from evaluation.rq2_v3_scientific_source_release_gate import (
    REQUIRED_RELEASE_KEYS as V3_RELEASE_KEYS,
)
from evaluation.rq2_provider_policy_source_audit import EXPECTED_COLAB_VERSIONS
from evaluation.rq2_v4_scientific_source_inventory import (
    VERSION as INVENTORY_VERSION,
    STATUS as INVENTORY_STATUS,
    V4_SOURCE_PATHS, FUTURE_REQUIRED_PATHS,
    V4SourceInventoryBlocked, preview_v4_scientific_source_inventory,
)
from evaluation.rq2_v4_unified_gtfree_discovery_plan import (
    VERSION as PROTOCOL, NAMESPACE, RELEASE_FILE,
    build_offline_v4_discovery_plan,
)
from evaluation.rq2_v4_d_task_aware_contract import VERSION as D_CONTRACT

VERSION = "rq2_v4_scientific_source_release_gate_v0"
RELEASE_SCHEMA = "rq2_v4_scientific_release_v1"
SHA1 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED_RELEASE_KEYS = frozenset((
    "schema", "protocol", "phase", "source_commit", "plan_sha256",
    "scientific_namespace", "source_inventory_sha256",
    "v2_source_files_sha256", "v3_source_files_sha256",
    "v3_future_source_files_sha256", "v4_source_files_sha256",
    "future_source_files_sha256",
    "C_system_prompt_sha256", "K_system_prompt_sha256",
    "split_sha256", "manifest_sha256", "model_ids", "harnesses",
    "discovery_cases", "ood_test_cases_locked", "stage_counts",
    "logical_stages", "text_extraction_policy",
    "v4_task_aware_contract", "runtime_versions",
    "runtime_attestation_sha256", "single_writer_policy",
    "automatic_retry_allowed", "use_previous_v2_outputs",
    "use_previous_v3_outputs", "source_protocol_frozen",
    "can_run_ood_test", "can_execute_api", "api_budget_approved",
))


class V4SourceReleaseBlocked(ValueError):
    """NO-GO: un requisito della release V4 non è verificato."""


def _runtime_proof(*, data: Path, repo: Path, commit: str,
                   inventory_sha: str, versions: dict) -> dict:
    """Stesse prove di trasporto congelate V3, in sessione V4 distinta."""
    try:
        return verify_v3_live_runtime_gate(
            data_dir=data, repo_dir=repo,
            expected_source_commit=commit,
            expected_source_inventory_sha256=inventory_sha,
            expected_runtime_versions=versions,
        )
    except (V3LiveRuntimeBlocked, OSError) as exc:
        raise V4SourceReleaseBlocked("SDK/Drive runtime attestation unavailable") from exc


def verify_v4_source_release(*, data_dir: Path, repo_dir: Path,
                             release: dict, expected_commit: str,
                             approved_release_sha256: str) -> dict:
    """Independently check an externally pinned, already-written release."""
    if (
        type(expected_commit) is not str or not SHA1.fullmatch(expected_commit)
        or type(approved_release_sha256) is not str
        or not SHA256.fullmatch(approved_release_sha256)
    ):
        raise V4SourceReleaseBlocked("Missing external commit/release pins")
    try:
        data = _strict_absolute(data_dir, "V4 data root")
        repo = _strict_absolute(repo_dir, "V4 source root")
        head, dirty = _repository_commit(repo)
    except (UnifiedScientificLedgerBlocked, OSError) as exc:
        raise V4SourceReleaseBlocked("Unsafe or unverifiable Git source") from exc
    if head != expected_commit or dirty:
        raise V4SourceReleaseBlocked("Unclean/incorrect V4 commit")
    if type(release) is not dict or set(release) != REQUIRED_RELEASE_KEYS:
        raise V4SourceReleaseBlocked("Missing/foreign V4 release fields")
    try:
        disk = _read(data / RELEASE_FILE)
        digest = _sha(release)
    except (UnifiedScientificLedgerBlocked, TypeError, ValueError, OSError) as exc:
        raise V4SourceReleaseBlocked("Noncanonical V4 release") from exc
    if disk is None or disk != release or digest != approved_release_sha256:
        raise V4SourceReleaseBlocked("Release bytes/SHA do not match external pin")

    plan = build_offline_v4_discovery_plan()
    expected = {
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
        "v4_task_aware_contract": D_CONTRACT,
        "single_writer_policy": "ONE_WRITER_LOCK_AND_DRIVE_PROOF",
        "automatic_retry_allowed": False,
        "use_previous_v2_outputs": False,
        "use_previous_v3_outputs": False,
        "source_protocol_frozen": True,
        "can_run_ood_test": False,
        "can_execute_api": False,
        "api_budget_approved": False,
    }
    if any(type(release.get(k)) is not type(v) or release[k] != v
           for k, v in expected.items()):
        raise V4SourceReleaseBlocked("Release plan/OOD/policy drift")
    if (
        len(plan["entries"]) != 180
        or len(plan["ood_test_cases_locked"]) != 11
        or plan["can_execute_api"] is not False
        or plan["can_run_ood_test"] is not False
        or plan["reuse_v3_d_outputs"] is not False
        or plan["reuse_v3_c_or_k_outputs"] is not False
        or plan["reuse_v2_d_or_ck_outputs"] is not False
    ):
        raise V4SourceReleaseBlocked("V4 frozen-plan drift")

    versions = release["runtime_versions"]
    if (
        type(versions) is not dict
        or set(versions) != {"python", *EXPECTED_COLAB_VERSIONS}
        or any(type(v) is not str or not v or len(v) > 100
               for v in versions.values())
        or type(release["runtime_attestation_sha256"]) is not str
        or not SHA256.fullmatch(release["runtime_attestation_sha256"])
    ):
        raise V4SourceReleaseBlocked("Runtime versions/attestation pins malformed")

    try:
        inv = preview_v4_scientific_source_inventory(
            data_dir=data, src_root=repo / "src",
        )
    except V4SourceInventoryBlocked as exc:
        raise V4SourceReleaseBlocked("GT-free V4 source inventory failed") from exc
    if (
        type(inv) is not dict
        or inv.get("version") != INVENTORY_VERSION
        or inv.get("status") != INVENTORY_STATUS
        or inv.get("protocol") != PROTOCOL
        or inv.get("plan_sha256") != plan["preview_sha256"]
        or inv.get("candidate_inventory_sha256") != _sha({
            key: val for key, val in inv.items()
            if key != "candidate_inventory_sha256"
        })
        or inv.get("missing_future_paths") != []
        or inv.get("future_required_paths") != list(FUTURE_REQUIRED_PATHS)
        or inv.get("gt_free_source_verified") is not True
        or inv.get("frozen_rq1_source_identity_verified") is not True
        or inv.get("can_execute_api") is not False
        or inv.get("can_create_claim") is not False
        or inv.get("can_run_ood_test") is not False
        or inv.get("ground_truth_read") is not False
        or inv.get("candidate_inventory_sha256") != release["source_inventory_sha256"]
    ):
        raise V4SourceReleaseBlocked("Unverified V4 inventory/plan")
    bindings = (
        "v2_source_files_sha256", "v3_source_files_sha256",
        "v3_future_source_files_sha256", "v4_source_files_sha256",
        "C_system_prompt_sha256", "K_system_prompt_sha256",
        "split_sha256", "manifest_sha256",
        "model_ids", "harnesses", "discovery_cases",
        "ood_test_cases_locked", "stage_counts", "logical_stages",
        "text_extraction_policy", "v4_task_aware_contract",
    )
    if any(
        type(release[key]) is not type(inv.get(key))
        or release[key] != inv[key] for key in bindings
    ):
        raise V4SourceReleaseBlocked("Source hash or prompt/model drift")
    if (
        type(release["v4_source_files_sha256"]) is not dict
        or set(release["v4_source_files_sha256"]) != set(V4_SOURCE_PATHS)
        or type(release["future_source_files_sha256"]) is not dict
        or set(release["future_source_files_sha256"]) != set(FUTURE_REQUIRED_PATHS)
    ):
        raise V4SourceReleaseBlocked("V4 source path inventory incomplete")
    try:
        future_actual = {
            name: hashlib.sha256(_source_bytes(repo / "src", name)).hexdigest()
            for name in FUTURE_REQUIRED_PATHS
        }
    except V3SourceInventoryBlocked as exc:
        raise V4SourceReleaseBlocked("V4 future dispatcher absent or unsafe") from exc
    if release["future_source_files_sha256"] != future_actual:
        raise V4SourceReleaseBlocked("V4 future dispatcher source drift")

    proof = _runtime_proof(
        data=data, repo=repo, commit=expected_commit,
        inventory_sha=release["source_inventory_sha256"], versions=versions,
    )
    # Exact fields, including realistic limitations: never make up hard caps.
    expected_runtime = {
        "status": "V3_SDK_DRIVE_RUNTIME_GATE_VERIFIED",
        "source_commit": expected_commit,
        "source_inventory_sha256": release["source_inventory_sha256"],
        "runtime_versions": versions,
        "sdk_retries_disabled_verified": True,
        "per_request_timeout_verified": True,
        "usage_meter_fail_closed": True,
        "single_writer_drive_verified": True,
        "sync_mock_scope": "HTTP_429_ONLY_CK_D_ONE_SEND_EACH",
        "timeout_scope": "SYNC_LOOPBACK_READ_TIMEOUT_0P3S_NOT_FULL_STAGE",
        "drive_scope": "SAME_COLAB_RUNTIME_ONE_SERIAL_WRITER_ONLY",
        "usage_scope": "UNKNOWN_PRESERVED_PER_STAGE_CONSENT_NO_HARD_CAP",
        "transport_observed": {
            "sync_429_http_sends": 4,
            "sync_timeout_loopback_sends": 4,
        },
        "drive_observed": {
            "same_runtime_lock_denied_second_writer": True,
            "same_runtime_exclusive_creators": 1,
            "same_runtime_writer_processes": 8,
            "other_colab_sessions_or_vms_verified": False,
        },
        "usage_observed": {
            "missing_usage_cost_recorded_as": "UNKNOWN",
            "stage_budget_is_hard_cap": False,
            "one_stage_approval_required": True,
        },
        "async_streaming_tested": False,
        "full_stage_timeout_guaranteed": False,
        "usd_hard_cap_guaranteed": False,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "model_requests_sent": 0,
    }
    if (
        type(proof) is not dict
        or any(
            type(proof.get(k)) is not type(v) or proof[k] != v
            for k, v in expected_runtime.items()
        )
        or proof.get("attestation_sha256") != _sha({
            k: v for k, v in proof.items() if k != "attestation_sha256"
        })
        or proof["attestation_sha256"] != release["runtime_attestation_sha256"]
    ):
        raise V4SourceReleaseBlocked("Insufficient V4 runtime proof")

    return {
        "status": "V4_SOURCE_BOUND_RELEASE_VERIFIED",
        "source_commit": expected_commit,
        "release_sha256": approved_release_sha256,
        "source_inventory_sha256": release["source_inventory_sha256"],
        "plan_sha256": plan["preview_sha256"],
        "can_execute_api": False,
        "can_create_claim": False,
        "can_run_ood_test": False,
        "model_requests_sent": 0,
    }
