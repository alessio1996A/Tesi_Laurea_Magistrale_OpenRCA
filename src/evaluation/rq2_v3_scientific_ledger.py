"""RQ2-V3 independent source-bound D/C/K ledger; NO PROVIDER DISPATCH.

This module never creates a release, never calls a model and never retries.
It requires an external commit/release SHA, a clean Git checkout and a
separate V3 source-inventory/release verifier (not yet shipped). Until that
verifier exists, construction fails CLOSED. The verifier MUST independently
check the real GT-free source inventory, runtime and single-writer filesystem
assumptions; neither a SHA nor a user-approval string constitutes API access.

Claims are durable before any external model invocation. A crash/ambiguous
invocation leaves an orphan claim; new claims are blocked, never retried.
Records are O_EXCL/fsync/readback and retain exact V3 D/C/K provenance.
Blocked C/K records require a failed parent and MUST NOT have a claim.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path
import re

from evaluation.rq2_v2_unified_scientific_ledger import (
    UnifiedScientificLedgerBlocked,
    _no_gt, _read, _sha, _write_once, _writer_lock,
)
from evaluation.rq2_v2_unified_scientific_ledger_preflight import (
    _repository_commit, _strict_absolute,
)
from evaluation.rq2_v3_scientific_receipt_adapter_candidate import (
    VERSION as RECEIPT_VERSION,
    V3ScientificReceiptBlocked,
    validate_v3_scientific_artifact,
)
from evaluation.rq2_v3_unified_gtfree_discovery_plan import (
    VERSION as PROTOCOL, NAMESPACE, RELEASE_FILE,
    build_offline_v3_discovery_plan,
)

VERSION = "rq2_v3_scientific_ledger_v0"
RELEASE_SCHEMA = "rq2_v3_scientific_release_v1"
CLAIMS_DIR = NAMESPACE / "claims"
RECORDS_DIR = NAMESPACE / "records"
LOCK_FILE = NAMESPACE / ".writer.lock"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
APPROVAL_REF = re.compile(r"[A-Za-z0-9_.:-]{8,160}\Z")
STATUSES = frozenset(("RECORDED_COMPLETE", "INVALID_OUTPUT",
                      "PROVIDER_ERROR", "BLOCKED_DEPENDENCY"))
ATTEMPTED = STATUSES - {"BLOCKED_DEPENDENCY"}
CLAIM_KEYS = frozenset((
    "schema", "protocol", "source_commit", "release_sha256",
    "source_inventory_sha256", "plan_sha256", "stage_id", "model_id",
    "attempt_number", "dependencies", "stage_authorization", "claim_sha256",
))
RECORD_KEYS = frozenset((
    "schema", "protocol", "source_commit", "release_sha256",
    "source_inventory_sha256", "plan_sha256", "stage_id", "model_id",
    "status", "artifact", "artifact_sha256", "dependencies",
    "claim_sha256", "record_sha256",
))
RECEIPT_KEYS = frozenset((
    "version", "stage_id", "status", "artifact",
    "can_execute_api", "can_write_scientific_records", "usd_cost_known",
    "observed_requests_are_http_hard_cap",
))


class V3ScientificLedgerBlocked(RuntimeError):
    """Fail closed on unverified release, identity, history or corruption."""


def _safe_read(path: Path) -> dict | None:
    try:
        return _read(path)
    except (UnifiedScientificLedgerBlocked, OSError) as exc:
        raise V3ScientificLedgerBlocked("Unreadable/noncanonical V3 data") from exc


def _safe_write(path: Path, obj: dict) -> None:
    try:
        _write_once(path, obj)
    except (UnifiedScientificLedgerBlocked, OSError) as exc:
        raise V3ScientificLedgerBlocked("Create-only V3 write failed") from exc


def _digest(value: object) -> str:
    try:
        return _sha(value)
    except (UnifiedScientificLedgerBlocked, TypeError, ValueError) as exc:
        raise V3ScientificLedgerBlocked("Noncanonical V3 object") from exc


def _authorization(auth: object, *, row: dict, release: str,
                   commit: str) -> None:
    """Auditable caller assertion, NOT a cryptographic approval or API permit."""
    if type(auth) is not dict or set(auth) != {
        "scope", "stage_id", "model_id", "source_commit",
        "release_sha256", "approval_reference", "stage_budget_usd",
    }:
        raise V3ScientificLedgerBlocked("One-stage authorization required")
    if (
        auth["scope"] != "ONE_V3_STAGE_CLAIM_ONLY"
        or auth["stage_id"] != row["stage_id"]
        or auth["model_id"] != row["model_id"]
        or auth["source_commit"] != commit
        or auth["release_sha256"] != release
        or type(auth["approval_reference"]) is not str
        or not APPROVAL_REF.fullmatch(auth["approval_reference"])
        or type(auth["stage_budget_usd"]) is not str
        or len(auth["stage_budget_usd"]) > 32
    ):
        raise V3ScientificLedgerBlocked("Wrong stage approval scope")
    try:
        cost = Decimal(auth["stage_budget_usd"])
    except InvalidOperation as exc:
        raise V3ScientificLedgerBlocked("Unparseable USD approval") from exc
    if (not cost.is_finite() or cost <= 0 or cost > Decimal("10000")
            or cost.as_tuple().exponent < -2):
        raise V3ScientificLedgerBlocked("Invalid approved stage USD")


def _receipt_artifact(receipt: object, *, stage_id: str) -> tuple[str, dict]:
    if (
        type(receipt) is not dict or set(receipt) != RECEIPT_KEYS
        or receipt["version"] != RECEIPT_VERSION
        or receipt["stage_id"] != stage_id
        or receipt["status"] not in ATTEMPTED
        or type(receipt["artifact"]) is not dict
        or any(receipt[k] is not False for k in (
            "can_execute_api", "can_write_scientific_records",
            "usd_cost_known", "observed_requests_are_http_hard_cap",
        ))
    ):
        raise V3ScientificLedgerBlocked("Untrusted/misrouted V3 receipt")
    return receipt["status"], receipt["artifact"]


class V3ScientificLedger:
    """Single-writer, release-pinned, create-only registry (not a dispatcher)."""

    def __init__(self, *, data_dir: Path, repo_dir: Path,
                 expected_commit: str, approved_release_sha256: str):
        try:
            self.data = _strict_absolute(data_dir, "V3 data root")
            self.repo = _strict_absolute(repo_dir, "V3 repo root")
        except UnifiedScientificLedgerBlocked as exc:
            raise V3ScientificLedgerBlocked("Unsafe/missing absolute root") from exc
        if (type(expected_commit) is not str
                or not HEX40.fullmatch(expected_commit)
                or type(approved_release_sha256) is not str
                or not HEX64.fullmatch(approved_release_sha256)):
            raise V3ScientificLedgerBlocked("External commit/release pins required")
        self.expected_commit = expected_commit
        self.release_sha = approved_release_sha256
        self.plan = build_offline_v3_discovery_plan()
        self.rows = {r["stage_id"]: r for r in self.plan["entries"]}
        if len(self.rows) != 180 or len(self.plan["ood_test_cases_locked"]) != 11:
            raise V3ScientificLedgerBlocked("V3 cohort/plan drift")
        self.root = self.data / NAMESPACE
        self.inventory_sha = None
        self._gate()
        self.audit_restart()

    def _source_release(self, release: dict) -> dict:
        """Future verifier MUST inspect source files and GT-free inputs.

        This import intentionally fails until the independent source
        inventory and frozen release gate are implemented and audited.
        """
        try:
            from evaluation.rq2_v3_scientific_source_release_gate import (
                V3SourceReleaseBlocked, verify_v3_source_release,
            )
        except ImportError as exc:
            raise V3ScientificLedgerBlocked(
                "V3 source/release gate not installed: NO-GO"
            ) from exc
        try:
            return verify_v3_source_release(
                data_dir=self.data, repo_dir=self.repo, release=release,
                expected_commit=self.expected_commit,
                approved_release_sha256=self.release_sha,
            )
        except V3SourceReleaseBlocked as exc:
            raise V3ScientificLedgerBlocked(
                "V3 source/release verification failed: NO-GO"
            ) from exc

    def _gate(self) -> None:
        try:
            head, dirty = _repository_commit(self.repo)
        except UnifiedScientificLedgerBlocked as exc:
            raise V3ScientificLedgerBlocked("Git identity unavailable") from exc
        if head != self.expected_commit or dirty:
            raise V3ScientificLedgerBlocked("Dirty/drifted V3 source checkout")
        for path in (
            self.data / "data", self.root,
            self.data / CLAIMS_DIR, self.data / RECORDS_DIR,
        ):
            if path.is_symlink() or (path.exists() and not path.is_dir()):
                raise V3ScientificLedgerBlocked("Unsafe V3 path or symlink")
        for historical in ("data/rq2", "data/rq2_v2_unified_scientific_v1",
                           "data/rq2_v2_provenance", "data/results"):
            if (self.data / historical).is_symlink():
                raise V3ScientificLedgerBlocked("Historical symlink: STOP")
        if not self.root.is_dir():
            raise V3ScientificLedgerBlocked("Pre-existing V3 release root required")
        release = _safe_read(self.data / RELEASE_FILE)
        if (
            release is None or _digest(release) != self.release_sha
            or release.get("schema") != RELEASE_SCHEMA
            or release.get("protocol") != PROTOCOL
            or release.get("source_commit") != self.expected_commit
            or release.get("plan_sha256") != self.plan["preview_sha256"]
            or release.get("scientific_namespace") != NAMESPACE.as_posix()
            or release.get("ood_test_cases_locked") !=
                self.plan["ood_test_cases_locked"]
            or type(release.get("source_inventory_sha256")) is not str
            or not HEX64.fullmatch(release["source_inventory_sha256"])
            or release.get("can_run_ood_test") is not False
            or release.get("can_execute_api") is not False
        ):
            raise V3ScientificLedgerBlocked("Absent/unpinned V3 release")
        proof = self._source_release(release)
        if (
            type(proof) is not dict
            or proof.get("status") != "V3_SOURCE_BOUND_RELEASE_VERIFIED"
            or proof.get("source_commit") != self.expected_commit
            or proof.get("release_sha256") != self.release_sha
            or proof.get("source_inventory_sha256") !=
                release["source_inventory_sha256"]
            or proof.get("plan_sha256") != self.plan["preview_sha256"]
            or proof.get("can_execute_api") is not False
            or proof.get("can_run_ood_test") is not False
            or proof.get("can_create_claim") is not False
        ):
            raise V3ScientificLedgerBlocked("Source inventory or release not verified")
        self.inventory_sha = release["source_inventory_sha256"]

    def _row(self, stage_id: str, model_id: str | None = None) -> dict:
        row = self.rows.get(stage_id) if type(stage_id) is str else None
        if row is None or (
            model_id is not None and (
                type(model_id) is not str or row["model_id"] != model_id
            )
        ):
            raise V3ScientificLedgerBlocked("Unknown/OOD/V2 stage or wrong model")
        return row

    def _path(self, stage_id: str, *, claim: bool) -> Path:
        self._row(stage_id)
        folder = CLAIMS_DIR if claim else RECORDS_DIR
        prefix = "V3_CLAIM_" if claim else "V3_RECORD_"
        filename = prefix + hashlib.sha256(
            stage_id.encode("utf-8")
        ).hexdigest() + ".json"
        return self.data / folder / filename

    def _identity(self, stage_id: str, model_id: str) -> dict:
        return {
            "protocol": PROTOCOL,
            "source_commit": self.expected_commit,
            "release_sha256": self.release_sha,
            "source_inventory_sha256": self.inventory_sha,
            "plan_sha256": self.plan["preview_sha256"],
            "stage_id": stage_id,
            "model_id": model_id,
        }

    def load_claim(self, *, stage_id: str) -> dict | None:
        row = self._row(stage_id)
        claim = _safe_read(self._path(stage_id, claim=True))
        if claim is None:
            return None
        core = {k: v for k, v in claim.items() if k != "claim_sha256"}
        if (
            set(claim) != CLAIM_KEYS
            or claim.get("schema") != VERSION + "_claim"
            or any(claim.get(k) != v for k, v in self._identity(
                stage_id, row["model_id"]
            ).items())
            or type(claim.get("attempt_number")) is not int
            or claim["attempt_number"] != 1
            or type(claim.get("dependencies")) is not dict
            or set(claim["dependencies"]) != set(row["depends_on"])
            or any(type(v) is not str or not HEX64.fullmatch(v)
                   for v in claim["dependencies"].values())
            or claim.get("claim_sha256") != _digest(core)
        ):
            raise V3ScientificLedgerBlocked("Claim identity or checksum mismatch")
        _authorization(
            claim["stage_authorization"], row=row, release=self.release_sha,
            commit=self.expected_commit,
        )
        return claim

    def load_record(self, *, stage_id: str) -> dict | None:
        row = self._row(stage_id)
        record = _safe_read(self._path(stage_id, claim=False))
        if record is None:
            return None
        core = {k: v for k, v in record.items() if k != "record_sha256"}
        if (
            set(record) != RECORD_KEYS
            or record.get("schema") != VERSION + "_record"
            or any(record.get(k) != v for k, v in self._identity(
                stage_id, row["model_id"]
            ).items())
            or record.get("status") not in STATUSES
            or type(record.get("artifact")) is not dict
            or record.get("artifact_sha256") != _digest(record["artifact"])
            or record.get("record_sha256") != _digest(core)
            or type(record.get("dependencies")) is not dict
            or set(record["dependencies"]) != set(row["depends_on"])
        ):
            raise V3ScientificLedgerBlocked("Record identity or checksum mismatch")
        try:
            _no_gt(record)
        except UnifiedScientificLedgerBlocked as exc:
            raise V3ScientificLedgerBlocked("Forbidden GT/scoring content") from exc
        parents = {}
        for parent_id in row["depends_on"]:
            parent = self.load_record(stage_id=parent_id)
            if (
                parent is None or parent["model_id"] != row["model_id"]
                or record["dependencies"][parent_id] != parent["record_sha256"]
            ):
                raise V3ScientificLedgerBlocked("Parent record SHA broken")
            parents[parent_id] = parent
        blocked = bool(parents) and any(
            parent["status"] != "RECORDED_COMPLETE" for parent in parents.values()
        )
        if (record["status"] == "BLOCKED_DEPENDENCY") != blocked:
            raise V3ScientificLedgerBlocked("Incorrect D/C/K dependency outcome")
        claim = self.load_claim(stage_id=stage_id)
        if blocked:
            if claim is not None or record["claim_sha256"] is not None:
                raise V3ScientificLedgerBlocked("Blocked stage may not have claim")
            if record["artifact"] != {}:
                raise V3ScientificLedgerBlocked("Blocked stage contains artifact")
        elif (
            claim is None or record["claim_sha256"] != claim["claim_sha256"]
            or record["dependencies"] != claim["dependencies"]
        ):
            raise V3ScientificLedgerBlocked("Unclaimed/mismatched result")
        if not blocked:
            source_d = None
            if row["stage"] != "D":
                d_id = stage_id.rsplit(":", 1)[0] + ":D"
                d = self.load_record(stage_id=d_id)
                if d is None or d["status"] != "RECORDED_COMPLETE":
                    raise V3ScientificLedgerBlocked("Immutable valid D required")
                source_d = d["artifact"]["diagnostic_run"]
            try:
                validate_v3_scientific_artifact(
                    stage_id=stage_id, logical_model=row["logical_model"],
                    status=record["status"], artifact=record["artifact"],
                    diagnostic_run=source_d,
                )
            except (V3ScientificReceiptBlocked, KeyError, TypeError) as exc:
                raise V3ScientificLedgerBlocked("Artifact provenance/readback failed") from exc
        return record

    def audit_restart(self) -> dict:
        """Read-only complete audit. Orphan counts NEVER authorize a retry."""
        self._gate()
        claims, records = set(), set()
        for claim, folder, prefix, seen in (
            (True, CLAIMS_DIR, "V3_CLAIM_", claims),
            (False, RECORDS_DIR, "V3_RECORD_", records),
        ):
            directory = self.data / folder
            if not directory.exists():
                continue
            if directory.is_symlink() or not directory.is_dir():
                raise V3ScientificLedgerBlocked("Unsafe ledger directory")
            for file in directory.iterdir():
                if file.is_symlink() or not file.is_file():
                    raise V3ScientificLedgerBlocked("Unexpected V3 entry")
                obj = _safe_read(file)
                if (
                    obj is None or type(obj.get("stage_id")) is not str
                    or file != self._path(obj["stage_id"], claim=claim)
                    or obj["stage_id"] in seen
                ):
                    raise V3ScientificLedgerBlocked("Unknown/duplicate V3 file")
                seen.add(obj["stage_id"])
                if claim:
                    self.load_claim(stage_id=obj["stage_id"])
                else:
                    self.load_record(stage_id=obj["stage_id"])
        for stage_id in claims:
            claim = self.load_claim(stage_id=stage_id)
            for parent_id, digest in claim["dependencies"].items():
                parent = self.load_record(stage_id=parent_id)
                if (
                    parent is None or parent["record_sha256"] != digest
                    or parent["status"] != "RECORDED_COMPLETE"
                ):
                    raise V3ScientificLedgerBlocked("Claim dependency drift")
        return {
            "status": "V3_SCIENTIFIC_LEDGER_READBACK_AUDITED",
            "claims": len(claims),
            "records": len(records),
            "orphan_claims": len(claims - records),
            "release_sha256": self.release_sha,
            "source_commit": self.expected_commit,
            "source_inventory_sha256": self.inventory_sha,
            "plan_sha256": self.plan["preview_sha256"],
            "automatic_retry_allowed": False,
            "can_execute_api": False,
            "can_run_ood_test": False,
        }

    def claim_stage(self, *, stage_id: str, model_id: str,
                    stage_authorization: dict) -> dict:
        """Create one claim after externally asserted ONE-stage approval.

        This method NEVER dispatches to any provider. The future dispatcher
        must separately prove the user-approved release, stage, budget,
        SDK/runtime and single-writer environment before making any call.
        """
        row = self._row(stage_id, model_id)
        _authorization(
            stage_authorization, row=row, release=self.release_sha,
            commit=self.expected_commit,
        )
        self._gate()
        try:
            with _writer_lock(self.data / LOCK_FILE):
                audit = self.audit_restart()
                if audit["orphan_claims"]:
                    raise V3ScientificLedgerBlocked("Orphan claim: manual review")
                if (
                    self.load_claim(stage_id=stage_id) is not None
                    or self.load_record(stage_id=stage_id) is not None
                ):
                    raise V3ScientificLedgerBlocked("Already attempted: no retry")
                deps = {}
                for parent_id in row["depends_on"]:
                    parent = self.load_record(stage_id=parent_id)
                    if parent is None or parent["status"] != "RECORDED_COMPLETE":
                        raise V3ScientificLedgerBlocked("Parent not complete")
                    deps[parent_id] = parent["record_sha256"]
                core = {
                    "schema": VERSION + "_claim",
                    **self._identity(stage_id, model_id),
                    "attempt_number": 1,
                    "dependencies": deps,
                    "stage_authorization": dict(stage_authorization),
                }
                claim = {**core, "claim_sha256": _digest(core)}
                path = self._path(stage_id, claim=True)
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                _safe_write(path, claim)
                if self.load_claim(stage_id=stage_id) != claim:
                    raise V3ScientificLedgerBlocked("Claim readback mismatch")
        except UnifiedScientificLedgerBlocked as exc:
            raise V3ScientificLedgerBlocked("Writer lock unavailable") from exc
        return {
            "stage_id": stage_id,
            "claim_sha256": claim["claim_sha256"],
            "status": "CLAIM_WITHOUT_RECORD",
            "can_execute_api": False,
        }

    def record_stage(self, *, stage_id: str, model_id: str,
                     receipt: dict | None = None,
                     expected_claim_sha256: str | None = None,
                     blocked: bool = False) -> dict:
        """Store exact adapter receipt, or only a dependency-blocked result."""
        row = self._row(stage_id, model_id)
        if type(blocked) is not bool:
            raise V3ScientificLedgerBlocked("Invalid blocked flag")
        if blocked:
            if receipt is not None or expected_claim_sha256 is not None:
                raise V3ScientificLedgerBlocked("Blocked output/claim forbidden")
            status, artifact = "BLOCKED_DEPENDENCY", {}
        else:
            status, artifact = _receipt_artifact(receipt, stage_id=stage_id)
            if (
                type(expected_claim_sha256) is not str
                or not HEX64.fullmatch(expected_claim_sha256)
            ):
                raise V3ScientificLedgerBlocked("Exact claim binding required")
        self._gate()
        try:
            with _writer_lock(self.data / LOCK_FILE):
                self.audit_restart()
                if self.load_record(stage_id=stage_id) is not None:
                    raise V3ScientificLedgerBlocked("Record exists: no overwrite")
                parents = {}
                for parent_id in row["depends_on"]:
                    parent = self.load_record(stage_id=parent_id)
                    if parent is None:
                        raise V3ScientificLedgerBlocked("Missing parent record")
                    parents[parent_id] = parent
                invalid_parent = bool(parents) and any(
                    parent["status"] != "RECORDED_COMPLETE"
                    for parent in parents.values()
                )
                if blocked != invalid_parent:
                    raise V3ScientificLedgerBlocked("Dependency-blocked mismatch")
                claim = self.load_claim(stage_id=stage_id)
                if blocked:
                    if claim is not None:
                        raise V3ScientificLedgerBlocked("Claimed stage cannot block")
                    claim_sha = None
                elif (
                    claim is None
                    or expected_claim_sha256 != claim["claim_sha256"]
                ):
                    raise V3ScientificLedgerBlocked("Unmatched pre-call claim")
                else:
                    claim_sha = claim["claim_sha256"]
                deps = {sid: p["record_sha256"] for sid, p in parents.items()}
                if claim is not None and claim["dependencies"] != deps:
                    raise V3ScientificLedgerBlocked("Claim parent SHA changed")
                if not blocked:
                    d_source = None
                    if row["stage"] != "D":
                        d_id = stage_id.rsplit(":", 1)[0] + ":D"
                        d = self.load_record(stage_id=d_id)
                        if d is None or d["status"] != "RECORDED_COMPLETE":
                            raise V3ScientificLedgerBlocked("Missing valid D for C/K")
                        d_source = d["artifact"]["diagnostic_run"]
                    try:
                        _no_gt(artifact)
                        validate_v3_scientific_artifact(
                            stage_id=stage_id, logical_model=row["logical_model"],
                            status=status, artifact=artifact,
                            diagnostic_run=d_source,
                        )
                    except (UnifiedScientificLedgerBlocked,
                            V3ScientificReceiptBlocked, KeyError, TypeError) as exc:
                        raise V3ScientificLedgerBlocked("Invalid V3 receipt") from exc
                core = {
                    "schema": VERSION + "_record",
                    **self._identity(stage_id, model_id),
                    "status": status,
                    "artifact": artifact,
                    "artifact_sha256": _digest(artifact),
                    "dependencies": deps,
                    "claim_sha256": claim_sha,
                }
                record = {**core, "record_sha256": _digest(core)}
                path = self._path(stage_id, claim=False)
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                _safe_write(path, record)
                if self.load_record(stage_id=stage_id) != record:
                    raise V3ScientificLedgerBlocked("Record readback mismatch")
        except UnifiedScientificLedgerBlocked as exc:
            raise V3ScientificLedgerBlocked("Writer lock unavailable") from exc
        return {
            "stage_id": stage_id,
            "status": status,
            "record_sha256": record["record_sha256"],
            "can_execute_api": False,
        }
