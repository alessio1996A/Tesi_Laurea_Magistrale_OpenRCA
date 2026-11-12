# RQ2 Gemini — BATCH 01: 10 stage discovery reali, sequenziali, senza retry

**Data:** 12 novembre 2026. **Stato:** cella preparata, **non eseguita**.
**Autorizzazione in chat:** dopo la prima D reale, l'utente ha confermato
la continuazione e chiesto esplicitamente di eseguire gli esperimenti
in blocchi «anche a 10 e 10» per accelerare. Questa cella limita
rigidamente il batch a dieci stage discovery Gemini, elencati sotto.
Una D può generare più chiamate al provider; 10 stage non equivalgono
a 10 chiamate HTTP e possono comportare costi reali.

**D già completata, NON ripetibile:**
`rq2_dryrun_workflow_preview_v0:cloudbed-1_q032:gemini:A1:D`,
record `73c1006d134ffef5bad7cba380925546c84d58c2ed20ba1730f75f1f42bbdfe7`,
claim `a64b2f3c19e9a179975fa99db31c820fd6840b575b3dc2f42a6fa550e35394f6`.
La D ha 7 invocazioni LLM, 6 round tool, 63.571 token,
41,398 secondi, `RECORDED_COMPLETE` e JSON valido; **non**
costituisce verifica dell'esattezza causale rispetto alla GT.

## Dieci stage autorizzati nel primo batch, in quest'ordine

| # | Caso | Harness | Stage |
|---:|---|---|---|
| 1 | cloudbed-1_q032 | A1 | C |
| 2 | cloudbed-1_q032 | A1 | K |
| 3 | cloudbed-1_q032 | A1_8R | D |
| 4 | cloudbed-1_q032 | A1_8R | C |
| 5 | cloudbed-1_q032 | A1_8R | K |
| 6 | cloudbed-1_q050 | A1 | D |
| 7 | cloudbed-1_q050 | A1 | C |
| 8 | cloudbed-1_q050 | A1 | K |
| 9 | cloudbed-1_q050 | A1_8R | D |
| 10 | cloudbed-1_q050 | A1_8R | C |

Tutti i dieci stage usano `gemini-3.5-flash-lite`. La K di
`cloudbed-1_q050` / `A1_8R` resta per il blocco successivo:
**non verrà lanciata automaticamente come undicesimo stage**.
Il batch successivo è separato e va predisposto dopo aver
letto l'audit di questo blocco.

**Regole immutabili:** source RQ1 non modificato; release scientifico
`a35c02f830a3c5f97424e0cbf8653eda6cfa674b9c8c34d95d04627e1dba8c52`,
`test_unlocked=false`; C usa SOLO evidenze D e non la diagnosi D;
K produce candidati non validati e non esegue pseudocodice; niente GT;
claim e output create-only su Drive; nessuna ripetizione automatica
e nessun retry in caso di crash, errore, risposta non valida o claim
ambiguo. **STOP alla prima failure o status diverso da
`RECORDED_COMPLETE`**, senza passare agli altri stage.
Nessuno dei 132 stage test è coinvolto.

## Segreti Google e come lanciare

Nel pannello **Segreti** di Colab abilitare il nome `GOOGLE_API_KEY`
(o `GEMINI_API_KEY` alternativo). Non incollare la chiave nel notebook
o nella chat. Non avviare due notebook o due batch in parallelo.
Questa cella comporta API REALI e possibili addebiti, non è fake.

**Eseguire la cella UNA sola volta.** Se Colab si disconnette
dopo un claim, **NON rieseguire** la cella. L'audit manuale è obbligatorio
prima di qualsiasi continuazione. Le stampe contengono soltanto
metriche aggregate e hash; non contengono predizioni, raw_response,
ground truth, token segreti o prompt.

## Singola cella Colab — esecuzione reale batch 01 (10 stage max)

~~~python
from pathlib import Path
from google.colab import drive, userdata
import hashlib, json, os, subprocess, sys

