"""RQ2-V2 Opzione A: ledger scientifico comune create-only, NO MODEL API.

RELEASE SEPARATA OBBLIGATORIA: il file release_v1.json deve gia'
esistere, con SHA256 esterno, commit Git clean ed espliciti presupposti.
Questo modulo NON crea release, NON costruisce LLM e NON effettua API.

D/C/K: una sola matrice 4 discovery x 5 harness x 3 provider. I claim sono
durabili prima di ogni futura richiesta; un claim senza record blocca
nuovi stage fino a riconciliazione MANUALE, senza retry automatico.
Il record e' O_EXCL + fsync + readback, con parent SHA, release SHA e
ricevuta di metering. Errori provider/JSON restano errori nel denominatore.

Il lock per processo e' solo un meccanismo candidato da verificare
sul filesystem reale Google Drive PRIMA della release scientifica.
Una release futura dovra' includere questo file nell'inventario
source-bound, verificare trasporti e approvazione API separatamente.

Contenuto
---------
- costanti: stati ammessi di un record, chiavi vietate (ground truth), limite di dimensione;
- funzioni di utilita': `_canonical`/`_sha` (JSON e hash canonici), `_no_gt` (nessuna chiave
  di ground truth), `_read`/`_write_once` (lettura sicura e scrittura create-only),
  `_meter` (ricevuta del contatore), `_validate_artifact` (l'output di uno stage e' coerente
  con il suo stato), `_writer_lock` (lock di scrittura del sistema operativo);
- `UnifiedScientificLedger`: il registro. `load_claim`/`load_record` rileggono e verificano,
  `audit_restart` controlla tutto il registro, `claim_stage` e `record_stage` scrivono;
- `create_authorized_scientific_release_once`: crea il file della release, disattivata di
  default (serve un opt-in di processo ESATTO e ulteriori approvazioni esterne).

Per ogni stage si scrivono due file in sequenza: prima il "claim" (la richiesta di esecuzione,
durabile PRIMA di qualsiasi chiamata futura) poi il "record" (il risultato). Un claim senza
record e' un "orfano" e blocca ogni altro stage finche' non e' riconciliato a mano.
"""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from evaluation.rq2_evidence_bundle import (
    EvidenceBundleError, build_evidence_bundle, evidence_ids,
)
from evaluation.rq2_output_contracts import (
    ContractError, validate_candidate_rule, validate_cause_probe,
)
from evaluation.rq2_stage_binding import ALLOWED_TOOLS
from evaluation.rq2_v2_unified_discovery_plan import (
    VERSION as PROTOCOL, build_offline_discovery_plan,
)
from evaluation.rq2_v2_unified_provenance_gate import (
    UnifiedRQ2ProvenanceError, audit_captured_v2_d,
)
from evaluation.rq2_v2_unified_release_preflight import (
    preview_unified_source_bound,
)
from evaluation.rq2_v2_unified_release_blueprint import (
    build_unified_release_blueprint,
)
from evaluation.rq2_v2_unified_scientific_release_contract import (
    canonical_release, release_digest, validate_future_release,
)
from evaluation.rq2_v2_unified_scientific_ledger_preflight import (
    NAMESPACE, RELEASE_FILE, CLAIMS, RECORDS, _strict_absolute,
    _repository_commit, preview_scientific_ledger_gate,
)

VERSION = "rq2_v2_unified_scientific_ledger_v0"
# File di lock di scrittura, dentro il namespace dei dati scientifici.
LOCK_FILE = NAMESPACE / ".writer.lock"
# Stati ammessi per un record: completo, output non valido, errore del provider, oppure bloccato
# perche' lo stage da cui dipende non e' completo. Errori e output non validi restano nel
# denominatore della valutazione.
STATUSES = frozenset((
    "RECORDED_COMPLETE", "INVALID_OUTPUT", "PROVIDER_ERROR",
    "BLOCKED_DEPENDENCY",
))
# Un hash SHA-256 valido: 64 caratteri esadecimali minuscoli.
HEX = re.compile(r"[0-9a-f]{64}\Z")
# Chiavi che non devono mai comparire in un artefatto (ground truth e punteggi): il registro
# e' GT-free.
FORBIDDEN = frozenset((
    "ground_truth", "ground_truth_reason", "scoring_points",
    "reference_fault_types", "true_fault_type", "true_label",
    "expected_fault_type", "fault_label", "ood_labels",
))
# Dimensione massima, in byte, di un file del registro.
MAX_RECORD_BYTES = 2_000_000


class UnifiedScientificLedgerBlocked(RuntimeError):
    """STOP: identita', dipendenze, release o integrita' non dimostrate."""


