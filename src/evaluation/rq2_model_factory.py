"""Candidate RQ2-only model factory, with explicit pinned synchronous transport.

This is NOT the RQ1 model factory. No imports or provider construction at
module import time. It is intended ONLY behind the signed RQ2 discovery
release's existing claim/dispatch gates. No keys are stored here; no
model.invoke, tool call, async, streaming or automatic retry is performed.

WARNING: this candidate transport policy must be preregistered/frozen before
any real provider call. A 300s per-request timeout is NOT a stage timeout.
"""
from __future__ import annotations

import hashlib
import importlib.metadata as metadata
from pathlib import Path

from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_provider_policy_source_audit import (
    EXPECTED_COLAB_VERSIONS, KNOWN_SOURCE_PATHS,
)
from evaluation.rq2_sdk_retry_mock_probe import EXPECTED_SOURCE_DIGESTS

VERSION = "rq2_model_factory_candidate_v0"
TIMEOUT_SECONDS = 300.0
GOOGLE_HTTP_ATTEMPTS = 1
ANTHROPIC_MAX_RETRIES = 0
ANTHROPIC_MAX_TOKENS = 4096


class RQ2ModelPolicyBlocked(RuntimeError):
    """Unsupported model or runtime drift: DO NOT fall back to RQ1 defaults."""


def assert_exact_runtime_snapshot() -> None:
    """Fail closed on package/version or known-source SHA mismatch, without SDK import."""
    for package, expected in EXPECTED_COLAB_VERSIONS.items():
        try:
            actual = metadata.version(package)
        except metadata.PackageNotFoundError as exc:
            raise RQ2ModelPolicyBlocked("Missing pinned RQ2 package: " + package) from exc
        if actual != expected:
            raise RQ2ModelPolicyBlocked("RQ2 runtime package drift: " + package)
    for package, expected_sha in EXPECTED_SOURCE_DIGESTS.items():
        path = Path(metadata.distribution(package).locate_file(KNOWN_SOURCE_PATHS[package]))
        if path.is_symlink() or not path.is_file():
            raise RQ2ModelPolicyBlocked("Missing expected RQ2 source: " + package)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
            raise RQ2ModelPolicyBlocked("RQ2 provider source drift: " + package)


def crea_modello_rq2(provider: str, model_name: str):
    """Construct only an approved sync model with explicit no-retry/timeout.

    Precondition (at call site): signed scientific release validated and
    an immutable stage claim written. This function makes no API request.
    """
    if type(provider) is not str or type(model_name) is not str:
        raise RQ2ModelPolicyBlocked("Provider/model ID must be exact strings")
    permitted = {
        (entry["provider"], entry["model_id"])
        for entry in CANDIDATE_MODELS.values()
    }
    if (provider, model_name) not in permitted:
        raise RQ2ModelPolicyBlocked("Provider/model ID not preregistered for RQ2")
    assert_exact_runtime_snapshot()
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_name,
            max_retries=GOOGLE_HTTP_ATTEMPTS,
            timeout=TIMEOUT_SECONDS,
        )
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_name,
            max_retries=ANTHROPIC_MAX_RETRIES,
            max_tokens=ANTHROPIC_MAX_TOKENS,
            timeout=TIMEOUT_SECONDS,
        )
    raise RQ2ModelPolicyBlocked("Unexpected provider")
