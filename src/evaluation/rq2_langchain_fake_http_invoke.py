"""RQ2 prefreeze FINAL targeted offline invoke: real LangChain+SDK, fake HTTP 503.

Uses exact pinned Colab versions/source SHA and no original data. Creates
LangChain models with literal dummy keys, then replaces their *entire* HTTP
transport with in-memory httpx2/httpx MockTransport. An additional socket
deny-all prevents any real connection, including localhost. Runs both
tool-free C/K-style and tool-bound D-style synchronous .invoke, with 503
on each fake request. Records request counts, never credentials/headers.
No graph, telemetry, ground truth, real model inference or release.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.rq2_langchain_bridge_source_trace import (
    trace_exact_bridge_sources,
)
from evaluation.rq2_langchain_parameter_mock_probe import (
    TEST_TIMEOUT_SECONDS,
    SYNTHETIC_ANTHROPIC_KEY,
    SYNTHETIC_GOOGLE_KEY,
    RQ2BridgeMockBlocked,
    network_forbidden,
    validate_trace,
)

VERSION = "rq2_langchain_fake_http_invoke_v0"
TOOL_SCHEMA = {
    "name": "synthetic_metric_lookup",
    "description": "Offline test schema. This tool is never called.",
    "parameters": {
        "type": "object",
        "properties": {"metric": {"type": "string"}},
        "required": ["metric"],
    },
}


def _mocked_error_invoke(model, count: list[dict], *, bound: bool, provider: str) -> dict:
    """Require exactly one HTTP fake send, even when the fake server returns 503."""
    from langchain_core.messages import HumanMessage, SystemMessage

    before = len(count)
    candidate = model.bind_tools([TOOL_SCHEMA]) if bound else model
    try:
        candidate.invoke([
            SystemMessage(content="Only synthetic offline transport test."),
            HumanMessage(content="No real data. Trigger one dummy provider request."),
        ])
    except Exception as exc:
        # Never emit exception text: it may contain secrets/headers in other SDKs.
        typename = type(exc).__name__
        if typename in {"RQ2BridgeMockBlocked", "AssertionError"}:
            raise RQ2BridgeMockBlocked("Socket blocked or invariant failed") from None
    else:
        raise RQ2BridgeMockBlocked("Fake HTTP 503 was silently accepted")
    attempts = len(count) - before
    if attempts != 1:
        raise RQ2BridgeMockBlocked(
            provider + " fake HTTP attempts unexpected (must be one): " + str(attempts)
        )
    return {
        "style": "D_bound_tools" if bound else "CK_tool_free",
        "fake_http_503_sends": attempts,
        "synthetic_tool_executed": False,
        "external_network_calls": 0,
    }


def _fake_google() -> dict:
    import httpx
    import httpx2
    from langchain_google_genai import ChatGoogleGenerativeAI

    count: list[dict] = []

    model = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite",
        api_key=SYNTHETIC_GOOGLE_KEY,
        max_retries=1,
        timeout=TEST_TIMEOUT_SECONDS,
    )
    sdk = model.client._api_client
    original = sdk._httpx_client
    uses_httpx2 = isinstance(original, httpx2.Client)
    library = httpx2 if uses_httpx2 else httpx
    def mock_503(request):
        count.append({"method": request.method})
        return library.Response(
            503,
            json={"error": {"code": 503, "message": "SYNTHETIC_503", "status": "UNAVAILABLE"}},
            request=request,
        )
    mocked_client = library.Client(
        transport=library.MockTransport(mock_503), trust_env=False
    )
    sdk._httpx_client = mocked_client
    try:
        outcomes = [
            _mocked_error_invoke(model, count, bound=False, provider="google"),
            _mocked_error_invoke(model, count, bound=True, provider="google"),
        ]
    finally:
        sdk._httpx_client = original
        mocked_client.close()
        model.client.close()
    return {
        "backend": "httpx2" if uses_httpx2 else "httpx",
        "sync_invoke_modes": outcomes,
        "fake_total_http_503_sends": len(count),
        "configured_max_retries": 1,
        "configured_timeout_seconds": TEST_TIMEOUT_SECONDS,
        "external_provider_requests": 0,
    }


def _fake_anthropic() -> dict:
    import anthropic
    import httpx2
    from langchain_anthropic import ChatAnthropic

    count: list[dict] = []
    def mock_503(request: httpx2.Request) -> httpx2.Response:
        count.append({"method": request.method})
        return httpx2.Response(
            503, request=request,
            json={"type": "error",
                  "error": {"type": "api_error", "message": "SYNTHETIC_503"}},
        )

    fake_http = httpx2.Client(
        transport=httpx2.MockTransport(mock_503), trust_env=False
    )
    model = ChatAnthropic(
        model="claude-sonnet-5-5",
        api_key=SYNTHETIC_ANTHROPIC_KEY,
        max_retries=0,
        timeout=TEST_TIMEOUT_SECONDS,
        max_tokens=4096,
    )
    sdk = anthropic.Anthropic(
        api_key=SYNTHETIC_ANTHROPIC_KEY,
        base_url="https://no-network.invalid",
        max_retries=0,
        timeout=TEST_TIMEOUT_SECONDS,
        http_client=fake_http,
        open_telemetry=False,
    )
    # Exact pinned source uses @cached_property _client: replace it with
    # our SDK constructed with explicit MockTransport BEFORE any .invoke.
    if "_client" in model.__dict__:
        raise RQ2BridgeMockBlocked("LangChain Anthropic SDK client was pre-cached")
    model.__dict__["_client"] = sdk
    try:
        outcomes = [
            _mocked_error_invoke(model, count, bound=False, provider="anthropic"),
            _mocked_error_invoke(model, count, bound=True, provider="anthropic"),
        ]
    finally:
        sdk.close()
        fake_http.close()
    return {
        "backend": "httpx2.MockTransport",
        "sync_invoke_modes": outcomes,
        "fake_total_http_503_sends": len(count),
        "configured_max_retries": 0,
        "configured_timeout_seconds": TEST_TIMEOUT_SECONDS,
        "external_provider_requests": 0,
    }


def run_fake_http_invoke(*, repo_dir: Path) -> dict:
    snapshot = trace_exact_bridge_sources(repo_dir=Path(repo_dir))
    validate_trace(snapshot)
    # Local unit tests can mock _fake_*; every real SDK operation is inside deny-all.
    with network_forbidden():
        google = _fake_google()
        anthropic = _fake_anthropic()
    for name, provider in (("google", google), ("anthropic", anthropic)):
        if provider["fake_total_http_503_sends"] != 2:
            raise RQ2BridgeMockBlocked(name + " total fake send count mismatch")
    return {
        "version": VERSION,
        "status": "SYNC_FAKE_HTTP_503_INVOKE_VERIFIED_AS_TESTED_NOT_RELEASED",
        "google": google,
        "anthropic": anthropic,
        "api_requests_to_real_providers": 0,
        "credentials_real": False,
        "model_outputs_generated": 0,
        "real_tools_executed": 0,
        "read_market": False,
        "read_ground_truth": False,
        "read_predictions": False,
        "scientific_release_signed": False,
        "can_execute_D": False,
        "can_execute_CK": False,
        "can_execute_test": False,
        "timeout_under_real_network_stall_verified": False,
        "async_streaming_retry_verified": False,
        "next_gate": (
            "Finish RQ2-only policy, preregister alias scoring and conservative "
            "K formalizability, sign immutably pinned discovery release, "
            "then request explicit authorization for the first paid D stage."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run_fake_http_invoke(repo_dir=args.repo_dir),
                     sort_keys=True, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
