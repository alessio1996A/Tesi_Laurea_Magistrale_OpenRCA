"""Contratto canonico di diagnosi RCA, indipendente dal provider LLM.

Non esegue inferenze, non usa telemetria e non consulta ground truth.
Lo schema interno e' deliberatamente piu' severo del parser storico:
le risposte storiche rimangono inalterate e devono essere valutate con
il loro parser e protocollo originali.

Formato atteso della risposta dell'agente: un oggetto JSON con chiavi "1", "2", ... (una per guasto), ognuna
con esattamente tre campi: "root cause occurrence datetime", "root cause component", "root cause reason".

Contenuto: i tipi `RootCause` e `Diagnosis`, il parser `parse_openrca_json` (valida senza riparare)
e il serializzatore `serialize_openrca_json`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime


class OutputContractError(ValueError):
    """Risposta non conforme al contratto canonico OpenRCA."""


# Nomi dei tre campi che ogni guasto deve avere, né più né meno.
OPENRCA_FIELDS = frozenset({
    "root cause occurrence datetime",
    "root cause component",
    "root cause reason",
})

# Formato canonico dell'istante del guasto, per esempio "2022-03-20 09:30:00".
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _check_text(value: object, field: str) -> str:
    """Controlla che il valore sia una stringa non vuota; la restituisce, altrimenti solleva l'errore."""
    if not isinstance(value, str) or not value.strip():
        raise OutputContractError(f"Campo obbligatorio non testuale o vuoto: {field}")
    return value


def _check_timestamp(value: object) -> str:
    """Controlla che il valore sia un istante nel formato canonico `YYYY-MM-DD HH:MM:SS`."""
    timestamp = _check_text(value, "root cause occurrence datetime")
    try:
        parsed = datetime.strptime(timestamp, DATETIME_FORMAT)
    except ValueError as exc:
        raise OutputContractError("Timestamp non valido: YYYY-MM-DD HH:MM:SS") from exc
    # Rilettura e riscrittura devono dare la stessa stringa: scarta forme tollerate da strptime
    # (per esempio senza zero iniziale) che non sono canoniche.
    if parsed.strftime(DATETIME_FORMAT) != timestamp:
        raise OutputContractError("Timestamp non nel formato canonico")
    # Timestamp locali OpenRCA: l'interpretazione del fuso e' competenza
    # dell'adapter del benchmark, non del contratto provider-agnostic.
    return timestamp


@dataclass(frozen=True)
class RootCause:
    """Un singolo guasto diagnosticato: quando è avvenuto, su quale componente e di che tipo.

    Immutabile (`frozen`): i valori vengono controllati alla creazione e non cambiano più.
    """
    occurrence_datetime: str
    component: str
    reason: str

    def __post_init__(self) -> None:
        """Controlla i tre campi subito dopo la creazione dell'oggetto."""
        _check_timestamp(self.occurrence_datetime)
        _check_text(self.component, "root cause component")
        _check_text(self.reason, "root cause reason")


@dataclass(frozen=True)
class Diagnosis:
    """Diagnosi completa: una sequenza non vuota di guasti (`RootCause`), nell'ordine dichiarato."""
    root_causes: tuple[RootCause, ...]

    def __post_init__(self) -> None:
        """Controlla che sia una tupla non vuota di oggetti `RootCause`."""
        if not isinstance(self.root_causes, tuple) or not self.root_causes:
            raise OutputContractError("La diagnosi deve contenere almeno un guasto")
        if any(not isinstance(root, RootCause) for root in self.root_causes):
            raise OutputContractError("I guasti devono essere oggetti RootCause")


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    """Costruisce un dizionario dalle coppie chiave/valore del JSON e rifiuta le chiavi ripetute.

    `json.loads` di norma tiene l'ultimo valore di una chiave duplicata senza avvisare: qui invece è un errore.
    """
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

    Argomenti:
      raw_response     testo JSON della risposta dell'agente.
      expected_faults  numero di guasti richiesti dall'istruzione (None = non controllare il numero).

    Restituisce la `Diagnosis`; solleva `OutputContractError` al primo problema trovato.

    Passi: (1) controllo degli argomenti; (2) lettura del JSON senza chiavi duplicate; (3) chiavi dei
    guasti consecutive da "1"; (4) numero di guasti atteso; (5) ogni guasto ha esattamente i tre campi.
    """
    # --- 1. Controllo degli argomenti.
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise OutputContractError("Risposta assente o non testuale")
    if expected_faults is not None and (
        type(expected_faults) is not int or expected_faults < 1
    ):
        raise OutputContractError("expected_faults deve essere un intero positivo")

    # --- 2. Lettura del JSON: nessuna riparazione, nessuna chiave duplicata.
    try:
        payload = json.loads(raw_response, object_pairs_hook=_no_duplicate_keys)
    except (json.JSONDecodeError, TypeError) as exc:
        raise OutputContractError("Risposta non analizzabile come JSON") from exc

    if not isinstance(payload, dict) or not payload:
        raise OutputContractError("La risposta deve essere un oggetto JSON non vuoto")

    # --- 3. Con N guasti le chiavi devono essere esattamente "1", "2", ..., "N".
    count = len(payload)
    valid_keys = {str(i) for i in range(1, count + 1)}
    if set(payload) != valid_keys:
        raise OutputContractError("Le chiavi dei guasti devono essere consecutive da '1'")

    # --- 4. Numero di guasti uguale a quello richiesto dall'istruzione, se noto.
    if expected_faults is not None and count != expected_faults:
        raise OutputContractError(
            f"Cardinalita' differente dall'istruzione: {count} != {expected_faults}"
        )

    # --- 5. Ogni guasto deve essere un oggetto con i tre campi richiesti, né più né meno;
    # il controllo del contenuto dei campi è fatto da `RootCause`.
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
    """Serializza in modo deterministico nel formato numerato OpenRCA.

    Restituisce una stringa JSON compatta (senza spazi), con le chiavi "1", "2", ... nell'ordine dei guasti.
    """
    if not isinstance(diagnosis, Diagnosis):
        raise OutputContractError("Oggetto Diagnosis richiesto")
    # Dizionario numerato da 1; `ensure_ascii=False` mantiene i caratteri non ASCII così come sono.
    payload = {
        str(index): {
            "root cause occurrence datetime": fault.occurrence_datetime,
            "root cause component": fault.component,
            "root cause reason": fault.reason,
        }
        for index, fault in enumerate(diagnosis.root_causes, start=1)
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
