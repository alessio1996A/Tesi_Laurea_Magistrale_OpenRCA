"""Nomenclatura delle varianti OpenRCA e lettura degli esperimenti storici.

Dalla versione di presentazione/manutenzione del 4 novembre 2026 i nomi
CANONICI usati per nuove esecuzioni sono A0, A1, A1_8R,
A1_8R_Planning e A1_PAVE.

Attenzione: nei 40 risultati V3 congelati la stringa storica "A1"
indica la variante CON otto regole; nelle esecuzioni nuove "A1" indica
invece SOLO il report deterministico. Non si deve quindi inferire il
significato della stringa senza conoscere il protocollo di provenienza.

Le conversioni sono esplicite, reversibili e non scrivono su disco.
"""
from __future__ import annotations

# Identificativi originali dei JSON/claim della campagna V3 congelata.
VARIANTI_INTERNE = (
    "A0", "A1_V2", "A1", "A1_VERIFY", "A1_VERIFY_ST",
)

# Identificativi operativi per TUTTE le nuove esecuzioni.
VARIANTI_FINALI = (
    "A0", "A1", "A1_8R", "A1_8R_Planning", "A1_PAVE",
)

# Una corrispondenza biunivoca, non una rinomina dei JSON storici.
NOMI_PRESENTAZIONE = dict(zip(VARIANTI_INTERNE, VARIANTI_FINALI))

DESCRIZIONI = {
    "A0": "Baseline LangGraph ReAct-style con cinque tool",
    "A1": "Baseline con report di evidenze deterministiche",
    "A1_8R": "Evidenze deterministiche e otto regole diagnostiche",
    "A1_8R_Planning": "Otto regole e verifiche mirate con planner deterministico",
    "A1_PAVE": (
        "Planning e contesto strutturale-temporale ispirato a PAVE: "
        "non equivale a PAVE completo e non certifica causalita'"
    ),
}

if len(set(VARIANTI_FINALI)) != len(VARIANTI_FINALI):
    raise RuntimeError("Le cinque etichette finali devono essere distinte")


def nome_presentazione(variante_storica: str) -> str:
    """Converte un ID storico V3 in un nome nuovo senza alterare file o JSON."""
    try:
        return NOMI_PRESENTAZIONE[variante_storica]
    except KeyError as errore:
        raise ValueError(
            f"Variante storica sconosciuta: {variante_storica}"
        ) from errore


def id_interno(nome_finale: str) -> str:
    """Recupera l'ID storico corrispondente al nome nuovo."""
    for identificativo, etichetta in NOMI_PRESENTAZIONE.items():
        if nome_finale == etichetta:
            return identificativo
    raise ValueError(f"Nome definitivo sconosciuto: {nome_finale}")


def variante_canonica(nome: str, *, schema: str = "current") -> str:
    """Risoluzione ESPLICITA del significato del nome dell'agente.

    schema="current": permette solamente le cinque etichette nuove.
    schema="historic_v3": interpreta le stringhe nel protocollo V3
    originale, incluso il significato storico di "A1" (otto regole).

    Non normalizzare "A1" senza questo parametro: sarebbe ambiguo.
    """
    if schema == "current":
        if nome not in VARIANTI_FINALI:
            raise ValueError(
                f"Nome agente non valido nel nuovo schema: {nome!r}. "
                "Per leggere i piani V3 usa schema='historic_v3'."
            )
        return nome

    if schema == "historic_v3":
        return nome_presentazione(nome)

    raise ValueError(f"Schema di nomenclatura sconosciuto: {schema!r}")
