"""G4K — dispatcher RQ2-V2 unificato, SORGENTE LIVE MA BLOCCATA.

Per UN stage discovery: source G4H -> claim G4F -> RQ1 D / C/K
tool-free con RQ2-only factory -> normalizzazione G4J -> record G4F.
Al termine D/C invalido, figli BLOCKED_DEPENDENCY nel medesimo ledger.

Il codice reale NON e' abilitato: LIVE_API_ENABLED=False. I test
possono esercitare il percorso tramite mock in TemporaryDirectory e
patch in-process, MA questa non e' autorizzazione a chiamare un LLM.

Quando verra' autorizzato un pilot, richiede un nuovo commit,
source freeze COMPLETO, release external SHA, consenso allo stage e
controllo tariffa/lock su Google Drive. Non e' una protezione di spesa
hard-cap: il budget autorizzato e' un limite operativo, non di fattura.
Nessuna modifica a sorgenti o protocolli RQ1; nessun test OOD.
"""
from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import agent.graph_engine as react_graph
from agent.rq2_v2_graph_engine import esegui_grafo_rca_v2
from evaluation.experiment_config import ExperimentConfig
from evaluation.experiment_runner import run_experiment
from evaluation.rq2_model_factory import crea_modello_rq2
from evaluation.rq2_ck_provider_transport import _one_call as _call_ck_model
from evaluation.rq2_v2_unified_live_stage_preflight import preview_one_unified_stage
from evaluation.rq2_v2_unified_provider_result_adapter import (
    normalize_ck_call, normalize_d_run,
)
from evaluation.rq2_v2_unified_scientific_ledger import (
    UnifiedScientificLedger, _read,
)
from evaluation.rq2_v2_unified_scientific_ledger_preflight import RELEASE_FILE
from evaluation.rq2_v2_unified_single_stage_dispatcher import (
    _bound_probe, _blocked_descendants,
)

VERSION = "rq2_v2_unified_live_single_stage_dispatcher_blocked_v0"

# SCONNESSO IN PRODUZIONE. Necessario nuovo commit/freeze prima di
# sostituire False con True. NON modificare per i test: fare patch
# solo nel processo unittest con SDK e rete integralmente fake.
LIVE_API_ENABLED = False
FAKE_APPROVAL = "SYNTHETIC_APPROVAL_NOT_REAL"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SHA1 = re.compile(r"[0-9a-f]{40}\Z")


class RQ2V2LiveDispatchBlocked(RuntimeError):
    """Protezione prima di ogni claim o creazione SDK."""


def _eligibility(
    *, confirm_paid_api: bool, approved_stage_id: str,
    approved_release_sha256: str, expected_commit: str,
    external_approval_reference: str,
) -> None:
    if LIVE_API_ENABLED is not True:
        raise RQ2V2LiveDispatchBlocked("Live RQ2-V2 API permanently disabled")
    if confirm_paid_api is not True:
        raise RQ2V2LiveDispatchBlocked("Explicit per-stage paid approval required")
    if (
        type(approved_stage_id) is not str
        or not approved_stage_id.strip()
        or type(approved_release_sha256) is not str
        or not SHA256.fullmatch(approved_release_sha256)
        or type(expected_commit) is not str
        or not SHA1.fullmatch(expected_commit)
        or type(external_approval_reference) is not str
        or not external_approval_reference.strip()
        or external_approval_reference == FAKE_APPROVAL
    ):
        raise RQ2V2LiveDispatchBlocked("Independently pinned stage/release required")


def _prepare(
    *, ledger: UnifiedScientificLedger, stage_id: str,
    approved_stage_id: str, approved_release_sha256: str,
    expected_commit: str, external_approval_reference: str,
) -> dict:
    if stage_id != approved_stage_id:
        raise RQ2V2LiveDispatchBlocked("Stage not independently approved")
    release = _read(ledger.data / RELEASE_FILE)
    if (
        release is None
        or release.get("approval_reference") != external_approval_reference
        or release.get("approval_reference") == FAKE_APPROVAL
        or release.get("phase") != "discovery"
        or release.get("api_budget_approved") is not True
        or release.get("scientific_protocol_frozen") is not True
    ):
        raise RQ2V2LiveDispatchBlocked("Real non-synthetic release not authorized")
    preview = preview_one_unified_stage(
        data_dir=ledger.data, repo_dir=ledger.repo,
        stage_id=stage_id, expected_commit=expected_commit,
        approved_release_sha256=approved_release_sha256,
    )
    if (
        preview.get("status") != "STAGE_SOURCE_PREVIEW_READY_BUT_NO_API"
        or preview.get("stage_id") != stage_id
        or preview.get("source_commit") != expected_commit
        or preview.get("release_sha256") != approved_release_sha256
        or preview.get("can_create_scientific_claim") is not False
        or preview.get("can_execute_api") is not False
        or preview.get("can_run_ood_test") is not False
    ):
        raise RQ2V2LiveDispatchBlocked("Stage authority/provenance mismatch")
    return preview


def _rq1_config(preview: dict, *, repo_dir: Path, data_dir: Path):
    return ExperimentConfig(
        variant=preview["harness"],
        case_id=preview["case_id"],
        model_name=preview["model_id"],
        model_provider=preview["model_provider"],
        max_tool_rounds=preview["d_config"]["max_tool_rounds"],
        max_verification_checks=preview["d_config"]["max_verification_checks"],
        recursion_limit=preview["d_config"]["recursion_limit"],
        variant_scheme="current",
        output_contract_mode="v2_enforce",
        repo_dir=repo_dir, data_dir=data_dir,
    )


