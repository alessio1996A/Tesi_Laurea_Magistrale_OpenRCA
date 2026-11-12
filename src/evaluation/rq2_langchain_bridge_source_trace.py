"""RQ2 pre-freeze: inspect exact installed LangChain/SDK bridge SOURCE only.

Read only source files whose SHA-256 was supplied by Colab. This *never*
imports a model integration, builds a client, uses credentials, reads Market,
or makes a provider request. Evidence for human code review, not a network
retry/timeout certification. RQ1 and all release gates remain unchanged.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

from evaluation.rq2_provider_policy_source_audit import (
    EXPECTED_COLAB_VERSIONS, KNOWN_SOURCE_PATHS,
    _package_evidence, preview_provider_policy,
)
from evaluation.rq2_sdk_retry_mock_probe import (
    EXPECTED_SOURCE_DIGESTS, validate_sdk_snapshot,
)

VERSION = "rq2_langchain_bridge_source_trace_v0"
TRACE_TERMS = {
    "langchain-google-genai": (
        "max_retries", "retry_options", "http_options",
        "timeout", "def _generate(", "def _agenerate(",
        "def _stream(", "def _astream(", "generate_content(",
        "generate_content_stream(", "Client(",
    ),
    "langchain-anthropic": (
        "max_retries", "default_request_timeout", "timeout",
        "def _client(", "def _async_client(",
        "messages.with_raw_response.create(", "def _generate(",
        "def _agenerate(", "def _stream(", "def _astream(",
    ),
    "google-genai": (
        "def retry_args(", "def _request(", "def _async_request(",
        "retry_options", "implicit_retry", "timeout",
        "self._retry(", "self._async_retry(",
    ),
    "anthropic": (
        "def _should_retry(", "def _attempt_request(",
        "def _request(", "max_retries", "timeout",
        "retries_taken", "DEFAULT_TIMEOUT",
    ),
}


class RQ2BridgeTraceBlocked(ValueError):
    """Exact SDK source/version or production source gate has changed."""


def _lines_for_review(source: str, terms: tuple[str, ...]) -> dict:
    """Small, stable per-term code excerpts with line numbers, not full sources."""
    lines = source.splitlines()
    selected = set()
    term_counts = {}
    for term in terms:
        indices = [
            idx for idx, line in enumerate(lines)
            if term in line and not line.lstrip().startswith("#")
        ]
        term_counts[term] = len(indices)
        # First and last matches surface both config and invocation paths.
        if indices:
            chosen = indices[:3] + indices[-2:]
            selected.update(chosen)
    excerpts = [
        {"line": idx + 1, "text": lines[idx].strip()[:200]}
        for idx in sorted(selected)
    ]
    return {
        "term_match_counts": term_counts,
        "matched_lines": excerpts[:90],
        "matched_lines_truncated": len(excerpts) > 90,
    }


def trace_exact_bridge_sources(*, repo_dir: Path) -> dict:
    """Strict Colab snapshot, text-only package auditing, fail closed."""
    repo_dir = Path(repo_dir)
    preflight = preview_provider_policy(repo_dir=repo_dir)
    validate_sdk_snapshot(preflight)
    release = repo_dir / "src/evaluation/rq2_ck_provider_transport.py"
    plan = repo_dir / "src/evaluation/rq2_dryrun_plan.py"
    if (
        release.is_symlink() or plan.is_symlink()
        or not release.is_file() or not plan.is_file()
        or "RELEASE_SHA256 = None" not in release.read_text(encoding="utf-8")
        or 'PLAN_STATUS = "DRAFT_NOT_EXECUTABLE"' not in plan.read_text(encoding="utf-8")
    ):
        raise RQ2BridgeTraceBlocked("Production or OOD gate no longer locked")

    sources = {}
    for package, expected_sha in EXPECTED_SOURCE_DIGESTS.items():
        relative = KNOWN_SOURCE_PATHS[package]
        # _package_evidence uses importlib.metadata only; no SDK import.
        dist = __import__("importlib.metadata", fromlist=["distribution"]).distribution(package)
        file = Path(dist.locate_file(relative))
        if file.is_symlink() or not file.is_file() or file.stat().st_size > 4_000_000:
            raise RQ2BridgeTraceBlocked("Source missing/too large/symlink: " + package)
        source_bytes = file.read_bytes()
        sha = hashlib.sha256(source_bytes).hexdigest()
        if sha != expected_sha:
            raise RQ2BridgeTraceBlocked("Source SHA changed: " + package)
        try:
            source_text = source_bytes.decode("utf-8")
            ast.parse(source_text)
        except (UnicodeDecodeError, SyntaxError) as exc:
            raise RQ2BridgeTraceBlocked("Unparseable installed source: " + package) from exc
        sources[package] = {
            "source_file": relative,
            "sha256": sha,
            "python_ast_parse_ok": True,
            **_lines_for_review(source_text, TRACE_TERMS[package]),
        }
    return {
        "version": VERSION,
        "status": "EXACT_SOURCE_BRIDGE_INSPECTED_FOR_REVIEW_NOT_SDK_HTTP_CERTIFIED",
        "colab_package_versions_match": True,
        "rq1_factory_unchanged": True,
        "rq2_release_sha_unpinned": True,
        "scientific_discovery_release_signed": False,
        "source_trace": sources,
        "google_langchain_retry_forwarding_verified": False,
        "anthropic_langchain_retry_forwarding_verified": False,
        "google_async_streaming_no_hidden_retry_verified": False,
        "request_timeout_enforcement_verified": False,
        "provider_api_calls": 0,
        "read_ground_truth": False,
        "read_market": False,
        "read_predictions": False,
        "files_written": False,
        "can_execute_D": False,
        "can_execute_CK": False,
        "can_execute_test": False,
        "next_gate": "Human review of exact installed bridging code, then narrowly scoped no-network integration tests and RQ2-only timeout/retry enforcement; do not alter frozen RQ1.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(
        trace_exact_bridge_sources(repo_dir=args.repo_dir),
        ensure_ascii=False, indent=2, sort_keys=True,
    ))


if __name__ == "__main__":
    main()
