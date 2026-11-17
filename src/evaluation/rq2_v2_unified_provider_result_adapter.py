"""G4J: normalizza SOLO ricevute D/C/K verso il ledger RQ2-V2 unificato.

NON costruisce provider, NON crea claim/record, NON legge dati/GT e
NON invia API. Input: RQ1 run_experiment D oppure il dict di
rq2_ck_provider_transport._one_call per C/K *gia' ottenuto*.

Usa lo STESSO validatore del ledger scientifico per evitare che
la classification del futuro dispatcher diverga dal readback. Una
misura incompleta significa "token osservati", MAI "fattura zero".
Il conteggio invocazioni logiche non e' un conteggio HTTP garantito.

Contenuto
---------
- `_row`: trova nel piano la riga di uno stage e ne verifica l'identita';
- `_meter`, `_from_metrics`, `_from_usage`: costruiscono il "contatore di stage" (richieste e
  token OSSERVATI) dalle metriche di D o dall'uso di token di C/K;
- `_classify_with_ledger`: decide se la ricevuta e' un esito completo o un output non valido,
  usando lo stesso validatore del ledger scientifico;
- `normalize_d_run`, `normalize_ck_call`: i due punti d'ingresso, per D e per C/K.

Esiti: `RECORDED_COMPLETE`, `INVALID_OUTPUT` oppure `PROVIDER_ERROR`; nessuna ricevuta autorizza
chiamate API (`can_execute_api` e' sempre False).
"""
from __future__ import annotations

import hashlib
import re

from evaluation.rq2_v2_unified_discovery_plan import build_offline_discovery_plan
from evaluation.rq2_v2_unified_provenance_gate import audit_captured_v2_d
from evaluation.rq2_v2_unified_scientific_ledger import (
    UnifiedScientificLedgerBlocked, _validate_artifact,
)

VERSION = "rq2_v2_unified_provider_result_adapter_v0"
# Nome dello schema del contatore di stage (richieste e token osservati).
METER_SCHEMA = "rq2_v2_unified_stage_meter_v0"
# Forma ammessa del codice d'errore del provider: un prefisso noto, i due punti e un nome breve
# di caratteri sicuri. Nessun testo libero dell'SDK puo' finire nel record.
ERROR_CODE = re.compile(
    r"(?:SDK_CONSTRUCTION_ERROR|PROVIDER_ERROR|PROTOCOL_ERROR):"
    r"[A-Za-z0-9_.:-]{1,100}\Z"
)


class UnifiedProviderReceiptBlocked(ValueError):
    """Sorgente, identity, contatore o output troppo ambiguo per registrare."""


def _row(*, stage_id: str, logical_model: str, stage: str) -> dict:
    """Riga del piano per `stage_id`, dopo aver verificato modello logico e stage.

    Tutti e tre gli argomenti devono essere stringhe esatte. Solleva
    `UnifiedProviderReceiptBlocked` se lo stage non e' nel piano discovery (ad esempio un caso OOD)
    o se modello e stage non coincidono con quelli della riga.
    """
    if (
        type(stage_id) is not str or type(logical_model) is not str
        or type(stage) is not str
    ):
        raise UnifiedProviderReceiptBlocked("Exact stage/model identity required")
    plan = build_offline_discovery_plan()
    row = next(
        (e for e in plan["entries"] if e["stage_id"] == stage_id),
        None,
    )
    if (
        row is None or row["logical_model"] != logical_model
        or row["stage"] != stage
    ):
        raise UnifiedProviderReceiptBlocked("Unknown, mismatched or OOD stage")
    return row


def _meter(*, attempts: int, input_observed: int,
           output_observed: int, complete: bool) -> dict:
    """Contatore di stage: richieste al modello e token OSSERVATI (non una fattura).

    `attempts` va da 0 a 492 (massimo teorico del piano), i token sono interi non negativi,
    `complete` indica se l'uso di token e' completo. Il costo in dollari resta "UNKNOWN" e il
    tetto di spesa non e' garantito.
    """
    if (
        type(attempts) is not int or attempts < 0 or attempts > 492
        or type(input_observed) is not int or input_observed < 0
        or type(output_observed) is not int or output_observed < 0
        or type(complete) is not bool
    ):
        raise UnifiedProviderReceiptBlocked("Invalid observed provider usage")
    return {
        "schema": METER_SCHEMA,
        "observed_model_requests": attempts,
        "input_tokens_observed": input_observed,
        "output_tokens_observed": output_observed,
        "usage_complete": complete,
        "cost_estimate_usd_not_invoice": "UNKNOWN",
        "usd_hard_cap_guaranteed": False,
    }


