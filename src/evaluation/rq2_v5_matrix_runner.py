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

Contenuto
---------
- costanti di protocollo, di stato degli stage e di azione del runner;
- `StageStore`: l'archivio su disco (un file di claim e uno di record per stage, create-only);
- `required_parents`, `validate_plan`, `select_rows`: lettura e filtro del piano;
- `run_stage` e `run_matrix`: esecuzione di uno stage e del lotto selezionato;
- `conformity`, `summarize`, `format_summary`: riepilogo di esiti e conformita' al formato.

Vocabolario
-----------
- stage: un passo del piano; D = diagnosi dell'agente, C = ipotesi di causa, K = regola candidata;
- claim: file che "prenota" uno stage prima della chiamata a pagamento; record: file con l'esito;
- orfano: claim senza record (esecuzione interrotta); mai rieseguito da solo.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Versione del runner e nome del protocollo: finiscono in ogni claim e in ogni record.
VERSION = "rq2_v5_matrix_runner_v0"
PROTOCOL = "rq2_v5_format_fair_matrix_v0"
# Cartella (sotto la radice dei dati) in cui vive l'archivio del run scientifico.
NAMESPACE = Path("data/rq2_v5_format_fair_v1")

# Nomi degli schemi dei due tipi di file dell'archivio.
RECORD_SCHEMA = "rq2_v5_stage_record_v0"
CLAIM_SCHEMA = "rq2_v5_stage_claim_v0"

# Esiti possibili di uno stage (campo `status` del record):
#   RECORDED_COMPLETE   risposta valida e ricevuta accettata;
#   INVALID_OUTPUT      il modello ha risposto, ma l'output non rispetta il contratto;
#   PROVIDER_ERROR      errore del provider/trasporto, nessun output utilizzabile;
#   BLOCKED_DEPENDENCY  stage mai eseguito perche' un genitore non e' completo.
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
# Esiti che l'esecutore reale puo' restituire (BLOCKED lo scrive solo il runner).
EXECUTOR_STATUSES = (
    STATUS_COMPLETE, STATUS_INVALID, STATUS_PROVIDER_ERROR,
    STATUS_RECEIPT_REJECTED,
)
# Esiti in cui il modello ha davvero prodotto un testo (servono alla conformita' al formato).
MODEL_OUTPUT_STATUSES = (STATUS_COMPLETE, STATUS_INVALID)

# Cosa ha fatto `run_stage` per uno stage (valore restituito e chiave dei conteggi del lotto).
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
    """JSON leggibile (indentato, chiavi ordinate) usato per scrivere claim e record su file."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      indent=2, allow_nan=True)


def _sha(value: object) -> str:
    """SHA-256 del JSON "canonico" di `value` (chiavi ordinate, senza spazi).

    E' la funzione che produce `claim_sha256` e `record_sha256`; la stessa e' usata da
    `rq2_k_run_integrity` per verificare che i file non siano stati alterati.
    """
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=True,
    ).encode("utf-8")).hexdigest()


def _key(stage_id: str) -> str:
    """Chiave del file di uno stage: SHA-256 del suo `stage_id` (nome file sicuro e univoco)."""
    return hashlib.sha256(stage_id.encode("utf-8")).hexdigest()


def _now() -> str:
    """Istante attuale in UTC, formato ISO senza frazioni (es. 2026-11-17T09:30:00Z)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _redact(text: str, secrets) -> str:
    """Sostituisce con *** ogni segreto (chiave API) presente nel testo, prima di stamparlo.

    Si considerano solo stringhe di almeno 8 caratteri, per non oscurare testo comune.
    """
    for secret in secrets:
        if type(secret) is str and len(secret) >= 8:
            text = text.replace(secret, "***")
    return text


# ---------------------------------------------------------------- archivio

