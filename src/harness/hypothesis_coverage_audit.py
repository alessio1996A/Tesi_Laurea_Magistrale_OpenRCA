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


# Per ogni regola: (livello di telemetria, nome della classe candidata), ricavati dal catalogo di `rule_batch`.
_RULE_CATALOG = {
    rule_id: (scope, category)
    for rule_id, scope, _, _, category in RULE_SPECS
}
# Il tool dell'agente che legge le metriche di ciascun livello: serve a riconoscere le chiamate mirate.
_SCOPE_TO_TOOL = {
    "node": "tool_get_node_metrics",
    "container": "tool_get_container_metrics",
}


def _qualifying_aliases(candidates: list[dict]) -> Counter:
    """Contare gli host per suffisso, evitando deduzioni su alias ambigui.

    Un componente "container" ha la forma `nodo.nome` (per esempio `node-5.frontend-0`). Per ogni suffisso
    (`frontend-0`) si conta su quanti nodi diversi compare tra i candidati: se è uno solo, il suffisso
    identifica senza ambiguità un container; se sono due o più, no.
    """
    # Per ogni suffisso, l'insieme dei nodi (host) in cui compare.
    suffix_hosts = {}
    for item in candidates:
        comp = item["componente_telemetria"]
        # I nodi puri (senza punto) non hanno un suffisso e si saltano.
        if "." in comp:
            host, suffix = comp.split(".", 1)
            suffix_hosts.setdefault(suffix, set()).add(host)
    return Counter({suffix: len(hosts) for suffix, hosts in suffix_hosts.items()})


def _matches_component(predicted: str, observed: str, aliases: Counter) -> bool:
    """True se il componente predetto dal modello corrisponde a quello osservato dalla regola.

    Corrispondono: (1) nomi identici; (2) il modello ha scritto solo il suffisso del container
    (`frontend-0`) e quel suffisso individua un unico container tra i candidati (`aliases[suffix] == 1`).
    Un nodo non è mai un alias di un suo container.
    """
    # Caso 1: stesso identico nome.
    if predicted == observed:
        return True
    # Caso 2: ammesso solo se il componente osservato è un container (ha il punto).
    if "." not in observed:
        return False
    _, suffix = observed.split(".", 1)
    return predicted == suffix and aliases[suffix] == 1


def verifica_copertura_ipotesi(
    diagnosis: Diagnosis,
    evidence_report: dict,
    tool_trajectory: list[dict[str, Any]],
) -> dict[str, Any]:
    """Restituisce un audit descrittivo, deterministico e senza effetti.

    Argomenti:
      diagnosis        diagnosi finale dell'agente (contiene l'elenco `root_causes`).
      evidence_report  report unificato delle evidenze ("unified_evidence_v2") con la sezione delle regole.
      tool_trajectory  chiamate ai tool fatte dall'agente, in ordine.

    Per ogni candidato delle regole riporta se la diagnosi lo riprende (stesso componente, stessa classe) e
    se l'agente ha chiamato il tool delle metriche proprio su quel componente. Non giudica se il candidato
    sia la vera causa.

    Passi: (1) validazione del report; (2) controllo dei candidati; (3) estrazione delle chiamate ai tool
    di metriche; (4) audit di ogni candidato; (5) riepilogo con i conteggi.
    """
    # --- 1. Validazione degli argomenti e del report delle regole.
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

    # I conteggi devono tornare: candidati riportati + omessi per budget = totale.
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

    # --- 2. Ogni candidato deve avere regola nota, componente non vuoto e classe coerente con la regola.
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

    # --- 3. Chiamate ai tool di metriche, divise in due gruppi: "mirate" (con un `cmdb_id` preciso) e
    # "generiche" (senza componente). Gli altri tipi di evento e gli altri tool non interessano.
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

    # --- 4. Audit di ogni candidato. Gli indici dei guasti della diagnosi partono da 1 (come li numera
    # chi legge la risposta); gli indici della traiettoria partono da 0.
    output = []
    for i, candidate in enumerate(candidates):
        rule_id = candidate["regola"]
        scope, canonical_reason = _RULE_CATALOG[rule_id]
        component = candidate["componente_telemetria"]
        # Guasti della diagnosi che indicano lo stesso componente del candidato.
        same_component = [
            j for j, fault in enumerate(diagnosis.root_causes, 1)
            if _matches_component(fault.component, component, aliases)
        ]
        # Tra questi, quelli la cui motivazione coincide con la classe del candidato (confronto
        # senza differenze di spazi e di maiuscole/minuscole).
        same_canonical_hypothesis = [
            j for j in same_component
            if (
                " ".join(diagnosis.root_causes[j - 1].reason.split()).casefold()
                == canonical_reason.casefold()
            )
        ]
        # Il tool da cui ci si aspetta un controllo dipende dal livello della regola (nodo o container).
        expected_tool = _SCOPE_TO_TOOL[scope]
        # Chiamate mirate: stesso tool e stesso componente. Generiche: stesso tool ma senza componente.
        targeted = [
            m["indice_traiettoria"] for m in metric_calls
            if m["tool"] == expected_tool and m["cmdb_id"] == component
        ]
        generic = [
            m["indice_traiettoria"] for m in metric_calls_without_id
            if m["tool"] == expected_tool
        ]

        # Stato del candidato nella diagnosi, dal più forte al più debole.
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

    # --- 5. Riepilogo: conteggi complessivi e dettaglio dei candidati. I campi `ground_truth_consultata` e
    # `causa_verificata` restano False: l'audit descrive la traccia, non valuta la causa.
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
