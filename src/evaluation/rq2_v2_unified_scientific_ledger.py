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
    _repository_commit,
)

VERSION = "rq2_v2_unified_scientific_ledger_v0"
LOCK_FILE = NAMESPACE / ".writer.lock"
STATUSES = frozenset((
    "RECORDED_COMPLETE", "INVALID_OUTPUT", "PROVIDER_ERROR",
    "BLOCKED_DEPENDENCY",
))
HEX = re.compile(r"[0-9a-f]{64}\Z")
FORBIDDEN = frozenset((
    "ground_truth", "ground_truth_reason", "scoring_points",
    "reference_fault_types", "true_fault_type", "true_label",
    "expected_fault_type", "fault_label", "ood_labels",
))
MAX_RECORD_BYTES = 2_000_000


class UnifiedScientificLedgerBlocked(RuntimeError):
    """STOP: identita', dipendenze, release o integrita' non dimostrate."""


def _canonical(obj: object) -> bytes:
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
    return hashlib.sha256(_canonical(obj)).hexdigest()


def _no_gt(obj: object) -> None:
    if type(obj) is dict:
        for key, val in obj.items():
            if type(key) is not str or key.lower() in FORBIDDEN:
                raise UnifiedScientificLedgerBlocked("Forbidden GT/scoring key")
            _no_gt(val)
    elif type(obj) is list:
        for item in obj:
            _no_gt(item)


def _read(path: Path) -> dict | None:
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
        if run.get("error") is not None:
            raise UnifiedScientificLedgerBlocked(
                "D run error must be preserved as PROVIDER_ERROR"
            )
        try:
            audit_captured_v2_d(
                run=run, case_id=row["case_id"],
                model=row["logical_model"], harness=row["harness"],
            )
        except (UnifiedRQ2ProvenanceError, KeyError, TypeError, ValueError):
            prov = False
        else:
            prov = True
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
    """
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise UnifiedScientificLedgerBlocked("Unsafe writer lock path")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
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
    """Create-only scientific D/C/K registry; NON dispatcher LLM.

    Requires pre-existing release file; cannot be constructed on a fresh
    benchmark root lacking an externally authorized release.
    """

    def __init__(self, *, data_dir: Path, repo_dir: Path,
                 expected_commit: str, approved_release_sha256: str):
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
        row = self.rows.get(sid) if type(sid) is str else None
        if row is None or (model_id is not None and (
            type(model_id) is not str or model_id != row["model_id"]
        )):
            raise UnifiedScientificLedgerBlocked("OOD/unknown stage or model")
        return row

    def _path(self, sid: str, *, claim: bool) -> Path:
        self._row(sid)
        folder = CLAIMS if claim else RECORDS
        prefix = "RQ2U_CLAIM_" if claim else "RQ2U_RECORD_"
        return self.data / folder / (
            prefix + hashlib.sha256(sid.encode("utf-8")).hexdigest() + ".json"
        )

    def load_claim(self, *, stage_id: str, _memo: dict | None = None) -> dict | None:
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
        claim = self.load_claim(stage_id=stage_id, _memo=_memo)
        if obj["status"] == "BLOCKED_DEPENDENCY":
            if claim is not None or obj["claim_sha256"] is not None:
                raise UnifiedScientificLedgerBlocked("Blocked stage has claim")
        elif claim is None or obj["claim_sha256"] != claim["claim_sha256"]:
            raise UnifiedScientificLedgerBlocked("Missing claim for attempted stage")
        if claim is not None and claim["dependencies"] != obj["dependencies"]:
            raise UnifiedScientificLedgerBlocked("Claim parent binding drift")
        stem = stage_id.rsplit(":", 1)[0]
        d = (obj if row["stage"] == "D" else
             self.load_record(stage_id=stem + ":D", _memo=_memo))
        _validate_artifact(row, obj["status"], obj["artifact"], d)
        if _memo is not None:
            _memo["records"][stage_id] = obj
        return obj

    def audit_restart(self) -> dict:
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
        """Claim create-only: NO MODEL CALL. Blocca ogni altro orphan."""
        row = self._row(stage_id, model_id)
        self._gate()
        with _writer_lock(self.data / LOCK_FILE):
            audit = self.audit_restart()
            if audit["orphan_claims"]:
                raise UnifiedScientificLedgerBlocked(
                    "Unresolved claim: manual review, no new stage"
                )
            if self.load_claim(stage_id=stage_id) is not None or (
                self.load_record(stage_id=stage_id) is not None
            ):
                raise UnifiedScientificLedgerBlocked("Already claimed, no retry")
            deps = {}
            for parent_id in row["depends_on"]:
                parent = self.load_record(stage_id=parent_id)
                if parent is None or parent["status"] != "RECORDED_COMPLETE":
                    raise UnifiedScientificLedgerBlocked("Parent not complete")
                deps[parent_id] = parent["record_sha256"]
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
            reread = self.load_claim(stage_id=stage_id)
            if reread is None or reread["claim_sha256"] != obj["claim_sha256"]:
                raise UnifiedScientificLedgerBlocked("Claim readback failure")
            return {
                "stage_id": stage_id, "claim_sha256": obj["claim_sha256"],
                "status": "CLAIM_WITHOUT_RECORD", "can_execute_api": False,
            }

    def record_stage(self, *, stage_id: str, model_id: str,
                     status: str, artifact: dict) -> dict:
        """Fissa risultato/errore dopo claim. Nessun retry o overwrite."""
        row = self._row(stage_id, model_id)
        if type(status) is not str or status not in STATUSES:
            raise UnifiedScientificLedgerBlocked("Unknown result status")
        if type(artifact) is not dict:
            raise UnifiedScientificLedgerBlocked("Artifact must be dict")
        self._gate()
        with _writer_lock(self.data / LOCK_FILE):
            self.audit_restart()
            if self.load_record(stage_id=stage_id) is not None:
                raise UnifiedScientificLedgerBlocked("Record already exists")
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
            _no_gt(artifact)
            d_id = stage_id.rsplit(":", 1)[0] + ":D"
            d = (None if row["stage"] == "D" else
                 self.load_record(stage_id=d_id))
            _validate_artifact(row, status, artifact, d)
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
            reread = self.load_record(stage_id=stage_id)
            if reread is None or reread["record_sha256"] != obj["record_sha256"]:
                raise UnifiedScientificLedgerBlocked("Record readback failure")
            return {
                "stage_id": stage_id, "status": status,
                "record_sha256": obj["record_sha256"],
                "can_execute_api": False,
            }
