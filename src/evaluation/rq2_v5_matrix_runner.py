"""RQ2-V5: runner a matrice, magro e riprendibile (solo libreria standard).

Esegue il ciclo D -> C -> K sul piano da 180 stage (5 harness x 3 modelli x
4 incidenti discovery x 3 stage) in lotti, scrivendo UN file per stage.

Garanzie (le stesse che contano per l'equita' del confronto):
- claim create-only PRIMA di ogni chiamata a pagamento: uno stage gia'
  tentato non viene mai rieseguito da solo (nessun retry nascosto);
- un claim senza record e' un ORFANO (es. Colab caduto a meta' stage): viene
  segnalato e mai rieseguito automaticamente;
- dipendenze D -> C -> K: C parte solo se D e' RECORDED_COMPLETE, K solo se
  lo e' anche C; altrimenti lo stage figlio riceve BLOCKED_DEPENDENCY, senza
  claim e senza chiamata al modello;
- ogni record porta SHA-256 e registro del formato (deviation), cosi' la
  conformita' strict e quella tollerante si calcolano per tutti i modelli;
- nessun accesso a ground truth, scorer ufficiale o casi OOD (il piano V4
  contiene solo i 4 incidenti discovery).

Questo modulo NON importa SDK, LangChain o harness: l'esecutore reale
(rq2_v5_stage_executor) viene iniettato. Cosi' la logica e' testabile offline.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

VERSION = "rq2_v5_matrix_runner_v0"
PROTOCOL = "rq2_v5_format_fair_matrix_v0"
NAMESPACE = Path("data/rq2_v5_format_fair_v1")

RECORD_SCHEMA = "rq2_v5_stage_record_v0"
CLAIM_SCHEMA = "rq2_v5_stage_claim_v0"

STATUS_COMPLETE = "RECORDED_COMPLETE"
STATUS_INVALID = "INVALID_OUTPUT"
STATUS_PROVIDER_ERROR = "PROVIDER_ERROR"
STATUS_BLOCKED = "BLOCKED_DEPENDENCY"
# Il modello ha risposto ma la ricevuta e' stata rifiutata dai controlli di
# integrita' V4 (non e' un errore del modello): l'output grezzo resta salvato.
STATUS_RECEIPT_REJECTED = "RECEIPT_REJECTED"
STATUSES = (
    STATUS_COMPLETE, STATUS_INVALID, STATUS_PROVIDER_ERROR,
    STATUS_BLOCKED, STATUS_RECEIPT_REJECTED,
)
EXECUTOR_STATUSES = (
    STATUS_COMPLETE, STATUS_INVALID, STATUS_PROVIDER_ERROR,
    STATUS_RECEIPT_REJECTED,
)
MODEL_OUTPUT_STATUSES = (STATUS_COMPLETE, STATUS_INVALID)

ACTION_ALREADY = "ALREADY_RECORDED"
ACTION_ORPHAN = "ORPHAN_CLAIM"
ACTION_WAITING = "WAITING_PARENT"
ACTION_BLOCKED = "BLOCKED_WRITTEN"
ACTION_PREPARE_FAILED = "PREPARE_FAILED"
ACTION_EXECUTED = "EXECUTED"


class StoreError(RuntimeError):
    """Errore dell'archivio: mai ignorato, mai riparato in silenzio."""


class ClaimExists(StoreError):
    """Lo stage ha gia' un claim: non va rieseguito."""


class RecordExists(StoreError):
    """Lo stage ha gia' un record: i record sono create-only."""


class StoreCorrupt(StoreError):
    """File di claim/record illeggibile o con hash non coerente."""


class PlanMismatch(RuntimeError):
    """Il piano non e' quello atteso (identita' o dipendenze cambiate)."""


# ---------------------------------------------------------------- utilita'

def _dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      indent=2, allow_nan=True)


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=True,
    ).encode("utf-8")).hexdigest()


