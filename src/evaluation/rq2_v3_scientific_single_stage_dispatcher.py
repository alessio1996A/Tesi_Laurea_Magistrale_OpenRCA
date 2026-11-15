"""RQ2-V3 single discovery stage dispatcher, default HARD DISABLED.

D, C and K are separate, individually authorized stages. The dispatcher
NEVER reuses V2 results/IDs/namespace. It requires the independently pinned
V3 ledger + GT-free source/release/runtime/Drive gates, a clean Git checkout,
a one-stage approval and an exact process-level opt-in BEFORE constructing a
provider client, creating a claim, or reading telemetry.

In the current pre-release phase, the runtime gate ALWAYS fails closed,
thus this module CANNOT call paid SDKs with the real source tree.
Unit tests use synthetic ledgers and fake functions; no real paid requests.

After a durable claim: one logical C/K invoke or one bounded D run; no retry.
Ambiguous exceptions leave an orphan claim for manual audit. Failure to
persist a receipt NEVER triggers another provider invocation. A source
digest is not a cryptographic user-approval signature or billing hard cap.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re

from evaluation.experiment_config import ExperimentConfig
from evaluation.experiment_runner import run_experiment
from evaluation.rq2_model_factory import crea_modello_rq2
from evaluation.rq2_probe_adapter import (
    CAUSE_SYSTEM, RULE_SYSTEM,
    prepare_cause_probe, prepare_candidate_rule,
)
from evaluation.rq2_stage_binding import ALLOWED_TOOLS
from evaluation.rq2_v2_unified_live_stage_preflight import (
    UnifiedStagePreviewBlocked, _source_instruction,
)
from evaluation.rq2_v2_unified_scientific_ledger import _read
from evaluation.rq2_v2_unified_scientific_ledger_preflight import (
    UnifiedScientificLedgerBlocked,
)
from evaluation.rq2_v2_ck_provider_transport_candidate import (
    one_ck_call_candidate,
)
from evaluation.rq2_v3_d_runner_capture_candidate import V3DRunnerCapture
from evaluation.rq2_v3_scientific_receipt_adapter_candidate import (
    normalize_v3_ck_call, normalize_v3_d_capture,
)
from evaluation.rq2_v3_scientific_ledger import (
    V3ScientificLedger, V3ScientificLedgerBlocked, _authorization,
)
from evaluation.rq2_v3_unified_gtfree_discovery_plan import (
    VERSION as PROTOCOL, RELEASE_FILE, build_offline_v3_discovery_plan,
)

VERSION = "rq2_v3_scientific_single_stage_dispatcher_v0"
LIVE_OPT_IN_ENV = "OPENRCA_RQ2_V3_ENABLE_PAID_SINGLE_STAGE"
LIVE_OPT_IN_EXACT = "EXPLICIT_V3_ONE_STAGE_ONLY_V1"
# Capture opt-in at module import: changing environment later is insufficient.
LIVE_API_ENABLED = os.environ.get(LIVE_OPT_IN_ENV) == LIVE_OPT_IN_EXACT
SHA1 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
D_MAX_ROUNDS = 6
PLANNER_CHECKS = 2
RECURSION_LIMIT = 30


class V3SingleStageDispatchBlocked(RuntimeError):
    """The stage is not eligible for exactly one approved model run."""


def _admission(*, stage_id: str, approved_stage_id: str,
               expected_commit: str, approved_release_sha256: str,
               stage_authorization: dict, confirm_paid_api: bool) -> dict:
    """Check caller assertion before touching source/ledger/provider."""
    if LIVE_API_ENABLED is not True or confirm_paid_api is not True:
        raise V3SingleStageDispatchBlocked(
            "V3 paid execution disabled; explicit one-stage consent required"
        )
    if (
        type(stage_id) is not str or not stage_id.startswith(PROTOCOL + ":")
        or stage_id != approved_stage_id
        or type(expected_commit) is not str or not SHA1.fullmatch(expected_commit)
        or type(approved_release_sha256) is not str
        or not SHA256.fullmatch(approved_release_sha256)
    ):
        raise V3SingleStageDispatchBlocked("Stage/commit/release external pin missing")
    plan = build_offline_v3_discovery_plan()
    if (
        plan.get("can_execute_api") is not False
        or plan.get("can_run_ood_test") is not False
        or len(plan["ood_test_cases_locked"]) != 11
        or len(plan["entries"]) != 180
    ):
        raise V3SingleStageDispatchBlocked("V3 discovery phase drift")
    row = next((item for item in plan["entries"]
                if item["stage_id"] == stage_id), None)
    if row is None or row["case_id"] in plan["ood_test_cases_locked"]:
        raise V3SingleStageDispatchBlocked("Unknown/V2/OOD stage: forbidden")
    try:
        _authorization(
            stage_authorization, row=row,
            release=approved_release_sha256, commit=expected_commit,
        )
    except V3ScientificLedgerBlocked as exc:
        raise V3SingleStageDispatchBlocked(
            "Unapproved exact V3 stage/model/budget"
        ) from exc
    # This is a caller assertion, not external proof of the user's approval.
    return row


def _release_prompt_proof(*, ledger: V3ScientificLedger,
                          package: dict, stage: str) -> None:
    try:
        release = _read(ledger.data / RELEASE_FILE)
    except UnifiedScientificLedgerBlocked as exc:
        raise V3SingleStageDispatchBlocked("Cannot verify release prompts") from exc
    prompt = CAUSE_SYSTEM if stage == "C" else RULE_SYSTEM
    expected = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    key = "C_system_prompt_sha256" if stage == "C" else "K_system_prompt_sha256"
    if (
        type(release) is not dict or release.get(key) != expected
        or type(package) is not dict
        or package.get("system_prompt_sha256") != expected
        or package.get("ready_for_api") is not False
        or package.get("model_api_calls") != 0
        or type(package.get("package_sha256")) is not str
        or not SHA256.fullmatch(package["package_sha256"])
    ):
        raise V3SingleStageDispatchBlocked("C/K prompt/package release drift")


def _prepare(*, ledger: V3ScientificLedger,
             row: dict) -> tuple[dict, ExperimentConfig, dict | None, dict | None]:
    """Finish source/dataset/parent/package checks BEFORE durable claim."""
    stage_id, stage = row["stage_id"], row["stage"]
    if (
        ledger.plan["preview_sha256"] !=
            build_offline_v3_discovery_plan()["preview_sha256"]
        or ledger._row(stage_id, row["model_id"]) != row
        or ledger.load_claim(stage_id=stage_id) is not None
        or ledger.load_record(stage_id=stage_id) is not None
    ):
        raise V3SingleStageDispatchBlocked("Stage already attempted or plan drift")
    audit = ledger.audit_restart()
    if (
        audit.get("orphan_claims") != 0
        or audit.get("can_execute_api") is not False
        or audit.get("can_run_ood_test") is not False
    ):
        raise V3SingleStageDispatchBlocked("Unresolved claim or unsafe audit")
    try:
        instruction = _source_instruction(
            data_dir=ledger.data, case_id=row["case_id"],
        )
    except UnifiedStagePreviewBlocked as exc:
        raise V3SingleStageDispatchBlocked(
            "Missing/invalid GT-free source instruction"
        ) from exc
    config = ExperimentConfig(
        variant=row["harness"], case_id=row["case_id"],
        model_name=row["model_id"], model_provider=row["model_provider"],
        max_tool_rounds=D_MAX_ROUNDS,
        max_verification_checks=PLANNER_CHECKS,
        recursion_limit=RECURSION_LIMIT, output_contract_mode="v2_enforce",
        variant_scheme="current", repo_dir=ledger.repo, data_dir=ledger.data,
    )
    if (
        config.canonical_variant != row["harness"]
        or config.model_name != row["model_id"]
        or config.model_provider != row["model_provider"]
    ):
        raise V3SingleStageDispatchBlocked("Unexpected D budget/engine/model")

    diagnostic_run = None
    package = None
    for parent_id in row["depends_on"]:
        parent = ledger.load_record(stage_id=parent_id)
        if parent is None or parent["status"] != "RECORDED_COMPLETE":
            raise V3SingleStageDispatchBlocked("Incomplete D/C parent")
    if stage in ("C", "K"):
        stem = stage_id.rsplit(":", 1)[0]
        d_record = ledger.load_record(stage_id=stem + ":D")
        if d_record is None or d_record["status"] != "RECORDED_COMPLETE":
            raise V3SingleStageDispatchBlocked("Valid V3 D record required")
        diagnostic_run = d_record["artifact"]["diagnostic_run"]
        try:
            if stage == "C":
                package = prepare_cause_probe(
                    original_instruction=instruction,
                    diagnostic_run=diagnostic_run,
                    allowed_tool_names=ALLOWED_TOOLS,
                )
            else:
                c_record = ledger.load_record(stage_id=stem + ":C")
                if c_record is None or c_record["status"] != "RECORDED_COMPLETE":
                    raise V3SingleStageDispatchBlocked("Valid V3 C required for K")
                package = prepare_candidate_rule(
                    original_instruction=instruction,
                    diagnostic_run=diagnostic_run,
                    cause_raw_json=c_record["artifact"]["raw_response"],
                    phase="discovery", allowed_tool_names=ALLOWED_TOOLS,
                )
        except V3SingleStageDispatchBlocked:
            raise
        except (ValueError, TypeError, KeyError) as exc:
            raise V3SingleStageDispatchBlocked(
                "Untrusted C/K evidence input: no claim"
            ) from exc
        _release_prompt_proof(ledger=ledger, package=package, stage=stage)
    return row, config, diagnostic_run, package


def preview_one_v3_stage(*, data_dir: Path, repo_dir: Path,
                         stage_id: str, expected_commit: str,
                         approved_release_sha256: str) -> dict:
    """Read-only stage preview; NEVER an authority for a paid request.

    Uses real ledger, and therefore currently fails closed because the
    runtime/Drive release gate is not yet certified.
    """
    ledger = V3ScientificLedger(
        data_dir=data_dir, repo_dir=repo_dir,
        expected_commit=expected_commit,
        approved_release_sha256=approved_release_sha256,
    )
    row = ledger._row(stage_id)
    _, config, _, package = _prepare(ledger=ledger, row=row)
    return {
        "version": VERSION,
        "status": "V3_STAGE_PREPARED_NO_API",
        "stage_id": stage_id,
        "model_id": row["model_id"],
        "logical_model": row["logical_model"],
        "stage": row["stage"],
        "harness": row["harness"],
        "release_sha256": approved_release_sha256,
        "source_commit": expected_commit,
        "prepared_package_sha256": (
            package["package_sha256"] if package is not None else None
        ),
        "max_tool_rounds_D": config.max_tool_rounds,
        "can_execute_api": False,
        "can_create_claim": False,
        "can_run_ood_test": False,
    }


def _provider_once(*, row: dict, config: ExperimentConfig,
                   diagnostic_run: dict | None,
                   package: dict | None) -> dict:
    """Entered only AFTER a durable stage claim; no fallback/retry."""
    stage = row["stage"]
    if stage == "D":
        model = crea_modello_rq2(
            row["model_provider"], row["model_id"],
        )
        capture = V3DRunnerCapture(harness=row["harness"])
        with capture:
            result = run_experiment(
                config, llm=model, verbose=False, salva=False,
            )
        return normalize_v3_d_capture(
            stage_id=row["stage_id"], logical_model=row["logical_model"],
            captured=capture.build_receipt(result),
        )
    if stage not in ("C", "K") or package is None or diagnostic_run is None:
        raise V3SingleStageDispatchBlocked("Missing C/K prepared package")
    messages = package["messages"]
    if (
        type(messages) is not list or len(messages) != 2
        or [message.get("role") for message in messages
            if type(message) is dict] != ["system", "user"]
        or any(type(message) is not dict
               or type(message.get("content")) is not str
               for message in messages)
    ):
        raise V3SingleStageDispatchBlocked("Malformed bound C/K system/user prompt")
    from langchain_core.messages import SystemMessage, HumanMessage
    payload = [
        SystemMessage(content=messages[0]["content"]),
        HumanMessage(content=messages[1]["content"]),
    ]
    call = one_ck_call_candidate(
        row["model_provider"], row["model_id"], payload,
    )
    return normalize_v3_ck_call(
        stage_id=row["stage_id"], logical_model=row["logical_model"],
        call=call, diagnostic_run=diagnostic_run,
    )


def _block_descendants(*, ledger: V3ScientificLedger, row: dict) -> list[str]:
    """Dependency-only records, no new claim or model call on failures."""
    suffixes = ("C", "K") if row["stage"] == "D" else (
        ("K",) if row["stage"] == "C" else ()
    )
    prefix = row["stage_id"].rsplit(":", 1)[0]
    written = []
    for suffix in suffixes:
        stage_id = prefix + ":" + suffix
        ledger.record_stage(
            stage_id=stage_id, model_id=row["model_id"], blocked=True,
        )
        written.append(stage_id)
    return written


def run_one_v3_stage(*, data_dir: Path, repo_dir: Path,
                     stage_id: str, approved_stage_id: str,
                     expected_commit: str, approved_release_sha256: str,
                     stage_authorization: dict,
                     confirm_paid_api: bool = False) -> dict:
    """Exactly one live-capable D/C/K stage, strictly blocked by default.

    The independent source/release + runtime/Drive gates must pass BEFORE
    claim, and the caller's approval assertion must match the exact model,
    stage, source, release and USD operational budget. No budget is a hard cap.
    """
    row = _admission(
        stage_id=stage_id, approved_stage_id=approved_stage_id,
        expected_commit=expected_commit,
        approved_release_sha256=approved_release_sha256,
        stage_authorization=stage_authorization,
        confirm_paid_api=confirm_paid_api,
    )
    ledger = V3ScientificLedger(
        data_dir=data_dir, repo_dir=repo_dir,
        expected_commit=expected_commit,
        approved_release_sha256=approved_release_sha256,
    )
    _, config, diagnostic_run, package = _prepare(
        ledger=ledger, row=row,
    )
    # All potentially failing offline checks are complete. The immutable
    # claim is the last action before touching the SDK/provider.
    claim = ledger.claim_stage(
        stage_id=stage_id, model_id=row["model_id"],
        stage_authorization=stage_authorization,
    )
    # Anything ambiguous from here leaves an orphan. NEVER auto-retry.
    receipt = _provider_once(
        row=row, config=config, diagnostic_run=diagnostic_run,
        package=package,
    )
    result = ledger.record_stage(
        stage_id=stage_id, model_id=row["model_id"],
        receipt=receipt, expected_claim_sha256=claim["claim_sha256"],
    )
    downstream = (
        _block_descendants(ledger=ledger, row=row)
        if result["status"] != "RECORDED_COMPLETE" else []
    )
    audit = ledger.audit_restart()
    if audit.get("orphan_claims") != 0:
        raise V3SingleStageDispatchBlocked("Orphan claim: manual audit mandatory")
    return {
        "version": VERSION,
        "status": "V3_ONE_STAGE_RECORDED",
        "stage_id": stage_id,
        "stage": row["stage"],
        "logical_model": row["logical_model"],
        "model_id": row["model_id"],
        "record_status": result["status"],
        "record_sha256": result["record_sha256"],
        "descendants_blocked": downstream,
        "source_commit": expected_commit,
        "release_sha256": approved_release_sha256,
        "claims_created": 1,
        "automatic_retry_allowed": False,
        "observed_cost_is_hard_cap": False,
        "can_run_ood_test": False,
    }
