"""RQ2 V2 — una sola K Sonnet reale, da D e C congelate e verificate.

Esecutore indipendente dal vecchio C INVALID_OUTPUT; non ripete D/C.
NO_API fino a release K canonica e conferma esplicita. Crea claim prima
dell'invocazione e record write-once, anche se la risposta e' invalida.
Il JSON di K contiene solamente una PROPOSTA: nessun detector e' eseguito.
Nessun accesso a scorer, ground truth o casi OOD test.
"""
from __future__ import annotations

import re
from decimal import Decimal
from importlib import metadata
from pathlib import Path

from evaluation.rq2_model_factory import (
    assert_exact_runtime_snapshot, crea_modello_rq2,
)
from evaluation.rq2_output_contracts import ContractError, validate_candidate_rule
from evaluation.rq2_provider_policy_source_audit import EXPECTED_COLAB_VERSIONS
from evaluation.rq2_v2_sonnet_c_contentblocks_v2 import (
    INPUT_PRICE, OUTPUT_PRICE, extract_visible_response,
)
from evaluation.rq2_v2_sonnet_k_sourcebound_preview import (
    K_CLAIM, K_RECORD, K_RELEASE, K_ROOT, MODEL_ID,
    PARENT_D_RECORD_SHA256, PARENT_D_BUNDLE_SHA256, C_RECORD_SHA256,
    STAGE_ID, PROTOCOL, preview_k,
)
from evaluation.rq2_v2_sonnet_pilot_ledger import (
    _canonical, _digest, _hash, _read_json, _safe_path, _write_once,
)

VERSION = "rq2_v2_sonnet_k_single_live_v1"
EXPECTED_K_RELEASE_SHA256 = None  # La release della preview non esiste.
CONTENT_EXTRACTION_POLICY = "text_blocks_only_v1"
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")


class KStageBlocked(ValueError):
    """Fermare lo stage senza tentare una nuova API."""


def read_k_release(*, data_dir: Path, binding: dict,
                   release_sha256: str | None) -> dict:
    """Accetta solo la release K distinta e pienamente vincolata agli hash."""
    pin = release_sha256 if release_sha256 is not None else EXPECTED_K_RELEASE_SHA256
    if type(pin) is not str or not SHA_RE.fullmatch(pin):
        raise KStageBlocked("NO_API: K release SHA absent")
    release = _read_json(_safe_path(Path(data_dir) / K_RELEASE))
    if _hash(_canonical(release)) != pin:
        raise KStageBlocked("K release SHA mismatch")
    expected = {
        "schema", "protocol", "stage_id", "code_commit", "k_binding_sha256",
        "parent_d_record_sha256", "parent_c_record_sha256",
        "k_package_sha256", "provider", "model_id", "stage", "harness",
        "max_llm_requests", "max_retries", "max_tokens", "timeout_seconds",
        "approved_usd_limit", "authorization", "api_budget_approved",
        "runtime_versions", "ood_test_locked", "content_extraction_policy",
    }
    if (set(release) != expected
            or release["schema"] != VERSION + "_release"
            or release["protocol"] != PROTOCOL
            or release["stage_id"] != STAGE_ID
            or release["code_commit"] != binding["code_commit"]
            or release["k_binding_sha256"] != binding["k_binding_sha256"]
            or release["parent_d_record_sha256"] != PARENT_D_RECORD_SHA256
            or release["parent_c_record_sha256"] != C_RECORD_SHA256
            or release["k_package_sha256"] != binding["k_package_sha256"]
            or release["provider"] != "anthropic"
            or release["model_id"] != MODEL_ID
            or release["stage"] != "K"
            or release["harness"] != "A1"
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
            or release["authorization"] != "approved_for_one_k"
            or release["api_budget_approved"] is not True
            or release["runtime_versions"] != EXPECTED_COLAB_VERSIONS
            or release["ood_test_locked"] is not True):
        raise KStageBlocked("Unapproved K release")
    return release


