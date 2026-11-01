"""Contratto canonico di diagnosi RCA, indipendente dal provider LLM.

Non esegue inferenze, non usa telemetria e non consulta ground truth.
Lo schema interno e' deliberatamente piu' severo del parser storico:
le risposte storiche rimangono inalterate e devono essere valutate con
il loro parser e protocollo originali.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime


class OutputContractError(ValueError):
    """Risposta non conforme al contratto canonico OpenRCA."""


OPENRCA_FIELDS = frozenset({
    "root cause occurrence datetime",
    "root cause component",
    "root cause reason",
})

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _check_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OutputContractError(f"Campo obbligatorio non testuale o vuoto: {field}")
    return value


def _check_timestamp(value: object) -> str:
    timestamp = _check_text(value, "root cause occurrence datetime")
    try:
        parsed = datetime.strptime(timestamp, DATETIME_FORMAT)
    except ValueError as exc:
        raise OutputContractError("Timestamp non valido: YYYY-MM-DD HH:MM:SS") from exc
    if parsed.strftime(DATETIME_FORMAT) != timestamp:
        raise OutputContractError("Timestamp non nel formato canonico")
    # Timestamp locali OpenRCA: l'interpretazione del fuso e' competenza
    # dell'adapter del benchmark, non del contratto provider-agnostic.
    return timestamp


@dataclass(frozen=True)
class RootCause:
    occurrence_datetime: str
    component: str
    reason: str

    def __post_init__(self) -> None:
        _check_timestamp(self.occurrence_datetime)
        _check_text(self.component, "root cause component")
        _check_text(self.reason, "root cause reason")


@dataclass(frozen=True)
class Diagnosis:
    root_causes: tuple[RootCause, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.root_causes, tuple) or not self.root_causes:
            raise OutputContractError("La diagnosi deve contenere almeno un guasto")
        if any(not isinstance(root, RootCause) for root in self.root_causes):
            raise OutputContractError("I guasti devono essere oggetti RootCause")


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise OutputContractError(f"Chiave JSON duplicata: {key}")
        result[key] = value
    return result


def parse_openrca_json(
    raw_response: str,
    *,
    expected_faults: int | None = None,
) -> Diagnosis:
    """Valida una risposta JSON *grezza* senza ripararla.

    La cardinalita' e' opzionale e deve arrivare soltanto
    dall'istruzione visibile all'agente, MAI dallo scoring_points.
    Non modifica l'input, non esegue retry e non corregge diagnosi.
    """
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise OutputContractError("Risposta assente o non testuale")
    if expected_faults is not None and (
        type(expected_faults) is not int or expected_faults < 1
    ):
        raise OutputContractError("expected_faults deve essere un intero positivo")

    try:
        payload = json.loads(raw_response, object_pairs_hook=_no_duplicate_keys)
    except (json.JSONDecodeError, TypeError) as exc:
        raise OutputContractError("Risposta non analizzabile come JSON") from exc

    if not isinstance(payload, dict) or not payload:
        raise OutputContractError("La risposta deve essere un oggetto JSON non vuoto")

    count = len(payload)
    valid_keys = {str(i) for i in range(1, count + 1)}
    if set(payload) != valid_keys:
        raise OutputContractError("Le chiavi dei guasti devono essere consecutive da '1'")

    if expected_faults is not None and count != expected_faults:
        raise OutputContractError(
            f"Cardinalita' differente dall'istruzione: {count} != {expected_faults}"
        )

    faults = []
    for index in range(1, count + 1):
        item = payload[str(index)]
        if not isinstance(item, dict):
            raise OutputContractError(f"Guasto {index}: oggetto JSON richiesto")

        present = set(item)
        if present != OPENRCA_FIELDS:
            missing = sorted(OPENRCA_FIELDS - present)
            extra = sorted(present - OPENRCA_FIELDS)
            raise OutputContractError(
                f"Guasto {index}: campi mancanti={missing}; aggiuntivi={extra}"
            )

        faults.append(RootCause(
            occurrence_datetime=item["root cause occurrence datetime"],
            component=item["root cause component"],
            reason=item["root cause reason"],
        ))
    return Diagnosis(tuple(faults))


def serialize_openrca_json(diagnosis: Diagnosis) -> str:
    """Serializza in modo deterministico nel formato numerato OpenRCA."""
    if not isinstance(diagnosis, Diagnosis):
        raise OutputContractError("Oggetto Diagnosis richiesto")
    payload = {
        str(index): {
            "root cause occurrence datetime": fault.occurrence_datetime,
            "root cause component": fault.component,
            "root cause reason": fault.reason,
        }
        for index, fault in enumerate(diagnosis.root_causes, start=1)
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
