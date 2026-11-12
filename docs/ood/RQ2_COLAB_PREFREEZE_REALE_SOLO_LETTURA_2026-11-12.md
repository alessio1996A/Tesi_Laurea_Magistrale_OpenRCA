# RQ2 — Colab: pre-freeze GT-free con sorgenti originali, **senza inferenze**

Data: **12 novembre 2026**. Stato: candidato non congelato. Repository RQ1 e risultati Evaluation20 non modificati.

Dopo la conferma `Ran 12 tests in 1.011s — OK` sul driver D sintetico, il passo operativo è eseguire una volta il nuovo `rq2_discovery_prereg_readiness.py` **sugli stessi due CSV GT-free originali usati nei precedenti audit**. Serve a raccogliere `plan_preview_sha256`, snapshot versioni Python, SHA prompt C/K, catalogo KPI source-only e controlli 4 discovery/11 test. Il modulo è **sola lettura** e restituisce sempre `can_execute_D=false`, `can_execute_CK=false`, `can_execute_test=false`.

## Una cella Colab (da copiare per intero)

Le directory qui riprendono la disposizione delle sessioni Evaluation20: **dati su Google Drive**, repository separato in `/content`. Il clone RQ2 è nuovo e non tocca `/content/Tesi_OpenRCA_Evaluation20` né i risultati in Drive. L'installazione delle dipendenze usa un **venv RQ2 separato** e le versioni utilizzate in Evaluation20, senza contattare alcun provider LLM.

```python
from pathlib import Path
from google.colab import drive
import os, subprocess, sys

drive.mount("/content/drive")

DATA = Path("/content/drive/MyDrive/Tesi_OpenRCA")
REPO = Path("/content/Tesi_OpenRCA_RQ2")
VENV = Path("/content/rq2_prefreeze_venv")
PY = VENV / "bin/python"
BRANCH = "feature/ood-knowledge-transfer-audit-2026-11-10"
URL = "https://github.com/alessio1996A/Tesi_Laurea_Magistrale_OpenRCA.git"

for relative in (
    "data/processed/split_market_v1.csv",
    "data/processed/benchmark_inputs_market.csv",
):
    assert (DATA / relative).is_file(), f"Manca sorgente GT-free: {relative}"

if not (REPO / ".git").is_dir():
    subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch",
         "--branch", BRANCH, URL, str(REPO)],
        check=True,
    )
else:
    subprocess.run(["git", "-C", str(REPO), "fetch", "origin", BRANCH], check=True)
    subprocess.run(
        ["git", "-C", str(REPO), "checkout", BRANCH], check=True,
    )
    subprocess.run(
        ["git", "-C", str(REPO), "pull", "--ff-only", "origin", BRANCH],
        check=True,
    )

if not PY.is_file():
    subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    subprocess.run([
        str(PY), "-m", "pip", "install", "--disable-pip-version-check",
        "langchain==1.4.7", "langchain-core==1.7.1",
        "langgraph==1.2.18", "langchain-google-genai==4.4.2",
        "langchain-anthropic==1.7.7", "google-genai==2.34.0",
        "anthropic==2.6.0", "google-auth==2.56.0",
        "pandas", "networkx", "python-dotenv"
    ], check=True)

environment = dict(os.environ)
environment["PYTHONPATH"] = str(REPO / "src")

print("=== RQ2 PREFREEZE: GT-FREE, NESSUNA API MODELLO ===")
print("Repository:", REPO, "| Dati:", DATA)
subprocess.run(
    [str(PY), "-m", "evaluation.rq2_discovery_prereg_readiness",
     "--data-dir", str(DATA), "--repo-dir", str(REPO)],
    cwd=REPO, env=environment, check=True,
)
```

**N.B.** La cella monta Drive, effettua un clone/aggiornamento del **codice** e, se serve, installa dipendenze in `/content/rq2_prefreeze_venv` (quindi ha accesso a GitHub/PyPI). **Non** effettua chiamate Gemini/Claude, non scrive nuovi artefatti nei dati Drive e non apre `Market.zip`, `record.csv`, scoring o output di predizioni. Il report `files_written=false` riguarda esclusivamente il modulo di preflight, non il clone/venv temporaneo.

Se il clone è privato e il login GitHub non è configurato, la cella può interrompersi prima del preflight: non sostituire il repository con un branch Evaluation20 vecchio solo per ottenere un report “OK”. Se una dipendenza non si installa, riportare l'errore: non cambiare arbitrariamente versioni di SDK e modelli.

## Output da riportare qui per l'audit

Conservare il JSON stampato dalla cella. In particolare:
- `status = REAL_GT_FREE_SOURCE_CHECKED_PREFREEZE_NOT_EXECUTABLE`;
- `plan_preview_sha256`, `source_split_sha256`, `source_manifest_sha256`;
- `discovery_stages=72`, `test_stages_locked=132`, `total_stages=204`;
- `C_system_prompt_sha256` e `K_system_prompt_sha256`;
- `kpi_source_catalog_sha256`, `runtime_package_versions_observed`;
- `can_execute_D=false`, `can_execute_CK=false`, `can_execute_test=false`.

Se un hash differisce o il modulo esce con errore, **stop**: non creare un release per aggirare il controllo. Dopo il JSON reale, finalizzare i criteri/scelte aperti del documento `RQ2_DISCOVERY_PREREG_V1_CANDIDATE_2026-11-12.md`, registrare il release scientifico create-only e pin SHA del solo canale discovery; poi eseguire un singolo stage D autorizzato. Gli 11 casi test restano chiusi fino al freeze K.

**Il budget non ha un tetto USD prestabilito; resta obbligatoria la rendicontazione dei token e l'integrità degli stage.**
