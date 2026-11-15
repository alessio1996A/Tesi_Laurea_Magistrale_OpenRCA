"""G4I: dispatcher unico RQ2-V2 per UN SOLO stage, per ora FAKE-ONLY.

Integra il preflight GT-free G4H e il vero ledger create-only G4F.
Questa implementazione usa i grafi reali soltanto attraverso un fake
gateway: nessun client SDK viene importato/costruito qui e le socket
sono bloccate anche durante l'esecuzione simulata.

Non e' una entrypoint per API a pagamento: accetta SOLO una release
sintetica in TemporaryDirectory, con marker fake e senza Market.zip.
Qualsiasi futuro adapter provider live richiede un gate SEPARATO e
un nuovo source freeze/approvazione esplicita, prima del primo claim.
Gli undici casi OOD rimangono inaccessibili.
"""
from __future__ import annotations

from pathlib import Path
import tempfile

from evaluation.rq2_langchain_parameter_mock_probe import network_forbidden
from evaluation.rq2_probe_adapter import (
    prepare_candidate_rule, prepare_cause_probe,
)
from evaluation.rq2_stage_binding import ALLOWED_TOOLS
from evaluation.rq2_v2_unified_dispatcher_offline import (
    OfflineFakeGateway, OfflineStageResponse, SimulatedProviderFailure,
    _classify_ck, _classify_d,
)
from evaluation.rq2_v2_unified_live_stage_preflight import (
    preview_one_unified_stage,
)
from evaluation.rq2_v2_unified_scientific_ledger import (
    UnifiedScientificLedger, _read,
)
from evaluation.rq2_v2_unified_scientific_ledger_preflight import RELEASE_FILE

VERSION = "rq2_v2_unified_single_stage_dispatcher_fake_v0"
MARKER = ".rq2_v2_unified_single_stage_fake_only"
MARKER_BYTES = b"RQ2_V2_UNIFIED_SINGLE_STAGE_FAKE_NO_API\n"
FAKE_RELEASE_REFERENCE = "SYNTHETIC_APPROVAL_NOT_REAL"


class UnifiedSingleStageBlocked(RuntimeError):
    """Provenienza, stage, gateway o modalita' fake non verificati."""


def _require_fake_only(
    *, ledger: UnifiedScientificLedger, gateway: OfflineFakeGateway,
) -> None:
    if type(ledger) is not UnifiedScientificLedger or not isinstance(
        gateway, OfflineFakeGateway
    ):
        raise UnifiedSingleStageBlocked("Only audited ledger and fake gateway")
    root = ledger.data
    # Non e' sufficiente un marker copiato in Drive: i test usano SEMPRE
    # una radice sotto la temporary directory del sistema operativo.
    temp = Path(tempfile.gettempdir()).resolve()
    if (
        root == temp
        or not root.resolve().is_relative_to(temp)
        or any(p.is_symlink() for p in (root, root.parent))
    ):
        raise UnifiedSingleStageBlocked("Offline fake root must be temporary")
    marker = root / MARKER
    allowed_processed = root / "data/processed"
    manifest = allowed_processed / "benchmark_inputs_market.csv"
    if (
        marker.is_symlink()
        or not marker.is_file()
        or marker.read_bytes() != MARKER_BYTES
        or (root / "Market.zip").exists()
        or (root / "data/results").exists()
        or (root / "data/rq2").exists()
        or (root / "data/rq2_v2_provenance").exists()
        or (root / "data/rq2_v2_unified_synthetic_v0").exists()
        or not allowed_processed.is_dir()
        or allowed_processed.is_symlink()
        or not manifest.is_file()
        or manifest.is_symlink()
        or {p.name for p in allowed_processed.iterdir()}
        != {"benchmark_inputs_market.csv"}
    ):
        raise UnifiedSingleStageBlocked("Real dataset/unsafe fake-only root")
    release = _read(root / RELEASE_FILE)
    if (
        type(release) is not dict
        or release.get("approval_reference") != FAKE_RELEASE_REFERENCE
        or release.get("approved_total_usd_limit") != "0.20"
        or release.get("phase") != "discovery"
    ):
        raise UnifiedSingleStageBlocked("Only SYNTHETIC release permitted")
    ledger.audit_restart()


