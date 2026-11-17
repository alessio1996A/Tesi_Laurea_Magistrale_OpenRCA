"""RQ2-V5.1: normalizzazione del formato della risposta, UGUALE per tutti i modelli.

Motivo: in V4 Sonnet e Haiku hanno restituito il JSON dentro un blocco Markdown
(fence), che il parser strict rifiuta alla posizione 0, mentre Gemini ha
restituito JSON puro. Per confrontare i modelli in modo equo la politica di
formato deve essere unica, dichiarata prima dei run e senza parametri per modello.

Storia della politica (da riportare nella tesi):
- V5: dopo l'audit dei run V4, unwrap della sola risposta che e' ESATTAMENTE un
  singolo blocco ```json ... ```.
- V5.1: affinata sul PILOTA (16 novembre 2026, archivio separato, non entra nei
  risultati), dove Sonnet ha risposto con un blocco json valido seguito da un
  paragrafo di commento. Con V5 quella cella (e i suoi C e K) andava persa per
  un testo che sta FUORI dal JSON. V5.1 e' congelata prima del primo stage del
  run scientifico.

Cosa fa (e SOLO questo):
- se la risposta contiene ESATTAMENTE un blocco ```json ... ``` (oppure
  ``` ... ``` senza lingua), con la fence di apertura e di chiusura su righe
  proprie, restituisce il contenuto interno INALTERATO. Il testo fuori dal
  blocco, se c'e', viene scartato ma resta nella risposta originale registrata;
- in ogni altro caso restituisce la risposta originale senza modifiche.

Cosa NON fa: non ripara JSON, non estrae JSON da testo libero, non rimuove
spazi dentro il blocco, non riordina chiavi, non ritenta chiamate al modello.
Piu' fence, lingua diversa da json, fence non chiuso o fence sulla stessa riga
del testo e' REJECTED_WRAPPER: la risposta resta quella originale e il parser
strict la rifiutera' come prima.

Ogni risposta riceve un flag `deviation` che va registrato accanto all'esito,
cosi' il tasso di conformita' strict (nessuna deviazione) e quello tollerante
(deviazione ammessa) si riportano insieme per tutti i modelli.

Solo funzioni pure: niente SDK, API, filesystem, ground truth o dispatcher.
"""
from __future__ import annotations

import hashlib
import re
from typing import NamedTuple

# Versione del modulo e nome della politica di formato: si registrano accanto a ogni esito.
VERSION = "rq2_v5_response_normalization_v2"
POLICY = "rq2_v5_1_single_json_fence_outside_text_v1"

# Le quattro "deviazioni" possibili, cioe' il modo in cui la risposta si discosta dal JSON puro:
#   NONE                     nessun fence: la risposta e' gia' JSON puro (o comunque non ha ```), resta com'e';
#   SINGLE_JSON_FENCE        tutta la risposta e' ESATTAMENTE un blocco ```json ... ```;
#   FENCE_WITH_OUTSIDE_TEXT  un solo blocco, ma con del testo prima o dopo (politica V5.1);
#   REJECTED_WRAPPER         fence presenti ma non accettabili (piu' blocchi, lingua diversa da json, ...):
#                            la risposta resta l'originale e il parser strict la rifiutera'.
DEVIATION_NONE = "NONE"
DEVIATION_SINGLE_JSON_FENCE = "SINGLE_JSON_FENCE"
DEVIATION_FENCE_WITH_OUTSIDE_TEXT = "FENCE_WITH_OUTSIDE_TEXT"
DEVIATION_REJECTED_WRAPPER = "REJECTED_WRAPPER"
DEVIATIONS = (
    DEVIATION_NONE, DEVIATION_SINGLE_JSON_FENCE,
    DEVIATION_FENCE_WITH_OUTSIDE_TEXT, DEVIATION_REJECTED_WRAPPER,
)
# Deviazioni per cui il testo passato al parser e' il contenuto del fence.
UNWRAPPED_DEVIATIONS = (
    DEVIATION_SINGLE_JSON_FENCE, DEVIATION_FENCE_WITH_OUTSIDE_TEXT,
)

# Segno di apertura/chiusura di un blocco di codice Markdown.
_FENCE_MARK = "```"
# Lingue ammesse dopo l'apertura: nessuna (``` da solo) oppure json.
_ALLOWED_LANGUAGES = ("", "json")
# Intera risposta = spazi opzionali, apertura, riga della lingua, contenuto,
# chiusura, spazi opzionali. Il contenuto interno non viene toccato.
# Gruppo 1 = lingua dichiarata; gruppo 2 = contenuto interno (ricerca minima, fino alla chiusura).
_SINGLE_FENCE = re.compile(
    r"\A[ \t\r\n]*```([A-Za-z0-9_+-]*)[ \t]*\r?\n(.*?)\r?\n?[ \t]*```[ \t\r\n]*\Z",
    re.DOTALL,
)
# Un solo blocco con testo fuori: il testo prima deve finire a capo e la fence
# di apertura stare su riga propria; dopo la chiusura puo' esserci altro testo
# solo a partire dalla riga successiva. Il contenuto interno non viene toccato.
_FENCE_WITH_TEXT = re.compile(
    r"\A(?:.*?\n)?[ \t]*```([A-Za-z0-9_+-]*)[ \t]*\r?\n(.*?)\r?\n[ \t]*```"
    r"[ \t]*(?:\r?\n.*)?\Z",
    re.DOTALL,
)


