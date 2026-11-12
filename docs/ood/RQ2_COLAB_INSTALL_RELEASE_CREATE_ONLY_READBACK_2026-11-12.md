# RQ2 — Installazione create-only e readback scientific release su Drive

Data 12 novembre 2026. Il release create-only e stato creato su GitHub
nel commit b1d3aa4f67e9ce3c63cf5bc76c40ac9b7953b33e.
SHA-256 esatto del JSON, gia riletto da GitHub:
a35c02f830a3c5f97424e0cbf8653eda6cfa674b9c8c34d95d04627e1dba8c52.

**Correzione 12/11 dopo riavvio Colab:** la versione precedente si arrestava alla riga `Restore RQ2 checkout/deps first` perché il runtime non conservava una o entrambe le directory temporanee in `/content`. Nessun dato Drive o release è stato alterato da quell'errore. La nuova cella effettua clone e installazione dei pacchetti pinned **solo quando mancano**, verifica il runtime Python 3.13.18, non sovrascrive directory locali ambigue e poi esegue gli stessi controlli offline del release.

Questa procedura NON esegue chiamate ai provider, NON crea claim,
NON modifica RQ1, NON ripete le suite PyCharm e NON sblocca gli 11 casi OOD.
Lo stage iniziale Gemini resta non autorizzato. Il pin sorgente e ancora None.

## Passo PyCharm

Aggiornare il branch dopo aver verificato che git status --short
sia pulito. Non ripetere i 53 test gia superati.

## Una cella Colab autosufficiente: ripristino temporaneo, installazione e readback

~~~
from pathlib import Path
from google.colab import drive
import hashlib, json, os, subprocess, sys

drive.mount("/content/drive")
REPO = Path("/content/Tesi_OpenRCA_RQ2")
DATA = Path("/content/drive/MyDrive/Tesi_OpenRCA")
DEPS = Path("/content/rq2_prefreeze_packages_py313")
BRANCH = "feature/ood-knowledge-transfer-audit-2026-11-10"
URL = "https://github.com/alessio1996A/Tesi_Laurea_Magistrale_OpenRCA.git"
NAME = "RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json"
EXPECTED = "a35c02f830a3c5f97424e0cbf8653eda6cfa674b9c8c34d95d04627e1dba8c52"
SOURCE = "792dd97e5beefda8ed1c86aa39410115e419432b"

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

# Ripristino automatico e fail-closed delle sole risorse TEMPORANEE /content.
# Non tocca dati sperimentali né release sul Drive.
print("=== [1/4] CHECKOUT RQ2 ===", flush=True)
assert not REPO.is_symlink(), "Il path del checkout RQ2 è un symlink: STOP"
if not REPO.exists():
    subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch",
         "--branch", BRANCH, URL, str(REPO)],
        env=dict(os.environ, GIT_TERMINAL_PROMPT="0"),
        check=True,
    )
    print("REPO: CLONED", flush=True)
elif not (REPO / ".git").is_dir():
    raise RuntimeError(
        "La cartella RQ2 esiste ma NON contiene .git: verifica manuale, NON cancellare"
    )
else:
    print("REPO: EXISTING", flush=True)

print("=== [2/4] DIPENDENZE PINNED ===", flush=True)
assert sys.version.split()[0] == "3.13.18", (
    "Versione Python Colab diversa dal runtime preregistrato: STOP"
)
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
assert not DEPS.is_symlink(), "Il path delle dipendenze è un symlink: STOP"
if not DEPS.exists():
    DEPS.mkdir(parents=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install",
         "--disable-pip-version-check",
         "--upgrade", "--target", str(DEPS), *PINS],
        check=True,
    )
    marker.write_text(signature + "\n", encoding="utf-8")
    print("DEPS: INSTALLED", flush=True)
elif (not DEPS.is_dir() or not marker.is_file()
      or marker.is_symlink() or marker.read_text().strip() != signature):
    raise RuntimeError(
        "Target dipendenze esistente ma incompleto/diverso: STOP, audit manuale"
    )
else:
    print("DEPS: REUSED", flush=True)
print("PYTHON_RUNTIME:", sys.version.split()[0], flush=True)

print("=== [3/4] VERIFICA SORGENTI E RELASE ===", flush=True)
assert (REPO / ".git").is_dir() and DEPS.is_dir(), (
    "Ripristino checkout/dipendenze non completato"
)
assert not subprocess.check_output(
    ["git", "-C", str(REPO), "status", "--porcelain"], text=True
).strip(), "Dirty Git worktree: STOP"
origin = subprocess.check_output(
    ["git", "-C", str(REPO), "remote", "get-url", "origin"], text=True
).strip()
assert origin in (URL, URL[:-4]), "Unexpected Git remote"
subprocess.run(
    ["git", "-C", str(REPO), "fetch", "--depth", "1", "origin", BRANCH],
    env=dict(os.environ, GIT_TERMINAL_PROMPT="0"), check=True
)
head = subprocess.check_output(
    ["git", "-C", str(REPO), "rev-parse", "FETCH_HEAD"], text=True
).strip()
subprocess.run(
    ["git", "-C", str(REPO), "checkout", "--detach", head], check=True
)
assert not subprocess.check_output(
    ["git", "-C", str(REPO), "status", "--porcelain"], text=True
).strip(), "Dirty checkout after fetch"
print("GIT_HEAD:", head)