ROOT = Path("/content/drive/MyDrive/Tesi_OpenRCA")
REPO = Path("/content/Tesi_OpenRCA_RQ2")
DEPS = Path("/content/rq2_prefreeze_packages_py313")
BRANCH = "feature/ood-knowledge-transfer-audit-2026-11-10"
REMOTE = "https://github.com/alessio1996A/Tesi_Laurea_Magistrale_OpenRCA.git"
SHA = "a35c02f830a3c5f97424e0cbf8653eda6cfa674b9c8c34d95d04627e1dba8c52"
PIN_BLOB = "84c33c05b198d1dc483f7fef466d8df52942f000"
FIRST_D = "rq2_dryrun_workflow_preview_v0:cloudbed-1_q032:gemini:A1:D"
FIRST_RECORD_SHA = "73c1006d134ffef5bad7cba380925546c84d58c2ed20ba1730f75f1f42bbdfe7"
FIRST_CLAIM_SHA = "a64b2f3c19e9a179975fa99db31c820fd6840b575b3dc2f42a6fa550e35394f6"
PREFIX = "rq2_dryrun_workflow_preview_v0:"
MODEL = "gemini-3.5-flash-lite"

# Esattamente 10 stage: nessun altro caso o provider.
STAGES = [
    ( "cloudbed-1_q032", "A1",    "C"),
    ( "cloudbed-1_q032", "A1",    "K"),
    ( "cloudbed-1_q032", "A1_8R", "D"),
    ( "cloudbed-1_q032", "A1_8R", "C"),
    ( "cloudbed-1_q032", "A1_8R", "K"),
    ( "cloudbed-1_q050", "A1",    "D"),
    ( "cloudbed-1_q050", "A1",    "C"),
    ( "cloudbed-1_q050", "A1",    "K"),
    ( "cloudbed-1_q050", "A1_8R", "D"),
    ( "cloudbed-1_q050", "A1_8R", "C"),
]
BATCH = [f"{PREFIX}{case}:gemini:{harness}:{stage}"
         for case, harness, stage in STAGES]
assert len(BATCH) == len(set(BATCH)) == 10
assert FIRST_D not in BATCH

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

drive.mount("/content/drive")
assert sys.version.split()[0] == "3.13.18", "Runtime Python differente: STOP"
assert ROOT.is_dir() and not ROOT.is_symlink(), "Root Drive assente/symlink"
assert (ROOT / "Market.zip").is_file() and not (ROOT / "Market.zip").is_symlink()
assert not REPO.is_symlink() and not DEPS.is_symlink(), "Symlink /content: STOP"

# Recovery solo temporaneo dopo riavvio Colab. Non si cancella Drive.
if not REPO.exists():
    subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch",
         "--branch", BRANCH, REMOTE, str(REPO)],
        env=dict(os.environ, GIT_TERMINAL_PROMPT="0"), check=True,
    )
    print("REPO: CLONED", flush=True)
else:
    assert (REPO / ".git").is_dir(), "Checkout RQ2 esistente non Git: STOP"
    print("REPO: REUSED", flush=True)

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
marker = DEPS / ".rq2_packages_ready"
if not DEPS.exists():
    DEPS.mkdir(parents=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install",
         "--disable-pip-version-check", "--upgrade",
         "--target", str(DEPS), *PINS],
        check=True,
    )
    marker.write_text(signature + "\n", encoding="utf-8")
    print("DEPS: INSTALLED", flush=True)
else:
    assert DEPS.is_dir() and marker.is_file() and not marker.is_symlink()
    assert marker.read_text().strip() == signature, "Package snapshot drift: STOP"
    print("DEPS: REUSED", flush=True)

assert not subprocess.check_output(
    ["git", "-C", str(REPO), "status", "--porcelain"], text=True
).strip(), "Checkout locale modificato: STOP"
origin = subprocess.check_output(
    ["git", "-C", str(REPO), "remote", "get-url", "origin"], text=True
).strip()
assert origin in (REMOTE, REMOTE[:-4]), "Remote Git non atteso"
subprocess.run(
    ["git", "-C", str(REPO), "fetch", "--depth", "1", "origin", BRANCH],
    env=dict(os.environ, GIT_TERMINAL_PROMPT="0"), check=True,
)
head = subprocess.check_output(
    ["git", "-C", str(REPO), "rev-parse", "FETCH_HEAD"], text=True,
).strip()
subprocess.run(["git", "-C", str(REPO), "checkout", "--detach", head], check=True)
assert not subprocess.check_output(
    ["git", "-C", str(REPO), "status", "--porcelain"], text=True
).strip(), "Checkout non pulito dopo fetch: STOP"
print("GIT_HEAD:", head, flush=True)

