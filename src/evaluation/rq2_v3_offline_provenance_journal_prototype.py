"""ISOLATED OFFLINE-ONLY journal prototype for candidate C/K provenance.

This journal creates its OWN TemporaryDirectory: no caller-supplied data
paths, Drive, scientific release, API credentials, live dispatch, or approval.
It is NOT the future production V3 ledger. Stage identities come from the
frozen V2 plan ONLY AS SYNTHETIC FIXTURES, so the final V3 identity,
source-bound release and namespace must be designed and frozen separately.

Tests only: create-only claims/records; canonical JSON and SHA; D/C/K parent
binding; C/K strict successor provenance; no retry, no GT, no orphan bypass.
Concurrency/Drive locking and source-pin checks are deliberately NOT claimed.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile

from evaluation.rq2_v2_unified_discovery_plan import build_offline_discovery_plan
from evaluation.rq2_v2_unified_scientific_ledger import (
    UnifiedScientificLedgerBlocked,
    _canonical, _no_gt, _read, _sha, _validate_artifact, _write_once,
)
from evaluation.rq2_v3_ck_provenance_receipt_candidate import (
    CKProvenanceReceiptBlocked,
    validate_candidate_ck_artifact,
)

VERSION = "rq2_v3_offline_provenance_journal_prototype_v0"
PROTOCOL = "RQ2_V3_OFFLINE_FIXTURE_NOT_A_SCIENTIFIC_RELEASE"
STATES = frozenset((
    "RECORDED_COMPLETE", "INVALID_OUTPUT", "PROVIDER_ERROR",
    "BLOCKED_DEPENDENCY",
))


class OfflineProvenanceJournalBlocked(RuntimeError):
    """Invalid, mismatched or corrupted sandbox-only scientific fixture."""


class OfflineProvenanceJournal:
    """One-process, one-temporary-directory, no-provider prototype.

    The directory is owned by this object and deleted by close(), or on
    leaving a context manager. This class cannot target existing data.
    """

    def __init__(self):
        self._temporary = tempfile.TemporaryDirectory(
            prefix="rq2_v3_OFFLINE_ONLY_no_api_"
        )
        self.root = Path(self._temporary.name)
        self.claims = self.root / "claims"
        self.records = self.root / "records"
        self.claims.mkdir()
        self.records.mkdir()
        plan = build_offline_discovery_plan()
        self.plan_sha = plan["preview_sha256"]
        self.rows = {r["stage_id"]: r for r in plan["entries"]}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        self._temporary.cleanup()

    def _row(self, stage_id: str, model_id: str | None = None):
        row = self.rows.get(stage_id) if type(stage_id) is str else None
        if row is None or (model_id is not None and model_id != row["model_id"]):
            raise OfflineProvenanceJournalBlocked("Unknown stage or model")
        return row

    def _path(self, stage_id: str, *, claim: bool) -> Path:
        self._row(stage_id)
        label = "CLAIM_" if claim else "RECORD_"
        folder = self.claims if claim else self.records
        name = hashlib.sha256(stage_id.encode("utf-8")).hexdigest()
        return folder / ("RQ2V3_FIXTURE_" + label + name + ".json")

    def load_claim(self, *, stage_id: str):
        row = self._row(stage_id)
        try:
            obj = _read(self._path(stage_id, claim=True))
        except UnifiedScientificLedgerBlocked as exc:
            raise OfflineProvenanceJournalBlocked("Unreadable claim") from exc
        if obj is None:
            return None
        core = {k: v for k, v in obj.items() if k != "claim_sha256"}
        if (
            set(obj) != {
                "schema", "protocol", "plan_sha256", "stage_id", "model_id",
                "attempt_number", "dependencies", "claim_sha256",
            }
            or obj["schema"] != VERSION + "_claim"
            or obj["protocol"] != PROTOCOL
            or obj["plan_sha256"] != self.plan_sha
            or obj["stage_id"] != stage_id
            or obj["model_id"] != row["model_id"]
            or type(obj["attempt_number"]) is not int
            or obj["attempt_number"] != 1
            or type(obj["dependencies"]) is not dict
            or set(obj["dependencies"]) != set(row["depends_on"])
            or obj["claim_sha256"] != _sha(core)
        ):
            raise OfflineProvenanceJournalBlocked("Invalid claim identity/SHA")
        return obj

    def load_record(self, *, stage_id: str):
        row = self._row(stage_id)
        try:
            obj = _read(self._path(stage_id, claim=False))
        except UnifiedScientificLedgerBlocked as exc:
            raise OfflineProvenanceJournalBlocked("Unreadable record") from exc
        if obj is None:
            return None
        core = {k: v for k, v in obj.items() if k != "record_sha256"}
        if (
            set(obj) != {
                "schema", "protocol", "plan_sha256", "stage_id", "model_id",
                "status", "artifact", "artifact_sha256", "dependencies",
                "claim_sha256", "record_sha256",
            }
            or obj["schema"] != VERSION + "_record"
            or obj["protocol"] != PROTOCOL
            or obj["plan_sha256"] != self.plan_sha
            or obj["stage_id"] != stage_id
            or obj["model_id"] != row["model_id"]
            or obj["status"] not in STATES
            or type(obj["artifact"]) is not dict
            or obj["artifact_sha256"] != _sha(obj["artifact"])
            or obj["record_sha256"] != _sha(core)
            or type(obj["dependencies"]) is not dict
            or set(obj["dependencies"]) != set(row["depends_on"])
        ):
            raise OfflineProvenanceJournalBlocked("Record identity/SHA mismatch")

        parents = {}
        for dep in row["depends_on"]:
            parent = self.load_record(stage_id=dep)
            if parent is None or obj["dependencies"][dep] != parent["record_sha256"]:
                raise OfflineProvenanceJournalBlocked("Missing/changed parent SHA")
            parents[dep] = parent
        blocked = bool(parents) and any(
            parent["status"] != "RECORDED_COMPLETE" for parent in parents.values()
        )
        if (obj["status"] == "BLOCKED_DEPENDENCY") != blocked:
            raise OfflineProvenanceJournalBlocked("Inconsistent blocked status")
        claim = self.load_claim(stage_id=stage_id)
        if blocked:
            if claim is not None or obj["claim_sha256"] is not None:
                raise OfflineProvenanceJournalBlocked("Blocked has forbidden claim")
        elif (
            claim is None
            or obj["claim_sha256"] != claim["claim_sha256"]
            or obj["dependencies"] != claim["dependencies"]
        ):
            raise OfflineProvenanceJournalBlocked("Claim/record mismatch")

        self._validate(row=row, status=obj["status"], artifact=obj["artifact"])
        return obj

    def _validate(self, *, row: dict, status: str, artifact: dict) -> None:
        _no_gt(artifact)
        if status == "BLOCKED_DEPENDENCY":
            if artifact:
                raise OfflineProvenanceJournalBlocked("Blocked has output")
            return
        if row["stage"] == "D":
            try:
                _validate_artifact(row, status, artifact, None)
            except UnifiedScientificLedgerBlocked as exc:
                raise OfflineProvenanceJournalBlocked("Invalid D artifact") from exc
            return
        d_id = row["stage_id"].rsplit(":", 1)[0] + ":D"
        d = self.load_record(stage_id=d_id)
        if d is None or d["status"] != "RECORDED_COMPLETE":
            raise OfflineProvenanceJournalBlocked("Missing successful D")
        try:
            validate_candidate_ck_artifact(
                stage_id=row["stage_id"],
                logical_model=row["logical_model"],
                status=status,
                artifact=artifact,
                diagnostic_run=d["artifact"]["diagnostic_run"],
            )
        except (CKProvenanceReceiptBlocked, KeyError, TypeError) as exc:
            raise OfflineProvenanceJournalBlocked("Invalid successor C/K artifact") from exc

    def audit(self) -> dict:
        counts = {"claims": 0, "records": 0, "orphan_claims": 0}
        for folder, claim, count_key in (
            (self.claims, True, "claims"),
            (self.records, False, "records"),
        ):
            if folder.is_symlink() or not folder.is_dir():
                raise OfflineProvenanceJournalBlocked("Unsafe fixture folder")
            for path in folder.iterdir():
                obj = _read(path)
                if (
                    path.is_symlink() or not path.is_file()
                    or obj is None or type(obj.get("stage_id")) is not str
                    or path != self._path(obj["stage_id"], claim=claim)
                ):
                    raise OfflineProvenanceJournalBlocked("Unknown fixture path")
                if claim:
                    self.load_claim(stage_id=obj["stage_id"])
                else:
                    self.load_record(stage_id=obj["stage_id"])
                counts[count_key] += 1

        for path in self.claims.iterdir():
            obj = _read(path)
            if self.load_record(stage_id=obj["stage_id"]) is None:
                counts["orphan_claims"] += 1
        return {
            **counts,
            "schema": VERSION,
            "protocol": PROTOCOL,
            "can_execute_api": False,
            "scientific_release_exists": False,
            "automatic_retry_allowed": False,
            "production_ready": False,
        }

    def claim_stage(self, *, stage_id: str, model_id: str) -> dict:
        row = self._row(stage_id, model_id)
        if self.audit()["orphan_claims"]:
            raise OfflineProvenanceJournalBlocked("Orphan requires manual review")
        if self.load_claim(stage_id=stage_id) or self.load_record(stage_id=stage_id):
            raise OfflineProvenanceJournalBlocked("Already claimed, no retry")
        deps = {}
        for dep in row["depends_on"]:
            parent = self.load_record(stage_id=dep)
            if parent is None or parent["status"] != "RECORDED_COMPLETE":
                raise OfflineProvenanceJournalBlocked("Parent not complete")
            deps[dep] = parent["record_sha256"]
        core = {
            "schema": VERSION + "_claim",
            "protocol": PROTOCOL,
            "plan_sha256": self.plan_sha,
            "stage_id": stage_id,
            "model_id": model_id,
            "attempt_number": 1,
            "dependencies": deps,
        }
        claim = {**core, "claim_sha256": _sha(core)}
        _write_once(self._path(stage_id, claim=True), claim)
        self.load_claim(stage_id=stage_id)
        return claim

    def record_stage(
        self, *, stage_id: str, model_id: str, status: str, artifact: dict,
    ) -> dict:
        row = self._row(stage_id, model_id)
        if status not in STATES or type(artifact) is not dict:
            raise OfflineProvenanceJournalBlocked("Invalid status/artifact")
        self.audit()
        if self.load_record(stage_id=stage_id) is not None:
            raise OfflineProvenanceJournalBlocked("Record already exists")
        parents = {}
        for dep in row["depends_on"]:
            parent = self.load_record(stage_id=dep)
            if parent is None:
                raise OfflineProvenanceJournalBlocked("Missing parent record")
            parents[dep] = parent
        blocked = bool(parents) and any(
            parent["status"] != "RECORDED_COMPLETE" for parent in parents.values()
        )
        if (status == "BLOCKED_DEPENDENCY") != blocked:
            raise OfflineProvenanceJournalBlocked("Blocked state inconsistent")
        claim = self.load_claim(stage_id=stage_id)
        if blocked:
            if claim is not None:
                raise OfflineProvenanceJournalBlocked("Blocked stage had claim")
            claim_sha = None
        else:
            if claim is None:
                raise OfflineProvenanceJournalBlocked("Missing pre-call claim")
            claim_sha = claim["claim_sha256"]
        deps = {k: v["record_sha256"] for k, v in parents.items()}
        if claim is not None and claim["dependencies"] != deps:
            raise OfflineProvenanceJournalBlocked("Parent SHA changed")
        self._validate(row=row, status=status, artifact=artifact)
        core = {
            "schema": VERSION + "_record",
            "protocol": PROTOCOL,
            "plan_sha256": self.plan_sha,
            "stage_id": stage_id,
            "model_id": model_id,
            "status": status,
            "artifact": artifact,
            "artifact_sha256": _sha(artifact),
            "dependencies": deps,
            "claim_sha256": claim_sha,
        }
        record = {**core, "record_sha256": _sha(core)}
        _write_once(self._path(stage_id, claim=False), record)
        self.load_record(stage_id=stage_id)
        return record
