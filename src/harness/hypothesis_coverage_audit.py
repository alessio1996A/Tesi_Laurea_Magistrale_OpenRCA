"""Audit offline della copertura investigativa dei candidati A1-R8.

Questo controllo NON individua la root cause, NON modifica la diagnosi,
NON giudica la causalita' e NON richiede ground truth o chiamate LLM.

Verifica esclusivamente:
- quali candidati osservativi sono ripresi nella risposta finale;
- quali componenti hanno ricevuto chiamate MIRATE ai tool di metriche;
- quali osservazioni non sono documentate dalla traiettoria dei tool.

Una chiamata senza cmdb_id o a log/tracce NON dimostra che sia stata
eseguita una verifica diretta del KPI del candidato. L'assenza di una
chiamata mirata NON implica che il modello non abbia visto l'evidence
report inserito nel prompt.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from harness.rule_batch import RULE_SPECS
from output.openrca_contract import Diagnosis


_RULE_CATALOG = {
    rule_id: (scope, category)
    for rule_id, scope, _, _, category in RULE_SPECS
}
_SCOPE_TO_TOOL = {
    "node": "tool_get_node_metrics",
    "container": "tool_get_container_metrics",
}


def _qualifying_aliases(candidates: list[dict]) -> Counter:
    """Contare gli host per suffisso, evitando deduzioni su alias ambigui."""
    suffix_hosts = {}
    for item in candidates:
        comp = item["componente_telemetria"]
        if "." in comp:
            host, suffix = comp.split(".", 1)
            suffix_hosts.setdefault(suffix, set()).add(host)
    return Counter({suffix: len(hosts) for suffix, hosts in suffix_hosts.items()})


def _matches_component(predicted: str, observed: str, aliases: Counter) -> bool:
    if predicted == observed:
        return True
    if "." not in observed:
        return False
    _, suffix = observed.split(".", 1)
    return predicted == suffix and aliases[suffix] == 1


def verifica_copertura_ipotesi(
    diagnosis: Diagnosis,
    evidence_report: dict,
    tool_trajectory: list[dict[str, Any]],
) -> dict[str, Any]:
    """Restituisce un audit descrittivo, deterministico e senza effetti."""
    if not isinstance(diagnosis, Diagnosis):
        raise TypeError("Diagnosis richiesta")
    if not isinstance(evidence_report, dict):
        raise TypeError("Report evidenze richiesto")
    if evidence_report.get("versione") != "unified_evidence_v2":
        raise ValueError("Versione report evidenze non supportata")
    rules = evidence_report.get("regole_diagnostiche_v0")
    if not isinstance(rules, dict) or rules.get("versione") != "rule_based_A1_R_v1":
        raise ValueError("Sezione regole A1-R8 mancante o incoerente")
    if not isinstance(tool_trajectory, list):
        raise TypeError("La traiettoria dei tool deve essere una lista")

    candidates = rules.get("candidati_riportati")
    count = rules.get("totale_candidati")
    omitted = rules.get("candidati_omessi_per_budget")
    if (
        not isinstance(candidates, list)
        or type(count) is not int or count < 0
        or type(omitted) is not int or omitted < 0
        or len(candidates) + omitted != count
    ):
        raise ValueError("Conteggi candidati e budget incoerenti")

    for i, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise ValueError(f"Candidato {i} non valido")
        rule_id = candidate.get("regola")
        component = candidate.get("componente_telemetria")
        category = candidate.get("classe_candidata")
        if (
            rule_id not in _RULE_CATALOG
            or not isinstance(component, str) or not component.strip()
            or category != _RULE_CATALOG[rule_id][1]
        ):
            raise ValueError(f"Candidato {i}: identita' o classe incoerente")

    aliases = _qualifying_aliases(candidates)
    metric_calls = []
    metric_calls_without_id = []
    for i, event in enumerate(tool_trajectory):
        if not isinstance(event, dict):
            raise ValueError(f"Evento traiettoria {i} non valido")
        if event.get("tipo") != "tool_call":
            continue
        tool_name = event.get("nome")
        if tool_name not in _SCOPE_TO_TOOL.values():
            continue
        args = event.get("parametri")
        if not isinstance(args, dict):
            raise ValueError(f"Tool call {i}: parametri non validi")
        cmdb_id = args.get("cmdb_id")
        info = {
            "indice_traiettoria": i,
            "tool": tool_name,
            "cmdb_id": cmdb_id,
        }
        if isinstance(cmdb_id, str) and cmdb_id.strip():
            metric_calls.append(info)
        else:
            metric_calls_without_id.append(info)

    output = []
    for i, candidate in enumerate(candidates):
        rule_id = candidate["regola"]
        scope, canonical_reason = _RULE_CATALOG[rule_id]
        component = candidate["componente_telemetria"]
        same_component = [
            j for j, fault in enumerate(diagnosis.root_causes, 1)
            if _matches_component(fault.component, component, aliases)
        ]
        same_canonical_hypothesis = [
            j for j in same_component
            if (
                " ".join(diagnosis.root_causes[j - 1].reason.split()).casefold()
                == canonical_reason.casefold()
            )
        ]
        expected_tool = _SCOPE_TO_TOOL[scope]
        targeted = [
            m["indice_traiettoria"] for m in metric_calls
            if m["tool"] == expected_tool and m["cmdb_id"] == component
        ]
        generic = [
            m["indice_traiettoria"] for m in metric_calls_without_id
            if m["tool"] == expected_tool
        ]

        if same_canonical_hypothesis:
            diagnosis_status = "componente_e_classe_canonica_ripresi"
        elif same_component:
            diagnosis_status = "componente_ripreso_classe_non_canonica"
        else:
            diagnosis_status = "candidato_non_ripreso_nella_diagnosi"

        output.append({
            "regola": rule_id,
            "componente_telemetria": component,
            "classe_candidata": canonical_reason,
            "provenienza": f"regole_diagnostiche_v0.candidati_riportati[{i}]",
            "stato_nella_diagnosi": diagnosis_status,
            "indici_guasti_stesso_componente": same_component,
            "indici_guasti_stessa_ipotesi_canonica": same_canonical_hypothesis,
            "tool_metriche_atteso": expected_tool,
            "chiamate_metriche_mirate": targeted,
            "chiamate_metriche_generiche_stesso_livello": generic,
            "indagine_mirata_documentata": bool(targeted),
            "verifica_causale": False,
        })

    return {
        "versione": "hypothesis_investigation_coverage_v1",
        "candidati_riportati": len(candidates),
        "candidati_omessi_per_budget": omitted,
        "copertura_lista_completa": omitted == 0,
        "candidati_ripresi_stessa_classe": sum(
            bool(x["indici_guasti_stessa_ipotesi_canonica"]) for x in output
        ),
        "candidati_con_metriche_mirate": sum(
            x["indagine_mirata_documentata"] for x in output
        ),
        "candidati": output,
        "ground_truth_consultata": False,
        "causa_verificata": False,
        "nota": (
            "Audit della traccia, non valutazione causale. "
            "Una chiamata ai tool non garantisce risultati utili. "
            "Assenza di chiamate mirate non equivale ad assenza "
            "di evidenze nel prompt."
        ),
    }
