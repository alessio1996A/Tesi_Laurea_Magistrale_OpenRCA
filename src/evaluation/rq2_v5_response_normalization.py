"""RQ2-V5: normalizzazione del formato della risposta, UGUALE per tutti i modelli.

Motivo: in V4 Sonnet e Haiku hanno restituito il JSON dentro un blocco Markdown
(fence), che il parser strict rifiuta alla posizione 0, mentre Gemini ha
restituito JSON puro. Per confrontare i modelli in modo equo la politica di
formato deve essere unica, dichiarata prima dei run e senza parametri per modello.

Cosa fa (e SOLO questo):
- se l'INTERA risposta e' esattamente un solo blocco ```json ... ``` (oppure
  ``` ... ``` senza lingua), restituisce il contenuto interno INALTERATO;
- in ogni altro caso restituisce la risposta originale senza modifiche.

Cosa NON fa: non ripara JSON, non estrae JSON da testo libero, non rimuove
spazi dentro il blocco, non riordina chiavi, non ritenta chiamate al modello.
Un fence con testo fuori, piu' fence, lingua diversa da json o fence non chiuso
e' REJECTED_WRAPPER: la risposta resta quella originale e il parser strict la
rifiutera' come prima.

Ogni risposta riceve un flag `deviation` che va registrato accanto all'esito,
cosi' il tasso di conformita' strict (nessuna deviazione) e quello tollerante
(deviazione ammessa) si riportano insieme per tutti i modelli.

Solo funzioni pure: niente SDK, API, filesystem, ground truth o dispatcher.
"""
from __future__ import annotations

import hashlib
import re
from typing import NamedTuple

VERSION = "rq2_v5_response_normalization_v1"
POLICY = "rq2_v5_single_json_fence_v1"

DEVIATION_NONE = "NONE"
DEVIATION_SINGLE_JSON_FENCE = "SINGLE_JSON_FENCE"
DEVIATION_REJECTED_WRAPPER = "REJECTED_WRAPPER"
DEVIATIONS = (
    DEVIATION_NONE, DEVIATION_SINGLE_JSON_FENCE, DEVIATION_REJECTED_WRAPPER,
)

_FENCE_MARK = "```"
_ALLOWED_LANGUAGES = ("", "json")
# Intera risposta = spazi opzionali, apertura, riga della lingua, contenuto,
# chiusura, spazi opzionali. Il contenuto interno non viene toccato.
_SINGLE_FENCE = re.compile(
    r"\A[ \t\r\n]*```([A-Za-z0-9_+-]*)[ \t]*\r?\n(.*?)\r?\n?[ \t]*```[ \t\r\n]*\Z",
    re.DOTALL,
)


class NormalizedResponse(NamedTuple):
    text: str | None          # testo da passare al parser strict
    deviation: str            # uno di DEVIATIONS
    language_tag: str | None  # lingua dichiarata nel fence, se presente
    raw_sha256: str | None    # SHA-256 della risposta originale (UTF-8)
    text_sha256: str | None   # SHA-256 del testo restituito (UTF-8)


def _sha256(value: str | None) -> str | None:
    if type(value) is not str:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_response(raw: object) -> NormalizedResponse:
    """Applica la politica V5; la risposta originale non viene mai persa.

    L'hash della risposta originale va sempre registrato dal chiamante: da esso
    si dimostra che la risposta grezza e' rimasta quella emessa dal modello.
    """
    if type(raw) is not str:
        return NormalizedResponse(None, DEVIATION_NONE, None, None, None)
    raw_hash = _sha256(raw)
    if _FENCE_MARK not in raw:
        return NormalizedResponse(raw, DEVIATION_NONE, None, raw_hash, raw_hash)

    rejected = NormalizedResponse(
        raw, DEVIATION_REJECTED_WRAPPER, None, raw_hash, raw_hash,
    )
    # Un solo blocco: esattamente un'apertura e una chiusura.
    if raw.count(_FENCE_MARK) != 2:
        return rejected
    match = _SINGLE_FENCE.match(raw)
    if match is None:
        return rejected
    language = match.group(1)
    if language.lower() not in _ALLOWED_LANGUAGES:
        return rejected
    inner = match.group(2)
    if not inner.strip():
        return rejected
    return NormalizedResponse(
        inner, DEVIATION_SINGLE_JSON_FENCE, language or None,
        raw_hash, _sha256(inner),
    )


def apply_policy(raw: object) -> tuple[str | None, dict]:
    """Applica la politica e restituisce (testo per il parser, registro formato).

    Il registro va salvato accanto all'esito di OGNI stage con output del
    modello. Contiene la risposta originale completa, cosi' l'audit non dipende
    dal testo normalizzato.
    """
    norm = normalize_response(raw)
    record = {
        "version": VERSION,
        "policy": POLICY,
        "deviation": norm.deviation,
        "language_tag": norm.language_tag,
        "raw_sha256": norm.raw_sha256,
        "text_sha256": norm.text_sha256,
        "original_response": raw if type(raw) is str else None,
    }
    return norm.text, record


def wrap_visible_text_extractor(extract, sink: list):
    """Avvolge l'estrattore del testo visibile del messaggio finale di D.

    Chiamato dal ponte V3 una sola volta per il messaggio finale: qui la
    stessa politica dei C/K viene applicata al D. I conteggi dei blocchi non
    cambiano; cambia solo `raw_text` e solo per un singolo fence JSON.
    `extract` deve restituire una NamedTuple con campo `raw_text`.
    """
    def wrapped(content):
        visible = extract(content)
        text, record = apply_policy(visible.raw_text)
        sink.append(record)
        if record["deviation"] == DEVIATION_SINGLE_JSON_FENCE:
            return visible._replace(raw_text=text)
        return visible
    return wrapped
