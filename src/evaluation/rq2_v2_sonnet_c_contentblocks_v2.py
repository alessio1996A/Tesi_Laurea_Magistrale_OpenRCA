"""RQ2 V2 — C Content Blocks V2: protocollo tecnico successore sul discovery q050.

Questa unità NON usa la release D per autorizzare C. La D viene soltanto
riletta e validata contro gli SHA osservati. K, OOD e V1 restano bloccati.
Nessuna API se manca una nuova release C canonica e la conferma esplicita.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from decimal import Decimal

from agent.graph_engine import testo_messaggio
from importlib import metadata
from pathlib import Path

from evaluation.rq2_evidence_bundle import build_evidence_bundle, evidence_ids
from evaluation.rq2_model_factory import (
    assert_exact_runtime_snapshot, crea_modello_rq2,
)
from evaluation.rq2_output_contracts import ContractError, validate_cause_probe
from evaluation.rq2_probe_adapter import prepare_cause_probe
from evaluation.rq2_provider_policy_source_audit import EXPECTED_COLAB_VERSIONS
from evaluation.rq2_stage_binding import ALLOWED_TOOLS
from evaluation.rq2_v2_sonnet_pilot_ledger import (
    CLAIM_RELATIVE as D_CLAIM_RELATIVE,
    MODEL_ID, RECORD_RELATIVE as D_RECORD_RELATIVE,
    RELEASE_RELATIVE as D_RELEASE_RELATIVE,
    RQ2V2SonnetPilotLedger,
    _canonical, _digest, _hash, _read_json, _safe_path, _write_once,
    source_binding,
)

VERSION = "rq2_v2_sonnet_c_contentblocks_v2"
PROTOCOL = "rq2_v2_sonnet_q050_c_contentblocks_v2"
STAGE_ID = PROTOCOL + ":cloudbed-1_q050:sonnet:A1:C"
C_ROOT = Path("data/rq2_v2_provenance/sonnet_q050_c_contentblocks_v2")
C_RELEASE = C_ROOT / "release_v1.json"
C_CLAIM = C_ROOT / "claims" / "cause_claim_v1.json"
C_RECORD = C_ROOT / "records" / "cause_record_v1.json"
EXPECTED_C_RELEASE_SHA256 = None  # Nessuna API prima della nuova release V2.
CONTENT_EXTRACTION_POLICY = "text_blocks_only_v1"

PARENT_CODE_COMMIT = "bf2b0a0a67977a65c79d47ada4b07e825eaf8dff"
PARENT_SOURCE_SHA256 = "05c1c12072432e6ee7332802142dd709a6a9adfbf71845615274bbd927240f0b"
PARENT_RELEASE_SHA256 = "c07e0aaa19b6cc1826e532c7da89e856c68e73975be84f572a727c09c7580813"
PARENT_CLAIM_SHA256 = "ec058cb6f061f9c342b4a54a7aa037b1d8de7242ba6b91c17cf22976a66dc29e"
PARENT_RECORD_SHA256 = "521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009"
PARENT_BUNDLE_SHA256 = "f63f1f0fd744497acc92814d8aabf80fb30cb08d8e5244ec62501d29052154d6"
C_PACKAGE_SHA256 = "49422ee1f91909514acc3cdf5868aa5c4e73990392804fe7b1fa8dec950e333f"
C_SYSTEM_SHA256 = "81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42"
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
INPUT_PRICE = Decimal("2.00")
OUTPUT_PRICE = Decimal("10.00")


class CauseStageBlocked(ValueError):
    """Arresto prima dell'API o durante il gate di integrità."""


