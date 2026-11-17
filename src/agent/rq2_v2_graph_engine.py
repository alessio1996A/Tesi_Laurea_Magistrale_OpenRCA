"""Esecutore diagnostico sperimentale RQ2-V2: sola provenance dei tool.

Deriva ESCLUSIVAMENTE da esegui_grafo_rca del sorgente V1 congelato.
Mantiene invariati grafo, prompt, routing, budget, token e risposta finale.
Differenza intenzionale: registra il tool_call_id originale negli eventi
tool_call e tool_result, se disponibile. Non fabbrica ID mancanti.

Questa implementazione NON e' collegata a un dispatcher a pagamento.
NON autorizza API, scoring, test OOD o riuso di claim e artefatti V1.
Il codice V1 src/agent/graph_engine.py rimane inalterato.

Contiene una sola funzione, `esegui_grafo_rca_v2`: esegue il grafo A0/A1/A1_8R, raccoglie metriche
(chiamate LLM e tool, token, durata) e traiettoria dei tool, e restituisce l'esito.
"""
from __future__ import annotations

import time

from langchain_core.messages import HumanMessage

from agent.graph_engine import crea_grafo_rca, testo_messaggio


def esegui_grafo_rca_v2(
    grafo,
    richiesta: str,
    recursion_limit: int = 30,
    verbose: bool = True,
) -> dict:
    """Esegue il grafo mantenendo l'interfaccia e le metriche esistenti.

    I fallimenti dell'ultimo tentativo sono riportati in ``error``;
    ``raw_response`` rimane None, non viene generata alcuna diagnosi fittizia.
    Il preprocessing e` misurato separatamente da experiment_runner.py.

    Argomenti:
      grafo            grafo compilato (`crea_grafo_rca` di `agent/graph_engine.py`).
      richiesta        testo dell'incidente da analizzare.
      recursion_limit  numero massimo di passi del grafo prima che LangGraph si fermi.
      verbose          se True stampa a video i round e i risultati dei tool.

    Restituisce un dizionario con `raw_response`, `metrics`, `tool_trajectory` ed `error`. A differenza
    della versione V1, ogni evento della traiettoria riporta il `tool_call_id` originale, se disponibile.
    """

    # Stato di partenza: solo la richiesta; contatori a zero.
    stato_iniziale = {
        "messages": [HumanMessage(content=richiesta)],
        "tool_rounds": 0,
        "finalization_done": False,
        "finalization_error": None,
    }

    metriche = {
        "llm_calls": 0,
        "tool_calls": 0,
        "tool_rounds": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        # A0/A1/A1_8R: segnala dati token mancanti senza mascherarli.
        "token_usage_complete": True,
    }
    # `traiettoria`: elenco ordinato di chiamate e risultati dei tool.
    traiettoria = []
    risposta_finale = None
    errore = None
    inizio = time.perf_counter()

    try:
        # Si segue il grafo passo per passo: ogni evento contiene gli aggiornamenti prodotti da un nodo.
        for evento in grafo.stream(
            stato_iniziale,
            config={"recursion_limit": recursion_limit},
            stream_mode="updates",
        ):
            for nodo, aggiornamento in evento.items():
                # Nodo dell'LLM: errori di finalizzazione, round di tool, token e chiamate richieste.
                if nodo == "agente":
                    if aggiornamento.get("finalization_error"):
                        errore = aggiornamento["finalization_error"]
                        risposta_finale = None

                    # Round di tool: massimo osservato, perché ogni aggiornamento riporta il totale.
                    metriche["tool_rounds"] = max(
                        metriche["tool_rounds"],
                        int(aggiornamento.get("tool_rounds", 0)),
                    )

                    for msg in aggiornamento.get("messages", []):
                        metriche["llm_calls"] += 1
                        # Token: se mancano o non sono interi non negativi, il conteggio si segna
                        # come incompleto invece di nascondere il dato mancante.
                        original_usage = getattr(msg, "usage_metadata", None)
                        token_fields = (
                            "input_tokens", "output_tokens", "total_tokens"
                        )
                        if (
                            not isinstance(original_usage, dict)
                            or not all(
                                type(original_usage.get(key)) is int
                                and original_usage[key] >= 0
                                for key in token_fields
                            )
                        ):
                            metriche["token_usage_complete"] = False
                        usage = original_usage if isinstance(original_usage, dict) else {}
                        for chiave in token_fields:
                            metriche[chiave] += int(usage.get(chiave, 0) or 0)

                        # Chiamate ai tool richieste dall'LLM in questo messaggio.
                        calls = getattr(msg, "tool_calls", None) or []
                        metriche["tool_calls"] += len(calls)
                        for chiamata in calls:
                            # V2: non inventare ID. Conservare solo l'ID
                            # originale che LangChain ha associato alla call.
                            call_event = {
                                "tipo": "tool_call",
                                "nome": chiamata.get("name"),
                                "parametri": chiamata.get("args", {}),
                            }
                            call_id = chiamata.get("id")
                            if call_id is not None:
                                call_event["tool_call_id"] = call_id
                            traiettoria.append(call_event)

                        if verbose and calls:
                            print(
                                "Round", metriche["tool_rounds"], "- tool:",
                                ", ".join(c.get("name", "?") for c in calls),
                            )

                        # Un messaggio senza chiamate ai tool e senza errori è la risposta finale:
                        # se il testo è vuoto è un errore ("EmptyFinalResponse").
                        if not calls and not aggiornamento.get("finalization_error"):
                            contenuto = testo_messaggio(
                                getattr(msg, "content", None),
                                solo_testo=True,
                            )
                            if contenuto.strip():
                                risposta_finale = contenuto
                            else:
                                errore = "EmptyFinalResponse: risposta finale vuota."
                                risposta_finale = None

                # Nodo dei tool: ogni messaggio è il risultato di una chiamata.
                elif nodo == "tools":
                    for msg in aggiornamento.get("messages", []):
                        estratto = testo_messaggio(msg.content)
                        result_event = {
                            "tipo": "tool_result",
                            "nome": msg.name,
                            "risposta": estratto,
                        }
                        # V2: riusa l'ID nativo di ToolMessage. Se assente
                        # l'ambiguita' rimane visibile al validatore fail-closed.
                        call_id = getattr(msg, "tool_call_id", None)
                        if call_id is not None:
                            result_event["tool_call_id"] = call_id
                        traiettoria.append(result_event)
                        if verbose:
                            print(
                                "Risultato", msg.name, "-", len(estratto),
                                "caratteri",
                            )

    except Exception as exc:
        errore = f"{type(exc).__name__}: {exc}"
        risposta_finale = None
        # Un'invocazione incompleta puo' aver consumato token non osservati.
        metriche["token_usage_complete"] = False
        if verbose:
            print("ERRORE ESECUZIONE:", errore)

    # Durata complessiva (secondi) e risultato.
    metriche["duration_seconds"] = round(time.perf_counter() - inizio, 3)
    return {
        "raw_response": risposta_finale,
        "metrics": metriche,
        "tool_trajectory": traiettoria,
        "error": errore,
    }
