"""Candidato V3 di strumentazione del runner D, SOLO OFFLINE; nessun dispatch a pagamento.

Strumenta l'esistente `run_experiment` GT-free senza modificare i motori a grafo RQ1/V2
congelati ne' il validatore dell'output. Il runner originale importa le due funzioni
esecutrici di D in modo dinamico. Dentro un contesto esplicito e a thread singolo si
reindirizzano SOLO quelle chiamate verso il ponte V3 del testo finale esatto.

Questo modulo NON esegue `run_experiment`, non carica file del benchmark, non costruisce
modelli, non scrive artefatti e non autorizza una release scientifica. Il futuro dispatcher
versionato dovra' imporre a parte: sorgente GT-free, nuovi ID V3, pin di release e sorgenti,
ledger create-only e approvazione per ogni stage.

Contenuto
---------
- `PLANNING_VARIANTS`, `REACT_VARIANTS`: harness che usano il motore "verify" o "react";
- `DRunnerCaptureBlocked`: errore "esecuzione D ambigua o non corrispondente";
- `V3DRunnerCapture`: contesto monouso (`with`) che intercetta la chiamata al grafo D,
  la passa dal ponte e poi, con `build_receipt`, restituisce risultato e metadati insieme.
"""
from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import patch

import agent.graph_engine as react
import agent.verify_graph as verify
from evaluation.rq2_v3_d_final_stream_candidate import (
    D_META_SCHEMA,
    run_d_final_candidate,
)

VERSION = "rq2_v3_d_runner_capture_candidate_v0"
# Harness a pianificazione (motore "verify") e harness ReAct (motore "react").
PLANNING_VARIANTS = frozenset(("A1_8R_Planning", "A1_PAVE"))
REACT_VARIANTS = frozenset(("A0", "A1", "A1_8R"))


class DRunnerCaptureBlocked(RuntimeError):
    """Impedisce un'esecuzione del grafo D ambigua o non corrispondente."""


class V3DRunnerCapture:
    """Contesto monouso per provare un runner di esperimento non modificato.

    Nei test offline il chiamante deve usare un LLM/grafo sintetico e un caricatore dati
    sostituito. Questo candidato di audit non va mai usato per chiamate a provider a pagamento.

    Uso: `with V3DRunnerCapture(harness=...) as cattura: risultato = run_experiment(...)`,
    poi `cattura.build_receipt(risultato)`.
    """

    def __init__(self, *, harness: str):
        """Prepara la cattura per `harness`; ne deriva il motore atteso ("react" o "verify").

        Solleva `DRunnerCaptureBlocked` per un harness sconosciuto. Lo stato interno conta le
        chiamate (deve essere una sola) e conserva risultato D e metadati dell'estrazione.
        """
        if harness in REACT_VARIANTS:
            self.expected_engine = "react"
        elif harness in PLANNING_VARIANTS:
            self.expected_engine = "verify"
        else:
            raise DRunnerCaptureBlocked("Unknown D harness")
        self.harness = harness
        self._active = False
        self._entered = False
        self._stack = None
        self._calls = 0
        self._d_run = None
        self._meta = None

    def _execute(self, *, engine: str, grafo, richiesta,
                 recursion_limit=30, verbose=False):
        """Sostituto della funzione esecutrice di D: passa dal ponte V3 del testo finale.

        Controlla che il contesto sia attivo, che il motore sia quello atteso e che sia la
        PRIMA chiamata; poi esegue `run_d_final_candidate` e conserva risultato e metadati.
        Restituisce il `diagnostic_run`, cosi' il runner originale prosegue come prima.
        """
        if not self._active or engine != self.expected_engine:
            raise DRunnerCaptureBlocked("Wrong/unsafely dispatched D engine")
        if self._calls:
            raise DRunnerCaptureBlocked("Repeated D execution forbidden")
        self._calls += 1
        result = run_d_final_candidate(
            grafo, richiesta, engine=engine,
            recursion_limit=recursion_limit, verbose=verbose,
        )
        self._d_run = result["diagnostic_run"]
        self._meta = result["d_final_text_extraction"]
        if self._meta.get("schema") != D_META_SCHEMA:
            raise DRunnerCaptureBlocked("Wrong D extraction metadata")
        return self._d_run

    def _react(self, grafo, richiesta, recursion_limit=30, verbose=False):
        """Sostituto di `esegui_grafo_rca` (motore ReAct)."""
        return self._execute(
            engine="react", grafo=grafo, richiesta=richiesta,
            recursion_limit=recursion_limit, verbose=verbose,
        )

    def _verify(self, grafo, richiesta, recursion_limit=30, verbose=False):
        """Sostituto di `esegui_grafo_rca_verify` (motore a pianificazione)."""
        return self._execute(
            engine="verify", grafo=grafo, richiesta=richiesta,
            recursion_limit=recursion_limit, verbose=verbose,
        )

    def __enter__(self):
        """Attiva il contesto: sostituisce le due funzioni esecutrici di D con quelle della cattura.

        Si puo' entrare una sola volta. Se la sostituzione fallisce, si ripristina tutto.
        """
        if self._entered:
            raise DRunnerCaptureBlocked("D capture is single-use")
        self._entered = True
        self._stack = ExitStack()
        try:
            self._stack.enter_context(
                patch.object(react, "esegui_grafo_rca", self._react)
            )
            self._stack.enter_context(
                patch.object(verify, "esegui_grafo_rca_verify", self._verify)
            )
        except Exception:
            self._stack.close()
            raise
        self._active = True
        return self

    def __exit__(self, exc_type, exc, tb):
        """Chiude il contesto e ripristina le funzioni originali; non nasconde le eccezioni."""
        self._active = False
        self._stack.close()
        return False

    def build_receipt(self, result: dict) -> dict:
        """Restituisce l'output originale del runner piu' la provenienza di D, SEPARATA.

        Non assegna lo stato scientifico RECORDED_COMPLETE e non salva nulla: il successo V3
        lo decidera' soltanto un futuro adattatore scientifico versionato.

        Argomento: `result`, il risultato del runner originale. Controlli: 1) il contesto non
        e' piu' attivo; 2) il grafo D e' stato eseguito esattamente una volta; 3) il testo
        finale del runner e' quello catturato; 4) l'harness e' quello atteso; 5) i metadati
        dell'estrazione ci sono.
        """
        if self._active:
            raise DRunnerCaptureBlocked("Runner context still active")
        if self._calls != 1 or type(self._d_run) is not dict:
            raise DRunnerCaptureBlocked("Exactly one D graph run required")
        if type(result) is not dict or result.get("raw_response") != self._d_run.get(
            "raw_response"
        ):
            raise DRunnerCaptureBlocked("Runner final text changed")
        if result.get("variant") != self.harness:
            raise DRunnerCaptureBlocked("Runner harness identity drift")
        if type(self._meta) is not dict:
            raise DRunnerCaptureBlocked("Missing extraction metadata")
        return {
            "version": VERSION,
            "diagnostic_run": result,
            "d_final_text_extraction": dict(self._meta),
            "can_execute_api": False,
            "scientific_release_frozen": False,
            "can_write_scientific_records": False,
        }
