"""Ledger scientifico V2 per UN solo pilot Sonnet D reale, separato da V1.

Nessuna API: il PIN della release parte volutamente da None. La sorgente
Market GT-free e i file di codice sono verificati prima del claim. Scritture
O_EXCL e readback, mai retry, nessun accesso ai risultati V1 o allo scorer.
NON riutilizzare gli store V2 synthetic-only per dati reali.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from evaluation.rq2_dryrun_plan import (
    EXPECTED_MANIFEST_SHA256, EXPECTED_SPLIT_SHA256,
)
from evaluation.rq2_evidence_bundle import build_evidence_bundle
from evaluation.rq2_protocol_identity_preflight import preview_protocol_identity
from evaluation.rq2_source_bound_d_preflight import preview_discovery_d_config
from evaluation.rq2_stage_binding import ALLOWED_TOOLS

VERSION = "rq2_v2_sonnet_sourcebound_ledger_v1"
PROTOCOL = "rq2_v2_sonnet_q050_d_sourcebound_pilot_v1"
STAGE_ID = PROTOCOL + ":cloudbed-1_q050:sonnet:A1:D"
MODEL_ID = "claude-sonnet-5-5"
RELATIVE_ROOT = Path("data/rq2_v2_provenance/sonnet_q050_d_pilot_v1")
RELEASE_RELATIVE = RELATIVE_ROOT / "release_v1.json"
CLAIM_RELATIVE = RELATIVE_ROOT / "claims" / "pilot_d_claim_v1.json"
RECORD_RELATIVE = RELATIVE_ROOT / "records" / "pilot_d_record_v1.json"
# Da impostare solo in un commit successivo, DOPO preregistrazione, pin
# runtime/codice, verifica budget e approvazione di UNA sola D a pagamento.
EXPECTED_RELEASE_SHA256: str | None = None
MAX_BYTES = 20_000_000
HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
FORBIDDEN = frozenset((
    "ground_truth", "ground_truth_reason", "scoring_points",
    "reference_fault_types", "true_fault_type", "true_label",
    "expected_fault_type", "fault_label", "ood_labels",
))


class SonnetPilotBlocked(ValueError):
    """Anomalia di source binding, release, provenance o ledger: STOP."""


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _forbid_gt(value) -> None:
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str or key.lower() in FORBIDDEN:
                raise SonnetPilotBlocked("GT/scoring key forbidden")
            _forbid_gt(item)
    elif type(value) is list:
        for item in value:
            _forbid_gt(item)


def _canonical(value) -> bytes:
    _forbid_gt(value)
    try:
        data = json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise SonnetPilotBlocked("Noncanonical JSON") from exc
    if len(data) > MAX_BYTES:
        raise SonnetPilotBlocked("Record exceeds bounded size")
    return data


def _digest(value) -> str:
    return _hash(_canonical(value))


def _safe_path(path: Path) -> Path:
    if not isinstance(path, Path) or not path.is_absolute() or ".." in path.parts:
        raise SonnetPilotBlocked("Absolute path without traversal required")
    if path.is_symlink():
        raise SonnetPilotBlocked("Symlink forbidden")
    return path


def _read_json(path: Path) -> dict:
    _safe_path(path)
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise SonnetPilotBlocked("Missing/oversized record")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise SonnetPilotBlocked("Unreadable JSON") from exc
    if type(value) is not dict or raw != _canonical(value):
        raise SonnetPilotBlocked("Noncanonical stored record")
    return value


def _write_once(path: Path, obj: dict) -> None:
    payload = _canonical(obj)
    _safe_path(path)
    if path.exists():
        raise SonnetPilotBlocked("Stage already exists; no retry")
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except OSError as exc:
        raise SonnetPilotBlocked("Exclusive create failed") from exc
    with os.fdopen(fd, "wb") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    # Non cancellare mai un file parziale in caso di write failure.


def source_binding(*, data_dir: Path, repo_dir: Path) -> dict:
    """Vera verifica GT-free dei due CSV e delle sorgenti congelate RQ1.

    Legge solo input di manifest/split, sorgenti Python e HEAD locale.
    Non legge ground truth, risultati V1 o OOD test come osservazioni.
    """
    root, repo = _safe_path(data_dir), _safe_path(repo_dir)
    if not root.is_dir() or not repo.is_dir():
        raise SonnetPilotBlocked("Missing data/repository directory")
    # Prima del preflight escludere link simbolici anche negli input GT-free.
    for source in (
        root / "data", root / "data/processed",
        root / "data/processed/split_market_v1.csv",
        root / "data/processed/benchmark_inputs_market.csv",
    ):
        _safe_path(source)
    preview = preview_discovery_d_config(
        data_dir=root, case_id="cloudbed-1_q050", logical_model="sonnet",
        harness="A1", proposed_model_name=MODEL_ID,
        output_contract_mode="v2_enforce",
    )
    identity = preview_protocol_identity(src_root=repo / "src")
    proposal = preview["experiment_config_proposal"]
    if (
        preview.get("source_verified_in_this_function") is not True
        or preview.get("split_sha256") != EXPECTED_SPLIT_SHA256
        or preview.get("manifest_sha256") != EXPECTED_MANIFEST_SHA256
        or identity.get("rq1_source_blob_sha1_match") is not True
        or proposal.get("variant") != "A1"
        or proposal.get("variant_scheme") != "current"
        or proposal.get("model_provider") != "anthropic"
        or proposal.get("model_name") != MODEL_ID
        or proposal.get("max_tool_rounds") != 6
        or proposal.get("recursion_limit") != 30
        or proposal.get("output_contract_mode") != "v2_enforce"
    ):
        raise SonnetPilotBlocked("Source or D config mismatch")
    graph_file = repo / "src/agent/rq2_v2_graph_engine.py"
    _safe_path(graph_file)
    if not graph_file.is_file():
        raise SonnetPilotBlocked("Missing V2 graph")
    try:
        head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=normal"],
            check=True, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError) as exc:
        raise SonnetPilotBlocked("Repository commit cannot be certified") from exc
    if dirty or not re.fullmatch(r"[0-9a-f]{40}", head):
        raise SonnetPilotBlocked("Unclean or unpinned repository")
    bound = {
        "protocol": PROTOCOL, "stage_id": STAGE_ID,
        "code_commit": head,
        "v2_graph_sha256": _hash(graph_file.read_bytes()),
        "rq1_runner_sha256": identity["rq1_source_sha256"][
            "evaluation/experiment_runner.py"
        ],
        "split_sha256": preview["split_sha256"],
        "manifest_sha256": preview["manifest_sha256"],
        "plan_preview_sha256": preview["plan_preview_sha256"],
        "instruction_sha256": preview["instruction_sha256"],
        "config": proposal,
    }
    return {**bound, "source_binding_sha256": _digest(bound)}


def read_frozen_release(*, data_dir: Path, binding: dict,
                        release_sha256: str | None = None) -> dict:
    """Nessuna release attiva finché EXPECTED_RELEASE_SHA256 e' None."""
    pin = release_sha256 if release_sha256 is not None else EXPECTED_RELEASE_SHA256
    if type(pin) is not str or not HASH_RE.fullmatch(pin):
        raise SonnetPilotBlocked("NO_API: scientific release SHA not pinned")
    release_path = _safe_path(data_dir) / RELEASE_RELATIVE
    release = _read_json(release_path)
    if _hash(_canonical(release)) != pin:
        raise SonnetPilotBlocked("Frozen release SHA mismatch")
    required = {
        "schema", "protocol", "stage_id", "source_binding_sha256",
        "code_commit", "provider", "model_id", "harness", "stage",
        "output_contract_mode", "max_tool_rounds", "recursion_limit",
        "max_retries", "max_tokens", "timeout_seconds",
        "max_llm_requests", "authorization", "api_budget_approved",
        "approved_usd_limit", "runtime_versions", "ood_test_locked",
    }
    if (
        set(release) != required
        or release["schema"] != "rq2_v2_sonnet_pilot_release_v1"
        or release["protocol"] != PROTOCOL
        or release["stage_id"] != STAGE_ID
        or release["source_binding_sha256"] != binding["source_binding_sha256"]
        or release["code_commit"] != binding["code_commit"]
        or release["provider"] != "anthropic"
        or release["model_id"] != MODEL_ID
        or release["harness"] != "A1"
        or release["stage"] != "D"
        or release["output_contract_mode"] != "v2_enforce"
        or type(release["max_tool_rounds"]) is not int
        or release["max_tool_rounds"] != 6
        or type(release["recursion_limit"]) is not int
        or release["recursion_limit"] != 30
        or type(release["max_retries"]) is not int
        or release["max_retries"] != 0
        or type(release["max_tokens"]) is not int
        or release["max_tokens"] != 4096
        or type(release["timeout_seconds"]) not in (int, float)
        or release["timeout_seconds"] != 300
        or type(release["max_llm_requests"]) is not int
        or release["max_llm_requests"] != 7
        or release["authorization"] != "approved_for_one_pilot"
        or release["api_budget_approved"] is not True
        or type(release["approved_usd_limit"]) not in (int, float)
        or not 0 < release["approved_usd_limit"] <= 100
        or type(release["runtime_versions"]) is not dict
        or not release["runtime_versions"]
        or release["ood_test_locked"] is not True
    ):
        raise SonnetPilotBlocked("Release is not a single approved D")
    return release


