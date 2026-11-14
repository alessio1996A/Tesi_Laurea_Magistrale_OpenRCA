"""G4D: guardia READ-ONLY del FUTURO ledger scientifico RQ2-V2.

Questa funzione non e' un ledger operativo, non firma release, non crea
claim, non scrive e non avvia provider. Le uniche fonti dati ammesse dal
controllo sono split/manifest GT-free verificati dalla preview G4A.
Qualunque mismatch di SHA/HEAD/status/root/namespace produce STOP.

Il namespace e' distinto da RQ1, RQ2 V1, dal pilot Sonnet V2 e
dal journal sintetico. La creazione di una release richiedera'
un'implementazione distinta, espressamente autorizzata e testata.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from evaluation.rq2_v2_unified_release_preflight import (
    preview_unified_source_bound,
)
from evaluation.rq2_v2_unified_release_blueprint import (
    build_unified_release_blueprint,
)

VERSION = "rq2_v2_unified_scientific_ledger_preflight_v0"
NAMESPACE = Path("data/rq2_v2_unified_scientific_v1")
RELEASE_FILE = NAMESPACE / "release_v1.json"
CLAIMS = NAMESPACE / "claims"
RECORDS = NAMESPACE / "records"
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
HISTORICAL = (
    Path("data/rq2"),
    Path("data/rq2_v2_provenance"),
    Path("data/rq2_v2_unified_synthetic_v0"),
    Path("data/results"),
)


class UnifiedScientificLedgerBlocked(RuntimeError):
    """Stop: le condizioni di una futura release non sono dimostrate."""


def _strict_absolute(root: Path, label: str) -> Path:
    if (
        type(root) is not Path
        or not root.is_absolute()
        or ".." in root.parts
        or root.is_symlink()
        or not root.is_dir()
    ):
        raise UnifiedScientificLedgerBlocked("Unsafe/missing " + label)
    return root


def _repository_commit(repo: Path) -> tuple[str, str]:
    git = repo / ".git"
    if git.is_symlink() or not git.exists():
        raise UnifiedScientificLedgerBlocked("Not a Git checkout")
    try:
        head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=normal"],
            check=True, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError, AttributeError) as exc:
        raise UnifiedScientificLedgerBlocked(
            "Git source identity cannot be proven"
        ) from exc
    if not _SHA1.fullmatch(head):
        raise UnifiedScientificLedgerBlocked("Invalid HEAD")
    return head, status


def _check_namespace(data_dir: Path) -> dict:
    # NON leggere o modificare i risultati degli esperimenti precedenti.
    # Verificare soltanto l'assenza di symlink nei path riservati.
    data = data_dir / "data"
    for path in (data, *[data_dir / rel for rel in HISTORICAL]):
        if path.is_symlink():
            raise UnifiedScientificLedgerBlocked(
                "Symlink in historical or data namespace"
            )
    if data.exists() and not data.is_dir():
        raise UnifiedScientificLedgerBlocked("Bad data directory")
    for path in (
        data_dir / NAMESPACE, data_dir / RELEASE_FILE,
        data_dir / CLAIMS, data_dir / RECORDS,
    ):
        if path.is_symlink() or path.exists():
            raise UnifiedScientificLedgerBlocked(
                "Future scientific namespace already occupied"
            )
    return {
        "namespace": NAMESPACE.as_posix(),
        "release_relative_path": RELEASE_FILE.as_posix(),
        "claims_relative_path": CLAIMS.as_posix(),
        "records_relative_path": RECORDS.as_posix(),
        "new_namespace_absent": True,
        "historical_paths_touched": False,
    }


def preview_scientific_ledger_gate(
    *, data_dir: Path, repo_dir: Path, expected_commit: str,
) -> dict:
    """Preflight READ-ONLY; mai invocare un modello o creare un claim.

    L'expected_commit e' un valore fissato esternamente e non desunto da
    HEAD (per evitare un falso 'freeze' del codice corrente).
    """
    if type(expected_commit) is not str or not _SHA1.fullmatch(expected_commit):
        raise UnifiedScientificLedgerBlocked("External pinned commit required")
    data = _strict_absolute(data_dir, "data root")
    repo = _strict_absolute(repo_dir, "repository root")
    head, status = _repository_commit(repo)
    if status or head != expected_commit:
        raise UnifiedScientificLedgerBlocked(
            "Git HEAD mismatch or dirty checkout: STOP"
        )
    namespace = _check_namespace(data)
    source = preview_unified_source_bound(
        data_dir=data, src_root=repo / "src",
    )
    blueprint = build_unified_release_blueprint(
        source_preview=source,
    )
    if (
        type(source) is not dict
        or source.get("can_execute_api") is not False
        or source.get("can_run_ood_test") is not False
        or source.get("scientific_release_frozen") is not False
        or source.get("ground_truth_read") is not False
        or source.get("gt_free_source_verified") is not True
        or type(blueprint) is not dict
        or blueprint.get("status") != "DRAFT_ALL_EXECUTION_BLOCKED_NO_API"
        or blueprint.get("logical_stage_count") != 180
        or blueprint.get("can_execute_api") is not False
        or blueprint.get("can_write_scientific_claims") is not False
        or blueprint.get("can_run_ood_test") is not False
        or blueprint.get("scientific_release_frozen") is not False
        or type(blueprint.get("blueprint_sha256")) is not str
        or not _SHA256.fullmatch(blueprint["blueprint_sha256"])
        or blueprint.get("source_plan_sha256") != source.get("plan_preview_sha256")
        or blueprint.get("model_ids") is not None  # Schema stays in entries.
    ):
        raise UnifiedScientificLedgerBlocked(
            "Unfrozen source/blueprint identity mismatch"
        )
    result = {
        "version": VERSION,
        "status": "LEDGER_NAMESPACE_PREFLIGHT_PASS_BUT_NO_RELEASE",
        "source_commit": head,
        "source_plan_sha256": source["plan_preview_sha256"],
        "blueprint_sha256": blueprint["blueprint_sha256"],
        "source_file_hashes_sha256": hashlib.sha256(
            json.dumps(
                source["source_files_sha256"],
                sort_keys=True, ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "split_sha256": source["split_sha256"],
        "manifest_sha256": source["manifest_sha256"],
        "discovery_case_count": 4,
        "ood_test_cases_locked": 11,
        "logical_stages": 180,
        "logical_model_invocation_bound_candidate": (
            blueprint["max_graph_invocations_if_all_stages_reached_candidate"]
        ),
        **namespace,
        "files_written": False,
        "source_verified": True,
        "scientific_release_signed": False,
        "api_budget_approved": False,
        "production_ledger_implemented": False,
        "production_dispatcher_implemented": False,
        "can_create_scientific_claim": False,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "model_requests_sent": 0,
    }
    return result
