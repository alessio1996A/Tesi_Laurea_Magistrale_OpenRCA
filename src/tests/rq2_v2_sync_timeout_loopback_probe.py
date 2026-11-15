"""RQ2-V2: prova mirata del read timeout sul percorso sync LangChain -> SDK.

Solo su runtime Colab PINNATO e repository clean; non e' un componente live.
HTTP reale ESCLUSIVAMENTE verso un server fittizio 127.0.0.1 locale.
Ogni richiesta SDK e' intercettata e reindirizzata al server di stallo;
DNS e connessioni esterne vietati. Credenziali letterali false.
Non verifica async/stream, quote, hard cap o idempotenza remota.
Non firma la release e NON attiva API RQ2-V2.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import re
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

VERSION = "rq2_v2_sync_timeout_loopback_probe_v0"
STALL_SECONDS = 2.0
TIMEOUT_SECONDS = 0.3
MAX_ELAPSED_SECONDS = 1.5
SHA1 = re.compile(r"[0-9a-f]{40}\Z")


class SyncTimeoutProbeBlocked(RuntimeError):
    """Runtime, network e comportamento sync non verificati: STOP."""


def verify_checkout(repo: Path, expected_commit: str) -> None:
    if not SHA1.fullmatch(expected_commit):
        raise SyncTimeoutProbeBlocked("External source commit pin required")
    if not repo.is_absolute() or not (repo / ".git").exists():
        raise SyncTimeoutProbeBlocked("Absolute Git checkout required")
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True, timeout=10,
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=repo, text=True, timeout=10,
        ).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise SyncTimeoutProbeBlocked("Git provenance unavailable") from exc
    if head != expected_commit or dirty:
        raise SyncTimeoutProbeBlocked("Unclean or unpinned source: STOP")


@contextmanager
def only_local_server(port: int):
    """Deny external DNS/connect, allowing solely this exact loopback port."""
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_getaddrinfo = socket.getaddrinfo

    def allowed(address):
        return (isinstance(address, tuple) and len(address) >= 2
                and address[0] in ("127.0.0.1", b"127.0.0.1")
                and address[1] == port)

    def connect(sock, address):
        if not allowed(address):
            raise SyncTimeoutProbeBlocked("Non-loopback network blocked")
        return original_connect(sock, address)

    def connect_ex(sock, address):
        if not allowed(address):
            raise SyncTimeoutProbeBlocked("Non-loopback connect_ex blocked")
        return original_connect_ex(sock, address)

    def getaddrinfo(host, service, *args, **kwargs):
        if host not in ("127.0.0.1", b"127.0.0.1") or service != port:
            raise SyncTimeoutProbeBlocked("External DNS blocked")
        return original_getaddrinfo(host, service, *args, **kwargs)

    with (
        patch.object(socket.socket, "connect", connect),
        patch.object(socket.socket, "connect_ex", connect_ex),
        patch.object(socket, "getaddrinfo", getaddrinfo),
    ):
        yield


class _StallHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        with self.server.counter_lock:
            self.server.request_count += 1
        time.sleep(STALL_SECONDS)
        try:
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b"synthetic-stall-only")
        except (OSError, BrokenPipeError):
            pass

    def log_message(self, *_args):
        pass


@contextmanager
def stalled_local_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StallHandler)
    server.daemon_threads = True
    server.request_count = 0
    server.counter_lock = threading.Lock()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def _redirect_transport(http_lib, port):
    """Intercept ALL SDK HTTP in memory; only the inner loopback transport sends."""
    class _LoopbackTransport(http_lib.BaseTransport):
        def __init__(self):
            self.inner = http_lib.HTTPTransport(retries=0, trust_env=False)

        def handle_request(self, request):
            if request.url.scheme != "https":
                raise SyncTimeoutProbeBlocked("Unexpected SDK request scheme")
            request.url = request.url.copy_with(
                scheme="http", host="127.0.0.1", port=port,
            )
            return self.inner.handle_request(request)

        def close(self):
            self.inner.close()

    return _LoopbackTransport()


def _contains_timeout(error):
    seen = set()
    current = error
    for _ in range(12):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        if "timeout" in type(current).__name__.lower():
            return True
        current = current.__cause__ or current.__context__
    return False


def _one_stall(model, *, bound, server, provider):
    from langchain_core.messages import HumanMessage, SystemMessage
    from evaluation.rq2_langchain_fake_http_invoke import TOOL_SCHEMA

    before = server.request_count
    candidate = model.bind_tools([TOOL_SCHEMA]) if bound else model
    start = time.monotonic()
    error = None
    try:
        candidate.invoke([
            SystemMessage(content="Synthetic loopback timeout test."),
            HumanMessage(content="No real data or model inference."),
        ])
    except Exception as exc:
        error = exc
    elapsed = time.monotonic() - start
    sends = server.request_count - before
    if error is None or not _contains_timeout(error):
        raise SyncTimeoutProbeBlocked(provider + " timeout not observed")
    if sends != 1:
        raise SyncTimeoutProbeBlocked(provider + " unexpected HTTP send count")
    if elapsed >= MAX_ELAPSED_SECONDS:
        raise SyncTimeoutProbeBlocked(provider + " read timeout not promptly enforced")
    return {
        "mode": "D_bound_tools" if bound else "CK_tool_free",
        "loopback_http_sends": sends,
        "timeout_exception_observed": True,
        "elapsed_seconds": round(elapsed, 4),
    }


def _google(server):
    import httpx
    import httpx2
    from langchain_google_genai import ChatGoogleGenerativeAI
    from evaluation.rq2_langchain_parameter_mock_probe import SYNTHETIC_GOOGLE_KEY

    model = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite", api_key=SYNTHETIC_GOOGLE_KEY,
        max_retries=1, timeout=TIMEOUT_SECONDS,
    )
    sdk = model.client._api_client
    original = sdk._httpx_client
    lib = httpx2 if isinstance(original, httpx2.Client) else httpx
    replacement = lib.Client(
        transport=_redirect_transport(lib, server.server_port), trust_env=False,
    )
    sdk._httpx_client = replacement
    try:
        results = [
            _one_stall(model, bound=False, server=server, provider="google"),
            _one_stall(model, bound=True, server=server, provider="google"),
        ]
    finally:
        sdk._httpx_client = original
        replacement.close()
        model.client.close()
    return results


def _anthropic(server):
    import anthropic
    import httpx2
    from langchain_anthropic import ChatAnthropic
    from evaluation.rq2_langchain_parameter_mock_probe import SYNTHETIC_ANTHROPIC_KEY

    fake_http = httpx2.Client(
        transport=_redirect_transport(httpx2, server.server_port),
        trust_env=False,
    )
    model = ChatAnthropic(
        model="claude-sonnet-5-5", api_key=SYNTHETIC_ANTHROPIC_KEY,
        max_retries=0, max_tokens=4096, timeout=TIMEOUT_SECONDS,
    )
    sdk = anthropic.Anthropic(
        api_key=SYNTHETIC_ANTHROPIC_KEY,
        base_url="https://no-network.invalid",
        max_retries=0, timeout=TIMEOUT_SECONDS,
        http_client=fake_http, open_telemetry=False,
    )
    if "_client" in model.__dict__:
        raise SyncTimeoutProbeBlocked("Anthropic SDK client precached")
    model.__dict__["_client"] = sdk
    try:
        results = [
            _one_stall(model, bound=False, server=server, provider="anthropic"),
            _one_stall(model, bound=True, server=server, provider="anthropic"),
        ]
    finally:
        sdk.close()
        fake_http.close()
    return results


def run_probe(*, repo: Path, expected_commit: str) -> dict:
    verify_checkout(repo, expected_commit)
    from evaluation.rq2_model_factory import (
        assert_exact_runtime_snapshot, TIMEOUT_SECONDS as LIVE_TIMEOUT,
        GOOGLE_HTTP_ATTEMPTS, ANTHROPIC_MAX_RETRIES,
    )
    from evaluation.rq2_v2_unified_live_dispatcher import LIVE_API_ENABLED
    if (LIVE_API_ENABLED is not False or LIVE_TIMEOUT != 300.0
            or GOOGLE_HTTP_ATTEMPTS != 1 or ANTHROPIC_MAX_RETRIES != 0):
        raise SyncTimeoutProbeBlocked("RQ2 factory/dispatcher policy drift")
    assert_exact_runtime_snapshot()
    with stalled_local_server() as server:
        with only_local_server(server.server_port):
            google = _google(server)
            anthropic = _anthropic(server)
        if server.request_count != 4:
            raise SyncTimeoutProbeBlocked("Unexpected total loopback sends")
    return {
        "status": "SYNC_LOCAL_STALL_TIMEOUT_CHECKED_NO_API_NO_RELEASE",
        "version": VERSION,
        "source_commit": expected_commit,
        "google": google,
        "anthropic": anthropic,
        "loopback_sends_total": 4,
        "external_api_requests": 0,
        "actual_model_calls": 0,
        "real_credentials_used": False,
        "ground_truth_read": False,
        "scientific_release_frozen": False,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "async_streaming_tested": False,
        "full_stage_timeout_guaranteed": False,
        "usd_hard_cap_guaranteed": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-dir", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    result = run_probe(repo=args.repo_dir, expected_commit=args.expected_commit)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
