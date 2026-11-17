"""Contratti JSON rigorosi di RQ2 per la validazione offline dell'output C/K prodotto dal LLM.

Nessun import di ground truth, dataset, provider, telemetria o runner. SOLO controlli di
struttura e di riferimento: nessuna affermazione sulla correttezza della diagnosi (RCA).
Questo modulo NON DEVE eseguire nessuno pseudocodice generato dal LLM.

Contenuto
---------
- `SCHEMA_C`, `SCHEMA_K`: nomi degli schemi della sonda delle cause (C) e della regola candidata (K);
- `ContractError`: errore "JSON sintatticamente valido ma contro lo schema";
- funzioni di supporto: `_duplicate_key_error`, `_reject_constant`, `_parse` (JSON rigoroso),
  `_keys`, `_text`, `_text_list` (forma dei campi), `_allowed_refs`, `_refs` (ID di evidenza),
  `_signals`, `_conditions` (segnali e condizioni della regola K);
- `validate_cause_probe`: valida l'output di C; `validate_candidate_rule`: valida l'output di K.
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Collection

# Nomi degli schemi: sonda C (cause) e regola candidata K.
SCHEMA_C = "rq2_cause_probe_v0"
SCHEMA_K = "rq2_candidate_rule_v0"
# Forma di un ID di evidenza (la lettera E e da 3 a 6 cifre), aggregazioni e operatori ammessi.
_EVIDENCE_RE = re.compile(r"E[0-9]{3,6}\Z")
_AGGREGATIONS = {"mean", "max", "min", "sum", "count", "p95", "last", "delta"}
_OPERATORS = {">", ">=", "<", "<=", "=="}


class ContractError(ValueError):
    """Una risposta JSON sintatticamente valida viola lo schema RQ2."""


def _duplicate_key_error(pairs: list[tuple[str, object]]) -> dict:
    """Callback di `json.loads` (`object_pairs_hook`): costruisce il dizionario e rifiuta chiavi duplicate."""
    result = {}
    for name, value in pairs:
        if name in result:
            raise ContractError("Duplicate JSON key: " + name)
        result[name] = value
    return result


def _reject_constant(token: str):
    """Callback di `json.loads` (`parse_constant`): rifiuta NaN, Infinity e -Infinity."""
    raise ContractError("Non-JSON numeric constant: " + token)


def _parse(raw: str) -> dict:
    """Legge `raw` come JSON rigoroso e restituisce l'oggetto (deve essere un dizionario).

    Rifiuta testo vuoto, risposte oltre 40.000 caratteri, chiavi duplicate, costanti non
    finite e qualsiasi JSON che non sia un oggetto.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ContractError("Empty/non-text response")
    # L'inclusione in blocchi markdown e' volutamente non valida (gli output grezzi non si riparano).
    if len(raw) > 40_000:
        raise ContractError("JSON response exceeds maximum length")
    try:
        obj = json.loads(raw, object_pairs_hook=_duplicate_key_error,
                         parse_constant=_reject_constant)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ContractError("Invalid strict JSON response: " + str(exc)) from exc
    if type(obj) is not dict:
        raise ContractError("Expected JSON object")
    return obj


def _keys(obj: dict, names: tuple[str, ...], label: str):
    """Controlla che `obj` abbia ESATTAMENTE i campi `names` (ne' di piu' ne' di meno)."""
    if set(obj) != set(names):
        raise ContractError(
            f"{label}: expected fields {sorted(names)}, got {sorted(obj)}"
        )


def _text(value: object, name: str, *, nullable: bool = False):
    """Controlla che `value` sia una stringa non vuota di al massimo 2000 caratteri.

    Con `nullable=True` e' ammesso anche `None`. `name` e' il nome del campo per l'errore.
    """
    if value is None and nullable:
        return
    if type(value) is not str or not value.strip():
        raise ContractError(f"{name} must be a nonempty string")
    if len(value) > 2000:
        raise ContractError(f"{name} exceeds 2000 characters")


def _text_list(value: object, name: str, *, max_count: int = 12):
    """Controlla che `value` sia una lista di al piu' `max_count` stringhe valide (vedi `_text`)."""
    if type(value) is not list or len(value) > max_count:
        raise ContractError(f"{name} must be a bounded JSON list")
    for item in value:
        _text(item, name + " item")


