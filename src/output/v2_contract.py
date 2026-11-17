"""Contratto di output OpenRCA V2 — SOLO validazione, mai riparazione.

Scopo: identico contratto per A0, A1_V2, A1-R8, A1_VERIFY e A1_VERIFY_ST.
La cardinalita' si ricava esclusivamente dalla richiesta ufficiale GT-free,
non da record.csv, query.csv, scoring_points o risultati del benchmark.

Usa intervalli [start_unix, end_unix) e timestamp locali Asia/Shanghai,
come i tool esistenti. Non fa chiamate LLM e non cambia predizioni.

Contenuto:
- `infer_requested_faults`: ricava dall'istruzione quanti guasti si chiedono (per esempio "two failures" -> 2);
- `validate_openrca_v2`: valida la risposta (schema, numero di guasti, istanti dentro la finestra) e
  solleva un errore al primo problema;
- `audit_openrca_v2`: come la precedente ma non solleva errori: restituisce un resoconto con ogni controllo.
"""
from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from output.openrca_contract import (
    Diagnosis,
    OutputContractError,
    parse_openrca_json,
)

# Fuso orario degli istanti scritti dall'agente (ora locale cinese, come nei dati del benchmark).
_SHANGHAI = ZoneInfo("Asia/Shanghai")
# Cerca nell'istruzione espressioni come "two failures", "a single fault", "3 distinct faults": un numero
# (in lettere o in cifre) o l'articolo "a/an", seguito da "failure/fault" (anche al plurale).
_COUNT = re.compile(
    r"\b(?P<amount>one|two|three|four|single|1|2|3|4|a|an)"
    r"\s+(?:(?:single|distinct|separate)\s+)?"
    r"(?P<noun>failures?|faults?)\b",
    re.IGNORECASE,
)
# Parole che indicano un numero preciso; "a"/"an" restano fuori perché sono solo un articolo indefinito.
_UNAMBIGUOUS = {
    "one": 1, "single": 1, "1": 1,
    "two": 2, "2": 2,
    "three": 3, "3": 3,
    "four": 4, "4": 4,
}


def infer_requested_faults(instruction: str) -> int | None:
    """Numero esplicito dall'istruzione. Nessuna inferenza dalle etichette.

    I riferimenti indefiniti ('a failure') sono considerati una richiesta
    di un guasto SOLO se non compare un numero esplicito. Se la richiesta
    contiene numeri espliciti incompatibili, blocchiamo la validazione.

    Restituisce il numero di guasti richiesti oppure None se l'istruzione non lo indica.
    """
    if not isinstance(instruction, str) or not instruction.strip():
        raise OutputContractError("Istruzione ufficiale mancante")
    # Tutte le espressioni "numero + guasto" trovate nell'istruzione.
    mentions = list(_COUNT.finditer(instruction))
    # Numeri espliciti distinti: se ce n'è più d'uno l'istruzione è ambigua.
    explicit = {
        _UNAMBIGUOUS[match.group("amount").lower()]
        for match in mentions
        if match.group("amount").lower() in _UNAMBIGUOUS
    }
    if len(explicit) > 1:
        raise OutputContractError(
            "Cardinalita' ambigua: numeri di guasti espliciti incompatibili"
        )
    # Un solo numero esplicito: è quello richiesto.
    if explicit:
        return next(iter(explicit))
    # Nessun numero ma un articolo indefinito ("a failure"): si intende un guasto.
    if any(m.group("amount").lower() in {"a", "an"} for m in mentions):
        return 1
    # Nessuna indicazione.
    return None


