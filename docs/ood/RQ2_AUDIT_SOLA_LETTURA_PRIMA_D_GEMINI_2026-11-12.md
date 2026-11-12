# RQ2 — Audit di sola lettura dopo la prima D reale Gemini

**12 novembre 2026. Stato: nessun nuovo stage autorizzato o avviato da questa procedura.**

## Evidenza comunicata dall'utente (NON ancora esito diagnostico)

Dopo la prima cella reale autorizzata, l'utente ha riportato:

```text
Drive already mounted at /content/drive
REPO: REUSED
DEPS: REUSED
GIT_HEAD: dbf6ba239e62ba55dfd387e6e7b02dde07d728fd
CREDENTIAL: PRESENT_NOT_PRINTED
AUTHORIZED_ONLY_STAGE: rq2_dryrun_workflow_preview_v0:cloudbed-1_q032:gemini:A1:D
REAL_MODEL: gemini-3.5-flash-lite
REAL_D_INVOCATIONS_FROM_CELL: 1
OTHER_DISCOVERY_STAGES: NOT_LAUNCHED
OOD_TEST: LOCKED
```

**Interpretazione limitata:** il processo esterno di Colab ha osservato il
ritorno del subprocess D con codice 0; l'output riportato non contiene
`RQ2_D_RESULT` né `STATUS: SINGLE_REAL_D_FINISHED_NO_CK_NO_TEST`.
L'assenza di queste righe non dimostra da sola un fallimento, ma
**non autorizza** a dichiarare un risultato diagnostico o a contare
un nuovo stage come completato senza l'archivio. Non eseguire una
seconda D per recuperare l'output della prima: il journal è create-only.

La seguente cella ricostruisce **solo risorse effimere** di Colab quando
necessario, verifica il SHA del release sul Drive e nel checkout Git,
poi usa le funzioni già presenti per convalidare il claim e il record
senza provider, tool, Market.zip, ground truth, predizioni, score o
scritture nel Drive. L'audit stampa **solo metadati**: niente
raw_response, evidenze E###, payload modello o segreti. Il
subprocess viene eseguito con `capture_output=True` per rendere
visibile nel notebook il JSON finale anche se l'output dei
subprocess precedenti non compariva.

## Unica cella Colab — READ ONLY, NO LLM

