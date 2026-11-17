"""Politica CANDIDATA di estrazione uniforme del testo C/K; OFFLINE, non collegata al live.

Una risposta fatta di frammenti di testo non deve acquistare caratteri nuovi solo perche'
il trasporto espone dei confini fra i blocchi. Questo modulo non ripara mai JSON malformato,
non interpreta i contenuti, non legge la GT, non costruisce SDK di provider e non fa chiamate API.

E' un *candidato* successore. Il sorgente congelato f0b64 e la release scientifica G4E/G4L
restano quelli validi per i record esistenti: non attivare stage live con questo modulo
senza una versione/release esplicitamente separata.

Contenuto
---------
- `MAX_BLOCKS`, `POLICY`, `TEXT_KINDS`: limite di blocchi, nome della politica, tipi di blocco "testo";
- `VisibleText`: il risultato (testo, tipo di contenuto, blocchi di testo e altri blocchi);
- `CKTextExtractionBlocked`: errore per un involucro di contenuto non valido o eccessivo;
- `extract_visible_ck_text`: l'estrazione vera e propria.
"""
from __future__ import annotations

from typing import NamedTuple


# Numero massimo di blocchi di contenuto accettati in una risposta (oltre: errore).
MAX_BLOCKS = 256
# Nome della politica, registrato accanto a ogni risposta estratta.
POLICY = "rq2_ck_exact_text_fragments_candidate_v1"
# Tipi di blocco considerati "testo visibile" (None = blocco senza campo `type`).
TEXT_KINDS = (None, "text", "text_delta")


class VisibleText(NamedTuple):
    """Testo visibile estratto da una risposta, con i conteggi dei blocchi.

    Campi: `raw_text` (frammenti uniti senza separatori), `content_kind` ("str", "list" o
    "unsupported"), `text_blocks` (frammenti di testo usati), `other_blocks` (blocchi ignorati).
    """

    raw_text: str
    content_kind: str
    text_blocks: int
    other_blocks: int


class CKTextExtractionBlocked(ValueError):
    """Involucro di blocchi di contenuto non valido o eccessivo: nessuna congettura, si blocca."""


def extract_visible_ck_text(content: object) -> VisibleText:
    """Restituisce solo il testo visibile, unendo i frammenti senza separatori.

    Il confine fra blocchi e' un metadato del trasporto, non il permesso di inserire un
    a capo o uno spazio. Gli spazi gia' presenti e la sintassi non valida restano esattamente
    come sono. Messaggi indipendenti e distinti non vanno passati come un'unica lista.
    Nessun contenuto di ragionamento, firma o uso di tool viene esposto.

    Argomenti: `content` e' il contenuto del messaggio del modello: stringa o lista di blocchi.
    Solleva `CKTextExtractionBlocked` se i blocchi sono piu' di `MAX_BLOCKS`.
    """
    # Contenuto gia' testuale: nessun frammento da unire (un blocco se non e' vuoto).
    if isinstance(content, str):
        return VisibleText(content, "str", int(bool(content)), 0)
    # Tipo non previsto (ne' stringa ne' lista): nessun testo.
    if not isinstance(content, list):
        return VisibleText("", "unsupported", 0, 0)
    if len(content) > MAX_BLOCKS:
        raise CKTextExtractionBlocked("Excessive C/K content blocks")

    # Lista di blocchi: si tengono i frammenti di testo (stringhe, oppure dizionari con tipo
    # "testo" e campo `text` stringa); tutto il resto si conta soltanto.
    fragments: list[str] = []
    other_count = 0
    for block in content:
        if isinstance(block, str):
            fragments.append(block)
        elif (
            isinstance(block, dict)
            and block.get("type") in TEXT_KINDS
            and isinstance(block.get("text"), str)
        ):
            fragments.append(block["text"])
        else:
            other_count += 1

    return VisibleText("".join(fragments), "list", len(fragments), other_count)