relpath = "data/rq2/RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json"
assert sha256(REPO / relpath) == sha256(ROOT / relpath) == SHA
release = json.loads((ROOT / relpath).read_text(encoding="utf-8"))
assert release["status"] == "SCIENTIFIC_DISCOVERY_RELEASE"
assert release["test_unlocked"] is False
assert release["live_provider_stage_authorization_granted"] is False
assert release["requires_explicit_confirmation_for_each_stage"] is True
assert release["model_ids"]["gemini"] == MODEL
assert release["first_discovery_D_proposed"]["case_id"] == "cloudbed-1_q032"
assert release["plan_preview_sha256"] == (
    "ecd6d926933a5ad056ad1a581fa7e490c0a13eee18070c7dac8627c1b19c062e"
)

blob = subprocess.check_output(
    ["git", "-C", str(REPO), "rev-parse",
     "HEAD:src/evaluation/rq2_ck_provider_transport.py"], text=True,
).strip()
assert blob == PIN_BLOB, "Changed provider release pin: STOP"

for rel, expected in release["rq2_pre_pin_code_sha256"].items():
    if rel == "evaluation/rq2_ck_provider_transport.py":
        continue  # post-release pin is independently verified above
    path = REPO / "src" / rel
    assert path.is_file() and not path.is_symlink() and sha256(path) == expected, (
        "Source drift: " + rel
    )
for rel, expected in (
    ("data/processed/split_market_v1.csv", release["source_split_sha256"]),
    ("data/processed/benchmark_inputs_market.csv", release["source_manifest_sha256"]),
):
    path = ROOT / rel
    assert path.is_file() and not path.is_symlink() and sha256(path) == expected

# Prefight IN UN PROCESSO SENZA SEGRETI. ZERO richieste API / claim nuovi.
base_env = dict(os.environ)
base_env["PYTHONPATH"] = os.pathsep.join((str(DEPS), str(REPO / "src")))
base_env["PYTHONDONTWRITEBYTECODE"] = "1"
for key in (
    "GOOGLE_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
    "GOOGLE_GENAI_USE_VERTEXAI", "LANGCHAIN_API_KEY", "LANGSMITH_API_KEY",
    "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING",
):
    base_env.pop(key, None)

precheck = """
from pathlib import Path
import sys
from evaluation.rq2_model_factory import assert_exact_runtime_snapshot
from evaluation.rq2_protocol_identity_preflight import preview_protocol_identity
from evaluation.rq2_ck_provider_transport import _read_release
from evaluation.rq2_dryrun_plan import preview_market, PLAN_STATUS
from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal
root = Path("/content/drive/MyDrive/Tesi_OpenRCA")
repo = Path("/content/Tesi_OpenRCA_RQ2")
first = "rq2_dryrun_workflow_preview_v0:cloudbed-1_q032:gemini:A1:D"
assert_exact_runtime_snapshot()
rel = _read_release(root)
assert rel["test_unlocked"] is False
assert PLAN_STATUS == "DRAFT_NOT_EXECUTABLE"
identity = preview_protocol_identity(src_root=repo / "src")
assert identity["rq1_source_blob_sha1_match"] is True
plan = preview_market(root)
assert plan["preview_sha256"] == rel["plan_preview_sha256"]
gemini = [e for e in plan["entries"] if (
    e["phase"] == "discovery" and e["logical_model"] == "gemini"
)]
want = [e["stage_id"] for e in gemini[1:11]]
assert len(gemini) == 24 and gemini[0]["stage_id"] == first
assert sys.argv[1:] == want, "Batch stage order diverged from frozen plan: STOP"
journal = RQ2DiscoveryClaimJournal(data_dir=root)
overview = journal.audit_restart()
assert overview["claims"] == overview["finished_with_matching_result"] == 1
assert overview["result_archive_discovery_count"] == 1
assert overview["unresolved_manual_review"] == 0
claim = journal._read_claim(first)
record = journal.store.load_discovery_stage(stage_id=first)
assert claim is not None and record is not None
assert claim["claim_sha256"] == (
    "a64b2f3c19e9a179975fa99db31c820fd6840b575b3dc2f42a6fa550e35394f6"
)
assert record["record_sha256"] == (
    "73c1006d134ffef5bad7cba380925546c84d58c2ed20ba1730f75f1f42bbdfe7"
)
assert record["status"] == "RECORDED_COMPLETE"
for sid in sys.argv[1:]:
    assert journal._read_claim(sid) is None, "Existing claim: NO RETRY"
    assert journal.store.load_discovery_stage(stage_id=sid) is None, (
        "Existing stage artifact: NO REEXECUTION"
    )
print("BATCH01_PREFLIGHT_OK_10_NEW_STAGES_NO_API", flush=True)
"""
subprocess.run(
    [sys.executable, "-c", precheck, *BATCH],
    cwd=REPO, env=base_env, check=True,
)
print("AUTHORIZED_BATCH01_COUNT: 10", flush=True)
for n, sid in enumerate(BATCH, 1):
    print(f"  {n:02d}/10 {sid}", flush=True)