def _bound_probe(
    *, ledger: UnifiedScientificLedger, preview: dict,
) -> dict:
    stage_id = preview["stage_id"]
    stage = preview["stage"]
    stem = stage_id.rsplit(":", 1)[0]
    d = ledger.load_record(stage_id=stem + ":D")
    if d is None or d["status"] != "RECORDED_COMPLETE":
        raise UnifiedSingleStageBlocked("Valid D required for C/K")
    diagnostic = d["artifact"]["diagnostic_run"]
    if stage == "C":
        package = prepare_cause_probe(
            original_instruction=preview["instruction"],
            diagnostic_run=diagnostic,
            allowed_tool_names=ALLOWED_TOOLS,
        )
    elif stage == "K":
        c = ledger.load_record(stage_id=stem + ":C")
        if c is None or c["status"] != "RECORDED_COMPLETE":
            raise UnifiedSingleStageBlocked("Valid C required for K")
        package = prepare_candidate_rule(
            original_instruction=preview["instruction"],
            diagnostic_run=diagnostic,
            cause_raw_json=c["artifact"]["raw_response"],
            phase="discovery",
            allowed_tool_names=ALLOWED_TOOLS,
        )
    else:
        raise UnifiedSingleStageBlocked("Probe requested for D")
    if (
        package.get("package_sha256") != preview["prepared_package_sha256"]
        or package.get("system_prompt_sha256")
        != preview["C_K_system_prompt_sha256"]
        or package.get("ready_for_api") is not False
        or package.get("model_api_calls") != 0
    ):
        raise UnifiedSingleStageBlocked("C/K immutable prompt binding drift")
    return package


def _blocked_descendants(
    *, ledger: UnifiedScientificLedger, preview: dict,
) -> list[str]:
    stage = preview["stage"]
    to_block = ("C", "K") if stage == "D" else (
        ("K",) if stage == "C" else ()
    )
    stem = preview["stage_id"].rsplit(":", 1)[0]
    saved = []
    for child in to_block:
        sid = stem + ":" + child
        ledger.record_stage(
            stage_id=sid,
            model_id=preview["model_id"],
            status="BLOCKED_DEPENDENCY",
            artifact={},
        )
        saved.append(sid)
    return saved


def _simulated_provider_error() -> dict:
    # Solo il gateway finto puo' generare questa eccezione;
    # l'errore e' simulato PRIMA di una chiamata HTTP reale.
    return {
        "provider_error": "SIMULATED_PROVIDER_FAILURE_PRE_REQUEST",
        "stage_meter": {
            "schema": "rq2_v2_unified_stage_meter_v0",
            "observed_model_requests": 0,
            "input_tokens_observed": 0,
            "output_tokens_observed": 0,
            "usage_complete": False,
            "cost_estimate_usd_not_invoice": "UNKNOWN",
            "usd_hard_cap_guaranteed": False,
        },
    }