class KLedger:
    """K create-only, distinta da D e C. Non esegue proposte di regole."""

    def __init__(self, *, data_dir: Path, repo_dir: Path,
                 release_sha256: str | None = None):
        self.data_dir = _safe_path(Path(data_dir))
        self.repo_dir = _safe_path(Path(repo_dir))
        self.release_sha256 = release_sha256
        self.root = self.data_dir / K_ROOT
        self.claim_path = self.data_dir / K_CLAIM
        self.record_path = self.data_dir / K_RECORD
        for path in (
            self.data_dir / "data", self.data_dir / "data/rq2_v2_provenance",
            self.root, self.root / "claims", self.root / "records",
            self.data_dir / K_RELEASE, self.claim_path, self.record_path,
        ):
            _safe_path(path)

    def _gate(self):
        binding, package = preview_k(
            data_dir=self.data_dir, repo_dir=self.repo_dir,
        )
        if (binding["stage_id"] != STAGE_ID
                or binding["parent_d_record_sha256"] != PARENT_D_RECORD_SHA256
                or binding["parent_c_record_sha256"] != C_RECORD_SHA256
                or binding["parent_d_bundle_sha256"] != PARENT_D_BUNDLE_SHA256
                or binding["phase"] != "discovery"
                or binding["ood_test_locked"] is not True
                or binding["k_execution_authorized"] is not False
                or package["ready_for_api"] is not False
                or package["model_api_calls"] != 0):
            raise KStageBlocked("K source/package preflight drift")
        release = read_k_release(
            data_dir=self.data_dir, binding=binding,
            release_sha256=self.release_sha256,
        )
        return binding, package, release

    def _verify_claim(self):
        if not self.claim_path.exists():
            return None
        claim = _read_json(self.claim_path)
        required = {
            "schema", "stage_id", "release_sha256", "k_binding_sha256",
            "parent_d_record_sha256", "parent_c_record_sha256",
            "attempt_number", "claim_sha256",
        }
        if (set(claim) != required
                or claim["schema"] != VERSION + "_claim"
                or claim["stage_id"] != STAGE_ID
                or claim["release_sha256"] != self.release_sha256
                or claim["parent_d_record_sha256"] != PARENT_D_RECORD_SHA256
                or claim["parent_c_record_sha256"] != C_RECORD_SHA256
                or type(claim["attempt_number"]) is not int
                or claim["attempt_number"] != 1
                or claim["claim_sha256"] != _digest({
                    k: v for k, v in claim.items() if k != "claim_sha256"
                })):
            raise KStageBlocked("K claim corrupt")
        return claim

    @staticmethod
    def _classify(rec: dict, package: dict):
        """Status di trasporto separato dalla decisione della regola K."""
        if (type(rec.get("observed_model_requests")) is not int
                or rec["observed_model_requests"] != 1
                or type(rec.get("raw_response")) not in (str, type(None))
                or type(rec.get("token_usage_complete")) is not bool
                or (rec.get("execution_error") is not None
                    and (type(rec["execution_error"]) is not str
                         or not rec["execution_error"].strip()))):
            raise KStageBlocked("Malformed K provider receipt")
        if rec["token_usage_complete"]:
            tokens = (rec.get("input_tokens"), rec.get("output_tokens"))
            if any(type(n) is not int or n < 0 for n in tokens):
                raise KStageBlocked("Malformed K token usage")
            cost = str((
                Decimal(tokens[0]) * INPUT_PRICE
                + Decimal(tokens[1]) * OUTPUT_PRICE
            ) / Decimal(1_000_000))
            if rec.get("cost_estimate_usd_not_invoice") != cost:
                raise KStageBlocked("Inconsistent K cost estimate")
        elif (rec.get("input_tokens") is not None
              or rec.get("output_tokens") is not None
              or rec.get("cost_estimate_usd_not_invoice") is not None):
            raise KStageBlocked("Incomplete K usage must be explicit")

        if (rec.get("response_content_kind") not in
                ("str", "list", "unsupported", "not_observed")
                or type(rec.get("text_blocks_observed")) is not int
                or type(rec.get("nontext_blocks_observed")) is not int
                or rec["text_blocks_observed"] < 0
                or rec["nontext_blocks_observed"] < 0
                or (rec["response_content_kind"] != "list"
                    and rec["nontext_blocks_observed"] != 0)):
            raise KStageBlocked("Malformed K block extraction receipt")

        if rec["execution_error"] is not None:
            return "EXECUTION_ERROR_REVIEW", None, "PROVIDER_ERROR"
        if rec["token_usage_complete"] is not True:
            return "EXECUTION_ERROR_REVIEW", None, "MISSING_USAGE"
        try:
            rule = validate_candidate_rule(
                rec["raw_response"],
                allowed_evidence_ids={f"E{i:03d}" for i in range(1, 9)},
            )
        except (ContractError, TypeError, ValueError):
            return "INVALID_OUTPUT", None, "K_JSON_CONTRACT"
        return "RECORDED_COMPLETE", rule["status"], None

    def _verify_record(self, claim, package):
        if not self.record_path.exists():
            return None
        rec = _read_json(self.record_path)
        required = {
            "schema", "stage_id", "claim_sha256", "k_binding_sha256",
            "parent_d_record_sha256", "parent_c_record_sha256",
            "k_package_sha256", "raw_response", "execution_error",
            "token_usage_complete", "input_tokens", "output_tokens",
            "observed_model_requests", "cost_estimate_usd_not_invoice",
            "response_content_kind", "text_blocks_observed",
            "nontext_blocks_observed", "status", "k_decision",
            "issue", "record_sha256",
        }
        if (set(rec) != required
                or claim is None
                or rec["schema"] != VERSION + "_record"
                or rec["stage_id"] != STAGE_ID
                or rec["claim_sha256"] != claim["claim_sha256"]
                or rec["k_binding_sha256"] != claim["k_binding_sha256"]
                or rec["parent_d_record_sha256"] != PARENT_D_RECORD_SHA256
                or rec["parent_c_record_sha256"] != C_RECORD_SHA256
                or rec["k_package_sha256"] != package["package_sha256"]
                or rec["record_sha256"] != _digest({
                    k: v for k, v in rec.items() if k != "record_sha256"
                })):
            raise KStageBlocked("K record corrupt")
        if (rec["status"], rec["k_decision"], rec["issue"]) != self._classify(rec, package):
            raise KStageBlocked("K classification drift")
        return rec

    def audit_restart(self):
        binding, package, _release = self._gate()
        claim = self._verify_claim()
        if claim is not None and claim["k_binding_sha256"] != binding["k_binding_sha256"]:
            raise KStageBlocked("K source binding changed after claim")
        rec = self._verify_record(claim, package)
        for folder, allowed in (
            (self.root / "claims", {self.claim_path.name}),
            (self.root / "records", {self.record_path.name}),
        ):
            if folder.exists() and (
                not folder.is_dir()
                or any(path.name not in allowed for path in folder.iterdir())
            ):
                raise KStageBlocked("Unrecognized K artifact")
        return {
            "claim_exists": claim is not None,
            "record_exists": rec is not None,
            "unresolved_claim": claim is not None and rec is None,
            "status": rec["status"] if rec is not None else None,
            "k_decision": rec["k_decision"] if rec is not None else None,
            "automatic_retry_allowed": False,
        }

    def claim_stage(self):
        binding, package, release = self._gate()
        audit = self.audit_restart()
        if audit["claim_exists"] or audit["record_exists"]:
            raise KStageBlocked("No retry: K stage already claimed")
        core = {
            "schema": VERSION + "_claim",
            "stage_id": STAGE_ID,
            "release_sha256": self.release_sha256,
            "k_binding_sha256": binding["k_binding_sha256"],
            "parent_d_record_sha256": PARENT_D_RECORD_SHA256,
            "parent_c_record_sha256": C_RECORD_SHA256,
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
            raise KStageBlocked("K claim absent or record already exists")
        if claim["k_binding_sha256"] != binding["k_binding_sha256"]:
            raise KStageBlocked("K source changed after claim")
        core = {
            "schema": VERSION + "_record",
            "stage_id": STAGE_ID,
            "claim_sha256": claim["claim_sha256"],
            "k_binding_sha256": binding["k_binding_sha256"],
            "parent_d_record_sha256": PARENT_D_RECORD_SHA256,
            "parent_c_record_sha256": C_RECORD_SHA256,
            "k_package_sha256": package["package_sha256"],
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
        core.update({"status": status, "k_decision": decision, "issue": issue})
        rec = {**core, "record_sha256": _digest(core)}
        (self.root / "records").mkdir(parents=True, exist_ok=True, mode=0o700)
        _write_once(self.record_path, rec)
        if self._verify_record(claim, package) is None:
            raise KStageBlocked("K record readback failed")
        return {
            "status": status, "decision": decision,
            "issue": issue, "record_sha256": rec["record_sha256"],
        }


def run_one_k(*, data_dir: Path, repo_dir: Path,
              release_sha256: str | None = None, confirm_paid_api: bool = False):
    """Una chiamata K solo se preregistrata, nessun retry o pseudocodice."""
    if confirm_paid_api is not True:
        raise KStageBlocked("Explicit K API confirmation required")
    ledger = KLedger(
        data_dir=data_dir, repo_dir=repo_dir,
        release_sha256=release_sha256,
    )
    binding, package, release = ledger._gate()
    assert_exact_runtime_snapshot()
    for name, version in release["runtime_versions"].items():
        if metadata.version(name) != version:
            raise KStageBlocked("Runtime drift")
    if ledger.audit_restart()["claim_exists"]:
        raise KStageBlocked("No retry: K claim already exists")
    # La costruzione del client non esegue HTTP. Claim precede invoke.
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
        # Mai archiviare o stampare il testo dell'errore provider.
        error = type(exc).__name__
    receipt = ledger.record_stage(
        raw_response=raw, execution_error=error,
        token_usage_complete=usage_complete, input_tokens=inputs,
        output_tokens=outputs, cost_estimate=cost,
        response_content_kind=kind, text_blocks_observed=text_count,
        nontext_blocks_observed=other_count,
    )
    audit = ledger.audit_restart()
    if audit["unresolved_claim"] or audit["status"] != receipt["status"]:
        raise KStageBlocked("K record final readback failed")
    return {
        "stage_id": STAGE_ID,
        "status": receipt["status"],
        "decision": receipt["decision"],
        "issue": receipt["issue"],
        "claim_sha256": claim["claim_sha256"],
        "record_sha256": receipt["record_sha256"],
        "parent_d_record_sha256": PARENT_D_RECORD_SHA256,
        "parent_c_record_sha256": C_RECORD_SHA256,
        "k_package_sha256": package["package_sha256"],
        "model_requests": 1,
        "input_tokens": inputs,
        "output_tokens": outputs,
        "usage_complete": usage_complete,
        "estimated_cost_usd_not_invoice": cost,
        "response_content_kind": kind,
        "text_blocks_observed": text_count,
        "nontext_blocks_observed": other_count,
        "rule_executed": False,
        "ood_test_locked": True,
        "automatic_retry": False,
    }