def _read_parent(data_dir: Path) -> dict:
    """Verifica SHA reali e stato della D senza invocare il suo vecchio gate HEAD.

    Il commit nuovo C deve essere distinto da quello D. Gli hash e la
    precedente release D sono verificati direttamente, senza riscriverli.
    """
    release = _read_json(data_dir / D_RELEASE_RELATIVE)
    if (_hash(_canonical(release)) != PARENT_RELEASE_SHA256
            or release.get("code_commit") != PARENT_CODE_COMMIT
            or release.get("source_binding_sha256") != PARENT_SOURCE_SHA256
            or release.get("model_id") != MODEL_ID
            or release.get("harness") != "A1"
            or release.get("stage") != "D"):
        raise CauseStageBlocked("Parent D release mismatch")
    parent = RQ2V2SonnetPilotLedger(
        data_dir=data_dir, repo_dir=data_dir,
        release_sha256=PARENT_RELEASE_SHA256,
    )
    claim = parent._verify_claim(required=True)
    record = parent._verify_record(claim)
    if (claim["claim_sha256"] != PARENT_CLAIM_SHA256
            or claim["source_binding_sha256"] != PARENT_SOURCE_SHA256
            or record is None
            or record["record_sha256"] != PARENT_RECORD_SHA256
            or record["status"] != "RECORDED_COMPLETE"
            or record["evidence_bundle_sha256"] != PARENT_BUNDLE_SHA256):
        raise CauseStageBlocked("Parent D claim/record mismatch")
    return record["diagnostic_run"]


def _original_instruction(data_dir: Path, binding: dict) -> str:
    manifest = _safe_path(data_dir / "data/processed/benchmark_inputs_market.csv")
    with manifest.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if (not reader.fieldnames or "case_id" not in reader.fieldnames
                or "instruction" not in reader.fieldnames
                or {"reason", "scoring_points", "ground_truth"} & set(reader.fieldnames)):
            raise CauseStageBlocked("Manifest is not GT-free")
        rows = [r for r in reader if r["case_id"] == "cloudbed-1_q050"]
    if len(rows) != 1:
        raise CauseStageBlocked("Missing/duplicate discovery instruction")
    instruction = rows[0]["instruction"]
    if _hash(instruction.encode("utf-8")) != binding["instruction_sha256"]:
        raise CauseStageBlocked("Original instruction SHA drift")
    return instruction


