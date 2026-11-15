"""Proposed pure V3 D/C/K scientific receipt adapter (OFFLINE ONLY).

NO SDK, API, file I/O, GT, claim, release or production dispatcher.
Rows are ALWAYS resolved from the distinct V3 GT-free plan. Strict
scientific contract logic is reused from the frozen V2 validators, NOT
their V2 stage-ID lookup or create-only namespace. The final V3 ledger
must independently validate source/release/commit, canonical bytes,
dependencies, claim-first, restart and the provenance envelopes.
"""
from __future__ import annotations

import hashlib

from evaluation.rq2_v2_ck_text_extraction_candidate import (
    POLICY, MAX_BLOCKS,
)
from evaluation.rq2_v2_unified_provider_result_adapter import (
    ERROR_CODE, UnifiedProviderReceiptBlocked,
    _from_metrics, _from_usage, _classify_with_ledger,
)
from evaluation.rq2_v2_unified_provenance_gate import audit_captured_v2_d
from evaluation.rq2_v2_unified_scientific_ledger import (
    UnifiedScientificLedgerBlocked, _validate_artifact,
)
from evaluation.rq2_v3_ck_provenance_receipt_candidate import (
    CKProvenanceReceiptBlocked,
    META_SCHEMA, _strict_metadata,
)
from evaluation.rq2_v3_d_final_stream_candidate import D_META_SCHEMA
from evaluation.rq2_v3_d_runner_capture_candidate import VERSION as D_CAPTURE
from evaluation.rq2_v3_unified_gtfree_discovery_plan import (
    VERSION as V3_PROTOCOL, build_offline_v3_discovery_plan,
)

VERSION = "rq2_v3_scientific_receipt_adapter_candidate_v0"
D_FIELDS = frozenset(("schema", "policy", "content_kind",
                      "text_blocks", "nontext_blocks"))
STATUSES = frozenset(("RECORDED_COMPLETE", "INVALID_OUTPUT", "PROVIDER_ERROR"))


class V3ScientificReceiptBlocked(ValueError):
    """A receipt is ambiguous, corrupted, or uses a frozen V2 stage ID."""


def _row(stage_id: str, logical_model: str, stage: str) -> dict:
    if (
        type(stage_id) is not str or
        not stage_id.startswith(V3_PROTOCOL + ":") or
        type(logical_model) is not str or
        stage not in ("D", "C", "K")
    ):
        raise V3ScientificReceiptBlocked("V3 stage/model identity required")
    plan = build_offline_v3_discovery_plan()
    row = next((r for r in plan["entries"] if r["stage_id"] == stage_id), None)
    if row is None or row["logical_model"] != logical_model or row["stage"] != stage:
        raise V3ScientificReceiptBlocked("Wrong V3 arm, model or stage")
    return row


def _validate_d_meta(meta: object, raw: object, error: object) -> None:
    if type(meta) is not dict or set(meta) != D_FIELDS:
        raise V3ScientificReceiptBlocked("Missing/unexpected D text provenance")
    if meta["schema"] != D_META_SCHEMA or meta["policy"] != POLICY:
        raise V3ScientificReceiptBlocked("Wrong D final-text policy/schema")
    n, other, kind = (
        meta["text_blocks"], meta["nontext_blocks"], meta["content_kind"]
    )
    if (
        type(n) is not int or type(other) is not int
        or n < 0 or other < 0 or n + other > MAX_BLOCKS
    ):
        raise V3ScientificReceiptBlocked("Invalid D block counts")
    if kind == "not_observed":
        if n or other or raw is not None:
            raise V3ScientificReceiptBlocked("Unobserved D metadata contradiction")
    elif kind == "str":
        if other or (raw is not None and n != int(bool(raw))):
            raise V3ScientificReceiptBlocked("D string provenance contradiction")
    elif kind == "list":
        if type(raw) is str and raw and not n:
            raise V3ScientificReceiptBlocked("D text without text blocks")
    elif kind == "unsupported":
        if raw not in (None, "") or n or other:
            raise V3ScientificReceiptBlocked("Unsupported D envelope contradiction")
    else:
        raise V3ScientificReceiptBlocked("Unexpected D content kind")

    if raw is not None and type(raw) is not str:
        raise V3ScientificReceiptBlocked("D final response must be text")
    if error is None and raw is not None and kind not in ("str", "list"):
        raise V3ScientificReceiptBlocked("D final response provenance missing")
    # When a graph fails AFTER observing a final message, the runner
    # may discard raw output but observed block counts remain truthful.
    # Such errors are never labelled RECORDED_COMPLETE.


