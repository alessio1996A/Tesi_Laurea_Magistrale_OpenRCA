"""RQ2: archivio di ARTEFATTI DI STADIO legato al sorgente, a sola creazione (nessuna esecuzione).

Questo modulo salva su disco il contenuto di uno stadio fornito dal chiamante, errori inclusi,
in una cartella RQ2 separata. NON invoca agenti, provider, strumenti, scorer ne' pseudocodice
prodotto da un modello. L'input e' un piano BOZZA_NON_ESEGUIBILE (`DRAFT_NOT_EXECUTABLE`):
NESSUNA scrittura o audit qui autorizza una chiamata a un modello o un congelamento scientifico.

Sotto questo contratto V0 si possono salvare solo gli stadi di discovery D/C/K. Gli stadi di test
sono bloccati del tutto finche' non sara' implementato un protocollo di congelamento SCIENTIFICO
separato e preregistrato; il congelamento del giornale sintetico di prova NON viene MAI accettato.

Il piano viene ricostruito dai CSV congelati senza ground truth (`preview_market`) e gli hash
vengono ricontrollati a ogni operazione di salvataggio. L'integrita' del risultato e' verificata
con JSON canonico e SHA-256: rileva corruzioni accidentali, NON modifiche malevole di chi puo'
riscrivere i byte e ricalcolare gli hash.

Contenuto:
- costanti: versione dell'archivio, sottocartella fissa, dimensione massima, stati ammessi e
  nomi di chiave vietati (schemi propri della valutazione);
- `RQ2ArtifactStoreError`: errore per violazione di integrita' o di fase;
- funzioni di supporto: `_encoded` (JSON canonico), `_sha`, `_source_sha`, `_filename`,
  `_check_no_gt_schema`, `_read_canonical`, `_create_exclusive`;
- `RQ2StageArtifactStore`: verifica i sorgenti, controlla i record esistenti, rifa' l'audit al
  riavvio, carica e salva gli artefatti di discovery.

Non usare questo archivio al posto di un sistema di claim/lease per esecuzioni asincrone.
Non e' ammesso alcun nuovo tentativo ne' sovrascrittura automatica. Una scrittura parziale o
interrotta resta su disco per l'analisi e blocca quello stadio.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from evaluation.rq2_dryrun_plan import (
    EXPECTED_MANIFEST_SHA256, EXPECTED_SPLIT_SHA256, PLAN_STATUS,
    preview_market,
)
from evaluation.rq2_stage_binding import StageBindingError, _validate_plan

STORE_VERSION = "rq2_stage_artifact_store_v0"
# Sottocartella FISSA di destinazione: il chiamante non puo' reindirizzare le scritture.
STORE_SUBDIRECTORY = Path("data/rq2/stage_artifacts_v0")
# Dimensione massima (in byte) di un artefatto serializzato.
MAX_ARTIFACT_BYTES = 32_000_000
# Stati ammessi per uno stadio registrato.
_STATUSES = frozenset((
    "RECORDED_COMPLETE", "INVALID_OUTPUT", "PROVIDER_ERROR",
    "BLOCKED_DEPENDENCY",
))
# Nomi di chiave dello schema riservato alla valutazione: non si possono salvare di nascosto
# dentro artefatti RQ2 destinati al modello. NON e' un filtro semantico del ground truth.
_FORBIDDEN_KEYS = frozenset((
    "ground_truth", "ground_truth_reason", "scoring_points",
    "reference_fault_types", "reference_complete", "true_fault_type",
    "true_label", "expected_fault_type", "fault_label", "ood_labels",
    "target_reasons",
))


class RQ2ArtifactStoreError(ValueError):
    """Rifiuta una violazione di integrita' del sorgente, di integrita' dell'artefatto o del gate di fase."""


def _encoded(value: object) -> bytes:
    """Serializza `value` in JSON canonico (chiavi ordinate, senza spazi, UTF-8) e ne controlla la taglia.

    Solleva `RQ2ArtifactStoreError` se il valore non e' serializzabile in modo canonico (anche per
    valori non finiti) o supera `MAX_ARTIFACT_BYTES`.
    """
    try:
        data = json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError, OverflowError) as exc:
        raise RQ2ArtifactStoreError("Noncanonical or nonfinite artifact") from exc
    if len(data) > MAX_ARTIFACT_BYTES:
        raise RQ2ArtifactStoreError("Artifact exceeds bounded storage size")
    return data


