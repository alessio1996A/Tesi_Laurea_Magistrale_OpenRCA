"""Nomenclatura delle varianti OpenRCA e lettura degli esperimenti storici.

Dalla versione di presentazione/manutenzione del 4 novembre 2026 i nomi
CANONICI usati per nuove esecuzioni sono A0, A1, A1_8R,
A1_8R_Planning e A1_PAVE.

Attenzione: nei 40 risultati V3 congelati la stringa storica "A1"
indica la variante CON otto regole; nelle esecuzioni nuove "A1" indica
invece SOLO il report deterministico. Non si deve quindi inferire il
significato della stringa senza conoscere il protocollo di provenienza.

Le conversioni sono esplicite, reversibili e non scrivono su disco.

Corrispondenza tra nomi storici (V3) e nomi nuovi, nello stesso ordine:
  A0 -> A0 | A1_V2 -> A1 | A1 -> A1_8R | A1_VERIFY -> A1_8R_Planning | A1_VERIFY_ST -> A1_PAVE

Funzioni: `nome_presentazione` (storico -> nuovo), `id_interno` (nuovo -> storico) e
`variante_canonica` (risolve il nome in modo esplicito secondo lo schema scelto).
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
# `zip` accoppia le due tuple posizione per posizione: storico -> nuovo.
NOMI_PRESENTAZIONE = dict(zip(VARIANTI_INTERNE, VARIANTI_FINALI))

# Descrizione breve di ciascuna variante nuova.
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

# Controllo all'importazione: le cinque etichette nuove devono essere tutte diverse.
if len(set(VARIANTI_FINALI)) != len(VARIANTI_FINALI):
    raise RuntimeError("Le cinque etichette finali devono essere distinte")


def nome_presentazione(variante_storica: str) -> str:
    """Converte un ID storico V3 in un nome nuovo senza alterare file o JSON.

    Solleva ValueError se l'ID storico non è uno dei cinque noti.
    """
    try:
        return NOMI_PRESENTAZIONE[variante_storica]
    except KeyError as errore:
        raise ValueError(
            f"Variante storica sconosciuta: {variante_storica}"
        ) from errore


def id_interno(nome_finale: str) -> str:
    """Recupera l'ID storico corrispondente al nome nuovo.

    Solleva ValueError se il nome nuovo non esiste.
    """
    # Ricerca inversa nel dizionario: la corrispondenza è biunivoca, quindi il risultato è unico.
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

    Restituisce il nome nel nuovo schema; solleva ValueError per un nome o uno schema non validi.
    """
    # Schema nuovo: il nome deve già essere uno dei cinque nuovi e viene restituito invariato.
    if schema == "current":
        if nome not in VARIANTI_FINALI:
            raise ValueError(
                f"Nome agente non valido nel nuovo schema: {nome!r}. "
                "Per leggere i piani V3 usa schema='historic_v3'."
            )
        return nome

    # Schema storico: il nome è quello dei file V3 e si converte nel corrispondente nome nuovo.
    if schema == "historic_v3":
        return nome_presentazione(nome)

    raise ValueError(f"Schema di nomenclatura sconosciuto: {schema!r}")
