"""Piano OFFLINE e NON eseguibile per RQ2-V2: 5 harness x 3 modelli.

Obiettivo A: confrontare la qualita' delle proposte K, non generalizzazione.
Riutilizza la coorte discovery 4 casi della V1 come scelta storica ESPLICITA.
I precedenti output V1 e il pilot Sonnet V2 NON vengono fusi con nuove run.

La preview puo' verificare soltanto split e manifest GT-free; non legge
Market.zip, ground truth, predizioni, scorer o credenziali, non chiama provider,
non scrive e non contiene il minimo dispatcher di esecuzione.

Contenuto
---------
- costanti del piano: versione, stato, stage D/C/K, modelli, harness, budget di D, motore di D per harness;
- `_assert_code_identity`: controlla che il piano coincida con i cinque agenti del runner RQ1;
- `build_offline_discovery_plan`: genera le 180 righe (4 casi x 3 modelli x 5 harness x 3 stage);
- `preview_gt_free_sources`: collega la preview a split e manifest originali verificati su disco.

Struttura del piano: per ogni caso, modello e harness ci sono tre stage in catena,
D (diagnosi dell'agente) -> C (ipotesi di causa) -> K (regola candidata).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from agent.variant_names import VARIANTI_FINALI
from evaluation.rq2_budget_preflight import CANDIDATE_MODELS
from evaluation.rq2_dryrun_plan import (
    DISCOVERY, TEST, EXPECTED_SPLIT_SHA256, EXPECTED_MANIFEST_SHA256,
    preview_market,
)

# Nome del protocollo e stato: il piano e' una BOZZA, senza API e senza congelamento scientifico.
VERSION = "rq2_v2_unified_five_harness_discovery_v0"
STATUS = "DRAFT_NO_API_NO_SCIENTIFIC_FREEZE"
# Gli stage di ogni cella: D = diagnosi, C = ipotesi di causa, K = regola candidata.
STAGES = ("D", "C", "K")
MODELS = ("gemini", "sonnet", "haiku")
# Le cinque varianti (harness) a confronto.
HARNESSES = (
    "A0", "A1", "A1_8R", "A1_8R_Planning", "A1_PAVE",
)
# Budget di D, uguali per tutti: turni massimi di tool, verifiche massime, limite di ricorsione.
MAX_TOOL_ROUNDS = 6
MAX_VERIFICATION_CHECKS = 2
RECURSION_LIMIT = 30

# Il progetto attuale ha D in due motori: occorre conservare i tool_call_id
# per entrambi. Planning/PAVE NON vanno instradati sul grafo ReAct semplice.
ENGINES = {
    "A0": "rq2_v2_graph_engine",
    "A1": "rq2_v2_graph_engine",
    "A1_8R": "rq2_v2_graph_engine",
    "A1_8R_Planning": "verify_graph",
    "A1_PAVE": "verify_graph",
}


class UnifiedRQ2PlanError(ValueError):
    """La preview non puo' autorizzare un campione o fonte ambigui."""


def _canonical(value: object) -> bytes:
    """JSON canonico (chiavi ordinate, senza spazi, NaN vietati) in UTF-8: base degli hash."""
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _sha(value: object) -> str:
    """SHA-256 del JSON canonico di `value`."""
    return hashlib.sha256(_canonical(value)).hexdigest()


def _assert_code_identity() -> None:
    """Il piano deve restare coerente con i cinque agenti del runner RQ1.

    Controlla: harness uguali a `VARIANTI_FINALI`, modelli uguali a `CANDIDATE_MODELS`, un motore
    di D per ogni harness, coorte congelata di 15 casi (4 discovery + 11 test, senza sovrapposizioni).
    Solleva `UnifiedRQ2PlanError` se qualcosa e' cambiato.
    """
    if (tuple(VARIANTI_FINALI) != HARNESSES
            or tuple(CANDIDATE_MODELS) != MODELS
            or set(ENGINES) != set(HARNESSES)
            or len(set(DISCOVERY) | set(TEST)) != 15
            or set(DISCOVERY) & set(TEST)
            or len(DISCOVERY) != 4 or len(TEST) != 11):
        raise UnifiedRQ2PlanError("Identity or frozen cohort drift")


