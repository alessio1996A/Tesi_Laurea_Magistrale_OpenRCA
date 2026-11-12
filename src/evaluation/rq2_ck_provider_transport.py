"""Actual C/K provider path, HARD-BLOCKED until scientific protocol release.

Uses the unchanged RQ1 agent.model_factory.crea_modello to instantiate
Gemini/Anthropic, but no provider client is created at import or in preflight.
Only a future, separately reviewed release with an exact pinned SHA-256
can enable a discovery request. No test stages, no auto retry, no tools,
no budget ceiling (per supervisor), no ground truth or scorer access.

A live pilot MUST call run_one_claimed_ck, which source-verifies the
discovery case, reconstructs C/K solely from saved D/C, creates a claim
BEFORE any SDK construction, then writes raw result + usage into the
existing create-only RQ2 stage record. Ambiguous crash => no auto retry.

This implementation is *not yet executable*: RELEASE_SHA256 is None until
the scientific preregistration is completed, audited and committed.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from langchain_core.messages import AIMessage

from agent.graph_engine import testo_messaggio
from agent.model_factory import crea_modello
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal
from evaluation.rq2_discovery_stage_recorder import RQ2DiscoveryStageRecorder
from evaluation.rq2_stage_binding import (
    prepare_bound_c, prepare_bound_k,
)
from evaluation.rq2_dryrun_plan import (
    DISCOVERY, TEST, HARNESSES, MAX_TOOL_ROUNDS,
)
from evaluation.rq2_toolfree_fake_transport import (
    PREFREEZE_C_SYSTEM_SHA256, PREFREEZE_K_SYSTEM_SHA256,
    _check_package,
)

VERSION = "rq2_ck_provider_transport_v0"
RELEASE_SHA256 = None  # SET ONLY AFTER SCIENTIFIC FREEZE; NEVER in a pilot ad hoc.
RELEASE_FILENAME = "RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json"


class RQ2LiveCKBlocked(RuntimeError):
    """Cannot run C/K without an independently frozen scientific release."""


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_release(root: Path) -> dict:
    """Verify *exact* preregistered release bytes before any provider action."""
    if RELEASE_SHA256 is None:
        raise RQ2LiveCKBlocked("Scientific discovery release is not frozen")
    if (
        type(RELEASE_SHA256) is not str
        or len(RELEASE_SHA256) != 64
        or any(ch not in "0123456789abcdef" for ch in RELEASE_SHA256)
    ):
        raise RQ2LiveCKBlocked("Invalid pinned release hash")
    source = root / "data/rq2" / RELEASE_FILENAME
    if source.is_symlink() or not source.is_file():
        raise RQ2LiveCKBlocked("Pinned release file missing/symlink")
    blob = source.read_bytes()
    if _sha(blob) != RELEASE_SHA256:
        raise RQ2LiveCKBlocked("Scientific release bytes changed")
    try:
        record = json.loads(blob)
    except (ValueError, UnicodeDecodeError) as exc:
        raise RQ2LiveCKBlocked("Scientific release is not JSON") from exc
    if (
        type(record) is not dict
        or record.get("status") != "SCIENTIFIC_DISCOVERY_RELEASE"
        or record.get("test_unlocked") is not False
        or record.get("enable_discovery_CK") is not True
        or record.get("retry_policy") != "NO_AUTOMATIC_RETRY"
        or record.get("model_ids") != {
            m: CANDIDATE_MODELS[m]["model_id"] for m in CANDIDATE_MODELS
        }
        or record.get("C_K_tool_calls_allowed") is not False
        or record.get("budget_limit_usd") is not None
        or record.get("D_output_contract_mode") != "v2_enforce"
        or record.get("D_variant_scheme") != "current"
        or record.get("D_max_tool_rounds") != MAX_TOOL_ROUNDS
        or record.get("D_recursion_limit") != 30
        or record.get("harnesses") != list(HARNESSES)
        or record.get("discovery_case_ids") != list(DISCOVERY)
        or record.get("test_case_ids") != list(TEST)
        or record.get("C_system_prompt_sha256") != PREFREEZE_C_SYSTEM_SHA256
        or record.get("K_system_prompt_sha256") != PREFREEZE_K_SYSTEM_SHA256
    ):
        raise RQ2LiveCKBlocked("Scientific release lacks mandatory safeguards")
    return record


def _source_bound_binding(
    recorder: RQ2DiscoveryStageRecorder, stage_id: str,
) -> tuple[dict, str]:
    """Derive C/K prompt without caller-supplied D answer or GT."""
    if type(stage_id) is not str or stage_id not in recorder.entries:
        raise RQ2LiveCKBlocked("Stage is not in source-verified RQ2 plan")
    entry = recorder.entries[stage_id]
    stage = entry["stage"]
    if entry["phase"] != "discovery" or stage not in ("C", "K"):
        raise RQ2LiveCKBlocked("Only discovery C/K may invoke the provider")
    model_id = CANDIDATE_MODELS[entry["logical_model"]]["model_id"]
    if recorder.store.load_discovery_stage(stage_id=stage_id) is not None:
        raise RQ2LiveCKBlocked("Stage already has an immutable output")
    d_id = stage_id.rsplit(":", 1)[0] + ":D"
    d = recorder.store.load_discovery_stage(stage_id=d_id)
    if d is None or d["status"] != "RECORDED_COMPLETE":
        raise RQ2LiveCKBlocked("Missing valid source-bound discovery D")
    if d["model_id_proposed"] != model_id:
        raise RQ2LiveCKBlocked("Recorded D uses different model ID")
    instruction = recorder._instruction(entry)
    if _sha(instruction.encode("utf-8")) != d["artifact"]["original_instruction_sha256"]:
        raise RQ2LiveCKBlocked("D and original instruction SHA differ")
    run = d["artifact"]["diagnostic_run"]
    if run.get("output_contract_mode") != "v2_enforce":
        raise RQ2LiveCKBlocked("Recorded D does not use frozen RQ1 V2 mode")
    c_id = stage_id.rsplit(":", 1)[0] + ":C"
    c_binding = prepare_bound_c(
        plan=recorder.plan, c_stage_id=c_id,
        original_instruction=instruction, diagnostic_run=run,
    )
    if stage == "C":
        binding = c_binding
    else:
        c = recorder.store.load_discovery_stage(stage_id=c_id)
        if c is None or c["status"] != "RECORDED_COMPLETE":
            raise RQ2LiveCKBlocked("Missing valid source-bound discovery C")
        if c["model_id_proposed"] != model_id:
            raise RQ2LiveCKBlocked("Recorded C uses different model ID")
        if c["artifact"]["c_binding_sha256"] != c_binding["binding_sha256"]:
            raise RQ2LiveCKBlocked("C evidence binding has changed")
        binding = prepare_bound_k(
            plan=recorder.plan, k_stage_id=stage_id,
            original_instruction=instruction, diagnostic_run=run,
            prior_c_binding=c_binding,
            cause_raw_json=c["artifact"]["raw_response"],
        )
    stage_from_package, _, _ = _check_package(binding)
    if stage_from_package != stage:
        raise RQ2LiveCKBlocked("Bound package stage differs")
    return binding, model_id


def _usage(ai: AIMessage) -> dict:
    raw = ai.usage_metadata
    fields = ("input_tokens", "output_tokens", "total_tokens")
    complete = (
        type(raw) is dict
        and all(type(raw.get(key)) is int and raw[key] >= 0 for key in fields)
        and raw["total_tokens"] == raw["input_tokens"] + raw["output_tokens"]
    )
    if not complete:
        return {
            "complete": False, "input_tokens": None,
            "output_tokens": None, "total_tokens": None,
            "input_token_details": None, "output_token_details": None,
        }
    detail = {}
    for key in ("input_token_details", "output_token_details"):
        value = raw.get(key)
        detail[key] = (
            {str(k): v for k, v in value.items()
             if type(k) is str and type(v) is int and v >= 0}
            if type(value) is dict else None
        )
    return {
        "complete": True,
        "input_tokens": raw["input_tokens"],
        "output_tokens": raw["output_tokens"],
        "total_tokens": raw["total_tokens"],
        **detail,
    }


def _one_call(provider: str, model_id: str, messages: list) -> dict:
    """Single remote attempt, no retry and no raw exception credential leaks."""
    started = time.monotonic()
    result = {
        "raw_response": None, "provider_error": None,
        "api_attempts": 0, "usage": {
            "complete": False, "input_tokens": None,
            "output_tokens": None, "total_tokens": None,
            "input_token_details": None, "output_token_details": None,
        },
        "finish_reason": None, "provider_response_model": None,
    }
    try:
        model = crea_modello(provider, model_id)  # lazy model SDK factory
    except Exception as exc:
        result["provider_error"] = "SDK_CONSTRUCTION_ERROR:" + type(exc).__name__
    else:
        result["api_attempts"] = 1  # may be billed even if invoke raises
        try:
            answer = model.invoke(messages)  # ONE request, never bind_tools
        except Exception as exc:
            code = getattr(exc, "status_code", None)
            # Error type and numeric HTTP code only, never exception text
            result["provider_error"] = "PROVIDER_ERROR:" + type(exc).__name__
            if type(code) is int:
                result["provider_error"] += f":HTTP_{code}"
        else:
            if not isinstance(answer, AIMessage):
                result["provider_error"] = "PROTOCOL_ERROR:NonAIMessage"
            elif answer.tool_calls or answer.invalid_tool_calls:
                result["provider_error"] = "PROTOCOL_ERROR:ToolCallsForbidden"
                result["usage"] = _usage(answer)
            else:
                result["usage"] = _usage(answer)
                result["raw_response"] = testo_messaggio(
                    answer.content, solo_testo=True
                )
                meta = answer.response_metadata or {}
                reason = meta.get("finish_reason", meta.get("stop_reason"))
                name = meta.get("model_name", meta.get("model"))
                result["finish_reason"] = reason if type(reason) is str else None
                result["provider_response_model"] = (
                    name if type(name) is str and len(name) <= 160 else None
                )
    result["elapsed_seconds"] = round(time.monotonic() - started, 6)
    return result


def run_one_claimed_ck(
    *, data_dir: Path, stage_id: str, confirm_paid_api: bool = False,
) -> dict:
    """Live path: preregistered source/freeze -> claim -> invoke -> record.

    Currently always blocked by RELEASE_SHA256=None. Never call in unit tests
    with real credentials or with unsaved claims. Does not release test.
    """
    if confirm_paid_api is not True:
        raise RQ2LiveCKBlocked("Explicit paid API invocation confirmation required")
    root = Path(data_dir)
    release = _read_release(root)  # MUST fail before any SDK/claim until frozen
    recorder = RQ2DiscoveryStageRecorder(data_dir=root)
    journal = RQ2DiscoveryClaimJournal(data_dir=root)
    if recorder.store.plan_sha != journal.plan_sha:
        raise RQ2LiveCKBlocked("Source-bound claim/recorder plan drift")
    if release.get("plan_preview_sha256") != recorder.plan["preview_sha256"]:
        raise RQ2LiveCKBlocked("Released discovery plan SHA differs")
    if release.get("source_manifest_sha256") != recorder.plan["manifest_sha256"]:
        raise RQ2LiveCKBlocked("Released manifest SHA differs")
    if release.get("source_split_sha256") != recorder.plan["split_sha256"]:
        raise RQ2LiveCKBlocked("Released split SHA differs")
    binding, model_id = _source_bound_binding(recorder, stage_id)
    entry = recorder.entries[stage_id]
    provider = CANDIDATE_MODELS[entry["logical_model"]]["provider"]
    stage, binding_sha, messages = _check_package(binding)
    # No automatic retry after any crash or ambiguous provider response.
    journal.claim_stage(stage_id=stage_id, model_id_proposed=model_id)
    call = _one_call(provider, model_id, messages)
    receipt = {
        "transport_version": VERSION, "stage_id": stage_id,
        "model_id": model_id, "provider": provider,
        "binding_sha256": binding_sha,
        "raw_response_sha256": (
            _sha(call["raw_response"].encode("utf-8"))
            if call["raw_response"] is not None else None
        ),
        "provider_error": call["provider_error"],
        "api_attempts": call["api_attempts"],
        "usage": call["usage"], "finish_reason": call["finish_reason"],
        "provider_response_model": call["provider_response_model"],
        "elapsed_seconds": call["elapsed_seconds"],
        "tools_enabled": False,
        "is_synthetic": False,
    }
    # After a provider response, recording errors must NOT trigger a retry.
    fn = recorder.record_c if stage == "C" else recorder.record_k
    record = fn(
        stage_id=stage_id, model_id_proposed=model_id,
        raw_response=call["raw_response"],
        provider_error=call["provider_error"],
        transport_receipt=receipt,
    )
    return {
        "stage_id": stage_id,
        "status": record["status"],
        "record_sha256": record["record_sha256"],
        "provider_attempts": call["api_attempts"],
        "usage": call["usage"],
        "financial_cost_ceiling": None,
        "test_unlocked": False,
    }
