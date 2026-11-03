"""Nomi leggibili delle cinque varianti nella presentazione V3.

Le sigle interne sono parte del protocollo congelato e NON devono essere
rinominate nei JSON sperimentali, nei run_id o nel codice di scoring.
Questa mappa cambia soltanto come vengono mostrati i nomi nel README,
nei grafici e nelle presentazioni per il relatore.
"""
from __future__ import annotations

# Ordine concordato di presentazione: dalla baseline al contesto PAVE-inspired.
VARIANTI_INTERNE = (
    "A0", "A1_V2", "A1", "A1_VERIFY", "A1_VERIFY_ST",
)

NOMI_PRESENTAZIONE = {
    "A0": "A0",
    "A1_V2": "A1",
    "A1": "A1_8R",
    "A1_VERIFY": "A1_8R_Planning",
    "A1_VERIFY_ST": "A1_PAVE",
}

DESCRIZIONI = {
    "A0": "Baseline ReAct-style con cinque tool di telemetria",
    "A1_V2": "Baseline con report di evidenze deterministiche",
    "A1": "Evidenze deterministiche e otto regole diagnostiche",
    "A1_VERIFY": "Otto regole, planner e verifiche mirate (massimo 4+2 round)",
    "A1_VERIFY_ST": (
        "Planner e contesto strutturale-temporale ispirato a PAVE; "
        "non equivale a PAVE completo né certifica causalità"
    ),
}


def nome_presentazione(variante_interna: str) -> str:
    """Restituisce l'etichetta visibile senza modificare l'ID sperimentale."""
    try:
        return NOMI_PRESENTAZIONE[variante_interna]
    except KeyError as errore:
        raise ValueError(
            f"Variante sperimentale sconosciuta: {variante_interna}"
        ) from errore


def id_interno(nome: str) -> str:
    """Converte il nome di presentazione nell'ID originale del protocollo."""
    for identificativo, etichetta in NOMI_PRESENTAZIONE.items():
        if nome == etichetta:
            return identificativo
    raise ValueError(f"Nome di presentazione sconosciuto: {nome}")
