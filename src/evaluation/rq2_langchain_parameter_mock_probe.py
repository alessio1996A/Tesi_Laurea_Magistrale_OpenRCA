"""Offline RQ2 LangChain-to-SDK configuration forwarding probe.

The exact, already verified Colab distributions are required. No dataset,
ground truth, real key, provider invoke, model output, or socket connection.
Unlike the previous source trace, this constructs *local* LangChain objects
with explicitly synthetic credentials, guarded by a deny-all socket context,
then inspects the SDK request configuration BEFORE dispatch.

This does NOT certify HTTP retry/timeout behavior or unlock any RQ2 calls.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import socket
from pathlib import Path
from unittest.mock import patch

from evaluation.rq2_langchain_bridge_source_trace import (
    trace_exact_bridge_sources,
)

VERSION = "rq2_langchain_parameter_mock_probe_v0"
TEST_TIMEOUT_SECONDS = 300.0
GOOGLE_ATTEMPTS = 1
ANTHROPIC_RETRIES = 0
SYNTHETIC_GOOGLE_KEY = "synthetic-google-never-authorized"
SYNTHETIC_ANTHROPIC_KEY = "sk-ant-synthetic-never-authorized"


class RQ2BridgeMockBlocked(RuntimeError):
    """Snapshot drift, network attempt or unexpected forwarded configuration."""


def validate_trace(trace: dict) -> None:
    """Require exact pinned source and closed release before any SDK imports."""
    if not isinstance(trace, dict) or trace.get("status") != (
        "EXACT_SOURCE_BRIDGE_INSPECTED_FOR_REVIEW_NOT_SDK_HTTP_CERTIFIED"
    ):
        raise RQ2BridgeMockBlocked("Pinned bridge source trace absent")
    for key in (
        "colab_package_versions_match", "rq1_factory_unchanged",
        "rq2_release_sha_unpinned",
    ):
        if trace.get(key) is not True:
            raise RQ2BridgeMockBlocked("Bridge source prerequisite changed: " + key)
    for key in (
        "scientific_discovery_release_signed", "can_execute_D",
        "can_execute_CK", "can_execute_test",
    ):
        if trace.get(key) is not False:
            raise RQ2BridgeMockBlocked("Production gate unexpectedly open: " + key)
    if trace.get("provider_api_calls") != 0:
        raise RQ2BridgeMockBlocked("Source trace reports API requests")


@contextlib.contextmanager
def network_forbidden():
    """Socket-level deny-all, including localhost; only synthetic objects allowed."""
    def forbid(*_args, **_kwargs):
        raise RQ2BridgeMockBlocked("Network access forbidden during offline probe")
    with patch.object(socket.socket, "connect", forbid), patch.object(
        socket.socket, "connect_ex", forbid
    ), patch.object(socket, "create_connection", forbid):
        yield


def probe_google_langchain_parameters() -> dict:
    """Build one fake-key client and inspect the generated SDK request config."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage

    model = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite",
        api_key=SYNTHETIC_GOOGLE_KEY,
        max_retries=GOOGLE_ATTEMPTS,
        timeout=TEST_TIMEOUT_SECONDS,
    )
    try:
        request = model._prepare_request(
            [HumanMessage(content="OFFLINE PARAMETER AUDIT ONLY")]
        )
        if not isinstance(request, dict):
            raise RQ2BridgeMockBlocked("Google request must be a dict")
        config = request.get("config")
        http_options = getattr(config, "http_options", None)
        retries = getattr(http_options, "retry_options", None)
        attempts = getattr(retries, "attempts", None)
        timeout_ms = getattr(http_options, "timeout", None)
        if attempts != GOOGLE_ATTEMPTS:
            raise RQ2BridgeMockBlocked("Google SDK request retry option not forwarded")
        if timeout_ms != int(TEST_TIMEOUT_SECONDS * 1000):
            raise RQ2BridgeMockBlocked("Google SDK request timeout not forwarded")
        return {
            "langchain_model_id": model.model,
            "configured_max_retries": model.max_retries,
            "sdk_http_retry_attempts": attempts,
            "configured_timeout_seconds": TEST_TIMEOUT_SECONDS,
            "sdk_http_timeout_milliseconds": timeout_ms,
            "generate_content_invoked": False,
            "client_network_calls": 0,
        }
    finally:
        client = getattr(model, "client", None)
        if client is not None:
            client.close()