def preview_c(*, data_dir: Path, repo_dir: Path) -> tuple[dict, dict]:
    """Sola lettura e calcolo in memoria, nessun client/claim/API."""
    data_dir, repo_dir = _safe_path(Path(data_dir)), _safe_path(Path(repo_dir))
    if not data_dir.is_dir() or not repo_dir.is_dir():
        raise CauseStageBlocked("Missing source roots")
    if data_dir.resolve() == repo_dir.resolve():
        raise CauseStageBlocked("Separate Drive data root and Git checkout required")
    base = source_binding(data_dir=data_dir, repo_dir=repo_dir)
    parent_run = _read_parent(data_dir)
    original_instruction = _original_instruction(data_dir, base)
    bundle = build_evidence_bundle(
        parent_run["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS,
    )
    if (bundle["bundle_sha256"] != PARENT_BUNDLE_SHA256
            or bundle["observations_count"] != 8
            or bundle["truncated_count"] != 3):
        raise CauseStageBlocked("Frozen D evidence differs")
    package = prepare_cause_probe(
        original_instruction=original_instruction, diagnostic_run=parent_run,
        allowed_tool_names=ALLOWED_TOOLS,
    )
    if (package["package_sha256"] != C_PACKAGE_SHA256
            or package["system_prompt_sha256"] != C_SYSTEM_SHA256
            or package["bundle_sha256"] != PARENT_BUNDLE_SHA256
            or package["model_api_calls"] != 0
            or package["ready_for_api"] is not False
            or len(evidence_ids(bundle)) != 8
            or sum(len(msg["content"]) for msg in package["messages"]) != 18084):
        raise CauseStageBlocked("Frozen cause package differs")
    identity = {
        "protocol": PROTOCOL, "stage_id": STAGE_ID,
        "code_commit": base["code_commit"],
        "source_binding_sha256": base["source_binding_sha256"],
        "parent_code_commit": PARENT_CODE_COMMIT,
        "parent_record_sha256": PARENT_RECORD_SHA256,
        "parent_release_sha256": PARENT_RELEASE_SHA256,
        "parent_bundle_sha256": PARENT_BUNDLE_SHA256,
        "c_package_sha256": C_PACKAGE_SHA256,
        "c_system_prompt_sha256": C_SYSTEM_SHA256,
        "model_id": MODEL_ID,
        "content_extraction_policy": CONTENT_EXTRACTION_POLICY,
    }
    return {**identity, "c_binding_sha256": _digest(identity)}, package


def read_c_release(*, data_dir: Path, binding: dict, release_sha256: str | None) -> dict:
    pin = release_sha256 if release_sha256 is not None else EXPECTED_C_RELEASE_SHA256
    if type(pin) is not str or not SHA_RE.fullmatch(pin):
        raise CauseStageBlocked("NO_API: C release SHA absent")
    release = _read_json(data_dir / C_RELEASE)
    if _hash(_canonical(release)) != pin:
        raise CauseStageBlocked("C release SHA mismatch")
    expected = {
        "schema", "protocol", "stage_id", "code_commit", "c_binding_sha256",
        "parent_record_sha256", "c_package_sha256", "provider", "model_id",
        "stage", "harness", "max_llm_requests", "max_retries",
        "max_tokens", "timeout_seconds", "approved_usd_limit",
        "authorization", "api_budget_approved", "runtime_versions",
        "ood_test_locked", "content_extraction_policy",
    }
    if (set(release) != expected
            or release["schema"] != VERSION + "_release"
            or release["protocol"] != PROTOCOL
            or release["stage_id"] != STAGE_ID
            or release["code_commit"] != binding["code_commit"]
            or release["c_binding_sha256"] != binding["c_binding_sha256"]
            or release["parent_record_sha256"] != PARENT_RECORD_SHA256
            or release["c_package_sha256"] != C_PACKAGE_SHA256
            or release["provider"] != "anthropic"
            or release["model_id"] != MODEL_ID
            or release["stage"] != "C" or release["harness"] != "A1"
            or release["content_extraction_policy"] != CONTENT_EXTRACTION_POLICY
            or type(release["max_llm_requests"]) is not int
            or release["max_llm_requests"] != 1
            or type(release["max_retries"]) is not int
            or release["max_retries"] != 0
            or type(release["max_tokens"]) is not int
            or release["max_tokens"] != 4096
            or type(release["timeout_seconds"]) not in (int, float)
            or release["timeout_seconds"] != 300
            or type(release["approved_usd_limit"]) not in (int, float)
            or not 0 < release["approved_usd_limit"] <= 100
            or release["authorization"] != "approved_for_one_c"
            or release["api_budget_approved"] is not True
            or release["runtime_versions"] != EXPECTED_COLAB_VERSIONS
            or release["ood_test_locked"] is not True):
        raise CauseStageBlocked("C scientific release not approved")
    return release


def extract_visible_response(content) -> tuple[str, str, int, int]:
    """Estrae il testo senza includere thinking, signature o tool-use.

    L'estrattore RQ1 e' gia' collaudato con blocchi Anthropic. Il tipo e i
    conteggi vengono registrati come diagnostica: nessun testo di reasoning.
    Risposte senza testo rimangono vuote/INVALID_OUTPUT, mai riparate.
    """
    if type(content) is str:
        return content, "str", int(bool(content)), 0
    if type(content) is list:
        if len(content) > 256:
            raise CauseStageBlocked("Unbounded Anthropic content blocks")
        text_blocks = sum(
            type(block) is str or (
                type(block) is dict
                and type(block.get("text")) is str
                and block.get("type") in (None, "text", "text_delta")
            ) for block in content
        )
        return (testo_messaggio(content, solo_testo=True), "list",
                text_blocks, len(content) - text_blocks)
    return "", "unsupported", 0, 0


class CauseLedger:
    """Nuovo ledger C ContentBlocks V2, isolato dalla C V1 invalida."""

    def __init__(self, *, data_dir: Path, repo_dir: Path, release_sha256=None):
        self.data_dir = _safe_path(Path(data_dir))
        self.repo_dir = _safe_path(Path(repo_dir))
        self.release_sha256 = release_sha256
        self.root = self.data_dir / C_ROOT
        self.claim_path = self.data_dir / C_CLAIM
        self.record_path = self.data_dir / C_RECORD
        for p in (self.data_dir / "data", self.data_dir / "data/rq2_v2_provenance",
                  self.root, self.root / "claims", self.root / "records",
                  self.data_dir / C_RELEASE, self.claim_path, self.record_path):
            _safe_path(p)

    def _gate(self):
        binding, package = preview_c(
            data_dir=self.data_dir, repo_dir=self.repo_dir,
        )
        release = read_c_release(
            data_dir=self.data_dir, binding=binding,
            release_sha256=self.release_sha256,
        )
        return binding, package, release

    def _verify_claim(self):
        if not self.claim_path.exists():
            return None
        claim = _read_json(self.claim_path)
        if (set(claim) != {"schema", "stage_id", "release_sha256",
                          "c_binding_sha256", "parent_record_sha256",
                          "attempt_number", "claim_sha256"}
                or claim["schema"] != VERSION + "_claim"
                or claim["stage_id"] != STAGE_ID
                or claim["release_sha256"] != self.release_sha256
                or claim["parent_record_sha256"] != PARENT_RECORD_SHA256
                or type(claim["attempt_number"]) is not int
                or claim["attempt_number"] != 1
                or claim["claim_sha256"] != _digest({
                    k: v for k, v in claim.items() if k != "claim_sha256"
                })):
            raise CauseStageBlocked("C claim corrupted")
        return claim

    @staticmethod
    def _classify(rec: dict, package: dict) -> tuple[str, str | None, str | None]:
        """Stato C fail-closed e contabilità controllata prima del readback."""
        if (rec.get("observed_model_requests") != 1
                or type(rec.get("raw_response")) not in (str, type(None))
                or (rec.get("execution_error") is not None
                    and (type(rec["execution_error"]) is not str
                         or not rec["execution_error"].strip()))
                or type(rec.get("token_usage_complete")) is not bool):
            raise CauseStageBlocked("Malformed C provider receipt")
        if rec["token_usage_complete"]:
            tokens = (rec.get("input_tokens"), rec.get("output_tokens"))
            if any(type(n) is not int or n < 0 for n in tokens):
                raise CauseStageBlocked("Inconsistent C token usage")
            expected_cost = str((
                Decimal(tokens[0]) * INPUT_PRICE
                + Decimal(tokens[1]) * OUTPUT_PRICE
            ) / Decimal(1_000_000))
            if rec.get("cost_estimate_usd_not_invoice") != expected_cost:
                raise CauseStageBlocked("Inconsistent C cost estimate")
        elif (rec.get("input_tokens") is not None
              or rec.get("output_tokens") is not None
              or rec.get("cost_estimate_usd_not_invoice") is not None):
            raise CauseStageBlocked("Partial C usage must be explicit")
        if (rec.get("response_content_kind") not in
                ("str", "list", "unsupported", "not_observed")
                or type(rec.get("text_blocks_observed")) is not int
                or type(rec.get("nontext_blocks_observed")) is not int
                or rec["text_blocks_observed"] < 0
                or rec["nontext_blocks_observed"] < 0
                or ((rec["response_content_kind"] != "list")
                    and rec["nontext_blocks_observed"] != 0)):
            raise CauseStageBlocked("Malformed C content block receipt")
        if rec["execution_error"] is not None:
            return "EXECUTION_ERROR_REVIEW", None, "PROVIDER_ERROR"
        if rec["token_usage_complete"] is not True:
            return "EXECUTION_ERROR_REVIEW", None, "MISSING_USAGE"
        try:
            valid = validate_cause_probe(
                rec["raw_response"], allowed_evidence_ids={
                    f"E{i:03d}" for i in range(1, 9)
                },
            )
        except (ContractError, TypeError, ValueError):
            return "INVALID_OUTPUT", None, "C_JSON_CONTRACT"
        return "RECORDED_COMPLETE", valid["decision"], None

    def _verify_record(self, claim, package):
        if not self.record_path.exists():
            return None
        rec = _read_json(self.record_path)
        fields = {
            "schema", "stage_id", "claim_sha256", "c_binding_sha256",
            "parent_record_sha256", "c_package_sha256", "raw_response",
            "execution_error", "token_usage_complete", "input_tokens",
            "output_tokens", "observed_model_requests",
            "cost_estimate_usd_not_invoice", "status", "c_decision",
            "issue", "record_sha256", "response_content_kind",
            "text_blocks_observed", "nontext_blocks_observed",
        }
        if (set(rec) != fields
                or claim is None
                or rec["schema"] != VERSION + "_record"
                or rec["stage_id"] != STAGE_ID
                or rec["claim_sha256"] != claim["claim_sha256"]
                or rec["c_binding_sha256"] != claim["c_binding_sha256"]
                or rec["parent_record_sha256"] != PARENT_RECORD_SHA256
                or rec["c_package_sha256"] != C_PACKAGE_SHA256
                or rec["record_sha256"] != _digest({
                    k: v for k, v in rec.items() if k != "record_sha256"
                })
                or type(rec["observed_model_requests"]) is not int
                or rec["observed_model_requests"] != 1):
            raise CauseStageBlocked("C record corrupt")
        if (rec["status"], rec["c_decision"], rec["issue"]) != self._classify(rec, package):
            raise CauseStageBlocked("C recorded classification drift")
        return rec

    def audit_restart(self):
        binding, package, _release = self._gate()
        claim = self._verify_claim()
        if claim is not None and claim["c_binding_sha256"] != binding["c_binding_sha256"]:
            raise CauseStageBlocked("C claim and source drift")
        rec = self._verify_record(claim, package)
        for folder, allowed in (
            (self.root / "claims", {self.claim_path.name}),
            (self.root / "records", {self.record_path.name}),
        ):
            if folder.exists() and (
                not folder.is_dir()
                or any(child.name not in allowed for child in folder.iterdir())
            ):
                raise CauseStageBlocked("Unrecognized C artifact")
        return {
            "claim_exists": claim is not None,
            "record_exists": rec is not None,
            "unresolved_claim": claim is not None and rec is None,
            "status": rec["status"] if rec is not None else None,
            "automatic_retry_allowed": False,
        }

    def claim_stage(self):
        binding, package, release = self._gate()
        audit = self.audit_restart()
        if audit["claim_exists"] or audit["record_exists"]:
            raise CauseStageBlocked("No retry: C already claimed")
        core = {
            "schema": VERSION + "_claim",
            "stage_id": STAGE_ID,
            "release_sha256": self.release_sha256,
            "c_binding_sha256": binding["c_binding_sha256"],
            "parent_record_sha256": PARENT_RECORD_SHA256,
            "attempt_number": 1,
        }
        claim = {**core, "claim_sha256": _digest(core)}
        (self.root / "claims").mkdir(parents=True, exist_ok=True, mode=0o700)
        _write_once(self.claim_path, claim)
        return claim

    def record_stage(self, *, raw_response: str | None, execution_error: str | None,
                     token_usage_complete: bool, input_tokens: int | None,
                     output_tokens: int | None, cost_estimate: str | None,
                     response_content_kind: str = "not_observed",
                     text_blocks_observed: int = 0,
                     nontext_blocks_observed: int = 0):
        binding, package, release = self._gate()
        self.audit_restart()
        claim = self._verify_claim()
        if claim is None or self.record_path.exists():
            raise CauseStageBlocked("Missing C claim or duplicate record")
        if (claim["c_binding_sha256"] != binding["c_binding_sha256"]
                or claim["parent_record_sha256"] != PARENT_RECORD_SHA256):
            raise CauseStageBlocked("C parent changed after claim")
        core = {
            "schema": VERSION + "_record",
            "stage_id": STAGE_ID,
            "claim_sha256": claim["claim_sha256"],
            "c_binding_sha256": binding["c_binding_sha256"],
            "parent_record_sha256": PARENT_RECORD_SHA256,
            "c_package_sha256": C_PACKAGE_SHA256,
            "raw_response": raw_response,
            "execution_error": execution_error,
            "token_usage_complete": token_usage_complete,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "observed_model_requests": 1,
            "cost_estimate_usd_not_invoice": cost_estimate,
            "response_content_kind": response_content_kind,
            "text_blocks_observed": text_blocks_observed,
            "nontext_blocks_observed": nontext_blocks_observed,
        }
        status, decision, issue = self._classify(core, package)
        core.update({"status": status, "c_decision": decision, "issue": issue})
        record = {**core, "record_sha256": _digest(core)}
        (self.root / "records").mkdir(parents=True, exist_ok=True, mode=0o700)
        _write_once(self.record_path, record)
        if self._verify_record(claim, package) is None:
            raise CauseStageBlocked("C record readback failed")
        return {"status": status, "decision": decision,
                "issue": issue, "record_sha256": record["record_sha256"]}


def run_one_c(*, data_dir: Path, repo_dir: Path,
              release_sha256: str | None = None,
              confirm_paid_api: bool = False) -> dict:
    """Una chiamata al provider, con risultato create-only e nessun retry."""
    if confirm_paid_api is not True:
        raise CauseStageBlocked("Explicit C API confirmation required")
    ledger = CauseLedger(
        data_dir=data_dir, repo_dir=repo_dir, release_sha256=release_sha256,
    )
    binding, package, release = ledger._gate()
    assert_exact_runtime_snapshot()
    for name, version in release["runtime_versions"].items():
        if metadata.version(name) != version:
            raise CauseStageBlocked("Runtime drift")
    if ledger.audit_restart()["claim_exists"]:
        raise CauseStageBlocked("No retry: existing C claim")
    # Factory senza richieste HTTP; lo stage sara' reclamato prima di invoke.
    model = crea_modello_rq2("anthropic", MODEL_ID)
    claim = ledger.claim_stage()
    from langchain_core.messages import HumanMessage, SystemMessage
    messages = [
        SystemMessage(content=package["messages"][0]["content"]),
        HumanMessage(content=package["messages"][1]["content"]),
    ]
    raw, error, usage_complete = None, None, False
    inputs, outputs, cost = None, None, None
    kind, text_count, other_count = "not_observed", 0, 0
    try:
        response = model.invoke(messages)
        raw, kind, text_count, other_count = extract_visible_response(
            response.content
        )
        usage = getattr(response, "usage_metadata", None)
        if (type(usage) is dict
                and type(usage.get("input_tokens")) is int
                and type(usage.get("output_tokens")) is int
                and usage["input_tokens"] >= 0 and usage["output_tokens"] >= 0):
            inputs, outputs, usage_complete = (
                usage["input_tokens"], usage["output_tokens"], True
            )
            cost = str((
                Decimal(inputs) * INPUT_PRICE
                + Decimal(outputs) * OUTPUT_PRICE
            ) / Decimal(1_000_000))
    except Exception as exc:
        # Non archiviare il testo del provider: puo' includere dati sensibili.
        error = type(exc).__name__
    receipt = ledger.record_stage(
        raw_response=raw, execution_error=error,
        token_usage_complete=usage_complete, input_tokens=inputs,
        output_tokens=outputs, cost_estimate=cost,
        response_content_kind=kind,
        text_blocks_observed=text_count,
        nontext_blocks_observed=other_count,
    )
    audit = ledger.audit_restart()
    if audit["unresolved_claim"] or audit["status"] != receipt["status"]:
        raise CauseStageBlocked("C final readback failed")
    return {
        "stage_id": STAGE_ID,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "issue": receipt["issue"],
        "claim_sha256": claim["claim_sha256"],
        "record_sha256": receipt["record_sha256"],
        "parent_record_sha256": PARENT_RECORD_SHA256,
        "c_package_sha256": C_PACKAGE_SHA256,
        "model_requests": 1,
        "input_tokens": inputs,
        "output_tokens": outputs,
        "usage_complete": usage_complete,
        "estimated_cost_usd_not_invoice": cost,
        "response_content_kind": kind,
        "text_blocks_observed": text_count,
        "nontext_blocks_observed": other_count,
        "ood_test_locked": True,
        "k_executed": False,
        "automatic_retry": False,
    }
