"""Versioned RQ2 C/K transport CANDIDATE (NOT connected to scientific live).

This is an audit-only successor to rq2_ck_provider_transport._one_call:
- one model.invoke, no manual retries, no tools, no GT/scorer reads;
- exact, provider-neutral visible-text fragment extraction;
- same normalized receipt structure for the existing C/K adapter;
- only non-sensitive block counts/kind added for future provenance;
- real SDK transport is NOT authorized by this module.

Do not import this into G4K or use on the existing create-only ledger.
A distinct scientific release, dataset namespace and code pin are required
before any live execution with this implementation.
"""
from __future__ import annotations

import time

from langchain_core.messages import AIMessage

from evaluation.rq2_ck_provider_transport import _usage
from evaluation.rq2_model_factory import crea_modello_rq2 as crea_modello
from evaluation.rq2_v2_ck_text_extraction_candidate import (
    CKTextExtractionBlocked,
    POLICY,
    extract_visible_ck_text,
)

VERSION = "rq2_v2_ck_provider_transport_candidate_v1"


def _empty_usage() -> dict:
    return {
        "complete": False,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "input_token_details": None,
        "output_token_details": None,
    }


def one_ck_call_candidate(provider: str, model_id: str, messages: list) -> dict:
    """One provider request at most; result not written to any ledger.

    This path is deliberately NOT called from the existing scientific
    dispatcher. All exception texts are suppressed to avoid leaking
    credential data from SDK errors. Never retry ambiguous calls.
    """
    started = time.monotonic()
    result = {
        "raw_response": None,
        "provider_error": None,
        "api_attempts": 0,
        "usage": _empty_usage(),
        "finish_reason": None,
        "provider_response_model": None,
        "content_extraction_policy": POLICY,
        "response_content_kind": "not_observed",
        "text_blocks_observed": 0,
        "nontext_blocks_observed": 0,
    }

    try:
        model = crea_modello(provider, model_id)
    except Exception as exc:
        result["provider_error"] = "SDK_CONSTRUCTION_ERROR:" + type(exc).__name__
    else:
        # An exception after this point may still correspond to a billable
        # remote request. Never infer zero cost or automatically retry.
        result["api_attempts"] = 1
        try:
            answer = model.invoke(messages)
        except Exception as exc:
            code = getattr(exc, "status_code", None)
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
                try:
                    visible = extract_visible_ck_text(answer.content)
                except CKTextExtractionBlocked:
                    result["provider_error"] = "PROTOCOL_ERROR:ContentBlockLimit"
                else:
                    result["raw_response"] = visible.raw_text
                    result["response_content_kind"] = visible.content_kind
                    result["text_blocks_observed"] = visible.text_blocks
                    result["nontext_blocks_observed"] = visible.other_blocks

                meta = answer.response_metadata or {}
                reason = meta.get("finish_reason", meta.get("stop_reason"))
                name = meta.get("model_name", meta.get("model"))
                result["finish_reason"] = (
                    reason if type(reason) is str else None
                )
                result["provider_response_model"] = (
                    name if type(name) is str and len(name) <= 160 else None
                )

    result["elapsed_seconds"] = round(time.monotonic() - started, 6)
    return result
