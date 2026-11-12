"""Offline-only durable, create-only claims against duplicate RQ2 calls.

No provider, agent, API, cost ceiling, scorer, or Market telemetry access.
A claim means "the stage may have started" but is NOT permission to run it.
The caller must obtain an independent protocol/authorization gate.

A claim is NEVER released on a timer: after a Colab crash, the ambiguous
CLAIM_WITHOUT_ARTIFACT remains a manual review item. Not deleting or
automatically retrying claims prevents accidental duplicate API billing.

This V0 journal ONLY accepts 4-case discovery D/C/K; test stages remain
inaccessible, irrespective of MOCK discovery freezes.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from evaluation.rq2_stage_artifact_store import (
    RQ2ArtifactStoreError, RQ2StageArtifactStore,
    _encoded, _create_exclusive, _read_canonical, _sha,
)

VERSION = "rq2_discovery_claim_journal_v0"
CLAIMS_SUBDIRECTORY = Path("data/rq2/stage_claims_v0")
CLAIM_KEYS = frozenset({
    "journal_version", "stage_id", "case_id", "phase", "stage",
    "logical_model", "harness", "model_id_proposed",
    "plan_preview_sha256", "split_sha256", "manifest_sha256",
    "dependency_record_hashes", "attempt_number", "created_at_utc",
    "authority", "claim_sha256",
})
AUTHORITY = "NO_API_AUTHORITY"
REVIEW = "CLAIM_WITHOUT_ARTIFACT"
FINISHED = "MATCHING_ARTIFACT_RECORDED"


class RQ2ClaimError(ValueError):
    """Refuse duplicate calls, corrupt journal, or unauthorized phase."""


def _claim_filename(stage_id: str) -> str:
    return "RQ2_CLAIM_" + _sha(stage_id.encode("utf-8")) + ".json"


class RQ2DiscoveryClaimJournal:
    """Read-only source verification; fixed write path, no external dispatch."""

    def __init__(self, *, data_dir: Path):
        self.store = RQ2StageArtifactStore(data_dir=Path(data_dir))
        self.entries = self.store.entries
        self.plan_sha = self.store.plan_sha
        self.root = self.store.data_dir / CLAIMS_SUBDIRECTORY
        self._guard_directory()
        # Do not create directory, claim, LLM, or experiment in constructor.

    def _guard_directory(self):
        for part in (
            self.store.data_dir / "data/rq2",
            self.root,
        ):
            if part.is_symlink():
                raise RQ2ClaimError("Symlink in claim journal path")
        if self.root.exists() and not self.root.is_dir():
            raise RQ2ClaimError("Claim journal path is not a directory")

    def _entry(self, sid: str) -> dict:
        if type(sid) is not str or sid not in self.entries:
            raise RQ2ClaimError("Unplanned stage ID")
        entry = self.entries[sid]
        if entry["phase"] != "discovery":
            raise RQ2ClaimError("TEST stage claims forbidden before scientific freeze")
        return entry

    def _path(self, sid: str) -> Path:
        self._entry(sid)
        return self.root / _claim_filename(sid)

    def _read_claim(self, sid: str) -> dict | None:
        path = self._path(sid)
        if not path.exists() and not path.is_symlink():
            return None
        try:
            claim = _read_canonical(path)
        except RQ2ArtifactStoreError as exc:
            raise RQ2ClaimError("Unreadable or noncanonical claim") from exc
        if set(claim) != CLAIM_KEYS:
            raise RQ2ClaimError("Claim schema mismatch")
        core = {key: val for key, val in claim.items()
                if key != "claim_sha256"}
        if claim["claim_sha256"] != _sha(_encoded(core)):
            raise RQ2ClaimError("Claim checksum mismatch")
        entry = self.entries[sid]
        if (
            claim["journal_version"] != VERSION
            or claim["stage_id"] != sid
            or claim["case_id"] != entry["case_id"]
            or claim["phase"] != "discovery"
            or claim["stage"] != entry["stage"]
            or claim["logical_model"] != entry["logical_model"]
            or claim["harness"] != entry["harness"]
            or claim["plan_preview_sha256"] != self.plan_sha
            or claim["split_sha256"] != self.store.plan_split_sha256
            or claim["manifest_sha256"] != self.store.plan_manifest_sha256
            or claim["attempt_number"] != 1
            or type(claim["attempt_number"]) is not int
            or claim["authority"] != AUTHORITY
            or type(claim["model_id_proposed"]) is not str
            or entry["logical_model"] not in claim["model_id_proposed"].lower()
            or type(claim["created_at_utc"]) is not str
            or not claim["created_at_utc"].endswith("+00:00")
            or type(claim["dependency_record_hashes"]) is not dict
            or set(claim["dependency_record_hashes"]) != set(entry["dependencies"])
        ):
            raise RQ2ClaimError("Claim identity or original sources mismatch")
        return claim

    def audit_restart(self) -> dict:
        """Inspect claims AND result archive; never auto-resubmit unresolved."""
        self._guard_directory()
        archive = self.store.audit_restart()
        if not self.root.exists():
            return {
                "journal_version": VERSION,
                "claims": 0,
                "finished_with_matching_result": 0,
                "unresolved_manual_review": 0,
                "result_archive_discovery_count":
                    archive["stored_discovery_stages"],
                "can_execute_api": False,
                "can_execute_test": False,
                "automatic_retry_allowed": False,
                "financial_cost_cap": None,
            }
        all_names = {item.name for item in self.root.iterdir()}
        allowed_names = {
            _claim_filename(sid) for sid, entry in self.entries.items()
            if entry["phase"] == "discovery"
        }
        if all_names - allowed_names:
            raise RQ2ClaimError("Foreign or test-stage file in claims directory")
        found, finished, unresolved = 0, 0, 0
        for sid, entry in self.entries.items():
            if entry["phase"] != "discovery":
                continue
            claim = self._read_claim(sid)
            if claim is None:
                continue
            found += 1
            for dep in entry["dependencies"]:
                previous = self.store.load_discovery_stage(stage_id=dep)
                if previous is None or (
                    previous["record_sha256"] !=
                    claim["dependency_record_hashes"][dep]
                ):
                    raise RQ2ClaimError("Claim dependency digest mismatch")
                if previous["status"] != "RECORDED_COMPLETE":
                    raise RQ2ClaimError("Claim after failed dependent stage")
                if previous["model_id_proposed"] != claim["model_id_proposed"]:
                    raise RQ2ClaimError("Claim uses different model than parent")
            result = self.store.load_discovery_stage(stage_id=sid)
            if result is None:
                unresolved += 1
            else:
                if result["model_id_proposed"] != claim["model_id_proposed"]:
                    raise RQ2ClaimError("Claim and result model identity differ")
                finished += 1
        return {
            "journal_version": VERSION,
            "claims": found,
            "finished_with_matching_result": finished,
            "unresolved_manual_review": unresolved,
            "result_archive_discovery_count":
                archive["stored_discovery_stages"],
            "can_execute_api": False,
            "can_execute_test": False,
            "automatic_retry_allowed": False,
            "financial_cost_cap": None,
        }

    def claim_stage(self, *, stage_id: str, model_id_proposed: str) -> dict:
        """Record POSSIBLE onset of one call; this authorizes NOTHING.

        An existing claim (even with no result) blocks a repeated attempt.
        If C or K is requested, its parent artifact must be complete.
        BLOCKED_DEPENDENCY must be stored without a provider claim.
        """
        entry = self._entry(stage_id)
        if (
            type(model_id_proposed) is not str
            or not model_id_proposed.strip()
            or len(model_id_proposed) > 160
            or entry["logical_model"] not in model_id_proposed.lower()
        ):
            raise RQ2ClaimError("Bad proposed model identity")
        self.audit_restart()
        if self._read_claim(stage_id) is not None:
            raise RQ2ClaimError("Stage already claimed: NEVER auto retry")
        if self.store.load_discovery_stage(stage_id=stage_id) is not None:
            raise RQ2ClaimError("Stage already recorded: create-only")
        dependencies = {}
        for dep in entry["dependencies"]:
            previous = self.store.load_discovery_stage(stage_id=dep)
            if previous is None:
                raise RQ2ClaimError("Cannot claim before dependency result")
            if previous["status"] != "RECORDED_COMPLETE":
                raise RQ2ClaimError("Dependent stage failed; record BLOCKED instead")
            if previous["model_id_proposed"] != model_id_proposed:
                raise RQ2ClaimError("Claim model differs from stored dependency")
            dependencies[dep] = previous["record_sha256"]
        self.store._verify_sources()
        core = {
            "journal_version": VERSION,
            "stage_id": stage_id,
            "case_id": entry["case_id"],
            "phase": entry["phase"],
            "stage": entry["stage"],
            "logical_model": entry["logical_model"],
            "harness": entry["harness"],
            "model_id_proposed": model_id_proposed,
            "plan_preview_sha256": self.plan_sha,
            "split_sha256": self.store.plan_split_sha256,
            "manifest_sha256": self.store.plan_manifest_sha256,
            "dependency_record_hashes": dependencies,
            "attempt_number": 1,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "authority": AUTHORITY,
        }
        claim = {**core, "claim_sha256": _sha(_encoded(core))}
        self._guard_directory()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            _create_exclusive(self._path(stage_id), _encoded(claim))
        except RQ2ArtifactStoreError as exc:
            raise RQ2ClaimError("Create-only claim refused") from exc
        return {
            "journal_version": VERSION,
            "stage_id": stage_id,
            "claim_sha256": claim["claim_sha256"],
            "status": REVIEW,
            "auto_retry": False,
            "can_execute_api": False,
            "can_execute_test": False,
            "financial_cost_cap": None,
        }
