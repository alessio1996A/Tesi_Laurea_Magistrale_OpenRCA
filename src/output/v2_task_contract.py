"""Validazione OpenRCA V2.4 task-aware, SENZA lettura di etichette.

Le sette task richiedono sottoinsiemi noti di tre campi. Seguiamo il
contratto ufficiale: i campi EXTRA non sostituiscono quelli richiesti,
ma non invalidano la risposta per la sola loro presenza.

- vincoli obbligatori: JSON, chiavi numerate, campi richiesti, numero guasti
- finestra della telemetria: solo AVVERTIMENTO sulla data prevista
- ordine cronologico per guasti multipli: controllo diagnostico separato
- non corregge/ritenta/inventa dati, nessuna API o scorer
"""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from output.openrca_contract import OutputContractError, _no_duplicate_keys
from output.v2_contract import infer_requested_faults

TIME = "root cause occurrence datetime"
COMPONENT = "root cause component"
REASON = "root cause reason"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
SHANGHAI = ZoneInfo("Asia/Shanghai")
TASK_REQUIRED_FIELDS = {
    "task_1": (TIME,),
    "task_2": (REASON,),
    "task_3": (COMPONENT,),
    "task_4": (TIME, REASON),
    "task_5": (TIME, COMPONENT),
    "task_6": (COMPONENT, REASON),
    "task_7": (TIME, COMPONENT, REASON),
}


def _parse_time(value: object) -> int:
    if not isinstance(value, str) or not value.strip():
        raise OutputContractError("Timestamp richiesto vuoto o non testuale")
    try:
        instant = datetime.strptime(value, TIME_FORMAT)
    except ValueError as exc:
        raise OutputContractError("Timestamp non canonico YYYY-MM-DD HH:MM:SS") from exc
    if instant.strftime(TIME_FORMAT) != value:
        raise OutputContractError("Timestamp non canonico YYYY-MM-DD HH:MM:SS")
    return int(instant.replace(tzinfo=SHANGHAI).timestamp())


