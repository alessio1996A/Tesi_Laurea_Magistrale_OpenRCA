import time

from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage
)

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode


class RCAState(TypedDict):
    """
    Stato condiviso dell'agente LangGraph.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    tool_rounds: int


def testo_messaggio(contenuto) -> str:
    """
    Converte il contenuto delle risposte in testo.
    """

    if isinstance(contenuto, str):
        return contenuto

    if isinstance(contenuto, list):
        return "\n".join(
            str(parte.get("text", ""))
            if isinstance(parte, dict)
            else str(parte)
            for parte in contenuto
        )

    return str(contenuto)


def crea_grafo_rca(
    llm,
    tools,
    system_prompt: str,
    max_tool_rounds: int
):
    """
    Costruisce il grafo LangGraph condiviso.

    Non esegue Gemini.
    Non legge dataset.
    Non utilizza ground truth.
    """

    if max_tool_rounds < 1:
        raise ValueError("Numero di round non valido.")

    if not system_prompt.strip():
        raise ValueError("Prompt di sistema vuoto.")

    if not tools:
        raise ValueError("Nessun tool disponibile.")

    # Colleghiamo i tool al modello.
    llm_with_tools = llm.bind_tools(tools)

    # =====================================================
    # NODO AGENTE
    # =====================================================

    def agente(state: RCAState):

        rounds = state.get("tool_rounds", 0)

        # Terminato il budget, richiediamo la diagnosi
        # senza permettere ulteriori chiamate ai tool.
        if rounds >= max_tool_rounds:

            prompt_finale = system_prompt + (
                "\nTool exploration budget exhausted. "
                "Do not request tools. "
                "Return the final diagnosis as ONLY "
                "valid OpenRCA JSON."
            )

            risposta = llm.invoke(
                [SystemMessage(content=prompt_finale)]
                + state["messages"]
            )

        else:

            risposta = llm_with_tools.invoke(
                [SystemMessage(content=system_prompt)]
                + state["messages"]
            )

            if getattr(risposta, "tool_calls", None):
                rounds += 1

        return {
            "messages": [risposta],
            "tool_rounds": rounds
        }

    # =====================================================
    # ROUTING
    # =====================================================

    def route_tools(state: RCAState):

        ultimo = state["messages"][-1]

        if getattr(ultimo, "tool_calls", None):
            return "tools"

        return END

    # =====================================================
    # COSTRUZIONE DEL GRAFO
    # =====================================================

    builder = StateGraph(RCAState)

    builder.add_node("agente", agente)
    builder.add_node("tools", ToolNode(tools))

    builder.add_conditional_edges(
        "agente",
        route_tools,
        {
            "tools": "tools",
            END: END
        }
    )

    builder.add_edge("tools", "agente")
    builder.add_edge(START, "agente")

    return builder.compile()


def esegui_grafo_rca(
    grafo,
    richiesta: str,
    recursion_limit: int = 30,
    verbose: bool = True
) -> dict:
    """
    Esegue il grafo e registra:

    - chiamate LLM;
    - chiamate tool;
    - token;
    - durata;
    - traiettoria investigativa;
    - eventuali errori.

    Non include il preprocessing A1 nella durata.
    """

    stato_iniziale = {
        "messages": [
            HumanMessage(content=richiesta)
        ],
        "tool_rounds": 0
    }

    metriche = {
        "llm_calls": 0,
        "tool_calls": 0,
        "tool_rounds": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0
    }

    traiettoria = []
    risposta_finale = None
    errore = None

    inizio = time.perf_counter()

    try:

        for evento in grafo.stream(
            stato_iniziale,
            config={"recursion_limit": recursion_limit},
            stream_mode="updates"
        ):

            for nodo, aggiornamento in evento.items():

                # =========================================
                # RISPOSTE DELL'AGENTE
                # =========================================

                if nodo == "agente":

                    metriche["tool_rounds"] = max(
                        metriche["tool_rounds"],
                        int(
                            aggiornamento.get(
                                "tool_rounds", 0
                            )
                        )
                    )

                    for msg in aggiornamento.get(
                        "messages", []
                    ):

                        metriche["llm_calls"] += 1

                        usage = (
                            getattr(
                                msg,
                                "usage_metadata",
                                None
                            ) or {}
                        )

                        for chiave in (
                            "input_tokens",
                            "output_tokens",
                            "total_tokens"
                        ):

                            metriche[chiave] += int(
                                usage.get(chiave, 0) or 0
                            )

                        calls = (
                            getattr(msg, "tool_calls", [])
                            or []
                        )

                        metriche["tool_calls"] += len(calls)

                        for chiamata in calls:

                            traiettoria.append({
                                "tipo": "tool_call",
                                "nome": chiamata.get("name"),
                                "parametri": chiamata.get(
                                    "args", {}
                                )
                            })

                        if verbose and calls:

                            print(
                                "Round",
                                metriche["tool_rounds"],
                                "- tool:",
                                ", ".join(
                                    c.get("name", "?")
                                    for c in calls
                                )
                            )

                        if not calls:
                            risposta_finale = (
                                testo_messaggio(msg.content)
                            )

                # =========================================
                # RISULTATI DEI TOOL
                # =========================================

                elif nodo == "tools":

                    for msg in aggiornamento.get(
                        "messages", []
                    ):

                        estratto = testo_messaggio(
                            msg.content
                        )

                        traiettoria.append({
                            "tipo": "tool_result",
                            "nome": msg.name,
                            "risposta": estratto
                        })

                        if verbose:

                            print(
                                "Risultato",
                                msg.name,
                                "-",
                                len(estratto),
                                "caratteri"
                            )

    except Exception as exc:

        errore = (
            f"{type(exc).__name__}: {exc}"
        )

        if verbose:
            print("ERRORE ESECUZIONE:", errore)

    # =====================================================
    # METRICHE FINALI
    # =====================================================

    metriche["duration_seconds"] = round(
        time.perf_counter() - inizio,
        3
    )

    return {
        "raw_response": risposta_finale,
        "metrics": metriche,
        "tool_trajectory": traiettoria,
        "error": errore
    }