```python
from pathlib import Path
from google.colab import drive
import hashlib, json, os, subprocess, sys

drive.mount("/content/drive")

REPO = Path("/content/Tesi_OpenRCA_RQ2")
DEPS = Path("/content/rq2_prefreeze_packages_py313")
ROOT = Path("/content/drive/MyDrive/Tesi_OpenRCA")
BRANCH = "feature/ood-knowledge-transfer-audit-2026-11-10"
ORIGIN = "https://github.com/alessio1996A/Tesi_Laurea_Magistrale_OpenRCA.git"
RELEASE_REL = "data/rq2/RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json"
RELEASE_SHA = "a35c02f830a3c5f97424e0cbf8653eda6cfa674b9c8c34d95d04627e1dba8c52"
PIN_BLOB = "84c33c05b198d1dc483f7fef466d8df52942f000"

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

assert sys.version.split()[0] == "3.13.18", "Runtime Python differente: STOP"
assert ROOT.is_dir() and not ROOT.is_symlink(), "Root Drive non trovata/symlink"
assert not REPO.is_symlink() and not DEPS.is_symlink(), "Symlink /content: STOP"

# RECOVERY SOLO DI /content; nessuna scrittura nei dati di Drive.
if not REPO.exists():
    subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch", "--branch",
         BRANCH, ORIGIN, str(REPO)],
        env=dict(os.environ, GIT_TERMINAL_PROMPT="0"), check=True,
    )
    print("REPO: CLONED")
else:
    assert (REPO / ".git").is_dir(), "Directory checkout RQ2 anomala"
    print("REPO: REUSED")

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
        [sys.executable, "-m", "pip", "install",
         "--disable-pip-version-check", "--upgrade",
         "--target", str(DEPS), *PINS],
        check=True,
    )
    marker.write_text(sig + "\n", encoding="utf-8")
    print("DEPS: INSTALLED")
else:
    assert DEPS.is_dir() and marker.is_file() and not marker.is_symlink(), (
        "Dipendenze incomplete/differenti: STOP"
    )
    assert marker.read_text().strip() == sig, "Pacchetti pinned drift: STOP"
    print("DEPS: REUSED")

assert not subprocess.check_output(
    ["git", "-C", str(REPO), "status", "--porcelain"], text=True
).strip(), "Checkout Git non pulito: STOP"
remote = subprocess.check_output(
    ["git", "-C", str(REPO), "remote", "get-url", "origin"], text=True
).strip()
assert remote in (ORIGIN, ORIGIN[:-4]), "Git remote differente"
subprocess.run(
    ["git", "-C", str(REPO), "fetch", "--depth", "1", "origin", BRANCH],
    env=dict(os.environ, GIT_TERMINAL_PROMPT="0"), check=True,
)
head = subprocess.check_output(
    ["git", "-C", str(REPO), "rev-parse", "FETCH_HEAD"], text=True
).strip()
subprocess.run(
    ["git", "-C", str(REPO), "checkout", "--detach", head], check=True,
)
print("GIT_HEAD:", head)
assert subprocess.check_output(
    ["git", "-C", str(REPO), "rev-parse",
     "HEAD:src/evaluation/rq2_ck_provider_transport.py"],
    text=True,
).strip() == PIN_BLOB, "Pinned source drift"

source_release = REPO / RELEASE_REL
drive_release = ROOT / RELEASE_REL
assert source_release.is_file() and not source_release.is_symlink()
assert drive_release.is_file() and not drive_release.is_symlink()
assert sha256(source_release) == sha256(drive_release) == RELEASE_SHA, (
    "Release GitHub/Drive drift: STOP"
)
release = json.loads(drive_release.read_text(encoding="utf-8"))
assert release["test_unlocked"] is False
assert release["live_provider_stage_authorization_granted"] is False

# Ambiente subprocess privo di credenziali e tracing.
env = dict(os.environ)
env["PYTHONPATH"] = os.pathsep.join((str(DEPS), str(REPO / "src")))
env["PYTHONDONTWRITEBYTECODE"] = "1"
for secret in (
    "GOOGLE_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
    "GOOGLE_GENAI_USE_VERTEXAI", "LANGCHAIN_API_KEY",
    "LANGSMITH_API_KEY", "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING",
):
    env.pop(secret, None)

# IMPORTA SOLO JOURNAL/STORE, NON RUNNER LIVE, NON CLIENT GOOGLE.
audit_code = """
import json
from pathlib import Path
from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal
from evaluation.rq2_ck_provider_transport import _read_release

root = Path("/content/drive/MyDrive/Tesi_OpenRCA")
sid = "rq2_dryrun_workflow_preview_v0:cloudbed-1_q032:gemini:A1:D"
release = _read_release(root)
assert release["test_unlocked"] is False
assert release["live_provider_stage_authorization_granted"] is False
journal = RQ2DiscoveryClaimJournal(data_dir=root)
overview = journal.audit_restart()
claim = journal._read_claim(sid)
record = journal.store.load_discovery_stage(stage_id=sid)
if record is not None and claim is None:
    raise RuntimeError("Artifact without preceding claim: STOP")
state = (
    "NO_CLAIM_OR_RECORD" if claim is None
    else "CLAIM_WITHOUT_ARTIFACT" if record is None
    else "CLAIM_AND_ARTIFACT_VERIFIED"
)
safe = {
    "stage_id": sid,
    "state": state,
    "journal_summary": {
        k: overview[k] for k in (
            "claims", "finished_with_matching_result",
            "unresolved_manual_review", "result_archive_discovery_count"
        )
    },
    "claim_sha256": claim["claim_sha256"] if claim else None,
    "artifact_record_sha256": record["record_sha256"] if record else None,
    "stage_status": record["status"] if record else None,
    "model_id": record["model_id_proposed"] if record else None,
    "test_unlocked": release["test_unlocked"],
}
if record is not None:
    artifact = record["artifact"]
    run = artifact.get("diagnostic_run", {})
    metrics = run.get("metrics", {})
    # WHITELIST DI SOLI KPI AGGREGATI, no prompt, no risposte raw, no GT.
    fields = (
        "llm_calls", "tool_rounds", "input_tokens", "output_tokens",
        "total_tokens", "token_usage_complete", "preprocessing_seconds",
        "end_to_end_seconds",
    )
    safe["metrics"] = {
        k: metrics.get(k) for k in fields
        if type(metrics.get(k)) in (int, float, bool)
    }
    safe["original_d_json_status_is_valid"] = (
        run.get("json_status") == "valid_json"
    )
    safe["provider_or_runner_error_present"] = run.get("error") is not None
    safe["tool_trajectory_length"] = (
        len(run["tool_trajectory"])
        if type(run.get("tool_trajectory")) is list else None
    )
    safe["evidence_bundle_present"] = (
        artifact.get("evidence_bundle_sha256") is not None
    )
    safe["trajectory_issue_type"] = artifact.get("tool_trajectory_issue")
print(json.dumps(safe, ensure_ascii=False, indent=2), flush=True)
"""
result = subprocess.run(
    [sys.executable, "-c", audit_code],
    cwd=REPO, env=env, text=True, capture_output=True,
)
if result.returncode != 0:
    print("AUDIT_OFFLINE_SUBPROCESS_FAILED:", result.returncode)
    print("Nessun retry della D. Condividere l'errore di audit, non segreti.")
    raise RuntimeError("L'audit di sola lettura non è riuscito")

data = json.loads(result.stdout)
print("\n=== RQ2 PRIMA D: ARCHIVIO IMMUTABILE ===")
print(json.dumps(data, indent=2, ensure_ascii=False))
print("PROVIDER_API_REQUESTS_FROM_THIS_AUDIT: 0")
print("NO_NEW_CLAIMS_OR_ARTIFACTS_WRITTEN: TRUE")
print("OOD_TEST: LOCKED")
print("STATUS: RQ2_FIRST_D_READ_ONLY_AUDIT_COMPLETE")
```

## Come interpretare l'output

- `CLAIM_AND_ARTIFACT_VERIFIED`: un tentativo D è registrato in modo
  persistente; **solo** il campo `stage_status` distingue
  `RECORDED_COMPLETE`, `PROVIDER_ERROR`, `INVALID_OUTPUT`, ecc.
- `CLAIM_WITHOUT_ARTIFACT`: tentativo avviato e stato ambiguo,
  **NO RETRY**; audit manuale prima di ogni azione.
- `NO_CLAIM_OR_RECORD`: il sistema non ha un record del tentativo
  desiderato; non inferire da ciò che non sia stata fatturata
  una richiesta senza verifica separata; non riavviare automaticamente.
- Il campo `original_d_json_status_is_valid` misura il contratto
  originale D, **non** la correttezza GT; `RECORDED_COMPLETE` significa
  che la traiettoria D è strutturalmente utilizzabile per C, **non**
  che la diagnosi è accurata.
- Questa cella non ha alcun percorso per lanciare LLM, C/K o test OOD.

**Output da inviare:** il solo JSON `RQ2 PRIMA D: ARCHIVIO IMMUTABILE`
e la riga `STATUS`. Non inviare dati raw o segreti.
