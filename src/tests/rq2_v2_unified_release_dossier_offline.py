"""Dossier di PRERELEASE RQ2-V2: SOLO dati, nessuna release o API.

Questa utility di revisione non e' un dispatcher, non crea un manifest G4E
e non ha privilegi scientifici. Consuma la preview G4A e il blueprint G4B
gia' ottenuti da sorgenti reali e controllati dal chiamante. Anche un PASS
significa esclusivamente: IDENTITA' DELLA PROPOSTA VERIFICABILE OFFLINE.

Non legge Market.zip, ground truth, OOD test, credenziali, file o rete.
Non crea, autorizza, firma o scrive una release; nessun hash qui emesso
puo' essere usato come SHA di release o consenso a spendere.
"""
from __future__ import annotations

import hashlib
import json
import re

from evaluation.rq2_model_factory import (
    TIMEOUT_SECONDS, GOOGLE_HTTP_ATTEMPTS, ANTHROPIC_MAX_RETRIES,
)
from evaluation.rq2_provider_policy_source_audit import EXPECTED_COLAB_VERSIONS
from evaluation.rq2_v2_unified_discovery_plan import (
    DISCOVERY, HARNESSES, MODELS, TEST, build_offline_discovery_plan,
)
from evaluation.rq2_v2_unified_release_blueprint import (
    build_unified_release_blueprint,
)
from evaluation.rq2_v2_unified_release_preflight import SOURCE_PATHS
from evaluation.rq2_v2_unified_scientific_release_contract import (
    RELEASE_SCHEMA, RELEASE_NAMESPACE,
)

VERSION = "rq2_v2_release_dossier_offline_v0"
STATUS = "PRERELEASE_DOSSIER_REVIEW_ONLY_NO_AUTHORITY"
SHA1 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
K_RUBRIC_PATH = "evaluation/rq2_v2_k_quality_rubric.py"


class ReleaseDossierBlocked(ValueError):
    """Drift della preregistrazione o provenienza inadeguata: STOP."""


