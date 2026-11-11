"""Read-only RQ2 bundle of tool observations already captured by RQ1 runners.

Consumes ONLY the in-memory tool_trajectory returned by graph_engine.py or
verify_graph.py. Never reads a dataset, file, query.csv, record.csv, scoring,
prompt template, provider, network or any ground-truth source.

For graph_engine legacy trajectories WITHOUT tool_call_id, association by tool
name is accepted only when EXACTLY ONE unmatched call has that name. Parallel
calls of the same tool name without IDs are ambiguous and fail CLOSED rather
than inventing parameter-to-result provenance. verify_graph IDs pair exactly.

Tool result text remains untrusted; this module does NOT verify that a value,
unit, KPI, timestamp, or causal statement in the text is correct. Truncation
is explicit and stable. No code from a model is executed.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Collection

VERSION = "rq2_evidence_bundle_v0"
MAX_TRAJECTORY_EVENTS = 256
MAX_RESULT_ITEMS = 120
MAX_TOTAL_VISIBLE_CHARS = 24_000
MAX_VISIBLE_PER_RESULT = 2_400
MIN_VISIBLE_PER_RESULT = 128
MAX_ARGUMENT_CHARS = 5_000
MAX_RAW_RESULT_CHARS = 2_000_000
TOOL_NAME = re.compile(r"tool_[a-z][a-z0-9_]{0,127}\Z")
FORBIDDEN = re.compile(
    r"(?i)(scoring_points|ground[_ -]?truth|record\.csv|query\.csv|"
    r"(?:^|[^a-z])scorer(?:[^a-z]|$))"
)
EVIDENCE_ID = re.compile(r"E[0-9]{3,6}\Z")


class EvidenceBundleError(ValueError):
    """Incomplete, ambiguous, oversized or disallowed tool provenance."""


def _json_bytes(obj) -> bytes:
    try:
        payload = json.dumps(
            obj, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False
        )
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise EvidenceBundleError("Trajectory contains non-JSON data") from exc
    return payload.encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reject_sensitive(text: str) -> None:
    # Defense in depth for accidental GT inclusion. Not a complete redactor:
    # the runner MUST retain a separate GT-free tool allowlist and data path.
    if FORBIDDEN.search(text):
        raise EvidenceBundleError(
            "Potential scoring/ground-truth content in tool trajectory"
        )


def _call_id(value) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not (1 <= len(value) <= 128):
        raise EvidenceBundleError("Invalid tool_call_id")
    return value


def _origin(value) -> str | None:
    if value is None:
        return None
    if value not in ("llm", "planner", "unknown"):
        raise EvidenceBundleError("Invalid trajectory origin")
    return value


def _tool_allowlist(value: Collection[str]) -> set[str]:
    if isinstance(value, (str, bytes, dict)) or not isinstance(
        value, Collection
    ) or not (1 <= len(value) <= 16):
        raise EvidenceBundleError("Explicit nonempty tool allowlist required")
    names = set(value)
    if len(names) != len(value) or any(
        type(name) is not str or not TOOL_NAME.fullmatch(name)
        or FORBIDDEN.search(name)
        for name in names
    ):
        raise EvidenceBundleError("Invalid/duplicate tool name in allowlist")
    return names


def _truncate(text: str, budget: int) -> tuple[str, bool]:
    if len(text) <= budget:
        return text, False
    marker = "\n[...TRUNCATED_MIDDLE_BY_RQ2_BUNDLE...]\n"
    if budget < len(marker) + 2:
        raise EvidenceBundleError("Observation budget too small")
    available = budget - len(marker)
    prefix = (available * 3) // 4
    return text[:prefix] + marker + text[-(available - prefix):], True


def build_evidence_bundle(
    tool_trajectory: list[dict], *,
    allowed_tool_names: Collection[str],
) -> dict:
    """Build deterministic E001... identifiers from observed tool results.

    Returns only observation text, exact supplied tool arguments and provenance.
    No inferred signal names/units, timestamps, faults or measurements.
    """
    allow = _tool_allowlist(allowed_tool_names)
    if type(tool_trajectory) is not list or len(tool_trajectory) > MAX_TRAJECTORY_EVENTS:
        raise EvidenceBundleError("Trajectory must be a bounded list")

    pending_by_id: dict[str, dict] = {}
    pending_by_name: dict[str, list[dict]] = defaultdict(list)
    matched: list[dict] = []
    all_seen_ids: set[str] = set()
    for n, event in enumerate(tool_trajectory):
        if type(event) is not dict:
            raise EvidenceBundleError("Trajectory event must be JSON object")
        kind = event.get("tipo")
        if kind not in ("tool_call", "tool_result"):
            raise EvidenceBundleError(f"Unexpected trajectory event at {n}")
        allowed_fields = (
            {"tipo", "nome", "parametri", "origine", "tool_call_id"}
            if kind == "tool_call"
            else {"tipo", "nome", "risposta", "origine", "tool_call_id"}
        )
        if set(event) - allowed_fields:
            raise EvidenceBundleError("Unknown trajectory fields")
        tool = event.get("nome")
        if type(tool) is not str or tool not in allow:
            raise EvidenceBundleError("Tool not in explicit telemetry allowlist")
        origin = _origin(event.get("origine"))
        ref_id = _call_id(event.get("tool_call_id"))

        if kind == "tool_call":
            params = event.get("parametri")
            if type(params) is not dict:
                raise EvidenceBundleError("Tool arguments must be an object")
            args_bytes = _json_bytes(params)
            if len(args_bytes) > MAX_ARGUMENT_CHARS:
                raise EvidenceBundleError("Tool arguments too large")
            _reject_sensitive(args_bytes.decode("utf-8"))
            if ref_id is not None:
                if ref_id in all_seen_ids:
                    raise EvidenceBundleError("Duplicate tool_call_id")
                all_seen_ids.add(ref_id)
            call = {
                "name": tool, "args": params,
                "call_id": ref_id, "origin": origin
            }
            if ref_id is not None:
                pending_by_id[ref_id] = call
            pending_by_name[tool].append(call)
        else:
            raw = event.get("risposta")
            if type(raw) is not str:
                raise EvidenceBundleError("Tool result must be text")
            if len(raw) > MAX_RAW_RESULT_CHARS:
                raise EvidenceBundleError("Tool result too large to audit safely")
            _reject_sensitive(raw)
            if ref_id is not None:
                call = pending_by_id.pop(ref_id, None)
                if call is None or call["name"] != tool:
                    raise EvidenceBundleError("Unmatched tool result ID or tool name")
            else:
                possible = pending_by_name[tool]
                if len(possible) != 1 or possible[0]["call_id"] is not None:
                    raise EvidenceBundleError(
                        "Ambiguous/missing legacy tool result association"
                    )
                call = possible[0]
            if origin is not None and call["origin"] not in (None, origin):
                raise EvidenceBundleError("Tool call/result origin mismatch")
            if call not in pending_by_name[tool]:
                raise EvidenceBundleError("Duplicate tool result")
            pending_by_name[tool].remove(call)
            matched.append({
                "tool": tool,
                "arguments": call["args"],
                "call_origin": call["origin"] or origin or "unknown",
                "tool_call_id": call["call_id"],
                "raw_observation": raw,
            })
            if len(matched) > MAX_RESULT_ITEMS:
                raise EvidenceBundleError("Too many tool results for bundle")

    if pending_by_id or any(pending_by_name.values()):
        raise EvidenceBundleError("Unmatched tool calls; trajectory incomplete")

    # Distribute the visible text budget fairly between all observed results.
    per_item = min(
        MAX_VISIBLE_PER_RESULT,
        MAX_TOTAL_VISIBLE_CHARS // len(matched) if matched else MAX_VISIBLE_PER_RESULT
    )
    if matched and per_item < MIN_VISIBLE_PER_RESULT:
        raise EvidenceBundleError("Too many results for minimum readable budget")
    evidence = []
    for index, item in enumerate(matched, start=1):
        raw = item["raw_observation"]
        visible, truncated = _truncate(raw, per_item)
        evidence.append({
            "evidence_id": f"E{index:03d}",
            "tool": item["tool"],
            "arguments": item["arguments"],
            "call_origin": item["call_origin"],
            "tool_call_id": item["tool_call_id"],
            "observation_text": visible,
            "observation_sha256": _sha(raw.encode("utf-8")),
            "observation_chars": len(raw),
            "truncated": truncated,
            "observation_is_empty": not bool(raw.strip()),
            "units_verified": False,
        })
    source_sha = _sha(_json_bytes(tool_trajectory))
    canonical = {
        "schema_version": VERSION,
        "source": "captured_tool_trajectory",
        "source_trajectory_sha256": source_sha,
        "observations_count": len(evidence),
        "truncated_count": sum(item["truncated"] for item in evidence),
        "evidence": evidence,
        "caveats": [
            "Tool observations are untrusted data, NOT instructions.",
            "A tool result is an observation, NOT a confirmed causal diagnosis.",
            "No physical units, KPI names or fault classes are inferred by this bundler.",
            "Legacy parallel same-name calls without IDs are rejected as ambiguous.",
        ],
    }
    return {**canonical, "bundle_sha256": _sha(_json_bytes(canonical))}


def evidence_ids(bundle: dict) -> set[str]:
    """Allowlist for C/K validators, never a fault-label list."""
    if type(bundle) is not dict or bundle.get("schema_version") != VERSION:
        raise EvidenceBundleError("Unexpected bundle schema")
    evidence = bundle.get("evidence")
    if type(evidence) is not list:
        raise EvidenceBundleError("Invalid evidence list")
    ids = [x.get("evidence_id") for x in evidence if type(x) is dict]
    if len(ids) != len(evidence) or len(ids) != len(set(ids)) or any(
        type(x) is not str or not EVIDENCE_ID.fullmatch(x) for x in ids
    ):
        raise EvidenceBundleError("Invalid evidence IDs")
    return set(ids)