class RQ2V2SonnetPilotLedger:
    """Source-bound ledger reale: una D, claim prima delle richieste, no retry."""

    def __init__(self, *, data_dir: Path, repo_dir: Path,
                 release_sha256: str | None = None):
        self.data_dir = _safe_path(data_dir)
        self.repo_dir = _safe_path(repo_dir)
        # L'hash approvato si passa al momento del pilot: nessun commit
        # di pin che alteri la HEAD scientifica gia' congelata.
        self.release_sha256 = (
            release_sha256 if release_sha256 is not None
            else EXPECTED_RELEASE_SHA256
        )
        self.root = self.data_dir / RELATIVE_ROOT
        self.claim_path = self.data_dir / CLAIM_RELATIVE
        self.record_path = self.data_dir / RECORD_RELATIVE
        # Non leggere o attraversare data/rq2 V1. Controllare ogni componente V2.
        for path in (
            self.data_dir / "data", self.data_dir / "data/rq2_v2_provenance",
            self.root, self.root / "claims", self.root / "records",
            self.data_dir / RELEASE_RELATIVE,
            self.claim_path, self.record_path,
        ):
            _safe_path(path)

    def _gate(self) -> tuple[dict, dict]:
        binding = source_binding(data_dir=self.data_dir, repo_dir=self.repo_dir)
        release = read_frozen_release(
            data_dir=self.data_dir, binding=binding,
            release_sha256=self.release_sha256,
        )
        return binding, release

    def _verify_claim(self, *, required: bool = False) -> dict | None:
        if not self.claim_path.exists() and not self.claim_path.is_symlink():
            if required:
                raise SonnetPilotBlocked("Missing original claim")
            return None
        claim = _read_json(self.claim_path)
        if (
            set(claim) != {"schema", "stage_id", "model_id",
                           "source_binding_sha256", "release_sha256",
                           "attempt_number", "claim_sha256"}
            or claim["schema"] != VERSION + "_claim"
            or claim["stage_id"] != STAGE_ID
            or claim["model_id"] != MODEL_ID
            or claim["attempt_number"] != 1
            or type(claim["attempt_number"]) is not int
            or claim["release_sha256"] != self.release_sha256
            or claim["claim_sha256"] != _digest({
                k: v for k, v in claim.items() if k != "claim_sha256"
            })
        ):
            raise SonnetPilotBlocked("Original claim invalid")
        return claim

    def _verify_record(self, claim: dict | None) -> dict | None:
        if not self.record_path.exists() and not self.record_path.is_symlink():
            return None
        record = _read_json(self.record_path)
        if (
            set(record) != {"schema", "stage_id", "model_id", "status",
                            "claim_sha256", "source_binding_sha256",
                            "diagnostic_run", "evidence_bundle_sha256",
                            "provenance_issue", "record_sha256"}
            or record["schema"] != VERSION + "_record"
            or record["stage_id"] != STAGE_ID
            or record["model_id"] != MODEL_ID
            or claim is None
            or record["claim_sha256"] != claim["claim_sha256"]
            or record["source_binding_sha256"] != claim["source_binding_sha256"]
            or record["record_sha256"] != _digest({
                k: v for k, v in record.items() if k != "record_sha256"
            })
        ):
            raise SonnetPilotBlocked("Pilot record/readback mismatch")
        expected_status, evidence_hash, issue = self._classify(
            record["diagnostic_run"]
        )
        if (record["status"], record["evidence_bundle_sha256"],
            record["provenance_issue"]) != (expected_status, evidence_hash, issue):
            raise SonnetPilotBlocked("Recorded status/provenance mismatch")
        return record

    @staticmethod
    def _classify(run: dict) -> tuple[str, str | None, str | None]:
        if (
            type(run) is not dict
            or run.get("case_id") != "cloudbed-1_q050"
            or run.get("variant") != "A1"
            or run.get("variant_scheme") != "current"
            or run.get("model") != MODEL_ID
            or run.get("model_provider") != "anthropic"
            or run.get("max_tool_rounds") != 6
            or run.get("output_contract_mode") != "v2_enforce"
            or type(run.get("metrics")) is not dict
            or type(run.get("tool_trajectory")) is not list
            or "error" not in run
        ):
            raise SonnetPilotBlocked("D run has incompatible identity")
        error = run["error"]
        if error is not None:
            if type(error) is not str or not error.strip():
                raise SonnetPilotBlocked("Invalid execution error receipt")
            return "EXECUTION_ERROR_REVIEW", None, "RUN_ERROR"
        try:
            bundle = build_evidence_bundle(
                run["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS,
            )
        except (ValueError, TypeError, KeyError) as exc:
            return "INVALID_OUTPUT", None, type(exc).__name__
        evidence_hash = bundle["bundle_sha256"]
        if (run.get("json_status") != "valid_json"
            or type(run.get("raw_response")) is not str
            or not run["raw_response"].strip()
            or type(run.get("output_contract_v2")) is not dict
            or run["output_contract_v2"].get("valid") is not True):
            return "INVALID_OUTPUT", evidence_hash, "D_JSON_CONTRACT"
        return "RECORDED_COMPLETE", evidence_hash, None

    def audit_restart(self) -> dict:
        binding, _release = self._gate()
        claim = self._verify_claim()
        if claim is not None and claim["source_binding_sha256"] != binding["source_binding_sha256"]:
            raise SonnetPilotBlocked("Claim and current input/source drift")
        record = self._verify_record(claim)
        for folder, allowed in (
            (self.root / "claims", {self.claim_path.name}),
            (self.root / "records", {self.record_path.name}),
        ):
            if folder.exists() and (
                not folder.is_dir()
                or any(p.name not in allowed for p in folder.iterdir())
            ):
                raise SonnetPilotBlocked("Foreign file in pilot ledger")
        return {
            "stage_id": STAGE_ID,
            "claim_exists": claim is not None,
            "record_exists": record is not None,
            "status": record["status"] if record is not None else None,
            "unresolved_claim": claim is not None and record is None,
            "automatic_retry_allowed": False,
            "ood_test_locked": True,
        }

    def claim_stage(self) -> dict:
        binding, _release = self._gate()
        status = self.audit_restart()
        if status["claim_exists"] or status["record_exists"]:
            raise SonnetPilotBlocked("No retry: stage already claimed")
        core = {
            "schema": VERSION + "_claim", "stage_id": STAGE_ID,
            "model_id": MODEL_ID,
            "source_binding_sha256": binding["source_binding_sha256"],
            "release_sha256": self.release_sha256,
            "attempt_number": 1,
        }
        claim = {**core, "claim_sha256": _digest(core)}
        (self.root / "claims").mkdir(parents=True, exist_ok=True, mode=0o700)
        _write_once(self.claim_path, claim)
        return {"stage_id": STAGE_ID, "claim_sha256": claim["claim_sha256"],
                "status": "CLAIM_WITHOUT_ARTIFACT", "automatic_retry": False}

    def record_stage(self, *, diagnostic_run: dict) -> dict:
        binding, _release = self._gate()
        self.audit_restart()
        claim = self._verify_claim(required=True)
        if self._verify_record(claim) is not None:
            raise SonnetPilotBlocked("Create-only record already exists")
        if claim["source_binding_sha256"] != binding["source_binding_sha256"]:
            raise SonnetPilotBlocked("Input/source changed after claim")
        status, evidence_sha, issue = self._classify(diagnostic_run)
        core = {
            "schema": VERSION + "_record", "stage_id": STAGE_ID,
            "model_id": MODEL_ID, "status": status,
            "claim_sha256": claim["claim_sha256"],
            "source_binding_sha256": binding["source_binding_sha256"],
            "diagnostic_run": diagnostic_run,
            "evidence_bundle_sha256": evidence_sha,
            "provenance_issue": issue,
        }
        record = {**core, "record_sha256": _digest(core)}
        (self.root / "records").mkdir(parents=True, exist_ok=True, mode=0o700)
        _write_once(self.record_path, record)
        # Readback canonico obbligatorio, nessun claim "complete" prima.
        reread = self._verify_record(claim)
        if reread is None or reread["record_sha256"] != record["record_sha256"]:
            raise SonnetPilotBlocked("Readback digest mismatch after write")
        return {
            "stage_id": STAGE_ID, "status": status,
            "record_sha256": record["record_sha256"],
            "evidence_bundle_sha256": evidence_sha,
            "automatic_retry": False,
            "ood_test_locked": True,
        }
