# RQ2 — Colab: pre-freeze GT-free con sorgenti originali, **senza inferenze**

Data: **12 novembre 2026**. Stato: candidato non congelato. Repository RQ1 e risultati Evaluation20 non modificati.

Dopo la conferma `Ran 12 tests in 1.011s — OK` sul driver D sintetico, il passo operativo è eseguire una volta il nuovo `rq2_discovery_prereg_readiness.py` **sugli stessi due CSV GT-free originali usati nei precedenti audit**. Serve a raccogliere `plan_preview_sha256`, snapshot versioni Python, SHA prompt C/K, catalogo KPI source-only e controlli 4 discovery/11 test. Il modulo è **sola lettura** e restituisce sempre `can_execute_D=false`, `can_execute_CK=false`, `can_execute_test=false`.

## Una cella Colab (da copiare per intero)

Le directory qui riprendono la disposizione delle sessioni Evaluation20: **dati su Google Drive**, repository separato in `/content`. Il clone RQ2 è nuovo e non tocca `/content/Tesi_OpenRCA_Evaluation20` né i risultati in Drive. **Correzione Colab Python 3.13:** la precedente cella si arrestava in `python -m venv` (exit 1). Ora `pip --target` installa le librerie in `/content/rq2_prefreeze_packages_py313` e avvia il preflight in un processo separato. Questa cartella non è un ambiente virtuale completo, ma isola i pacchetti usati dal subprocess; non usa né altera il `rq2_prefreeze_venv` incompleto. I pin RQ1 sono mantenuti; i pacchetti non pin (pandas, networkx, dotenv) vengono registrati dal report quando disponibili.

```python
from pathlib import Path
from google.colab import drive
import hashlib, os, subprocess, sys

# RQ2: controllo SOLO dei manifest GT-free e del codice.
# Nessuna chiamata API ai modelli; nessun file scritto su Drive.
drive.mount("/content/drive")

DATA = Path("/content/drive/MyDrive/Tesi_OpenRCA")
REPO = Path("/content/Tesi_OpenRCA_RQ2")
DEPS = Path("/content/rq2_prefreeze_packages_py313")  # NON è un venv
BRANCH = "feature/ood-knowledge-transfer-audit-2026-11-10"
URL = "https://github.com/alessio1996A/Tesi_Laurea_Magistrale_OpenRCA.git"

print("\n=== [1/4] SORGENTI ORIGINALI GT-FREE ===", flush=True)
for relative in (
    "data/processed/split_market_v1.csv",
    "data/processed/benchmark_inputs_market.csv",
):
    path = DATA / relative
    assert path.is_file(), f"Manca il file originale: {path}"
    print("OK:", relative, flush=True)

print("\n=== [2/4] BRANCH RQ2 SEPARATO ===", flush=True)
if not (REPO / ".git").is_dir():
    subprocess.run([
        "git", "clone", "--depth", "1", "--single-branch",
        "--branch", BRANCH, URL, str(REPO)
    ], check=True)
else:
    subprocess.run(["git", "-C", str(REPO), "fetch", "origin", BRANCH], check=True)
    subprocess.run(["git", "-C", str(REPO), "checkout", BRANCH], check=True)
    subprocess.run([
        "git", "-C", str(REPO), "pull", "--ff-only", "origin", BRANCH
    ], check=True)
subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], check=True)

print("\n=== [3/4] LIBRERIE ISOLATE (SENZA VENV) ===", flush=True)
print("Python Colab:", sys.version.split()[0], flush=True)
PINS = [
    "langchain==1.4.7",
    "langchain-core==1.7.1",
    "langgraph==1.2.18",
    "langchain-google-genai==4.4.2",
    "langchain-anthropic==1.7.7",
    "google-genai==2.34.0",
    "anthropic==2.6.0",
    "google-auth==2.56.0",
    "pandas", "networkx", "python-dotenv",
]
signature = hashlib.sha256(
    ("\n".join(PINS) + "\n" + sys.version).encode("utf-8")
).hexdigest()
ready = DEPS / ".rq2_packages_ready"

if not ready.is_file() or ready.read_text().strip() != signature:
    DEPS.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable, "-m", "pip", "install",
        "--disable-pip-version-check",
        "--upgrade", "--target", str(DEPS),
        *PINS
    ], check=True)
    ready.write_text(signature + "\n", encoding="utf-8")
print("Dipendenze RQ2 pronte:", DEPS, flush=True)

print("\n=== [4/4] PREFLIGHT REALE DI SOLA LETTURA ===", flush=True)
env = dict(os.environ)
env["PYTHONPATH"] = os.pathsep.join((str(DEPS), str(REPO / "src")))
subprocess.run([
    sys.executable, "-m", "evaluation.rq2_discovery_prereg_readiness",
    "--data-dir", str(DATA),
    "--repo-dir", str(REPO),
], cwd=REPO, env=env, check=True)

print("\n=== PREFLIGHT TERMINATO ===", flush=True)
print("API Gemini/Claude invocate da questa cella: 0")
print("Esperimenti RQ2 lanciati: 0")
print("Test OOD: ancora bloccati")
```

**N.B.** La cella monta Drive, effettua un clone/aggiornamento del **codice** e, se serve, installa dipendenze mediante `pip --target` in `/content/rq2_prefreeze_packages_py313` (quindi ha accesso a GitHub/PyPI). **Non** effettua chiamate Gemini/Claude, non scrive nuovi artefatti nei dati Drive e non apre `Market.zip`, `record.csv`, scoring o output di predizioni. Il report `files_written=false` riguarda esclusivamente il modulo di preflight, non il clone/venv temporaneo.

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


## Correzione applicata dopo errore Colab (12 novembre 2026)

Nel notebook dell'utente la vecchia cella ha trovato i due CSV originali ed è arrivata allo step Python, ma `[sys.executable, "-m", "venv", "/content/rq2_prefreeze_venv"]` è uscito con status 1, prima di qualsiasi preflight o modello. La causa specifica non è leggibile dal traceback. Per evitare dipendenze da `venv/ensurepip` nel runtime Colab Python 3.13, la **cella sopra** usa un target temporaneo su `/content` e un subprocess con `PYTHONPATH`. La directory `/content/rq2_prefreeze_venv` parzialmente creata non serve e non viene usata. Nessuna modifica ai dati Drive e nessuna API LLM. **Nuova cella ancora da eseguire; non dichiarare il preflight superato prima del JSON.**
