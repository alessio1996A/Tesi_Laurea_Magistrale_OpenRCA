# RQ2 — Verifica mirata dopo pin del release scientifico (senza API)

**Data 12 novembre 2026 — RELEASE SU DRIVE CON SHA-256 VERIFICATO;
PIN CODICE RQ2 APPLICATO, API NON AUTORIZZATE; OOD TEST BLOCCATI.**

## Evidenze acquisite e perimetro

L'utente ha eseguito in Colab la cella di recovery e installazione:
`GIT_HEAD=46894101e4b72676064cf2b54b217d14ce07019e`,
`REPO: CLONED`, `DEPS: INSTALLED`, Python `3.13.18`,
`CREATE_ONLY: file created` e
`STATUS: RELEASE_DRIVE_READBACK_VERIFIED_API_NOT_AUTHORIZED`.
L'impronta letta dal Drive corrisponde a quella del release GitHub:
`a35c02f830a3c5f97424e0cbf8653eda6cfa674b9c8c34d95d04627e1dba8c52`.
Il report utente dichiara zero API e test OOD chiusi.

Il pin esatto è stato introdotto **solo** in
`src/evaluation/rq2_ck_provider_transport.py` nel commit
`0d0bf949d483646ea17af1650b95b1c02d85d957`.
Nuovo Git blob SHA-1 del solo file:
`84c33c05b198d1dc483f7fef466d8df52942f000`.
Le altre dodici SHA-256 del manifesto release sono quelle
pre-pin e devono rimanere identiche. Il digest pre-pin della
`rq2_ck_provider_transport.py` **non** deve essere confrontato
contro il file corrente: è cambiato intenzionalmente per introdurre
la costante. Non modificare il release firmato per "aggiornare" quel
digest: è testimonianza del checkout originale, e questa differenza
è documentata.

## 1. PyCharm: pull e controllo della sola modifica del pin

Nel terminale PowerShell dalla root del repository:

```powershell
git status --short
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
git rev-parse HEAD
git rev-parse HEAD:src/evaluation/rq2_ck_provider_transport.py
```

Il risultato di `git rev-parse HEAD:...` deve essere (hash del blob Git versionato, indipendente da eventuali conversioni CRLF nel working tree Windows):
`84c33c05b198d1dc483f7fef466d8df52942f000`.
Se il primo comando mostra modifiche locali da preservare,
fermarsi prima del pull. **Non ripetere** le 53 verifiche
già positive; questo è un controllo di identità del nuovo pin.

## 2. Colab: unica cella di verifica OFFLINE post-pin

La cella sotto ripristina repository e dipendenze pinned solo se
mancano da `/content`, senza cancellare cartelle preesistenti;
verifica il release in repository e su Drive, la nuova impronta
di `rq2_ck_provider_transport.py` e quelle dei 12 file non modificati,
esegue il vero `_read_release` **senza chiamare modelli**,
e verifica che D/C/K rifiutino la chiamata senza consenso.
I processi di validazione non ricevono chiavi API.
Non esegue nuovi test di modellazione, né suite, né letture
di GT/Market.zip/predizioni/claim.

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
PIN_COMMIT = "0d0bf949d483646ea17af1650b95b1c02d85d957"
PIN_GIT_BLOB = "84c33c05b198d1dc483f7fef466d8df52942f000"
EXPECTED = "a35c02f830a3c5f97424e0cbf8653eda6cfa674b9c8c34d95d04627e1dba8c52"
RELEASE_REL = "data/rq2/RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json"

def file_sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

assert sys.version.split()[0] == "3.13.18", "Python runtime drift: STOP"
assert not REPO.is_symlink() and not DEPS.is_symlink(), "Symlink path: STOP"
if not REPO.exists():
    subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch",
         "--branch", BRANCH, URL, str(REPO)],
        env=dict(os.environ, GIT_TERMINAL_PROMPT="0"), check=True,
    )
    print("CHECKOUT: CLONED")
else:
    assert (REPO / ".git").is_dir(), "Directory Git RQ2 non valida: STOP"
    print("CHECKOUT: REUSED")

PINS = [
    "langchain==1.4.7", "langchain-core==1.7.1",
    "langgraph==1.2.18", "langchain-google-genai==4.4.2",
    "langchain-anthropic==1.7.7", "google-genai==2.34.0",
    "anthropic==2.6.0", "google-auth==2.56.0",
    "pandas", "networkx", "python-dotenv",
]
sig = hashlib.sha256(
    ("\n".join(PINS) + "\n" + sys.version).encode("utf-8")
).hexdigest()
marker = DEPS / ".rq2_packages_ready"
if not DEPS.exists():
    DEPS.mkdir(parents=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
         "--upgrade", "--target", str(DEPS), *PINS],
        check=True,
    )
    marker.write_text(sig + "\n", encoding="utf-8")
    print("DEPENDENCIES: INSTALLED")
else:
    assert DEPS.is_dir() and marker.is_file() and not marker.is_symlink()
    assert marker.read_text().strip() == sig, "Pinned deps drift: STOP"
    print("DEPENDENCIES: REUSED")