def _from_metrics(metrics: object, *, can_be_zero: bool) -> dict:
    """Contatore di stage per D, dalle metriche del runner RQ1.

    Argomenti: `metrics` (dizionario del runner) e `can_be_zero` (True solo se D ha avuto un
    errore, e allora zero chiamate sono ammesse). Se l'uso di token e' dichiarato completo, input,
    output e totale devono essere coerenti; altrimenti si tengono i conteggi osservabili e si
    segna "incompleto".
    """
    if type(metrics) is not dict:
        raise UnifiedProviderReceiptBlocked("Missing D runner metrics")
    calls = metrics.get("llm_calls")
    if type(calls) is not int or calls < (0 if can_be_zero else 1):
        raise UnifiedProviderReceiptBlocked("D logical LLM call count unproven")
    complete = metrics.get("token_usage_complete")
    if type(complete) is not bool:
        raise UnifiedProviderReceiptBlocked("D usage completeness missing")
    inp, out = metrics.get("input_tokens"), metrics.get("output_tokens")
    if complete:
        if type(inp) is not int or type(out) is not int or inp < 0 or out < 0:
            raise UnifiedProviderReceiptBlocked("Complete D usage inconsistent")
        if (
            type(metrics.get("total_tokens")) is not int
            or metrics["total_tokens"] != inp + out
        ):
            raise UnifiedProviderReceiptBlocked("Complete D token total inconsistent")
    else:
        # Un campo assente NON e' una prova di zero fatturato:
        # il ledger conserva i conteggi osservabili e flag incomplete.
        inp = inp if type(inp) is int and inp >= 0 else 0
        out = out if type(out) is int and out >= 0 else 0
    return _meter(
        attempts=calls, input_observed=inp,
        output_observed=out, complete=complete,
    )


def _from_usage(usage: object, *, attempts: int) -> dict:
    """Contatore di stage per C/K, dal dizionario `usage` del trasporto.

    `attempts` puo' essere solo 0 o 1 (C/K fa al piu' una chiamata). Per l'uso di token valgono
    le stesse regole di `_from_metrics`: completo = coerente, incompleto = conteggi osservati.
    """
    if type(attempts) is not int or attempts not in (0, 1):
        raise UnifiedProviderReceiptBlocked("CK must be zero/one SDK invoke")
    if type(usage) is not dict or type(usage.get("complete")) is not bool:
        raise UnifiedProviderReceiptBlocked("CK usage completeness absent")
    complete = usage["complete"]
    inp = usage.get("input_tokens")
    out = usage.get("output_tokens")
    if complete:
        if type(inp) is not int or type(out) is not int or inp < 0 or out < 0:
            raise UnifiedProviderReceiptBlocked("Complete CK usage malformed")
        if (
            type(usage.get("total_tokens")) is not int
            or usage["total_tokens"] != inp + out
        ):
            raise UnifiedProviderReceiptBlocked("Complete CK token total inconsistent")
    else:
        inp = inp if type(inp) is int and inp >= 0 else 0
        out = out if type(out) is int and out >= 0 else 0
    return _meter(
        attempts=attempts, input_observed=inp,
        output_observed=out, complete=complete,
    )


def _classify_with_ledger(
    *, row: dict, artifact: dict, d_record: dict | None,
) -> str:
    """Stato della ricevuta: prima si prova come COMPLETO, poi come OUTPUT NON VALIDO.

    Usa lo stesso validatore del ledger scientifico (`_validate_artifact`). Se la ricevuta non
    e' coerente con nessuno dei due stati solleva `UnifiedProviderReceiptBlocked`.
    """
    try:
        _validate_artifact(row, "RECORDED_COMPLETE", artifact, d_record)
    except UnifiedScientificLedgerBlocked as original:
        try:
            _validate_artifact(row, "INVALID_OUTPUT", artifact, d_record)
        except UnifiedScientificLedgerBlocked as error:
            raise UnifiedProviderReceiptBlocked(
                "Receipt is inconsistent with either scientific status"
            ) from error
        return "INVALID_OUTPUT"
    return "RECORDED_COMPLETE"