def audit_task_output(
    raw_response: str | None,
    *,
    task_index: str,
    instruction: str,
    start_unix: int,
    end_unix: int,
) -> dict:
    """Risultato serializzabile, senza il contenuto della risposta grezza.

    'valid': JSON riconosciuto e campi richiesti (con cardinalita') presenti.
    Non e' una misura di accuratezza o di conformita' allo scorer esatto.
    'timestamp_in_window': diagnostico; None se nessun timestamp analizzabile.
    """
    result = {
        "contract": "openrca_v2_task_aware_v1",
        "valid": False,
        "error": None,
        "task_index": task_index,
        "required_fields": None,
        "expected_faults": None,
        "diagnosed_faults": None,
        "timestamp_in_window": None,
        "temporal_outliers": [],
        "chronological_order": None,
        "extra_fields": [],
    }
    try:
        fields = TASK_REQUIRED_FIELDS.get(task_index)
        if fields is None:
            raise OutputContractError(f"Task non riconosciuto: {task_index}")
        result["required_fields"] = list(fields)
        if (
            type(start_unix) is not int
            or type(end_unix) is not int
            or start_unix >= end_unix
        ):
            raise OutputContractError("Finestra di telemetria non valida")
        faults = infer_requested_faults(instruction)
        if faults is None:
            raise OutputContractError("Cardinalita' non esplicita nella richiesta")
        result["expected_faults"] = faults
        if not isinstance(raw_response, str) or not raw_response.strip():
            raise OutputContractError("Risposta vuota o non testuale")
        try:
            parsed = json.loads(
                raw_response, object_pairs_hook=_no_duplicate_keys,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    OutputContractError(f"JSON non finito: {value}")
                ),
            )
        except (json.JSONDecodeError, TypeError) as exc:
            raise OutputContractError("JSON non analizzabile") from exc
        if not isinstance(parsed, dict) or not parsed:
            raise OutputContractError("Oggetto JSON numerato non vuoto richiesto")
        count = len(parsed)
        result["diagnosed_faults"] = count
        if set(parsed) != {str(i) for i in range(1, count + 1)}:
            raise OutputContractError("Indici guasti non consecutivi da '1'")
        if count != faults:
            raise OutputContractError(
                f"Numero di guasti diverso dalla richiesta: {count} != {faults}"
            )

        timestamps = []
        unknown_fields = set()
        for index in range(1, count + 1):
            item = parsed[str(index)]
            if not isinstance(item, dict):
                raise OutputContractError(f"Guasto {index}: oggetto richiesto")
            missing = set(fields) - set(item)
            if missing:
                raise OutputContractError(
                    f"Guasto {index}: campi richiesti mancanti: {sorted(missing)}"
                )
            for field in fields:
                value = item[field]
                if field == TIME:
                    _parse_time(value)
                elif not isinstance(value, str) or not value.strip():
                    raise OutputContractError(
                        f"Guasto {index}: campo {field} non testuale o vuoto"
                    )
            unknown_fields.update(set(item) - set(fields))
            # Il timestamp puo' essere EXTRA e venire ignorato dallo scorer.
            # Se presente e valido, lo usiamo per segnalare fuori finestra.
            if TIME in item:
                try:
                    unix = _parse_time(item[TIME])
                except OutputContractError:
                    if TIME in fields:
                        raise
                    timestamps.append(None)
                else:
                    timestamps.append(unix)
                    if unix < start_unix or unix >= end_unix:
                        result["temporal_outliers"].append({
                            "fault_index": index,
                            "position": (
                                "before_start" if unix < start_unix
                                else "at_or_after_end"
                            ),
                            "signed_seconds_from_nearest_boundary": (
                                unix - start_unix if unix < start_unix
                                else unix - end_unix
                            ),
                        })
            else:
                timestamps.append(None)
        if any(t is not None for t in timestamps):
            result["timestamp_in_window"] = not result["temporal_outliers"]
        if len(timestamps) >= 2 and all(t is not None for t in timestamps):
            result["chronological_order"] = (
                timestamps == sorted(timestamps)
            )
        result["extra_fields"] = sorted(unknown_fields)
        result["valid"] = True
    except (OutputContractError, ValueError, TypeError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def task_output_instruction(*, task_index: str, instruction: str) -> str:
    """Istruzioni aggiuntive uniformi per le cinque varianti in V2 enforce.

    Si ricavano SOLO da task_index e dalla richiesta GT-free.
    Da usare in una campagna V2 dichiarata, non nei run storici.
    """
    fields = TASK_REQUIRED_FIELDS.get(task_index)
    if fields is None:
        raise OutputContractError(f"Task non riconosciuto: {task_index}")
    n = infer_requested_faults(instruction)
    if n is None:
        raise OutputContractError("Numero di guasti mancante nella richiesta")
    field_names = ", ".join(fields)
    return (
        "\n\nV2 TASK-SPECIFIC OUTPUT CONTRACT (takes precedence over the "
        "generic three-field example above):\n"
        f"Return exactly {n} numbered root-cause entries, starting at '1'.\n"
        f"For this task ({task_index}), the required fields are: {field_names}.\n"
        "Use only these fields unless additional fields are independently "
        "supported by observed evidence. Never fabricate missing fields.\n"
        "If a datetime is requested, format it as Asia/Shanghai "
        "YYYY-MM-DD HH:MM:SS. Do not confuse telemetry search limits "
        "with certainty about fault onset.\n"
        "Return only a JSON object, no Markdown or explanations."
    )


def enforce_task_output(
    raw_response: str | None,
    *,
    task_index: str,
    instruction: str,
    start_unix: int,
    end_unix: int,
) -> tuple[str | None, str, dict]:
    """Applica il contratto senza retry e senza cambiare valori del modello.

    La predizione viene ricodificata come JSON solo se valida. Nessun
    timestamp viene riscritto; un valore fuori finestra resta segnalato.
    """
    audit = audit_task_output(
        raw_response,
        task_index=task_index,
        instruction=instruction,
        start_unix=start_unix,
        end_unix=end_unix,
    )
    if not audit["valid"]:
        return None, f"invalid_v2_task_output: {audit['error']}", audit
    # OpenRCA richiede che i guasti multipli siano numerati in ordine
    # cronologico. Non riordiniamo le risposte originali automaticamente.
    if (
        TIME in audit["required_fields"]
        and audit["chronological_order"] is False
    ):
        audit["valid"] = False
        audit["error"] = "Guasti multipli non in ordine cronologico"
        return None, "invalid_v2_task_output: ordine cronologico", audit
    parsed = json.loads(raw_response, object_pairs_hook=_no_duplicate_keys)
    return (
        json.dumps(parsed, ensure_ascii=False, allow_nan=False),
        "valid_json",
        audit,
    )