source_file = REPO / "data/rq2" / NAME
assert source_file.is_file() and not source_file.is_symlink()
assert digest(source_file) == EXPECTED, "GitHub release byte drift"
release = json.loads(source_file.read_text(encoding="utf-8"))
assert release["status"] == "SCIENTIFIC_DISCOVERY_RELEASE"
assert release["test_unlocked"] is False
assert release["live_provider_stage_authorization_granted"] is False
assert release["source_checkout_commit_pre_release"] == SOURCE
assert release["plan_preview_sha256"] == (
    "ecd6d926933a5ad056ad1a581fa7e490c0a13eee18070c7dac8627c1b19c062e"
)

for rel, sha in release["rq2_pre_pin_code_sha256"].items():
    source = REPO / "src" / rel
    assert source.is_file() and not source.is_symlink(), rel
    assert digest(source) == sha, "Source drift: " + rel
for rel, expected in (
    ("data/processed/split_market_v1.csv", release["source_split_sha256"]),
    ("data/processed/benchmark_inputs_market.csv",
     release["source_manifest_sha256"]),
):
    p = DATA / rel
    assert p.is_file() and not p.is_symlink(), rel
    assert digest(p) == expected, "GT-free CSV drift: " + rel

env = dict(os.environ)
env["PYTHONPATH"] = os.pathsep.join((str(DEPS), str(REPO / "src")))
env["PYTHONDONTWRITEBYTECODE"] = "1"
for secret in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
    env.pop(secret, None)

precheck = (
    "from evaluation.rq2_model_factory import assert_exact_runtime_snapshot;"
    "from evaluation.rq2_ck_provider_transport import RELEASE_SHA256;"
    "from evaluation.rq2_dryrun_plan import PLAN_STATUS;"
    "assert_exact_runtime_snapshot();"
    "assert RELEASE_SHA256 is None;"
    "assert PLAN_STATUS == 'DRAFT_NOT_EXECUTABLE';"
    "print('RUNTIME_POLICY_OK_GATES_CLOSED')"
)
subprocess.run([sys.executable, "-c", precheck], cwd=REPO, env=env, check=True)

folder = DATA / "data/rq2"
assert not folder.is_symlink(), "Symlink in destination"
folder.mkdir(parents=True, exist_ok=True)
assert folder.is_dir() and not folder.is_symlink()
dest = folder / NAME
if dest.exists() or dest.is_symlink():
    assert dest.is_file() and not dest.is_symlink()
    assert digest(dest) == EXPECTED, "Existing different release: MANUAL AUDIT"
    print("CREATE_ONLY: existing matching file, no overwrite")
else:
    # Exclusive-create prevents overwriting any prior release.
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(source_file.read_bytes())
        f.flush()
        os.fsync(f.fileno())
    print("CREATE_ONLY: file created")
assert digest(dest) == EXPECTED, "Drive readback mismatch"

# Validate the existing runtime release schema with an IN-MEMORY pin only.
# No source code modification, no provider instantiation, no API.
validation = (
    "from pathlib import Path;"
    "import evaluation.rq2_ck_provider_transport as t;"
    "assert t.RELEASE_SHA256 is None;"
    "t.RELEASE_SHA256 = '" + EXPECTED + "';"
    "r = t._read_release(Path(" + repr(str(DATA)) + "));"
    "assert r['test_unlocked'] is False;"
    "assert r['live_provider_stage_authorization_granted'] is False;"
    "print('RELEASE_CONTRACT_READBACK_OK')"
)
subprocess.run([sys.executable, "-c", validation], cwd=REPO, env=env, check=True)
print("RELEASE_SHA256:", EXPECTED)
print("REAL_API_CALLS: 0")
print("OOD_TEST: LOCKED")
print("SOURCE_RELEASE_PIN: STILL_NONE")
print("STATUS: RELEASE_DRIVE_READBACK_VERIFIED_API_NOT_AUTHORIZED")
~~~

Riportare all'assistente GIT_HEAD, CREATE_ONLY, RELEASE_CONTRACT_READBACK_OK,
RELEASE_SHA256 e la riga STATUS. Se emerge mismatch o errore: STOP,
nessun secondo release e nessuna sovrascrittura manuale.

## Passo successivo

Dopo readback positivo, applicare su GitHub il pin esatto del release
soltanto in codice RQ2. Fare una verifica di regressione MIRATA
del nuovo pin, non rifare i test vecchi. Il piano draft resta
non-dispatchable. Richiedere l'autorizzazione esplicita al primo
singolo stage Gemini D solo dopo questo passaggio.
