"""V3 D runner instrumentation candidate, OFFLINE ONLY; no paid dispatch.

Instrument the existing GT-free run_experiment without modifying the frozen
RQ1/V2 graph engines or output validator. The original runner imports the
two D executor functions dynamically. Inside an explicitly scoped,
single-threaded context we redirect ONLY those executor calls to the exact
final-text V3 stream bridge.

This module DOES NOT execute run_experiment itself, load benchmark files,
construct models, write an artifact or authorize a scientific release.
The future versioned dispatcher must separately enforce GT-free source,
new V3 IDs, release/source pins, create-only ledger and per-stage approval.
"""
from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import patch

import agent.graph_engine as react
import agent.verify_graph as verify
from evaluation.rq2_v3_d_final_stream_candidate import (
    D_META_SCHEMA,
    run_d_final_candidate,
)

VERSION = "rq2_v3_d_runner_capture_candidate_v0"
PLANNING_VARIANTS = frozenset(("A1_8R_Planning", "A1_PAVE"))
REACT_VARIANTS = frozenset(("A0", "A1", "A1_8R"))


class DRunnerCaptureBlocked(RuntimeError):
    """Prevent ambiguous/mismatched D graph execution."""


class V3DRunnerCapture:
    """Single-use context for testing an unmodified experiment runner.

    Caller must use a synthetic LLM/graph and patched data loader in offline
    tests. Never use this audit candidate to run paid provider calls.
    """

    def __init__(self, *, harness: str):
        if harness in REACT_VARIANTS:
            self.expected_engine = "react"
        elif harness in PLANNING_VARIANTS:
            self.expected_engine = "verify"
        else:
            raise DRunnerCaptureBlocked("Unknown D harness")
        self.harness = harness
        self._active = False
        self._entered = False
        self._stack = None
        self._calls = 0
        self._d_run = None
        self._meta = None

    def _execute(self, *, engine: str, grafo, richiesta,
                 recursion_limit=30, verbose=False):
        if not self._active or engine != self.expected_engine:
            raise DRunnerCaptureBlocked("Wrong/unsafely dispatched D engine")
        if self._calls:
            raise DRunnerCaptureBlocked("Repeated D execution forbidden")
        self._calls += 1
        result = run_d_final_candidate(
            grafo, richiesta, engine=engine,
            recursion_limit=recursion_limit, verbose=verbose,
        )
        self._d_run = result["diagnostic_run"]
        self._meta = result["d_final_text_extraction"]
        if self._meta.get("schema") != D_META_SCHEMA:
            raise DRunnerCaptureBlocked("Wrong D extraction metadata")
        return self._d_run

    def _react(self, grafo, richiesta, recursion_limit=30, verbose=False):
        return self._execute(
            engine="react", grafo=grafo, richiesta=richiesta,
            recursion_limit=recursion_limit, verbose=verbose,
        )

    def _verify(self, grafo, richiesta, recursion_limit=30, verbose=False):
        return self._execute(
            engine="verify", grafo=grafo, richiesta=richiesta,
            recursion_limit=recursion_limit, verbose=verbose,
        )

    def __enter__(self):
        if self._entered:
            raise DRunnerCaptureBlocked("D capture is single-use")
        self._entered = True
        self._stack = ExitStack()
        try:
            self._stack.enter_context(
                patch.object(react, "esegui_grafo_rca", self._react)
            )
            self._stack.enter_context(
                patch.object(verify, "esegui_grafo_rca_verify", self._verify)
            )
        except Exception:
            self._stack.close()
            raise
        self._active = True
        return self

    def __exit__(self, exc_type, exc, tb):
        self._active = False
        self._stack.close()
        return False

    def build_receipt(self, result: dict) -> dict:
        """Return original runner output plus *separate* D provenance.

        Does not label scientific RECORDED_COMPLETE or save anything. V3
        success is only decided by a future versioned scientific adapter.
        """
        if self._active:
            raise DRunnerCaptureBlocked("Runner context still active")
        if self._calls != 1 or type(self._d_run) is not dict:
            raise DRunnerCaptureBlocked("Exactly one D graph run required")
        if type(result) is not dict or result.get("raw_response") != self._d_run.get(
            "raw_response"
        ):
            raise DRunnerCaptureBlocked("Runner final text changed")
        if result.get("variant") != self.harness:
            raise DRunnerCaptureBlocked("Runner harness identity drift")
        if type(self._meta) is not dict:
            raise DRunnerCaptureBlocked("Missing extraction metadata")
        return {
            "version": VERSION,
            "diagnostic_run": result,
            "d_final_text_extraction": dict(self._meta),
            "can_execute_api": False,
            "scientific_release_frozen": False,
            "can_write_scientific_records": False,
        }
