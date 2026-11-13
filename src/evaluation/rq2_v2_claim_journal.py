"""Journal indipendente RQ2-V2, create-only e SOLO per fixture sintetiche.

Il claim NON concede nessuna API authority. Ogni tentativo puo' avere un
solo claim; un claim orfano resta irrisolto e non viene mai ritentato.
V1 non e' importata, letta o alterata.
"""
from __future__ import annotations

from pathlib import Path

from evaluation.rq2_v2_artifact_store import (
    RQ2V2StoreError, RQ2V2SyntheticArtifactStore, VERSION as STORE_VERSION,
    canonical, digest, read_canonical, synthetic_guard, write_exclusive,
    _parent_ids,
)
from evaluation.rq2_v2_isolation_policy import (
    CLAIMS_RELATIVE, DRAFT_PROTOCOL, RQ2V2IsolationError,
    preview_v2_destination,
)

VERSION = "rq2_v2_synthetic_claim_journal_v0"


class RQ2V2ClaimError(ValueError):
    """Stage gia' reclamato, dipendenza falsa o claim non canonico."""


class RQ2V2SyntheticClaimJournal:
    """Crea claim prima dei record in namespace V2 di fixture, senza provider."""

    def __init__(self, *, data_dir: Path):
        self.data_dir = data_dir
        synthetic_guard(data_dir)
        self.store = RQ2V2SyntheticArtifactStore(data_dir=data_dir)
        self.root = data_dir / CLAIMS_RELATIVE
        self.audit_restart()  # read-only

    def _preview(self, stage_id: str) -> dict:
        synthetic_guard(self.data_dir)
        try:
            return preview_v2_destination(
                data_dir=self.data_dir, stage_id=stage_id
            )
        except RQ2V2IsolationError as exc:
            raise RQ2V2ClaimError("Unplanned/locked V2 stage") from exc

    def _path(self, stage_id: str) -> Path:
        return Path(self._preview(stage_id)["claim_path_preview"])

    def load_claim(self, *, stage_id: str) -> dict | None:
        path = self._path(stage_id)
        if not path.exists() and not path.is_symlink():
            return None
        claim = read_canonical(path)
        keys = {
            "schema", "protocol", "stage_id", "model_id",
            "attempt_number", "dependencies", "authorization",
            "claim_sha256",
        }
        if set(claim) != keys:
            raise RQ2V2ClaimError("Claim schema mismatch")
        core = {key: val for key, val in claim.items()
                if key != "claim_sha256"}
        if (
            claim["schema"] != VERSION
            or claim["protocol"] != DRAFT_PROTOCOL
            or claim["stage_id"] != stage_id
            or type(claim["model_id"]) is not str
            or self._preview(stage_id)["model"] not in claim["model_id"].lower()
            or claim["attempt_number"] != 1
            or type(claim["attempt_number"]) is not int
            or claim["authorization"] != "NO_API_AUTHORITY"
            or type(claim["dependencies"]) is not dict
            or set(claim["dependencies"]) != set(_parent_ids(stage_id))
            or any(type(val) is not str or len(val) != 64
                   for val in claim["dependencies"].values())
            or claim["claim_sha256"] != digest(core)
        ):
            raise RQ2V2ClaimError("Claim identity/digest mismatch")
        return claim

    def audit_restart(self) -> dict:
        synthetic_guard(self.data_dir)
        stored = self.store.audit_restart()
        count, matched, unresolved = 0, 0, 0
        if self.root.exists():
            for path in self.root.iterdir():
                if not path.name.startswith("V2_CLAIM_") or (
                    len(path.name) != len("V2_CLAIM_") + 64 + len(".json")
                ) or not path.name.endswith(".json"):
                    raise RQ2V2ClaimError("Foreign claim in V2 namespace")
                item = read_canonical(path)
                sid = item.get("stage_id")
                if type(sid) is not str or self._path(sid) != path:
                    raise RQ2V2ClaimError("Unplanned claim filename")
                claim = self.load_claim(stage_id=sid)
                for pid, sha in claim["dependencies"].items():
                    parent = self.store.load(stage_id=pid)
                    if (
                        parent is None or parent["record_sha256"] != sha
                        or parent["status"] != "RECORDED_COMPLETE"
                        or parent["model_id"] != claim["model_id"]
                    ):
                        raise RQ2V2ClaimError("Claim parent provenance mismatch")
                result = self.store.load(stage_id=sid)
                if result is None:
                    unresolved += 1
                elif (
                    result["claim_sha256"] != claim["claim_sha256"]
                    or result["model_id"] != claim["model_id"]
                ):
                    raise RQ2V2ClaimError("Claim/result identity mismatch")
                else:
                    matched += 1
                count += 1
        # Un risultato non-blocked senza claim e' vietato.
        if self.store.root.exists():
            for path in self.store.root.iterdir():
                rec = read_canonical(path)
                sid = rec["stage_id"]
                claim = self.load_claim(stage_id=sid)
                if rec["status"] == "BLOCKED_DEPENDENCY":
                    if claim is not None:
                        raise RQ2V2ClaimError("Blocked result has provider claim")
                elif claim is None or rec["claim_sha256"] != claim["claim_sha256"]:
                    raise RQ2V2ClaimError("Attempted result missing original claim")
        return {
            "journal_version": VERSION,
            "store_version": STORE_VERSION,
            "claims": count,
            "finished_with_matching_result": matched,
            "unresolved_manual_review": unresolved,
            "stored_stage_records": stored["stored_records"],
            "can_execute_api": False,
            "can_execute_test": False,
            "automatic_retry_allowed": False,
        }

    def claim_stage(self, *, stage_id: str, model_id: str) -> dict:
        preview = self._preview(stage_id)
        if (
            type(model_id) is not str or not model_id.strip()
            or preview["model"] not in model_id.lower()
        ):
            raise RQ2V2ClaimError("Incompatible model ID")
        self.audit_restart()
        if self.load_claim(stage_id=stage_id) is not None:
            raise RQ2V2ClaimError("Already claimed: NEVER auto retry")
        if self.store.load(stage_id=stage_id) is not None:
            raise RQ2V2ClaimError("Already recorded: create-only")
        parents = {}
        for pid in _parent_ids(stage_id):
            item = self.store.load(stage_id=pid)
            if (
                item is None or item["status"] != "RECORDED_COMPLETE"
                or item["model_id"] != model_id
            ):
                raise RQ2V2ClaimError("Parent missing/failed: claim refused")
            parents[pid] = item["record_sha256"]
        core = {
            "schema": VERSION, "protocol": DRAFT_PROTOCOL,
            "stage_id": stage_id, "model_id": model_id,
            "attempt_number": 1, "dependencies": parents,
            "authorization": "NO_API_AUTHORITY",
        }
        claim = {**core, "claim_sha256": digest(core)}
        synthetic_guard(self.data_dir)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            write_exclusive(self._path(stage_id), claim)
        except RQ2V2StoreError as exc:
            raise RQ2V2ClaimError("Exclusive create-only claim failed") from exc
        return {
            "stage_id": stage_id,
            "claim_sha256": claim["claim_sha256"],
            "status": "CLAIM_WITHOUT_ARTIFACT",
            "can_execute_api": False,
            "automatic_retry": False,
        }

    def record_stage(self, *, stage_id: str, model_id: str,
                     status: str, artifact: dict) -> dict:
        """Record solo dopo claim, eccetto BLOCKED_DEPENDENCY senza claim."""
        preview = self._preview(stage_id)
        if (
            type(model_id) is not str
            or preview["model"] not in model_id.lower()
        ):
            raise RQ2V2ClaimError("Incompatible model ID")
        self.audit_restart()
        claim = self.load_claim(stage_id=stage_id)
        if status == "BLOCKED_DEPENDENCY":
            if claim is not None:
                raise RQ2V2ClaimError("Blocked stage must not have a claim")
            ref = None
        else:
            if claim is None or claim["model_id"] != model_id:
                raise RQ2V2ClaimError("Missing/mismatched original claim")
            for pid, expected in claim["dependencies"].items():
                parent = self.store.load(stage_id=pid)
                if parent is None or expected != parent["record_sha256"]:
                    raise RQ2V2ClaimError("Claim dependency changed")
            ref = claim["claim_sha256"]
        return self.store.save(
            stage_id=stage_id, model_id=model_id,
            status=status, artifact=artifact, claim_sha256=ref,
        )
