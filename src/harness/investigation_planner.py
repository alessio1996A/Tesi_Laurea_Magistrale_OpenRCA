"""Policy v0: *plan* bounded candidate investigations before final RCA.

No model inference, no tool execution, no ground truth, no prediction edits.
This planner is deliberately NOT connected to the historical LangGraph.
The evidence rules produce observable *hypotheses*, not ground truth.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from harness.rule_batch import RULE_SPECS

RULE_INFO = {
    rule_id: (scope, label)
    for rule_id, scope, _, _, label in RULE_SPECS
}
METRICS_TOOL = {
    "container": "tool_get_container_metrics",
    "node": "tool_get_node_metrics",
}


def _integer(value: Any) -> bool:
    return type(value) is int


def _checked_calls(
    trajectory: list[dict[str, Any]], start: int, end: int
) -> list[tuple[str, str, str | None, int, int]]:
    """Only valid scoped tool calls; broad calls do not imply targeted checks."""
    checked = []
    for index, item in enumerate(trajectory):
        if not isinstance(item, dict):
            raise ValueError(f"Evento traiettoria {index} malformato")
        if item.get("tipo") != "tool_call":
            continue
        tool_name = item.get("nome")
        if tool_name not in METRICS_TOOL.values():
            continue
        args = item.get("parametri")
        if not isinstance(args, dict):
            raise ValueError(f"Argomenti tool call {index} non validi")
        component = args.get("cmdb_id")
        begin = args.get("start_unix")
        finish = args.get("end_unix")
        if (
            not isinstance(component, str) or not component.strip()
            or not _integer(begin) or not _integer(finish)
            or not start <= begin < finish <= end
        ):
            continue
        kpi = args.get("kpi_name")
        if kpi is not None and not isinstance(kpi, str):
            continue
        checked.append((tool_name, component, kpi, begin, finish))
    return checked


def pianifica_verifiche_mirate(
    evidence_report: dict,
    tool_trajectory: list[dict[str, Any]],
    *,
    start_unix: int,
    end_unix: int,
    max_checks: int,
    remaining_rounds: int,
) -> dict[str, Any]:
    """Suggest up to min(max_checks, remaining_rounds) distinct tool calls.

    Selection is deterministic, round-robin between container and node,
    with at most one first-pass request per component before a second-pass
    request on the same component. This is a *coverage* policy only:
    no severity or causal ranking is inferred from candidate order.
    """
    if (
        not _integer(start_unix) or not _integer(end_unix)
        or start_unix >= end_unix
    ):
        raise ValueError("Finestra Unix non valida")
    if (
        not _integer(max_checks) or max_checks < 0
        or not _integer(remaining_rounds) or remaining_rounds < 0
    ):
        raise ValueError("Budget deve essere intero non negativo")
    if not isinstance(evidence_report, dict):
        raise TypeError("Report evidenze richiesto")
    if evidence_report.get("versione") != "unified_evidence_v2":
        raise ValueError("Versione report non supportata")

    case = evidence_report.get("caso")
    if not isinstance(case, dict) or (
        case.get("start_unix") != start_unix
        or case.get("end_unix") != end_unix
    ):
        raise ValueError("Finestra del caso non coerente")

    rules = evidence_report.get("regole_diagnostiche_v0")
    if not isinstance(rules, dict) or rules.get("versione") != "rule_based_A1_R_v1":
        raise ValueError("Report regole richiesto")
    rule_window = rules.get("finestra")
    if not isinstance(rule_window, dict) or (
        rule_window.get("start_unix") != start_unix
        or rule_window.get("end_unix") != end_unix
    ):
        raise ValueError("Finestra delle regole non coerente")
    candidates = rules.get("candidati_riportati")
    omitted = rules.get("candidati_omessi_per_budget")
    total = rules.get("totale_candidati")
    if (
        not isinstance(candidates, list)
        or not _integer(omitted) or omitted < 0
        or not _integer(total) or total != len(candidates) + omitted
    ):
        raise ValueError("Candidati e conteggi incoerenti")
    if not isinstance(tool_trajectory, list):
        raise TypeError("Traiettoria tool non valida")

    checked = _checked_calls(tool_trajectory, start_unix, end_unix)

    pending = []
    already_covered = []
    for index, item in enumerate(candidates):
        if not isinstance(item, dict):
            raise ValueError(f"Candidato {index} malformato")
        rule_id = item.get("regola")
        if rule_id not in RULE_INFO:
            raise ValueError(f"Candidato {index}: regola sconosciuta")
        scope, category = RULE_INFO[rule_id]
        component = item.get("componente_telemetria")
        first = item.get("timestamp_primo_segnale_unix")
        last = item.get("timestamp_ultimo_segnale_unix")
        if (
            item.get("classe_candidata") != category
            or not isinstance(component, str) or not component.strip()
            or not _integer(first) or not _integer(last)
            or not start_unix <= first <= last < end_unix
        ):
            raise ValueError(f"Candidato {index}: metadati incoerenti")

        evidence = item.get("evidenze") or {}
        if not isinstance(evidence, dict):
            raise ValueError(f"Candidato {index}: evidenze malformate")
        kpi = evidence.get("kpi_principale")
        if not isinstance(kpi, str) or not kpi.strip():
            kpi = None

        tool_name = METRICS_TOOL[scope]
        # An earlier call is considered sufficient for planning purposes
        # only if it covered the *candidate signal interval*. This does
        # NOT certify the result was useful or the cause is correct.
        was_queried = any(
            name == tool_name and comp == component
            and (prior_kpi is None or prior_kpi == kpi or kpi is None)
            and begin <= first and finish > last
            for name, comp, prior_kpi, begin, finish in checked
        )
        proposed = {
            "candidate_index": index,
            "rule_id": rule_id,
            "scope": scope,
            "component": component,
            "category": category,
            "tool": tool_name,
            "arguments": {
                "start_unix": start_unix,
                "end_unix": end_unix,
                "cmdb_id": component,
                **({"kpi_name": kpi} if kpi is not None else {}),
            },
            "signal_interval_unix": [first, last],
            "provenance": (
                f"regole_diagnostiche_v0.candidati_riportati[{index}]"
            ),
        }
        (already_covered if was_queried else pending).append(proposed)

    # Avoid duplicate calls that have identical target parameters:
    # these can correspond to distinct rule candidates, not extra tool work.
    unique = {}
    for candidate in sorted(
        pending,
        key=lambda p: (
            p["scope"], p["component"],
            p["arguments"].get("kpi_name", ""), p["rule_id"],
        ),
    ):
        key = (
            candidate["tool"],
            candidate["component"],
            candidate["arguments"].get("kpi_name"),
        )
        unique.setdefault(key, candidate)

    scope_queues = {"container": [], "node": []}
    for candidate in unique.values():
        scope_queues[candidate["scope"]].append(candidate)

    # Fairness across component identities within each scope:
    # one per component before revisiting that component with another KPI.
    queues = {}
    for scope, items in scope_queues.items():
        groups = defaultdict(list)
        for item in items:
            groups[item["component"]].append(item)
        fair = []
        while any(groups.values()):
            for component in sorted(groups):
                if groups[component]:
                    fair.append(groups[component].pop(0))
        queues[scope] = fair

    limit = min(max_checks, remaining_rounds)
    plan = []
    while len(plan) < limit and any(queues.values()):
        made_progress = False
        for scope in ("container", "node"):
            if len(plan) >= limit:
                break
            if queues[scope]:
                plan.append(queues[scope].pop(0))
                made_progress = True
        if not made_progress:
            break

    return {
        "versione": "investigation_planner_v0",
        "stato": "proposte_non_eseguite",
        "verifiche_proposte": plan,
        "budget_richiesto": max_checks,
        "round_disponibili": remaining_rounds,
        "budget_utilizzato_nel_piano": len(plan),
        "candidati_riportati": len(candidates),
        "candidati_omessi_per_budget": omitted,
        "candidati_con_chiamata_precedente": len(already_covered),
        "candidati_senza_chiamata_precedente": len(pending),
        "proposte_non_selezionate": (
            max(0, len(unique) - len(plan))
        ),
        "strumenti_chiamati": False,
        "llm_chiamato": False,
        "causa_verificata": False,
        "nota": (
            "Proposta di copertura investigativa, non ranking causale. "
            "Il budget e' un limite per future chiamate e non esegue tool. "
            "La mancata proposta non implica assenza di guasto."
        ),
    }
