# RQ2 — Audit Gemini V1 reale in Google Colab (sola lettura, dopo 852/852)

**Data:** 13 novembre 2026.  
**Stato:** cella pronta ma **NON ancora eseguita**.  
**Risultato PyCharm comunicato dall'utente:** `Ran 852 tests in 78.413s / OK`.  
**Nessuna API LLM; nessun nuovo claim; nessun write ai dati del progetto.**

## Scopo e prerequisiti

Verificare i 24 artefatti reali Gemini V1 già acquisiti, senza
ripeterli e senza accedere alle 11 query OOD test. Il report
mostra gli 8 arm (4 discovery × A1/A1_8R), il risultato
tecnico D/C/K, la decisione C e il preflight delle K.

La cella usa una directory temporanea **distinta** per il
checkout, monta il Drive dove sono già presenti
`/content/drive/MyDrive/Tesi_OpenRCA/data/rq2` e
`data/processed`, riusa soltanto se il marker di
dipendenze precedenti ha la firma esatta e blocca
qualunque drift di Python, Git/source o manifest V1.

**Questo non è il pilot Sonnet.** Non chiama Gemini,
Sonnet o Haiku e non consulta le ground truth.

## Una sola cella Google Colab — eseguire solo dopo aver letto i gate

~~~python
from pathlib import Path
from google.colab import drive
import hashlib, json, os, subprocess, sys

# Snapshot immutabile: include audit e suite test 852/852.
BRANCH = "experiment/rq2-provenance-v2-offline-2026-11-13"
PIN_COMMIT = "489a53467087b8070c8909ceddad1d6aee74d02d"
AUDIT_BLOB = "dd36792d8bd64ddfcd24e658d519f2e057b312ac"
REMOTE = "https://github.com/alessio1996A/Tesi_Laurea_Magistrale_OpenRCA.git"

DATA = Path("/content/drive/MyDrive/Tesi_OpenRCA")
REPO = Path("/content/Tesi_OpenRCA_RQ2_Gemini_Audit_Readonly")
DEPS_OLD = Path("/content/rq2_prefreeze_packages_py313")
DEPS_NEW = Path("/content/rq2_gemini_audit_packages_py313")

# Fail-closed: niente cambio silenzioso del runtime sperimentale.
assert sys.version.split()[0] == "3.13.18", "PYTHON_RUNTIME_DRIFT: STOP"
for target in (REPO, DEPS_OLD, DEPS_NEW):
    assert not target.is_symlink(), f"SYMLINK_PATH_STOP: {target.name}"

drive.mount("/content/drive")
assert DATA.is_dir() and not DATA.is_symlink(), "DRIVE_ROOT_MISSING: STOP"
for rel in (
    "data/processed/split_market_v1.csv",
    "data/processed/benchmark_inputs_market.csv",
    "data/rq2",
):
    path = DATA / rel
    assert path.exists() and not path.is_symlink(), f"V1_SOURCE_MISSING: {rel}"
print("DRIVE_V1_SOURCE_PATHS: PRESENT (not modified)", flush=True)

# Preparare solo /content: MAI cancellare o riparare vecchi dati su Drive.
git_env = dict(os.environ)
git_env["GIT_TERMINAL_PROMPT"] = "0"
if not REPO.exists():
    subprocess.run([
        "git", "clone", "--depth", "20", "--single-branch",
        "--branch", BRANCH, REMOTE, str(REPO),
    ], check=True, env=git_env)
else:
    assert (REPO / ".git").is_dir(), "AUDIT_CHECKOUT_NOT_GIT: STOP"
    origin = subprocess.check_output(
        ["git", "-C", str(REPO), "remote", "get-url", "origin"],
        text=True,
    ).strip()
    assert origin in (REMOTE, REMOTE[:-4]), "UNEXPECTED_ORIGIN: STOP"
