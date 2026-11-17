"""RQ2-V4: validazione D task-aware, GT-free, senza API né scritture.

Questo è un NUOVO criterio per la futura release V4. RQ1, V2 e V3 sono
congelate: non modifica i risultati o gli status delle vecchie release.

Il contratto D è quello effettivamente usato da run_experiment con
output_contract_mode='v2_enforce': ciascun task_1..task_7 richiede solo
il proprio sottoinsieme di datetime/component/reason. Il controllo storico
del ledger V2/V3 impone erroneamente tutti e tre i campi per ogni task.

L'esito formale non certifica accuratezza causale né trasferimento K.
Questa versione rifiuta audit incoerenti, duplicate keys, cardinalità
non verificata e prove di provenance mancanti. Nessun repair o retry.

Contenuto
---------
- `AUDIT_CONTRACT`, `AUDIT_FIELDS`: nome del contratto e campi esatti del suo audit;
- `V4DTaskAwareBlocked`: errore "output D non dimostrabilmente conforme al task";
- `_reject_constant`: rifiuta le costanti JSON non finite (NaN, Infinity);
- `validate_v4_d_task_aware`: convalida struttura e audit di un run D, senza ground truth;
- `classify_v4_d`: stato formale di D (RECORDED_COMPLETE oppure INVALID_OUTPUT);
- `require_v4_d_status`: rilettura, con lo stesso identico classificatore.
"""
from __future__ import annotations

import json

from output.openrca_contract import OutputContractError, _no_duplicate_keys
from output.v2_task_contract import TASK_REQUIRED_FIELDS, TIME, _parse_time
from evaluation.rq2_v2_unified_provenance_gate import (
    UnifiedRQ2ProvenanceError, audit_captured_v2_d,
)

VERSION = "rq2_v4_d_task_aware_contract_v0"
# Nome del contratto registrato nell'audit del run D e campi (esatti) che l'audit deve avere.
AUDIT_CONTRACT = "openrca_v2_task_aware_v1"
AUDIT_FIELDS = frozenset((
    "contract", "valid", "error", "task_index", "required_fields",
    "expected_faults", "diagnosed_faults", "timestamp_in_window",
    "temporal_outliers", "chronological_order", "extra_fields",
))


class V4DTaskAwareBlocked(ValueError):
    """Output D non dimostrabilmente conforme al task OpenRCA."""


def _reject_constant(value: str) -> None:
    """Callback di `json.loads` per `parse_constant`: rifiuta NaN, Infinity e -Infinity."""
    raise V4DTaskAwareBlocked("JSON nonfinite constant")


