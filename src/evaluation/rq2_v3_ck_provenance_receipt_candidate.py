"""Proposed successor-only C/K receipt contract with auditable text provenance.

OFFLINE CONTRACT ONLY. This module does not write records, instantiate an
LLM, read ground truth, or authorize live execution. Existing V2 source,
release and create-only ledger must never be modified or reused as V3.

The old V2 adapter provides strictly checked scientific classification and
metering. This successor receipt adds ONLY a bounded metadata envelope,
which a future *separate, source-bound V3 ledger* must validate and persist.
"""
from __future__ import annotations

from evaluation.rq2_v2_ck_text_extraction_candidate import MAX_BLOCKS, POLICY
from evaluation.rq2_v2_unified_provider_result_adapter import (
    normalize_ck_call,
    _row,
)
from evaluation.rq2_v2_unified_scientific_ledger import (
    UnifiedScientificLedgerBlocked,
    _validate_artifact,
)

VERSION = "rq2_v3_ck_provenance_receipt_candidate_v0"
META_SCHEMA = "rq2_v3_ck_text_extraction_meta_v0"
META_KEYS = frozenset((
    "schema", "policy", "content_kind", "text_blocks", "nontext_blocks",
))
RECORDABLE = frozenset(("RECORDED_COMPLETE", "INVALID_OUTPUT", "PROVIDER_ERROR"))


class CKProvenanceReceiptBlocked(ValueError):
    """Fail closed on missing or contradictory transport provenance."""


def _strict_metadata(meta: object, *, raw: object, error: bool) -> None:
    if type(meta) is not dict or set(meta) != META_KEYS:
        raise CKProvenanceReceiptBlocked("Missing or unexpected extraction metadata")
    if meta["schema"] != META_SCHEMA or meta["policy"] != POLICY:
        raise CKProvenanceReceiptBlocked("Wrong candidate extraction policy/schema")

    kind = meta["content_kind"]
    texts, others = meta["text_blocks"], meta["nontext_blocks"]
    if type(texts) is not int or type(others) is not int:
        raise CKProvenanceReceiptBlocked("Block counts must be integers")
    if not (0 <= texts <= MAX_BLOCKS and 0 <= others <= MAX_BLOCKS
            and texts + others <= MAX_BLOCKS):
        raise CKProvenanceReceiptBlocked("Unbounded content block counts")

    if error:
        if kind != "not_observed" or texts != 0 or others != 0:
            raise CKProvenanceReceiptBlocked("Error receipt has unexpected content")
        if raw is not None:
            raise CKProvenanceReceiptBlocked("Error receipt must not carry raw text")
        return

    if type(raw) is not str:
        raise CKProvenanceReceiptBlocked("Successful invoke lacks text string")
    if kind == "str":
        if texts != int(bool(raw)) or others != 0:
            raise CKProvenanceReceiptBlocked("String block counts inconsistent")
    elif kind == "list":
        if raw and texts == 0:
            raise CKProvenanceReceiptBlocked("Visible text without observed text blocks")
    elif kind == "unsupported":
        if raw != "" or texts or others:
            raise CKProvenanceReceiptBlocked("Unsupported content must be empty")
    else:
        raise CKProvenanceReceiptBlocked("Unknown successful content kind")


def candidate_ck_record_receipt(
    *, stage_id: str, logical_model: str, call: dict,
    diagnostic_run: dict,
) -> dict:
    """Normalize C/K using the old strict validator, then ADD provenance.

    The result is intentionally incompatible with V2's artifact field list.
    It may only be persisted under a separately defined successor schema.
    """
    if type(call) is not dict:
        raise CKProvenanceReceiptBlocked("Transport receipt must be a dict")

    baseline = normalize_ck_call(
        stage_id=stage_id,
        logical_model=logical_model,
        call=call,
        diagnostic_run=diagnostic_run,
    )
    meta = {
        "schema": META_SCHEMA,
        "policy": call.get("content_extraction_policy"),
        "content_kind": call.get("response_content_kind"),
        "text_blocks": call.get("text_blocks_observed"),
        "nontext_blocks": call.get("nontext_blocks_observed"),
    }
    _strict_metadata(
        meta,
        raw=call.get("raw_response"),
        error=call.get("provider_error") is not None,
    )

    artifact = {**baseline["artifact"], "text_extraction": meta}
    validate_candidate_ck_artifact(
        stage_id=stage_id, logical_model=logical_model,
        status=baseline["status"], artifact=artifact,
        diagnostic_run=diagnostic_run,
    )
    return {
        **baseline,
        "version": VERSION,
        "receipt_schema": VERSION,
        "artifact": artifact,
    }


def validate_candidate_ck_artifact(
    *, stage_id: str, logical_model: str,
    status: str, artifact: dict, diagnostic_run: dict,
) -> None:
    """Revalidate an enriched artifact, including after disk readback.

    A future ledger must ALSO check claim, release, stage dependencies,
    source hashes, canonical bytes, and commit pin. Those are intentionally
    not bypassed or implemented by this standalone validator.
    """
    if status not in RECORDABLE or type(artifact) is not dict:
        raise CKProvenanceReceiptBlocked("Unsupported candidate receipt/status")
    if type(diagnostic_run) is not dict:
        raise CKProvenanceReceiptBlocked("Missing diagnostic run")

    required_base = (
        {"stage_meter", "provider_error"} if status == "PROVIDER_ERROR"
        else {"stage_meter", "raw_response"}
    )
    if set(artifact) != required_base | {"text_extraction"}:
        raise CKProvenanceReceiptBlocked("Candidate artifact fields mismatch")

    meta = artifact["text_extraction"]
    _strict_metadata(
        meta,
        raw=artifact.get("raw_response"),
        error=status == "PROVIDER_ERROR",
    )
    if status == "RECORDED_COMPLETE" and (
        meta["content_kind"] not in ("str", "list")
    ):
        raise CKProvenanceReceiptBlocked("Complete C/K must have visible text")

    row = _row(
        stage_id=stage_id,
        logical_model=logical_model,
        stage=stage_id.rsplit(":", 1)[-1],
    )
    original = {name: artifact[name] for name in required_base}
    d_record = {
        "status": "RECORDED_COMPLETE",
        "artifact": {"diagnostic_run": diagnostic_run},
    }
    try:
        _validate_artifact(row, status, original, d_record)
    except UnifiedScientificLedgerBlocked as exc:
        raise CKProvenanceReceiptBlocked(
            "Underlying C/K evidence/status contract mismatch"
        ) from exc