def _key(stage_id: str) -> str:
    return hashlib.sha256(stage_id.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _redact(text: str, secrets) -> str:
    for secret in secrets:
        if type(secret) is str and len(secret) >= 8:
            text = text.replace(secret, "***")
    return text


# ---------------------------------------------------------------- archivio

class StageStore:
    """Un file per claim e un file per record, entrambi create-only."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.claims = self.root / "claims"
        self.records = self.root / "records"
        self.released = self.root / "released_claims"
        for folder in (self.claims, self.records, self.released):
            folder.mkdir(parents=True, exist_ok=True)

    # -- primitive
    @staticmethod
    def _write_new(path: Path, payload: dict) -> None:
        data = (_dumps(payload) + "\n").encode("utf-8")
        # O_EXCL: se il file esiste gia' solleva FileExistsError (create-only).
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            view = memoryview(data)
            while view:
                written = os.write(fd, view)
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)

    @staticmethod
    def _read(path: Path, sha_field: str) -> dict | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise StoreCorrupt("File illeggibile: " + path.name) from exc
        if type(payload) is not dict or sha_field not in payload:
            raise StoreCorrupt("File senza hash: " + path.name)
        core = {k: v for k, v in payload.items() if k != sha_field}
        if _sha(core) != payload[sha_field]:
            raise StoreCorrupt("Hash non coerente: " + path.name)
        return payload

    # -- claim
    def _claim_path(self, stage_id: str) -> Path:
        return self.claims / f"V5_CLAIM_{_key(stage_id)}.json"

    def _record_path(self, stage_id: str) -> Path:
        return self.records / f"V5_RECORD_{_key(stage_id)}.json"

    def load_claim(self, stage_id: str) -> dict | None:
        return self._read(self._claim_path(stage_id), "claim_sha256")

    def load_record(self, stage_id: str) -> dict | None:
        return self._read(self._record_path(stage_id), "record_sha256")

    def claim(self, stage_id: str, info: dict) -> dict:
        core = {"schema": CLAIM_SCHEMA, "protocol": PROTOCOL,
                "stage_id": stage_id, "claimed_at_utc": _now(), **info}
        claim = {**core, "claim_sha256": _sha(core)}
        try:
            self._write_new(self._claim_path(stage_id), claim)
        except FileExistsError as exc:
            raise ClaimExists(stage_id) from exc
        return claim

    def write_record(self, stage_id: str, body: dict) -> dict:
        core = {"schema": RECORD_SCHEMA, "protocol": PROTOCOL,
                "runner_version": VERSION, "stage_id": stage_id, **body}
        record = {**core, "record_sha256": _sha(core)}
        try:
            self._write_new(self._record_path(stage_id), record)
        except FileExistsError as exc:
            raise RecordExists(stage_id) from exc
        return record

    def orphans(self, stage_ids) -> list[str]:
        return [s for s in stage_ids
                if self._claim_path(s).exists()
                and not self._record_path(s).exists()]

    def release_orphan(self, stage_id: str, reason: str) -> dict:
        """Sblocca ESPLICITAMENTE un claim orfano, lasciando traccia.

        Non e' mai chiamata dal runner. Va usata solo dopo aver verificato a
        mano che lo stage non abbia prodotto un record, e la decisione va
        dichiarata nella tesi (run interrotto, possibile costo gia' sostenuto).
        """
        if type(reason) is not str or len(reason.strip()) < 10:
            raise StoreError("Motivazione esplicita obbligatoria")
        path = self._claim_path(stage_id)
        if not path.exists() or self._record_path(stage_id).exists():
            raise StoreError("Non e' un claim orfano")
        claim = self.load_claim(stage_id)
        n = len(list(self.released.glob(path.stem + ".*.json"))) + 1
        target = self.released / f"{path.stem}.{n}.json"
        os.replace(path, target)
        entry = {"stage_id": stage_id, "released_at_utc": _now(),
                 "reason": reason.strip(), "claim_sha256": claim["claim_sha256"],
                 "archived_as": target.name}
        with open(self.released / "log.jsonl", "a", encoding="utf-8") as log:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry


# ---------------------------------------------------------------- piano

def required_parents(row: dict) -> list[str]:
    """Genitori richiesti: C dipende da D; K da D e C (stesso stem)."""
    stem = row["stage_id"].rsplit(":", 1)[0]
    stage = row["stage"]
    if stage == "D":
        parents = []
    elif stage == "C":
        parents = [stem + ":D"]
    elif stage == "K":
        parents = [stem + ":D", stem + ":C"]
    else:
        raise PlanMismatch("Stage sconosciuto: " + repr(stage))
    if not set(row["depends_on"]).issubset(parents):
        raise PlanMismatch("Dipendenze del piano diverse da D->C->K")
    return parents


def validate_plan(rows: list[dict]) -> None:
    ids = [r["stage_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise PlanMismatch("stage_id duplicati")
    seen: set[str] = set()
    for row in rows:
        for parent in required_parents(row):
            if parent not in seen:
                raise PlanMismatch("Genitore non precede il figlio: " + parent)
        seen.add(row["stage_id"])


def select_rows(rows: list[dict], *, models=None, harnesses=None,
                cases=None, stages=None) -> list[dict]:
    """Filtra il piano mantenendo l'ordine; nomi sconosciuti = errore."""
    for label, wanted, key in (
        ("modello", models, "logical_model"), ("harness", harnesses, "harness"),
        ("caso", cases, "case_id"), ("stage", stages, "stage"),
    ):
        if wanted is not None:
            known = {r[key] for r in rows}
            unknown = set(wanted) - known
            if unknown:
                raise PlanMismatch(f"{label} sconosciuto: {sorted(unknown)}")
    return [
        r for r in rows
        if (models is None or r["logical_model"] in models)
        and (harnesses is None or r["harness"] in harnesses)
        and (cases is None or r["case_id"] in cases)
        and (stages is None or r["stage"] in stages)
    ]


# ---------------------------------------------------------------- esecuzione

def _blocked_record(store: StageStore, row: dict, parent_id: str,
                    parent_status: str) -> dict:
    return store.write_record(row["stage_id"], {
        **_identity(row),
        "status": STATUS_BLOCKED,
        "blocked_by": {"stage_id": parent_id, "status": parent_status},
        "receipt": None, "format": None, "provenance": None,
        "error_summary": None, "claim_sha256": None,
        "started_at_utc": None, "finished_at_utc": _now(),
        "elapsed_seconds": 0.0, "source_commit": None,
    })


def _identity(row: dict) -> dict:
    return {k: row[k] for k in (
        "stage", "case_id", "logical_model", "model_id",
        "model_provider", "harness",
    )}


def _block_descendants(store: StageStore, plan: list[dict], row: dict,
                       status: str) -> list[str]:
    """Scrive BLOCKED_DEPENDENCY per i discendenti dello stage fallito."""
    stem = row["stage_id"].rsplit(":", 1)[0]
    written = []
    for child in plan:
        if (child["stage_id"].rsplit(":", 1)[0] != stem
                or child["stage_id"] == row["stage_id"]
                or row["stage_id"] not in required_parents(child)):
            continue
        if (store.load_record(child["stage_id"]) is None
                and store.load_claim(child["stage_id"]) is None):
            _blocked_record(store, child, row["stage_id"], status)
            written.append(child["stage_id"])
    return written


def run_stage(row: dict, *, plan: list[dict], store: StageStore, executor,
              source_commit: str | None = None, secrets=(), log=print) -> str:
    """Un solo stage. Restituisce un codice azione (costanti ACTION_*)."""
    stage_id = row["stage_id"]
    if store.load_record(stage_id) is not None:
        return ACTION_ALREADY
    if store.load_claim(stage_id) is not None:
        log(f"  ORFANO {stage_id}: claim senza record, NON riesegue")
        return ACTION_ORPHAN

    parents = {}
    for parent_id in required_parents(row):
        record = store.load_record(parent_id)
        if record is None:
            return ACTION_WAITING
        if record["status"] != STATUS_COMPLETE:
            _blocked_record(store, row, parent_id, record["status"])
            return ACTION_BLOCKED
        parents[parent_id] = record

    # Tutto cio' che puo' fallire OFFLINE avviene prima del claim.
    try:
        prepared = executor.prepare(row, parents)
    except Exception as exc:  # noqa: BLE001 - fermiamo il lotto, nessun claim
        log(f"  PREPARAZIONE FALLITA {stage_id}: {type(exc).__name__}: "
            + _redact(str(exc), secrets)[:300])
        return ACTION_PREPARE_FAILED

    try:
        claim = store.claim(stage_id, {**_identity(row),
                                       "source_commit": source_commit})
    except ClaimExists:
        # Un altro processo (o un altro notebook Colab) l'ha preso: non toccare.
        return ACTION_ORPHAN
    started = time.monotonic()
    started_at = _now()
    error_summary = None
    try:
        outcome = executor.run(row, prepared)
        if (type(outcome) is not dict
                or outcome.get("status") not in EXECUTOR_STATUSES):
            raise StoreError("Esito dell'esecutore non valido")
    except Exception as exc:  # noqa: BLE001 - dopo il claim: registra e basta
        text = _redact(traceback.format_exc(), secrets)
        log("  ECCEZIONE nello stage (traceback sotto, solo qui, non salvato):")
        log(text[-1500:])
        error_summary = {
            "code": "EXECUTOR_EXCEPTION:" + type(exc).__name__,
            "message_sha256": hashlib.sha256(
                str(exc).encode("utf-8")).hexdigest(),
        }
        outcome = {"status": STATUS_PROVIDER_ERROR, "receipt": None,
                   "format": None, "provenance": None}

    status = outcome["status"]
    body = {
        **_identity(row),
        "status": status,
        "receipt": outcome.get("receipt"),
        "format": outcome.get("format"),
        "provenance": outcome.get("provenance"),
        "error_summary": error_summary or outcome.get("error_summary"),
        "blocked_by": None,
        "claim_sha256": claim["claim_sha256"],
        "started_at_utc": started_at, "finished_at_utc": _now(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "source_commit": source_commit,
    }
    try:
        store.write_record(stage_id, body)
    except (TypeError, ValueError) as exc:
        # Esito non serializzabile: non perdere lo stage (il claim e' preso).
        status = STATUS_RECEIPT_REJECTED
        store.write_record(stage_id, {**body, "status": status,
                                      "receipt": None, "format": None,
                                      "provenance": None,
                                      "error_summary": {
            "code": "RECORD_SERIALIZATION_ERROR:" + type(exc).__name__}})
    if status != STATUS_COMPLETE:
        _block_descendants(store, plan, row, status)
    return ACTION_EXECUTED


def run_matrix(rows: list[dict], *, plan: list[dict], store: StageStore,
               executor, source_commit: str | None = None,
               max_stages: int | None = None,
               time_budget_seconds: float | None = None,
               secrets=(), log=print) -> dict:
    """Esegue le righe selezionate, in ordine di piano.

    max_stages conta solo gli stage realmente eseguiti (cioe' con claim).
    Si ferma subito se la preparazione di uno stage fallisce: e' quasi sempre
    un problema sistematico (dati, chiavi, pacchetti) e non va ripetuto 60 volte.
    """
    validate_plan(plan)
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
        action = run_stage(row, plan=plan, store=store, executor=executor,
                           source_commit=source_commit, secrets=secrets,
                           log=log)
        counts[action] = counts.get(action, 0) + 1
        if action == ACTION_EXECUTED:
            executed += 1
            record = store.load_record(row["stage_id"])
            log(f"  -> {record['status']} ({record['elapsed_seconds']} s)")
        elif action == ACTION_PREPARE_FAILED:
            stopped = "prepare_failed"
            break
    return {"actions": counts, "executed": executed, "stopped": stopped}


# ---------------------------------------------------------------- riepilogo

def conformity(record: dict) -> dict:
    """Conformita' strict e tollerante di UNO stage con output del modello.

    strict: il modello ha emesso direttamente JSON valido (nessuna deviazione).
    tolerant: la risposta e' valida dopo la normalizzazione V5 (un solo fence).
    Un fence viene sempre rifiutato dal parser strict, quindi non serve
    rieseguire il parser: strict = completo e deviation NONE.
    """
    fmt = record.get("format") or {}
    if record["status"] not in MODEL_OUTPUT_STATUSES:
        return {"has_output": False, "strict": None, "tolerant": None,
                "deviation": None}
    complete = record["status"] == STATUS_COMPLETE
    return {
        "has_output": True,
        "strict": complete and fmt.get("deviation") == "NONE",
        "tolerant": complete,
        "deviation": fmt.get("deviation"),
    }


def summarize(plan: list[dict], store: StageStore) -> dict:
    """Stato complessivo: stage per esito e conformita' per modello."""
    by_cell: dict[str, dict[str, int]] = {}
    conf: dict[str, dict[str, int]] = {}
    pending = orphan = 0
    for row in plan:
        record = store.load_record(row["stage_id"])
        cell = f"{row['logical_model']}|{row['harness']}|{row['stage']}"
        if record is None:
            if store.load_claim(row["stage_id"]) is not None:
                orphan += 1
                label = "ORPHAN"
            else:
                pending += 1
                label = "PENDING"
        else:
            label = record["status"]
            c = conformity(record)
            if c["has_output"]:
                m = conf.setdefault(row["logical_model"], {
                    "with_output": 0, "strict_ok": 0, "tolerant_ok": 0,
                    "fence": 0, "rejected_wrapper": 0})
                m["with_output"] += 1
                m["strict_ok"] += int(bool(c["strict"]))
                m["tolerant_ok"] += int(bool(c["tolerant"]))
                m["fence"] += int(c["deviation"] == "SINGLE_JSON_FENCE")
                m["rejected_wrapper"] += int(
                    c["deviation"] == "REJECTED_WRAPPER")
        by_cell.setdefault(cell, {})
        by_cell[cell][label] = by_cell[cell].get(label, 0) + 1
    return {"stages": len(plan), "pending": pending, "orphan": orphan,
            "by_cell": by_cell, "conformity_by_model": conf}


def format_summary(summary: dict) -> str:
    lines = [f"Stage nel piano: {summary['stages']} | da fare: "
             f"{summary['pending']} | orfani: {summary['orphan']}", ""]
    lines.append("Conformita' al formato (solo stage con output del modello):")
    for model, m in sorted(summary["conformity_by_model"].items()):
        lines.append(
            f"  {model:7s} output={m['with_output']:3d}  "
            f"strict={m['strict_ok']:3d}  tollerante={m['tolerant_ok']:3d}  "
            f"fence={m['fence']:3d}  wrapper_rifiutati={m['rejected_wrapper']:3d}")
    lines.append("")
    lines.append("Esiti per modello|harness|stage:")
    for cell, counts in sorted(summary["by_cell"].items()):
        inner = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        lines.append(f"  {cell}: {inner}")
    return "\n".join(lines)