def build_offline_discovery_plan() -> dict:
    """Genera 180 stage D/C/K con release e API permanentemente disabilitate.

    Restituisce il piano: dizionario con il riepilogo (protocollo, stato, modelli, harness,
    casi, budget, avvertenze `can_*` tutte False, limiti noti), le 180 righe (`entries`) e due
    hash (`entries_sha256` e `preview_sha256`) che identificano il piano.

    Passi: 1) controlla l'identita' del codice; 2) per ogni caso, modello, harness e stage
    crea una riga con le dipendenze D -> C -> K; 3) verifica che le righe siano 180, tutte
    diverse e con ogni dipendenza PRIMA del suo stage; 4) compone riepilogo e hash.
    """
    _assert_code_identity()
    # 1-2. Una riga per ogni combinazione; lo stage_id contiene versione, caso, modello,
    # harness e stage. C dipende da D; K dipende da C (che a sua volta dipende da D).
    rows = []
    for case_id in DISCOVERY:
        for model in MODELS:
            for harness in HARNESSES:
                prefix = f"{VERSION}:{case_id}:{model}:{harness}"
                for stage in STAGES:
                    stage_id = prefix + ":" + stage
                    dependencies = (
                        [] if stage == "D" else
                        [prefix + ":D"] if stage == "C" else
                        [prefix + ":C"]
                    )
                    rows.append({
                        "stage_id": stage_id,
                        "case_id": case_id,
                        "logical_model": model,
                        "model_id": CANDIDATE_MODELS[model]["model_id"],
                        "model_provider": CANDIDATE_MODELS[model]["provider"],
                        "harness": harness,
                        "stage": stage,
                        "depends_on": dependencies,
                        "d_engine": ENGINES[harness],
                        "execution_status": "BLOCKED_DRAFT",
                    })

    # 3. Controlli di struttura: 180 stage distinti e ogni dipendenza compare PRIMA del figlio.
    ids = [row["stage_id"] for row in rows]
    if len(rows) != 180 or len(set(ids)) != 180:
        raise UnifiedRQ2PlanError("Unexpected discovery matrix")
    positions = {stage_id: i for i, stage_id in enumerate(ids)}
    if any(
        dep not in positions or positions[dep] >= i
        for i, row in enumerate(rows) for dep in row["depends_on"]
    ):
        raise UnifiedRQ2PlanError("Broken D/C/K ordering")

    # 4. Riepilogo del piano: obiettivo, parametri, conteggi e, soprattutto, tutte le
    # dichiarazioni "NON puo'/NON ha" (API, release, scrittura file, lettura di GT e telemetria).
    summary = {
        "protocol": VERSION,
        "status": STATUS,
        "mode": "OFFLINE_DISCOVERY_PLAN_ONLY",
        "research_objective": (
            "compare evidence-grounded K candidate quality across five "
            "harnesses and three LLMs, without generalization claims"
        ),
        "models": list(MODELS),
        "model_ids": {
            name: CANDIDATE_MODELS[name]["model_id"] for name in MODELS
        },
        "harnesses": list(HARNESSES),
        "discovery_cases": list(DISCOVERY),
        "discovery_case_count": len(DISCOVERY),
        "ood_test_cases_locked": list(TEST),
        "ood_test_case_count": len(TEST),
        "harness_model_arms": len(HARNESSES) * len(MODELS),
        "discovery_arm_cases": len(DISCOVERY) * len(HARNESSES) * len(MODELS),
        "stage_counts": {"D": 60, "C": 60, "K": 60},
        "logical_stages": 180,
        "planned_llm_http_calls": None,
        "max_tool_rounds_D": MAX_TOOL_ROUNDS,
        "max_verification_checks_planning": MAX_VERIFICATION_CHECKS,
        "max_recursion_depth_D": RECURSION_LIMIT,
        "output_contract_mode_D": "v2_enforce",
        "canonical_variant_scheme": "current",
        "C_and_K_prompt_contracts": "rq2_probe_adapter_v0_unchanged",
        "all_k_conditions_posthoc": False,
        "provenance_policy": (
            "preserve native tool_call_id for both ReAct and planner executors; "
            "reject ambiguous/unpaired tool results"
        ),
        "code_paths_not_modified": True,
        "split_sha256_expected": EXPECTED_SPLIT_SHA256,
        "manifest_sha256_expected": EXPECTED_MANIFEST_SHA256,
        "split_manifest_source_verified": False,
        "scientific_release_frozen": False,
        "provider_model_versions_frozen_for_campaign": False,
        "signed_release_exists": False,
        "api_budget_approved": False,
        "can_call_model_api": False,
        "can_write_real_claims": False,
        "can_run_ood_test": False,
        "ground_truth_read": False,
        "telemetry_read": False,
        "historical_records_read": False,
        "model_api_calls": 0,
        "files_written": False,
        "analysis_unit": "incident_case_within_model_and_harness",
        "comparison_policy": (
            "pair by the same four cases; account for failures and abstentions; "
            "no cherry-picking or cross-version pooling"
        ),
        "known_limitations": [
            "Four discovery incidents are few independent cases.",
            "Five harnesses x three models is factorial, not 60 independent faults.",
            "Historical Gemini V1 and Sonnet V2 pilot are external comparators.",
            "Planning/PAVE use a different graph and must retain tool provenance.",
            "New V2 release, source-bound orchestration, budgets and offline "
            "tests are not yet implemented or authorized.",
            "No evaluation of K causal correctness or generalization is possible "
            "from syntactic contract validity alone.",
        ],
    }
    # L'hash delle righe e quello dell'intero rapporto identificano il piano in modo univoco.
    report = {
        **summary,
        "entries_sha256": _sha(rows),
        "entries": rows,
    }
    return {
        **report,
        "preview_sha256": _sha(report),
    }


