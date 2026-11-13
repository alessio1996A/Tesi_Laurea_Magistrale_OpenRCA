"""RQ2 V2 Sonnet — preflight READ-ONLY per K, da D e C ContentBlocks V2.

Non esistono API, claim, scritture, scorer, GT o accessi ai test OOD.
Questa unità non è un runner: genera solo un pacchetto K non eseguibile,
riferito al record C valido e frozen; non corregge né sostituisce la C V1.

Il caso q050 e' allocato a DISCOVERY dalla partizione GT-free congelata.
La confidenza LOW della C non autorizza a inventare soglie. K potrà restituire
insufficient_evidence qualora le osservazioni non bastino.
"""
from __future__ import annotations

from pathlib import Path

import evaluation.rq2_v2_sonnet_c_contentblocks_v2 as parent_c
from evaluation.rq2_dryrun_plan import DISCOVERY
from evaluation.rq2_evidence_bundle import build_evidence_bundle, evidence_ids
from evaluation.rq2_output_contracts import validate_cause_probe
from evaluation.rq2_probe_adapter import prepare_candidate_rule, prepare_cause_probe
from evaluation.rq2_stage_binding import ALLOWED_TOOLS
from evaluation.rq2_v2_sonnet_pilot_ledger import (
    _canonical, _digest, _hash, _read_json, _safe_path, source_binding,
)

VERSION = "rq2_v2_sonnet_k_sourcebound_preview_v1"
PROTOCOL = "rq2_v2_sonnet_q050_k_contentblocks_v2_v1"
CASE_ID = "cloudbed-1_q050"
STAGE_ID = PROTOCOL + ":" + CASE_ID + ":sonnet:A1:K"

# Un eventuale runner futuro utilizzerà un namespace separato.
# PREVIEW_K non lo crea, non vi scrive e non legge OOD.
K_ROOT = Path("data/rq2_v2_provenance/sonnet_q050_k_contentblocks_v2_v1")
K_RELEASE = K_ROOT / "release_v1.json"
K_CLAIM = K_ROOT / "claims" / "candidate_rule_claim_v1.json"
K_RECORD = K_ROOT / "records" / "candidate_rule_record_v1.json"

C_SOURCE_COMMIT = "73927d747430bf79e36cb65ecdcba632d9561f9d"
C_RELEASE_SHA256 = "7053f040afa04cdf9e63d91722e1ac7594e2da3965502a83234a9fa21c75e849"
C_BINDING_SHA256 = "344ce9ba435176e5ab48f1fabe139e470d739933b344ef0bfc35dcc404e2ede8"
C_CLAIM_SHA256 = "1c87f64f92ff7487b647cfd7beb430cda26a5e6d34db98caf1021e843d980591"
C_RECORD_SHA256 = "8e853074e69f1718ae1a8ebda3f67954bc495fa0d14651e0dfa8a3f03744a49b"
INVALID_C_RECORD_SHA256 = "39364800134f3713302a6f314822930b501a4300af6d62a12f7ce376a93f0579"

PARENT_D_RECORD_SHA256 = parent_c.PARENT_RECORD_SHA256
PARENT_D_BUNDLE_SHA256 = parent_c.PARENT_BUNDLE_SHA256
PARENT_C_PACKAGE_SHA256 = parent_c.C_PACKAGE_SHA256
PARENT_C_SYSTEM_SHA256 = parent_c.C_SYSTEM_SHA256
MODEL_ID = parent_c.MODEL_ID


class KPreviewBlocked(ValueError):
    """Arresto read-only per dipendenze, SHA o partizione non validi."""


def _validated_c_parent(data_dir: Path, *, c_package: dict) -> dict:
    """Controlla release, claim e record C SENZA invocare il gate su HEAD C.

    La HEAD corrente è necessariamente la nuova HEAD K, non la HEAD C.
    Il ledger della C viene usato solo per validare record e formato già
    congelati; non si può usare il suo audit_restart su una HEAD successiva.
    """
    release = _read_json(data_dir / parent_c.C_RELEASE)
    if (_hash(_canonical(release)) != C_RELEASE_SHA256
            or release.get("code_commit") != C_SOURCE_COMMIT
            or release.get("c_binding_sha256") != C_BINDING_SHA256
            or release.get("parent_record_sha256") != PARENT_D_RECORD_SHA256
            or release.get("c_package_sha256") != PARENT_C_PACKAGE_SHA256
            or release.get("content_extraction_policy") != "text_blocks_only_v1"
            or release.get("model_id") != MODEL_ID
            or release.get("stage") != "C"
            or release.get("harness") != "A1"):
        raise KPreviewBlocked("Frozen C release mismatch")

    reader = parent_c.CauseLedger(
        data_dir=data_dir, repo_dir=data_dir,
        release_sha256=C_RELEASE_SHA256,
    )
    claim = reader._verify_claim()
    if claim is None or claim["claim_sha256"] != C_CLAIM_SHA256:
        raise KPreviewBlocked("Frozen C claim mismatch")
    if claim["c_binding_sha256"] != C_BINDING_SHA256:
        raise KPreviewBlocked("Frozen C binding mismatch")
    record = reader._verify_record(claim, c_package)
    if (record is None or record["record_sha256"] != C_RECORD_SHA256
            or record["status"] != "RECORDED_COMPLETE"
            or record["c_decision"] != "diagnosis"
            or record["issue"] is not None
            or record["parent_record_sha256"] != PARENT_D_RECORD_SHA256
            or record["c_package_sha256"] != PARENT_C_PACKAGE_SHA256
            or record["response_content_kind"] != "list"
            or record["text_blocks_observed"] != 1
            or record["nontext_blocks_observed"] != 1
            or record["observed_model_requests"] != 1):
        raise KPreviewBlocked("Frozen C record mismatch")
    return record


