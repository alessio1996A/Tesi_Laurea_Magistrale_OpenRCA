# RQ2 — Preflight finale Colab dopo approvazione scientifica (solo lettura)

**12/11/2026 · Metodo scientifico APPROVATO dall'utente; release NON firmato; API VIETATE.**

La risposta dell'utente «ok approvo, e inizierei con gemini» approva il
pacchetto scientifico di
`RQ2_REVIEW_SCIENTIFICO_PRIMA_RELEASE_2026-11-12.md`,
non un consumo di token. Primo stage *proposto in ordine di piano*:
`cloudbed-1_q032` / `gemini-3.5-flash-lite` / `A1` / `D`;
autorizzazione esplicita specifica ancora **mancante**. Lo studio RQ2-C
mantiene l'arm preregistrato `A1_8R + Claude Sonnet 5.5`.

## Cosa fare in PyCharm

Solo sincronizzare il branch (modifiche esclusivamente documentali);
**non ripetere** i 53 unit test verdi, i test fake HTTP o RQ1.

```powershell
git status --short
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
git rev-parse HEAD
```

Se `git status --short` mostra modifiche locali non comprese, fermarsi
e valutarle prima del pull. Non modificare i sorgenti frozen.

## Google Colab — un'unica cella, SOLO OFFLINE

La cella monta i **due CSV GT-free originali** presenti sul Drive
dell'utente, clona/aggiorna esclusivamente il branch RQ2 in `/content`,
ripristina nel target temporaneo le dipendenze pinned solo se assenti,
e avvia **una sola volta** la CLI di preflight esistente sul checkout che
potrà essere usato per RQ2. Verifica inoltre **senza istanziare client**
che i sei pacchetti e i quattro sorgenti SDK/LangChain siano esattamente
quelli preregistrati dalla factory RQ2-only. Non avvia test unitari,
modelli, tool, agenti, scoring con GT, o stage della campagna.
Nessun write sul Drive dati. Gli accessi di rete sono limitati a
Google Drive, GitHub e PyPI per clone/rispristino di pacchetti; **zero
richieste ai provider Gemini/Claude**.