def _sha(data: bytes) -> str:
    """SHA-256 (esadecimale) dei byte `data`."""
    return hashlib.sha256(data).hexdigest()


def _source_sha(path: Path) -> str:
    """SHA-256 del file sorgente `path` (CSV congelato senza ground truth); errore se illeggibile."""
    try:
        return _sha(path.read_bytes())
    except OSError as exc:
        raise RQ2ArtifactStoreError("GT-free source unreadable") from exc


def _filename(stage_id: str) -> str:
    """Nome del file di uno stadio: `RQ2_STAGE_<sha256 dell'id>.json` (nome deterministico)."""
    return "RQ2_STAGE_" + _sha(stage_id.encode("utf-8")) + ".json"


def _check_no_gt_schema(value: object) -> None:
    """Rifiuta i nomi di CHIAVE riservati alla valutazione (a ogni livello), non il testo prodotto dal modello.

    Controlla ricorsivamente dizionari e liste; le chiavi devono essere stringhe e non comparire
    (in minuscolo) in `_FORBIDDEN_KEYS`.
    """
    if type(value) is dict:
        for name, item in value.items():
            if type(name) is not str or name.lower() in _FORBIDDEN_KEYS:
                raise RQ2ArtifactStoreError("Forbidden/non-string artifact key")
            _check_no_gt_schema(item)
    elif type(value) is list:
        for item in value:
            _check_no_gt_schema(item)


def _read_canonical(path: Path) -> dict:
    """Legge un artefatto da `path` e verifica che sia un dizionario in JSON canonico.

    Passi: 1) rifiuta link simbolici e percorsi che non sono file; 2) legge al massimo
    `MAX_ARTIFACT_BYTES + 1` byte; 3) interpreta il JSON; 4) controlla che, ricodificato in forma
    canonica, dia esattamente gli stessi byte letti.
    """
    if path.is_symlink() or not path.is_file():
        raise RQ2ArtifactStoreError("Invalid/symlink artifact path")
    try:
        with path.open("rb") as inp:
            data = inp.read(MAX_ARTIFACT_BYTES + 1)
    except OSError as exc:
        raise RQ2ArtifactStoreError("Cannot read artifact") from exc
    if len(data) > MAX_ARTIFACT_BYTES:
        raise RQ2ArtifactStoreError("Artifact too large")
    try:
        value = json.loads(data)
    except (ValueError, UnicodeDecodeError, RecursionError) as exc:
        raise RQ2ArtifactStoreError("Corrupt artifact JSON") from exc
    if type(value) is not dict or _encoded(value) != data:
        raise RQ2ArtifactStoreError("Artifact not canonical JSON")
    return value


def _create_exclusive(path: Path, content: bytes) -> None:
    """Crea `path` in modo ESCLUSIVO (a sola creazione, permessi 0600) e vi scrive `content` con fsync.

    Se il file esiste gia' (anche come link simbolico) solleva un errore: nessuna sovrascrittura.
    """
    if path.is_symlink() or path.exists():
        raise RQ2ArtifactStoreError("Create-only: stage already exists")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise RQ2ArtifactStoreError("Create-only: stage already exists") from exc
    except OSError as exc:
        raise RQ2ArtifactStoreError("Cannot create isolated stage artifact") from exc
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