def normalize_d_run(
    *, stage_id: str, logical_model: str, run: dict,
) -> dict:
    """No I/O: normalizza il risultato immutato RQ1 dopo l'LLM.

    Un errore del runner usa un codice redatto + hash, senza salvare
    testo potenzialmente contenente token/credenziali.

    Argomenti: `stage_id` e `logical_model` (devono coincidere con una riga D del piano) e
    `run` (risultato del runner RQ1, dizionario). Restituisce la ricevuta normalizzata:
    versione, stage, stato, artefatto (diagnosi + contatore, oppure codice d'errore + contatore)
    e dichiarazioni "nessuna API, costo sconosciuto".

    Passi: 1) riga del piano; 2) l'origine del run (caso, variante, modello, provider, contratto
    di output, turni di tool) deve coincidere col piano; 3) contatore dalle metriche;
    4) se c'e' un errore si registra solo un codice con hash, altrimenti si classifica l'esito.
    """
    row = _row(stage_id=stage_id, logical_model=logical_model, stage="D")
    if type(run) is not dict:
        raise UnifiedProviderReceiptBlocked("RQ1 D run must be dict")
    # Identita' attesa del run D, ricavata dal piano: qualsiasi scostamento blocca la ricevuta.
    required = {
        "case_id": row["case_id"],
        "variant": row["harness"],
        "variant_scheme": "current",
        "model": row["model_id"],
        "model_provider": row["model_provider"],
        "output_contract_mode": "v2_enforce",
        "max_tool_rounds": 6,
    }
    if any(run.get(key) != value for key, value in required.items()):
        raise UnifiedProviderReceiptBlocked("D run origin/model identity drift")
    error = run.get("error")
    if error is not None and (
        type(error) is not str or not error.strip()
    ):
        raise UnifiedProviderReceiptBlocked("Unrecognizable D execution error")
    meter = _from_metrics(
        run.get("metrics"), can_be_zero=(error is not None),
    )
    if error is not None:
        # Conservare la distinzione tra errori senza registrare testo
        # arbitrario dell'SDK, headers o credenziali.
        err_hash = hashlib.sha256(error.encode("utf-8")).hexdigest()[:16]
        status, artifact = "PROVIDER_ERROR", {
            "provider_error": "RUNNER_EXECUTION_ERROR_SHA256_" + err_hash,
            "stage_meter": meter,
        }
        _validate_artifact(row, status, artifact, None)
    else:
        artifact = {"diagnostic_run": run, "stage_meter": meter}
        status = _classify_with_ledger(
            row=row, artifact=artifact, d_record=None,
        )
    return {
        "version": VERSION, "stage_id": stage_id,
        "status": status, "artifact": artifact,
        "can_execute_api": False, "provider_requests_sent_here": 0,
        "usd_cost_known": False, "observed_requests_are_http_hard_cap": False,
    }


def normalize_ck_call(
    *, stage_id: str, logical_model: str, call: dict,
    diagnostic_run: dict,
) -> dict:
    """Normalizza la risposta gia' ricevuta dal trasporto tool-free C/K.

    Per K, lo stato del parent C deve essere verificato dal ledger G4F
    prima di qualsiasi dispatch: il parser non sostituisce tale gate.

    Argomenti: `stage_id` e `logical_model` (riga C o K del piano), `call` (dizionario del
    trasporto C/K gia' ottenuto) e `diagnostic_run` (il D da cui si parte). Restituisce la
    ricevuta normalizzata, con la stessa forma di `normalize_d_run`.

    Passi: 1) lo stage deve essere C o K e presente nel piano; 2) il D deve avere provenienza
    attendibile per quel caso, modello e harness; 3) contatore dall'uso di token;
    4) con errore del provider: solo un codice sicuro e nessun testo di risposta; senza errore:
    una sola chiamata e un testo di risposta, poi classificazione dell'esito.
    """
    if type(stage_id) is not str:
        raise UnifiedProviderReceiptBlocked("Stage ID must be text")
    stage = stage_id.rsplit(":", 1)[-1]
    if stage not in ("C", "K"):
        raise UnifiedProviderReceiptBlocked("C/K-only receipt adapter")
    row = _row(stage_id=stage_id, logical_model=logical_model, stage=stage)
    if type(call) is not dict or type(diagnostic_run) is not dict:
        raise UnifiedProviderReceiptBlocked("CK transport/source D missing")
    # D deve essere della stessa coorte, harness e modello, non un
    # blob inventato dall'utente dopo una richiesta C/K.
    try:
        audit_captured_v2_d(
            run=diagnostic_run, case_id=row["case_id"],
            model=row["logical_model"], harness=row["harness"],
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise UnifiedProviderReceiptBlocked("Untrusted D provenance for CK") from exc

    attempts = call.get("api_attempts")
    meter = _from_usage(call.get("usage"), attempts=attempts)
    error = call.get("provider_error")
    raw = call.get("raw_response")
    if error is not None:
        if type(error) is not str or not ERROR_CODE.fullmatch(error) or raw is not None:
            raise UnifiedProviderReceiptBlocked("Unsafe CK provider error")
        status, artifact = "PROVIDER_ERROR", {
            "provider_error": error,
            "stage_meter": meter,
        }
        _validate_artifact(row, status, artifact, {"status": "RECORDED_COMPLETE",
                                                   "artifact": {"diagnostic_run": diagnostic_run}})
    else:
        if attempts != 1 or type(raw) is not str:
            raise UnifiedProviderReceiptBlocked("Missing unambiguous CK response")
        artifact = {"raw_response": raw, "stage_meter": meter}
        d_record = {"status": "RECORDED_COMPLETE",
                    "artifact": {"diagnostic_run": diagnostic_run}}
        status = _classify_with_ledger(
            row=row, artifact=artifact, d_record=d_record,
        )
    return {
        "version": VERSION, "stage_id": stage_id,
        "status": status, "artifact": artifact,
        "can_execute_api": False, "provider_requests_sent_here": 0,
        "usd_cost_known": False, "observed_requests_are_http_hard_cap": False,
    }