def validate_v4_d_task_aware(run: dict) -> dict:
    """Convalida solo struttura e audit D già registrati; nessuna GT.

    Da invocare SOLO insieme al controllo indipendente della provenance D.
    La funzione restituisce metadati, mai testo grezzo o contenuto del guasto.
    In futuro classificatore e readback DEVONO usare la stessa funzione.

    Argomento: `run`, il risultato del runner D (dizionario). Restituisce un riepilogo con
    task, campi richiesti, numero di guasti e `task_contract_valid` True. Solleva
    `V4DTaskAwareBlocked` al primo scostamento.

    Passi: 1) il run non ha errori, usa il contratto "v2_enforce" e ha JSON valido; 2) il task
    e' noto e se ne ricavano i campi richiesti; 3) l'audit ha i campi e i valori attesi;
    4) il numero di guasti e' fra 1 e 4 e coincide con quello diagnosticato; 5) risposta
    grezza e previsione canonica sono JSON senza chiavi duplicate e uguali fra loro, con
    indici 1..N; 6) ogni guasto ha i campi richiesti dal task (testi non vuoti, orari
    validi); 7) i campi extra dichiarati nell'audit sono quelli reali; 8) se il task richiede
    l'orario e i guasti sono almeno due, l'ordine e' cronologico.
    """
    if type(run) is not dict:
        raise V4DTaskAwareBlocked("D run must be dict")
    # 1. Nessun errore del runner, contratto "v2_enforce" e JSON valido.
    if (
        run.get("error") is not None
        or run.get("output_contract_mode") != "v2_enforce"
        or run.get("json_status") != "valid_json"
    ):
        raise V4DTaskAwareBlocked("D runner error or invalid task status")

    # 2. Task e campi richiesti: ogni task_1..task_7 richiede solo il proprio sottoinsieme.
    task = run.get("task_index")
    if type(task) is not str or task not in TASK_REQUIRED_FIELDS:
        raise V4DTaskAwareBlocked("Unknown task index")
    fields = TASK_REQUIRED_FIELDS[task]

    # 3. Audit del contratto presente, completo e coerente col task.
    audit = run.get("output_contract_v2")
    if (
        type(audit) is not dict or set(audit) != AUDIT_FIELDS
        or audit.get("contract") != AUDIT_CONTRACT
        or audit.get("valid") is not True
        or audit.get("error") is not None
        or audit.get("task_index") != task
        or audit.get("required_fields") != list(fields)
    ):
        raise V4DTaskAwareBlocked("Task-aware audit absent or inconsistent")

    # 4. Numero di guasti atteso (1-4) uguale a quello diagnosticato.
    expected = audit.get("expected_faults")
    if (
        type(expected) is not int or expected < 1 or expected > 4
        or type(audit.get("diagnosed_faults")) is not int
        or audit["diagnosed_faults"] != expected
    ):
        raise V4DTaskAwareBlocked("Unverified fault count")

    # 5. Risposta originale e previsione canonica: JSON valido, senza chiavi duplicate ne'
    # costanti non finite, e identici fra loro.
    raw = run.get("raw_response")
    prediction = run.get("prediction")
    if (
        type(raw) is not str or not raw.strip()
        or type(prediction) is not str or not prediction.strip()
    ):
        raise V4DTaskAwareBlocked("Missing original/canonical response")

    try:
        parsed = json.loads(
            raw, object_pairs_hook=_no_duplicate_keys,
            parse_constant=_reject_constant,
        )
        predicted = json.loads(
            prediction, object_pairs_hook=_no_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (ValueError, TypeError, RecursionError, OutputContractError) as exc:
        raise V4DTaskAwareBlocked("Noncanonical or duplicated JSON") from exc
    if (
        type(parsed) is not dict or len(parsed) != expected
        or set(parsed) != {str(i) for i in range(1, expected + 1)}
        or predicted != parsed
    ):
        raise V4DTaskAwareBlocked("Fault indexes/count or prediction mismatch")

    # 6. Campi richiesti dal task per ogni guasto; si raccolgono anche i campi extra e gli orari.
    extra = set()
    times = []
    for i in range(1, expected + 1):
        item = parsed[str(i)]
        if type(item) is not dict or not set(fields).issubset(item):
            raise V4DTaskAwareBlocked("Missing task-required fields")
        for name in fields:
            value = item[name]
            if name == TIME:
                try:
                    times.append(_parse_time(value))
                except (OutputContractError, ValueError, TypeError) as exc:
                    raise V4DTaskAwareBlocked("Bad task-required timestamp") from exc
            elif type(value) is not str or not value.strip():
                raise V4DTaskAwareBlocked("Empty/nontext task-required field")
        extra.update(set(item) - set(fields))

    # 7. I campi extra non rendono invalido un task: come nel contratto V2.4.
    if audit.get("extra_fields") != sorted(extra):
        raise V4DTaskAwareBlocked("Extra-field audit mismatch")

    # 8. Ordine cronologico degli indici, richiesto solo se il task include l'orario.
    if TIME in fields and expected >= 2:
        if times != sorted(times) or audit.get("chronological_order") is not True:
            raise V4DTaskAwareBlocked("Nonchronological fault indexes")
    elif TIME in fields and audit.get("chronological_order") is False:
        raise V4DTaskAwareBlocked("Chronology audit contradiction")

    return {
        "version": VERSION,
        "task_index": task,
        "required_fields": list(fields),
        "fault_count": expected,
        "task_contract_valid": True,
        "causal_correctness_verified": False,
        "can_execute_api": False,
        "ground_truth_read": False,
    }


def classify_v4_d(*, row: dict, run: dict) -> str:
    """CLASSIFICAZIONE V4 D: provenance + contratto task-aware.

    L'errore runner/provider va instradato separatamente a PROVIDER_ERROR,
    mai riclassificato come INVALID_OUTPUT. I due esiti formali sono
    RECORDED_COMPLETE oppure INVALID_OUTPUT.

    Argomenti (per nome): `row` (riga del piano, deve essere uno stage D) e `run` (risultato
    del runner D, senza errori). Restituisce lo stato: COMPLETO se provenienza e contratto
    task-aware sono entrambi dimostrati, altrimenti OUTPUT NON VALIDO.
    """
    if (
        type(row) is not dict or row.get("stage") != "D"
        or type(run) is not dict or run.get("error") is not None
    ):
        raise V4DTaskAwareBlocked("Not an attempted no-error D stage")
    # Identita' del braccio (caso, modello, harness) necessaria per l'audit di provenienza.
    for key in ("case_id", "logical_model", "harness"):
        if type(row.get(key)) is not str or not row[key]:
            raise V4DTaskAwareBlocked("Missing D analysis arm identity")
    try:
        audit_captured_v2_d(
            run=run, case_id=row["case_id"],
            model=row["logical_model"], harness=row["harness"],
        )
        validate_v4_d_task_aware(run)
    except (
        UnifiedRQ2ProvenanceError, V4DTaskAwareBlocked,
        KeyError, TypeError, ValueError,
    ):
        return "INVALID_OUTPUT"
    return "RECORDED_COMPLETE"


def require_v4_d_status(*, row: dict, run: dict, status: str) -> None:
    """READBACK V4: lo stesso identico classificatore, nessuna reinterpretazione.

    Verifica che lo `status` salvato (COMPLETO oppure OUTPUT NON VALIDO) coincida con quello
    che `classify_v4_d` calcola ora per `row` e `run`; altrimenti solleva `V4DTaskAwareBlocked`.
    """
    if status not in ("RECORDED_COMPLETE", "INVALID_OUTPUT"):
        raise V4DTaskAwareBlocked("Unsupported D status for task-aware readback")
    if classify_v4_d(row=row, run=run) != status:
        raise V4DTaskAwareBlocked("D stored status differs from task-aware proof")
