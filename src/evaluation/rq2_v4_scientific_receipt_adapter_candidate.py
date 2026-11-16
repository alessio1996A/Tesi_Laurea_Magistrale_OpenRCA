"""RQ2-V4 scientific receipt adapter: D task-aware; C/K frozen semantics.

Solo funzioni pure. Niente SDK, API, filesystem, GT, claim o dispatcher.
Le funzioni C/K del V3 *codice* sono riutilizzate soltanto per preservare
lo stesso contratto di evidenza e di estrazione, MAI per leggere o
reimpiegare risultati V3. Stage e ricevute scientifiche sono esclusivi V4.

La valutazione D è identica in classify e readback, senza il controllo
errato dei tre campi obbligatori per ogni task del ledger V2/V3.
"""
from __future__ import annotations

import hashlib

from evaluation.rq2_v2_unified_provider_result_adapter import (
    _from_metrics, UnifiedProviderReceiptBlocked,
)
from evaluation.rq2_v2_unified_scientific_ledger import (
    UnifiedScientificLedgerBlocked, _meter, _validate_artifact,
)
from evaluation.rq2_v3_d_runner_capture_candidate import VERSION as D_CAPTURE
from evaluation.rq2_v3_scientific_receipt_adapter_candidate import (
    VERSION as V3_RECEIPT,
    V3ScientificReceiptBlocked,
    D_ERROR_CODE,
    _validate_d_meta, _validate_d_identity,
    validate_v3_scientific_artifact, normalize_v3_ck_call,
)
from evaluation.rq2_v3_unified_gtfree_discovery_plan import VERSION as V3_PROTOCOL
from evaluation.rq2_v4_d_task_aware_contract import (
    V4DTaskAwareBlocked, classify_v4_d, require_v4_d_status,
)
from evaluation.rq2_v4_unified_gtfree_discovery_plan import (
    VERSION as PROTOCOL, build_offline_v4_discovery_plan,
)

VERSION = "rq2_v4_scientific_receipt_adapter_candidate_v0"
STATUSES = frozenset(("RECORDED_COMPLETE", "INVALID_OUTPUT", "PROVIDER_ERROR"))


class V4ScientificReceiptBlocked(ValueError):
    """Unsupported/mismatched scientific V4 receipt."""


def _row(stage_id: str, logical_model: str, stage: str) -> dict:
    if (
        type(stage_id) is not str or not stage_id.startswith(PROTOCOL + ":")
        or stage not in ("D", "C", "K") or type(logical_model) is not str
    ):
        raise V4ScientificReceiptBlocked("V4 identity required")
    plan = build_offline_v4_discovery_plan()
    row = next((r for r in plan["entries"] if r["stage_id"] == stage_id), None)
    if row is None or row["stage"] != stage or row["logical_model"] != logical_model:
        raise V4ScientificReceiptBlocked("Unknown/OOD/mismatched V4 stage")
    return row


def _v3_id(v4_id: str) -> str:
    if type(v4_id) is not str or not v4_id.startswith(PROTOCOL + ":"):
        raise V4ScientificReceiptBlocked("V4 stage id required")
    return V3_PROTOCOL + v4_id[len(PROTOCOL):]


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


def validate_v4_scientific_artifact(
    *, stage_id: str, logical_model: str, status: str,
    artifact: dict, diagnostic_run: dict | None = None,
) -> None:
    """Validate V4 receipt; used unchanged by adapter and ledger readback."""
    stage = stage_id.rsplit(":", 1)[-1] if type(stage_id) is str else ""
    row = _row(stage_id, logical_model, stage)
    if status not in STATUSES or type(artifact) is not dict:
        raise V4ScientificReceiptBlocked("Unknown status or artifact type")

    if stage != "D":
        if type(diagnostic_run) is not dict:
            raise V4ScientificReceiptBlocked("Immutable V4 D parent required")
        # Reuse *pure V3 C/K code*, not V3 data or scientific stage IDs.
        # The referenced D run must be V4-validated by the parent ledger.
        try:
            validate_v3_scientific_artifact(
                stage_id=_v3_id(stage_id),
                logical_model=logical_model, status=status,
                artifact=artifact, diagnostic_run=diagnostic_run,
            )
        except (V3ScientificReceiptBlocked, UnifiedScientificLedgerBlocked,
                KeyError, TypeError, ValueError) as exc:
            raise V4ScientificReceiptBlocked("Untrusted C/K receipt") from exc
        return

    if diagnostic_run is not None:
        raise V4ScientificReceiptBlocked("D must not take a parent")
    required = (
        {"provider_error", "stage_meter"} if status == "PROVIDER_ERROR"
        else {"diagnostic_run", "stage_meter"}
    )
    if set(artifact) != required | {"d_final_text_extraction"}:
        raise V4ScientificReceiptBlocked("Missing/foreign V4 D artifact fields")

    try:
        _meter(
            artifact["stage_meter"],
            allow_zero_requests=status == "PROVIDER_ERROR",
        )
        if status == "PROVIDER_ERROR":
            error = artifact["provider_error"]
            if (
                type(error) is not str
                or (not D_ERROR_CODE.fullmatch(error)
                    and error != "SDK_CONSTRUCTION_ERROR")
            ):
                raise V4ScientificReceiptBlocked("Unredacted provider error")
            _validate_d_meta(
                artifact["d_final_text_extraction"], raw=None, error=error,
            )
            _validate_artifact(
                row, "PROVIDER_ERROR",
                {k: artifact[k] for k in required}, None,
            )
            return

        run = artifact["diagnostic_run"]
        _validate_d_identity(row, run)
        _validate_d_meta(
            artifact["d_final_text_extraction"],
            raw=run.get("raw_response"), error=run.get("error"),
        )
        require_v4_d_status(row=row, run=run, status=status)
    except (V4ScientificReceiptBlocked, V3ScientificReceiptBlocked,
            UnifiedScientificLedgerBlocked, V4DTaskAwareBlocked,
            KeyError, TypeError, ValueError) as exc:
        raise V4ScientificReceiptBlocked("V4 D receipt/status failed readback") from exc


