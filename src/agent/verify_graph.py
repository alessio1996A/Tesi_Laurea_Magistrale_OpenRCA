"""Variante LangGraph A1_VERIFY: esplorazione, verifiche mirate, finale.

Architettura separata dal motore storico A0/A1/A1_V2. I candidati del
report A1-R8 sono SOLO segnali osservativi e non etichette o cause certe.
I controlli del planner sono tool call deterministicamente costruite;
NON sono chiamate LLM. Nessuna ground truth o scoring viene letta.

Budget totale di round con tool: max_tool_rounds. Il massimo
max_verification_checks viene riservato dal budget all'inizio:
max_exploration_rounds = max_tool_rounds - max_verification_checks.
Ogni verifica richiede un round di tool; la finalizzazione usa una
sola chiamata LLM, senza nuovi tool. Nessun retry implicito.

Flusso del grafo (nodi in ordine di esecuzione):
  1. agente   : l'LLM esplora liberamente con i tool, fino al budget esplorativo;
  2. tools    : esegue le chiamate (ToolNode di LangGraph) e torna all'agente;
  3. planner  : quando l'esplorazione finisce, propone verifiche mirate (nessuna chiamata LLM);
  4. verifica : trasforma ogni proposta in una tool call sintetica; i risultati passano da `tools`;
  5. finale   : una sola chiamata LLM, senza tool, produce la diagnosi in JSON OpenRCA.

Contenuto del modulo: lo stato del grafo (`VerifyRCAState`), la costruzione del grafo
(`crea_grafo_rca_verify`) e l'esecuzione con raccolta di metriche e traiettoria
(`esegui_grafo_rca_verify`).
"""
from __future__ import annotations

import json
import time
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from agent.graph_engine import (
    _contesto_finale_testuale,
    _messaggio_senza_tool,
    testo_messaggio,
)
from harness.investigation_planner import pianifica_verifiche_mirate


class VerifyRCAState(TypedDict, total=False):
    """Stato a fasi: esplorazione LLM, pianificazione, verifiche e finale.

    total=False rende facoltative le chiavi del TypedDict nel type checking;
    lo stato iniziale viene comunque costruito esplicitamente dal runner.
    Nessun checkpointer persistente e' collegato al grafo.

    Campi:
      messages             conversazione; `add_messages` accoda i nuovi messaggi invece di sostituirli.
      phase                fase corrente: exploring, planning, verifying, ready_to_finalize, done.
      exploration_rounds   round di tool già usati dall'LLM nell'esplorazione.
      verification_rounds  round di tool usati dalle verifiche del planner.
      verification_plan    verifiche proposte dal planner.
      verification_cursor  posizione della prossima verifica da eseguire nel piano.
      verification_status  stato restituito dal planner ("proposte_non_eseguite").
      finalization_error   errore della chiamata finale (None se è andata bene).
    """
    messages: Annotated[list[BaseMessage], add_messages]
    phase: str
    exploration_rounds: int
    verification_rounds: int
    verification_plan: list[dict]
    verification_cursor: int
    verification_status: str
    finalization_error: str | None


def _traccia_chiamate(messages: list[BaseMessage]) -> list[dict]:
    """Ricostruisce le chiamate LLM eseguite prima delle verifiche pianificate.

    Il planner usa questo storico per evitare di ripetere interrogazioni
    gia' sufficientemente mirate sulla stessa ipotesi.

    Argomenti:
      messages  conversazione finora (messaggi dell'utente, dell'LLM e dei tool).

    Restituisce una lista di eventi `tool_call` (nome e parametri), nello stesso formato della traiettoria
    che il planner si aspetta.
    """
    trajectory = []
    for msg in messages:
        # Le chiamate ai tool sono nei messaggi dell'LLM (AIMessage): gli altri messaggi si ignorano.
        if not isinstance(msg, AIMessage):
            continue
        for call in getattr(msg, "tool_calls", None) or []:
            trajectory.append({
                "tipo": "tool_call",
                "nome": call.get("name"),
                "parametri": call.get("args", {}),
            })
    return trajectory