assert not subprocess.check_output(
    ["git", "-C", str(REPO), "status", "--porcelain"], text=True
).strip(), "DIRTY_CHECKOUT: STOP"
subprocess.run(
    ["git", "-C", str(REPO), "cat-file", "-e", PIN_COMMIT + "^{commit}"],
    check=True,
)
subprocess.run(
    ["git", "-C", str(REPO), "checkout", "--detach", PIN_COMMIT],
    check=True,
)
head = subprocess.check_output(
    ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True,
).strip()
assert head == PIN_COMMIT, "GIT_COMMIT_DRIFT: STOP"
blob = subprocess.check_output(
    ["git", "-C", str(REPO), "rev-parse",
     "HEAD:src/evaluation/rq2_v1_gemini_readonly_audit.py"],
    text=True,
).strip()
assert blob == AUDIT_BLOB, "AUDIT_SOURCE_DRIFT: STOP"
assert not subprocess.check_output(
    ["git", "-C", str(REPO), "status", "--porcelain"], text=True
).strip(), "CHECKOUT_MODIFIED: STOP"
print("GIT_HEAD:", head, flush=True)
print("AUDIT_SOURCE_BLOB:", blob, flush=True)

# Le medesime versioni usate per il protocollo RQ2-V1;
# nessun SDK viene invocato dall'audit.
PINS = [
    "langchain==1.4.7", "langchain-core==1.7.1",
    "langgraph==1.2.18", "langchain-google-genai==4.4.2",
    "langchain-anthropic==1.7.7", "google-genai==2.34.0",
    "anthropic==2.6.0", "google-auth==2.56.0",
    "pandas", "networkx", "python-dotenv",
]
signature = hashlib.sha256(
    ("\n".join(PINS) + "\n" + sys.version).encode("utf-8")
).hexdigest()

def valid_deps(path):
    marker = path / ".rq2_packages_ready"
    return (
        path.is_dir() and not path.is_symlink()
        and marker.is_file() and not marker.is_symlink()
        and marker.read_text(encoding="utf-8").strip() == signature
    )

if valid_deps(DEPS_OLD):
    deps = DEPS_OLD
    print("DEPS: VERIFIED_REUSE_PREVIOUS", flush=True)
else:
    deps = DEPS_NEW
    if not deps.exists():
        deps.mkdir(mode=0o700)
        subprocess.run([
            sys.executable, "-m", "pip", "install",
            "--disable-pip-version-check",
            "--target", str(deps), *PINS,
        ], check=True)
        (deps / ".rq2_packages_ready").write_text(
            signature + "\n", encoding="utf-8",
        )  # marker ONLY in /content, NEVER in Drive
        print("DEPS: INSTALLED_IN_TEMP_PATH", flush=True)
    else:
        assert valid_deps(deps), "UNVERIFIED_DEPENDENCIES: STOP"
        print("DEPS: VERIFIED_REUSE_AUDIT_TEMP", flush=True)

# Processo figlio con credenziali provider e tracing esclusi.
env = dict(os.environ)
for key in (
    "GOOGLE_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
    "GOOGLE_GENAI_USE_VERTEXAI", "LANGCHAIN_API_KEY",
    "LANGCHAIN_TRACING_V2", "LANGSMITH_API_KEY",
    "LANGSMITH_TRACING", "LANGSMITH_ENDPOINT",
):
    env.pop(key, None)
env["PYTHONPATH"] = os.pathsep.join((str(deps), str(REPO / "src")))
env["PYTHONDONTWRITEBYTECODE"] = "1"
env["PYTHONNOUSERSITE"] = "1"

# SOURCE-VERIFIED original journal, solo letture; output redatto.
process = subprocess.run([
    sys.executable, "-m", "evaluation.rq2_v1_gemini_readonly_audit",
    "--data-dir", str(DATA),
], env=env, capture_output=True, text=True)
if process.returncode != 0:
    print("AUDIT_STOPPED_NONZERO: no retry and no API", flush=True)
    print(process.stderr[-3500:])
    raise RuntimeError("Audit non completato: inviare traceback, NON cambiare V1")

