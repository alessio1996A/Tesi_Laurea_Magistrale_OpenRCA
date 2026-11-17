"""CANDIDATO versionato di trasporto C/K per RQ2 (NON collegato al live scientifico).

E' un successore, solo per audit, di `rq2_ck_provider_transport._one_call`:
- una sola chiamata `model.invoke`, nessun retry manuale, nessun tool, nessuna lettura di GT o scorer;
- estrazione esatta del testo visibile, uguale per tutti i provider;
- stessa struttura di ricevuta normalizzata dell'adattatore C/K esistente;
- aggiunge solo conteggi e tipo dei blocchi (non sensibili) per la futura provenienza;
- il trasporto reale con SDK NON e' autorizzato da questo modulo.

Non importarlo in G4K e non usarlo sul ledger create-only esistente.
Per qualsiasi esecuzione live con questa implementazione servono una release scientifica,
un namespace dei dati e un pin del codice distinti.

Contenuto
---------
- `_empty_usage`: risposta dell'uso di token "non osservato";
- `one_ck_call_candidate`: la chiamata singola, con tutti gli errori ridotti a codici senza testo.
"""
from __future__ import annotations

import time

from langchain_core.messages import AIMessage

from evaluation.rq2_ck_provider_transport import _usage
from evaluation.rq2_model_factory import crea_modello_rq2 as crea_modello
from evaluation.rq2_v2_ck_text_extraction_candidate import (
    CKTextExtractionBlocked,
    POLICY,
    extract_visible_ck_text,
)

VERSION = "rq2_v2_ck_provider_transport_candidate_v1"


def _empty_usage() -> dict:
    """Uso di token "non osservato": tutti i conteggi a None e `complete` False.

    E' il valore di partenza; viene sostituito da `_usage(answer)` solo se il provider
    ha restituito una risposta valida.
    """
    return {
        "complete": False,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "input_token_details": None,
        "output_token_details": None,
    }


def one_ck_call_candidate(provider: str, model_id: str, messages: list) -> dict:
    """Al piu' UNA richiesta al provider; il risultato non viene scritto in nessun ledger.

    Questo percorso NON e' volutamente chiamato dal dispatcher scientifico esistente.
    Tutti i testi delle eccezioni vengono soppressi, per non far trapelare credenziali
    contenute negli errori degli SDK. Le chiamate ambigue non si ritentano mai.

    Argomenti: `provider` ("google" o "anthropic"), `model_id` (identificativo del modello) e
    `messages` (lista dei messaggi system e user).

    Restituisce un dizionario con: testo grezzo (`raw_response`), eventuale `provider_error`
    (solo codice, mai il testo), numero di chiamate (`api_attempts`: 0 o 1), uso di token,
    motivo di arresto, modello che ha risposto, politica di estrazione e conteggi dei blocchi
    di contenuto (testo / non testo), piu' la durata.

    Passi:
      1. costruisce il modello: se fallisce, errore SDK_CONSTRUCTION_ERROR e nessuna chiamata;
      2. fa UNA `invoke` (da qui il costo e' potenzialmente gia' sostenuto);
      3. una risposta non `AIMessage`, o con tool call, e' un errore di protocollo;
      4. altrimenti estrae il testo visibile e registra motivo di arresto e modello.
    """
    started = time.monotonic()
    # Risultato iniziale: tutto "non osservato"; i campi si riempiono solo se la chiamata riesce.
    result = {
        "raw_response": None,
        "provider_error": None,
        "api_attempts": 0,
        "usage": _empty_usage(),
        "finish_reason": None,
        "provider_response_model": None,
        "content_extraction_policy": POLICY,
        "response_content_kind": "not_observed",
        "text_blocks_observed": 0,
        "nontext_blocks_observed": 0,
    }

    # 1. Costruzione del modello (nessun costo finora).
    try:
        model = crea_modello(provider, model_id)
    except Exception as exc:
        result["provider_error"] = "SDK_CONSTRUCTION_ERROR:" + type(exc).__name__
    else:
        # Un'eccezione da qui in poi puo' comunque corrispondere a una richiesta remota
        # a pagamento: non si deduce mai "costo zero" e non si ritenta automaticamente.
        result["api_attempts"] = 1
        # 2. L'unica chiamata al modello. Dell'errore si conservano solo il tipo e,
        # se c'e', il codice HTTP (mai il testo, che potrebbe contenere credenziali).
        try:
            answer = model.invoke(messages)
        except Exception as exc:
            code = getattr(exc, "status_code", None)
            result["provider_error"] = "PROVIDER_ERROR:" + type(exc).__name__
            if type(code) is int:
                result["provider_error"] += f":HTTP_{code}"
        else:
            # 3. Errori di protocollo: la risposta non e' un messaggio AI, oppure contiene
            # tool call (qui vietate: C e K non usano tool).
            if not isinstance(answer, AIMessage):
                result["provider_error"] = "PROTOCOL_ERROR:NonAIMessage"
            elif answer.tool_calls or answer.invalid_tool_calls:
                result["provider_error"] = "PROTOCOL_ERROR:ToolCallsForbidden"
                result["usage"] = _usage(answer)
            else:
                # 4. Risposta valida: uso di token e testo visibile (i blocchi che non sono
                # testo vengono solo contati, mai esposti).
                result["usage"] = _usage(answer)
                try:
                    visible = extract_visible_ck_text(answer.content)
                except CKTextExtractionBlocked:
                    result["provider_error"] = "PROTOCOL_ERROR:ContentBlockLimit"
                else:
                    result["raw_response"] = visible.raw_text
                    result["response_content_kind"] = visible.content_kind
                    result["text_blocks_observed"] = visible.text_blocks
                    result["nontext_blocks_observed"] = visible.other_blocks

                # Metadati: motivo di arresto e nome del modello, nelle due varianti dei
                # provider (`finish_reason`/`stop_reason`, `model_name`/`model`).
                meta = answer.response_metadata or {}
                reason = meta.get("finish_reason", meta.get("stop_reason"))
                name = meta.get("model_name", meta.get("model"))
                result["finish_reason"] = (
                    reason if type(reason) is str else None
                )
                result["provider_response_model"] = (
                    name if type(name) is str and len(name) <= 160 else None
                )

    # Durata totale della funzione, in secondi (anche quando c'e' stato un errore).
    result["elapsed_seconds"] = round(time.monotonic() - started, 6)
    return result