def preview_gt_free_sources(data_dir: Path) -> dict:
    """Collega la preview a uno split/manifest originali verificati su disco.

    Non modifica il piano, non crea release e non puo' sbloccare alcuna API.

    Argomenti: `data_dir` e' la radice dei dati, un `Path` assoluto, senza ".." e non un
    collegamento simbolico. Restituisce un riepilogo con stato
    `GT_FREE_SOURCE_CHECKED_PLAN_STILL_BLOCKED`; solleva `UnifiedRQ2PlanError` se il percorso
    non e' sicuro o se split/manifest non coincidono con quelli congelati.
    """
    # Percorso sicuro: assoluto, senza risalite e senza link simbolici.
    if not isinstance(data_dir, Path) or not data_dir.is_absolute():
        raise UnifiedRQ2PlanError("Absolute pathlib.Path required")
    if ".." in data_dir.parts or data_dir.is_symlink():
        raise UnifiedRQ2PlanError("Unsafe data root")
    # Verifica di sorgente: hash di split e manifest, partizione discovery/test e conteggi
    # della preview storica (`rq2_dryrun_plan`, 204 stage) devono essere quelli congelati.
    historical = preview_market(data_dir)
    if (
        historical.get("source_verified") is not True
        or historical.get("split_sha256") != EXPECTED_SPLIT_SHA256
        or historical.get("manifest_sha256") != EXPECTED_MANIFEST_SHA256
        or historical.get("partition", {}).get("discovery_case_ids")
        != sorted(DISCOVERY)
        or historical.get("partition", {}).get("test_case_ids")
        != sorted(TEST)
        or historical.get("stages") != {"D": 90, "C": 90, "K": 24}
        or historical.get("total_stage_entries") != 204
        or historical.get("can_execute_api") is not False
    ):
        raise UnifiedRQ2PlanError("Frozen GT-free source verification failed")
    preview = build_offline_discovery_plan()
    # Non trasformare source verification in scientific release.
    return {
        "status": "GT_FREE_SOURCE_CHECKED_PLAN_STILL_BLOCKED",
        "protocol": VERSION,
        "base_plan_preview_sha256": preview["preview_sha256"],
        "split_manifest_source_verified": True,
        "split_sha256": historical["split_sha256"],
        "manifest_sha256": historical["manifest_sha256"],
        "discovery_case_count": preview["discovery_case_count"],
        "harness_model_arms": preview["harness_model_arms"],
        "stage_counts": preview["stage_counts"],
        "logical_stages": preview["logical_stages"],
        "can_call_model_api": False,
        "can_run_ood_test": False,
        "scientific_release_frozen": False,
        "ground_truth_read": False,
        "telemetry_read": False,
        "model_api_calls": 0,
        "files_written": False,
    }
