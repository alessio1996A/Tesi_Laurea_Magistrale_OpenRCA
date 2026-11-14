"""G4G: orchestratore D→C→K con vero ledger scientifico, SOLO FAKE.

ATTENZIONE: non e' un dispatcher live. A differenza del journal G3B,
usa l'implementazione scientifica create-only G4F, ma esclusivamente con:
  - radice TemporaryDirectory priva di Market/data processed;
  - marker esplicito synthetic-only;
  - release fittizia con approval_reference SYNTHETIC_APPROVAL_NOT_REAL;
  - gateway OfflineFakeGateway, iniettato dalla suite di test.

Nessun provider SDK, credenziale, HTTP, dataset, GT o scoring importato.
Non esegue tool o modelli direttamente: attraversa funzioni FAKE
fornite dal test, con reali grafi LangGraph dietro il gateway finto.
Anche un PASS qui NON puo' abilitare la campagna pagata.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from evaluation.rq2_evidence_bundle import (
    build_evidence_bundle, evidence_ids,
)
from evaluation.rq2_output_contracts import (
    ContractError, validate_cause_probe, validate_candidate_rule,
)
from evaluation.rq2_probe_adapter import (
    prepare_candidate_rule, prepare_cause_probe,
)
from evaluation.rq2_stage_binding import ALLOWED_TOOLS
from evaluation.rq2_v2_unified_discovery_plan import (
    DISCOVERY, HARNESSES, MODELS, VERSION as PROTOCOL,
)
from evaluation.rq2_v2_unified_provenance_gate import (
    audit_captured_v2_d, UnifiedRQ2ProvenanceError,
)
from evaluation.rq2_v2_unified_scientific_ledger import (
    UnifiedScientificLedger, _read,
)
from evaluation.rq2_v2_unified_scientific_ledger_preflight import (
    RELEASE_FILE,
)

VERSION = "rq2_v2_unified_offline_fake_dispatcher_v0"
MARKER = ".rq2_v2_unified_fake_dispatch_only"
MARKER_BYTES = b"RQ2_V2_UNIFIED_FAKE_DISPATCH_NO_API\n"


class OfflineDispatchBlocked(ValueError):
    """Un fake gateway o uno stage non appartiene alla simulazione sicura."""


class SimulatedProviderFailure(RuntimeError):
    """Solo eccezioni intenzionalmente simulate; mai HTTP."""


@dataclass(frozen=True)
class OfflineStageResponse:
    output: object
    meter: dict


class OfflineFakeGateway:
    """Contratto da implementare SOLO in un test con LLMS e tool finti."""

    def run_d(self, *, case_id: str, model: str, harness: str) -> OfflineStageResponse:
        raise NotImplementedError

    def run_c(self, *, package: dict, model: str) -> OfflineStageResponse:
        raise NotImplementedError

    def run_k(self, *, package: dict, model: str) -> OfflineStageResponse:
        raise NotImplementedError


def _gate(ledger: UnifiedScientificLedger, gateway: OfflineFakeGateway) -> None:
    if type(ledger) is not UnifiedScientificLedger:
        raise OfflineDispatchBlocked("G4F scientific ledger required")
    if not isinstance(gateway, OfflineFakeGateway):
        raise OfflineDispatchBlocked("Only fake offline gateway permitted")
    root = ledger.data
    marker = root / MARKER
    if (
        marker.is_symlink()
        or not marker.is_file()
        or marker.read_bytes() != MARKER_BYTES
        or (root / "Market.zip").exists()
        or (root / "data/processed").exists()
        or (root / "data/rq2").exists()
        or (root / "data/results").exists()
    ):
        raise OfflineDispatchBlocked("Real dataset or missing fake-only marker")
    # Una release approvata da una persona reale non e' ammessa in
    # questa simulazione. Il test usa solo un placeholder dichiarato.
    release = _read(root / RELEASE_FILE)
    if (
        type(release) is not dict
        or release.get("approval_reference") != "SYNTHETIC_APPROVAL_NOT_REAL"
        or release.get("approved_total_usd_limit") != "0.20"
        or release.get("phase") != "discovery"
    ):
        raise OfflineDispatchBlocked("Not a fake simulation release")
    ledger.audit_restart()


def _sid(*, case_id: str, model: str, harness: str, stage: str) -> str:
    if (
        case_id not in DISCOVERY or model not in MODELS
        or harness not in HARNESSES or stage not in ("D", "C", "K")
    ):
        raise OfflineDispatchBlocked("Unknown/OOD identity")
    return f"{PROTOCOL}:{case_id}:{model}:{harness}:{stage}"


def _classify_d(run: dict, *, case_id: str, model: str, harness: str) -> str:
    if type(run) is not dict:
        raise OfflineDispatchBlocked("Fake D did not return a dict")
    if run.get("error") is not None:
        # Gli errori del runner verranno conservati come provider failure
        # solo nel driver reale; qui si rifiuta di inventare un receipt.
        raise OfflineDispatchBlocked("D returned execution error without receipt")
    try:
        audit_captured_v2_d(
            run=run, case_id=case_id, model=model, harness=harness,
        )
    except UnifiedRQ2ProvenanceError:
        return "INVALID_OUTPUT"
    if (
        run.get("json_status") == "valid_json"
        and type(run.get("output_contract_v2")) is dict
        and run["output_contract_v2"].get("valid") is True
    ):
        return "RECORDED_COMPLETE"
    return "INVALID_OUTPUT"


def _classify_ck(raw: str, *, stage: str, d_run: dict) -> str:
    bundle = build_evidence_bundle(
        d_run["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS,
    )
    validator = (
        validate_cause_probe if stage == "C" else validate_candidate_rule
    )
    try:
        validator(raw, allowed_evidence_ids=evidence_ids(bundle))
    except (ContractError, TypeError, ValueError):
        return "INVALID_OUTPUT"
    return "RECORDED_COMPLETE"


def _save_blocked(
    ledger: UnifiedScientificLedger, *,
    case_id: str, model: str, harness: str, stages: tuple[str, ...],
) -> None:
    for stage in stages:
        sid = _sid(case_id=case_id, model=model, harness=harness, stage=stage)
        ledger.record_stage(
            stage_id=sid,
            model_id=ledger.rows[sid]["model_id"],
            status="BLOCKED_DEPENDENCY", artifact={},
        )


def run_offline_fake_triplet(
    *, ledger: UnifiedScientificLedger, gateway: OfflineFakeGateway,
    case_id: str, model: str, harness: str, original_instruction: str,
) -> dict:
    """Una tripla D/C/K, effettivo claim/record G4F e grafi/provider FAKE."""
    _gate(ledger, gateway)
    if (
        type(original_instruction) is not str
        or not original_instruction.strip()
        or len(original_instruction) > 6000
    ):
        raise OfflineDispatchBlocked("Fake GT-free instruction required")
    ids = {
        stage: _sid(
            case_id=case_id, model=model, harness=harness, stage=stage,
        )
        for stage in ("D", "C", "K")
    }
    model_id = ledger.rows[ids["D"]]["model_id"]
    state = {}
    ledger.claim_stage(stage_id=ids["D"], model_id=model_id)
    try:
        d_result = gateway.run_d(
            case_id=case_id, model=model, harness=harness,
        )
    except SimulatedProviderFailure as exc:
        ledger.record_stage(
            stage_id=ids["D"], model_id=model_id, status="PROVIDER_ERROR",
            artifact={
                "provider_error": "SIMULATED_" + type(exc).__name__,
                "stage_meter": {
                    "schema": "rq2_v2_unified_stage_meter_v0",
                    "observed_model_requests": 0,
                    "input_tokens_observed": 0,
                    "output_tokens_observed": 0,
                    "usage_complete": False,
                    "cost_estimate_usd_not_invoice": "UNKNOWN",
                    "usd_hard_cap_guaranteed": False,
                },
            },
        )
        _save_blocked(
            ledger, case_id=case_id, model=model,
            harness=harness, stages=("C", "K"),
        )
        return {
            "stage_status": {
                "D": "PROVIDER_ERROR", "C": "BLOCKED_DEPENDENCY",
                "K": "BLOCKED_DEPENDENCY",
            },
            "can_execute_api": False, "real_model_requests": 0,
        }

    if type(d_result) is not OfflineStageResponse:
        raise OfflineDispatchBlocked("Malformed D fake gateway response")
    d_run = d_result.output
    d_status = _classify_d(
        d_run, case_id=case_id, model=model, harness=harness,
    )
    ledger.record_stage(
        stage_id=ids["D"], model_id=model_id, status=d_status,
        artifact={"diagnostic_run": d_run, "stage_meter": d_result.meter},
    )
    state["D"] = d_status
    if d_status != "RECORDED_COMPLETE":
        _save_blocked(
            ledger, case_id=case_id, model=model,
            harness=harness, stages=("C", "K"),
        )
        return {
            "stage_status": {**state, "C": "BLOCKED_DEPENDENCY",
                             "K": "BLOCKED_DEPENDENCY"},
            "can_execute_api": False, "real_model_requests": 0,
        }

    cause_package = prepare_cause_probe(
        original_instruction=original_instruction, diagnostic_run=d_run,
        allowed_tool_names=ALLOWED_TOOLS,
    )
    ledger.claim_stage(stage_id=ids["C"], model_id=model_id)
    try:
        c_result = gateway.run_c(package=cause_package, model=model)
    except SimulatedProviderFailure as exc:
        ledger.record_stage(
            stage_id=ids["C"], model_id=model_id, status="PROVIDER_ERROR",
            artifact={
                "provider_error": "SIMULATED_" + type(exc).__name__,
                "stage_meter": {
                    "schema": "rq2_v2_unified_stage_meter_v0",
                    "observed_model_requests": 0,
                    "input_tokens_observed": 0,
                    "output_tokens_observed": 0,
                    "usage_complete": False,
                    "cost_estimate_usd_not_invoice": "UNKNOWN",
                    "usd_hard_cap_guaranteed": False,
                },
            },
        )
        _save_blocked(
            ledger, case_id=case_id, model=model,
            harness=harness, stages=("K",),
        )
        return {
            "stage_status": {
                "D": d_status, "C": "PROVIDER_ERROR",
                "K": "BLOCKED_DEPENDENCY",
            },
            "can_execute_api": False, "real_model_requests": 0,
        }
    if type(c_result) is not OfflineStageResponse or type(c_result.output) is not str:
        raise OfflineDispatchBlocked("Malformed C fake gateway response")
    c_status = _classify_ck(c_result.output, stage="C", d_run=d_run)
    ledger.record_stage(
        stage_id=ids["C"], model_id=model_id, status=c_status,
        artifact={"raw_response": c_result.output, "stage_meter": c_result.meter},
    )
    state["C"] = c_status
    if c_status != "RECORDED_COMPLETE":
        _save_blocked(
            ledger, case_id=case_id, model=model, harness=harness, stages=("K",),
        )
        return {
            "stage_status": {**state, "K": "BLOCKED_DEPENDENCY"},
            "can_execute_api": False, "real_model_requests": 0,
        }

    rule_package = prepare_candidate_rule(
        original_instruction=original_instruction,
        diagnostic_run=d_run, cause_raw_json=c_result.output,
        phase="discovery", allowed_tool_names=ALLOWED_TOOLS,
    )
    ledger.claim_stage(stage_id=ids["K"], model_id=model_id)
    try:
        k_result = gateway.run_k(package=rule_package, model=model)
    except SimulatedProviderFailure as exc:
        ledger.record_stage(
            stage_id=ids["K"], model_id=model_id, status="PROVIDER_ERROR",
            artifact={
                "provider_error": "SIMULATED_" + type(exc).__name__,
                "stage_meter": {
                    "schema": "rq2_v2_unified_stage_meter_v0",
                    "observed_model_requests": 0,
                    "input_tokens_observed": 0,
                    "output_tokens_observed": 0,
                    "usage_complete": False,
                    "cost_estimate_usd_not_invoice": "UNKNOWN",
                    "usd_hard_cap_guaranteed": False,
                },
            },
        )
        state["K"] = "PROVIDER_ERROR"
    else:
        if type(k_result) is not OfflineStageResponse or type(k_result.output) is not str:
            raise OfflineDispatchBlocked("Malformed K fake gateway response")
        state["K"] = _classify_ck(k_result.output, stage="K", d_run=d_run)
        ledger.record_stage(
            stage_id=ids["K"], model_id=model_id, status=state["K"],
            artifact={"raw_response": k_result.output, "stage_meter": k_result.meter},
        )
    return {
        "stage_status": state,
        "can_execute_api": False,
        "real_model_requests": 0,
    }