class NormalizedResponse(NamedTuple):
    """Esito della normalizzazione: una tupla con nome, quindi immutabile (campi qui sotto)."""

    text: str | None          # testo da passare al parser strict
    deviation: str            # uno di DEVIATIONS
    language_tag: str | None  # lingua dichiarata nel fence, se presente
    raw_sha256: str | None    # SHA-256 della risposta originale (UTF-8)
    text_sha256: str | None   # SHA-256 del testo restituito (UTF-8)


def _sha256(value: str | None) -> str | None:
    """SHA-256 (esadecimale) del testo in UTF-8; None se `value` non e' una stringa."""
    if type(value) is not str:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_response(raw: object) -> NormalizedResponse:
    """Applica la politica V5; la risposta originale non viene mai persa.

    L'hash della risposta originale va sempre registrato dal chiamante: da esso
    si dimostra che la risposta grezza e' rimasta quella emessa dal modello.

    Argomenti: `raw` e' la risposta del modello (normalmente una stringa).
    Restituisce un `NormalizedResponse`.

    Passi:
      1. se `raw` non e' una stringa: nessun output (tutto None);
      2. se non c'e' nessun ``` : la risposta resta com'e' (deviazione NONE);
      3. se i ``` non sono esattamente due, o il blocco non ha la forma attesa, o la
         lingua non e' json (o vuota), o il contenuto e' vuoto: REJECTED_WRAPPER, la
         risposta resta l'originale;
      4. altrimenti si restituisce il contenuto interno del blocco, INALTERATO, con la
         deviazione SINGLE_JSON_FENCE (blocco solo) o FENCE_WITH_OUTSIDE_TEXT (con testo fuori).
    """
    # 1. Risposta assente o non testuale.
    if type(raw) is not str:
        return NormalizedResponse(None, DEVIATION_NONE, None, None, None)
    raw_hash = _sha256(raw)
    # 2. Nessun fence: nulla da fare.
    if _FENCE_MARK not in raw:
        return NormalizedResponse(raw, DEVIATION_NONE, None, raw_hash, raw_hash)

    # Risposta "scartata": il testo resta l'originale (e il parser strict la rifiutera').
    rejected = NormalizedResponse(
        raw, DEVIATION_REJECTED_WRAPPER, None, raw_hash, raw_hash,
    )
    # 3. Un solo blocco: esattamente un'apertura e una chiusura.
    if raw.count(_FENCE_MARK) != 2:
        return rejected
    # Prima si prova la forma "solo il blocco"; se non combacia, quella "blocco + testo fuori".
    deviation = DEVIATION_SINGLE_JSON_FENCE
    match = _SINGLE_FENCE.match(raw)
    if match is None:
        deviation = DEVIATION_FENCE_WITH_OUTSIDE_TEXT
        match = _FENCE_WITH_TEXT.match(raw)
    if match is None:
        return rejected
    # Lingua ammessa: nessuna oppure json (maiuscole/minuscole indifferenti).
    language = match.group(1)
    if language.lower() not in _ALLOWED_LANGUAGES:
        return rejected
    # Un blocco vuoto (solo spazi) non e' una risposta.
    inner = match.group(2)
    if not inner.strip():
        return rejected
    # 4. Contenuto interno inalterato, con gli hash dell'originale e del testo restituito.
    return NormalizedResponse(
        inner, deviation, language or None, raw_hash, _sha256(inner),
    )


def apply_policy(raw: object) -> tuple[str | None, dict]:
    """Applica la politica e restituisce (testo per il parser, registro formato).

    Il registro va salvato accanto all'esito di OGNI stage con output del
    modello. Contiene la risposta originale completa, cosi' l'audit non dipende
    dal testo normalizzato.

    Argomenti: `raw` e' la risposta del modello.
    Restituisce la coppia (testo da dare al parser strict, dizionario "registro formato"
    con versione, politica, deviazione, lingua, hash e risposta originale).
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
    cambiano; cambia solo `raw_text` e solo per un singolo fence JSON (con o senza testo fuori).
    `extract` deve restituire una NamedTuple con campo `raw_text`.

    Argomenti: `extract` (la funzione originale) e `sink` (lista in cui si accoda il
    registro formato di ogni messaggio finale). Restituisce la funzione avvolta.
    """
    def wrapped(content):
        """Chiama l'estrattore originale, registra il formato e, solo se la risposta era
        un singolo fence JSON, sostituisce `raw_text` con il contenuto interno."""
        visible = extract(content)
        text, record = apply_policy(visible.raw_text)
        sink.append(record)
        if record["deviation"] in UNWRAPPED_DEVIATIONS:
            return visible._replace(raw_text=text)
        return visible
    return wrapped