class StageStore:
    """Un file per claim e un file per record, entrambi create-only.

    Struttura della cartella `root`: `claims/` (un claim per stage avviato), `records/` (un
    record per stage concluso o bloccato) e `released_claims/` (claim orfani sbloccati a mano,
    con un registro `log.jsonl`). Ogni file contiene il proprio SHA-256: chi lo legge verifica
    che non sia stato alterato. Nessun file viene mai riscritto.
    """

    def __init__(self, root: Path):
        """Prepara le tre cartelle (le crea se mancano). `root` e' la cartella dell'archivio."""
        self.root = Path(root)
        self.claims = self.root / "claims"
        self.records = self.root / "records"
        self.released = self.root / "released_claims"
        for folder in (self.claims, self.records, self.released):
            folder.mkdir(parents=True, exist_ok=True)

    # -- primitive
    @staticmethod
    def _write_new(path: Path, payload: dict) -> None:
        """Scrive `payload` come JSON in un file NUOVO: se esiste gia', `FileExistsError`.

        Il file viene scritto per intero e forzato su disco (`fsync`) prima di chiuderlo,
        cosi' un'interruzione non lascia un file a meta' creduto valido.
        """
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
        """Legge un file dell'archivio e ne verifica l'hash.

        Restituisce None se il file non esiste; solleva `StoreCorrupt` se e' illeggibile,
        privo del campo hash (`sha_field`) o con hash non coerente con il contenuto.
        """
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
        """Percorso del file di claim di uno stage."""
        return self.claims / f"V5_CLAIM_{_key(stage_id)}.json"

    def _record_path(self, stage_id: str) -> Path:
        """Percorso del file di record di uno stage."""
        return self.records / f"V5_RECORD_{_key(stage_id)}.json"

    def load_claim(self, stage_id: str) -> dict | None:
        """Claim dello stage (con hash verificato) oppure None se non esiste."""
        return self._read(self._claim_path(stage_id), "claim_sha256")

    def load_record(self, stage_id: str) -> dict | None:
        """Record dello stage (con hash verificato) oppure None se non esiste."""
        return self._read(self._record_path(stage_id), "record_sha256")

    def claim(self, stage_id: str, info: dict) -> dict:
        """Prenota lo stage scrivendo il claim (create-only) PRIMA della chiamata a pagamento.

        `info` aggiunge campi (identita' dello stage, commit del codice). Se il claim esiste
        gia' solleva `ClaimExists`: lo stage e' stato gia' tentato e non va rieseguito.
        """
        core = {"schema": CLAIM_SCHEMA, "protocol": PROTOCOL,
                "stage_id": stage_id, "claimed_at_utc": _now(), **info}
        claim = {**core, "claim_sha256": _sha(core)}
        try:
            self._write_new(self._claim_path(stage_id), claim)
        except FileExistsError as exc:
            raise ClaimExists(stage_id) from exc
        return claim

    def write_record(self, stage_id: str, body: dict) -> dict:
        """Scrive il record (create-only) con l'esito dello stage; `body` e' il contenuto.

        Aggiunge schema, protocollo, versione del runner e l'hash. Se il record esiste gia'
        solleva `RecordExists`.
        """
        core = {"schema": RECORD_SCHEMA, "protocol": PROTOCOL,
                "runner_version": VERSION, "stage_id": stage_id, **body}
        record = {**core, "record_sha256": _sha(core)}
        try:
            self._write_new(self._record_path(stage_id), record)
        except FileExistsError as exc:
            raise RecordExists(stage_id) from exc
        return record

    def orphans(self, stage_ids) -> list[str]:
        """Tra gli `stage_ids` dati, quelli con claim ma senza record (stage interrotti)."""
        return [s for s in stage_ids
                if self._claim_path(s).exists()
                and not self._record_path(s).exists()]

    def release_orphan(self, stage_id: str, reason: str) -> dict:
        """Sblocca ESPLICITAMENTE un claim orfano, lasciando traccia.

        Non e' mai chiamata dal runner. Va usata solo dopo aver verificato a
        mano che lo stage non abbia prodotto un record, e la decisione va
        dichiarata nella tesi (run interrotto, possibile costo gia' sostenuto).

        Argomenti: `stage_id` dello stage orfano e `reason` (motivazione di almeno 10 caratteri).
        Restituisce la voce scritta nel registro `released_claims/log.jsonl`.
        """
        # La motivazione e' obbligatoria: lo sblocco deve lasciare una traccia leggibile.
        if type(reason) is not str or len(reason.strip()) < 10:
            raise StoreError("Motivazione esplicita obbligatoria")
        path = self._claim_path(stage_id)
        # Si sblocca solo un vero orfano: claim presente e record assente.
        if not path.exists() or self._record_path(stage_id).exists():
            raise StoreError("Non e' un claim orfano")
        claim = self.load_claim(stage_id)
        # Il claim non si cancella: si sposta in `released_claims/` con un numero progressivo.
        n = len(list(self.released.glob(path.stem + ".*.json"))) + 1
        target = self.released / f"{path.stem}.{n}.json"
        os.replace(path, target)
        # Voce di registro: una riga JSON aggiunta in coda a `log.jsonl` (mai riscritta).
        entry = {"stage_id": stage_id, "released_at_utc": _now(),
                 "reason": reason.strip(), "claim_sha256": claim["claim_sha256"],
                 "archived_as": target.name}
        with open(self.released / "log.jsonl", "a", encoding="utf-8") as log:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry


