"""RQ2 *mock-only* create-only journal for fail-closed workflow tests.

No model provider, API key, telemetry tool, dataset, scorer, or LLM output.
This module cannot execute D, C, or K. It only writes synthetic completion
receipts to a caller-owned temporary directory for testing state transitions.

It deliberately accepts ONLY a verified-internal-shape DRAFT_NOT_EXECUTABLE
plan, explicitly refuses paid API and test before MOCK discovery freeze.
A MOCK freeze is NOT a scientific or production rule freeze.

Never import this module into a production provider dispatch pathway.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from evaluation.rq2_dryrun_plan import PLAN_STATUS, VERSION

JOURNAL_VERSION = "rq2_mock_journal_v0"
STAGE_KEYS = {
    "stage_id", "case_id", "cloudbed", "task_index", "start_unix", "end_unix",
    "phase", "logical_model", "harness", "max_tool_rounds_for_D",
    "stage", "dependencies", "execution_status",
}
FREEZE_NAME = "MOCK_DISCOVERY_FREEZE.json"


class MockJournalError(ValueError):
    """Refuse an ambiguous/invalid mock transition or journal corruption."""


def _serialized(obj) -> bytes:
    try:
        return json.dumps(
            obj, sort_keys=True, ensure_ascii=False, allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise MockJournalError("Noncanonical mock content") from exc


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _record_name(stage_id: str) -> str:
    return "MOCK_STAGE_" + _sha(stage_id.encode("utf-8")) + ".json"


def _read_json(path: Path) -> dict:
    if path.is_symlink():
        raise MockJournalError("Symlink in mock journal")
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise MockJournalError("Cannot read mock receipt") from exc
    if len(payload) > 50_000:
        raise MockJournalError("Oversized mock receipt")
    try:
        item = json.loads(payload)
    except (ValueError, RecursionError) as exc:
        raise MockJournalError("Corrupt mock receipt") from exc
    if type(item) is not dict or _serialized(item) != payload:
        raise MockJournalError("Mock receipt is not canonical")
    return item


def _create_only(path: Path, obj: dict) -> None:
    payload = _serialized(obj)
    if path.is_symlink() or path.exists():
        raise MockJournalError("Create-only: receipt already exists")
    # The stage identifier is hashed to prevent any path traversal.
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise MockJournalError("Create-only: receipt already exists") from exc
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
    except Exception:
        # Never overwrite/delete an incomplete receipt: a restart must fail
        # closed on a partial write until manually audited.
        raise


class RQ2MockJournal:
    """Deterministic synthetic stage receipts with discovery/test gate.

    Constructor needs a directory path created by the *test harness* (tmpdir).
    It is not a provider runner and cannot switch from mock to live mode.
    """

    def __init__(self, *, plan: dict, root: Path):
        if type(plan) is not dict or plan.get("protocol") != VERSION:
            raise MockJournalError("Wrong RQ2 stage plan protocol")
        if (
            plan.get("status") != PLAN_STATUS
            or plan.get("preview_only") is not True
            or plan.get("can_execute_api") is not False
            or plan.get("api_budget_approved") is not False
            or plan.get("model_api_calls") != 0
            or plan.get("files_written") is not False
            or plan.get("cross_phase_gate")
            != "TEST_BLOCKED_UNTIL_DISCOVERY_RULES_FREEZE"
        ):
            raise MockJournalError("Only blocked non-executable plans are accepted")
        entries = plan.get("entries")
        if type(entries) is not list or len(entries) != 204:
            raise MockJournalError("Unexpected number of mock stages")
        by_id = {}
        for entry in entries:
            if type(entry) is not dict or set(entry) != STAGE_KEYS:
                raise MockJournalError("Stage contains unexpected fields")
            ident = entry["stage_id"]
            if type(ident) is not str or not ident.startswith(VERSION + ":"):
                raise MockJournalError("Invalid stage ID")
            if ident in by_id:
                raise MockJournalError("Duplicate stage ID")
            if entry["execution_status"] != "BLOCKED_DRAFT":
                raise MockJournalError("Unexpected executable stage")
            if entry["phase"] not in ("discovery", "test"):
                raise MockJournalError("Unknown phase")
            if entry["stage"] not in ("D", "C", "K"):
                raise MockJournalError("Unknown stage")
            if entry["stage"] == "K" and entry["phase"] != "discovery":
                raise MockJournalError("K must never be in test")
            if type(entry["dependencies"]) is not list or any(
                type(dep) is not str for dep in entry["dependencies"]
            ):
                raise MockJournalError("Invalid stage dependency list")
            by_id[ident] = entry
        counts = {
            stage: sum(e["stage"] == stage for e in entries)
            for stage in ("D", "C", "K")
        }
        if counts != {"D": 90, "C": 90, "K": 24}:
            raise MockJournalError("Unexpected mock stage totals")
        # Validate the authentic digest produced by rq2_dryrun_plan.
        expected_hash = _sha(_serialized({
            "summary": {
                key: value for key, value in plan.items()
                if key not in ("entries", "preview_sha256")
            },
            "entries": entries,
        }))
        if plan.get("preview_sha256") != expected_hash:
            raise MockJournalError("Plan preview hash mismatch")
        previous = set()
        for entry in entries:
            if any(dep not in previous for dep in entry["dependencies"]):
                raise MockJournalError("Non-topological stage dependencies")
            prefix = entry["stage_id"].rsplit(":", 1)[0]
            expected = (
                [] if entry["stage"] == "D" else
                [prefix + ":D"] if entry["stage"] == "C" else
                [prefix + ":C"]
            )
            if entry["dependencies"] != expected:
                raise MockJournalError("Unexpected D/C/K dependency shape")
            previous.add(entry["stage_id"])

        directory = Path(root)
        if directory.exists() and (not directory.is_dir() or directory.is_symlink()):
            raise MockJournalError("Invalid journal directory")
        if not directory.exists():
            try:
                directory.mkdir(parents=False, mode=0o700)
            except OSError as exc:
                raise MockJournalError("Cannot create journal directory") from exc
        self.root = directory
        self.plan_sha = expected_hash
        self.entries = by_id
        self.stage_order = [e["stage_id"] for e in entries]

    def _path(self, stage_id: str) -> Path:
        return self.root / _record_name(stage_id)

    def _completed(self, stage_id: str) -> dict | None:
        path = self._path(stage_id)
        if path.is_symlink():
            raise MockJournalError("Symlink in mock stage receipt")
        if not path.exists():
            return None
        data = _read_json(path)
        if set(data) != {
            "journal_version", "plan_sha256", "stage_id", "phase",
            "stage", "mock_outcome", "dependencies",
            "record_sha256",
        }:
            raise MockJournalError("Unexpected mock record schema")
        core = {k: value for k, value in data.items() if k != "record_sha256"}
        if data["record_sha256"] != _sha(_serialized(core)):
            raise MockJournalError("Mock record digest mismatch")
        entry = self.entries.get(stage_id)
        if (
            entry is None
            or data["journal_version"] != JOURNAL_VERSION
            or data["plan_sha256"] != self.plan_sha
            or data["stage_id"] != stage_id
            or data["phase"] != entry["phase"]
            or data["stage"] != entry["stage"]
            or data["mock_outcome"] != "MOCK_COMPLETE"
            or data["dependencies"] != entry["dependencies"]
        ):
            raise MockJournalError("Mock record does not match plan")
        return data

    def _freeze(self) -> dict | None:
        path = self.root / FREEZE_NAME
        if path.is_symlink():
            raise MockJournalError("Symlink in mock freeze receipt")
        if not path.exists():
            return None
        data = _read_json(path)
        if set(data) != {
            "journal_version", "plan_sha256",
            "status", "discovery_k_record_hashes", "freeze_sha256"
        }:
            raise MockJournalError("Unexpected mock freeze schema")
        core = {k: v for k, v in data.items() if k != "freeze_sha256"}
        if _sha(_serialized(core)) != data["freeze_sha256"]:
            raise MockJournalError("Mock freeze integrity mismatch")
        if data["journal_version"] != JOURNAL_VERSION or (
            data["plan_sha256"] != self.plan_sha
        ) or data["status"] != "MOCK_ONLY_NOT_RULE_FREEZE":
            raise MockJournalError("Wrong mock freeze source")
        required_k = sorted(
            stage_id for stage_id, e in self.entries.items()
            if e["phase"] == "discovery" and e["stage"] == "K"
        )
        observed = {
            key: self._completed(key)["record_sha256"]
            for key in required_k
            if self._completed(key) is not None
        }
        if len(observed) != 24 or data["discovery_k_record_hashes"] != observed:
            raise MockJournalError("Mock freeze does not match all 24 K receipts")
        return data

    def mark_mock_complete(self, stage_id: str) -> dict:
        """Create ONE synthetic receipt, never execute a model or a tool."""
        if stage_id not in self.entries:
            raise MockJournalError("Unknown stage ID")
        if self._completed(stage_id) is not None:
            raise MockJournalError("Create-only: stage already completed")
        entry = self.entries[stage_id]
        if entry["phase"] == "test" and self._freeze() is None:
            raise MockJournalError("Test stage blocked until discovery MOCK freeze")
        for dependency in entry["dependencies"]:
            if self._completed(dependency) is None:
                raise MockJournalError("Stage dependency not complete")
        core = {
            "journal_version": JOURNAL_VERSION,
            "plan_sha256": self.plan_sha,
            "stage_id": stage_id,
            "phase": entry["phase"],
            "stage": entry["stage"],
            "mock_outcome": "MOCK_COMPLETE",
            "dependencies": entry["dependencies"],
        }
        record = {**core, "record_sha256": _sha(_serialized(core))}
        _create_only(self._path(stage_id), record)
        return record

    def freeze_mock_discovery(self) -> dict:
        """Create a mock phase gate; NOT a scientific pseudorule freeze."""
        if (self.root / FREEZE_NAME).exists():
            raise MockJournalError("Create-only: freeze already exists")
        all_k = sorted(
            sid for sid, e in self.entries.items()
            if e["phase"] == "discovery" and e["stage"] == "K"
        )
        hashes = {}
        for sid in all_k:
            record = self._completed(sid)
            if record is None:
                raise MockJournalError("Cannot freeze incomplete mock discovery")
            hashes[sid] = record["record_sha256"]
        if len(hashes) != 24:
            raise MockJournalError("Unexpected number of mock K receipts")
        core = {
            "journal_version": JOURNAL_VERSION,
            "plan_sha256": self.plan_sha,
            "status": "MOCK_ONLY_NOT_RULE_FREEZE",
            "discovery_k_record_hashes": hashes,
        }
        result = {**core, "freeze_sha256": _sha(_serialized(core))}
        _create_only(self.root / FREEZE_NAME, result)
        return result

    def resume_audit(self) -> dict:
        """Fail closed on unknown files, malformed receipts or missing gates."""
        expected_files = {_record_name(sid) for sid in self.entries}
        expected_files.add(FREEZE_NAME)
        actual = {p.name for p in self.root.iterdir()}
        if actual - expected_files:
            raise MockJournalError("Unknown file in mock journal")
        frozen = self._freeze()
        completed = []
        completed_set = set()
        for sid in self.stage_order:
            record = self._completed(sid)
            if record is None:
                continue
            e = self.entries[sid]
            if not set(e["dependencies"]) <= completed_set:
                raise MockJournalError("Recorded stage lacks prior dependencies")
            if e["phase"] == "test" and frozen is None:
                raise MockJournalError("Test receipt before discovery mock freeze")
            completed_set.add(sid)
            completed.append(sid)
        return {
            "journal_version": JOURNAL_VERSION,
            "plan_sha256": self.plan_sha,
            "status": "MOCK_ONLY_NEVER_API",
            "completed_stage_count": len(completed),
            "discovery_mock_frozen": frozen is not None,
            "model_api_calls": 0,
            "can_execute_api": False,
            "ground_truth_read": False,
        }
