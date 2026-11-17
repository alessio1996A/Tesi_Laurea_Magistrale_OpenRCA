"""G4D: guardia READ-ONLY del FUTURO ledger scientifico RQ2-V2.

Questa funzione non e' un ledger operativo, non firma release, non crea
claim, non scrive e non avvia provider. Le uniche fonti dati ammesse dal
controllo sono split/manifest GT-free verificati dalla preview G4A.
Qualunque mismatch di SHA/HEAD/status/root/namespace produce STOP.

Il namespace e' distinto da RQ1, RQ2 V1, dal pilot Sonnet V2 e
dal journal sintetico. La creazione di una release richiedera'
un'implementazione distinta, espressamente autorizzata e testata.

Contenuto
---------
- costanti: cartella (namespace) dei futuri dati scientifici, file della release, cartelle dei
  claim e dei record, e l'elenco dei percorsi storici che NON vanno toccati;
- `UnifiedScientificLedgerBlocked`: errore "stop, condizioni non dimostrate" (usato anche dal
  ledger scientifico `rq2_v2_unified_scientific_ledger`);
- `_strict_absolute`: accetta solo cartelle assolute, senza `..` e senza link;
- `_repository_commit`: HEAD di git e stato "pulito/sporco" del checkout;
- `_check_namespace`: verifica che il futuro namespace sia ancora libero e che i percorsi storici
  non siano link (senza leggerli);
- `preview_scientific_ledger_gate`: il controllo completo, in sola lettura.
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
# Cartella dei futuri dati scientifici e i suoi tre percorsi (relativi alla radice dei dati):
# il file della release, le richieste di esecuzione ("claims") e i risultati ("records").
NAMESPACE = Path("data/rq2_v2_unified_scientific_v1")
RELEASE_FILE = NAMESPACE / "release_v1.json"
CLAIMS = NAMESPACE / "claims"
RECORDS = NAMESPACE / "records"
# Forme ammesse: hash di commit git (SHA-1, 40 caratteri) e SHA-256 (64 caratteri).
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
# Percorsi degli esperimenti precedenti: qui si verifica solo che non siano link simbolici,
# senza mai leggerli o modificarli.
HISTORICAL = (
    Path("data/rq2"),
    Path("data/rq2_v2_provenance"),
    Path("data/rq2_v2_unified_synthetic_v0"),
    Path("data/results"),
)


class UnifiedScientificLedgerBlocked(RuntimeError):
    """Stop: le condizioni di una futura release non sono dimostrate."""


def _strict_absolute(root: Path, label: str) -> Path:
    """Restituisce `root` solo se e' un `Path` assoluto, senza `..`, non un link e una cartella.

    `label` e' il nome da mostrare nel messaggio d'errore ("data root", "repository root").
    """
    if (
        not isinstance(root, Path)
        or not root.is_absolute()
        or ".." in root.parts
        or root.is_symlink()
        or not root.is_dir()
    ):
        raise UnifiedScientificLedgerBlocked("Unsafe/missing " + label)
    return root


def _repository_commit(repo: Path) -> tuple[str, str]:
    """Restituisce `(HEAD, stato)` del checkout git in `repo`.

    HEAD e' l'hash di 40 caratteri del commit corrente; lo stato e' l'output di
    `git status --porcelain` (stringa vuota = checkout pulito, nessun file modificato o nuovo).
    Solleva `UnifiedScientificLedgerBlocked` se non e' un checkout git, se git non risponde
    entro 10 secondi o se HEAD non ha la forma di un hash.
    """
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
    """Verifica che il futuro namespace scientifico sia libero e restituisce i suoi percorsi.

    Passi: 1) nessun percorso storico (ne' `data`) e' un link simbolico; 2) `data`, se esiste,
    e' una cartella; 3) namespace, file della release, claim e record NON devono ancora esistere.
    """
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
    # Il futuro namespace deve essere ancora vuoto: nessuna release gia' creata.
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

    Argomenti (per nome): `data_dir` (radice dei dati), `repo_dir` (radice del repository) e
    `expected_commit` (hash git atteso). Restituisce il riepilogo "preflight superato ma nessuna
    release", con hash del piano, del blueprint e dei file sorgente.

    Passi: 1) commit atteso ben formato; 2) cartelle sicure; 3) HEAD uguale al commit atteso e
    checkout pulito; 4) namespace libero; 5) preview delle sorgenti e blueprint; 6) preview e
    blueprint devono dichiarare "nessuna API, nessuna release" e avere hash coerenti;
    7) si assembla il riepilogo.
    """
    # 1. Il commit atteso arriva dall'esterno e deve avere la forma di un hash git.
    if type(expected_commit) is not str or not _SHA1.fullmatch(expected_commit):
        raise UnifiedScientificLedgerBlocked("External pinned commit required")
    # 2. Cartelle sicure.
    data = _strict_absolute(data_dir, "data root")
    repo = _strict_absolute(repo_dir, "repository root")
    # 3. HEAD uguale al commit atteso e nessuna modifica locale.
    head, status = _repository_commit(repo)
    if status or head != expected_commit:
        raise UnifiedScientificLedgerBlocked(
            "Git HEAD mismatch or dirty checkout: STOP"
        )
    # 4. Namespace dei dati ancora libero.
    namespace = _check_namespace(data)
    # 5. Preview delle sorgenti (G4A) e blueprint (G4B), entrambi senza autorizzazione API.
    source = preview_unified_source_bound(
        data_dir=data, src_root=repo / "src",
    )
    blueprint = build_unified_release_blueprint(
        source_preview=source,
    )
    # 6. Coerenza: nulla e' eseguibile ne' congelato, 180 stage, hash del blueprint ben formato
    # e uguale a quello del piano della preview.
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
        # Il blueprint non ha `model_ids` al livello alto: gli identificativi dei modelli
        # stanno dentro `entries`.
        or blueprint.get("model_ids") is not None
    ):
        raise UnifiedScientificLedgerBlocked(
            "Unfrozen source/blueprint identity mismatch"
        )
    # 7. Riepilogo: l'hash dei file sorgente e' lo SHA-256 del loro dizionario in forma canonica.
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
