"""Piano successore RQ2-V4 solo OFFLINE: nuova identita, nessuna API.

Non importa risultati della V3. La sua unica novita metodologica
e' usare la validazione D task-aware coerente con run_experiment.
5 harness x 3 modelli x 4 incidenti discovery x (D/C/K) = 180 stage.
Gli undici casi OOD restano sigillati; nessuna chiamata ai provider.

Contenuto
---------
- costanti: versione, stato, namespace e file di release proposti, stage D/C/K;
- `V4DiscoveryPlanBlocked`: errore "piano V4 non ricavabile dal V3 o OOD non separati";
- `_sha`: SHA-256 canonico di un oggetto JSON;
- `_id`: converte un ID di stage V3 nell'ID V4 (cambia solo il prefisso del protocollo);
- `build_offline_v4_discovery_plan`: ricava dal piano V3 le 180 righe V4, invariate tranne
  gli ID e lo stato, e le verifica.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from evaluation.rq2_v3_unified_gtfree_discovery_plan import (
    VERSION as V3_PROTOCOL,
    build_offline_v3_discovery_plan,
)
from evaluation.rq2_v4_d_task_aware_contract import VERSION as D_CONTRACT

VERSION = "rq2_v4_task_aware_d_discovery_v0"
# Stato dichiarato: bozza task-aware, nessuna release, nessuna API.
STATUS = "V4_TASK_AWARE_DRAFT_NO_RELEASE_NO_API"
# Cartella proposta per i dati scientifici V4 e file della release (qui solo proposti).
NAMESPACE = Path("data/rq2_v4_task_aware_scientific_v1")
RELEASE_FILE = NAMESPACE / "release_v1.json"
# Ordine degli stage per ogni braccio: D (diagnosi), C (cause), K (regola candidata).
STAGES = ("D", "C", "K")


class V4DiscoveryPlanBlocked(ValueError):
    """V4 plan non deducibile dal V3 predefinito, o OOD non separati."""


def _sha(value: object) -> str:
    """SHA-256 (esadecimale) della forma canonica JSON di `value` (chiavi ordinate, NaN vietato)."""
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _id(old: str) -> str:
    """Converte un ID di stage V3 nel corrispondente ID V4.

    Solleva `V4DiscoveryPlanBlocked` se `old` non e' una stringa che comincia col protocollo V3.
    """
    if type(old) is not str or not old.startswith(V3_PROTOCOL + ":"):
        raise V4DiscoveryPlanBlocked("Unknown V3 parent stage identity")
    return VERSION + old[len(V3_PROTOCOL):]


def build_offline_v4_discovery_plan() -> dict:
    """Piano nominale V4, senza dipendenze da release o file sperimentali.

    Restituisce il piano V4 (dizionario) con le 180 righe `entries` e le dichiarazioni
    "nessuna API, nessun claim, nessun risultato riusato", piu' `preview_sha256`.

    Passi: 1) ricostruisce il piano V3 e ne verifica conteggi e divieti (180 stage, 4 casi di
    discovery, 11 OOD sigillati, nessuna API); 2) per ogni riga V3 crea la riga V4: stessi
    dati, nuovo ID di stage e di dipendenze, stato "bloccato"; 3) controlla ID distinti, OOD
    separati dalla discovery, nessun ID V3 rimasto, dipendenze sempre precedenti e braccio
    di analisi invariato; 4) assembla il piano e ne calcola l'hash.
    """
    # 1. Piano V3 di partenza e sue invarianti.
    v3 = build_offline_v3_discovery_plan()
    if (
        v3.get("protocol") != V3_PROTOCOL
        or len(v3.get("entries", [])) != 180
        or len(v3.get("discovery_cases", [])) != 4
        or len(v3.get("ood_test_cases_locked", [])) != 11
        or v3.get("stage_counts") != {"D": 60, "C": 60, "K": 60}
        or v3.get("can_execute_api") is not False
        or v3.get("can_run_ood_test") is not False
    ):
        raise V4DiscoveryPlanBlocked("V3 source plan drift")
    # 2. Una riga V4 per ogni riga V3: solo ID, dipendenze e stato cambiano.
    rows = []
    for old in v3["entries"]:
        if old.get("stage") not in STAGES:
            raise V4DiscoveryPlanBlocked("Unknown source stage")
        row = {
            **old,
            "stage_id": _id(old["stage_id"]),
            "depends_on": [_id(parent) for parent in old["depends_on"]],
            "execution_status": "BLOCKED_NO_V4_RELEASE",
        }
        rows.append(row)
    # 3. Coerenza del piano V4: ID distinti, OOD fuori dalla discovery, nessun ID V3 riusato,
    # ogni dipendenza compare prima della riga che la richiede, braccio di analisi invariato.
    ids = [r["stage_id"] for r in rows]
    if (
        len(set(ids)) != 180
        or set(v3["discovery_cases"]) & set(v3["ood_test_cases_locked"])
        or set(ids) & {r["stage_id"] for r in v3["entries"]}
        or any(
            parent not in ids[:i]
            for i, row in enumerate(rows) for parent in row["depends_on"]
        )
        or any(
            row[key] != old[key]
            for row, old in zip(rows, v3["entries"])
            for key in (
                "case_id", "logical_model", "model_id",
                "model_provider", "harness", "stage", "d_engine",
            )
        )
    ):
        raise V4DiscoveryPlanBlocked("Analysis arm or dependency changed")
    # 4. Piano finale: tutto cio' che e' "eseguibile" o "scritto" resta False o zero.
    core = {
        "protocol": VERSION,
        "status": STATUS,
        "source_protocol": V3_PROTOCOL,
        "source_plan_sha256": v3["preview_sha256"],
        "mode": "OFFLINE_DRAFT_ONLY",
        "scientific_namespace": NAMESPACE.as_posix(),
        "release_file": RELEASE_FILE.as_posix(),
        "D_validation_contract": D_CONTRACT,
        "D_output_mode_unchanged": "v2_enforce",
        "C_and_K_prompts_unchanged": True,
        "model_ids": dict(v3["model_ids"]),
        "models": list(v3["models"]),
        "harnesses": list(v3["harnesses"]),
        "discovery_cases": list(v3["discovery_cases"]),
        "ood_test_cases_locked": list(v3["ood_test_cases_locked"]),
        "stage_counts": {"D": 60, "C": 60, "K": 60},
        "logical_stages": 180,
        "reuse_v3_d_outputs": False,
        "reuse_v3_c_or_k_outputs": False,
        "reuse_v2_d_or_ck_outputs": False,
        "ground_truth_read": False,
        "provider_requests_sent": 0,
        "files_written": False,
        "can_create_claim": False,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "source_release_frozen": False,
        "entries_sha256": _sha(rows),
        "entries": rows,
    }
    return {**core, "preview_sha256": _sha(core)}
