"""Candidato RQ2 V3: estrazione esatta del testo visibile per le risposte FINALI di D.

SOLO PROGETTO OFFLINE: nessuna release V3 legata ai sorgenti, nessun ledger e nessun
dispatcher live.

Una piccola "vista" sul flusso del grafo normalizza SOLO l'ultimo `AIMessage` visibile prima
che i runner D congelati (ReAct e verify) lo leggano. Non modifica mai l'`AIMessage` originale,
il grafo, i risultati dei tool, i prompt, le chiamate al provider ne' i budget di D. Non
ripara JSON malformato. Nessun monkeypatch globale di `graph_engine`.

La stessa identica funzione/politica di estrazione e' usata dal trasporto C/K candidato: tutti
i modelli e gli harness seguono le stesse regole sui blocchi di testo. Non chiamare provider
reali e non registrare questo sotto la release V2 congelata.

Contenuto
---------
- `VERSION`, `D_META_SCHEMA`, `ENGINES`: versione, schema dei metadati e motori ammessi
  ("react" e "verify");
- `DFinalStreamCandidateBlocked`: errore "forma del flusso finale troppo ambigua";
- `ExactFinalTextStream`: la vista sul grafo, monouso, che sostituisce il testo del messaggio
  finale con il testo visibile estratto;
- `run_d_final_candidate`: esegue il grafo D attraverso la vista e restituisce una ricevuta
  candidata con i metadati dell'estrazione.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage

from agent.rq2_v2_graph_engine import esegui_grafo_rca_v2
from agent.verify_graph import esegui_grafo_rca_verify
from evaluation.rq2_v2_ck_text_extraction_candidate import (
    POLICY,
    extract_visible_ck_text,
)

VERSION = "rq2_v3_d_final_stream_candidate_v0"
D_META_SCHEMA = "rq2_v3_d_final_text_meta_v0"
# Motori D supportati: ReAct (nodo finale "agente") e verify (nodo finale "finale").
ENGINES = ("react", "verify")


class DFinalStreamCandidateBlocked(RuntimeError):
    """La forma del flusso dell'output finale e' troppo ambigua: non si indovina mai."""


class ExactFinalTextStream:
    """Vista monouso di un grafo esistente e gia' compilato.

    Lo stato del grafo non viene mai modificato. Una copia superficiale dell'evento e del
    messaggio porta il testo finale visibile ESATTO al runner originale del grafo.
    """

    def __init__(self, graph: object, *, engine: str):
        """Crea la vista su `graph` per il motore `engine` ("react" o "verify").

        Memorizza anche i metadati dell'estrazione, inizialmente "non osservato", che si
        riempiono quando passa il messaggio finale.
        """
        if engine not in ENGINES:
            raise DFinalStreamCandidateBlocked("Unknown D engine")
        self.graph = graph
        self.engine = engine
        self._used = False
        self._final_count = 0
        self.final_meta = {
            "schema": D_META_SCHEMA,
            "policy": POLICY,
            "content_kind": "not_observed",
            "text_blocks": 0,
            "nontext_blocks": 0,
        }

    def stream(self, initial_state, *, config, stream_mode):
        """Generatore con la stessa interfaccia di `graph.stream`, ma col testo finale sostituito.

        Passi: 1) si puo' usare una sola volta; 2) per ogni evento del grafo si guardano solo i
        nodi finali (nodo "agente" per ReAct, "finale" per verify); 3) i messaggi con tool call
        sono esplorazione, non risposta finale, e si saltano; 4) il messaggio finale e' uno solo:
        se ce ne sono di piu' si blocca; 5) se ne estrae il testo visibile e se ne registrano i
        metadati; 6) si passa al runner una COPIA del messaggio con quel testo.
        """
        if self._used:
            raise DFinalStreamCandidateBlocked(
                "Graph stream view cannot be reused for a second execution"
            )
        self._used = True
        # Nessun `graph.invoke`, nessuna factory SDK, nessuna richiesta extra a tool o provider.
        for event in self.graph.stream(
            initial_state, config=config, stream_mode=stream_mode
        ):
            if type(event) is not dict:
                raise DFinalStreamCandidateBlocked("Unexpected graph event")
            changed = None
            for node, update in event.items():
                # Nodo candidato: quello che produce la risposta finale per il motore scelto.
                candidate_node = (
                    node == "agente" if self.engine == "react"
                    else node == "finale"
                )
                if not candidate_node or type(update) is not dict:
                    continue
                if update.get("finalization_error"):
                    # Si tiene l'errore originale: non si inventa una diagnosi.
                    continue
                messages = update.get("messages")
                if type(messages) is not list:
                    raise DFinalStreamCandidateBlocked(
                        "Final event without explicit message list"
                    )
                new_messages = list(messages)
                mutated = False
                for i, msg in enumerate(messages):
                    if not isinstance(msg, AIMessage):
                        # I messaggi non AI non si reinterpretano mai come output del modello.
                        continue
                    if getattr(msg, "tool_calls", None):
                        # Esplorazione ReAct, NON una risposta finale.
                        continue
                    if getattr(msg, "invalid_tool_calls", None):
                        raise DFinalStreamCandidateBlocked(
                            "Unparsed tool calls in apparent final message"
                        )
                    self._final_count += 1
                    if self._final_count > 1:
                        raise DFinalStreamCandidateBlocked(
                            "Multiple final model messages are ambiguous"
                        )
                    visible = extract_visible_ck_text(msg.content)
                    self.final_meta = {
                        "schema": D_META_SCHEMA,
                        "policy": POLICY,
                        "content_kind": visible.content_kind,
                        "text_blocks": visible.text_blocks,
                        "nontext_blocks": visible.other_blocks,
                    }
                    # Copia esplicita dell'intero messaggio. NON si modifica il contenuto
                    # originale dell'SDK ne' alcuna traiettoria dei tool.
                    new_messages[i] = msg.model_copy(
                        update={"content": visible.raw_text}
                    )
                    mutated = True
                if mutated:
                    if changed is None:
                        changed = dict(event)
                    changed[node] = {**update, "messages": new_messages}
            # Si restituisce l'evento modificato, oppure l'originale se non c'e' nulla da cambiare.
            yield changed if changed is not None else event


def run_d_final_candidate(
    graph: object, request: str, *, engine: str,
    recursion_limit: int = 30, verbose: bool = False,
) -> dict:
    """Esegue il grafo D gia' compilato attraverso il ponte del testo finale.

    L'output e' una *ricevuta candidata* offline, non un `diagnostic_run` di produzione. Il
    contratto di risultato di D e le metriche dei token restano intatti. Un futuro runner o
    ledger V3 dovra' legare e validare esplicitamente i metadati.

    Argomenti: `graph` (grafo compilato), `request` (richiesta al modello), `engine` ("react"
    o "verify"), `recursion_limit` (limite di ricorsione del grafo, 30 di default) e
    `verbose`. Restituisce un dizionario con `diagnostic_run` (risultato del runner D),
    `d_final_text_extraction` (metadati) e le dichiarazioni "nessuna API, non legato ai sorgenti".

    Passi: 1) si avvolge il grafo nella vista; 2) si usa il runner D del motore scelto;
    3) il risultato deve essere un dizionario; 4) se c'e' una risposta grezza, l'estrazione
    del testo finale deve risultare tracciata.
    """
    bridge = ExactFinalTextStream(graph, engine=engine)
    if engine == "react":
        result = esegui_grafo_rca_v2(
            bridge, request,
            recursion_limit=recursion_limit, verbose=verbose,
        )
    elif engine == "verify":
        result = esegui_grafo_rca_verify(
            bridge, request,
            recursion_limit=recursion_limit, verbose=verbose,
        )
    else:
        raise DFinalStreamCandidateBlocked("Unknown D engine")

    if type(result) is not dict:
        raise DFinalStreamCandidateBlocked("Invalid D runner receipt")
    if result.get("raw_response") is not None and (
        bridge.final_meta["content_kind"] == "not_observed"
    ):
        raise DFinalStreamCandidateBlocked(
            "D output without traced final text extraction"
        )
    return {
        "version": VERSION,
        "diagnostic_run": result,
        "d_final_text_extraction": dict(bridge.final_meta),
        "can_execute_api": False,
        "scientific_release_frozen": False,
        "source_bound": False,
    }