def _assert_unchanged_invalid_c(data_dir: Path) -> None:
    """Preserva la C iniziale INVALID_OUTPUT nel suo proprio namespace."""
    old_path = data_dir / "data/rq2_v2_provenance/sonnet_q050_c_v1/records/cause_record_v1.json"
    old = _read_json(old_path)
    if (old.get("record_sha256") != INVALID_C_RECORD_SHA256
            or old["record_sha256"] != _digest({
                k: v for k, v in old.items() if k != "record_sha256"
            })
            or old.get("status") != "INVALID_OUTPUT"
            or old.get("raw_response") != ""):
        raise KPreviewBlocked("Previous C INVALID_OUTPUT changed")


def preview_k(*, data_dir: Path, repo_dir: Path) -> tuple[dict, dict]:
    """Ritorna (source-bound binding, pacchetto K) SOLO in memoria.

    Non fornisce il permesso di eseguire K. Nessun accesso a ground truth,
    dati test, metriche di scorer, modelli, strumenti di telemetria, ecc.
    """
    data_dir = _safe_path(Path(data_dir))
    repo_dir = _safe_path(Path(repo_dir))
    if (not data_dir.is_dir() or not repo_dir.is_dir()
            or data_dir.resolve() == repo_dir.resolve()):
        raise KPreviewBlocked("Separate and existing data/repository roots required")
    if CASE_ID not in DISCOVERY:
        raise KPreviewBlocked("K case is outside frozen discovery allocation")
    base = source_binding(data_dir=data_dir, repo_dir=repo_dir)
    diagnostic_run = parent_c._read_parent(data_dir)
    instruction = parent_c._original_instruction(data_dir, base)
    bundle = build_evidence_bundle(
        diagnostic_run["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS,
    )
    if (bundle["bundle_sha256"] != PARENT_D_BUNDLE_SHA256
            or bundle["observations_count"] != 8
            or bundle["truncated_count"] != 3
            or len(evidence_ids(bundle)) != 8):
        raise KPreviewBlocked("Parent D evidence drift")

    c_package = prepare_cause_probe(
        original_instruction=instruction, diagnostic_run=diagnostic_run,
        allowed_tool_names=ALLOWED_TOOLS,
    )
    if (c_package["package_sha256"] != PARENT_C_PACKAGE_SHA256
            or c_package["system_prompt_sha256"] != PARENT_C_SYSTEM_SHA256
            or c_package["bundle_sha256"] != PARENT_D_BUNDLE_SHA256
            or c_package["model_api_calls"] != 0
            or c_package["ready_for_api"] is not False):
        raise KPreviewBlocked("Original C prompt package drift")
    parent_record = _validated_c_parent(data_dir, c_package=c_package)
    _assert_unchanged_invalid_c(data_dir)

    # Usare il parser reale anche prima di passare il testo all'adapter K.
    cause = validate_cause_probe(
        parent_record["raw_response"], allowed_evidence_ids=evidence_ids(bundle),
    )
    if cause["decision"] != "diagnosis":
        raise KPreviewBlocked("Frozen C decision changed")
    package = prepare_candidate_rule(
        original_instruction=instruction,
        diagnostic_run=diagnostic_run,
        cause_raw_json=parent_record["raw_response"],
        phase="discovery",
        allowed_tool_names=ALLOWED_TOOLS,
    )
    if (package.get("stage") != "K_candidate_rule"
            or package.get("bundle_sha256") != PARENT_D_BUNDLE_SHA256
            or package.get("model_api_calls") != 0
            or package.get("ready_for_api") is not False
            or type(package.get("messages")) is not list
            or len(package["messages"]) != 2
            or any(type(m.get("content")) is not str for m in package["messages"])):
        raise KPreviewBlocked("K package is not a blocked GT-free preview")

    identity = {
        "protocol": PROTOCOL,
        "stage_id": STAGE_ID,
        "code_commit": base["code_commit"],
        "source_binding_sha256": base["source_binding_sha256"],
        "parent_d_record_sha256": PARENT_D_RECORD_SHA256,
        "parent_d_bundle_sha256": PARENT_D_BUNDLE_SHA256,
        "parent_c_source_commit": C_SOURCE_COMMIT,
        "parent_c_release_sha256": C_RELEASE_SHA256,
        "parent_c_binding_sha256": C_BINDING_SHA256,
        "parent_c_claim_sha256": C_CLAIM_SHA256,
        "parent_c_record_sha256": C_RECORD_SHA256,
        "k_package_sha256": package["package_sha256"],
        "k_system_prompt_sha256": package["system_prompt_sha256"],
        "model_id": MODEL_ID,
        "phase": "discovery",
        "ood_test_locked": True,
        "k_execution_authorized": False,
    }
    return {**identity, "k_binding_sha256": _digest(identity)}, package


def require_fresh_k_namespace(*, data_dir: Path) -> None:
    """Gate solo per prima release; MAI cancella un namespace preesistente."""
    data_dir = _safe_path(Path(data_dir))
    for path in (K_ROOT, K_RELEASE, K_CLAIM, K_RECORD):
        full = _safe_path(data_dir / path)
        if full.exists() or full.is_symlink():
            raise KPreviewBlocked("K namespace already exists; no overwrite or retry")