summary = json.loads(process.stdout)
assert summary["source_verified_by_v1_store"] is True
assert summary["observed_stages"] == summary["planned_stages"] == 24
assert summary["by_record_status"] == {
    "RECORDED_COMPLETE": 22,
    "INVALID_OUTPUT": 1,
    "BLOCKED_DEPENDENCY": 1,
}
assert summary["v1_total_recorded_all_providers"] == 39, "V1_RECORD_COUNT_DRIFT: STOP"
assert summary["v1_total_claims_all_providers"] == 32, "V1_CLAIM_COUNT_DRIFT: STOP"
assert summary["unresolved_claims"] == 0
assert summary["scientific_k_rules_frozen"] == 0
assert summary["can_run_ood_test"] is False
assert summary["read_ground_truth"] is False
assert summary["model_api_calls"] == 0
assert summary["files_written"] == 0
assert summary["changed_v1_records"] is False
assert len(summary["cases"]) == 8

print("STATUS: GEMINI_V1_24_READONLY_AUDIT_OK", flush=True)
print("COUNTS_BY_STATUS:", json.dumps(summary["by_record_status"]))
print("C_DECISIONS:", json.dumps(summary["C_decisions"], sort_keys=True))
print("K_CONTRACT:", json.dumps(summary["K_contract_statuses"], sort_keys=True))
print("K_PREFLIGHT:", json.dumps(summary["K_preflight_statuses"], sort_keys=True))
print("V1_TOTAL_RECORDS_ALL_PROVIDERS:", summary["v1_total_recorded_all_providers"])
print("V1_TOTAL_CLAIMS_ALL_PROVIDERS:", summary["v1_total_claims_all_providers"])
print("UNRESOLVED_CLAIMS:", summary["unresolved_claims"])
print("PER_DISCOVERY_ARM:")
for row in summary["cases"]:
    print(
        row["case_id"], row["harness"],
        "D=" + row["D_record_status"],
        "C=" + row["C_record_status"],
        "C_decision=" + str(row["C_decision"]),
        "K=" + row["K_record_status"],
        "K_contract=" + str(row["K_contract_status"]),
        "K_preflight=" + str(row["K_preflight_status"]),
    )
print("GROUND_TRUTH_READ: FALSE | API_CALLS: 0 | V1_WRITES: 0 | OOD_TEST: LOCKED")
~~~

## Interpretazione corretta

- `candidate`: proposta JSON strutturalmente valida; serve
  verifica indipendente delle misure/KPI, delle unità,
  delle aggregazioni, delle soglie e delle finestre.
- `requires_verification`: nessun permesso per usare K
  su OOD; non equivale a un fallimento del modello.
- `insufficient_evidence`: astensione esplicita,
  **non** una regola formalizzabile.
- `RECORDED_COMPLETE`: provenance/contratto tecnico
  accettato, **non** diagnosi corretta rispetto alla GT.
- `INVALID_OUTPUT` e `BLOCKED_DEPENDENCY`:
  conservare entrambi; non tentare di nuovo né riscrivere.

Il programma può stampare `AUDIT_STOPPED_NONZERO`
se trova un record o una sorgente inattesa.
In tal caso fermarsi e riportare l'errore, mai
eseguire la campagna provider o alterare Drive.

## Prossimo passo

Dopo l'output reale Gemini:
1. Registrare in GitHub un report GT-free
   dei 24 stage già osservati e delle 8 K;
2. quantificare quante K richiedono verifica
   vs astensione, senza consultare OOD/test/GT;
3. preparare una **release V2 separata source-bound**
   con test offline e un pilot Sonnet D su un caso
   discovery già visto in V1, previa nuova
   autorizzazione alla spesa; 
4. non associare direttamente Gemini V1 e Sonnet V2
   come confronto causale a parità di esecutore.

**Non inserire chiavi API in questa cella.**