def _canonical(obj: object) -> bytes:
    return json.dumps(
        obj, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _source_hashes_valid(src: dict) -> bool:
    hashes = src.get("source_files_sha256")
    return (
        type(hashes) is dict
        and len(SOURCE_PATHS) == 30
        and len(set(SOURCE_PATHS)) == 30
        and set(hashes) == set(SOURCE_PATHS)
        and all(type(value) is str and SHA256.fullmatch(value)
                for value in hashes.values())
        and src.get("source_file_count") == 30
    )


def build_prerelease_dossier(
    *, source_preview: dict,
    blueprint: dict,
    expected_commit: str,
    runtime_versions: dict,
) -> dict:
    """Prepara metadati scientifici senza inserire alcuna approvazione.

    La validita' reale di split, manifest, sorgenti e runtime viene
    stabilita dal preflight G4A eseguito su Colab, NON da questa funzione
    che riceve strutture in memoria. I fixture sintetici dei test
    non diventano mai prova di un source preflight reale.
    """
    if type(expected_commit) is not str or not SHA1.fullmatch(expected_commit):
        raise ReleaseDossierBlocked("External exact Git commit pin required")
    if type(source_preview) is not dict or type(blueprint) is not dict:
        raise ReleaseDossierBlocked("Source and blueprint are required")
    if not _source_hashes_valid(source_preview):
        raise ReleaseDossierBlocked("30 source hashes including K rubric required")
    if (
        source_preview.get("status") != "OFFLINE_SOURCE_BOUND_NO_RELEASE_NO_API"
        or source_preview.get("frozen_rq1_source_identity_verified") is not True
        or source_preview.get("gt_free_source_verified") is not True
        or source_preview.get("ground_truth_read") is not False
        or source_preview.get("can_execute_api") is not False
        or source_preview.get("can_run_ood_test") is not False
        or source_preview.get("model_requests_sent") != 0
        or source_preview.get("claims_written") != 0
        or source_preview.get("data_files_written") is not False
        or source_preview.get("scientific_release_frozen") is not False
        or source_preview.get("approved_api_budget_exists") is not False
        or source_preview.get("source_commit_pinned_for_release") is not False
        or source_preview.get("ood_test_cases_locked") != len(TEST)
        or source_preview.get("logical_stages") != 180
    ):
        raise ReleaseDossierBlocked("Untrusted or accidentally authorized source")

    if type(runtime_versions) is not dict or any(
        runtime_versions.get(name) != version
        for name, version in EXPECTED_COLAB_VERSIONS.items()
    ):
        raise ReleaseDossierBlocked("Pinned Colab SDK versions not established")
    if set(runtime_versions) != set(EXPECTED_COLAB_VERSIONS):
        raise ReleaseDossierBlocked("Unexpected or missing SDK distribution")
    if (
        TIMEOUT_SECONDS != 300.0
        or GOOGLE_HTTP_ATTEMPTS != 1
        or ANTHROPIC_MAX_RETRIES != 0
    ):
        raise ReleaseDossierBlocked("RQ2-only transport policy drift")

    # Non fidarsi di un blueprint passato arbitrariamente dal chiamante.
    regenerated = build_unified_release_blueprint(
        source_preview=source_preview
    )
    if _canonical(blueprint) != _canonical(regenerated):
        raise ReleaseDossierBlocked("Draft blueprint mismatch")
    plan = build_offline_discovery_plan()
    stages = plan["entries"]
    first = stages[0]
    if (
        first["case_id"] != DISCOVERY[0] or first["stage"] != "D"
        or first["logical_model"] != "gemini" or first["harness"] != "A0"
        or len(DISCOVERY) != 4 or len(TEST) != 11
        or len(HARNESSES) != 5 or len(MODELS) != 3
        or len(stages) != 180
        or regenerated["logical_stage_count"] != 180
        or regenerated["can_execute_api"] is not False
        or regenerated["can_write_scientific_claims"] is not False
        or regenerated["can_run_ood_test"] is not False
    ):
        raise ReleaseDossierBlocked("Pilot or campaign identity drift")
    hashes = source_preview["source_files_sha256"]

    return {
        "version": VERSION,
        "status": STATUS,
        "source_commit_proposed": expected_commit,
        "source_file_count": 30,
        "source_inventory_sha256": hashlib.sha256(_canonical(hashes)).hexdigest(),
        "k_rubric_sha256": hashes[K_RUBRIC_PATH],
        "source_plan_sha256": plan["preview_sha256"],
        "blueprint_sha256": regenerated["blueprint_sha256"],
        "split_sha256": source_preview["split_sha256"],
        "manifest_sha256": source_preview["manifest_sha256"],
        "C_system_prompt_sha256": source_preview["C_system_prompt_sha256"],
        "K_system_prompt_sha256": source_preview["K_system_prompt_sha256"],
        "runtime_versions": dict(sorted(runtime_versions.items())),
        "proposed_release_schema_only": RELEASE_SCHEMA,
        "proposed_namespace_only": RELEASE_NAMESPACE,
        "candidate_pilot_stage_id": first["stage_id"],
        "logical_stages_planned": 180,
        "discovery_count": 4,
        "ood_test_count_locked": 11,
        "transport_proven_only_for_tested_sync_scenarios": [
            "synthetic_http_503",
            "synthetic_http_429",
            "loopback_read_timeout_0p3s",
        ],
        "full_stage_timeout_guaranteed": False,
        "max_http_attempts_guaranteed": None,
        "usd_hard_cap_guaranteed": False,
        "external_release_approval_present": False,
        "approved_budget_present": False,
        "per_stage_paid_api_approval_present": False,
        "source_commit_frozen_for_live_release": False,
        "release_manifest_created": False,
        "release_sha256": None,
        "scientific_claims_written": 0,
        "real_provider_requests_sent": 0,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "files_written": False,
    }
