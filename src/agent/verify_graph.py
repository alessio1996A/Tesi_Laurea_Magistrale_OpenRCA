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
    messages: Annotated[list[BaseMessage], add_messages]
    phase: str
    exploration_rounds: int
    verification_rounds: int
    verification_plan: list[dict]
    verification_cursor: int
    verification_status: str
    finalization_error: str | None


def _traccia_chiamate(messages: list[BaseMessage]) -> list[dict]:
    """Ricostruzione del solo storico chiamate prima delle verifiche."""
    trajectory = []
    for msg in messages:
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
    """
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

    tool_names = {tool.name for tool in tools}
    if len(tool_names) != len(tools):
        raise ValueError("Nomi dei tool duplicati")
    required = {"tool_get_node_metrics", "tool_get_container_metrics"}
    if not required.issubset(tool_names):
        raise ValueError("Tool metriche obbligatori mancanti")

    # Dei round totali, una quota e' riservata alle verifiche mirate.
    # Con budget 6 e max_verification_checks=2: 4 round esplorativi.
    exploration_budget = max_tool_rounds - max_verification_checks
    llm_with_tools = llm.bind_tools(tools)

    # Fase 1: l'LLM sceglie liberamente i tool fino al budget esplorativo.
    def agente(state: VerifyRCAState):
        rounds = state.get("exploration_rounds", 0)
        if rounds >= exploration_budget:
            return {"phase": "planning"}

        reply = llm_with_tools.invoke(
            [SystemMessage(content=system_prompt)] + state["messages"]
        )
        calls = getattr(reply, "tool_calls", None) or []
        return {
            "messages": [reply],
            "phase": "exploring" if calls else "planning",
            "exploration_rounds": rounds + (1 if calls else 0),
        }

    def route_agente(state: VerifyRCAState):
        return "tools" if state.get("phase") == "exploring" else "planner"

    # Fase 2: il planner usa SOLO evidenze e traiettoria gia' osservate.
    # Le sue proposte non sono prove causali ne' chiamate all'LLM.
    def planner(state: VerifyRCAState):
        exploration_rounds = state.get("exploration_rounds", 0)
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

    # Fase 3: ToolNode esegue i controlli deterministici ammessi.
    # Ogni verifica occupa un round ma non richiede una scelta LLM.
    def verifica(state: VerifyRCAState):
        plan = state.get("verification_plan", [])
        cursor = state.get("verification_cursor", 0)
        if cursor >= len(plan):
            return {"phase": "ready_to_finalize"}

        item = plan[cursor]
        name = item["tool"]
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
        return (
            "tools" if state.get("phase") == "verifying"
            else "finale"
        )

    def route_tools(state: VerifyRCAState):
        return (
            "verifica" if state.get("phase") == "verifying"
            else "agente"
        )

    # Fase 4: una sola chiamata LLM per la diagnosi definitiva.
    # L'output non puo' attivare nuovi tool o correggere la ground truth.
    def finale(state: VerifyRCAState):
        context = _contesto_finale_testuale(state["messages"])
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
        response = llm.invoke([
            SystemMessage(content=system_prompt + policy),
            HumanMessage(content=context),
        ])

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
        if not testo_messaggio(getattr(response, "content", None)).strip():
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
    """Esegue il grafo e separa le chiamate LLM dalle chiamate del planner."""
    if not isinstance(richiesta, str) or not richiesta.strip():
        raise ValueError("Richiesta mancante")

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
    trajectory = []
    origins = {}
    verification_plan = []
    verification_status = "non_eseguito"
    response_text = None
    error = None
    started = time.perf_counter()

    try:
        for event in grafo.stream(
            initial_state,
            config={"recursion_limit": recursion_limit},
            stream_mode="updates",
        ):
            for node, update in event.items():
                if node == "planner":
                    verification_plan = list(update.get("verification_plan", []))
                    verification_status = update.get("verification_status", "")
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

                        calls = getattr(message, "tool_calls", None) or []
                        metrics["tool_calls"] += len(calls)
                        if node == "verifica":
                            metrics["verification_tool_calls"] += len(calls)

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
                                getattr(message, "content", None)
                            ) or None

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        response_text = None
        # Any incomplete external invocation may still have incurred cost:
        # never claim a complete usage record after an exception.
        metrics["token_usage_complete"] = False
        if verbose:
            print("Errore variante verifica:", error)

    # Anche su eccezione conserviamo i round gia' osservati
    # dalla stream, invece di segnare impropriamente zero.
    metrics["tool_rounds"] = (
        metrics["exploration_tool_rounds"]
        + metrics["verification_tool_rounds"]
    )
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
