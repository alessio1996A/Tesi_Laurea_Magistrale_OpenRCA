"""Piano di discovery RQ2 V3 GT-free, successore del V2; PRE-RELEASE, NESSUNA API/CLAIM.

Le uniche modifiche di infrastruttura previste rispetto a RQ2 V2 sono l'estrazione esatta del
testo finale, neutra rispetto al provider, per ENTRAMBI gli esecutori D e per C/K, piu' una
provenienza del testo verificabile. Budget del grafo D, prompt C/K, ID dei modelli, coorte e
harness restano identici. L'integrazione dell'estrazione in D e lo schema di provenienza NON
sono ancora implementati; nessuna release e' autorizzata. Nessun risultato D/C/K della V2 puo'
essere importato o riproposto di nascosto sotto un ID di stage V3.

Questo modulo costruisce soltanto le identita' e un piano deterministico. NON legge dataset
sorgente, file di release, ground truth/Market ne' alcun record storico. Non scrive su
filesystem e non usa SDK o dispatcher di provider.

Contenuto
---------
- costanti: versione, stato, namespace e file di release proposti, stage D/C/K;
- `RQ2V3PlanBlocked`: errore "identita' o invarianti del successore cambiate";
- `_canonical`, `_sha`: JSON e hash canonici;
- `_v3_stage_id`: converte un ID di stage V2 nel corrispondente ID V3;
- `build_offline_v3_discovery_plan`: ricostruisce il piano V2, lo verifica e ne ricava le 180
  righe V3 (4 casi x 3 modelli x 5 harness x 3 stage).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from evaluation.rq2_v2_unified_discovery_plan import (
    VERSION as V2_PROTOCOL,
    DISCOVERY, TEST, MODELS, HARNESSES, ENGINES,
    MAX_TOOL_ROUNDS, MAX_VERIFICATION_CHECKS, RECURSION_LIMIT,
    build_offline_discovery_plan,
)
from evaluation.rq2_v2_ck_text_extraction_candidate import POLICY as CK_POLICY

VERSION = "rq2_v3_unified_equal_ck_extraction_discovery_v0"
# Stato dichiarato: bozza GT-free, nessuna release, nessuna API.
STATUS = "V3_GT_FREE_DRAFT_NO_RELEASE_NO_API"
# Cartella proposta per i dati scientifici V3 e file della release (qui solo proposti).
NAMESPACE = Path("data/rq2_v3_unified_scientific_v1")
RELEASE_FILE = NAMESPACE / "release_v1.json"
# Ordine degli stage per ogni braccio: D (diagnosi), poi C (cause), poi K (regola candidata).
STAGES = ("D", "C", "K")
# Nome dello schema dei metadati di estrazione del testo C/K.
CK_PROVENANCE_SCHEMA = "rq2_v3_ck_text_extraction_meta_v0"


class RQ2V3PlanBlocked(ValueError):
    """Blocco se le identita' o le invarianti del discovery successore cambiano."""