def _canonical(obj: object) -> bytes:
    """Forma canonica di `obj` in byte UTF-8 (JSON con chiavi ordinate, senza spazi, NaN vietato).

    Solleva `UnifiedScientificLedgerBlocked` se non e' serializzabile o supera
    `MAX_RECORD_BYTES`.
    """
    try:
        raw = json.dumps(
            obj, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise UnifiedScientificLedgerBlocked("Noncanonical JSON") from exc
    if len(raw) > MAX_RECORD_BYTES:
        raise UnifiedScientificLedgerBlocked("Oversize record")
    return raw


def _sha(obj: object) -> str:
    """SHA-256 (esadecimale) della forma canonica di `obj`."""
    return hashlib.sha256(_canonical(obj)).hexdigest()


def _no_gt(obj: object) -> None:
    """Controlla, ricorsivamente in dizionari e liste, che non compaia nessuna chiave di GT.

    Le chiavi devono essere stringhe e non essere in `FORBIDDEN` (senza distinguere maiuscole).
    Solleva `UnifiedScientificLedgerBlocked` al primo caso.
    """
    if type(obj) is dict:
        for key, val in obj.items():
            if type(key) is not str or key.lower() in FORBIDDEN:
                raise UnifiedScientificLedgerBlocked("Forbidden GT/scoring key")
            _no_gt(val)
    elif type(obj) is list:
        for item in obj:
            _no_gt(item)


def _read(path: Path) -> dict | None:
    """Legge un file JSON del registro; `None` se non esiste.

    Il file deve essere regolare (non un link), entro `MAX_RECORD_BYTES`, JSON valido e GIA' in
    forma canonica (rilegge e ricanonicalizza: se i byte differiscono, e' stato alterato).
    """
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_RECORD_BYTES:
        raise UnifiedScientificLedgerBlocked("Unsafe/oversized JSON path")
    try:
        raw = path.read_bytes()
        obj = json.loads(raw)
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        raise UnifiedScientificLedgerBlocked("Unreadable scientific record") from exc
    if type(obj) is not dict or _canonical(obj) != raw:
        raise UnifiedScientificLedgerBlocked("Noncanonical scientific record")
    return obj


def _write_once(path: Path, obj: dict) -> None:
    """Scrive `obj` in `path` in modo create-only: se il file esiste gia', si blocca.

    Passi: 1) la destinazione deve essere libera; 2) `os.open` con `O_EXCL` fallisce se il file
    compare nel frattempo (nessuna sovrascrittura, nemmeno in concorrenza); 3) scrive i byte
    canonici e li forza su disco con `fsync`.
    """
    if path.is_symlink() or path.exists():
        raise UnifiedScientificLedgerBlocked("Create-only destination occupied")
    raw = _canonical(obj)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except OSError as exc:
        raise UnifiedScientificLedgerBlocked("O_EXCL create failed") from exc
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _meter(m: object, *, allow_zero_requests: bool) -> None:
    """Valida la ricevuta del contatore di stage `m`; solleva `UnifiedScientificLedgerBlocked`.

    Deve avere esattamente i sette campi del contatore (schema, richieste e token osservati,
    completezza, costo stimato, nessun tetto di spesa garantito). `allow_zero_requests` e' True
    solo per gli errori del provider, dove puo' non esserci stata alcuna richiesta.
    """
    # Un HTTP fallito puo' avere token non misurati, MAI inventare 0
    # come totale fatturato certificato.
    if type(m) is not dict or set(m) != {
        "schema", "observed_model_requests", "input_tokens_observed",
        "output_tokens_observed", "usage_complete",
        "cost_estimate_usd_not_invoice", "usd_hard_cap_guaranteed",
    }:
        raise UnifiedScientificLedgerBlocked("Stage meter receipt required")
    if (
        m["schema"] != "rq2_v2_unified_stage_meter_v0"
        or type(m["observed_model_requests"]) is not int
        or m["observed_model_requests"] < (0 if allow_zero_requests else 1)
        or any(type(m[key]) is not int or m[key] < 0
               for key in ("input_tokens_observed", "output_tokens_observed"))
        or type(m["usage_complete"]) is not bool
        or m["usd_hard_cap_guaranteed"] is not False
        or type(m["cost_estimate_usd_not_invoice"]) is not str
        or not m["cost_estimate_usd_not_invoice"].strip()
        or len(m["cost_estimate_usd_not_invoice"]) > 50
    ):
        raise UnifiedScientificLedgerBlocked("Malformed/incomplete stage meter")
    cost = m["cost_estimate_usd_not_invoice"]
    # La completezza dei TOKEN non certifica il PREZZO applicato: il
    # costo puo' essere sconosciuto anche con usage_metadata completo.
    # Non registrare mai 0 USD per mascherare listini non verificati.
    # Il costo e' "UNKNOWN" oppure un numero finito non negativo.
    if cost == "UNKNOWN":
        pass
    else:
        try:
            parsed = Decimal(cost)
        except InvalidOperation as exc:
            raise UnifiedScientificLedgerBlocked("Non-numeric cost") from exc
        if not parsed.is_finite() or parsed < 0:
            raise UnifiedScientificLedgerBlocked("Negative/nonfinite cost")


def _validate_artifact(row: dict, status: str, artifact: dict,
                       d_record: dict | None) -> None:
    """Verifica che `artifact` sia coerente con lo `status` dichiarato per lo stage `row`.

    Argomenti: `row` (riga del piano), `status` (uno di `STATUSES`), `artifact` (output dello
    stage) e `d_record` (record D del genitore, serve per C e K). Solleva
    `UnifiedScientificLedgerBlocked` se qualcosa non torna.

    Regole per stato:
    - BLOCKED_DEPENDENCY: l'artefatto deve essere vuoto;
    - ogni altro stato: ricevuta del contatore valida;
    - PROVIDER_ERROR: solo contatore e codice d'errore;
    - D: esecuzione con provenienza verificata, JSON valido e contratto di output v2 valido;
    - C/K: risposta grezza che rispetta il contratto (causa o regola) sulle evidenze del D
      genitore, che deve essere completo.
    Alla fine "RECORDED_COMPLETE" e' ammesso se e solo se il payload e' valido.
    """
    if status == "BLOCKED_DEPENDENCY":
        if artifact:
            raise UnifiedScientificLedgerBlocked("Blocked stage has output")
        return
    if type(artifact) is not dict or "stage_meter" not in artifact:
        raise UnifiedScientificLedgerBlocked("Attempted stage missing meter")
    _meter(artifact["stage_meter"], allow_zero_requests=status=="PROVIDER_ERROR")
    stage = row["stage"]
    if status == "PROVIDER_ERROR":
        if set(artifact) != {"stage_meter", "provider_error"} or (
            type(artifact["provider_error"]) is not str
            or not artifact["provider_error"].strip()
        ):
            raise UnifiedScientificLedgerBlocked("Provider error receipt missing")
        return
    if stage == "D":
        if set(artifact) != {"stage_meter", "diagnostic_run"} or (
            type(artifact["diagnostic_run"]) is not dict
        ):
            raise UnifiedScientificLedgerBlocked("D runner receipt missing")
        run = artifact["diagnostic_run"]
        # Un errore del runner D va registrato come PROVIDER_ERROR, non come D.
        if run.get("error") is not None:
            raise UnifiedScientificLedgerBlocked(
                "D run error must be preserved as PROVIDER_ERROR"
            )
        # Provenienza: il run D deve risultare catturato davvero per quel caso, modello e harness.
        try:
            audit_captured_v2_d(
                run=run, case_id=row["case_id"],
                model=row["logical_model"], harness=row["harness"],
            )
        except (UnifiedRQ2ProvenanceError, KeyError, TypeError, ValueError):
            prov = False
        else:
            prov = True
        # Risposta del D: un JSON i cui elementi (chiavi numeriche) hanno data, componente e
        # motivo della causa radice, con contratto di output v2 valido.
        raw = run.get("raw_response")
        try:
            parsed = json.loads(raw) if type(raw) is str else None
        except (ValueError, TypeError, RecursionError):
            parsed = None
        valid_task = (
            type(parsed) is dict and bool(parsed)
            and all(
                type(k) is str and k.isdigit()
                and type(item) is dict
                and {
                    "root cause occurrence datetime",
                    "root cause component", "root cause reason",
                }.issubset(item)
                for k, item in parsed.items()
            )
            and type(run.get("output_contract_v2")) is dict
            and run["output_contract_v2"].get("valid") is True
        )
        valid = (
            prov and run.get("json_status") == "valid_json"
            and valid_task
        )
    else:
        # C/K: solo contatore e risposta grezza; serve un D genitore completo, da cui si
        # ricostruiscono le evidenze ammesse per il validatore del contratto.
        if set(artifact) != {"stage_meter", "raw_response"} or (
            type(artifact["raw_response"]) is not str
        ):
            raise UnifiedScientificLedgerBlocked("C/K raw response required")
        if d_record is None or d_record["status"] != "RECORDED_COMPLETE":
            raise UnifiedScientificLedgerBlocked("C/K requires valid D")
        try:
            bundle = build_evidence_bundle(
                d_record["artifact"]["diagnostic_run"]["tool_trajectory"],
                allowed_tool_names=ALLOWED_TOOLS,
            )
            validator = (
                validate_cause_probe if stage == "C"
                else validate_candidate_rule
            )
            validator(
                artifact["raw_response"],
                allowed_evidence_ids=evidence_ids(bundle),
            )
        except (EvidenceBundleError, ContractError, KeyError, TypeError, ValueError):
            valid = False
        else:
            valid = True
    if (status == "RECORDED_COMPLETE") != valid:
        raise UnifiedScientificLedgerBlocked(
            "Payload/status or evidence contract mismatch"
        )


@contextmanager
def _writer_lock(path: Path):
    """Lock OS sulla radice: fail-closed se il filesystem non lo supporta.

    In Colab Google Drive/FUSE NON considerarlo certificato senza
    test contemporanei sul filesystem di destinazione.

    Uso: `with _writer_lock(percorso): ...`. Il lock e' non bloccante: se un altro processo lo
    possiede si solleva `UnifiedScientificLedgerBlocked` invece di attendere.
    """
    # 1. Il percorso del lock deve essere un file regolare (o assente), mai un link.
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise UnifiedScientificLedgerBlocked("Unsafe writer lock path")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        # 2. Windows: si blocca il primo byte del file con `msvcrt` (il file deve avere almeno
        # un byte, quindi se e' vuoto vi si scrive "0").
        if sys.platform == "win32":
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            if os.fstat(fd).st_size == 0:
                os.write(fd, b"0")
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise UnifiedScientificLedgerBlocked("Writer lock unavailable") from exc
            try:
                yield
            finally:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        # 3. Linux/macOS: lock esclusivo non bloccante con `flock`.
        else:
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise UnifiedScientificLedgerBlocked("Writer lock unavailable") from exc
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


class UnifiedScientificLedger:
    """Registro scientifico D/C/K create-only; NON e' un dispatcher di LLM.

    Richiede un file di release gia' esistente: non si puo' costruire su una radice dati
    nuova priva di una release autorizzata dall'esterno.

    Per ogni stage del piano esistono al piu' un claim e un record, mai sovrascritti. Ogni
    lettura verifica gli hash (stage, release, piano, genitori): un file alterato o fuori
    posto blocca tutto.
    """

    def __init__(self, *, data_dir: Path, repo_dir: Path,
                 expected_commit: str, approved_release_sha256: str):
        """Apre il registro dopo aver verificato release, sorgenti e contenuto gia' scritto.

        Argomenti (per nome): `data_dir` (radice dei dati), `repo_dir` (radice del repository),
        `expected_commit` (hash git atteso) e `approved_release_sha256` (SHA-256 della release
        approvata dall'esterno). Passi: 1) cartelle sicure; 2) pin ben formati; 3) piano
        offline e indice dei suoi stage; 4) `_gate()` e `audit_restart()`.
        """
        self.data = _strict_absolute(data_dir, "data root")
        self.repo = _strict_absolute(repo_dir, "repo root")
        self.expected_commit = expected_commit
        self.release_sha = approved_release_sha256
        if (
            type(expected_commit) is not str
            or not re.fullmatch(r"[0-9a-f]{40}", expected_commit)
            or type(approved_release_sha256) is not str
            or not HEX.fullmatch(approved_release_sha256)
        ):
            raise UnifiedScientificLedgerBlocked("External commit/release pin required")
        self.plan = build_offline_discovery_plan()
        self.rows = {row["stage_id"]: row for row in self.plan["entries"]}
        self.root = self.data / NAMESPACE
        self._gate()
        self.audit_restart()

    def _dirs(self) -> None:
        """Verifica che i percorsi del registro siano cartelle sicure e il namespace esista.

        Nessun contenuto storico viene letto: si controlla solo che non siano link simbolici.
        """
        # Non accedere ai contenuti storici; evitare collisioni e symlink.
        for path in (
            self.data / "data", self.root,
            self.root / "claims", self.root / "records",
        ):
            if path.is_symlink() or (path.exists() and not path.is_dir()):
                raise UnifiedScientificLedgerBlocked("Unsafe scientific path")
        for old in (
            self.data / "data/rq2",
            self.data / "data/rq2_v2_provenance",
            self.data / "data/rq2_v2_unified_synthetic_v0",
            self.data / "data/results",
        ):
            if old.is_symlink():
                raise UnifiedScientificLedgerBlocked("Historical symlink")
        if not self.root.is_dir():
            raise UnifiedScientificLedgerBlocked("Scientific release namespace missing")

    def _gate(self) -> dict:
        """Ripete tutti i controlli d'ingresso e restituisce preview, blueprint e ricevuta.

        Passi: 1) checkout git pulito e uguale al commit atteso; 2) percorsi sicuri; 3) la
        release esiste ed ha l'hash approvato; 4) sorgenti, blueprint e contratto della release
        (`validate_future_release`); 5) la ricevuta non deve concedere nessuna autorita'.
        """
        head, status = _repository_commit(self.repo)
        if head != self.expected_commit or status:
            raise UnifiedScientificLedgerBlocked("Dirty/drifted Git checkout")
        self._dirs()
        release_path = self.data / RELEASE_FILE
        release = _read(release_path)
        if release is None or release_digest(release) != self.release_sha:
            raise UnifiedScientificLedgerBlocked("Missing/different scientific release")
        source = preview_unified_source_bound(
            data_dir=self.data, src_root=self.repo / "src",
        )
        blueprint = build_unified_release_blueprint(source_preview=source)
        receipt = validate_future_release(
            release=release, source_preview=source, blueprint=blueprint,
            externally_approved_sha256=self.release_sha,
            expected_source_commit=self.expected_commit,
        )
        if (
            receipt.get("can_execute_api") is not False
            or receipt.get("can_create_scientific_claim") is not False
            or receipt.get("can_run_ood_test") is not False
        ):
            raise UnifiedScientificLedgerBlocked("Release authority leak")
        return {"source": source, "blueprint": blueprint, "receipt": receipt}

    def _row(self, sid: str, model_id: str | None = None) -> dict:
        """Riga del piano per `sid`; se `model_id` e' dato deve coincidere con quello della riga.

        Un identificativo sconosciuto (ad esempio un caso OOD) blocca.
        """
        row = self.rows.get(sid) if type(sid) is str else None
        if row is None or (model_id is not None and (
            type(model_id) is not str or model_id != row["model_id"]
        )):
            raise UnifiedScientificLedgerBlocked("OOD/unknown stage or model")
        return row

    def _path(self, sid: str, *, claim: bool) -> Path:
        """Percorso del file di claim (`claim=True`) o di record dello stage `sid`.

        Il nome e' un prefisso fisso piu' lo SHA-256 dell'identificativo dello stage.
        """
        self._row(sid)
        folder = CLAIMS if claim else RECORDS
        prefix = "RQ2U_CLAIM_" if claim else "RQ2U_RECORD_"
        return self.data / folder / (
            prefix + hashlib.sha256(sid.encode("utf-8")).hexdigest() + ".json"
        )

    def load_claim(self, *, stage_id: str, _memo: dict | None = None) -> dict | None:
        """Legge e verifica il claim dello stage; `None` se non esiste.

        Controlla campi esatti, schema, protocollo, hash di release e piano, stage e modello,
        tentativo numero 1, dipendenze uguali a quelle del piano e hash del claim stesso.
        `_memo` e' una cache interna per non rileggere gli stessi file durante un audit.
        """
        row = self._row(stage_id)
        if _memo is not None and stage_id in _memo["claims"]:
            return _memo["claims"][stage_id]
        obj = _read(self._path(stage_id, claim=True))
        if obj is None:
            return None
        core = {k: v for k, v in obj.items() if k != "claim_sha256"}
        if (
            set(obj) != {
                "schema", "protocol", "release_sha256", "plan_sha256",
                "stage_id", "model_id", "attempt_number", "dependencies",
                "claim_sha256",
            }
            or obj["schema"] != VERSION + "_claim"
            or obj["protocol"] != PROTOCOL
            or obj["release_sha256"] != self.release_sha
            or obj["plan_sha256"] != self.plan["preview_sha256"]
            or obj["stage_id"] != stage_id
            or obj["model_id"] != row["model_id"]
            or type(obj["attempt_number"]) is not int
            or obj["attempt_number"] != 1
            or type(obj["dependencies"]) is not dict
            or set(obj["dependencies"]) != set(row["depends_on"])
            or any(type(v) is not str or not HEX.fullmatch(v)
                   for v in obj["dependencies"].values())
            or obj["claim_sha256"] != _sha(core)
        ):
            raise UnifiedScientificLedgerBlocked("Claim identity or SHA mismatch")
        if _memo is not None:
            _memo["claims"][stage_id] = obj
        return obj

    def load_record(self, *, stage_id: str, _memo: dict | None = None) -> dict | None:
        """Legge e verifica il record dello stage; `None` se non esiste.

        Passi: 1) campi, schema, protocollo, release, piano, stage, modello, stato, hash
        dell'artefatto e del record; 2) nessuna chiave di ground truth; 3) ogni record genitore
        esiste, ha l'hash dichiarato e lo stesso modello; 4) lo stato BLOCKED_DEPENDENCY compare
        se e solo se un genitore non e' completo; 5) il claim esiste (tranne per lo stato
        bloccato) con hash e dipendenze coerenti; 6) l'artefatto e' coerente con lo stato
        (`_validate_artifact`).
        """
        row = self._row(stage_id)
        if _memo is not None and stage_id in _memo["records"]:
            return _memo["records"][stage_id]
        obj = _read(self._path(stage_id, claim=False))
        if obj is None:
            return None
        core = {k: v for k, v in obj.items() if k != "record_sha256"}
        if (
            set(obj) != {
                "schema", "protocol", "release_sha256", "plan_sha256",
                "stage_id", "model_id", "status", "artifact",
                "artifact_sha256", "dependencies", "claim_sha256",
                "record_sha256",
            }
            or obj["schema"] != VERSION + "_record"
            or obj["protocol"] != PROTOCOL
            or obj["release_sha256"] != self.release_sha
            or obj["plan_sha256"] != self.plan["preview_sha256"]
            or obj["stage_id"] != stage_id
            or obj["model_id"] != row["model_id"]
            or obj["status"] not in STATUSES
            or type(obj["artifact"]) is not dict
            or obj["artifact_sha256"] != _sha(obj["artifact"])
            or type(obj["dependencies"]) is not dict
            or set(obj["dependencies"]) != set(row["depends_on"])
            or obj["record_sha256"] != _sha(core)
        ):
            raise UnifiedScientificLedgerBlocked("Record identity or SHA mismatch")
        # Nessuna ground truth nell'artefatto; poi i record genitori (ricorsione con cache).
        _no_gt(obj["artifact"])
        parents = {}
        for pid in row["depends_on"]:
            parent = self.load_record(stage_id=pid, _memo=_memo)
            if (
                parent is None
                or obj["dependencies"][pid] != parent["record_sha256"]
                or parent["model_id"] != row["model_id"]
            ):
                raise UnifiedScientificLedgerBlocked("Broken parent SHA")
            parents[pid] = parent
        bad_parents = bool(parents) and any(
            val["status"] != "RECORDED_COMPLETE" for val in parents.values()
        )
        if (obj["status"] == "BLOCKED_DEPENDENCY") != bad_parents:
            raise UnifiedScientificLedgerBlocked("Incorrect blocked dependency")
        # Un record "bloccato" non ha claim; ogni altro stato ne richiede uno con lo stesso hash.
        claim = self.load_claim(stage_id=stage_id, _memo=_memo)
        if obj["status"] == "BLOCKED_DEPENDENCY":
            if claim is not None or obj["claim_sha256"] is not None:
                raise UnifiedScientificLedgerBlocked("Blocked stage has claim")
        elif claim is None or obj["claim_sha256"] != claim["claim_sha256"]:
            raise UnifiedScientificLedgerBlocked("Missing claim for attempted stage")
        if claim is not None and claim["dependencies"] != obj["dependencies"]:
            raise UnifiedScientificLedgerBlocked("Claim parent binding drift")
        # Per C e K serve il record D dello stesso caso/harness/modello (stesso prefisso dell'id).
        stem = stage_id.rsplit(":", 1)[0]
        d = (obj if row["stage"] == "D" else
             self.load_record(stage_id=stem + ":D", _memo=_memo))
        _validate_artifact(row, obj["status"], obj["artifact"], d)
        if _memo is not None:
            _memo["records"][stage_id] = obj
        return obj

    def audit_restart(self) -> dict:
        """Rilegge e verifica TUTTO il registro; restituisce i conteggi (claim, record, orfani).

        Passi: 1) `_gate()`; 2) ogni file in `claims/` e `records/` deve avere nome, contenuto
        e posizione attesi; 3) ogni claim deve avere i genitori completi con l'hash dichiarato;
        4) un claim senza record e' "orfano": si conta e richiede revisione manuale, senza
        nessun ritento automatico.
        """
        self._gate()
        memo = {"claims": {}, "records": {}}
        counts = {"claims": 0, "records": 0, "orphan_claims": 0}
        for kind, folder, prefix in (
            ("claims", CLAIMS, "RQ2U_CLAIM_"),
            ("records", RECORDS, "RQ2U_RECORD_"),
        ):
            base = self.data / folder
            if not base.exists():
                continue
            for file in base.iterdir():
                if (
                    file.is_symlink() or not file.is_file()
                    or not file.name.endswith(".json")
                    or not file.name.startswith(prefix)
                    or not HEX.fullmatch(file.name[len(prefix):-5])
                ):
                    raise UnifiedScientificLedgerBlocked("Unexpected ledger file")
                raw = _read(file)
                sid = raw.get("stage_id")
                if type(sid) is not str or file != self._path(sid, claim=kind=="claims"):
                    raise UnifiedScientificLedgerBlocked("Stage filename mismatch")
                if kind == "claims":
                    self.load_claim(stage_id=sid, _memo=memo)
                else:
                    self.load_record(stage_id=sid, _memo=memo)
                counts[kind] += 1
        for sid, claim in memo["claims"].items():
            for parent_id, sha in claim["dependencies"].items():
                parent = self.load_record(stage_id=parent_id, _memo=memo)
                if (
                    parent is None or parent["record_sha256"] != sha
                    or parent["status"] != "RECORDED_COMPLETE"
                ):
                    raise UnifiedScientificLedgerBlocked("Claim parent drift")
            if self.load_record(stage_id=sid, _memo=memo) is None:
                counts["orphan_claims"] += 1
        return {
            "status": "SCIENTIFIC_LEDGER_READBACK_AUDITED",
            **counts,
            "release_sha256": self.release_sha,
            "plan_sha256": self.plan["preview_sha256"],
            "automatic_retry_allowed": False,
            "can_execute_api": False,
            "can_run_ood_test": False,
            "unresolved_claims_require_manual_review": (
                counts["orphan_claims"] > 0
            ),
        }

    def claim_stage(self, *, stage_id: str, model_id: str) -> dict:
        """Claim create-only: NO MODEL CALL. Blocca ogni altro orphan.

        Scrive il claim dello stage (la richiesta di esecuzione durabile). Passi, sotto lock di
        scrittura: 1) audit completo; 2) nessun claim orfano di altri stage; 3) lo stage non e'
        gia' stato richiesto ne' registrato (nessun ritento); 4) tutti i genitori sono completi
        e se ne registra l'hash; 5) scrittura create-only e rilettura di verifica.
        """
        row = self._row(stage_id, model_id)
        self._gate()
        with _writer_lock(self.data / LOCK_FILE):
            # 1-2. Audit completo e nessun claim orfano: un claim senza record blocca tutto.
            audit = self.audit_restart()
            if audit["orphan_claims"]:
                raise UnifiedScientificLedgerBlocked(
                    "Unresolved claim: manual review, no new stage"
                )
            # 3. Un solo tentativo per stage: niente ritenti.
            if self.load_claim(stage_id=stage_id) is not None or (
                self.load_record(stage_id=stage_id) is not None
            ):
                raise UnifiedScientificLedgerBlocked("Already claimed, no retry")
            # 4. Genitori completi; se ne registra l'hash nel claim.
            deps = {}
            for parent_id in row["depends_on"]:
                parent = self.load_record(stage_id=parent_id)
                if parent is None or parent["status"] != "RECORDED_COMPLETE":
                    raise UnifiedScientificLedgerBlocked("Parent not complete")
                deps[parent_id] = parent["record_sha256"]
            # 5. Contenuto del claim (senza il suo hash), poi hash, scrittura e rilettura.
            core = {
                "schema": VERSION + "_claim",
                "protocol": PROTOCOL,
                "release_sha256": self.release_sha,
                "plan_sha256": self.plan["preview_sha256"],
                "stage_id": stage_id,
                "model_id": model_id,
                "attempt_number": 1,
                "dependencies": deps,
            }
            obj = {**core, "claim_sha256": _sha(core)}
            path = self._path(stage_id, claim=True)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            _write_once(path, obj)
            # Rilettura di verifica: il file su disco deve avere lo stesso hash.
            reread = self.load_claim(stage_id=stage_id)
            if reread is None or reread["claim_sha256"] != obj["claim_sha256"]:
                raise UnifiedScientificLedgerBlocked("Claim readback failure")
            return {
                "stage_id": stage_id, "claim_sha256": obj["claim_sha256"],
                "status": "CLAIM_WITHOUT_RECORD", "can_execute_api": False,
            }

    def record_stage(self, *, stage_id: str, model_id: str,
                     status: str, artifact: dict) -> dict:
        """Fissa risultato/errore dopo claim. Nessun retry o overwrite.

        Argomenti (per nome): `stage_id`, `model_id`, `status` (uno di `STATUSES`) e `artifact`
        (output dello stage). Passi, sotto lock: 1) audit completo; 2) il record non esiste
        ancora; 3) i record genitori esistono e lo stato "bloccato" e' coerente con essi;
        4) il claim esiste (non per lo stato bloccato) e le sue dipendenze coincidono;
        5) nessuna ground truth e artefatto coerente con lo stato; 6) scrittura create-only
        e rilettura di verifica.
        """
        row = self._row(stage_id, model_id)
        # Argomenti ben formati prima di prendere il lock.
        if type(status) is not str or status not in STATUSES:
            raise UnifiedScientificLedgerBlocked("Unknown result status")
        if type(artifact) is not dict:
            raise UnifiedScientificLedgerBlocked("Artifact must be dict")
        self._gate()
        with _writer_lock(self.data / LOCK_FILE):
            # 1-2. Audit completo; il record non deve esistere gia'.
            self.audit_restart()
            if self.load_record(stage_id=stage_id) is not None:
                raise UnifiedScientificLedgerBlocked("Record already exists")
            # 3. Record dei genitori e coerenza dello stato "bloccato".
            parents = {}
            for pid in row["depends_on"]:
                rec = self.load_record(stage_id=pid)
                if rec is None:
                    raise UnifiedScientificLedgerBlocked("Parent record missing")
                parents[pid] = rec
            blocked = bool(parents) and any(
                parent["status"] != "RECORDED_COMPLETE"
                for parent in parents.values()
            )
            if (status == "BLOCKED_DEPENDENCY") != blocked:
                raise UnifiedScientificLedgerBlocked("Blocked state inconsistent")
            # 4. Claim: assente per lo stato bloccato, obbligatorio per gli altri.
            claim = self.load_claim(stage_id=stage_id)
            if status == "BLOCKED_DEPENDENCY":
                if claim is not None:
                    raise UnifiedScientificLedgerBlocked("Blocked stage has claim")
                claim_sha = None
            elif claim is None:
                raise UnifiedScientificLedgerBlocked("Attempted stage has no claim")
            else:
                claim_sha = claim["claim_sha256"]
            deps = {key: val["record_sha256"] for key, val in parents.items()}
            if claim is not None and claim["dependencies"] != deps:
                raise UnifiedScientificLedgerBlocked("Claim dependency drift")
            # 5. Nessuna ground truth; per C e K serve il D dello stesso caso/harness/modello.
            _no_gt(artifact)
            d_id = stage_id.rsplit(":", 1)[0] + ":D"
            d = (None if row["stage"] == "D" else
                 self.load_record(stage_id=d_id))
            _validate_artifact(row, status, artifact, d)
            # 6. Contenuto del record (senza il suo hash), poi hash, scrittura e rilettura.
            core = {
                "schema": VERSION + "_record",
                "protocol": PROTOCOL,
                "release_sha256": self.release_sha,
                "plan_sha256": self.plan["preview_sha256"],
                "stage_id": stage_id,
                "model_id": model_id,
                "status": status,
                "artifact": artifact,
                "artifact_sha256": _sha(artifact),
                "dependencies": deps,
                "claim_sha256": claim_sha,
            }
            obj = {**core, "record_sha256": _sha(core)}
            path = self._path(stage_id, claim=False)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            _write_once(path, obj)
            # Rilettura di verifica: il file su disco deve avere lo stesso hash.
            reread = self.load_record(stage_id=stage_id)
            if reread is None or reread["record_sha256"] != obj["record_sha256"]:
                raise UnifiedScientificLedgerBlocked("Record readback failure")
            return {
                "stage_id": stage_id, "status": status,
                "record_sha256": obj["record_sha256"],
                "can_execute_api": False,
            }


# G4L — predisposizione create-only con opt-in ESATTO di processo.
# Di default nessuna scrittura e' possibile. L'opt-in non equivale
# alla firma/approvazione esterna della release e non abilita API LLM.
# La gate rimane indipendente dal dispatcher pagato; non attivare
# in nessun processo di preflight o test su dati reali GT-free.
# Nome della variabile d'ambiente e valore ESATTO che la attiva (qualsiasi altro valore = no).
RELEASE_WRITE_OPT_IN_ENV = "OPENRCA_RQ2_V2_ENABLE_RELEASE_CREATE"
RELEASE_WRITE_OPT_IN_EXACT = "EXPLICIT_CREATE_ONLY_V1"


def runtime_release_write_optin() -> bool:
    """Valuta esattamente l'opt-in di processo, non il consenso umano."""
    return os.environ.get(RELEASE_WRITE_OPT_IN_ENV) == RELEASE_WRITE_OPT_IN_EXACT


# Valutato UNA volta, all'import del modulo: attivarlo dopo non ha effetto.
SCIENTIFIC_RELEASE_WRITE_ENABLED = runtime_release_write_optin()


def create_authorized_scientific_release_once(
    *, data_dir: Path, repo_dir: Path, expected_commit: str,
    approved_release_sha256: str, external_approval_reference: str,
    release: dict,
) -> dict:
    """Crea UNA futura release G4E solo dopo approvazioni esterne.

    La funzione e' inattiva per default. Non costruisce modelli, non
    esegue provider, non crea claim e non accede ai casi OOD. Senza
    opt-in esatto presente prima dell'import, blocca PRIMA di leggere
    o scrivere il filesystem. Non attivare nei preflight o nei notebook
    di verifica. I test usano esclusivamente fixture offline temporanee.

    L'opt-in non e' approvazione: sono comunque necessari commit clean,
    audit Colab 30 SOURCE_PATHS, digest esterno della release approvato,
    budget esplicito e reference non sintetica. Dopo errore di scrittura,
    fermarsi e auditare manualmente il namespace (nessun retry).

    Argomenti (per nome): `data_dir`, `repo_dir`, `expected_commit` (hash git atteso),
    `approved_release_sha256` (SHA-256 approvato dall'esterno), `external_approval_reference`
    (riferimento non sintetico all'approvazione) e `release` (dizionario della release).
    Restituisce un riepilogo "release creata, nessuna API, nessun claim".

    Passi: 1) opt-in di processo attivo; 2) riferimento d'approvazione reale e uguale a quello
    nella release; 3) preflight G4D (checkout pulito, namespace libero); 4) versioni di
    runtime degli SDK uguali a quelle fissate nella release; 5) sorgenti, blueprint e contratto
    della release; 6) creazione atomica del namespace e scrittura create-only della release,
    con rilettura e confronto dell'hash.
    """
    # 1. Senza l'opt-in esatto presente all'import non si legge ne' si scrive nulla.
    if SCIENTIFIC_RELEASE_WRITE_ENABLED is not True:
        raise UnifiedScientificLedgerBlocked(
            "Scientific release creation HARD-DISABLED"
        )
    # 2. Serve un riferimento d'approvazione esplicito, non "SYNTHETIC_", presente anche nella
    # release.
    if (
        type(release) is not dict
        or type(external_approval_reference) is not str
        or not external_approval_reference.strip()
        or external_approval_reference.startswith("SYNTHETIC_")
        or release.get("approval_reference") != external_approval_reference
    ):
        raise UnifiedScientificLedgerBlocked(
            "Explicit external non-synthetic release approval required"
        )

    # 3. G4D verifica HEAD clean e namespace assente; nessuna scrittura.
    data = _strict_absolute(data_dir, "data root")
    repo = _strict_absolute(repo_dir, "repository root")
    gate = preview_scientific_ledger_gate(
        data_dir=data, repo_dir=repo, expected_commit=expected_commit,
    )
    if (
        gate.get("status") != "LEDGER_NAMESPACE_PREFLIGHT_PASS_BUT_NO_RELEASE"
        or gate.get("source_commit") != expected_commit
        or gate.get("new_namespace_absent") is not True
        or gate.get("can_execute_api") is not False
        or gate.get("can_create_scientific_claim") is not False
        or gate.get("can_run_ood_test") is not False
    ):
        raise UnifiedScientificLedgerBlocked("Release preflight failed")

    # 4. Versioni degli SDK installate = versioni della release, verificate senza invocare modelli.
    import importlib.metadata as metadata
    from evaluation.rq2_provider_policy_source_audit import (
        EXPECTED_COLAB_VERSIONS,
    )
    from evaluation.rq2_model_factory import assert_exact_runtime_snapshot

    try:
        installed_versions = {
            name: metadata.version(name) for name in EXPECTED_COLAB_VERSIONS
        }
        if (
            installed_versions != EXPECTED_COLAB_VERSIONS
            or release.get("runtime_versions") != installed_versions
        ):
            raise UnifiedScientificLedgerBlocked(
                "Unpinned release SDK versions"
            )
        assert_exact_runtime_snapshot()
    except (metadata.PackageNotFoundError, ImportError, OSError) as exc:
        raise UnifiedScientificLedgerBlocked(
            "Cannot verify pinned SDK runtime"
        ) from exc

    # 5. Sorgenti, blueprint e contenuto della release; la ricevuta non deve concedere nulla.
    source = preview_unified_source_bound(
        data_dir=data, src_root=repo / "src",
    )
    blueprint = build_unified_release_blueprint(source_preview=source)
    receipt = validate_future_release(
        release=release,
        source_preview=source,
        blueprint=blueprint,
        externally_approved_sha256=approved_release_sha256,
        expected_source_commit=expected_commit,
    )
    if (
        receipt.get("status") != "RELEASE_CONTENT_VALIDATED_NO_EXECUTION_AUTHORITY"
        or receipt.get("release_sha256") != approved_release_sha256
        or receipt.get("can_execute_api") is not False
        or receipt.get("can_create_scientific_claim") is not False
        or receipt.get("can_run_ood_test") is not False
    ):
        raise UnifiedScientificLedgerBlocked("Release contract not verified")

    # 6. Create-only: il mkdir della root nuova e' il gate atomico contro
    # sessioni concorrenti. Non rimuovere eventuali file parziali a
    # seguito di errori: il successivo preflight deve fermarsi.
    root = data / NAMESPACE
    if root.is_symlink() or root.exists():
        raise UnifiedScientificLedgerBlocked("Scientific release already exists")
    try:
        root.mkdir(mode=0o700)
        with _writer_lock(data / LOCK_FILE):
            (root / "claims").mkdir(mode=0o700)
            (root / "records").mkdir(mode=0o700)
            release_path = data / RELEASE_FILE
            _write_once(release_path, release)
            written = _read(release_path)
            if written != release or release_digest(written) != approved_release_sha256:
                raise UnifiedScientificLedgerBlocked("Release readback SHA mismatch")
    except OSError as exc:
        raise UnifiedScientificLedgerBlocked(
            "Incomplete scientific release; MANUAL AUDIT ONLY"
        ) from exc

    return {
        "status": "SCIENTIFIC_RELEASE_CREATED_NO_API_NO_CLAIM",
        "release_sha256": approved_release_sha256,
        "source_commit": expected_commit,
        "release_relative_path": RELEASE_FILE.as_posix(),
        "provider_requests_sent": 0,
        "scientific_claims_written": 0,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "requires_separate_stage_authorization": True,
    }
