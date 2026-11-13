"""Bozza RQ2-V2: verifica OFFLINE di identita' e destinazioni disgiunte.

NON e' un registro, non legge Market/GT, non crea cartelle, claim o record,
non apre file e NON consente API, nuove release o sblocco di test OOD.
Il protocollo V2 e' un CANDIDATO: nessuna coorte e' preregistrata qui.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

DRAFT_PROTOCOL = "rq2_knowledge_transfer_provenance_v2_draft"
DRAFT_STATUS = "DRAFT_NOT_EXECUTABLE"
ROOT_RELATIVE = Path("data/rq2_v2_provenance")
CLAIMS_RELATIVE = ROOT_RELATIVE / "stage_claims_v1"
ARTIFACTS_RELATIVE = ROOT_RELATIVE / "stage_artifacts_v1"
V1_ROOT_RELATIVE = Path("data/rq2")

# Questi nomi sono SOLO il set candidato gia' noto dalla V1.
# Non sono un'autorizzazione a rieseguire i 72 stage reali o testare OOD.
_DISCOVERY = frozenset((
    "cloudbed-1_q032", "cloudbed-1_q050",
    "cloudbed-2_q026", "cloudbed-2_q045",
))
_TEST_LOCKED = frozenset((
    "cloudbed-1_q014", "cloudbed-1_q021", "cloudbed-1_q030",
    "cloudbed-1_q059", "cloudbed-2_q014", "cloudbed-2_q021",
    "cloudbed-2_q040", "cloudbed-2_q041", "cloudbed-2_q058",
    "cloudbed-2_q076", "cloudbed-2_q077",
))
_MODELS = frozenset(("gemini", "sonnet", "haiku"))
_HARNESSES = frozenset(("A1", "A1_8R"))
_STAGES = frozenset(("D", "C", "K"))


class RQ2V2IsolationError(ValueError):
    """Stadio/namespace non approvabile in un controllo solo di lettura."""


def _reject_symlinks(root: Path) -> None:
    # Non fare resolve(): nessuna normalizzazione di symlink o di '..'.
    for candidate in (
        root, root / "data", root / ROOT_RELATIVE,
        root / CLAIMS_RELATIVE, root / ARTIFACTS_RELATIVE,
    ):
        if candidate.is_symlink():
            raise RQ2V2IsolationError("Symbolic link in candidate V2 path")


def preview_v2_destination(*, data_dir: Path, stage_id: str) -> dict:
    """Calcola percorsi V2 solo se l'identita' e' discovery; nessuna scrittura.

    Non verifica i sorgenti GT-free: serve un release gate distinto prima
    di ogni registrazione effettiva o chiamata a provider.
    """
    if type(stage_id) is not str:
        raise RQ2V2IsolationError("Stage ID must be an exact string")
    parts = stage_id.split(":")
    if (
        len(parts) != 5 or parts[0] != DRAFT_PROTOCOL
        or parts[1] not in _DISCOVERY
        or parts[2] not in _MODELS
        or parts[3] not in _HARNESSES
        or parts[4] not in _STAGES
    ):
        raise RQ2V2IsolationError("Unplanned or test-locked V2 stage")

    if not isinstance(data_dir, Path) or not data_dir.is_absolute():
        raise RQ2V2IsolationError("Absolute pathlib.Path data_dir required")
    if ".." in data_dir.parts:
        raise RQ2V2IsolationError("Traversal forbidden in data_dir")
    _reject_symlinks(data_dir)

    case_id, model, harness, stage = parts[1:]
    # Il basename e' derivato dall'intero ID: nessun path fornito dall'LLM.
    digest = hashlib.sha256(stage_id.encode("utf-8")).hexdigest()
    claim = data_dir / CLAIMS_RELATIVE / ("V2_CLAIM_" + digest + ".json")
    record = data_dir / ARTIFACTS_RELATIVE / ("V2_STAGE_" + digest + ".json")
    old_root = data_dir / V1_ROOT_RELATIVE
    if old_root in claim.parents or old_root in record.parents:
        raise RQ2V2IsolationError("Candidate V2 overlaps frozen V1")

    return {
        "protocol": DRAFT_PROTOCOL,
        "status": DRAFT_STATUS,
        "case_id": case_id,
        "model": model,
        "harness": harness,
        "stage": stage,
        "stage_id": stage_id,
        "claim_path_preview": str(claim),
        "artifact_path_preview": str(record),
        "namespace": str(data_dir / ROOT_RELATIVE),
        "can_write": False,
        "can_execute_api": False,
        "can_execute_test": False,
        "scientific_release_frozen": False,
        "data_files_written": 0,
        "provider_api_calls": 0,
    }