def _allowed_refs(allowed_evidence_ids: Collection[str]) -> set[str]:
    """Allowlist degli ID di evidenza come insieme: al massimo 5000 ID distinti e ben formati."""
    if isinstance(allowed_evidence_ids, (str, bytes, dict)) or not isinstance(
        allowed_evidence_ids, Collection
    ):
        raise ContractError("Evidence allowlist must be a collection of IDs")
    if len(allowed_evidence_ids) > 5000:
        raise ContractError("Evidence allowlist too large")
    result = set(allowed_evidence_ids)
    if len(result) != len(allowed_evidence_ids) or not all(
        isinstance(v, str) and _EVIDENCE_RE.fullmatch(v) for v in result
    ):
        raise ContractError("Malformed/duplicate allowed evidence IDs")
    return result


def _refs(value: object, allowed: set[str]):
    """Controlla gli `evidence_ids` citati: lista limitata (32), senza duplicati, tutti in `allowed`."""
    if type(value) is not list or len(value) > 32:
        raise ContractError("evidence_ids must be a bounded JSON list")
    if len(value) != len(set(v for v in value if type(v) is str)):
        raise ContractError("Duplicate or non-string evidence_ids")
    if any(
        type(ref) is not str or not _EVIDENCE_RE.fullmatch(ref)
        or ref not in allowed for ref in value
    ):
        raise ContractError("Unknown/malformed evidence ID")


def validate_cause_probe(
    raw_json: str, *, allowed_evidence_ids: Collection[str],
) -> dict:
    """Valida la sonda C. L'allowlist deve essere generata dai log reali dei tool.

    Argomenti: `raw_json` (risposta grezza) e `allowed_evidence_ids` (ID di evidenza ammessi).
    Restituisce l'oggetto validato; solleva `ContractError` al primo scostamento.

    Passi: 1) JSON rigoroso con esattamente i campi dello schema C; 2) versione di schema,
    decisione ("diagnosis" o "abstain") e confidenza ammesse; 3) tipo di guasto, componente,
    ID di evidenza, alternative e limiti ben formati; 4) con "diagnosis": serve il tipo di
    guasto e almeno un ID di evidenza; con "abstain": nessun tipo di guasto ne' componente
    e un motivo fra i limiti.
    """
    obj = _parse(raw_json)
    _keys(obj, (
        "schema_version", "decision", "predicted_fault_type",
        "predicted_component", "confidence", "evidence_ids",
        "alternatives", "limitations",
    ), "cause probe")
    if obj["schema_version"] != SCHEMA_C:
        raise ContractError("Wrong cause probe schema version")
    if obj["decision"] not in ("diagnosis", "abstain"):
        raise ContractError("decision must be diagnosis or abstain")
    if obj["confidence"] not in ("low", "medium", "high", "unassessed"):
        raise ContractError("Invalid confidence value")
    _text(obj["predicted_fault_type"], "predicted_fault_type", nullable=True)
    _text(obj["predicted_component"], "predicted_component", nullable=True)
    _refs(obj["evidence_ids"], _allowed_refs(allowed_evidence_ids))
    _text_list(obj["alternatives"], "alternatives")
    _text_list(obj["limitations"], "limitations")
    if obj["decision"] == "diagnosis":
        _text(obj["predicted_fault_type"], "predicted_fault_type")
        if not obj["evidence_ids"]:
            raise ContractError("Diagnosis requires observed evidence IDs")
    else:
        if obj["predicted_fault_type"] is not None:
            raise ContractError("Abstention must not assert a fault type")
        if obj["predicted_component"] is not None:
            raise ContractError("Abstention must not assert a component")
        if not obj["limitations"]:
            raise ContractError("Abstention requires reason in limitations")
    return obj


def _signals(value: object) -> set[tuple[str, str, str, int]]:
    """Valida `required_signals` (al piu' 12) e restituisce le loro firme `(metrica, unita', aggregazione, finestra)`.

    Ogni segnale ha esattamente i campi dello schema, un'aggregazione ammessa e una finestra
    intera fra 1 e 86400 secondi; due segnali uguali sono un errore.
    """
    if type(value) is not list or len(value) > 12:
        raise ContractError("required_signals must be a bounded list")
    signatures = set()
    for item in value:
        if type(item) is not dict:
            raise ContractError("Signal must be a JSON object")
        _keys(item, ("metric", "unit", "aggregation", "window_seconds"), "signal")
        for key in ("metric", "unit"):
            _text(item[key], "signal." + key)
        if item["aggregation"] not in _AGGREGATIONS:
            raise ContractError("Unsupported signal aggregation")
        if type(item["window_seconds"]) is not int or not (
            1 <= item["window_seconds"] <= 86400
        ):
            raise ContractError("Invalid signal window_seconds")
        signature = (item["metric"], item["unit"],
                     item["aggregation"], item["window_seconds"])
        if signature in signatures:
            raise ContractError("Duplicate signal definition")
        signatures.add(signature)
    return signatures