assert not subprocess.check_output(
    ["git", "-C", str(REPO), "status", "--porcelain"], text=True
).strip(), "Dirty checkout: STOP"
origin = subprocess.check_output(
    ["git", "-C", str(REPO), "remote", "get-url", "origin"], text=True
).strip()
assert origin in (URL, URL[:-4]), "Unexpected Git origin: STOP"
subprocess.run(
    ["git", "-C", str(REPO), "fetch", "--depth", "1", "origin", BRANCH],
    env=dict(os.environ, GIT_TERMINAL_PROMPT="0"), check=True
)
head = subprocess.check_output(
    ["git", "-C", str(REPO), "rev-parse", "FETCH_HEAD"], text=True
).strip()
subprocess.run(["git", "-C", str(REPO), "checkout", "--detach", head], check=True)
assert not subprocess.check_output(
    ["git", "-C", str(REPO), "status", "--porcelain"], text=True
).strip(), "Dirty post-fetch checkout"
print("GIT_HEAD:", head)

blob = subprocess.check_output(
    ["git", "-C", str(REPO), "rev-parse",
     "HEAD:src/evaluation/rq2_ck_provider_transport.py"], text=True
).strip()
assert blob == PIN_GIT_BLOB, "Source pin blob mismatch: STOP"
assert file_sha256(REPO / RELEASE_REL) == EXPECTED
assert file_sha256(DATA / RELEASE_REL) == EXPECTED

r = json.loads((DATA / RELEASE_REL).read_text(encoding="utf-8"))
assert r["status"] == "SCIENTIFIC_DISCOVERY_RELEASE"
assert r["test_unlocked"] is False
assert r["live_provider_stage_authorization_granted"] is False
for rel, expected_hash in r["rq2_pre_pin_code_sha256"].items():
    if rel == "evaluation/rq2_ck_provider_transport.py":
        continue  # exactly one intentional post-pin source drift
    f = REPO / "src" / rel
    assert f.is_file() and not f.is_symlink(), rel
    assert file_sha256(f) == expected_hash, "RQ2 source drift: " + rel

env = dict(os.environ)
env["PYTHONPATH"] = os.pathsep.join((str(DEPS), str(REPO / "src")))
env["PYTHONDONTWRITEBYTECODE"] = "1"
for secret in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
    env.pop(secret, None)
code = (
    "from pathlib import Path;"
    "from inspect import signature;"
    "from evaluation.rq2_model_factory import assert_exact_runtime_snapshot;"
    "from evaluation.rq2_dryrun_plan import PLAN_STATUS;"
    "from evaluation.rq2_ck_provider_transport import "
    "RELEASE_SHA256, _read_release, run_one_claimed_ck, RQ2LiveCKBlocked;"
    "from evaluation.rq2_discovery_d_provider_transport import "
    "run_one_claimed_discovery_d, RQ2LiveDBlocked;"
    "assert_exact_runtime_snapshot();"
    "assert RELEASE_SHA256 == '" + EXPECTED + "';"
    "assert PLAN_STATUS == 'DRAFT_NOT_EXECUTABLE';"
    "r = _read_release(Path(" + repr(str(DATA)) + "));"
    "assert r['test_unlocked'] is False;"
    "assert r['live_provider_stage_authorization_granted'] is False;"
    "assert signature(run_one_claimed_discovery_d).parameters"
    "['confirm_paid_api'].default is False;"
    "assert signature(run_one_claimed_ck).parameters"
    "['confirm_paid_api'].default is False;"
    "stage = 'rq2_dryrun_workflow_preview_v0:cloudbed-1_q032:gemini:A1:D'\n"
    "try:\n"
    " run_one_claimed_discovery_d(data_dir=Path("
      + repr(str(DATA)) + "),repo_dir=Path("
      + repr(str(REPO)) + "),stage_id=stage)\n"
    "except RQ2LiveDBlocked:\n pass\n"
    "else:\n raise AssertionError('D accepted missing consent')\n"
    "try:\n"
    " run_one_claimed_ck(data_dir=Path("
      + repr(str(DATA)) + "),stage_id=stage[:-1]+'C')\n"
    "except RQ2LiveCKBlocked:\n pass\n"
    "else:\n raise AssertionError('C/K accepted missing consent')\n"
    "print('RELEASE_PIN_READBACK_AND_NO_CONSENT_GATES_OK')"
)
subprocess.run([sys.executable, "-c", code], cwd=REPO, env=env, check=True)
print("RELEASE_SHA256:", EXPECTED)
print("TEST_OOD: LOCKED")
print("LIVE_PROVIDER_REQUESTS: 0")
print("STATUS: RQ2_POST_PIN_OFFLINE_GATES_VERIFIED")
```

Riportare: `GIT_HEAD`,
`RELEASE_PIN_READBACK_AND_NO_CONSENT_GATES_OK`,
`RELEASE_SHA256` e `STATUS`.
Un errore interrompe la procedura: non fare tentativi API o
sovrascritture su Drive.

**Questo controllo è necessario solo perché abbiamo applicato il
nuovo pin. Non ripete la precedente suite sintetica o il fake HTTP.**
Dopo il suo esito positivo, l'assistente richiederà l'autorizzazione
**separata e specifica** a una sola D Gemini su
`cloudbed-1_q032` / `A1`; l'esecuzione potrà
essere avviata esclusivamente con un successivo comando di Colab
dedicato. Il release con `test_unlocked=false` non deve
essere modificato.