def crea_grafo_rca_verify(
    llm,
    tools,
    system_prompt: str,
    max_tool_rounds: int,
    max_verification_checks: int,
    evidence_report: dict,
    start_unix: int,
    end_unix: int,
    structural_context: dict | None = None,
):
    """Crea una variante chiusa, isolata e provider-agnostic.

    I tool devono avere i nomi previsti dalla factory OpenRCA; il
    planner non puo' richiamare strumenti estranei all'allowlist.

    Argomenti:
      llm                      modello di linguaggio (deve supportare `bind_tools`).
      tools                    tool dell'agente; devono comprendere i due tool di metriche.
      system_prompt            prompt di sistema (non vuoto).
      max_tool_rounds          budget totale di round con tool (intero >= 1).
      max_verification_checks  quota di round riservata alle verifiche del planner (0 <= q < max_tool_rounds).
      evidence_report          report A1 con le evidenze e i candidati delle regole.
      start_unix, end_unix     finestra del caso, in secondi unix (start < end).
      structural_context       contesto strutturale-temporale opzionale ("structural_temporal_context_v1").

    Restituisce il grafo LangGraph compilato, pronto per essere eseguito da `esegui_grafo_rca_verify`.
    """
    # --- Controllo degli argomenti: ogni condizione non rispettata interrompe subito la costruzione.
    if type(max_tool_rounds) is not int or max_tool_rounds < 1:
        raise ValueError("Budget round non valido")
    if (type(max_verification_checks) is not int
            or not 0 <= max_verification_checks < max_tool_rounds):
        raise ValueError("Riservare almeno un round esplorativo")
    if not isinstance(system_prompt, str) or not system_prompt.strip():
        raise ValueError("Prompt di sistema mancante")
    if not tools:
        raise ValueError("Tool mancanti")
    if (type(start_unix) is not int or type(end_unix) is not int
            or start_unix >= end_unix):
        raise ValueError("Finestra caso non valida")
    if not isinstance(evidence_report, dict):
        raise TypeError("Report A1 richiesto")

    # Nomi dei tool: devono essere distinti e comprendere i due tool di metriche, gli unici che il planner
    # può richiamare (`required`).
    tool_names = {tool.name for tool in tools}
    if len(tool_names) != len(tools):
        raise ValueError("Nomi dei tool duplicati")
    required = {"tool_get_node_metrics", "tool_get_container_metrics"}
    if not required.issubset(tool_names):
        raise ValueError("Tool metriche obbligatori mancanti")

    # Dei round totali, una quota e' riservata alle verifiche mirate.
    # Con budget 6 e max_verification_checks=2: 4 round esplorativi.
    # Il contesto strutturale e' opzionale e non altera la policy del planner.
    if structural_context is not None and (
        not isinstance(structural_context, dict)
        or structural_context.get("versione") != "structural_temporal_context_v1"
        or structural_context.get("causa_verificata") is not False
        or structural_context.get("propagazione_verificata") is not False
    ):
        raise ValueError("Contesto strutturale non valido")
    # Il contesto, se presente, viene serializzato una sola volta (chiavi ordinate: testo riproducibile)
    # e aggiunto al contesto della chiamata finale.
    structural_context_text = (
        json.dumps(structural_context, sort_keys=True, ensure_ascii=False, allow_nan=False)
        if structural_context is not None else None
    )
    # Round disponibili per l'esplorazione dell'LLM e modello con i tool collegati.
    exploration_budget = max_tool_rounds - max_verification_checks
    llm_with_tools = llm.bind_tools(tools)

    # Fase 1: l'LLM sceglie liberamente i tool fino al budget esplorativo.
    def agente(state: VerifyRCAState):
        """Nodo dell'LLM: chiede nuovi tool finché c'è budget, poi passa al planner."""
        rounds = state.get("exploration_rounds", 0)
        # Budget esplorativo esaurito: nessuna nuova chiamata LLM, si passa alla pianificazione.
        if rounds >= exploration_budget:
            return {"phase": "planning"}

        reply = llm_with_tools.invoke(
            [SystemMessage(content=system_prompt)] + state["messages"]
        )
        # Se la risposta contiene chiamate ai tool si resta in esplorazione (e si conta un round);
        # se non ne contiene, l'LLM ha finito di esplorare e si passa al planner.
        calls = getattr(reply, "tool_calls", None) or []
        return {
            "messages": [reply],
            "phase": "exploring" if calls else "planning",
            "exploration_rounds": rounds + (1 if calls else 0),
        }

    def route_agente(state: VerifyRCAState):
        """Dopo l'agente: se ha chiesto tool si va a `tools`, altrimenti al `planner`."""
        return "tools" if state.get("phase") == "exploring" else "planner"

    # Fase 2: il planner usa SOLO evidenze e traiettoria gia' osservate.
    # Le sue proposte non sono prove causali ne' chiamate all'LLM.
    def planner(state: VerifyRCAState):
        """Nodo del planner: costruisce il piano delle verifiche mirate (nessuna chiamata LLM)."""
        exploration_rounds = state.get("exploration_rounds", 0)
        # Round ancora disponibili: il piano non può superarli.
        available = max_tool_rounds - exploration_rounds
        report = pianifica_verifiche_mirate(
            evidence_report,
            _traccia_chiamate(state["messages"]),
            start_unix=start_unix,
            end_unix=end_unix,
            max_checks=max_verification_checks,
            remaining_rounds=available,
        )
        return {
            "phase": "verifying",
            "verification_plan": report["verifiche_proposte"],
            "verification_cursor": 0,
            "verification_rounds": 0,
            "verification_status": report["stato"],
        }

    # Fase 3: il planner prepara le richieste; ToolNode esegue i controlli.
    # Ogni verifica consuma un round, ma NON una nuova decisione LLM.
    # Le tool_call sintetiche servono a riutilizzare la stessa ToolNode.
    def verifica(state: VerifyRCAState):
        """Nodo delle verifiche: prepara la prossima richiesta del piano come tool call sintetica."""
        plan = state.get("verification_plan", [])
        cursor = state.get("verification_cursor", 0)
        # Piano concluso: si può passare alla risposta finale.
        if cursor >= len(plan):
            return {"phase": "ready_to_finalize"}

        item = plan[cursor]
        name = item["tool"]
        # Controlli di sicurezza: tool consentito e argomenti coerenti con la finestra del caso.
        if name not in required or name not in tool_names:
            raise ValueError("Planner ha richiesto un tool non autorizzato")
        args = item["arguments"]
        if (args.get("start_unix") != start_unix or
                args.get("end_unix") != end_unix or
                args.get("cmdb_id") != item["component"]):
            raise ValueError("Il piano non rispetta la finestra del caso")

        # Messaggio sintetico per ToolNode: il chiamante sara' marcato
        # come planner, non come LLM, nel registro delle metriche.
        synthetic = AIMessage(content="", tool_calls=[{
            "name": name,
            "args": dict(args),
            "id": f"planner-check-{cursor}",
            "type": "tool_call",
        }])
        return {
            "messages": [synthetic],
            "phase": "verifying",
            "verification_cursor": cursor + 1,
            "verification_rounds": state.get("verification_rounds", 0) + 1,
        }

    def route_verifica(state: VerifyRCAState):
        """Dopo `verifica`: se c'è una richiesta da eseguire si va a `tools`, altrimenti al `finale`."""
        return (
            "tools" if state.get("phase") == "verifying"
            else "finale"
        )

    def route_tools(state: VerifyRCAState):
        """Dopo `tools`: durante le verifiche si torna a `verifica`, altrimenti all'`agente`."""
        return (
            "verifica" if state.get("phase") == "verifying"
            else "agente"
        )

    # Fase 4: una sola chiamata LLM per la diagnosi definitiva.
    # L'output non puo' attivare nuovi tool o correggere la ground truth.
    def finale(state: VerifyRCAState):
        """Nodo finale: una sola chiamata LLM, senza tool, per la diagnosi definitiva."""
        # Contesto della chiamata finale: riassunto testuale della conversazione, più il contesto
        # strutturale se presente.
        context = _contesto_finale_testuale(state["messages"])
        if structural_context_text is not None:
            context += "\n\nSTRUCTURAL_CONTEXT_JSON:\n" + structural_context_text
        # Regola aggiunta al prompt di sistema: i controlli sono osservazioni, non cause confermate.
        policy = (
            "\n\nINVESTIGATION VERIFICATION POLICY:\n"
            "Deterministic telemetry checks, when present, are only "
            "observations and NOT confirmed root causes. Compare alternative "
            "hypotheses, component scope and chronology; do not infer "
            "causality from temporal order. A missing or inconclusive "
            "signal does not prove that a fault is absent. "
            "Use only available evidence and the original incident instruction. "
            "Return ONLY valid OpenRCA JSON. No tools are available."
        )
        # Si usa `llm` e non `llm_with_tools`: in questa fase nessun tool è disponibile.
        response = llm.invoke([
            SystemMessage(content=system_prompt + policy),
            HumanMessage(content=context),
        ])

        # Errore 1: il modello chiede comunque dei tool (validi o non validi): la risposta non è utilizzabile.
        if (
            getattr(response, "tool_calls", None)
            or getattr(response, "invalid_tool_calls", None)
        ):
            return {
                "messages": [_messaggio_senza_tool(response)],
                "phase": "done",
                "finalization_error": (
                    "VerifyFinalizationToolCall: il modello ha richiesto "
                    "tool durante la finalizzazione senza strumenti."
                ),
            }
        # Errore 2: risposta senza testo.
        if not testo_messaggio(
            getattr(response, "content", None), solo_testo=True
        ).strip():
            return {
                "messages": [_messaggio_senza_tool(response)],
                "phase": "done",
                "finalization_error": "VerifyFinalizationEmpty: risposta vuota.",
            }
        return {
            "messages": [response],
            "phase": "done",
            "finalization_error": None,
        }

    # Costruzione del grafo: nodi, poi archi. Gli archi condizionali scelgono il nodo successivo con le
    # funzioni `route_*` sopra. Ciclo di esplorazione: agente <-> tools; ciclo di verifica: verifica <-> tools.
    builder = StateGraph(VerifyRCAState)
    builder.add_node("agente", agente)
    builder.add_node("tools", ToolNode(tools))
    builder.add_node("planner", planner)
    builder.add_node("verifica", verifica)
    builder.add_node("finale", finale)
    builder.add_edge(START, "agente")
    builder.add_conditional_edges(
        "agente", route_agente, {
            "tools": "tools", "planner": "planner",
        }
    )
    builder.add_conditional_edges(
        "tools", route_tools, {
            "agente": "agente", "verifica": "verifica",
        }
    )
    builder.add_edge("planner", "verifica")
    builder.add_conditional_edges(
        "verifica", route_verifica, {
            "tools": "tools", "finale": "finale",
        }
    )
    builder.add_edge("finale", END)
    return builder.compile()