def normalize_v4_d_capture(
    *, stage_id: str, logical_model: str, captured: dict,
) -> dict:
    """One already-finished D run -> task-aware V4 receipt, no API."""
    row = _row(stage_id, logical_model, "D")
    if (
        type(captured) is not dict
        or captured.get("version") != D_CAPTURE
        or captured.get("can_execute_api") is not False
        or captured.get("can_write_scientific_records") is not False
        or captured.get("scientific_release_frozen") is not False
    ):
        raise V4ScientificReceiptBlocked("Untrusted D capture envelope")
    run = captured.get("diagnostic_run")
    if type(run) is not dict:
        raise V4ScientificReceiptBlocked("Missing D result")
    _validate_d_identity(row, run)
    error = run.get("error")
    if error is not None and (type(error) is not str or not error.strip()):
        raise V4ScientificReceiptBlocked("Malformed runner error")
    try:
        _validate_d_meta(
            captured.get("d_final_text_extraction"),
            raw=run.get("raw_response"), error=error,
        )
        meter = _from_metrics(
            run.get("metrics"), can_be_zero=error is not None,
        )
    except (V3ScientificReceiptBlocked, UnifiedProviderReceiptBlocked,
            ValueError, KeyError, TypeError) as exc:
        raise V4ScientificReceiptBlocked("Bad D text provenance or usage") from exc

    if error is not None:
        status = "PROVIDER_ERROR"
        fingerprint = hashlib.sha256(error.encode("utf-8")).hexdigest()[:16]
        artifact = {
            "provider_error": "RUNNER_EXECUTION_ERROR_SHA256_" + fingerprint,
            "stage_meter": meter,
            "d_final_text_extraction": dict(captured["d_final_text_extraction"]),
        }
    else:
        status = classify_v4_d(row=row, run=run)
        artifact = {
            "diagnostic_run": run,
            "stage_meter": meter,
            "d_final_text_extraction": dict(captured["d_final_text_extraction"]),
        }
    validate_v4_scientific_artifact(
        stage_id=stage_id, logical_model=logical_model,
        status=status, artifact=artifact,
    )
    return _receipt(stage_id, status, artifact)


def normalize_v4_ck_call(
    *, stage_id: str, logical_model: str,
    call: dict, diagnostic_run: dict,
) -> dict:
    """Reuse exact V3 C/K grammar/evidence code, with exclusive V4 identities."""
    stage = stage_id.rsplit(":", 1)[-1] if type(stage_id) is str else ""
    _row(stage_id, logical_model, stage)
    if stage not in ("C", "K"):
        raise V4ScientificReceiptBlocked("Only C/K accepted")
    if type(diagnostic_run) is not dict:
        raise V4ScientificReceiptBlocked("V4 D parent required")
    try:
        inherited = normalize_v3_ck_call(
            stage_id=_v3_id(stage_id),
            logical_model=logical_model, call=call,
            diagnostic_run=diagnostic_run,
        )
    except (V3ScientificReceiptBlocked, UnifiedScientificLedgerBlocked,
            ValueError, KeyError, TypeError) as exc:
        raise V4ScientificReceiptBlocked("C/K transport/evidence invalid") from exc
    if (
        type(inherited) is not dict
        or inherited.get("version") != V3_RECEIPT
        or inherited.get("stage_id") != _v3_id(stage_id)
        or inherited.get("status") not in STATUSES
    ):
        raise V4ScientificReceiptBlocked("Foreign/untrusted C/K normalizer")
    status, artifact = inherited["status"], inherited["artifact"]
    validate_v4_scientific_artifact(
        stage_id=stage_id, logical_model=logical_model,
        status=status, artifact=artifact,
        diagnostic_run=diagnostic_run,
    )
    return _receipt(stage_id, status, artifact)
