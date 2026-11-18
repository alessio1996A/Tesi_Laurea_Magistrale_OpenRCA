"""RQ2 - ablazione D->K: lo stadio K SENZA il passo C (nessun file congelato modificato).

Domanda. Nel run congelato (V5.1) K riceve la traiettoria di D e la causa scritta da
C. Che cosa cambia se K riceve SOLO la traiettoria di D? Qui si esegue quella
variante con gli stessi 4 incidenti di discovery, gli stessi 3 modelli e gli stessi
5 harness: 60 nuovi stadi K. I record D del run congelato si RILEGGONO (sola lettura)
e non si rieseguono: D e' identico per costruzione.

Che cosa cambia rispetto a K del run V5.1 (e SOLO questo):
- il prompt di sistema: `K_NO_CAUSE_SYSTEM` e' `RULE_SYSTEM` con UNA sola frase
  sostituita (quella che nomina la sonda di causa); il resto e' identico, hash
  compreso nel manifest;
- il pacchetto: manca il campo `unverified_model_cause_probe`.
Il resto (contratto di output, politica di formato V5.1, politica di retry, claim
create-only, parametri del provider) e' riusato senza modifiche.

Che cosa NON e' (da dichiarare nella tesi): una variante in cui K vede la diagnosi
di D. Nel run congelato la risposta di D non viene mai passata a C ne' a K, per non
ancorare i passi successivi: qui resta cosi'. K vede soltanto le evidenze raccolte
da D (la traiettoria degli strumenti). Un confronto con "K che vede la diagnosi di D"
sarebbe un'altra ablazione, non eseguita.

Garanzie: nessun accesso a ground truth, scorer o incidenti sigillati; archivio NUOVO
(`data/rq2_dk_ablation_v1`), a sola creazione; l'archivio del run congelato non viene
mai scritto; nessuna riesecuzione di D, C, L1 o L2.

Contenuto:
- costanti: versione, protocollo, cartelle, prompt K senza causa e suo SHA-256;
- `prepare_k_no_cause`: pacchetto di prompt di K senza causa (offline);
- `build_dk_plan`: i 60 stadi K del piano V4 (nessuna modifica);
- `SourceDRecords`: lettura in sola lettura dei record D del run congelato;
- `DKExecutor`: prepara e esegue UNA chiamata per stadio (con la politica di retry);
- `run_dk_stage`, `run_dk_matrix`: ciclo con claim create-only e blocco se D non e' completo;
- `compare_with_frozen`: confronto descrittivo cella per cella con i K del run congelato.
"""
from __future__ import annotations

import hashlib
import time
import traceback
from pathlib import Path

from evaluation import rq2_v5_matrix_runner as mr
from evaluation.rq2_probe_adapter import (
    RULE_SYSTEM, ProbeInputError, _instruction, _package, _run_bundle,
)
from evaluation.rq2_stage_binding import ALLOWED_TOOLS
from evaluation.rq2_v4_unified_gtfree_discovery_plan import (
    build_offline_v4_discovery_plan,
)
from evaluation.rq2_v5_response_normalization import apply_policy
from evaluation.rq2_v5_retry import ck_error_is_transport, run_with_one_retry

VERSION = "rq2_dk_ablation_v0"
PROTOCOL = "rq2_dk_ablation_matrix_v0"
# Archivio NUOVO per i 60 K senza causa; quello del run congelato e' solo letto.
NAMESPACE = Path("data/rq2_dk_ablation_v1")
SOURCE_NAMESPACE = mr.NAMESPACE
EXPECTED_K_STAGES = 60

# Frase di RULE_SYSTEM che nomina la sonda di causa di C e frase che la sostituisce.
_CAUSE_SENTENCE = (
    "Use ONLY the observed tool evidence and the model's own previously frozen cause\n"
    "probe (which may be wrong); it is NOT ground truth."
)
_NO_CAUSE_SENTENCE = (
    "Use ONLY the observed tool evidence. No prior cause analysis is provided\n"
    "and none must be assumed."
)
if RULE_SYSTEM.count(_CAUSE_SENTENCE) != 1:  # il prompt congelato e' cambiato: ci si ferma
    raise RuntimeError("RULE_SYSTEM diverso da quello atteso: ablazione non valida")