def run_one_unified_stage_fake(
    *, data_dir: Path, repo_dir: Path,
    stage_id: str, expected_commit: str,
    approved_release_sha256: str,
    gateway: OfflineFakeGateway,
) -> dict:
    """Un solo stage effettivamente claimed/recorded, con backend SOLO fake.

    Se D/C fallisce, archivia anche gli stage figli come
    BLOCKED_DEPENDENCY, senza nuove richieste né claim ai figli.
    Crash o ricevuta ambigua dopo il claim: resta orphan, niente retry.
    """
    ledger = UnifiedScientificLedger(
        data_dir=data_dir, repo_dir=repo_dir,
        expected_commit=expected_commit,
        approved_release_sha256=approved_release_sha256,
    )
    _require_fake_only(ledger=ledger, gateway=gateway)
    preview = preview_one_unified_stage(
        data_dir=data_dir, repo_dir=repo_dir,
        stage_id=stage_id,
        expected_commit=expected_commit,
        approved_release_sha256=approved_release_sha256,
    )
    if (
        preview.get("status") != "STAGE_SOURCE_PREVIEW_READY_BUT_NO_API"
        or preview.get("can_execute_api") is not False
        or preview.get("can_create_scientific_claim") is not False
        or preview.get("can_run_ood_test") is not False
        or preview.get("model_requests_sent") != 0
        or preview.get("stage_id") != stage_id
        or preview.get("release_sha256") != ledger.release_sha
        or preview.get("source_commit") != ledger.expected_commit
    ):
        raise UnifiedSingleStageBlocked("Preflight authority or identity drift")

    stage = preview["stage"]
    package = _bound_probe(ledger=ledger, preview=preview) if (
        stage in ("C", "K")
    ) else None
    # Ogni operazione che puo' fallire PRE-CLAIM e' conclusa.
    # Il claim e' l'ultima operazione prima del callback fake.
    ledger.claim_stage(stage_id=stage_id, model_id=preview["model_id"])
    try:
        with network_forbidden():
            if stage == "D":
                response = gateway.run_d(
                    case_id=preview["case_id"],
                    model=preview["logical_model"],
                    harness=preview["harness"],
                )
            elif stage == "C":
                response = gateway.run_c(
                    package=package, model=preview["logical_model"],
                )
            else:
                response = gateway.run_k(
                    package=package, model=preview["logical_model"],
                )
    except SimulatedProviderFailure:
        status = "PROVIDER_ERROR"
        artifact = _simulated_provider_error()
        simulated_invocations = 0
    else:
        if type(response) is not OfflineStageResponse:
            raise UnifiedSingleStageBlocked("Invalid fake gateway receipt")
        if type(response.meter) is not dict:
            raise UnifiedSingleStageBlocked("Missing fake metering receipt")
        simulated_invocations = response.meter.get("observed_model_requests")
        if stage == "D":
            if type(response.output) is not dict:
                raise UnifiedSingleStageBlocked("Invalid D fake output")
            status = _classify_d(
                response.output,
                case_id=preview["case_id"],
                model=preview["logical_model"],
                harness=preview["harness"],
            )
            artifact = {
                "diagnostic_run": response.output,
                "stage_meter": response.meter,
            }
        else:
            if type(response.output) is not str:
                raise UnifiedSingleStageBlocked("Invalid C/K fake raw output")
            stem = stage_id.rsplit(":", 1)[0]
            d = ledger.load_record(stage_id=stem + ":D")
            if d is None:
                raise UnifiedSingleStageBlocked("Missing source-bound D")
            status = _classify_ck(
                response.output, stage=stage,
                d_run=d["artifact"]["diagnostic_run"],
            )
            artifact = {
                "raw_response": response.output,
                "stage_meter": response.meter,
            }

    persisted = ledger.record_stage(
        stage_id=stage_id, model_id=preview["model_id"],
        status=status, artifact=artifact,
    )
    descendants = (
        _blocked_descendants(ledger=ledger, preview=preview)
        if status != "RECORDED_COMPLETE" else []
    )
    audit = ledger.audit_restart()
    if audit["orphan_claims"]:
        raise UnifiedSingleStageBlocked("Incomplete ledger after fake execution")
    return {
        "version": VERSION,
        "status": "FAKE_STAGE_RECORDED_NO_API",
        "stage_id": stage_id,
        "stage": stage,
        "record_status": persisted["status"],
        "record_sha256": persisted["record_sha256"],
        "downstream_blocked": descendants,
        "simulated_model_invocations": simulated_invocations,
        "real_provider_requests": 0,
        "api_credentials_used": False,
        "release_sha256": ledger.release_sha,
        "source_commit": ledger.expected_commit,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "scientific_release_for_real_execution": False,
    }