# Chiave da COLAB SECRETS; non viene mai passata via argv, stampata
# o salvata su Drive/GitHub.
def get_secret(name):
    try:
        return userdata.get(name)
    except Exception:
        return None

key = get_secret("GOOGLE_API_KEY") or get_secret("GEMINI_API_KEY")
if not isinstance(key, str) or not key.strip():
    raise RuntimeError("Abilitare GOOGLE_API_KEY o GEMINI_API_KEY nei Segreti Colab")
paid_env = dict(base_env)
paid_env["GOOGLE_API_KEY"] = key.strip()
paid_env["LANGCHAIN_TRACING_V2"] = "false"
paid_env["LANGSMITH_TRACING"] = "false"
del key
print("GOOGLE_CREDENTIAL: PRESENT_NOT_PRINTED", flush=True)

# Driver di UN SINGOLO stage per processo. Nessun ciclo interno,
# nessuna retry API, nessun richiamo ad altri stage.
# stdout interno del runner viene silenziato per non esporre dati.
driver = """
import contextlib, json, os, sys
from pathlib import Path
from evaluation.rq2_discovery_d_provider_transport import run_one_claimed_discovery_d
from evaluation.rq2_ck_provider_transport import run_one_claimed_ck
from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal

root = Path("/content/drive/MyDrive/Tesi_OpenRCA")
repo = Path("/content/Tesi_OpenRCA_RQ2")
sid = sys.argv[1]
try:
    with open(os.devnull, "w") as silent, contextlib.redirect_stdout(silent):
        if sid.endswith(":D"):
            receipt = run_one_claimed_discovery_d(
                data_dir=root, repo_dir=repo, stage_id=sid,
                confirm_paid_api=True
            )
            metrics = receipt["observed_run_metrics"]
            usage = {
                k: metrics[k] for k in (
                    "llm_calls", "tool_rounds", "input_tokens", "output_tokens",
                    "total_tokens", "token_usage_complete", "end_to_end_seconds"
                ) if k in metrics and type(metrics[k]) in (int, float, bool)
            }
        elif sid.endswith((":C", ":K")):
            receipt = run_one_claimed_ck(
                data_dir=root, stage_id=sid, confirm_paid_api=True
            )
            usage = {
                k: v for k, v in receipt["usage"].items()
                if k in ("complete", "input_tokens", "output_tokens", "total_tokens")
                and type(v) in (int, bool)
            }
        else:
            raise ValueError("Unsupported stage")
    journal = RQ2DiscoveryClaimJournal(data_dir=root)
    recorded = journal.store.load_discovery_stage(stage_id=sid)
    claim = journal._read_claim(sid)
    assert recorded is not None and claim is not None
    assert recorded["record_sha256"] == receipt["record_sha256"]
    assert recorded["status"] == receipt["status"]
    state = journal.audit_restart()
    assert state["unresolved_manual_review"] == 0
    print("RQ2_BATCH_STAGE_RESULT:" + json.dumps({
        "stage_id": sid, "status": receipt["status"],
        "record_sha256": receipt["record_sha256"],
        "claim_sha256": claim["claim_sha256"],
        "metrics": usage,
        "completed_claims": state["finished_with_matching_result"],
        "unresolved": state["unresolved_manual_review"],
        "ood_test_locked": True,
    }, ensure_ascii=False, allow_nan=False), flush=True)
except BaseException as exc:
    # Errore tipizzato, NO messaggi di eccezione o traceback con segreti.
    print("RQ2_BATCH_STAGE_ERROR:" + json.dumps({
        "stage_id": sid, "error_type": type(exc).__name__,
        "action": "STOP_NO_RETRY_MANUAL_AUDIT",
    }), flush=True)
    raise SystemExit(2)
"""

