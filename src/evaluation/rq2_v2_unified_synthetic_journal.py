"""Journal UNIFICATO G3 (5 harness x 3 modelli), SOLO fixture sintetiche.

Non e' una release scientifica, non e' il dispatcher live e non usa Market.
Permette di verificare in sicurezza claim, dipendenze D/C/K, SHA,
immutabilita' e ripartenza, in un namespace separato dagli archivi V1
e dal pilot Sonnet V2. NESSUNA API, credenziale, GT o pseudocodice eseguito.

Un claim viene creato una sola volta con O_EXCL; un claim senza record
e' una condizione DA INVESTIGARE, MAI un'autorizzazione a ritentare.
"""
from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path

from evaluation.rq2_evidence_bundle import (
    EvidenceBundleError, build_evidence_bundle, evidence_ids,
)
from evaluation.rq2_output_contracts import (
    ContractError, validate_candidate_rule, validate_cause_probe,
)
from evaluation.rq2_stage_binding import ALLOWED_TOOLS
from evaluation.rq2_v2_artifact_store import (
    RQ2V2StoreError, canonical, digest, read_canonical,
    reject_gt_keys, synthetic_guard, write_exclusive,
)
from evaluation.rq2_v2_unified_discovery_plan import (
    VERSION as PROTOCOL, build_offline_discovery_plan,
)
from evaluation.rq2_v2_unified_provenance_gate import (
    UnifiedRQ2ProvenanceError, audit_captured_v2_d,
)

VERSION = "rq2_v2_unified_synthetic_claim_journal_v0"
RELATIVE_ROOT = Path("data/rq2_v2_unified_synthetic_v0")
CLAIMS = RELATIVE_ROOT / "claims"
RECORDS = RELATIVE_ROOT / "records"
STATUSES = frozenset((
    "RECORDED_COMPLETE", "INVALID_OUTPUT", "PROVIDER_ERROR",
    "BLOCKED_DEPENDENCY",
))
_HEX = re.compile(r"[0-9a-f]{64}\Z")


class UnifiedRQ2JournalError(ValueError):
    """Identita', vincoli, integrita' o stato non rispettati."""


@lru_cache(maxsize=1)
def _planned_rows() -> dict[str, dict]:
    # Piano deterministico identico per tutti i journal, nessuna I/O.
    return {
        row["stage_id"]: row
        for row in build_offline_discovery_plan()["entries"]
    }


def _entry(stage_id: str) -> dict:
    if type(stage_id) is not str:
        raise UnifiedRQ2JournalError("Stage ID must be text")
    row = _planned_rows().get(stage_id)
    if row is None:
        raise UnifiedRQ2JournalError("Unknown/locked unified V2 stage")
    return row


def _paths(root: Path) -> None:
    # synthetic_guard rifiuta anche Market.zip, data/processed e la V1.
    synthetic_guard(root)
    for part in (
        root / "data", root / RELATIVE_ROOT,
        root / CLAIMS, root / RECORDS,
    ):
        if part.is_symlink():
            raise UnifiedRQ2JournalError("Symlink in unified V2 storage")
        if part.exists() and not part.is_dir():
            raise UnifiedRQ2JournalError("Non-directory in unified V2 storage")


def _stage_path(root: Path, stage_id: str, folder: Path, prefix: str) -> Path:
    _entry(stage_id)
    name = hashlib.sha256(stage_id.encode("utf-8")).hexdigest()
    return root / folder / (prefix + name + ".json")


def _read(path: Path) -> dict | None:
    if not path.exists() and not path.is_symlink():
        return None
    try:
        return read_canonical(path)
    except RQ2V2StoreError as exc:
        raise UnifiedRQ2JournalError("Stored file is not canonical") from exc


def _assert_sha(value: object, field: str) -> None:
    if type(value) is not str or not _HEX.fullmatch(value):
        raise UnifiedRQ2JournalError("Invalid SHA256: " + field)