def _conditions(value: object, signals: set) -> set:
    """Valida `conditions` (al piu' 24) e restituisce le firme dei segnali che usano.

    Ogni condizione ha i campi dello schema, un operatore ammesso, una soglia numerica finita e
    la firma di un segnale gia' dichiarato in `signals`.
    """
    if type(value) is not list or len(value) > 24:
        raise ContractError("conditions must be a bounded list")
    used = set()
    for item in value:
        if type(item) is not dict:
            raise ContractError("Condition must be a JSON object")
        _keys(item, (
            "metric", "operator", "threshold", "unit",
            "aggregation", "window_seconds",
        ), "condition")
        for key in ("metric", "unit"):
            _text(item[key], "condition." + key)
        if item["operator"] not in _OPERATORS:
            raise ContractError("Unsupported comparator")
        threshold = item["threshold"]
        if type(threshold) not in (int, float) or not math.isfinite(threshold):
            raise ContractError("Threshold must be a finite number")
        if item["aggregation"] not in _AGGREGATIONS:
            raise ContractError("Unsupported condition aggregation")
        if type(item["window_seconds"]) is not int or not (
            1 <= item["window_seconds"] <= 86400
        ):
            raise ContractError("Invalid condition window_seconds")
        signature = (item["metric"], item["unit"],
                     item["aggregation"], item["window_seconds"])
        if signature not in signals:
            raise ContractError("Condition has no matching required_signal")
        used.add(signature)
    return used


def validate_candidate_rule(
    raw_json: str, *, allowed_evidence_ids: Collection[str],
) -> dict:
    """Valida la proposta K; non valuta MAI il suo pseudocodice ne' le sue soglie.

    Argomenti: `raw_json` e `allowed_evidence_ids`, come per `validate_cause_probe`. Restituisce
    l'oggetto validato; solleva `ContractError` al primo scostamento.

    Passi: 1) JSON rigoroso con esattamente i campi dello schema K; 2) versione e stato
    ("candidate" o "insufficient_evidence") ammessi; 3) testi, ID di evidenza, segnali,
    condizioni, combinazione e liste ben formati; 4) stato "candidate": tutti i testi presenti,
    evidenze, segnali e condizioni non vuoti, ogni segnale usato da una condizione, combinazione
    "all" o "any", e astensione, controesempi e limiti non vuoti; 5) stato
    "insufficient_evidence": nessuna logica di rilevamento (niente segnali, condizioni, regola,
    combinazione o pseudocodice) e una spiegazione dell'astensione.
    """
    obj = _parse(raw_json)
    _keys(obj, (
        "schema_version", "status", "hypothesized_fault_type",
        "rule_name", "scope", "evidence_ids", "required_signals",
        "conditions", "combination", "abstain_when", "counterexamples",
        "limitations", "pseudocode",
    ), "candidate rule")
    if obj["schema_version"] != SCHEMA_K:
        raise ContractError("Wrong candidate rule schema")
    if obj["status"] not in ("candidate", "insufficient_evidence"):
        raise ContractError("Invalid candidate rule status")
    for key in ("hypothesized_fault_type", "rule_name", "scope", "pseudocode"):
        _text(obj[key], key, nullable=True)
    _refs(obj["evidence_ids"], _allowed_refs(allowed_evidence_ids))
    sigs = _signals(obj["required_signals"])
    used = _conditions(obj["conditions"], sigs)
    if obj["combination"] not in ("all", "any", None):
        raise ContractError("Invalid combination")
    _text_list(obj["abstain_when"], "abstain_when")
    _text_list(obj["counterexamples"], "counterexamples")
    _text_list(obj["limitations"], "limitations")
    if obj["status"] == "candidate":
        for key in ("hypothesized_fault_type", "rule_name", "scope", "pseudocode"):
            _text(obj[key], key)
        if not obj["evidence_ids"] or not sigs or not obj["conditions"]:
            raise ContractError("Candidate requires evidence, signals, conditions")
        if sigs != used:
            raise ContractError("All required signals must be used in conditions")
        if obj["combination"] not in ("all", "any"):
            raise ContractError("Candidate requires all/any combination")
        if any(not obj[key] for key in
               ("abstain_when", "counterexamples", "limitations")):
            raise ContractError("Candidate missing abstention, counterexamples or limits")
    else:
        if obj["required_signals"] or obj["conditions"] or obj["pseudocode"] is not None:
            raise ContractError("Insufficient evidence cannot assert detector logic")
        if obj["rule_name"] is not None or obj["combination"] is not None:
            raise ContractError("Insufficient evidence cannot define a rule")
        if not obj["abstain_when"] or not obj["limitations"]:
            raise ContractError("Insufficient evidence must explain abstention")
    return obj
