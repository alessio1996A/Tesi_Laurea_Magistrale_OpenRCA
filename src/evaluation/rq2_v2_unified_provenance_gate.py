"""Gate OFFLINE per la provenance D nella RQ2-V2 comune ai cinque agenti.

Valida identita' e trajectory *gia' raccolta*, non esegue il runner.
L'RCA ReAct A0/A1/A1_8R usa rq2_v2_graph_engine; Planning/PAVE
conservano gli ID nativi nel verify_graph gia' esistente.
Nessun GT, modello, tool, file, scorer o pseudocodice viene eseguito.
"""
from __future__ import annotations

from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_evidence_bundle import (
    EvidenceBundleError, build_evidence_bundle,
)
from evaluation.rq2_stage_binding import ALLOWED_TOOLS
from evaluation.rq2_v2_unified_discovery_plan import (
    DISCOVERY, ENGINES, HARNESSES, MODELS,
    MAX_TOOL_ROUNDS, RECURSION_LIMIT, VERSION,
)


class UnifiedRQ2ProvenanceError(ValueError):
    """Non dichiarare attribuzione delle evidenze se mancano identita'/ID."""


def audit_captured_v2_d(
    *, run: dict, case_id: str, model: str, harness: str,
) -> dict:
    """Controlla un risultato D ricevuto in memoria; NON crea una run.

    Controlla 5/3/4, la nomenclatura corrente, l'output task-aware, il budget
    e la presenza degli ID nativi per OGNI tool call/result. Il matcher
    gia' verificato costruisce il bundle solo se i risultati sono associati
    univocamente ai parametri originali. Il JSON finale puo' essere invalido:
    questo non viene qui trasformato in una diagnosi corretta.
    """
    if (
        type(case_id) is not str or case_id not in DISCOVERY
        or type(model) is not str or model not in MODELS
        or type(harness) is not str or harness not in HARNESSES
        or type(run) is not dict
    ):
        raise UnifiedRQ2ProvenanceError("Unknown or OOD-locked discovery identity")

    provider = CANDIDATE_MODELS[model]
    identity = {
        "case_id": case_id,
        "variant": harness,
        "variant_scheme": "current",
        "model": provider["model_id"],
        "model_provider": provider["provider"],
        "output_contract_mode": "v2_enforce",
        "max_tool_rounds": MAX_TOOL_ROUNDS,
    }
    if any(run.get(key) != expected for key, expected in identity.items()):
        raise UnifiedRQ2ProvenanceError("D run identity or contract mismatch")

    # In RQ1 il recursion_limit e' un valore di ExperimentConfig e non
    # necessariamente e' presente nell'output: non inventarlo nel report.
    trace = run.get("tool_trajectory")
    if type(trace) is not list:
        raise UnifiedRQ2ProvenanceError("Missing D tool trajectory")
    for event in trace:
        if (
            type(event) is not dict
            or event.get("tipo") not in ("tool_call", "tool_result")
            or type(event.get("tool_call_id")) is not str
            or not event["tool_call_id"].strip()
        ):
            raise UnifiedRQ2ProvenanceError(
                "V2 requires native tool_call_id on every tool call/result"
            )
    try:
        bundle = build_evidence_bundle(
            trace, allowed_tool_names=ALLOWED_TOOLS,
        )
    except EvidenceBundleError as exc:
        raise UnifiedRQ2ProvenanceError(
            "Unpaired/ambiguous/unsafe D evidence: " + str(exc)
        ) from exc

    items = bundle["evidence"]
    if len(trace) != 2 * len(items):
        raise UnifiedRQ2ProvenanceError("Incomplete D evidence trajectory")

    origins = sorted({e["call_origin"] for e in items})
    if harness in ("A1_8R_Planning", "A1_PAVE") and any(
        e["call_origin"] not in ("llm", "planner") for e in items
    ):
        raise UnifiedRQ2ProvenanceError(
            "Planning/PAVE evidence must have explicit llm/planner origin"
        )
    if harness not in ("A1_8R_Planning", "A1_PAVE") and any(
        e["call_origin"] == "planner" for e in items
    ):
        raise UnifiedRQ2ProvenanceError("Planner origin on ReAct harness")

    metrics = run.get("metrics")
    if type(metrics) is not dict:
        raise UnifiedRQ2ProvenanceError("Missing D execution metrics")
    if type(run.get("error")) not in (str, type(None)):
        raise UnifiedRQ2ProvenanceError("Malformed D execution error")
    token_flag = metrics.get("token_usage_complete")
    if type(token_flag) is not bool:
        raise UnifiedRQ2ProvenanceError("Token metering flag unavailable")

    return {
        "protocol": VERSION,
        "status": "OFFLINE_TRAJECTORY_AUDITED_NOT_SCIENTIFIC_FREEZE",
        "case_id": case_id,
        "logical_model": model,
        "harness": harness,
        "d_engine_required": ENGINES[harness],
        "capture_has_native_tool_call_ids": True,
        "tool_result_pairs_matched": len(items),
        "tool_call_origins": origins,
        "evidence_bundle_sha256": bundle["bundle_sha256"],
        "token_usage_complete": token_flag,
        "d_error_recorded": run["error"] is not None,
        "ground_truth_read": False,
        "reads_files": False,
        "model_api_calls": 0,
        "files_written": False,
        "scientific_release_frozen": False,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "note": (
            "Does not certify diagnostic correctness, physical metric "
            "semantics, provider parity, candidate rule quality, or DNS causality."
        ),
    }
