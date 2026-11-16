"""RQ2-V5: politica di retry unica, dichiarata PRIMA del run scientifico.

Motivo (pilota del 16 novembre 2026): il K di Gemini A0 e' finito in
PROVIDER_ERROR (0 token, nessuna risposta); rifatto 3 volte con lo STESSO
input e' riuscito 3 volte su 3. Un errore di trasporto senza risposta non
contiene informazione sul modello: perdere la cella per questo falserebbe il
confronto.

Regola (identica per tutti i modelli, stessa configurazione, stesso input):
- al massimo UN secondo tentativo per stage, dentro lo stesso claim;
- solo se il primo tentativo e' un errore di TRASPORTO senza alcun output del
  modello. Mai su INVALID_OUTPUT, mai su RECEIPT_REJECTED, mai su errori che
  dipendono dal comportamento del modello (tool durante la finalizzazione,
  budget di round esaurito, risposta vuota, ricorsione del grafo);
- il primo tentativo resta SEMPRE nel record (errore, durata, token): non si
  cancella e non si sovrascrive;
- se anche il secondo fallisce, l'esito finale e' PROVIDER_ERROR.

Solo funzioni pure (stdlib): nessun SDK, nessuna API.
"""
from __future__ import annotations

import time

RETRY_POLICY = "rq2_v5_one_transport_retry_v1"
MAX_ATTEMPTS = 2
RETRY_PAUSE_SECONDS = 10

# Errori del grafo di D che nascono dal comportamento del modello: non si
# ritentano (ritentarli significherebbe selezionare sul comportamento).
D_MODEL_BEHAVIOR_ERRORS = frozenset({
    "AgentBudgetExhausted",
    "AgentFinalizationEmpty",
    "VerifyFinalizationToolCall",
    "VerifyFinalizationEmpty",
    "EmptyFinalResponse",
    "GraphRecursionError",
})


def error_type(text: object) -> str | None:
    """Nome del tipo dell'errore da 'Tipo: messaggio' (solo il nome)."""
    if type(text) is not str or not text.strip():
        return None
    return text.split(":", 1)[0].strip()[:120]


def d_error_is_transport(error: object) -> bool:
    """D: errore del grafo senza risposta e non dovuto al comportamento del modello."""
    name = error_type(error)
    return name is not None and name not in D_MODEL_BEHAVIOR_ERRORS


def ck_error_is_transport(call: dict) -> bool:
    """C/K: eccezione sollevata dalla chiamata al provider, senza risposta.

    SDK_CONSTRUCTION_ERROR (deterministico) e PROTOCOL_ERROR (il modello ha
    risposto in modo non ammesso) NON sono errori di trasporto.
    """
    error = call.get("provider_error") if type(call) is dict else None
    return (
        type(error) is str
        and error.startswith("PROVIDER_ERROR:")
        and call.get("raw_response") is None
    )


def run_with_one_retry(attempt, *, sleep=time.sleep,
                       pause: float = RETRY_PAUSE_SECONDS) -> dict:
    """Esegue `attempt(n)` (n = 1, 2) e applica la politica.

    `attempt(n)` restituisce (outcome, retriable, summary): `outcome` e' il
    dizionario dell'esecutore, `retriable` dice se l'esito e' un errore di
    trasporto, `summary` e' un dizionario JSON-serializzabile da conservare.
    Restituisce l'esito dell'ULTIMO tentativo con, in provenance["retry"], la
    storia di tutti i tentativi.
    """
    attempts: list[dict] = []
    outcome: dict | None = None
    for number in range(1, MAX_ATTEMPTS + 1):
        outcome, retriable, summary = attempt(number)
        if retriable and outcome.get("status") != "PROVIDER_ERROR":
            raise ValueError("Retry ammesso solo per PROVIDER_ERROR")
        attempts.append({"attempt": number, "status": outcome.get("status"),
                         **summary})
        if not retriable or number == MAX_ATTEMPTS:
            break
        sleep(pause)
    provenance = dict(outcome.get("provenance") or {})
    provenance["retry"] = {
        "policy": RETRY_POLICY, "max_attempts": MAX_ATTEMPTS,
        "attempts": attempts,
    }
    return {**outcome, "provenance": provenance}