K_NO_CAUSE_SYSTEM = RULE_SYSTEM.replace(_CAUSE_SENTENCE, _NO_CAUSE_SENTENCE)
K_NO_CAUSE_SYSTEM_SHA256 = hashlib.sha256(
    K_NO_CAUSE_SYSTEM.encode("utf-8")).hexdigest()
K_STAGE_NAME = "K_candidate_rule_no_cause"


def prepare_k_no_cause(
    *, original_instruction: str, diagnostic_run: dict, phase: str,
    allowed_tool_names,
) -> dict:
    """Pacchetto di prompt per K SENZA la causa di C (nessuna chiamata a modelli).

    Argomenti (per nome): `original_instruction` (istruzione originale senza ground
    truth), `diagnostic_run` (esecuzione D registrata), `phase` (deve essere
    "discovery"), `allowed_tool_names` (strumenti ammessi). Restituisce il pacchetto
    con messaggi sistema/utente, hash e flag "non pronto per le API".

    Passi: 1) rifiuta fasi diverse da discovery; 2) valida l'istruzione; 3) costruisce
    le evidenze dalla sola traiettoria degli strumenti di D (la risposta di D non
    viene usata); 4) assembla il pacchetto SENZA il campo della causa.
    """
    if phase != "discovery":
        raise ProbeInputError("K is forbidden outside discovery phase")
    instruction = _instruction(original_instruction)
    bundle = _run_bundle(diagnostic_run, allowed_tool_names)
    observed = {
        "original_instruction": instruction,
        "evidence_bundle": bundle,
        "diagnosis_is_gt_verified": False,
    }
    return _package(K_STAGE_NAME, K_NO_CAUSE_SYSTEM, observed, bundle)


def build_dk_plan() -> tuple[dict, list[dict]]:
    """Piano dell'ablazione: i 60 stadi K del piano V4, invariati.

    Restituisce `(piano completo, righe K)`. Solleva `mr.PlanMismatch` se le righe K
    non sono esattamente 60 o se un id e' duplicato.
    """
    plan = build_offline_v4_discovery_plan()
    rows = [r for r in plan["entries"] if r["stage"] == "K"]
    ids = [r["stage_id"] for r in rows]
    if len(rows) != EXPECTED_K_STAGES or len(set(ids)) != len(ids):
        raise mr.PlanMismatch("Il piano deve avere 60 stadi K distinti")
    return plan, rows


def d_parent_id(row: dict) -> str:
    """Identificativo dello stadio D dello stesso caso/modello/harness di `row`."""
    return row["stage_id"].rsplit(":", 1)[0] + ":D"


def c_parent_id(row: dict) -> str:
    """Identificativo dello stadio C (usato solo dal confronto con il run congelato)."""
    return row["stage_id"].rsplit(":", 1)[0] + ":C"