def _known_pre_request_error() -> dict:
    # SDK construction fallita PRIMA di model.invoke: nessuna API e'
    # stata deliberatamente invocata, costo comunque UNKNOWN.
    return {
        "status": "PROVIDER_ERROR",
        "artifact": {
            "provider_error": "SDK_CONSTRUCTION_ERROR",
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
    }


def run_one_claimed_unified_stage(
    *, data_dir: Path, repo_dir: Path, stage_id: str,
    expected_commit: str, approved_release_sha256: str,
    external_approval_reference: str,
    approved_stage_id: str,
    confirm_paid_api: bool = False,
) -> dict:
    """Live-capable entrypoint, **blocked until explicitly activated**.

    Il caller deve fornire pin EXTERNAL, legati a una reale approvazione
    del singolo pilot; il digest passato dal caller NON e' una firma.
    Non catturare e ritentare le eccezioni ambigue dopo il claim.
    """
    _eligibility(
        confirm_paid_api=confirm_paid_api,
        approved_stage_id=approved_stage_id,
        approved_release_sha256=approved_release_sha256,
        expected_commit=expected_commit,
        external_approval_reference=external_approval_reference,
    )
    if stage_id != approved_stage_id:
        raise RQ2V2LiveDispatchBlocked("Not the approved discovery stage")
    ledger = UnifiedScientificLedger(
        data_dir=data_dir, repo_dir=repo_dir,
        expected_commit=expected_commit,
        approved_release_sha256=approved_release_sha256,
    )
    preview = _prepare(
        ledger=ledger, stage_id=stage_id,
        approved_stage_id=approved_stage_id,
        approved_release_sha256=approved_release_sha256,
        expected_commit=expected_commit,
        external_approval_reference=external_approval_reference,
    )
    package = (
        _bound_probe(ledger=ledger, preview=preview)
        if preview["stage"] in ("C", "K") else None
    )
    # Tutti i controlli PRE-CLAIM completati. Nessuna seconda
    # invocazione automatica: dopo un claim orfano serve audit manuale.
    ledger.claim_stage(stage_id=stage_id, model_id=preview["model_id"])

    if preview["stage"] == "D":
        try:
            model = crea_modello_rq2(
                preview["model_provider"], preview["model_id"]
            )
        except Exception:
            receipt = _known_pre_request_error()
        else:
            config = _rq1_config(
                preview, repo_dir=ledger.repo, data_dir=ledger.data,
            )
            # Solo wrapper contestuale: il codice RQ1 rimane invariato.
            # Garantisce tool_call_id nativi nel D non-Planning/PAVE.
            with patch.object(
                react_graph, "esegui_grafo_rca", esegui_grafo_rca_v2,
            ):
                result = run_experiment(
                    config, llm=model, verbose=False, salva=False,
                )
            receipt = normalize_d_run(
                stage_id=stage_id,
                logical_model=preview["logical_model"], run=result,
            )
    else:
        messages = package["messages"]
        if (
            type(messages) is not list or len(messages) != 2
            or [m.get("role") for m in messages] != ["system", "user"]
            or any(type(m.get("content")) is not str for m in messages)
        ):
            raise RQ2V2LiveDispatchBlocked("Untrusted bound CK messages")
        from langchain_core.messages import HumanMessage, SystemMessage
        payload = [
            SystemMessage(content=messages[0]["content"]),
            HumanMessage(content=messages[1]["content"]),
        ]
        # Un solo invoke logico tramite il trasporto RQ2-only
        # gia' testato. Nessun bind_tools, scorer o GT.
        call = _call_ck_model(
            preview["model_provider"], preview["model_id"], payload,
        )
        d_id = stage_id.rsplit(":", 1)[0] + ":D"
        d = ledger.load_record(stage_id=d_id)
        if d is None or d["status"] != "RECORDED_COMPLETE":
            raise RQ2V2LiveDispatchBlocked("Immutable parent D missing after claim")
        receipt = normalize_ck_call(
            stage_id=stage_id,
            logical_model=preview["logical_model"],
            call=call, diagnostic_run=d["artifact"]["diagnostic_run"],
        )

    saved = ledger.record_stage(
        stage_id=stage_id,
        model_id=preview["model_id"],
        status=receipt["status"],
        artifact=receipt["artifact"],
    )
    blocked = (
        _blocked_descendants(ledger=ledger, preview=preview)
        if saved["status"] != "RECORDED_COMPLETE" else []
    )
    audited = ledger.audit_restart()
    if audited["orphan_claims"]:
        raise RQ2V2LiveDispatchBlocked("Unresolved claims require manual audit")

    return {
        "version": VERSION,
        "stage_id": stage_id,
        "status": saved["status"],
        "record_sha256": saved["record_sha256"],
        "downstream_blocked": blocked,
        "release_sha256": ledger.release_sha,
        "source_commit": ledger.expected_commit,
        "logical_model": preview["logical_model"],
        "model_id": preview["model_id"],
        "reported_usage": receipt["artifact"]["stage_meter"],
        "no_automatic_retry": True,
        "ood_test_locked": True,
        "usd_hard_cap_guaranteed": False,
        "api_spending_cap_enforced": False,
    }