def validate_openrca_v2(
    raw_response: str,
    *,
    instruction: str,
    start_unix: int,
    end_unix: int,
    require_explicit_cardinality: bool = True,
) -> Diagnosis:
    """Valida forma, schema, cardinalita' e finestra: NON cambia l'output.

    Il numero di guasti deriva dalla SOLA istruzione visibile all'agente.
    Un output conforme non implica una diagnosi corretta sul piano causale.

    Argomenti:
      raw_response                  risposta JSON dell'agente.
      instruction                   istruzione ufficiale visibile all'agente (da cui si ricava il numero di guasti).
      start_unix, end_unix          finestra ufficiale [start, end), in secondi unix.
      require_explicit_cardinality  se True l'istruzione deve indicare il numero di guasti, altrimenti errore.

    Restituisce la `Diagnosis` validata; solleva `OutputContractError` al primo problema.
    """
    # Finestra valida: interi veri (i booleani sono esclusi) con start < end.
    if (
        type(start_unix) is not int
        or type(end_unix) is not int
        or start_unix >= end_unix
    ):
        raise OutputContractError("Finestra Unix non valida")
    # Numero di guasti richiesto, ricavato solo dall'istruzione.
    expected = infer_requested_faults(instruction)
    if expected is None and require_explicit_cardinality:
        raise OutputContractError(
            "Numero di guasti non ricavabile univocamente dall'istruzione"
        )

    # Schema e numero di guasti, controllati dal parser canonico.
    diagnosis = parse_openrca_json(raw_response, expected_faults=expected)
    # Ogni istante, convertito da ora locale di Shanghai a secondi unix, deve cadere in [start, end).
    for index, fault in enumerate(diagnosis.root_causes, 1):
        # Il parser canonico ha gia' verificato il formato della stringa.
        local = datetime.strptime(
            fault.occurrence_datetime, "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=_SHANGHAI)
        unix = local.timestamp()
        if not (start_unix <= unix < end_unix):
            raise OutputContractError(
                f"Guasto {index}: timestamp fuori dall'intervallo ufficiale"
            )
    return diagnosis


def audit_openrca_v2(
    raw_response: str | None,
    *,
    instruction: str,
    start_unix: int,
    end_unix: int,
) -> dict:
    """Audit multilivello: JSON/schema/cardinalita' separati dal vincolo temporale.

    'valid' mantiene la definizione V2 originale (tutti i controlli).
    'schema_cardinality_valid' NON comporta che il timestamp sia nella finestra.
    Gli istanti fuori finestra non vengono mai modificati o normalizzati.

    La finestra diagnostica e' un controllo interno di plausibilita':
    il benchmark non e' stato ancora dimostrato richiederla in ogni caso.

    Argomenti: gli stessi di `validate_openrca_v2` (la risposta può essere None).

    Restituisce un dizionario con: `valid`, `reason` (motivo del rifiuto, se c'è), numero di guasti
    attesi e trovati, `schema_cardinality_valid`, `timestamp_in_window` ed elenco dei guasti fuori
    finestra (`temporal_outliers`), con la distanza in secondi dal confine più vicino.
    """
    # Esito iniziale "non valido"; i campi si riempiono man mano che i controlli vanno a buon fine.
    result = {
        "valid": False,
        "reason": None,
        "expected_faults": None,
        "diagnosed_faults": None,
        "schema_cardinality_valid": False,
        "timestamp_in_window": None,
        "temporal_outliers": [],
    }
    # Ogni errore previsto viene catturato in fondo e scritto in `reason`: l'audit non solleva eccezioni.
    try:
        # 1. Finestra valida.
        if (
            type(start_unix) is not int
            or type(end_unix) is not int
            or start_unix >= end_unix
        ):
            raise OutputContractError("Finestra Unix non valida")
        # 2. Numero di guasti richiesto dall'istruzione (obbligatorio in questo audit).
        expected = infer_requested_faults(instruction)
        result["expected_faults"] = expected
        if expected is None:
            raise OutputContractError(
                "Numero di guasti non ricavabile univocamente dall'istruzione"
            )
        # 3. Schema e numero di guasti.
        diagnosis = parse_openrca_json(raw_response, expected_faults=expected)
        result["schema_cardinality_valid"] = True
        result["diagnosed_faults"] = len(diagnosis.root_causes)
        # 4. Istanti dentro la finestra: quelli fuori vengono elencati senza essere modificati.
        for index, fault in enumerate(diagnosis.root_causes, 1):
            instant = int(datetime.strptime(
                fault.occurrence_datetime, "%Y-%m-%d %H:%M:%S"
            ).replace(tzinfo=_SHANGHAI).timestamp())
            if instant < start_unix or instant >= end_unix:
                result["temporal_outliers"].append({
                    "fault_index": index,
                    "reported_local_datetime": fault.occurrence_datetime,
                    "signed_seconds_from_nearest_boundary": (
                        instant - start_unix
                        if instant < start_unix else instant - end_unix
                    ),
                    "position": "before_start" if instant < start_unix
                                else "at_or_after_end",
                })
        # 5. Esito finale: valido solo se nessun istante è fuori finestra.
        result["timestamp_in_window"] = not result["temporal_outliers"]
        if not result["timestamp_in_window"]:
            first = result["temporal_outliers"][0]["fault_index"]
            raise OutputContractError(
                f"Guasto {first}: timestamp fuori dall'intervallo ufficiale"
            )
        result["valid"] = True
    except (OutputContractError, ValueError, TypeError) as exc:
        result["reason"] = f"{type(exc).__name__}: {exc}"
    return result