def _canonical(data: object) -> bytes:
    """Forma canonica di `data` in byte UTF-8 (JSON con chiavi ordinate, senza spazi, NaN vietato)."""
    return json.dumps(
        data, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _sha(value: object) -> str:
    """SHA-256 (esadecimale) della forma canonica di `value`."""
    return hashlib.sha256(_canonical(value)).hexdigest()


def _v3_stage_id(v2_id: str) -> str:
    """Converte un ID di stage V2 nel corrispondente ID V3 (cambia solo il prefisso del protocollo).

    Solleva `RQ2V3PlanBlocked` se l'ID non e' una stringa che comincia col protocollo V2.
    """
    if type(v2_id) is not str or not v2_id.startswith(V2_PROTOCOL + ":"):
        raise RQ2V3PlanBlocked("Unexpected original V2 stage ID")
    return VERSION + v2_id[len(V2_PROTOCOL):]


def build_offline_v3_discovery_plan() -> dict:
    """Crea un piano unico di 4 casi x 3 modelli x 5 harness x 3 stage.

    Restituisce il piano V3 (dizionario) con le 180 righe `entries`, i parametri invariati
    rispetto alla V2 e le dichiarazioni "nessuna API, nessuna release", piu' `preview_sha256`.

    Passi: 1) ricostruisce il piano V2 e verifica coorte, modelli e harness; 2) controlla gli
    hash del piano V2 (non deve essere stato alterato); 3) per ogni riga V2 controlla
    identita' del braccio e dipendenze D->C->K e crea la riga V3 con ID V3 e stato "bloccato";
    4) verifica 180 ID distinti e dipendenze sempre precedenti nell'ordine; 5) confronta ogni
    riga V3 con la sua V2 (stessi braccio, modello, stage; ID diverso, nessun riferimento
    rimasto alla V2); 6) assembla il piano e ne calcola l'hash.
    """
    # 1. Piano V2 di partenza e invarianti di coorte, modelli e harness.
    v2 = build_offline_discovery_plan()
    entries = v2.get("entries")
    if (
        v2.get("protocol") != V2_PROTOCOL
        or v2.get("logical_stages") != 180
        or type(entries) is not list
        or len(entries) != 180
        or len(DISCOVERY) != 4
        or len(TEST) != 11
        or set(DISCOVERY) & set(TEST)
        or tuple(MODELS) != ("gemini", "sonnet", "haiku")
        or tuple(HARNESSES) != (
            "A0", "A1", "A1_8R", "A1_8R_Planning", "A1_PAVE"
        )
        or tuple(ENGINES) != tuple(HARNESSES)
        or V2_PROTOCOL == VERSION
    ):
        raise RQ2V3PlanBlocked("Baseline cohort/model/harness drift")

    # 2. Gli hash dichiarati dal piano V2 devono corrispondere al suo contenuto.
    if (
        v2.get("entries_sha256") != _sha(entries)
        or v2.get("preview_sha256") != _sha({
            key: value for key, value in v2.items() if key != "preview_sha256"
        })
    ):
        raise RQ2V3PlanBlocked("V2 preview or entries SHA drift")

    # 3. Una riga V3 per ogni riga V2.
    rows = []
    for old in entries:
        if type(old) is not dict or old.get("stage") not in STAGES:
            raise RQ2V3PlanBlocked("Malformed baseline entry")
        if (
            old.get("case_id") not in DISCOVERY
            or old.get("logical_model") not in MODELS
            or old.get("harness") not in HARNESSES
            or old.get("model_id") != v2["model_ids"].get(old["logical_model"])
            or old.get("d_engine") != ENGINES.get(old["harness"])
        ):
            raise RQ2V3PlanBlocked("Baseline arm identity drift")
        # Dipendenze attese: D non ne ha, C dipende da D, K dipende da C.
        prefix = (
            f"{V2_PROTOCOL}:{old['case_id']}:"
            f"{old['logical_model']}:{old['harness']}"
        )
        expected_deps = (
            [] if old["stage"] == "D" else
            [prefix + ":D"] if old["stage"] == "C" else [prefix + ":C"]
        )
        if old["stage_id"] != prefix + ":" + old["stage"] or (
            old.get("depends_on") != expected_deps
        ):
            raise RQ2V3PlanBlocked("Baseline D/C/K dependency drift")
        row = {
            "stage_id": _v3_stage_id(old["stage_id"]),
            "case_id": old["case_id"],
            "logical_model": old["logical_model"],
            "model_id": old["model_id"],
            "model_provider": old["model_provider"],
            "harness": old["harness"],
            "stage": old["stage"],
            "depends_on": [
                _v3_stage_id(parent) for parent in old["depends_on"]
            ],
            "d_engine": old["d_engine"],
            "execution_status": "BLOCKED_NO_V3_RELEASE",
        }
        rows.append(row)

    # 4. 180 ID distinti e ogni dipendenza compare PRIMA della riga che la richiede.
    ids = [r["stage_id"] for r in rows]
    positions = {stage_id: i for i, stage_id in enumerate(ids)}
    if len(rows) != 180 or len(positions) != 180 or any(
        dep not in positions or positions[dep] >= idx
        for idx, r in enumerate(rows) for dep in r["depends_on"]
    ):
        raise RQ2V3PlanBlocked("Invalid ordering, duplicates, or dependency")
    # 5. Il braccio di analisi non deve essere cambiato e nessun ID V2 deve essere rimasto.
    for old, new in zip(entries, rows):
        if (
            new["case_id"] != old["case_id"]
            or new["harness"] != old["harness"]
            or new["logical_model"] != old["logical_model"]
            or new["model_id"] != old["model_id"]
            or new["model_provider"] != old["model_provider"]
            or new["d_engine"] != old["d_engine"]
            or new["stage"] != old["stage"]
            or new["stage_id"] == old["stage_id"]
            or any(dep.startswith(V2_PROTOCOL + ":") for dep in new["depends_on"])
        ):
            raise RQ2V3PlanBlocked("Changed analysis arm or V2 identity leakage")

    # 6. Piano finale: tutto cio' che e' "eseguibile" o "scritto" resta False o zero.
    core = {
        "protocol": VERSION,
        "status": STATUS,
        "base_v2_protocol": V2_PROTOCOL,
        "base_v2_plan_sha256": v2["preview_sha256"],
        "base_v2_entries_sha256": v2["entries_sha256"],
        "mode": "GT_FREE_PLAN_ONLY",
        "scientific_namespace_proposed": NAMESPACE.as_posix(),
        "release_relative_path_proposed": RELEASE_FILE.as_posix(),
        "discovery_cases": list(DISCOVERY),
        "ood_test_cases_locked": list(TEST),
        "models": list(MODELS),
        "model_ids": dict(v2["model_ids"]),
        "harnesses": list(HARNESSES),
        "stage_counts": {"D": 60, "C": 60, "K": 60},
        "logical_stages": 180,
        "max_tool_rounds_D": MAX_TOOL_ROUNDS,
        "max_verification_checks_planning": MAX_VERIFICATION_CHECKS,
        "max_recursion_depth_D": RECURSION_LIMIT,
        "d_output_contract": "v2_enforce",
        "c_and_k_prompts": "rq2_probe_adapter_v0_unchanged",
        "uniform_final_text_extraction_policy_candidate": CK_POLICY,
        "d_final_output_extraction_integration_verified": False,
        "d_final_output_provenance_schema_frozen": False,
        "ck_text_extraction_policy": CK_POLICY,
        "ck_text_provenance_schema": CK_PROVENANCE_SCHEMA,
        "reuse_v2_d_outputs": False,
        "reuse_v2_c_or_k_outputs": False,
        "comparison_policy": (
            "paired by the same four discovery cases; model/harness "
            "results within one V3 release only; report provider errors, "
            "JSON validity, abstentions, K blocked, cost and causality separately"
        ),
        "analysis_unit": "incident_case_within_model_and_harness",
        "release_frozen": False,
        "source_commit_pinned": False,
        "model_api_calls": 0,
        "can_execute_api": False,
        "can_write_scientific_claims": False,
        "can_run_ood_test": False,
        "ground_truth_read": False,
        "telemetry_read": False,
        "historical_results_read": False,
        "files_written": False,
        "entries_sha256": _sha(rows),
        "entries": rows,
    }
    return {**core, "preview_sha256": _sha(core)}
