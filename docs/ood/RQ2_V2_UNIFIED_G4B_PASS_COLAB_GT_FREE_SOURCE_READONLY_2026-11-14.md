# RQ2-V2 unificata — G4B 18/18 PASS e preflight Colab GT-free reale (sola lettura)

**Data:** 14 novembre 2026. **Branch:** `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`. **Opzione A**: 4 discovery × 5 harness × 3 LLM × D/C/K = 180 stage logici; **Opzione B successiva**: 11 test OOD lockati, senza scoring o generalizzazione adesso.

## Evidenza nuova fornita dall'utente

```text
Ran 18 tests in 0.485s

OK
```

Questi sono i test G4B `src/tests/test_rq2_v2_unified_release_blueprint_offline.py`. Le suite G1=25, G2=9, G3A=23, G3B=9, G4A=18, G4B=18 hanno tutte esito utente `OK`: **102 metodi di unittest** totali, ma **non** 102 casi reali o run API. G4B verifica una descrizione non eseguibile a partire da un report G4A simulato; **non** verifica ancora split/manifest reali con il nuovo codice.

## Passo successivo: leggere davvero i CSV GT-free congelati, non il benchmark

Questo preflight è nuovo per la **matrice unificata**. I CSV originali erano già stati verificati nella RQ2 V1 il 12 novembre, ma la nuova catena `preview_unified_source_bound`→`build_unified_release_blueprint` non è stata ancora provata con i file reali. La cella seguente esegue la verifica **senza installazioni pip né SDK**, perché tutta la catena di preflight importa esclusivamente componenti stdlib del repository (non crea LLM). 

La cella monta Google Drive, senza modificarne i dati; crea/aggiorna un checkout separato solo nel filesystem temporaneo Colab `/content/Tesi_OpenRCA_RQ2_Unified_Preflight`, con `git status` clean check, e legge soltanto:
- `data/processed/split_market_v1.csv`
- `data/processed/benchmark_inputs_market.csv`
- i file sorgente Python del repository necessari alla provenance RQ1/RQ2.

L'audit usa i **metadati di partizione** anche degli 11 casi riservati, ma non apre le loro telemetrie, GT o predizioni: non sta eseguendo l'Opzione B. Nessun `Market.zip`, `record.csv`, `query.csv`, scorer, API provider, token pagati o output scientifici salvati.

### Una sola cella Google Colab da incollare integralmente

