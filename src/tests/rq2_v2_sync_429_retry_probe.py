"""RQ2-V2: solo nuovo caso HTTP 429 su .invoke sincrono, con HTTP finto.

Riutilizza semantiche già provate del probe 503, senza richiamare legacy
source guard V1 (il suo RELEASE_SHA256 storico non deve essere alterato).
Nessuna credenziale reale, socket, GT, Market, claim, release o API.
Non certifica status ulteriori, streaming/async o hard cap HTTP/USD.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rq2_v2_sync_timeout_loopback_probe import verify_checkout

VERSION = "rq2_v2_sync_429_retry_probe_v0"
FAKE_STATUS = 429


class Sync429ProbeBlocked(RuntimeError):
    """Policy retry RQ2 non dimostrata per HTTP 429."""


def _single_429_invoke(model, count: list, *, bound: bool, provider: str) -> dict:
    from langchain_core.messages import HumanMessage, SystemMessage
    from evaluation.rq2_langchain_fake_http_invoke import TOOL_SCHEMA

    before = len(count)
    candidate = model.bind_tools([TOOL_SCHEMA]) if bound else model
    try:
        candidate.invoke([
            SystemMessage(content="Synthetic 429 retry policy only."),
            HumanMessage(content="Synthetic request; no dataset or model output."),
        ])
    except Exception:
        pass  # error message must never be printed or treated as evidence
    else:
        raise Sync429ProbeBlocked(provider + " fake 429 unexpectedly accepted")
    sends = len(count) - before
    if sends != 1:
        raise Sync429ProbeBlocked(provider + " implicit retry or no HTTP: " + str(sends))
    return {
        "mode": "D_bound_tools" if bound else "CK_tool_free",
        "synthetic_429_http_sends": sends,
        "http_error_observed": True,
    }


def _fake_google() -> list[dict]:
    import httpx
    import httpx2
    from langchain_google_genai import ChatGoogleGenerativeAI
    from evaluation.rq2_langchain_parameter_mock_probe import SYNTHETIC_GOOGLE_KEY

    seen: list[dict] = []
    model = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite",
        api_key=SYNTHETIC_GOOGLE_KEY,
        max_retries=1, timeout=300.0,
    )
    sdk = model.client._api_client
    original = sdk._httpx_client
    lib = httpx2 if isinstance(original, httpx2.Client) else httpx

    def handler(request):
        seen.append({"method": request.method})
        return lib.Response(
            FAKE_STATUS,
            json={"error": {"code": 429, "message": "SYNTHETIC_429",
                            "status": "RESOURCE_EXHAUSTED"}},
            request=request,
        )

    fake = lib.Client(transport=lib.MockTransport(handler), trust_env=False)
    sdk._httpx_client = fake
    try:
        return [
            _single_429_invoke(model, seen, bound=False, provider="google"),
            _single_429_invoke(model, seen, bound=True, provider="google"),
        ]
    finally:
        sdk._httpx_client = original
        fake.close()
        model.client.close()


def _fake_anthropic() -> list[dict]:
    import anthropic
    import httpx2
    from langchain_anthropic import ChatAnthropic
    from evaluation.rq2_langchain_parameter_mock_probe import SYNTHETIC_ANTHROPIC_KEY

    seen: list[dict] = []
    def handler(request):
        seen.append({"method": request.method})
        return httpx2.Response(
            FAKE_STATUS,
            json={"type": "error",
                  "error": {"type": "rate_limit_error", "message": "SYNTHETIC_429"}},
            request=request,
        )

    fake_http = httpx2.Client(
        transport=httpx2.MockTransport(handler), trust_env=False,
    )
    model = ChatAnthropic(
        model="claude-sonnet-5-5",
        api_key=SYNTHETIC_ANTHROPIC_KEY,
        max_retries=0, max_tokens=4096, timeout=300.0,
    )
    sdk = anthropic.Anthropic(
        api_key=SYNTHETIC_ANTHROPIC_KEY,
        base_url="https://no-network.invalid",
        max_retries=0, timeout=300.0,
        http_client=fake_http, open_telemetry=False,
    )
    if "_client" in model.__dict__:
        raise Sync429ProbeBlocked("Anthropic SDK cached before fake injection")
    model.__dict__["_client"] = sdk
    try:
        return [
            _single_429_invoke(model, seen, bound=False, provider="anthropic"),
            _single_429_invoke(model, seen, bound=True, provider="anthropic"),
        ]
    finally:
        sdk.close()
        fake_http.close()


def run_probe(*, repo_dir: Path, expected_commit: str) -> dict:
    verify_checkout(repo_dir, expected_commit)

    from evaluation.rq2_model_factory import (
        assert_exact_runtime_snapshot, TIMEOUT_SECONDS, GOOGLE_HTTP_ATTEMPTS,
        ANTHROPIC_MAX_RETRIES,
    )
    from evaluation.rq2_v2_unified_live_dispatcher import LIVE_API_ENABLED
    from evaluation.rq2_langchain_parameter_mock_probe import network_forbidden

    if (LIVE_API_ENABLED is not False or TIMEOUT_SECONDS != 300.0
            or GOOGLE_HTTP_ATTEMPTS != 1 or ANTHROPIC_MAX_RETRIES != 0):
        raise Sync429ProbeBlocked("RQ2-only policy drift")
    assert_exact_runtime_snapshot()
    with network_forbidden():
        google = _fake_google()
        anthropic = _fake_anthropic()
    results = {"google": google, "anthropic": anthropic}
    if any(
        [x["mode"] for x in value] != ["CK_tool_free", "D_bound_tools"]
        or [x["synthetic_429_http_sends"] for x in value] != [1, 1]
        for value in results.values()
    ):
        raise Sync429ProbeBlocked("Unexpected provider mode or retry")
    return {
        "version": VERSION,
        "status": "SYNC_HTTP_429_MOCK_ONE_SEND_EACH_NO_API_NOT_RELEASED",
        "source_commit": expected_commit,
        "providers": results,
        "synthetic_429_http_sends_total": 4,
        "external_provider_requests": 0,
        "real_credentials_used": False,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "scientific_release_frozen": False,
        "async_streaming_tested": False,
        "max_http_attempts_guaranteed": None,
        "usd_hard_cap_guaranteed": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-dir", required=True, type=Path)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    print(json.dumps(
        run_probe(repo_dir=args.repo_dir, expected_commit=args.expected_commit),
        indent=2, sort_keys=True,
    ))


if __name__ == "__main__":
    main()
