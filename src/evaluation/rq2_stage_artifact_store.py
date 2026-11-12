"""RQ2 source-bound, create-only STAGE ARTIFACT storage (no execution).

This module persists caller-supplied stage content, including errors, in a
separate RQ2 directory. It does NOT invoke agents, providers, tools, scorers
or model-produced pseudocode. Its input is a DRAFT_NOT_EXECUTABLE plan: NO
write or audit here authorizes any model call or scientific freeze.

Only discovery D/C/K can be stored under this V0 contract. Test stages are
blocked entirely until a separate, preregistered SCIENTIFIC freeze protocol
is implemented; the synthetic mock-journal freeze is NEVER accepted.

The plan is rebuilt using the frozen GT-free CSVs (preview_market) and hashes
are checked again on each store operation. Result integrity is checked with
canonical JSON and SHA-256; this detects accidental corruption, NOT malicious
edits by an attacker who can rewrite bytes and recompute hashes.

Never use this store in place of a claim/lease system for asynchronous runs.
No retry or automatic overwrite is permitted. A partial/crashed write remains
on disk for investigation and blocks that stage.
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
STORE_SUBDIRECTORY = Path("data/rq2/stage_artifacts_v0")
MAX_ARTIFACT_BYTES = 32_000_000
_STATUSES = frozenset((
    "RECORDED_COMPLETE", "INVALID_OUTPUT", "PROVIDER_ERROR",
    "BLOCKED_DEPENDENCY",
))
# These refer to evaluation-only schema keys and cannot be silently stored
# inside model-facing RQ2 artifacts. This is NOT a semantic GT scrubber.
_FORBIDDEN_KEYS = frozenset((
    "ground_truth", "ground_truth_reason", "scoring_points",
    "reference_fault_types", "reference_complete", "true_fault_type",
    "true_label", "expected_fault_type", "fault_label", "ood_labels",
    "target_reasons",
))


class RQ2ArtifactStoreError(ValueError):
    """Refuse a source-integrity, artifact-integrity or phase-gate violation."""


def _encoded(value: object) -> bytes:
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
    return hashlib.sha256(data).hexdigest()


def _source_sha(path: Path) -> str:
    try:
        return _sha(path.read_bytes())
    except OSError as exc:
        raise RQ2ArtifactStoreError("GT-free source unreadable") from exc


def _filename(stage_id: str) -> str:
    return "RQ2_STAGE_" + _sha(stage_id.encode("utf-8")) + ".json"


def _check_no_gt_schema(value: object) -> None:
    """Reject known evaluation-only KEY names, not model text content."""
    if type(value) is dict:
        for name, item in value.items():
            if type(name) is not str or name.lower() in _FORBIDDEN_KEYS:
                raise RQ2ArtifactStoreError("Forbidden/non-string artifact key")
            _check_no_gt_schema(item)
    elif type(value) is list:
        for item in value:
            _check_no_gt_schema(item)


def _read_canonical(path: Path) -> dict:
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
    """Read-only source validation + persist immutable discovery artifacts.

    The destination is fixed under data_dir/data/rq2/stage_artifacts_v0.
    A caller cannot redirect it into RQ1's data/results directory.
    """

    def __init__(self, *, data_dir: Path):
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
        # No writes in constructor: a preflight cannot create output files.

    def _verify_sources(self) -> None:
        split = self.data_dir / "data/processed/split_market_v1.csv"
        manifest = self.data_dir / "data/processed/benchmark_inputs_market.csv"
        if (
            _source_sha(split) != EXPECTED_SPLIT_SHA256
            or _source_sha(manifest) != EXPECTED_MANIFEST_SHA256
        ):
            raise RQ2ArtifactStoreError("Original GT-free sources changed")

    def _guard_directory(self) -> None:
        # Only the new RQ2 subdirectory may be written.
        if any(p.is_symlink() for p in (
            self.data_dir / "data/rq2", self.root,
        )):
            raise RQ2ArtifactStoreError("Symlink in RQ2 artifact path")
        if self.root.exists() and not self.root.is_dir():
            raise RQ2ArtifactStoreError("Artifact root is not a directory")

    def _path(self, stage_id: str) -> Path:
        if stage_id not in self.entries:
            raise RQ2ArtifactStoreError("Stage not in verified plan")
        return self.root / _filename(stage_id)

    def _check_record(self, stage_id: str) -> dict | None:
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
        """Verify all existing receipts and ordered dependencies on resume."""
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
        """Load a verified discovery artifact, never release test or model calls.

        Re-audits the full journal first, then returns the canonical record.
        This is for a separate offline D/C/K recorder, NOT a provider runner.
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
        """Store one caller-provided result; NEVER dispatch an agent/provider."""
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
        # All existing stored files, including failures, must survive re-audit.
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