class RQ2StageArtifactStore:
    """Validazione dei sorgenti in sola lettura + salvataggio di artefatti di discovery immutabili.

    La destinazione e' fissa sotto `data_dir/data/rq2/stage_artifacts_v0`: il chiamante non puo'
    reindirizzarla nella cartella `data/results` di RQ1.
    """

    def __init__(self, *, data_dir: Path):
        """Prepara l'archivio senza scrivere nulla.

        Argomento (per nome): `data_dir`, radice dei dati. Passi: 1) ricostruisce il piano dai CSV
        congelati e ne valida le voci; 2) controlla che sia la bozza bloccata originale (sorgenti
        verificati, nessuna API eseguibile o a budget, nessuna chiamata, hash di split e manifest
        attesi); 3) memorizza hash del piano, voci e cartella radice; 4) ricontrolla i sorgenti e
        la cartella di destinazione.
        """
        self.data_dir = Path(data_dir)
        try:
            plan = preview_market(self.data_dir)
            entries = _validate_plan(plan)
        except (ValueError, OSError, StageBindingError) as exc:
            raise RQ2ArtifactStoreError("Source-verified RQ2 plan required") from exc
        if (
            plan.get("source_verified") is not True
            or plan.get("status") != PLAN_STATUS
            or plan.get("can_execute_api") is not False
            or plan.get("api_budget_approved") is not False
            or plan.get("model_api_calls") != 0
            or plan.get("split_sha256") != EXPECTED_SPLIT_SHA256
            or plan.get("manifest_sha256") != EXPECTED_MANIFEST_SHA256
        ):
            raise RQ2ArtifactStoreError("Only the original blocked draft is valid")
        self.plan_sha = plan["preview_sha256"]
        self.entries = entries
        self.root = self.data_dir / STORE_SUBDIRECTORY
        self._verify_sources()
        self._guard_directory()
        # Nessuna scrittura nel costruttore: un controllo preliminare non puo' creare file di output.

    def _verify_sources(self) -> None:
        """Ricalcola l'SHA-256 dei due CSV congelati (split e manifest) e li confronta con quelli attesi."""
        split = self.data_dir / "data/processed/split_market_v1.csv"
        manifest = self.data_dir / "data/processed/benchmark_inputs_market.csv"
        if (
            _source_sha(split) != EXPECTED_SPLIT_SHA256
            or _source_sha(manifest) != EXPECTED_MANIFEST_SHA256
        ):
            raise RQ2ArtifactStoreError("Original GT-free sources changed")

    def _guard_directory(self) -> None:
        """Controlla la cartella di destinazione: niente link simbolici e radice (se esiste) deve essere una cartella."""
        # Si puo' scrivere solo nella nuova sottocartella RQ2.
        if any(p.is_symlink() for p in (
            self.data_dir / "data/rq2", self.root,
        )):
            raise RQ2ArtifactStoreError("Symlink in RQ2 artifact path")
        if self.root.exists() and not self.root.is_dir():
            raise RQ2ArtifactStoreError("Artifact root is not a directory")

    def _path(self, stage_id: str) -> Path:
        """Percorso del file di `stage_id`; errore se lo stadio non e' nel piano verificato."""
        if stage_id not in self.entries:
            raise RQ2ArtifactStoreError("Stage not in verified plan")
        return self.root / _filename(stage_id)

    def _check_record(self, stage_id: str) -> dict | None:
        """Legge e verifica a fondo il record di `stage_id`; restituisce `None` se non esiste ancora.

        Passi: 1) legge il JSON canonico; 2) controlla l'insieme esatto delle chiavi; 3) ricalcola
        l'hash del record; 4) confronta identita' (stadio, caso, fase, modello, harness), hash di
        piano/split/manifest, autorizzazione "nessuna API", stato ammesso, fase di discovery,
        modello proposto, hash dell'artefatto e dipendenze; 5) coerenza di stato bloccato e
        artefatto vuoto; 6) nessuna chiave riservata alla valutazione nell'artefatto.
        """
        path = self._path(stage_id)
        if not path.exists() and not path.is_symlink():
            return None
        record = _read_canonical(path)
        keys = {
            "store_version", "stage_id", "case_id", "stage", "phase",
            "logical_model", "harness", "model_id_proposed",
            "plan_preview_sha256", "split_sha256", "manifest_sha256",
            "status", "dependency_record_hashes", "artifact",
            "artifact_sha256", "record_sha256", "authorization",
        }
        if set(record) != keys:
            raise RQ2ArtifactStoreError("Invalid artifact record schema")
        core = {k: v for k, v in record.items() if k != "record_sha256"}
        if record["record_sha256"] != _sha(_encoded(core)):
            raise RQ2ArtifactStoreError("Artifact digest mismatch")
        e = self.entries[stage_id]
        if (
            record["store_version"] != STORE_VERSION
            or record["stage_id"] != stage_id
            or record["case_id"] != e["case_id"]
            or record["stage"] != e["stage"]
            or record["phase"] != e["phase"]
            or record["logical_model"] != e["logical_model"]
            or record["harness"] != e["harness"]
            or record["plan_preview_sha256"] != self.plan_sha
            or record["split_sha256"] != EXPECTED_SPLIT_SHA256
            or record["manifest_sha256"] != EXPECTED_MANIFEST_SHA256
            or record["authorization"] != "NO_API_AUTHORITY"
            or type(record["status"]) is not str
            or record["status"] not in _STATUSES
            or e["phase"] != "discovery"
            or type(record["model_id_proposed"]) is not str
            or e["logical_model"] not in record["model_id_proposed"].lower()
            or type(record["artifact"]) is not dict
            or _sha(_encoded(record["artifact"])) != record["artifact_sha256"]
            or type(record["dependency_record_hashes"]) is not dict
            or set(record["dependency_record_hashes"]) != set(e["dependencies"])
        ):
            raise RQ2ArtifactStoreError("Artifact identity or source mismatch")
        if record["status"] == "BLOCKED_DEPENDENCY":
            if not e["dependencies"] or record["artifact"]:
                raise RQ2ArtifactStoreError("Malformed blocked dependency receipt")
        elif not record["artifact"]:
            raise RQ2ArtifactStoreError("Empty non-blocked stage artifact")
        _check_no_gt_schema(record["artifact"])
        return record

    def audit_restart(self) -> dict:
        """Verifica tutte le ricevute esistenti e le dipendenze ordinate alla ripresa.

        Restituisce il rapporto di audit: versione, stato (nessun artefatto oppure audit dei soli
        artefatti di discovery), hash del piano, numero di stadi salvati, conteggio per stato e i
        flag "nessuna lettura di ground truth, zero chiamate, API e fase di test bloccate".

        Passi: 1) ricontrolla sorgenti e cartella; 2) se la radice non esiste, rapporto vuoto;
        3) rifiuta file sconosciuti o non di discovery; 4) per ogni stadio salvato verifica il
        record, le dipendenze (devono esistere e avere gli hash attesi), che il modello coincida
        con quello dei genitori e che lo stato "bloccato" coincida con il fallimento di un genitore.
        """
        self._verify_sources()
        self._guard_directory()
        if not self.root.exists():
            return {
                "store_version": STORE_VERSION,
                "status": "SOURCE_VERIFIED_NO_ARTIFACTS",
                "plan_preview_sha256": self.plan_sha,
                "stored_discovery_stages": 0,
                "by_status": {},
                "read_ground_truth": False,
                "model_api_calls": 0,
                "can_execute_api": False,
                "test_phase_unlocked": False,
            }
        seen = set()
        counts: Counter[str] = Counter()
        actual = {p.name for p in self.root.iterdir()}
        permitted = {
            _filename(sid) for sid, e in self.entries.items()
            if e["phase"] == "discovery"
        }
        if actual - permitted:
            raise RQ2ArtifactStoreError("Unknown/non-discovery file in artifact root")
        for stage_id, entry in self.entries.items():
            if entry["phase"] != "discovery":
                continue
            item = self._check_record(stage_id)
            if item is None:
                continue
            previous = [self._check_record(dep) for dep in entry["dependencies"]]
            if any(v is None for v in previous):
                raise RQ2ArtifactStoreError("Artifact without prior dependency")
            expected_hashes = {
                dep: prior["record_sha256"]
                for dep, prior in zip(entry["dependencies"], previous)
            }
            if item["dependency_record_hashes"] != expected_hashes:
                raise RQ2ArtifactStoreError("Dependency artifact digest mismatch")
            if previous:
                if any(
                    parent["model_id_proposed"] != item["model_id_proposed"]
                    for parent in previous
                ):
                    raise RQ2ArtifactStoreError("Stage model differs from dependency")
                failed = any(
                    parent["status"] != "RECORDED_COMPLETE" for parent in previous
                )
                if (item["status"] == "BLOCKED_DEPENDENCY") != failed:
                    raise RQ2ArtifactStoreError("Dependency outcome does not match block")
            seen.add(stage_id)
            counts[item["status"]] += 1
        return {
            "store_version": STORE_VERSION,
            "status": "DISCOVERY_ARTIFACT_AUDIT_ONLY",
            "plan_preview_sha256": self.plan_sha,
            "stored_discovery_stages": len(seen),
            "by_status": dict(sorted(counts.items())),
            "read_ground_truth": False,
            "model_api_calls": 0,
            "can_execute_api": False,
            "test_phase_unlocked": False,
        }

    def load_discovery_stage(self, *, stage_id: str) -> dict | None:
        """Carica un artefatto di discovery verificato, senza mai sbloccare test o chiamate ai modelli.

        Argomento (per nome): `stage_id`. Rifa' prima l'audit dell'intero giornale, poi restituisce
        il record canonico (o `None` se non c'e'). E' pensato per un registratore D/C/K offline
        separato, NON per un esecutore di provider. Rifiuta stadi sconosciuti e stadi di test.
        """
        if type(stage_id) is not str or stage_id not in self.entries:
            raise RQ2ArtifactStoreError("Unknown discovery stage")
        if self.entries[stage_id]["phase"] != "discovery":
            raise RQ2ArtifactStoreError("Test artifacts remain locked")
        self.audit_restart()
        return self._check_record(stage_id)

    def save_discovery_stage(
        self, *, stage_id: str, model_id_proposed: str,
        status: str, artifact: dict,
    ) -> dict:
        """Salva UN risultato fornito dal chiamante; NON avvia MAI un agente o un provider.

        Argomenti (per nome): `stage_id`, `model_id_proposed`, `status`, `artifact`. Restituisce
        un riepilogo (hash di record e di artefatto, zero chiamate, API e test bloccati).

        Passi: 1) stadio pianificato e di discovery (i risultati di TEST sono bloccati); 2) metadati
        validi (stato ammesso, artefatto dizionario, modello coerente e non vuoto); 3) coerenza
        tra stato "bloccato" e artefatto vuoto; 4) niente chiavi riservate alla valutazione;
        5) nuovo audit del giornale e controllo che lo stadio non sia gia' salvato; 6) le
        dipendenze devono esistere, con lo stesso modello, e lo stato deve rispettarne l'esito;
        7) costruzione del record con hash e scrittura esclusiva.
        """
        if type(stage_id) is not str or stage_id not in self.entries:
            raise RQ2ArtifactStoreError("Unplanned stage")
        e = self.entries[stage_id]
        if e["phase"] != "discovery":
            raise RQ2ArtifactStoreError("TEST results blocked before scientific freeze")
        if (
            type(status) is not str
            or status not in _STATUSES
            or type(artifact) is not dict
            or type(model_id_proposed) is not str
            or e["logical_model"] not in model_id_proposed.lower()
            or len(model_id_proposed) > 160
            or not model_id_proposed.strip()
        ):
            raise RQ2ArtifactStoreError("Invalid stage result metadata")
        if status == "BLOCKED_DEPENDENCY":
            if e["stage"] == "D" or artifact:
                raise RQ2ArtifactStoreError("Only dependent stages may be blocked")
        elif not artifact:
            raise RQ2ArtifactStoreError("Non-blocked artifact cannot be empty")
        _check_no_gt_schema(artifact)
        _encoded(artifact)
        # Tutti i file gia' salvati, fallimenti inclusi, devono superare il nuovo audit.
        self.audit_restart()
        if self._check_record(stage_id) is not None:
            raise RQ2ArtifactStoreError("Create-only: stage already stored")
        dependencies = {}
        failed = False
        for dep in e["dependencies"]:
            parent = self._check_record(dep)
            if parent is None:
                raise RQ2ArtifactStoreError("Missing prior D/C artifact")
            if parent["model_id_proposed"] != model_id_proposed:
                raise RQ2ArtifactStoreError("Prior stage model identity changed")
            dependencies[dep] = parent["record_sha256"]
            failed |= parent["status"] != "RECORDED_COMPLETE"
        if (status == "BLOCKED_DEPENDENCY") != failed:
            raise RQ2ArtifactStoreError("Stage must preserve dependency outcome")
        core = {
            "store_version": STORE_VERSION,
            "stage_id": stage_id,
            "case_id": e["case_id"],
            "stage": e["stage"],
            "phase": e["phase"],
            "logical_model": e["logical_model"],
            "harness": e["harness"],
            "model_id_proposed": model_id_proposed,
            "plan_preview_sha256": self.plan_sha,
            "split_sha256": EXPECTED_SPLIT_SHA256,
            "manifest_sha256": EXPECTED_MANIFEST_SHA256,
            "status": status,
            "dependency_record_hashes": dependencies,
            "artifact": artifact,
            "artifact_sha256": _sha(_encoded(artifact)),
            "authorization": "NO_API_AUTHORITY",
        }
        record = {**core, "record_sha256": _sha(_encoded(core))}
        payload = _encoded(record)
        self._guard_directory()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        _create_exclusive(self._path(stage_id), payload)
        return {
            "store_version": STORE_VERSION,
            "stage_id": stage_id,
            "status": status,
            "record_sha256": record["record_sha256"],
            "artifact_sha256": record["artifact_sha256"],
            "model_api_calls": 0,
            "can_execute_api": False,
            "test_phase_unlocked": False,
            "files_written": True,
        }
