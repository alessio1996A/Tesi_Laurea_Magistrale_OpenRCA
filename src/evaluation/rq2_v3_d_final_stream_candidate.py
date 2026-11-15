"""RQ2 V3 candidate: exact visible-text extraction for FINAL D responses.

OFFLINE DESIGN ONLY, no source-bound V3 release, ledger or live dispatcher.

A small graph-stream view normalizes ONLY the final visible AIMessage before
the frozen ReAct/verify D runners read it. It never modifies the original
AIMessage, the graph, tool results, prompts, provider calls, or D budgets.
It does not repair malformed JSON. No global monkeypatch of graph_engine.

The exact same extraction function/policy is used by the candidate C/K
transport; all models and harnesses follow the same text-block rules.
Do not call real providers or record this under the frozen V2 release.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage

from agent.rq2_v2_graph_engine import esegui_grafo_rca_v2
from agent.verify_graph import esegui_grafo_rca_verify
from evaluation.rq2_v2_ck_text_extraction_candidate import (
    POLICY,
    extract_visible_ck_text,
)

VERSION = "rq2_v3_d_final_stream_candidate_v0"
D_META_SCHEMA = "rq2_v3_d_final_text_meta_v0"
ENGINES = ("react", "verify")


class DFinalStreamCandidateBlocked(RuntimeError):
    """Final-output stream shape is too ambiguous; never guess."""


class ExactFinalTextStream:
    """Single-use view of an existing, already-compiled graph.

    The graph's own state is never edited. A shallow event/message copy
    carries the exact visible final text to the original graph runner.
    """

    def __init__(self, graph: object, *, engine: str):
        if engine not in ENGINES:
            raise DFinalStreamCandidateBlocked("Unknown D engine")
        self.graph = graph
        self.engine = engine
        self._used = False
        self._final_count = 0
        self.final_meta = {
            "schema": D_META_SCHEMA,
            "policy": POLICY,
            "content_kind": "not_observed",
            "text_blocks": 0,
            "nontext_blocks": 0,
        }

    def stream(self, initial_state, *, config, stream_mode):
        if self._used:
            raise DFinalStreamCandidateBlocked(
                "Graph stream view cannot be reused for a second execution"
            )
        self._used = True
        # No graph.invoke, no SDK factory, no extra tool/provider requests.
        for event in self.graph.stream(
            initial_state, config=config, stream_mode=stream_mode
        ):
            if type(event) is not dict:
                raise DFinalStreamCandidateBlocked("Unexpected graph event")
            changed = None
            for node, update in event.items():
                candidate_node = (
                    node == "agente" if self.engine == "react"
                    else node == "finale"
                )
                if not candidate_node or type(update) is not dict:
                    continue
                if update.get("finalization_error"):
                    # Keep the original error; do not invent a diagnosis.
                    continue
                messages = update.get("messages")
                if type(messages) is not list:
                    raise DFinalStreamCandidateBlocked(
                        "Final event without explicit message list"
                    )
                new_messages = list(messages)
                mutated = False
                for i, msg in enumerate(messages):
                    if not isinstance(msg, AIMessage):
                        # Never reinterpret non-AI messages as model output.
                        continue
                    if getattr(msg, "tool_calls", None):
                        # ReAct exploration, NOT a final answer.
                        continue
                    if getattr(msg, "invalid_tool_calls", None):
                        raise DFinalStreamCandidateBlocked(
                            "Unparsed tool calls in apparent final message"
                        )
                    self._final_count += 1
                    if self._final_count > 1:
                        raise DFinalStreamCandidateBlocked(
                            "Multiple final model messages are ambiguous"
                        )
                    visible = extract_visible_ck_text(msg.content)
                    self.final_meta = {
                        "schema": D_META_SCHEMA,
                        "policy": POLICY,
                        "content_kind": visible.content_kind,
                        "text_blocks": visible.text_blocks,
                        "nontext_blocks": visible.other_blocks,
                    }
                    # Explicit copy of the complete message object. Do NOT
                    # mutate SDK-original content or any tool trajectory.
                    new_messages[i] = msg.model_copy(
                        update={"content": visible.raw_text}
                    )
                    mutated = True
                if mutated:
                    if changed is None:
                        changed = dict(event)
                    changed[node] = {**update, "messages": new_messages}
            yield changed if changed is not None else event


def run_d_final_candidate(
    graph: object, request: str, *, engine: str,
    recursion_limit: int = 30, verbose: bool = False,
) -> dict:
    """Run the already-compiled D graph through the final-text bridge.

    Output is an offline *candidate receipt*, not a production diagnostic_run.
    The original D result contract and token metrics are untouched. Future
    V3 runner/ledger must explicitly bind and validate the metadata.
    """
    bridge = ExactFinalTextStream(graph, engine=engine)
    if engine == "react":
        result = esegui_grafo_rca_v2(
            bridge, request,
            recursion_limit=recursion_limit, verbose=verbose,
        )
    elif engine == "verify":
        result = esegui_grafo_rca_verify(
            bridge, request,
            recursion_limit=recursion_limit, verbose=verbose,
        )
    else:
        raise DFinalStreamCandidateBlocked("Unknown D engine")

    if type(result) is not dict:
        raise DFinalStreamCandidateBlocked("Invalid D runner receipt")
    if result.get("raw_response") is not None and (
        bridge.final_meta["content_kind"] == "not_observed"
    ):
        raise DFinalStreamCandidateBlocked(
            "D output without traced final text extraction"
        )
    return {
        "version": VERSION,
        "diagnostic_run": result,
        "d_final_text_extraction": dict(bridge.final_meta),
        "can_execute_api": False,
        "scientific_release_frozen": False,
        "source_bound": False,
    }
