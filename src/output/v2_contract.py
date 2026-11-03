"""Contratto di output OpenRCA V2 — SOLO validazione, mai riparazione.

Scopo: identico contratto per A0, A1_V2, A1-R8, A1_VERIFY e A1_VERIFY_ST.
La cardinalita' si ricava esclusivamente dalla richiesta ufficiale GT-free,
non da record.csv, query.csv, scoring_points o risultati del benchmark.

Usa intervalli [start_unix, end_unix) e timestamp locali Asia/Shanghai,
come i tool esistenti. Non fa chiamate LLM e non cambia predizioni.
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

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_COUNT = re.compile(
    r"\b(?P<amount>one|two|three|four|single|1|2|3|4|a|an)"
    r"\s+(?:(?:single|distinct|separate)\s+)?"
    r"(?P<noun>failures?|faults?)\b",
    re.IGNORECASE,
)
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
    """
    if not isinstance(instruction, str) or not instruction.strip():
        raise OutputContractError("Istruzione ufficiale mancante")
    mentions = list(_COUNT.finditer(instruction))
    explicit = {
        _UNAMBIGUOUS[match.group("amount").lower()]
        for match in mentions
        if match.group("amount").lower() in _UNAMBIGUOUS
    }
    if len(explicit) > 1:
        raise OutputContractError(
            "Cardinalita' ambigua: numeri di guasti espliciti incompatibili"
        )
    if explicit:
        return next(iter(explicit))
    if any(m.group("amount").lower() in {"a", "an"} for m in mentions):
        return 1
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
    """
    if (
        type(start_unix) is not int
        or type(end_unix) is not int
        or start_unix >= end_unix
    ):
        raise OutputContractError("Finestra Unix non valida")
    expected = infer_requested_faults(instruction)
    if expected is None and require_explicit_cardinality:
        raise OutputContractError(
            "Numero di guasti non ricavabile univocamente dall'istruzione"
        )

    diagnosis = parse_openrca_json(raw_response, expected_faults=expected)
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
    """
    result = {
        "valid": False,
        "reason": None,
        "expected_faults": None,
        "diagnosed_faults": None,
        "schema_cardinality_valid": False,
        "timestamp_in_window": None,
        "temporal_outliers": [],
    }
    try:
        if (
            type(start_unix) is not int
            or type(end_unix) is not int
            or start_unix >= end_unix
        ):
            raise OutputContractError("Finestra Unix non valida")
        expected = infer_requested_faults(instruction)
        result["expected_faults"] = expected
        if expected is None:
            raise OutputContractError(
                "Numero di guasti non ricavabile univocamente dall'istruzione"
            )
        diagnosis = parse_openrca_json(raw_response, expected_faults=expected)
        result["schema_cardinality_valid"] = True
        result["diagnosed_faults"] = len(diagnosis.root_causes)
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
