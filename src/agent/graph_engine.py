"""Motore LangGraph condiviso per gli esperimenti OpenRCA A0 e A1.

Il budget di esplorazione limita i *round* in cui il modello puo` richiedere
strumenti. Al raggiungimento del budget viene eseguito UN SOLO tentativo di
finalizzazione senza strumenti; richieste di tool in questa fase non vengono
eseguite e sono registrate come fallimento esplicito.

Non contiene etichette, ground truth o logica specifica dei due agenti.
"""

from __future__ import annotations

import time
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode


class RCAState(TypedDict):
    """Stato condiviso del grafo, indipendente dalla variante A0/A1."""

    messages: Annotated[list[BaseMessage], add_messages]
    tool_rounds: int
    finalization_done: bool
    finalization_error: str | None


def testo_messaggio(contenuto) -> str:
    """Converte il contenuto di un messaggio LangChain in testo leggibile."""

    if contenuto is None:
        return ""
    if isinstance(contenuto, str):
        return contenuto
    if isinstance(contenuto, list):
        parti = []
        for elemento in contenuto:
            if isinstance(elemento, str):
                parti.append(elemento)
            elif isinstance(elemento, dict):
                testo = elemento.get("text")
                if isinstance(testo, str):
                    parti.append(testo)
                else:
                    parti.append(str(elemento))
            else:
                parti.append(str(elemento))
        return "\n".join(parti)
    return str(contenuto)


def _messaggio_senza_tool(risposta) -> AIMessage:
    """Crea un messaggio neutro preservando l'uso token, non le richieste tool.

    Serve solo quando la finalizzazione e` fallita. Non trasforma
    richieste di tool in una diagnosi e non inventa contenuto.
    """

    kwargs = {"content": ""}
    usage = getattr(risposta, "usage_metadata", None)
    metadata = getattr(risposta, "response_metadata", None)
    if isinstance(usage, dict):
        kwargs["usage_metadata"] = usage
    if isinstance(metadata, dict):
        kwargs["response_metadata"] = metadata
    return AIMessage(**kwargs)


def crea_grafo_rca(llm, tools, system_prompt: str, max_tool_rounds: int):
    """Costruisce un grafo con limite rigido ai round esplorativi.

    Un round corrisponde a una risposta LLM contenente >=1 tool_calls.
    Piu` tool_calls nella stessa risposta contano come un round.
    Dopo l'ultimo round, i tool di quel round sono eseguiti e si tenta una
    sola risposta finale: nessuna tool_call successiva verra` eseguita.
    """

    if max_tool_rounds < 1:
        raise ValueError("Numero di round non valido.")
    if not system_prompt.strip():
        raise ValueError("Prompt di sistema vuoto.")
    if not tools:
        raise ValueError("Nessun tool disponibile.")

    llm_with_tools = llm.bind_tools(tools)

    def agente(state: RCAState):
        rounds = int(state.get("tool_rounds", 0))

        if rounds >= max_tool_rounds:
            # Finale consentito UNA SOLA VOLTA: il router terminera` sempre.
            prompt_finale = system_prompt + (
                "\n\nTool exploration budget exhausted. "
                "Do not request any tools. "
                "Use only the evidence already available. "
                "Do not invent facts if evidence is insufficient. "
                "Return ONLY valid OpenRCA JSON."
            )
            risposta = llm.invoke(
                [SystemMessage(content=prompt_finale)] + state["messages"]
            )

            # Alcuni provider restituiscono tool_calls persino senza bind_tools.
            # L'istruzione testuale non e` una protezione: impediamo via codice
            # l'esecuzione di qualunque nuova tool_call dopo il budget.
            if (
                getattr(risposta, "tool_calls", None)
                or getattr(risposta, "invalid_tool_calls", None)
            ):
                return {
                    "messages": [_messaggio_senza_tool(risposta)],
                    "tool_rounds": rounds,
                    "finalization_done": True,
                    "finalization_error": (
                        "AgentBudgetExhausted: il modello ha richiesto "
                        "tool durante l'unica finalizzazione consentita; "
                        "nessun tool ulteriore e' stato eseguito."
                    ),
                }

            if not testo_messaggio(getattr(risposta, "content", None)).strip():
                return {
                    "messages": [_messaggio_senza_tool(risposta)],
                    "tool_rounds": rounds,
                    "finalization_done": True,
                    "finalization_error": (
                        "AgentFinalizationEmpty: risposta finale vuota "
                        "dopo l'esaurimento del budget."
                    ),
                }

            return {
                "messages": [risposta],
                "tool_rounds": rounds,
                "finalization_done": True,
                "finalization_error": None,
            }

        risposta = llm_with_tools.invoke(
            [SystemMessage(content=system_prompt)] + state["messages"]
        )
        if getattr(risposta, "tool_calls", None):
            rounds += 1

        return {
            "messages": [risposta],
            "tool_rounds": rounds,
            "finalization_done": False,
            "finalization_error": None,
        }

    def route_tools(state: RCAState):
        # Priorita` assoluta alla fine della fase di finalizzazione.
        if state.get("finalization_done") or state.get("finalization_error"):
            return END
        ultimo = state["messages"][-1]
        if getattr(ultimo, "tool_calls", None):
            return "tools"
        return END

    builder = StateGraph(RCAState)
    builder.add_node("agente", agente)
    builder.add_node("tools", ToolNode(tools))
    builder.add_conditional_edges(
        "agente", route_tools, {"tools": "tools", END: END}
    )
    builder.add_edge("tools", "agente")
    builder.add_edge(START, "agente")
    return builder.compile()