```python
from google.colab import drive
from pathlib import Path
import json, os, re, subprocess, sys

# G4: SOLA LETTURA dei CSV originali; NON e' un runner sperimentale.
drive.mount("/content/drive")

DATA = Path("/content/drive/MyDrive/Tesi_OpenRCA")
REPO = Path("/content/Tesi_OpenRCA_RQ2_Unified_Preflight")
BRANCH = "feature/rq2-v2-unified-five-harness-three-models-2026-11-14"
URL = "https://github.com/alessio1996A/Tesi_Laurea_Magistrale_OpenRCA.git"

print("=== 1/3: CSV ORIGINALI GT-FREE ===", flush=True)
assert DATA.is_dir() and not DATA.is_symlink(), "Data root absent/unsafe"
for rel in (
    "data/processed/split_market_v1.csv",
    "data/processed/benchmark_inputs_market.csv",
):
    source = DATA / rel
    assert source.is_file() and not source.is_symlink(), f"Missing/unsafe: {rel}"
    print("FOUND:", rel, flush=True)

print("=== 2/3: CODICE UNIFICATO SEPARATO ===", flush=True)
if (REPO / ".git").is_dir():
    before = subprocess.check_output(
        ["git", "-C", str(REPO), "status", "--porcelain"],
        text=True,
    )
    assert before.strip() == "", "Checkout dirty: STOP, inspect manually"
    subprocess.run(
        ["git", "-C", str(REPO), "fetch", "origin", BRANCH],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(REPO), "checkout", "--detach", "FETCH_HEAD"],
        check=True,
    )
else:
    assert not REPO.exists(), "Existing non-git path: STOP"
    subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch",
         "--branch", BRANCH, URL, str(REPO)],
        check=True,
    )

head = subprocess.check_output(
    ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True,
).strip()
assert re.fullmatch(r"[0-9a-f]{40}", head)
assert not subprocess.check_output(
    ["git", "-C", str(REPO), "status", "--porcelain"], text=True,
).strip(), "Checkout modified: STOP"
print("CODE_COMMIT:", head, flush=True)

print("=== 3/3: RQ2 V2 UNIFIED SOURCE GATE — NO API ===", flush=True)
# Il processo figlio carica i soli moduli sorgente e stdlib: nessun SDK.
code = r"""
import json, os
from pathlib import Path
from evaluation.rq2_v2_unified_release_preflight import preview_unified_source_bound
from evaluation.rq2_v2_unified_release_blueprint import build_unified_release_blueprint

data = Path(os.environ["RQ2_DATA_ROOT"])
repo = Path(os.environ["RQ2_REPO_ROOT"])
source = preview_unified_source_bound(data_dir=data, src_root=repo / "src")
plan = build_unified_release_blueprint(source_preview=source)

assert source["status"] == "OFFLINE_SOURCE_BOUND_NO_RELEASE_NO_API"
assert source["gt_free_source_verified"] is True
assert source["frozen_rq1_source_identity_verified"] is True
assert source["logical_stages"] == 180
assert source["can_execute_api"] is False
assert source["can_run_ood_test"] is False
assert source["ground_truth_read"] is False
assert plan["logical_stage_count"] == 180
assert plan["max_graph_invocations_if_all_stages_reached_candidate"] == 492
assert plan["can_execute_api"] is False
assert plan["can_write_scientific_claims"] is False
assert plan["can_run_ood_test"] is False
assert plan["scientific_release_frozen"] is False

report = {
    "status": "RQ2_V2_UNIFIED_REAL_GT_FREE_SOURCE_PREFLIGHT_OK_NO_API",
    "source_status": source["status"],
    "blueprint_status": plan["status"],
    "source_plan_preview_sha256": source["plan_preview_sha256"],
    "blueprint_sha256": plan["blueprint_sha256"],
    "split_sha256": source["split_sha256"],
    "manifest_sha256": source["manifest_sha256"],
    "C_system_prompt_sha256": source["C_system_prompt_sha256"],
    "K_system_prompt_sha256": source["K_system_prompt_sha256"],
    "source_file_count": source["source_file_count"],
    "harnesses": source["harnesses"],
    "model_ids": source["model_ids"],
    "discovery_cases": source["discovery_cases"],
    "ood_test_cases_locked": source["ood_test_cases_locked"],
    "stage_counts": source["stage_counts"],
    "max_graph_invocations_candidate_not_HTTP": (
        plan["max_graph_invocations_if_all_stages_reached_candidate"]
    ),
    "can_execute_api": False,
    "can_run_ood_test": False,
    "scientific_release_frozen": False,
    "model_requests_sent": 0,
    "ground_truth_read": False,
    "scientific_artifacts_written": 0,
}
print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
"""
env = os.environ.copy()
env["PYTHONPATH"] = str(REPO / "src")
env["RQ2_DATA_ROOT"] = str(DATA)
env["RQ2_REPO_ROOT"] = str(REPO)
subprocess.run(
    [sys.executable, "-B", "-c", code],
    cwd=REPO, env=env, check=True,
)
print("G4 REAL GT-FREE SOURCE PREFLIGHT: TERMINATO (0 API)")
```

### Output atteso e interpretazione

- `status="RQ2_V2_UNIFIED_REAL_GT_FREE_SOURCE_PREFLIGHT_OK_NO_API"`
- `source_plan_preview_sha256`, `blueprint_sha256`, `split_sha256`, `manifest_sha256`, `C_system_prompt_sha256`, `K_system_prompt_sha256` per tracciabilità.
- `discovery_cases` = i quattro casi previsti; `ood_test_cases_locked=11`; `stage_counts` D/C/K=60 ciascuno.
- `model_requests_sent=0`, `ground_truth_read=false`, `can_execute_api=false`, `scientific_release_frozen=false`.
- Non mostra gli ID dei test OOD né le loro etichette.

**Se fallisce:** copiare tutto l'errore e STOP, senza cambiare hash, input o branch per forzare `OK`. La cella non autorizza una campagna reale; la successiva attività rimane l'implementazione di un **unico ledger/dispatcher scientifico** con release immutabile e prove di trasporto/no-retry, seguita da consenso esplicito a un pilot a pagamento. Opzione B resta differita.
