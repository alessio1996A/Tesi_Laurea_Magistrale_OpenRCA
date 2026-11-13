"""Archivio RQ2-V2 separato, create-only, SOLO per prove sintetiche offline.

Non usa i moduli di persistenza V1, non accede a Market/GT, non invoca
provider e NON autorizza una campagna scientifica. Richiede un marker
sintetico esplicito e rifiuta directory di dati del benchmark.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from evaluation.rq2_evidence_bundle import build_evidence_bundle, evidence_ids
from evaluation.rq2_output_contracts import (
    validate_candidate_rule, validate_cause_probe,
)
from evaluation.rq2_stage_binding import ALLOWED_TOOLS
from evaluation.rq2_v2_isolation_policy import (
    ARTIFACTS_RELATIVE, CLAIMS_RELATIVE, DRAFT_PROTOCOL,
    ROOT_RELATIVE, RQ2V2IsolationError, preview_v2_destination,
)

VERSION = "rq2_v2_synthetic_artifact_store_v0"
MARKER = ".rq2_v2_synthetic_only"
MARKER_BYTES = b"RQ2_V2_SYNTHETIC_ONLY_NO_API_V0\n"
STATUSES = frozenset((
    "RECORDED_COMPLETE", "INVALID_OUTPUT", "PROVIDER_ERROR",
    "BLOCKED_DEPENDENCY",
))
FORBIDDEN_KEYS = frozenset((
    "ground_truth", "ground_truth_reason", "scoring_points",
    "reference_fault_types", "true_fault_type", "true_label",
    "expected_fault_type", "fault_label", "ood_labels",
))


class RQ2V2StoreError(ValueError):
    """Rifiuta path, schema, provenance o artefatti sintetici incoerenti."""


def canonical(value) -> bytes:
    try:
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError, OverflowError) as exc:
        raise RQ2V2StoreError("Noncanonical JSON") from exc
    if len(encoded) > 2_000_000:
        raise RQ2V2StoreError("Synthetic record exceeds safety budget")
    return encoded


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def reject_gt_keys(value) -> None:
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str or key.lower() in FORBIDDEN_KEYS:
                raise RQ2V2StoreError("Forbidden scoring/GT key")
            reject_gt_keys(item)
    elif type(value) is list:
        for item in value:
            reject_gt_keys(item)


def synthetic_guard(data_dir: Path) -> None:
    """Rifiuta esplicitamente root reali e fonti OpenRCA; nessuna scrittura."""
    if type(data_dir) is not Path or not data_dir.is_absolute():
        raise RQ2V2StoreError("Absolute pathlib.Path root required")
    if ".." in data_dir.parts or not data_dir.is_dir() or data_dir.is_symlink():
        raise RQ2V2StoreError("Unsafe/nonexistent data root")
    marker = data_dir / MARKER
    if marker.is_symlink() or not marker.is_file() or (
        marker.read_bytes() != MARKER_BYTES
    ):
        raise RQ2V2StoreError("Synthetic-only marker required")
    for forbidden in (
        data_dir / "Market.zip",
        data_dir / "data/processed",
        data_dir / "data/rq2",
        data_dir / "data/results",
    ):
        if forbidden.exists() or forbidden.is_symlink():
            raise RQ2V2StoreError("Real benchmark or frozen V1 path forbidden")
    for location in (
        data_dir / "data", data_dir / ROOT_RELATIVE,
        data_dir / CLAIMS_RELATIVE, data_dir / ARTIFACTS_RELATIVE,
    ):
        if location.is_symlink():
            raise RQ2V2StoreError("Symlink in V2 namespace")
        if location.exists() and not location.is_dir():
            raise RQ2V2StoreError("Non-directory in V2 namespace")


def write_exclusive(path: Path, value: dict) -> None:
    """Scrittura create-only O_EXCL, mai replace, rename o retry."""
    payload = canonical(value)
    if path.is_symlink() or path.exists():
        raise RQ2V2StoreError("Create-only: existing path")
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except OSError as exc:
        raise RQ2V2StoreError("Exclusive create failed") from exc
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
    except OSError:
        # Conserva ogni file parziale: non cancellarlo, non fare retry.
        raise


def read_canonical(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise RQ2V2StoreError("Invalid/missing stored file")
    if path.stat().st_size > 2_000_000:
        raise RQ2V2StoreError("Oversized stored file")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, ValueError, UnicodeError, RecursionError) as exc:
        raise RQ2V2StoreError("Unreadable JSON") from exc
    if type(value) is not dict or canonical(value) != raw:
        raise RQ2V2StoreError("Noncanonical stored JSON")
    return value


def _parent_ids(stage_id: str) -> list[str]:
    stem, stage = stage_id.rsplit(":", 1)
    if stage == "D":
        return []
    if stage == "C":
        return [stem + ":D"]
    if stage == "K":
        return [stem + ":C"]
    raise RQ2V2StoreError("Unplanned stage")


class RQ2V2SyntheticArtifactStore:
    """Nuova radice V2, ma solo fixture e nessuna autorizzazione API."""

    def __init__(self, *, data_dir: Path):
        self.data_dir = data_dir
        synthetic_guard(data_dir)
        self.root = data_dir / ARTIFACTS_RELATIVE
        # Costruttore read-only: non creare directory.
        self.audit_restart()

    def _preview(self, stage_id: str) -> dict:
        synthetic_guard(self.data_dir)
        try:
            return preview_v2_destination(
                data_dir=self.data_dir, stage_id=stage_id
            )
        except RQ2V2IsolationError as exc:
            raise RQ2V2StoreError("Unplanned/locked stage ID") from exc

    def _path(self, stage_id: str) -> Path:
        return Path(self._preview(stage_id)["artifact_path_preview"])

    def load(self, *, stage_id: str) -> dict | None:
        path = self._path(stage_id)
        if not path.exists() and not path.is_symlink():
            return None
        record = read_canonical(path)
        keys = {
            "schema", "protocol", "stage_id", "model_id", "status",
            "artifact", "artifact_sha256", "dependencies",
            "claim_sha256", "authorization", "record_sha256",
        }
        if set(record) != keys:
            raise RQ2V2StoreError("Stage record keys mismatch")
        core = {key: val for key, val in record.items()
                if key != "record_sha256"}
        if record["record_sha256"] != digest(core):
            raise RQ2V2StoreError("Stage record SHA mismatch")
        if (
            record["schema"] != VERSION
            or record["protocol"] != DRAFT_PROTOCOL
            or record["stage_id"] != stage_id
            or record["authorization"] != "NO_API_AUTHORITY"
            or record["status"] not in STATUSES
            or type(record["model_id"]) is not str
            or stage_id.split(":")[2] not in record["model_id"].lower()
            or type(record["artifact"]) is not dict
            or record["artifact_sha256"] != digest(record["artifact"])
            or type(record["dependencies"]) is not dict
            or set(record["dependencies"]) != set(_parent_ids(stage_id))
            or any(type(val) is not str or len(val) != 64
                   for val in record["dependencies"].values())
        ):
            raise RQ2V2StoreError("Stage record identity mismatch")
        if record["status"] == "BLOCKED_DEPENDENCY":
            if record["artifact"] or record["claim_sha256"] is not None:
                raise RQ2V2StoreError("Blocked stage must not have claim/output")
        elif (
            not record["artifact"] or type(record["claim_sha256"]) is not str
            or len(record["claim_sha256"]) != 64
        ):
            raise RQ2V2StoreError("Attempted stage missing claim/output")
        reject_gt_keys(record["artifact"])
        return record

    def audit_restart(self) -> dict:
        synthetic_guard(self.data_dir)
        count = 0
        if self.root.exists():
            if not self.root.is_dir():
                raise RQ2V2StoreError("Invalid artifact root")
            for path in self.root.iterdir():
                if not path.name.startswith("V2_STAGE_") or (
                    len(path.name) != len("V2_STAGE_") + 64 + len(".json")
                ) or not path.name.endswith(".json"):
                    raise RQ2V2StoreError("Foreign file in V2 artifact root")
                record = read_canonical(path)
                sid = record.get("stage_id")
                if type(sid) is not str or self._path(sid) != path:
                    raise RQ2V2StoreError("Unplanned artifact filename")
                verified = self.load(stage_id=sid)
                for parent_id in _parent_ids(sid):
                    parent = self.load(stage_id=parent_id)
                    if parent is None or (
                        verified["dependencies"][parent_id] != parent["record_sha256"]
                    ) or parent["model_id"] != verified["model_id"]:
                        raise RQ2V2StoreError("Broken dependency provenance")
                parents = [self.load(stage_id=s) for s in _parent_ids(sid)]
                failed = bool(parents) and any(
                    parent["status"] != "RECORDED_COMPLETE" for parent in parents
                )
                if (verified["status"] == "BLOCKED_DEPENDENCY") != failed:
                    raise RQ2V2StoreError("Blocked dependency status mismatch")
                count += 1
        return {
            "store_version": VERSION, "stored_records": count,
            "can_execute_api": False, "can_execute_test": False,
            "automatic_retry": False,
        }

    def save(self, *, stage_id: str, model_id: str,
             status: str, artifact: dict, claim_sha256: str | None) -> dict:
        preview = self._preview(stage_id)
        if (
            type(model_id) is not str or not model_id.strip()
            or preview["model"] not in model_id.lower()
            or type(status) is not str or status not in STATUSES
            or type(artifact) is not dict
        ):
            raise RQ2V2StoreError("Invalid model/status/artifact")
        if self.load(stage_id=stage_id) is not None:
            raise RQ2V2StoreError("Create-only: stage already stored")
        self.audit_restart()

        dependencies = {}
        for pid in _parent_ids(stage_id):
            parent = self.load(stage_id=pid)
            if parent is None or parent["model_id"] != model_id:
                raise RQ2V2StoreError("Missing/incompatible parent stage")
            dependencies[pid] = parent["record_sha256"]
        failed = bool(dependencies) and any(
            self.load(stage_id=pid)["status"] != "RECORDED_COMPLETE"
            for pid in dependencies
        )
        if (status == "BLOCKED_DEPENDENCY") != failed:
            raise RQ2V2StoreError("Blocked status must match parent outcome")
        if status == "BLOCKED_DEPENDENCY":
            if artifact or claim_sha256 is not None:
                raise RQ2V2StoreError("Blocked stage may not have output/claim")
        elif (
            not artifact or type(claim_sha256) is not str
            or len(claim_sha256) != 64
        ):
            raise RQ2V2StoreError("Attempted stage needs claim and artifact")
        reject_gt_keys(artifact)

        # Un esito D technical complete richiede provenance tool verificata.
        if preview["stage"] == "D" and status == "RECORDED_COMPLETE":
            run = artifact.get("diagnostic_run")
            if type(run) is not dict or run.get("error") is not None:
                raise RQ2V2StoreError("Complete D requires successful run")
            try:
                build_evidence_bundle(
                    run["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise RQ2V2StoreError("D tool provenance invalid") from exc
        if preview["stage"] in ("C", "K") and status == "RECORDED_COMPLETE":
            raw = artifact.get("raw_response")
            d_id = stage_id.rsplit(":", 1)[0] + ":D"
            d = self.load(stage_id=d_id)
            if d is None or d["status"] != "RECORDED_COMPLETE":
                raise RQ2V2StoreError("C/K needs complete D evidence")
            run = d["artifact"]["diagnostic_run"]
            bundle = build_evidence_bundle(
                run["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS
            )
            validator = (
                validate_cause_probe if preview["stage"] == "C"
                else validate_candidate_rule
            )
            try:
                validator(raw, allowed_evidence_ids=evidence_ids(bundle))
            except (TypeError, ValueError) as exc:
                raise RQ2V2StoreError("Invalid synthetic C/K contract") from exc

        core = {
            "schema": VERSION, "protocol": DRAFT_PROTOCOL,
            "stage_id": stage_id, "model_id": model_id,
            "status": status, "artifact": artifact,
            "artifact_sha256": digest(artifact),
            "dependencies": dependencies,
            "claim_sha256": claim_sha256,
            "authorization": "NO_API_AUTHORITY",
        }
        result = {**core, "record_sha256": digest(core)}
        synthetic_guard(self.data_dir)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        write_exclusive(self._path(stage_id), result)
        return {"stage_id": stage_id, "status": status,
                "record_sha256": result["record_sha256"],
                "can_execute_api": False}