def _validate_payload(stage: str, status: str, artifact: dict,
                      entry: dict, d_record: dict | None) -> None:
    """Cattura stati invalidi senza mascherarli con successi inventati."""
    if status == "BLOCKED_DEPENDENCY":
        if artifact:
            raise UnifiedRQ2JournalError("Blocked stage cannot carry output")
        return
    if status == "PROVIDER_ERROR":
        if set(artifact) != {"provider_error"} or (
            type(artifact["provider_error"]) is not str
            or not artifact["provider_error"].strip()
        ):
            raise UnifiedRQ2JournalError("Provider error receipt required")
        return
    if stage == "D":
        if set(artifact) != {"diagnostic_run"} or (
            type(artifact["diagnostic_run"]) is not dict
        ):
            raise UnifiedRQ2JournalError("D diagnostic_run required")
        run = artifact["diagnostic_run"]
        if run.get("error") is not None:
            raise UnifiedRQ2JournalError(
                "D with execution error cannot be complete/invalid"
            )
        try:
            audit_captured_v2_d(
                run=run, case_id=entry["case_id"],
                model=entry["logical_model"], harness=entry["harness"],
            )
        except UnifiedRQ2ProvenanceError:
            prov = False
        else:
            prov = True
        result_valid = (
            prov and run.get("json_status") == "valid_json"
            and type(run.get("raw_response")) is str
            and bool(run["raw_response"].strip())
        )
        if (status == "RECORDED_COMPLETE") != result_valid:
            raise UnifiedRQ2JournalError("D status/provenance/output mismatch")
        return

    if set(artifact) != {"raw_response"} or type(artifact["raw_response"]) is not str:
        raise UnifiedRQ2JournalError("C/K raw text required")
    if d_record is None or d_record["status"] != "RECORDED_COMPLETE":
        raise UnifiedRQ2JournalError("C/K requires completed D")
    d = d_record["artifact"]["diagnostic_run"]
    try:
        bundle = build_evidence_bundle(
            d["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS,
        )
        refs = evidence_ids(bundle)
        validator = (
            validate_cause_probe if stage == "C"
            else validate_candidate_rule
        )
        validator(artifact["raw_response"], allowed_evidence_ids=refs)
    except (EvidenceBundleError, ContractError, KeyError, TypeError, ValueError):
        valid = False
    else:
        valid = True
    if (status == "RECORDED_COMPLETE") != valid:
        raise UnifiedRQ2JournalError("C/K status/contract mismatch")


class UnifiedRQ2SyntheticJournal:
    """Archivio di prova create-only, NON utilizzabile con dati OpenRCA reali."""

    def __init__(self, *, data_dir: Path):
        self.root = Path(data_dir)
        _paths(self.root)
        self.plan = build_offline_discovery_plan()
        # Nessuna directory viene creata nel costruttore.
        self.audit_restart()

    def _entry_model(self, stage_id: str, model_id: str) -> dict:
        item = _entry(stage_id)
        if type(model_id) is not str or model_id != item["model_id"]:
            raise UnifiedRQ2JournalError("Exact model ID mismatch")
        return item

    def _path(self, stage_id: str, *, claim: bool) -> Path:
        return _stage_path(
            self.root, stage_id, CLAIMS if claim else RECORDS,
            "V2U_CLAIM_" if claim else "V2U_RECORD_",
        )

    def load_claim(self, *, stage_id: str) -> dict | None:
        _paths(self.root)
        item = _entry(stage_id)
        obj = _read(self._path(stage_id, claim=True))
        if obj is None:
            return None
        expected = {
            "schema", "protocol", "plan_sha256", "stage_id",
            "model_id", "attempt_number", "dependencies",
            "authorization", "claim_sha256",
        }
        core = {k: v for k, v in obj.items() if k != "claim_sha256"}
        if (
            set(obj) != expected
            or obj["schema"] != VERSION + "_claim"
            or obj["protocol"] != PROTOCOL
            or obj["plan_sha256"] != self.plan["preview_sha256"]
            or obj["stage_id"] != stage_id
            or obj["model_id"] != item["model_id"]
            or type(obj["attempt_number"]) is not int
            or obj["attempt_number"] != 1
            or obj["authorization"] != "SYNTHETIC_NO_API_AUTHORITY"
            or type(obj["dependencies"]) is not dict
            or set(obj["dependencies"]) != set(item["depends_on"])
            or any(
                type(val) is not str or not _HEX.fullmatch(val)
                for val in obj["dependencies"].values()
            )
            or obj["claim_sha256"] != digest(core)
        ):
            raise UnifiedRQ2JournalError("Corrupt claim or protocol identity")
        return obj

    def load_record(self, *, stage_id: str) -> dict | None:
        _paths(self.root)
        item = _entry(stage_id)
        obj = _read(self._path(stage_id, claim=False))
        if obj is None:
            return None
        expected = {
            "schema", "protocol", "plan_sha256", "stage_id", "model_id",
            "status", "artifact", "artifact_sha256", "dependencies",
            "authorization", "claim_sha256", "record_sha256",
        }
        core = {k: v for k, v in obj.items() if k != "record_sha256"}
        if (
            set(obj) != expected
            or obj["schema"] != VERSION + "_record"
            or obj["protocol"] != PROTOCOL
            or obj["plan_sha256"] != self.plan["preview_sha256"]
            or obj["stage_id"] != stage_id
            or obj["model_id"] != item["model_id"]
            or obj["status"] not in STATUSES
            or type(obj["artifact"]) is not dict
            or obj["artifact_sha256"] != digest(obj["artifact"])
            or type(obj["dependencies"]) is not dict
            or set(obj["dependencies"]) != set(item["depends_on"])
            or obj["authorization"] != "SYNTHETIC_NO_API_AUTHORITY"
            or obj["record_sha256"] != digest(core)
        ):
            raise UnifiedRQ2JournalError("Corrupt record or protocol identity")
        try:
            reject_gt_keys(obj["artifact"])
        except RQ2V2StoreError as exc:
            raise UnifiedRQ2JournalError("Forbidden GT in stored record") from exc
        for pid in item["depends_on"]:
            parent = self.load_record(stage_id=pid)
            if (
                parent is None or obj["dependencies"][pid] != parent["record_sha256"]
                or parent["model_id"] != item["model_id"]
            ):
                raise UnifiedRQ2JournalError("Broken parent SHA reference")
        parents = [
            self.load_record(stage_id=pid) for pid in item["depends_on"]
        ]
        bad_parent = bool(parents) and any(
            p["status"] != "RECORDED_COMPLETE" for p in parents
        )
        if (obj["status"] == "BLOCKED_DEPENDENCY") != bad_parent:
            raise UnifiedRQ2JournalError("Blocked status disagrees with parents")
        claim = self.load_claim(stage_id=stage_id)
        if obj["status"] == "BLOCKED_DEPENDENCY":
            if claim is not None or obj["claim_sha256"] is not None:
                raise UnifiedRQ2JournalError("Blocked record has claim")
        elif claim is None or obj["claim_sha256"] != claim["claim_sha256"]:
            raise UnifiedRQ2JournalError("Missing/mismatched execution claim")
        if claim is not None and claim["dependencies"] != obj["dependencies"]:
            raise UnifiedRQ2JournalError("Parent binding differs from claim")
        stem = stage_id.rsplit(":", 1)[0]
        d_rec = (
            obj if item["stage"] == "D"
            else self.load_record(stage_id=stem + ":D")
        )
        _validate_payload(
            item["stage"], obj["status"], obj["artifact"], item, d_rec,
        )
        return obj

    def audit_restart(self) -> dict:
        _paths(self.root)
        count_claim, count_record, unresolved, matched = 0, 0, 0, 0
        for folder, claim, prefix in (
            (CLAIMS, True, "V2U_CLAIM_"),
            (RECORDS, False, "V2U_RECORD_"),
        ):
            location = self.root / folder
            if not location.exists():
                continue
            for path in location.iterdir():
                if (
                    path.is_symlink() or not path.is_file()
                    or not path.name.startswith(prefix)
                    or not _HEX.fullmatch(
                        path.name[len(prefix):-5]
                    ) or not path.name.endswith(".json")
                ):
                    raise UnifiedRQ2JournalError("Unexpected file in synthetic journal")
                raw = _read(path)
                sid = raw.get("stage_id")
                if type(sid) is not str or self._path(sid, claim=claim) != path:
                    raise UnifiedRQ2JournalError("Unplanned filename/record ID")
                if claim:
                    self.load_claim(stage_id=sid)
                    count_claim += 1
                else:
                    self.load_record(stage_id=sid)
                    count_record += 1

        # Un claim orfano non viene cancellato né riciclato, nemmeno se
        # il processo e' fallito prima di una qualunque chiamata LLM.
        location = self.root / CLAIMS
        if location.exists():
            for path in location.iterdir():
                sid = _read(path)["stage_id"]
                claim_obj = self.load_claim(stage_id=sid)
                for pid, sha in claim_obj["dependencies"].items():
                    parent = self.load_record(stage_id=pid)
                    if (
                        parent is None or parent["record_sha256"] != sha
                        or parent["status"] != "RECORDED_COMPLETE"
                    ):
                        raise UnifiedRQ2JournalError("Claim parent drift")
                rec = self.load_record(stage_id=sid)
                if rec is None:
                    unresolved += 1
                else:
                    matched += 1
        return {
            "status": "SYNTHETIC_RESTART_AUDITED",
            "protocol": PROTOCOL,
            "plan_sha256": self.plan["preview_sha256"],
            "claims": count_claim,
            "stored_stage_records": count_record,
            "matched_claim_records": matched,
            "unresolved_claims_for_manual_review": unresolved,
            "can_execute_api": False,
            "can_access_market": False,
            "can_run_ood_test": False,
            "automatic_retry_allowed": False,
            "writes_only_synthetic_fixture": True,
        }

    def claim_stage(self, *, stage_id: str, model_id: str) -> dict:
        _paths(self.root)
        item = self._entry_model(stage_id, model_id)
        self.audit_restart()
        if self.load_claim(stage_id=stage_id) is not None:
            raise UnifiedRQ2JournalError("Already claimed: never auto retry")
        if self.load_record(stage_id=stage_id) is not None:
            raise UnifiedRQ2JournalError("Already recorded: create-only")
        deps = {}
        for pid in item["depends_on"]:
            prior = self.load_record(stage_id=pid)
            if prior is None or prior["status"] != "RECORDED_COMPLETE":
                raise UnifiedRQ2JournalError("Parent missing/invalid: stage blocked")
            deps[pid] = prior["record_sha256"]
        core = {
            "schema": VERSION + "_claim",
            "protocol": PROTOCOL,
            "plan_sha256": self.plan["preview_sha256"],
            "stage_id": stage_id,
            "model_id": model_id,
            "attempt_number": 1,
            "dependencies": deps,
            "authorization": "SYNTHETIC_NO_API_AUTHORITY",
        }
        obj = {**core, "claim_sha256": digest(core)}
        directory = self.root / CLAIMS
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        _paths(self.root)
        try:
            write_exclusive(self._path(stage_id, claim=True), obj)
        except RQ2V2StoreError as exc:
            raise UnifiedRQ2JournalError("Exclusive claim creation failed") from exc
        return {
            "stage_id": stage_id,
            "status": "CLAIM_WITHOUT_RECORD",
            "claim_sha256": obj["claim_sha256"],
            "can_execute_api": False,
        }

    def record_stage(self, *, stage_id: str, model_id: str,
                     status: str, artifact: dict) -> dict:
        """Registra un singolo outcome di una fixture; MAI una API reale."""
        _paths(self.root)
        item = self._entry_model(stage_id, model_id)
        if type(status) is not str or status not in STATUSES or type(artifact) is not dict:
            raise UnifiedRQ2JournalError("Invalid status/artifact")
        self.audit_restart()
        if self.load_record(stage_id=stage_id) is not None:
            raise UnifiedRQ2JournalError("Already recorded: create-only")
        deps = {}
        for pid in item["depends_on"]:
            prior = self.load_record(stage_id=pid)
            if prior is None:
                raise UnifiedRQ2JournalError("Parent record missing")
            deps[pid] = prior["record_sha256"]
        failed = bool(deps) and any(
            self.load_record(stage_id=pid)["status"] != "RECORDED_COMPLETE"
            for pid in deps
        )
        if (status == "BLOCKED_DEPENDENCY") != failed:
            raise UnifiedRQ2JournalError("Blocked outcome contradicts parent status")
        claim = self.load_claim(stage_id=stage_id)
        if status == "BLOCKED_DEPENDENCY":
            if claim is not None:
                raise UnifiedRQ2JournalError("Blocked stage cannot have a claim")
            claim_sha = None
        else:
            if claim is None or claim["model_id"] != model_id:
                raise UnifiedRQ2JournalError("Missing claim for attempted stage")
            if claim["dependencies"] != deps:
                raise UnifiedRQ2JournalError("Dependency SHA changed after claim")
            claim_sha = claim["claim_sha256"]
        _validate_payload(
            item["stage"], status, artifact, item,
            self.load_record(stage_id=stage_id.rsplit(":", 1)[0] + ":D")
            if item["stage"] != "D" else None,
        )
        try:
            reject_gt_keys(artifact)
        except RQ2V2StoreError as exc:
            raise UnifiedRQ2JournalError("Forbidden GT/scoring field") from exc
        core = {
            "schema": VERSION + "_record",
            "protocol": PROTOCOL,
            "plan_sha256": self.plan["preview_sha256"],
            "stage_id": stage_id,
            "model_id": model_id,
            "status": status,
            "artifact": artifact,
            "artifact_sha256": digest(artifact),
            "dependencies": deps,
            "authorization": "SYNTHETIC_NO_API_AUTHORITY",
            "claim_sha256": claim_sha,
        }
        obj = {**core, "record_sha256": digest(core)}
        directory = self.root / RECORDS
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        _paths(self.root)
        try:
            write_exclusive(self._path(stage_id, claim=False), obj)
        except RQ2V2StoreError as exc:
            raise UnifiedRQ2JournalError("Exclusive record creation failed") from exc
        return {
            "stage_id": stage_id,
            "status": status,
            "record_sha256": obj["record_sha256"],
            "can_execute_api": False,
        }