def esegui_grafo_rca(
    grafo,
    richiesta: str,
    recursion_limit: int = 30,
    verbose: bool = True,
) -> dict:
    """Esegue il grafo mantenendo l'interfaccia e le metriche esistenti.

    I fallimenti dell'ultimo tentativo sono riportati in ``error``;
    ``raw_response`` rimane None, non viene generata alcuna diagnosi fittizia.
    Il preprocessing e` misurato separatamente da experiment_runner.py.
    """

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
    }
    traiettoria = []
    risposta_finale = None
    errore = None
    inizio = time.perf_counter()

    try:
        for evento in grafo.stream(
            stato_iniziale,
            config={"recursion_limit": recursion_limit},
            stream_mode="updates",
        ):
            for nodo, aggiornamento in evento.items():
                if nodo == "agente":
                    if aggiornamento.get("finalization_error"):
                        errore = aggiornamento["finalization_error"]
                        risposta_finale = None

                    metriche["tool_rounds"] = max(
                        metriche["tool_rounds"],
                        int(aggiornamento.get("tool_rounds", 0)),
                    )

                    for msg in aggiornamento.get("messages", []):
                        metriche["llm_calls"] += 1
                        usage = getattr(msg, "usage_metadata", None) or {}
                        for chiave in (
                            "input_tokens", "output_tokens", "total_tokens"
                        ):
                            metriche[chiave] += int(usage.get(chiave, 0) or 0)

                        calls = getattr(msg, "tool_calls", None) or []
                        metriche["tool_calls"] += len(calls)
                        for chiamata in calls:
                            traiettoria.append(
                                {
                                    "tipo": "tool_call",
                                    "nome": chiamata.get("name"),
                                    "parametri": chiamata.get("args", {}),
                                }
                            )

                        if verbose and calls:
                            print(
                                "Round", metriche["tool_rounds"], "- tool:",
                                ", ".join(c.get("name", "?") for c in calls),
                            )

                        if not calls and not aggiornamento.get("finalization_error"):
                            contenuto = testo_messaggio(
                                getattr(msg, "content", None)
                            )
                            if contenuto.strip():
                                risposta_finale = contenuto
                            else:
                                errore = "EmptyFinalResponse: risposta finale vuota."
                                risposta_finale = None

                elif nodo == "tools":
                    for msg in aggiornamento.get("messages", []):
                        estratto = testo_messaggio(msg.content)
                        traiettoria.append(
                            {
                                "tipo": "tool_result",
                                "nome": msg.name,
                                "risposta": estratto,
                            }
                        )
                        if verbose:
                            print(
                                "Risultato", msg.name, "-", len(estratto),
                                "caratteri",
                            )

    except Exception as exc:
        errore = f"{type(exc).__name__}: {exc}"
        risposta_finale = None
        if verbose:
            print("ERRORE ESECUZIONE:", errore)

    metriche["duration_seconds"] = round(time.perf_counter() - inizio, 3)
    return {
        "raw_response": risposta_finale,
        "metrics": metriche,
        "tool_trajectory": traiettoria,
        "error": errore,
    }