# Unico ciclo sequenziale, al massimo 10 stage specificati sopra.
# Se uno stage non è RECORDED_COMPLETE, fermarsi anche se ha salvato
# un artefatto di failure. NON saltarlo e NON ritentarlo.
finished = []
for i, sid in enumerate(BATCH, 1):
    print(f"\n=== REAL STAGE {i}/10: {sid} ===", flush=True)
    completed = subprocess.run(
        [sys.executable, "-c", driver, sid],
        cwd=REPO, env=paid_env,
        text=True, capture_output=True,
    )
    lines = completed.stdout.splitlines()
    safe_results = [line[len("RQ2_BATCH_STAGE_RESULT:"):]
                    for line in lines if line.startswith("RQ2_BATCH_STAGE_RESULT:")]
    safe_errors = [line[len("RQ2_BATCH_STAGE_ERROR:"):]
                   for line in lines if line.startswith("RQ2_BATCH_STAGE_ERROR:")]
    if completed.returncode != 0 or len(safe_results) != 1 or safe_errors:
        for error in safe_errors:
            print("BATCH_STAGE_ERROR:", error, flush=True)
        print("BATCH01_STOP_NO_RETRY_MANUAL_AUDIT_REQUIRED", flush=True)
        # Never print unfiltered stdout/stderr, prompts or credential context.
        raise RuntimeError("Batch stopped; preserve claims, do not rerun")
    result = json.loads(safe_results[0])
    assert result["stage_id"] == sid
    finished.append(result)
    print("BATCH_STAGE:", json.dumps(result, ensure_ascii=False), flush=True)
    if result["status"] != "RECORDED_COMPLETE":
        print("BATCH01_STOP_NONCOMPLETE_NO_RETRY", flush=True)
        raise RuntimeError("Noncomplete stage; audit before any further stage")
print("\nSTATUS: BATCH01_10_REAL_DISCOVERY_STAGES_COMPLETED")
print("BATCH01_COMPLETED_COUNT:", len(finished))
print("OTHER_STAGES: NOT_LAUNCHED")
print("OOD_TEST: LOCKED")
# No further API calls. Secret was never displayed or stored.
paid_env.pop("GOOGLE_API_KEY", None)
~~~

## Invio dell'output

Se tutti e dieci sono `RECORDED_COMPLETE`, condividere
le dieci righe `BATCH_STAGE` e il riepilogo
`STATUS: BATCH01_10_REAL_DISCOVERY_STAGES_COMPLETED`.
Se l'esecuzione si interrompe, condividere **solo**
`BATCH01_STOP_...` e le righe `BATCH_STAGE` già stampate;
non ripetere la cella. Si effettua **audit offline** del Drive
per ricostruire i claim e i risultati (inclusi gli errori).
Non condividere la chiave, le risposte raw o la ground truth.

**Nessuna ripetizione di unit test già verdi**: la cella è un
orchestratore operativo isolato e non modifica il codice
del protocollo RQ1/RQ2, lo scoring, le etichette o il release.
I 23 stage Gemini discovery residui si suddividono ex ante in
blocchi massimi 10+10+3; il blocco 02 **non** parte
automaticamente dopo il blocco 01.