def _validate_v3_base(
    row: dict, status: str, base: dict, diagnostic_run: dict | None,
) -> None:
    parent = (
        {"status": "RECORDED_COMPLETE",
         "artifact": {"diagnostic_run": diagnostic_run}}
        if row["stage"] != "D" else None
    )
    try:
        _validate_artifact(row, status, base, parent)
    except UnifiedScientificLedgerBlocked as exc:
        raise V3ScientificReceiptBlocked(
            "Underlying diagnosis/evidence/status contract mismatch"
        ) from exc


def validate_v3_scientific_artifact(
    *, stage_id: str, logical_model: str, status: str,
    artifact: dict, diagnostic_run: dict | None = None,
) -> None:
    """Pure readback-ready artifact validator; not a ledger/release gate."""
    stage = stage_id.rsplit(":", 1)[-1] if type(stage_id) is str else ""
    row = _row(stage_id, logical_model, stage)
    if status not in STATUSES or type(artifact) is not dict:
        raise V3ScientificReceiptBlocked("Invalid status/artifact type")

    if stage == "D":
        required = (
            {"provider_error", "stage_meter"} if status == "PROVIDER_ERROR"
            else {"diagnostic_run", "stage_meter"}
        )
        if set(artifact) != required | {"d_final_text_extraction"}:
            raise V3ScientificReceiptBlocked("D V3 artifact schema mismatch")
        if status == "PROVIDER_ERROR":
            if diagnostic_run is not None:
                raise V3ScientificReceiptBlocked("D error has untrusted source")
            # A D runner error must have discarded raw output; the meta
            # remains source-bound only under a future V3 ledger.
            _validate_d_meta(
                artifact["d_final_text_extraction"], raw=None,
                error=artifact["provider_error"],
            )
        else:
            d = artifact["diagnostic_run"]
            if type(d) is not dict:
                raise V3ScientificReceiptBlocked("D runner payload missing")
            _validate_d_identity(row, d)
            _validate_d_meta(
                artifact["d_final_text_extraction"],
                raw=d.get("raw_response"), error=d.get("error"),
            )
        base = {k: artifact[k] for k in required}
        _validate_v3_base(row, status, base, None)
        return

    if type(diagnostic_run) is not dict:
        raise V3ScientificReceiptBlocked("Immutable parent D run required")
    _validate_d_identity(row, diagnostic_run)
    try:
        audit_captured_v2_d(
            run=diagnostic_run, case_id=row["case_id"],
            model=row["logical_model"], harness=row["harness"],
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise V3ScientificReceiptBlocked("Untrusted D tool provenance") from exc
    required = (
        {"provider_error", "stage_meter"} if status == "PROVIDER_ERROR"
        else {"raw_response", "stage_meter"}
    )
    if set(artifact) != required | {"text_extraction"}:
        raise V3ScientificReceiptBlocked("C/K V3 artifact schema mismatch")
    meta = artifact["text_extraction"]
    try:
        _strict_metadata(
            meta, raw=artifact.get("raw_response"),
            error=status == "PROVIDER_ERROR",
        )
    except CKProvenanceReceiptBlocked as exc:
        raise V3ScientificReceiptBlocked("Untrusted C/K text metadata") from exc
    if status == "RECORDED_COMPLETE" and meta["content_kind"] not in ("str", "list"):
        raise V3ScientificReceiptBlocked("Complete C/K lacks visible text")
    base = {k: artifact[k] for k in required}
    _validate_v3_base(row, status, base, diagnostic_run)


def _validate_d_identity(row: dict, run: dict) -> None:
    required = {
        "case_id": row["case_id"],
        "variant": row["harness"],
        "variant_scheme": "current",
        "model": row["model_id"],
        "model_provider": row["model_provider"],
        "output_contract_mode": "v2_enforce",
        "max_tool_rounds": 6,
    }
    if type(run) is not dict or any(
        run.get(key) != value for key, value in required.items()
    ):
        raise V3ScientificReceiptBlocked("D case/model/harness/output drift")


def _receipt(stage_id: str, status: str, artifact: dict) -> dict:
    return {
        "version": VERSION,
        "stage_id": stage_id,
        "status": status,
        "artifact": artifact,
        "can_execute_api": False,
        "can_write_scientific_records": False,
        "usd_cost_known": False,
        "observed_requests_are_http_hard_cap": False,
    }


def normalize_v3_d_capture(
    *, stage_id: str, logical_model: str, captured: dict,
) -> dict:
    """D receipt from the *already obtained* exact final-text runner output."""
    row = _row(stage_id, logical_model, "D")
    if (
        type(captured) is not dict
        or captured.get("version") != D_CAPTURE
        or captured.get("can_execute_api") is not False
        or captured.get("can_write_scientific_records") is not False
        or captured.get("scientific_release_frozen") is not False
    ):
        raise V3ScientificReceiptBlocked("Untrusted D capture envelope")
    run = captured.get("diagnostic_run")
    meta = captured.get("d_final_text_extraction")
    _validate_d_identity(row, run)
    error = run.get("error")
    if error is not None and (
        type(error) is not str or not error.strip()
    ):
        raise V3ScientificReceiptBlocked("Invalid D error representation")
    _validate_d_meta(meta, raw=run.get("raw_response"), error=error)
    try:
        meter = _from_metrics(
            run.get("metrics"), can_be_zero=(error is not None)
        )
    except UnifiedProviderReceiptBlocked as exc:
        raise V3ScientificReceiptBlocked("Bad D usage") from exc

    if error is not None:
        fingerprint = hashlib.sha256(error.encode("utf-8")).hexdigest()[:16]
        status = "PROVIDER_ERROR"
        artifact = {
            "provider_error": "RUNNER_EXECUTION_ERROR_SHA256_" + fingerprint,
            "stage_meter": meter,
            "d_final_text_extraction": dict(meta),
        }
    else:
        base = {"diagnostic_run": run, "stage_meter": meter}
        try:
            _validate_artifact(row, "RECORDED_COMPLETE", base, None)
        except UnifiedScientificLedgerBlocked:
            try:
                _validate_artifact(row, "INVALID_OUTPUT", base, None)
            except UnifiedScientificLedgerBlocked as exc:
                raise V3ScientificReceiptBlocked(
                    "Inconsistent D task/evidence status"
                ) from exc
            status = "INVALID_OUTPUT"
        else:
            status = "RECORDED_COMPLETE"
        artifact = {**base, "d_final_text_extraction": dict(meta)}
    validate_v3_scientific_artifact(
        stage_id=stage_id, logical_model=logical_model,
        status=status, artifact=artifact,
    )
    return _receipt(stage_id, status, artifact)


def normalize_v3_ck_call(
    *, stage_id: str, logical_model: str,
    call: dict, diagnostic_run: dict,
) -> dict:
    """C/K receipt using V3 identities, original evidence and strict parser."""
    if type(stage_id) is not str:
        raise V3ScientificReceiptBlocked("V3 stage ID required")
    stage = stage_id.rsplit(":", 1)[-1]
    if stage not in ("C", "K"):
        raise V3ScientificReceiptBlocked("C/K stage required")
    row = _row(stage_id, logical_model, stage)
    if type(call) is not dict or type(diagnostic_run) is not dict:
        raise V3ScientificReceiptBlocked("Missing C/K transport or D source")
    _validate_d_identity(row, diagnostic_run)
    try:
        audit_captured_v2_d(
            run=diagnostic_run, case_id=row["case_id"],
            model=row["logical_model"], harness=row["harness"],
        )
        meter = _from_usage(
            call.get("usage"), attempts=call.get("api_attempts")
        )
    except (ValueError, TypeError, KeyError, UnifiedProviderReceiptBlocked) as exc:
        raise V3ScientificReceiptBlocked("CK evidence/usage contract mismatch") from exc
    error, raw = call.get("provider_error"), call.get("raw_response")
    meta = {
        "schema": META_SCHEMA,
        "policy": call.get("content_extraction_policy"),
        "content_kind": call.get("response_content_kind"),
        "text_blocks": call.get("text_blocks_observed"),
        "nontext_blocks": call.get("nontext_blocks_observed"),
    }
    try:
        _strict_metadata(meta, raw=raw, error=error is not None)
    except CKProvenanceReceiptBlocked as exc:
        raise V3ScientificReceiptBlocked("C/K extraction metadata mismatch") from exc
    if error is not None:
        if (
            type(error) is not str or not ERROR_CODE.fullmatch(error)
            or raw is not None
        ):
            raise V3ScientificReceiptBlocked("Untrusted provider error")
        status = "PROVIDER_ERROR"
        base = {"provider_error": error, "stage_meter": meter}
    else:
        if call.get("api_attempts") != 1 or type(raw) is not str:
            raise V3ScientificReceiptBlocked("Unambiguous C/K call required")
        base = {"raw_response": raw, "stage_meter": meter}
        try:
            status = _classify_with_ledger(
                row=row, artifact=base,
                d_record={"status": "RECORDED_COMPLETE",
                          "artifact": {"diagnostic_run": diagnostic_run}},
            )
        except UnifiedProviderReceiptBlocked as exc:
            raise V3ScientificReceiptBlocked("C/K status ambiguous") from exc
    artifact = {**base, "text_extraction": meta}
    validate_v3_scientific_artifact(
        stage_id=stage_id, logical_model=logical_model,
        status=status, artifact=artifact,
        diagnostic_run=diagnostic_run,
    )
    return _receipt(stage_id, status, artifact)