def _sdk_timeout_seconds(value: object) -> float | None:
    """Anthropic/httpx2 timeout may be a float or a timeout structure."""
    if type(value) in (int, float):
        return float(value)
    read = getattr(value, "read", None)
    return float(read) if type(read) in (int, float) else None


def probe_anthropic_langchain_parameters() -> dict:
    """Inspect LangChain client kwargs and SDK object without calling messages."""
    from langchain_anthropic import ChatAnthropic

    model = ChatAnthropic(
        model="claude-sonnet-5-5",
        api_key=SYNTHETIC_ANTHROPIC_KEY,
        max_retries=ANTHROPIC_RETRIES,
        timeout=TEST_TIMEOUT_SECONDS,
        max_tokens=4096,
    )
    params = model._client_params
    # Never include client_params in output: that object contains the fake key.
    if params.get("max_retries") != ANTHROPIC_RETRIES:
        raise RQ2BridgeMockBlocked("Anthropic max_retries not forwarded")
    if params.get("timeout") != TEST_TIMEOUT_SECONDS:
        raise RQ2BridgeMockBlocked("Anthropic timeout not forwarded")
    sdk_client = model._client  # local construction ONLY
    try:
        sdk_retries = getattr(sdk_client, "max_retries", None)
        sdk_timeout = _sdk_timeout_seconds(getattr(sdk_client, "timeout", None))
        if sdk_retries != ANTHROPIC_RETRIES:
            raise RQ2BridgeMockBlocked("Anthropic SDK retry parameter mismatch")
        if sdk_timeout != TEST_TIMEOUT_SECONDS:
            raise RQ2BridgeMockBlocked("Anthropic SDK timeout parameter mismatch")
        return {
            "configured_max_retries": model.max_retries,
            "sdk_max_retries": sdk_retries,
            "configured_timeout_seconds": TEST_TIMEOUT_SECONDS,
            "sdk_timeout_seconds": sdk_timeout,
            "messages_create_invoked": False,
            "client_network_calls": 0,
        }
    finally:
        sdk_client.close()


def run_mock_parameter_probe(*, repo_dir: Path) -> dict:
    trace = trace_exact_bridge_sources(repo_dir=Path(repo_dir))
    validate_trace(trace)
    # The deny-all is installed BEFORE importing the provider LangChain wrappers.
    with network_forbidden():
        google = probe_google_langchain_parameters()
        anthropic = probe_anthropic_langchain_parameters()
    return {
        "version": VERSION,
        "status": "LANGCHAIN_LOCAL_FORWARDING_CHECKED_NETWORK_HTTP_NOT_CERTIFIED",
        "google": google,
        "anthropic": anthropic,
        "external_provider_requests": 0,
        "real_credentials_used": False,
        "sdk_http_transport_exercised": False,
        "read_market": False,
        "read_ground_truth": False,
        "read_predictions": False,
        "files_written": False,
        "scientific_release_signed": False,
        "can_execute_D": False,
        "can_execute_CK": False,
        "can_execute_test": False,
        "next_gate": (
            "Choose and document RQ2-only retry/timeout policy, verify a "
            "fake-HTTP model.invoke for C and D with source-bound tools, "
            "and complete independent scientific preregistration gates."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(
        run_mock_parameter_probe(repo_dir=args.repo_dir),
        ensure_ascii=False, indent=2, sort_keys=True,
    ))


if __name__ == "__main__":
    main()