class SourceDRecords:
    """Lettura in SOLA LETTURA dei record del run congelato (D, e K per il confronto).

    Non crea cartelle e non scrive mai: se l'archivio non esiste solleva un errore.
    Ogni file e' riletto verificandone l'hash SHA-256 interno.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.records = self.root / "records"
        if not self.records.is_dir():
            raise mr.StoreError("Archivio del run congelato non trovato: " + str(self.root))

    def load(self, stage_id: str) -> dict | None:
        """Record dello stadio (con hash verificato) oppure `None` se non esiste."""
        path = self.records / f"V5_RECORD_{mr._key(stage_id)}.json"
        return mr.StageStore._read(path, "record_sha256")


class DKExecutor:
    """prepare(): tutto cio' che puo' fallire offline; run(): una sola chiamata a K.

    I parametri `call_fn`, `normalize_fn` e `instruction_fn` servono SOLO ai test
    (iniettano versioni finte); in produzione restano `None` e si usano le funzioni
    reali del run V5.1, importate al momento dell'uso (servono LangChain e gli SDK).
    """

    def __init__(self, *, data_dir: Path, sleep=time.sleep, call_fn=None,
                 normalize_fn=None, instruction_fn=None):
        self.data_dir = Path(data_dir)
        self._sleep = sleep
        self._call_fn = call_fn
        self._normalize_fn = normalize_fn
        self._instruction_fn = instruction_fn

    def prepare(self, row: dict, d_record: dict) -> dict:
        """Costruisce e controlla il pacchetto di K a partire dal record D.

        Argomenti: `row` (riga K del piano) e `d_record` (record D completo del run
        congelato). Restituisce pacchetto, esecuzione D e provenienza (hash del
        pacchetto, del prompt e del record D di origine).
        """
        if self._instruction_fn is not None:
            instruction = self._instruction_fn(self.data_dir, row["case_id"])
        else:
            from evaluation.rq2_v2_unified_live_stage_preflight import (
                _source_instruction,
            )
            instruction = _source_instruction(
                data_dir=self.data_dir, case_id=row["case_id"])
        diagnostic_run = d_record["receipt"]["artifact"]["diagnostic_run"]
        package = prepare_k_no_cause(
            original_instruction=instruction, diagnostic_run=diagnostic_run,
            phase="discovery", allowed_tool_names=ALLOWED_TOOLS,
        )
        messages = package["messages"]
        if (
            [m["role"] for m in messages] != ["system", "user"]
            or package["system_prompt_sha256"] != K_NO_CAUSE_SYSTEM_SHA256
            or package["model_api_calls"] != 0
        ):
            raise ValueError("Pacchetto K senza causa non conforme al prompt congelato")
        return {
            "package": package, "diagnostic_run": diagnostic_run,
            "provenance": {
                "variant": "K_NO_CAUSE",
                "package_sha256": package["package_sha256"],
                "system_prompt_sha256": package["system_prompt_sha256"],
                "source_d_record_sha256": d_record["record_sha256"],
                "source_namespace": SOURCE_NAMESPACE.as_posix(),
            },
        }

    def run(self, row: dict, prepared: dict) -> dict:
        """Esegue lo stadio con la politica di retry unica (al piu' due tentativi)."""
        return run_with_one_retry(
            lambda number: self._attempt(row, prepared), sleep=self._sleep,
        )

    def _attempt(self, row: dict, prepared: dict):
        """Un tentativo di K. Restituisce (esito, ritentabile, riepilogo).

        Passi: 1) prepara i messaggi (LangChain in produzione); 2) una sola chiamata al
        provider; 3) politica di formato V5.1 sul testo; 4) normalizza la ricevuta con
        il contratto strict V4 (un rifiuto diventa RECEIPT_REJECTED, non un errore del
        modello); 5) segnala se l'errore e' di trasporto e quindi ritentabile.
        """
        messages = prepared["package"]["messages"]
        if self._call_fn is not None:
            payload = [dict(m) for m in messages]
            call = self._call_fn(row["model_provider"], row["model_id"], payload)
        else:
            from langchain_core.messages import HumanMessage, SystemMessage
            from evaluation.rq2_v2_ck_provider_transport_candidate import (
                one_ck_call_candidate,
            )
            payload = [SystemMessage(content=messages[0]["content"]),
                       HumanMessage(content=messages[1]["content"])]
            call = one_ck_call_candidate(
                row["model_provider"], row["model_id"], payload)
        summary = {k: call.get(k) for k in (
            "provider_error", "api_attempts", "usage", "finish_reason",
            "elapsed_seconds")}
        text, fmt = apply_policy(call.get("raw_response"))
        for_receipt = dict(call)
        if call.get("provider_error") is None and text is not None:
            for_receipt["raw_response"] = text
        if self._normalize_fn is not None:
            # Solo test: normalizzatore finto, la cui eccezione di rifiuto e' ValueError.
            normalize, blocked = self._normalize_fn, ValueError
        else:
            from evaluation.rq2_v4_scientific_receipt_adapter_candidate import (
                V4ScientificReceiptBlocked, normalize_v4_ck_call,
            )
            normalize, blocked = normalize_v4_ck_call, V4ScientificReceiptBlocked
        try:
            receipt = normalize(
                stage_id=row["stage_id"], logical_model=row["logical_model"],
                call=for_receipt, diagnostic_run=prepared["diagnostic_run"],
            )
        except blocked as exc:
            return {
                "status": mr.STATUS_RECEIPT_REJECTED, "receipt": None,
                "format": fmt,
                "provenance": {**prepared["provenance"], "raw_call": dict(summary)},
                "error_summary": {"code": "V4_RECEIPT_REJECTED",
                                  "detail": str(exc)[:200]},
            }, False, summary
        retriable = (receipt["status"] == "PROVIDER_ERROR"
                     and ck_error_is_transport(call))
        return {"status": receipt["status"], "receipt": receipt,
                "format": fmt, "provenance": prepared["provenance"]
                }, retriable, summary


def _identity_fields(row: dict) -> dict:
    """Campi di identita' dello stadio, copiati dalla riga del piano."""
    return mr._identity(row)


def _blocked(store: mr.StageStore, row: dict, parent_id: str, status: str) -> dict:
    """Scrive il record BLOCKED_DEPENDENCY (D non completo): nessuna chiamata al modello."""
    return store.write_record(row["stage_id"], {
        "protocol": PROTOCOL, "runner_version": VERSION,
        **_identity_fields(row),
        "status": mr.STATUS_BLOCKED,
        "blocked_by": {"stage_id": parent_id, "status": status},
        "receipt": None, "format": None, "provenance": None,
        "error_summary": None, "claim_sha256": None,
        "started_at_utc": None, "finished_at_utc": mr._now(),
        "elapsed_seconds": 0.0, "source_commit": None,
    })


def run_dk_stage(row: dict, *, source: SourceDRecords, store: mr.StageStore,
                 executor, source_commit: str | None = None, secrets=(),
                 log=print) -> str:
    """Un solo stadio K senza causa. Restituisce un codice azione (`mr.ACTION_*`).

    Passi: 1) se esiste il record, non fa nulla; 2) se esiste il claim senza record e'
    un ORFANO e non si riesegue mai da soli; 3) legge il record D del run congelato
    (assente: attesa; non completo: stadio bloccato); 4) prepara offline (un errore
    ferma il lotto, senza claim); 5) claim create-only; 6) una chiamata; 7) record
    create-only con identita', esito, formato e provenienza.
    """
    stage_id = row["stage_id"]
    if store.load_record(stage_id) is not None:
        return mr.ACTION_ALREADY
    if store.load_claim(stage_id) is not None:
        log(f"  ORFANO {stage_id}: claim senza record, NON riesegue")
        return mr.ACTION_ORPHAN

    parent_id = d_parent_id(row)
    d_record = source.load(parent_id)
    if d_record is None:
        return mr.ACTION_WAITING
    if d_record["status"] != mr.STATUS_COMPLETE:
        _blocked(store, row, parent_id, d_record["status"])
        return mr.ACTION_BLOCKED

    try:
        prepared = executor.prepare(row, d_record)
    except Exception as exc:  # noqa: BLE001 - ferma il lotto, nessun claim
        log(f"  PREPARAZIONE FALLITA {stage_id}: {type(exc).__name__}: "
            + mr._redact(str(exc), secrets)[:300])
        return mr.ACTION_PREPARE_FAILED

    try:
        claim = store.claim(stage_id, {
            **_identity_fields(row), "protocol": PROTOCOL,
            "source_commit": source_commit})
    except mr.ClaimExists:
        return mr.ACTION_ORPHAN
    started = time.monotonic()
    started_at = mr._now()
    error_summary = None
    try:
        outcome = executor.run(row, prepared)
        if (type(outcome) is not dict
                or outcome.get("status") not in mr.EXECUTOR_STATUSES):
            raise mr.StoreError("Esito dell'esecutore non valido")
    except Exception as exc:  # noqa: BLE001 - dopo il claim: registra e basta
        text = mr._redact(traceback.format_exc(), secrets)
        log("  ECCEZIONE nello stadio (traceback sotto, solo qui, non salvato):")
        log(text[-1500:])
        error_summary = {
            "code": "EXECUTOR_EXCEPTION:" + type(exc).__name__,
            "message_sha256": hashlib.sha256(
                str(exc).encode("utf-8")).hexdigest(),
        }
        outcome = {"status": mr.STATUS_PROVIDER_ERROR, "receipt": None,
                   "format": None, "provenance": None}

    body = {
        "protocol": PROTOCOL, "runner_version": VERSION,
        **_identity_fields(row),
        "status": outcome["status"],
        "receipt": outcome.get("receipt"),
        "format": outcome.get("format"),
        "provenance": outcome.get("provenance"),
        "error_summary": error_summary or outcome.get("error_summary"),
        "blocked_by": None,
        "claim_sha256": claim["claim_sha256"],
        "started_at_utc": started_at, "finished_at_utc": mr._now(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "source_commit": source_commit,
    }
    try:
        store.write_record(stage_id, body)
    except (TypeError, ValueError) as exc:
        # Esito non serializzabile: non si perde lo stadio (il claim e' gia' preso).
        store.write_record(stage_id, {**body, "status": mr.STATUS_RECEIPT_REJECTED,
                                      "receipt": None, "format": None,
                                      "provenance": None,
                                      "error_summary": {
            "code": "RECORD_SERIALIZATION_ERROR:" + type(exc).__name__}})
    return mr.ACTION_EXECUTED


def run_dk_matrix(rows: list[dict], *, source: SourceDRecords,
                  store: mr.StageStore, executor,
                  source_commit: str | None = None,
                  max_stages: int | None = None,
                  time_budget_seconds: float | None = None,
                  secrets=(), log=print) -> dict:
    """Esegue le righe selezionate in ordine di piano; si ferma se una preparazione fallisce.

    `max_stages` conta solo gli stadi realmente eseguiti (cioe' con claim). Restituisce
    il conteggio delle azioni, il numero di stadi eseguiti e il motivo dell'arresto.
    """
    counts: dict[str, int] = {}
    started = time.monotonic()
    executed = 0
    stopped = None
    for row in rows:
        if max_stages is not None and executed >= max_stages:
            stopped = "max_stages"
            break
        if (time_budget_seconds is not None
                and time.monotonic() - started >= time_budget_seconds):
            stopped = "time_budget"
            break
        log(f"- {row['stage_id'].split(':', 1)[1]}")
        action = run_dk_stage(row, source=source, store=store,
                              executor=executor, source_commit=source_commit,
                              secrets=secrets, log=log)
        counts[action] = counts.get(action, 0) + 1
        if action == mr.ACTION_EXECUTED:
            executed += 1
            record = store.load_record(row["stage_id"])
            log(f"  -> {record['status']} ({record['elapsed_seconds']} s)")
        elif action == mr.ACTION_PREPARE_FAILED:
            stopped = "prepare_failed"
            break
    return {"actions": counts, "executed": executed, "stopped": stopped}


def _k_label(record: dict | None) -> str:
    """Etichetta di un K: candidate / insufficient_evidence / non valido / assente."""
    if record is None:
        return "assente"
    if record["status"] != mr.STATUS_COMPLETE:
        return record["status"]
    return mr._k_outcome(record)


def compare_with_frozen(rows: list[dict], *, source: SourceDRecords,
                        store: mr.StageStore) -> dict:
    """Confronto DESCRITTIVO cella per cella: K del run congelato contro K senza causa.

    Per ogni riga del piano affianca l'etichetta del K congelato (con la causa di C)
    e quella del K senza causa. Restituisce le celle, e i conteggi per modello e per
    harness. Non fa inferenza: con 4 incidenti e una esecuzione per cella e' solo una
    tabella di conteggi.
    """
    cells = []
    by_model: dict[str, dict[str, dict[str, int]]] = {}
    by_harness: dict[str, dict[str, dict[str, int]]] = {}
    for row in rows:
        frozen = _k_label(source.load(row["stage_id"]))
        ablated = _k_label(store.load_record(row["stage_id"]))
        cells.append({"stage_id": row["stage_id"], "case_id": row["case_id"],
                      "model": row["logical_model"], "harness": row["harness"],
                      "with_cause": frozen, "without_cause": ablated})
        for table, key in ((by_model, row["logical_model"]),
                           (by_harness, row["harness"])):
            slot = table.setdefault(key, {"with_cause": {}, "without_cause": {}})
            slot["with_cause"][frozen] = slot["with_cause"].get(frozen, 0) + 1
            slot["without_cause"][ablated] = slot["without_cause"].get(ablated, 0) + 1
    return {"cells": cells, "by_model": by_model, "by_harness": by_harness}