def esegui_grafo_rca_verify(
    grafo,
    richiesta: str,
    recursion_limit: int = 30,
    verbose: bool = True,
) -> dict:
    """Esegue il grafo e separa le chiamate LLM dalle chiamate del planner.

    Argomenti:
      grafo            grafo compilato da `crea_grafo_rca_verify`.
      richiesta        testo dell'incidente da analizzare (non vuoto).
      recursion_limit  numero massimo di passi del grafo prima che LangGraph si fermi.
      verbose          se True stampa a video le chiamate ai tool e i risultati.

    Restituisce un dizionario con: risposta grezza dell'LLM (None se c'è stato un errore), metriche
    (chiamate LLM, tool, token, durata), traiettoria dei tool con l'origine di ciascuna chiamata
    ("llm" o "planner"), eventuale errore e il riepilogo delle verifiche.
    """
    if not isinstance(richiesta, str) or not richiesta.strip():
        raise ValueError("Richiesta mancante")

    # Stato di partenza: solo la richiesta; contatori a zero e piano vuoto.
    initial_state: VerifyRCAState = {
        "messages": [HumanMessage(content=richiesta)],
        "phase": "exploring",
        "exploration_rounds": 0,
        "verification_rounds": 0,
        "verification_plan": [],
        "verification_cursor": 0,
        "verification_status": "non_eseguito",
        "finalization_error": None,
    }

    # Metriche raccolte durante l'esecuzione. `token_usage_complete` diventa False se anche una sola risposta
    # non riporta i token: così non si dichiara mai un conteggio completo quando non lo è.
    metrics = {
        "llm_calls": 0,
        "tool_calls": 0,
        "tool_rounds": 0,
        "exploration_tool_rounds": 0,
        "verification_tool_rounds": 0,
        "verification_tool_calls": 0,
        "verification_tool_results": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "token_usage_complete": True,
    }
    # `trajectory`: elenco ordinato di chiamate e risultati dei tool. `origins`: associa ogni id di chiamata
    # a chi l'ha prodotta ("llm" o "planner"), per etichettare poi i risultati.
    trajectory = []
    origins = {}
    verification_plan = []
    verification_status = "non_eseguito"
    response_text = None
    error = None
    started = time.perf_counter()

    try:
        # Si segue il grafo passo per passo: ogni evento contiene gli aggiornamenti prodotti da un nodo.
        for event in grafo.stream(
            initial_state,
            config={"recursion_limit": recursion_limit},
            stream_mode="updates",
        ):
            for node, update in event.items():
                # Il planner pubblica il piano delle verifiche e il suo stato.
                if node == "planner":
                    verification_plan = list(update.get("verification_plan", []))
                    verification_status = update.get("verification_status", "")
                # Nodi che producono chiamate ai tool: `agente` (scelte dell'LLM) e `verifica` (del planner).
                # I round si registrano con il massimo osservato, perché ogni aggiornamento riporta il totale.
                if node in ("agente", "verifica"):
                    metrics["exploration_tool_rounds"] = max(
                        metrics["exploration_tool_rounds"],
                        int(update.get("exploration_rounds", 0)),
                    )
                    metrics["verification_tool_rounds"] = max(
                        metrics["verification_tool_rounds"],
                        int(update.get("verification_rounds", 0)),
                    )
                    for message in update.get("messages", []):
                        # Solo le risposte dell'LLM consumano token: quelle del planner sono sintetiche.
                        if node == "agente":
                            metrics["llm_calls"] += 1
                            usage = getattr(message, "usage_metadata", None)
                            if not isinstance(usage, dict) or not all(
                                isinstance(usage.get(key), int)
                                for key in (
                                    "input_tokens", "output_tokens", "total_tokens"
                                )
                            ):
                                metrics["token_usage_complete"] = False
                            else:
                                for key in (
                                    "input_tokens", "output_tokens", "total_tokens"
                                ):
                                    metrics[key] += usage[key]

                        # Conteggio delle chiamate ai tool, distinguendo quelle delle verifiche del planner.
                        calls = getattr(message, "tool_calls", None) or []
                        metrics["tool_calls"] += len(calls)
                        if node == "verifica":
                            metrics["verification_tool_calls"] += len(calls)

                        # Ogni chiamata entra nella traiettoria con la sua origine.
                        for call in calls:
                            call_id = str(call.get("id") or "")
                            origin = "planner" if node == "verifica" else "llm"
                            if call_id:
                                origins[call_id] = origin
                            trajectory.append({
                                "tipo": "tool_call",
                                "nome": call.get("name"),
                                "parametri": call.get("args", {}),
                                "origine": origin,
                                "tool_call_id": call_id or None,
                            })
                        if verbose and calls:
                            print(
                                "Tool", node, ":",
                                ", ".join(c.get("name", "?") for c in calls),
                            )

                # Risultati dei tool: l'origine si ricava dall'id della chiamata ("unknown" se non trovato).
                elif node == "tools":
                    for message in update.get("messages", []):
                        call_id = str(getattr(message, "tool_call_id", ""))
                        origin = origins.get(call_id, "unknown")
                        if origin == "planner":
                            metrics["verification_tool_results"] += 1
                        result_text = testo_messaggio(message.content)
                        trajectory.append({
                            "tipo": "tool_result",
                            "nome": message.name,
                            "risposta": result_text,
                            "origine": origin,
                            "tool_call_id": call_id or None,
                        })
                        if verbose:
                            print(
                                "Tool result", origin, message.name,
                                len(result_text), "characters",
                            )

                # Risposta finale: si contano token e chiamata LLM; il testo è accettato solo se non ci sono errori.
                elif node == "finale":
                    if update.get("finalization_error"):
                        error = update["finalization_error"]
                        response_text = None
                    for message in update.get("messages", []):
                        metrics["llm_calls"] += 1
                        usage = getattr(message, "usage_metadata", None)
                        if not isinstance(usage, dict) or not all(
                            isinstance(usage.get(key), int)
                            for key in (
                                "input_tokens", "output_tokens", "total_tokens"
                            )
                        ):
                            metrics["token_usage_complete"] = False
                        else:
                            for key in (
                                "input_tokens", "output_tokens", "total_tokens"
                            ):
                                metrics[key] += usage[key]
                        if error is None:
                            response_text = testo_messaggio(
                                getattr(message, "content", None),
                                solo_testo=True,
                            ) or None

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        response_text = None
        # Un'invocazione esterna incompleta può comunque aver generato un costo:
        # dopo un'eccezione non si dichiara mai un conteggio dei token completo.
        metrics["token_usage_complete"] = False
        if verbose:
            print("Errore variante verifica:", error)

    # Anche su eccezione conserviamo i round gia' osservati
    # dalla stream, invece di segnare impropriamente zero.
    metrics["tool_rounds"] = (
        metrics["exploration_tool_rounds"]
        + metrics["verification_tool_rounds"]
    )
    # Durata complessiva e risultato: la parte `verification` documenta cosa ha fatto il planner;
    # `causa_verificata` è sempre False perché i controlli sono osservazioni, non prove causali.
    metrics["duration_seconds"] = round(
        time.perf_counter() - started, 3
    )
    return {
        "raw_response": response_text,
        "metrics": metrics,
        "tool_trajectory": trajectory,
        "error": error,
        "verification": {
            "versione": "pre_finalization_verification_v1",
            "piano": verification_plan,
            "stato_piano": verification_status,
            "tool_chiamati_dal_planner": metrics["verification_tool_calls"],
            "risposte_tool_del_planner": metrics["verification_tool_results"],
            "causa_verificata": False,
            "nota": (
                "Controlli deterministici pre-finalizzazione: "
                "nessuna verifica causale garantita."
            ),
        },
    }