```python
from pathlib import Path
from google.colab import drive
import hashlib, json, os, subprocess, sys

drive.mount("/content/drive")

REPO = Path("/content/Tesi_OpenRCA_RQ2")
DATA = Path("/content/drive/MyDrive/Tesi_OpenRCA")
DEPS = Path("/content/rq2_prefreeze_packages_py313")
BRANCH = "feature/ood-knowledge-transfer-audit-2026-11-10"
URL = "https://github.com/alessio1996A/Tesi_Laurea_Magistrale_OpenRCA.git"

for name in (
    "data/processed/split_market_v1.csv",
    "data/processed/benchmark_inputs_market.csv",
):
    assert (DATA / name).is_file(), "CSV GT-free originale mancante: " + name

git_env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
if not (REPO / ".git").is_dir():
    assert not REPO.exists(), "Directory checkout RQ2 preesistente non Git"
    subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch",
         "--branch", BRANCH, URL, str(REPO)],
        check=True, env=git_env,
    )
else:
    remote = subprocess.check_output(
        ["git", "-C", str(REPO), "remote", "get-url", "origin"],
        text=True,
    ).strip()
    assert remote in (URL, URL[:-4]), "Origin differente: STOP"
    assert not subprocess.check_output(
        ["git", "-C", str(REPO), "status", "--porcelain"], text=True
    ).strip(), "Checkout RQ2 sporco: STOP"
    subprocess.run(
        ["git", "-C", str(REPO), "fetch", "--depth", "1",
         "origin", BRANCH],
        check=True, env=git_env,
    )
    target = subprocess.check_output(
        ["git", "-C", str(REPO), "rev-parse", "FETCH_HEAD"],
        text=True,
    ).strip()
    subprocess.run(
        ["git", "-C", str(REPO), "checkout", "--detach", target],
        check=True,
    )

head = subprocess.check_output(
    ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True
).strip()
assert not subprocess.check_output(
    ["git", "-C", str(REPO), "status", "--porcelain"], text=True
).strip(), "Checkout RQ2 sporco dopo checkout: STOP"
print("RQ2_GIT_HEAD:", head, flush=True)

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
marker = DEPS / ".rq2_packages_ready"
if not marker.is_file() or marker.read_text().strip() != signature:
    DEPS.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install",
         "--disable-pip-version-check", "--upgrade", "--target", str(DEPS),
         *PINS],
        check=True,
    )
    marker.write_text(signature + "\n", encoding="utf-8")
print("PYTHON_RUNTIME:", sys.version.split()[0], flush=True)

env = dict(os.environ)
env["PYTHONPATH"] = os.pathsep.join((str(DEPS), str(REPO / "src")))
env["PYTHONDONTWRITEBYTECODE"] = "1"
# Nessun client LLM viene creato. Difesa aggiuntiva per i subprocess.
for key in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
    env.pop(key, None)

policy = (
    "from evaluation.rq2_model_factory import assert_exact_runtime_snapshot;"
    "from evaluation.rq2_dryrun_plan import PLAN_STATUS;"
    "from evaluation.rq2_ck_provider_transport import RELEASE_SHA256;"
    "assert_exact_runtime_snapshot();"
    "assert PLAN_STATUS == 'DRAFT_NOT_EXECUTABLE';"
    "assert RELEASE_SHA256 is None;"
    "print('SOURCE_POLICY_AND_CLOSED_GATES_OK')"
)
subprocess.run(
    [sys.executable, "-c", policy],
    cwd=REPO, env=env, check=True,
)

run = subprocess.run(
    [sys.executable, "-m", "evaluation.rq2_discovery_prereg_readiness",
     "--data-dir", str(DATA), "--repo-dir", str(REPO)],
    cwd=REPO, env=env, check=True,
    text=True, capture_output=True,
)
report = json.loads(run.stdout)
assert report["status"] == "REAL_GT_FREE_SOURCE_CHECKED_PREFREEZE_NOT_EXECUTABLE"
assert (report["discovery_stages"], report["test_stages_locked"],
        report["total_stages"]) == (72, 132, 204)
assert (report["discovery_window_groups"],
        report["test_window_groups"]) == (4, 10)
assert report["rq1_13_blob_match"] is True
assert report["release_sha256_pinned_in_production"] is False
assert report["provider_calls_executed"] == 0
assert report["read_ground_truth"] is False
assert report["can_execute_D"] is False
assert report["can_execute_CK"] is False
assert report["can_execute_test"] is False

print("\n=== PREFLIGHT SCIENTIFICO GT-FREE ===")
print(json.dumps(report, indent=2, ensure_ascii=False))
print("\n=== RISULTATO ===")
print("STATUS: OFFLINE_FINAL_PREFLIGHT_OK_RELEASE_NOT_SIGNED")
print("HEAD:", head)
print("REAL_GEMINI_CLAUDE_REQUESTS: 0")
print("TEST_OOD: LOCKED")
```

### Output da inviare all'assistente

Copia **`RQ2_GIT_HEAD`**, `SOURCE_POLICY_AND_CLOSED_GATES_OK`,
il JSON del preflight e la riga
`STATUS: OFFLINE_FINAL_PREFLIGHT_OK_RELEASE_NOT_SIGNED`.
Non inviare chiavi o token, né dump di `record.csv` / GT.

Nota: la CLI `rq2_discovery_prereg_readiness` conserva per design
`effective_Google_SDK_retry_timeout_verified=false` e
`effective_Anthropic_SDK_retry_timeout_verified=false`: tali campi
riflettono lo schema storico della CLI, **non annullano** l'audit
separato SDK/HTTP503 già superato e registrato. La verifica della
factory `assert_exact_runtime_snapshot` qui garantisce soltanto
versioni e SHA attesi; non certifica timeout sotto stallo reale.

### Cosa NON autorizza l'esito

Questo controllo riacquisisce provenienza e identità sul checkout
finale **prima del release**; non modifica
`RELEASE_SHA256=None` o `PLAN_STATUS="DRAFT_NOT_EXECUTABLE"`,
non firma `RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json`, non apre
gli 11 casi test e non dà consenso per il primo stage.
Dopo output positivo: verificare drift/hash, creare release
scientifico **create-only** con `test_unlocked=false`,
verificare readback SHA, e chiedere il consenso specifico
per la prima D Gemini, senza avviare una campagna automatica.