# ---------------------------------------------------------------- piano

def required_parents(row: dict) -> list[str]:
    """Genitori richiesti: C dipende da D; K da D e C (stesso stem).

    Lo "stem" e' lo `stage_id` senza l'ultimo pezzo (":D", ":C" o ":K"): identifica la
    cella (modello, harness, caso). Solleva `PlanMismatch` se lo stage e' sconosciuto o se
    le dipendenze dichiarate nel piano non sono un sottoinsieme di quelle attese.
    """
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
    """Controlla il piano: `stage_id` tutti diversi e ogni genitore PRIMA del figlio.

    Non restituisce nulla; solleva `PlanMismatch` al primo problema.
    """
    ids = [r["stage_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise PlanMismatch("stage_id duplicati")
    # `seen` raccoglie gli stage gia' incontrati: un genitore deve starci prima del figlio.
    seen: set[str] = set()
    for row in rows:
        for parent in required_parents(row):
            if parent not in seen:
                raise PlanMismatch("Genitore non precede il figlio: " + parent)
        seen.add(row["stage_id"])


def select_rows(rows: list[dict], *, models=None, harnesses=None,
                cases=None, stages=None) -> list[dict]:
    """Filtra il piano mantenendo l'ordine; nomi sconosciuti = errore.

    Argomenti: `rows` (piano completo) e quattro filtri opzionali (insiemi di modelli
    logici, harness, casi, stage). None = nessun filtro su quel campo.
    """
    # Un nome che non compare nel piano e' quasi sempre un errore di battitura: si rifiuta.
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
    """Scrive il record BLOCKED_DEPENDENCY di uno stage il cui genitore non e' completo.

    Nessun claim e nessuna chiamata al modello: il record dice solo quale genitore
    (`parent_id`, con il suo `parent_status`) ha impedito l'esecuzione.
    """
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
    """Campi che identificano uno stage (stage, caso, modello, provider, harness): vanno
    identici nella riga del piano, nel claim e nel record."""
    return {k: row[k] for k in (
        "stage", "case_id", "logical_model", "model_id",
        "model_provider", "harness",
    )}


def _block_descendants(store: StageStore, plan: list[dict], row: dict,
                       status: str) -> list[str]:
    """Scrive BLOCKED_DEPENDENCY per i discendenti dello stage fallito.

    Argomenti: `store`, `plan` (piano completo), `row` (lo stage fallito) e `status` (il suo
    esito). Restituisce gli `stage_id` bloccati. Sono "discendenti" gli stage della stessa
    cella (stesso stem) che hanno `row` fra i genitori; si bloccano solo quelli che non hanno
    ne' record ne' claim.
    """
    stem = row["stage_id"].rsplit(":", 1)[0]
    written = []
    for child in plan:
        # Si saltano gli stage di altre celle, lo stage stesso e quelli che non ne dipendono.
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
    """Un solo stage. Restituisce un codice azione (costanti ACTION_*).

    Argomenti:
      row            riga del piano per lo stage da eseguire;
      plan           piano completo (serve a bloccare i discendenti se lo stage fallisce);
      store          archivio `StageStore`;
      executor       oggetto con `prepare(row, parents)` e `run(row, prepared)` (iniettato);
      source_commit  commit del codice, registrato in claim e record;
      secrets        chiavi API da oscurare nei messaggi stampati;
      log            funzione di stampa (di default `print`).

    Passi:
      1. se esiste gia' il record: ALREADY_RECORDED; se esiste solo il claim: ORFANO, mai rieseguito;
      2. per ogni genitore: record mancante -> WAITING_PARENT; genitore non completo -> si scrive
         il record BLOCKED_DEPENDENCY (nessuna chiamata al modello);
      3. `prepare` (tutto cio' che puo' fallire OFFLINE) PRIMA del claim: se fallisce, nessun claim;
      4. claim create-only, poi una sola esecuzione a pagamento (`executor.run`);
      5. un'eccezione dopo il claim diventa PROVIDER_ERROR (senza testo dell'errore nel record);
      6. si scrive il record; se l'esito non e' completo si bloccano i discendenti.
    """
    stage_id = row["stage_id"]
    # 1. Stage gia' concluso o gia' tentato.
    if store.load_record(stage_id) is not None:
        return ACTION_ALREADY
    if store.load_claim(stage_id) is not None:
        log(f"  ORFANO {stage_id}: claim senza record, NON riesegue")
        return ACTION_ORPHAN

    # 2. Dipendenze: tutti i genitori devono essere completi, altrimenti si attende o si blocca.
    parents = {}
    for parent_id in required_parents(row):
        record = store.load_record(parent_id)
        if record is None:
            return ACTION_WAITING
        if record["status"] != STATUS_COMPLETE:
            _blocked_record(store, row, parent_id, record["status"])
            return ACTION_BLOCKED
        parents[parent_id] = record

    # 3. Tutto cio' che puo' fallire OFFLINE avviene prima del claim.
    try:
        prepared = executor.prepare(row, parents)
    except Exception as exc:  # noqa: BLE001 - fermiamo il lotto, nessun claim
        log(f"  PREPARAZIONE FALLITA {stage_id}: {type(exc).__name__}: "
            + _redact(str(exc), secrets)[:300])
        return ACTION_PREPARE_FAILED

    # 4. Claim create-only: se qualcuno l'ha gia' preso, non si esegue.
    try:
        claim = store.claim(stage_id, {**_identity(row),
                                       "source_commit": source_commit})
    except ClaimExists:
        # Un altro processo (o un altro notebook Colab) l'ha preso: non toccare.
        return ACTION_ORPHAN
    # Da qui in poi lo stage e' "a pagamento": si misurano tempo di inizio e durata.
    started = time.monotonic()
    started_at = _now()
    error_summary = None
    try:
        outcome = executor.run(row, prepared)
        # L'esito dell'esecutore deve essere un dizionario con uno stato ammesso.
        if (type(outcome) is not dict
                or outcome.get("status") not in EXECUTOR_STATUSES):
            raise StoreError("Esito dell'esecutore non valido")
    except Exception as exc:  # noqa: BLE001 - dopo il claim: registra e basta
        # 5. Il traceback (con i segreti oscurati) si stampa soltanto; nel record resta solo il
        # tipo di eccezione e l'hash del messaggio.
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

    # 6. Contenuto del record: identita', esito, ricevuta, registro del formato, provenienza,
    # hash del claim, tempi e commit.
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
    # Scrittura del record (create-only).
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
    # Uno stage non completo impedisce quelli che ne dipendono (C dopo D, K dopo D e C).
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

    Argomenti: `rows` (stage selezionati, in ordine), `plan` (piano completo), `store`,
    `executor`, `source_commit`, `max_stages` (tetto di stage eseguiti), `time_budget_seconds`
    (tetto di tempo), `secrets` e `log`.

    Restituisce un dizionario con i conteggi per azione (`actions`), il numero di stage
    eseguiti (`executed`) e il motivo dell'arresto anticipato (`stopped`: `max_stages`,
    `time_budget`, `prepare_failed` oppure None se si e' arrivati in fondo).
    """
    # Il piano deve essere coerente (genitori prima dei figli) prima di partire.
    validate_plan(plan)
    counts: dict[str, int] = {}
    started = time.monotonic()
    executed = 0
    stopped = None
    for row in rows:
        # Limiti del lotto: numero massimo di stage eseguiti e tempo massimo.
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

    Restituisce `has_output` (il modello ha prodotto un testo), `strict`, `tolerant` e la
    `deviation` registrata; gli ultimi tre sono None se non c'e' output del modello.
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


def _k_outcome(record: dict) -> str:
    """Esito di un K completo: candidate / insufficient_evidence / altro.

    Serve a distinguere 'contratto rispettato' da 'regola proposta': un K
    puo' essere RECORDED_COMPLETE e comunque astenersi.
    """
    try:
        raw = record["receipt"]["artifact"]["raw_response"]
        status = json.loads(raw).get("status")
    except (KeyError, TypeError, ValueError, AttributeError):
        return "non_leggibile"
    return status if status in ("candidate", "insufficient_evidence") else "altro"


def summarize(plan: list[dict], store: StageStore) -> dict:
    """Stato complessivo: stage per esito e conformita' per modello.

    Argomenti: `plan` (stage da riassumere) e `store`. Restituisce un dizionario con: numero di
    stage, da fare (`pending`), orfani, esiti per cella "modello|harness|stage" (`by_cell`),
    conformita' al formato per modello, stage ritentati e recuperati per modello, ed esiti dei K
    completi (regola candidata o astensione) per modello.
    """
    by_cell: dict[str, dict[str, int]] = {}
    conf: dict[str, dict[str, int]] = {}
    retry: dict[str, dict[str, int]] = {}
    k_out: dict[str, dict[str, int]] = {}
    pending = orphan = 0
    for row in plan:
        record = store.load_record(row["stage_id"])
        cell = f"{row['logical_model']}|{row['harness']}|{row['stage']}"
        # Senza record: ORPHAN se esiste il claim (interrotto), altrimenti PENDING (da fare).
        if record is None:
            if store.load_claim(row["stage_id"]) is not None:
                orphan += 1
                label = "ORPHAN"
            else:
                pending += 1
                label = "PENDING"
        else:
            label = record["status"]
            # Conformita' al formato: solo per gli stage in cui il modello ha prodotto un testo.
            c = conformity(record)
            if c["has_output"]:
                m = conf.setdefault(row["logical_model"], {
                    "with_output": 0, "strict_ok": 0, "tolerant_ok": 0,
                    "fence": 0, "outside_text": 0, "rejected_wrapper": 0})
                m["with_output"] += 1
                m["strict_ok"] += int(bool(c["strict"]))
                m["tolerant_ok"] += int(bool(c["tolerant"]))
                m["fence"] += int(c["deviation"] == "SINGLE_JSON_FENCE")
                m["outside_text"] += int(
                    c["deviation"] == "FENCE_WITH_OUTSIDE_TEXT")
                m["rejected_wrapper"] += int(
                    c["deviation"] == "REJECTED_WRAPPER")
            # Stage ritentati (piu' di un tentativo) e, fra questi, quelli recuperati (completi).
            attempts = ((record.get("provenance") or {}).get("retry") or {}
                        ).get("attempts") or []
            if len(attempts) > 1:
                r = retry.setdefault(row["logical_model"],
                                     {"retried": 0, "recovered": 0})
                r["retried"] += 1
                r["recovered"] += int(record["status"] == STATUS_COMPLETE)
            # Esito dei K completi: regola proposta, astensione o altro.
            if row["stage"] == "K" and record["status"] == STATUS_COMPLETE:
                k = k_out.setdefault(row["logical_model"], {})
                outcome_label = _k_outcome(record)
                k[outcome_label] = k.get(outcome_label, 0) + 1
        by_cell.setdefault(cell, {})
        by_cell[cell][label] = by_cell[cell].get(label, 0) + 1
    return {"stages": len(plan), "pending": pending, "orphan": orphan,
            "by_cell": by_cell, "conformity_by_model": conf,
            "retry_by_model": retry, "k_outcomes_by_model": k_out}


def format_summary(summary: dict) -> str:
    """Testo leggibile del riepilogo di `summarize`: conformita' al formato per modello,
    retry, esiti dei K ed esiti per cella (modello|harness|stage)."""
    lines = [f"Stage nel piano: {summary['stages']} | da fare: "
             f"{summary['pending']} | orfani: {summary['orphan']}", ""]
    lines.append("Conformita' al formato (solo stage con output del modello):")
    for model, m in sorted(summary["conformity_by_model"].items()):
        lines.append(
            f"  {model:7s} output={m['with_output']:3d}  "
            f"strict={m['strict_ok']:3d}  tollerante={m['tolerant_ok']:3d}  "
            f"fence={m['fence']:3d}  fence+testo={m['outside_text']:3d}  "
            f"wrapper_rifiutati={m['rejected_wrapper']:3d}")
    lines.append("")
    if summary.get("retry_by_model"):
        lines.append("Retry per errore di trasporto (secondo tentativo):")
        for model, r in sorted(summary["retry_by_model"].items()):
            lines.append(f"  {model:7s} ritentati={r['retried']:3d}  "
                         f"recuperati={r['recovered']:3d}")
        lines.append("")
    if summary.get("k_outcomes_by_model"):
        lines.append("Esito dei K completi (regola proposta o astensione):")
        for model, k in sorted(summary["k_outcomes_by_model"].items()):
            inner = ", ".join(f"{n}={v}" for n, v in sorted(k.items()))
            lines.append(f"  {model:7s} {inner}")
        lines.append("")
    lines.append("Esiti per modello|harness|stage:")
    for cell, counts in sorted(summary["by_cell"].items()):
        inner = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        lines.append(f"  {cell}: {inner}")
    return "\n".join(lines)
