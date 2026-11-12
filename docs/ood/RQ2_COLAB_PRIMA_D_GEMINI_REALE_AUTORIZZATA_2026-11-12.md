# RQ2 — Prima D discovery Gemini reale, singolo stage autorizzato

**Data:** 12 novembre 2026. **Stato:** cella preparata; **NON eseguita**.
**Autorizzazione specifica dell'utente:** «Autorizzo esplicitamente una sola
esecuzione reale RQ2 discovery: provider Google, modello
gemini-3.5-flash-lite, caso cloudbed-1_q032, harness A1, stage D. [...]
Prepara la cella Colab GitHub [...] con claim create-only e senza avviare
automaticamente altri stage».

La presente cella **non è un preflight sintetico**. La sua esecuzione
con una chiave Google valida può chiamare realmente l'API Gemini ed
essere fatturata. Una **D logica** può comportare più richieste LLM,
fino ai round consentiti dal runner RQ1; non equivale a una richiesta
HTTP. **Non** esegue le fasi C/K, né altri incidenti né alcuno degli
11 casi test OOD. La politica RQ2-only ha un solo tentativo HTTP per
ogni chiamata Gemini nel percorso sync pinned e timeout candidato di
300 secondi **per richiesta**, non per l'intera D. Le verifiche offline
precedenti non garantiscono l'esito remoto o i timeout sotto stallo.

## Identità scientifica immutabile

- Branch: feature/ood-knowledge-transfer-audit-2026-11-10.
- Commit Git sorgente precedente alla cella: ebebe2ca843ce0e0ae3025c564028657ffa979a9
  (la cella documentale aggiorna solo docs).
- Release: data/rq2/RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json.
- Release SHA-256: a35c02f830a3c5f97424e0cbf8653eda6cfa674b9c8c34d95d04627e1dba8c52.
- File Python post-pin: src/evaluation/rq2_ck_provider_transport.py.
- Git blob SHA-1 post-pin: 84c33c05b198d1dc483f7fef466d8df52942f000.
- Stage ID: rq2_dryrun_workflow_preview_v0:cloudbed-1_q032:gemini:A1:D.
- Originali GT-free: data/processed/split_market_v1.csv e
  data/processed/benchmark_inputs_market.csv su Drive, con hash release.
- Telemetria D: Market.zip su Drive, senza file di ground truth.
- Destinazioni RQ2 create-only su Drive:
  data/rq2/stage_claims_v0/ e data/rq2/stage_artifacts_v0/.
- RQ1: graph, runner, tools, harness e 13 sorgenti frozen invariati.
- Le chiavi **non sono mai scritte su GitHub, Drive, nei report o nell'output**.

## Prima dell'esecuzione

Nel notebook Google Colab aprire il pannello **Segreti** (icona chiave):
creare o abilitare l'accesso a un segreto chiamato GOOGLE_API_KEY.
La cella accetta anche GEMINI_API_KEY come nome alternativo, ma passa
il valore al subprocess come GOOGLE_API_KEY; non stampare né incollare
il valore nella chat. Verificare che la chiave appartenga al progetto
Google che si intende utilizzare. Non eseguire la cella in parallelo
o due volte. Non interrompere il runtime dopo la creazione del claim.
Un eventuale claim privo di risultato resta in audit manuale.

## Una sola cella Colab, da eseguire una volta

~~~python
from pathlib import Path
from google.colab import drive, userdata
import hashlib, json, os, subprocess, sys

# UNICO stage autorizzato, fissato ex ante: NON parametrizzare con altri casi.
ROOT = Path("/content/drive/MyDrive/Tesi_OpenRCA")
REPO = Path("/content/Tesi_OpenRCA_RQ2")
DEPS = Path("/content/rq2_prefreeze_packages_py313")
BRANCH = "feature/ood-knowledge-transfer-audit-2026-11-10"
ORIGIN = "https://github.com/alessio1996A/Tesi_Laurea_Magistrale_OpenRCA.git"
STAGE = "rq2_dryrun_workflow_preview_v0:cloudbed-1_q032:gemini:A1:D"
MODEL_ID = "gemini-3.5-flash-lite"
RELEASE = "data/rq2/RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json"
RELEASE_SHA = "a35c02f830a3c5f97424e0cbf8653eda6cfa674b9c8c34d95d04627e1dba8c52"
PIN_BLOB = "84c33c05b198d1dc483f7fef466d8df52942f000"

def file_sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for buf in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(buf)
    return h.hexdigest()

drive.mount("/content/drive")
assert sys.version.split()[0] == "3.13.18", "Python Colab diverso dal runtime pinned"
assert ROOT.is_dir() and not ROOT.is_symlink(), "Data root Drive mancante/symlink"
assert (ROOT / "Market.zip").is_file() and not (ROOT / "Market.zip").is_symlink(), (
    "Market.zip originale non disponibile su Drive"
)
assert not REPO.is_symlink() and not DEPS.is_symlink(), "Symlink locale non consentito"

# Recovery delle sole directory TEMPORANEE /content, senza toccare Drive.
if not REPO.exists():
    subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch", "--branch",
         BRANCH, ORIGIN, str(REPO)],
        env=dict(os.environ, GIT_TERMINAL_PROMPT="0"), check=True,
    )
    print("REPO: CLONED", flush=True)
else:
    assert (REPO / ".git").is_dir(), "Checkout non Git: STOP"
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
    assert DEPS.is_dir() and marker.is_file() and not marker.is_symlink(), (
        "Dipendenze esistenti non certificate: STOP"
    )
    assert marker.read_text().strip() == signature, "Drift delle dipendenze: STOP"
    print("DEPS: REUSED", flush=True)

assert not subprocess.check_output(
    ["git", "-C", str(REPO), "status", "--porcelain"], text=True
).strip(), "Checkout modificato: STOP"
remote = subprocess.check_output(
    ["git", "-C", str(REPO), "remote", "get-url", "origin"], text=True
).strip()
assert remote in (ORIGIN, ORIGIN[:-4]), "Remote Git inatteso: STOP"
subprocess.run(
    ["git", "-C", str(REPO), "fetch", "--depth", "1", "origin", BRANCH],
    env=dict(os.environ, GIT_TERMINAL_PROMPT="0"), check=True,
)
head = subprocess.check_output(
    ["git", "-C", str(REPO), "rev-parse", "FETCH_HEAD"], text=True
).strip()
subprocess.run(["git", "-C", str(REPO), "checkout", "--detach", head], check=True)
assert not subprocess.check_output(
    ["git", "-C", str(REPO), "status", "--porcelain"], text=True
).strip(), "Checkout post-fetch modificato: STOP"
print("GIT_HEAD:", head, flush=True)

# Confronta file release bytes su GitHub e Drive, NO modifiche a file firmati.
source_release = REPO / RELEASE
drive_release = ROOT / RELEASE
assert source_release.is_file() and not source_release.is_symlink()
assert drive_release.is_file() and not drive_release.is_symlink()
assert file_sha256(source_release) == RELEASE_SHA, "Release GitHub alterato"
assert file_sha256(drive_release) == RELEASE_SHA, "Release Drive alterato"
frozen = json.loads(drive_release.read_text(encoding="utf-8"))
assert frozen["status"] == "SCIENTIFIC_DISCOVERY_RELEASE"
assert frozen["test_unlocked"] is False
assert frozen["live_provider_stage_authorization_granted"] is False
assert frozen["first_discovery_D_proposed"] == {
    "case_id": "cloudbed-1_q032", "logical_model": "gemini",
    "harness": "A1", "stage": "D", "authorized": False,
}
assert frozen["model_ids"]["gemini"] == MODEL_ID
assert frozen["plan_preview_sha256"] == (
    "ecd6d926933a5ad056ad1a581fa7e490c0a13eee18070c7dac8627c1b19c062e"
)
pin_blob = subprocess.check_output(
    ["git", "-C", str(REPO), "rev-parse",
     "HEAD:src/evaluation/rq2_ck_provider_transport.py"], text=True
).strip()
assert pin_blob == PIN_BLOB, "Sorgente pin differente"
for rel, expected in frozen["rq2_pre_pin_code_sha256"].items():
    if rel == "evaluation/rq2_ck_provider_transport.py":
        continue  # unica variazione intenzionale post-release
    p = REPO / "src" / rel
    assert p.is_file() and not p.is_symlink(), "Sorgente mancante: " + rel
    assert file_sha256(p) == expected, "Drift sorgente RQ2: " + rel
for rel, expected in (
    ("data/processed/split_market_v1.csv", frozen["source_split_sha256"]),
    ("data/processed/benchmark_inputs_market.csv",
     frozen["source_manifest_sha256"]),
):
    p = ROOT / rel
    assert p.is_file() and not p.is_symlink(), "CSV GT-free assente: " + rel
    assert file_sha256(p) == expected, "Drift CSV GT-free: " + rel

# La prima verifica opera SENZA chiavi, API, claim o tool. Fail closed.
pre_env = dict(os.environ)
pre_env["PYTHONPATH"] = os.pathsep.join((str(DEPS), str(REPO / "src")))
pre_env["PYTHONDONTWRITEBYTECODE"] = "1"
for k in (
    "GOOGLE_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
    "GOOGLE_GENAI_USE_VERTEXAI", "LANGCHAIN_API_KEY", "LANGSMITH_API_KEY",
    "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING",
):
    pre_env.pop(k, None)

preflight_code = """
from pathlib import Path
from evaluation.rq2_ck_provider_transport import _read_release, RELEASE_SHA256
from evaluation.rq2_dryrun_plan import preview_market, PLAN_STATUS
from evaluation.rq2_model_factory import assert_exact_runtime_snapshot
from evaluation.rq2_protocol_identity_preflight import preview_protocol_identity
from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal

data = Path("/content/drive/MyDrive/Tesi_OpenRCA")
repo = Path("/content/Tesi_OpenRCA_RQ2")
stage = "rq2_dryrun_workflow_preview_v0:cloudbed-1_q032:gemini:A1:D"
assert_exact_runtime_snapshot()
release = _read_release(data)
assert release["enable_discovery_D"] is True
assert release["test_unlocked"] is False
assert release["live_provider_stage_authorization_granted"] is False
assert RELEASE_SHA256 == "a35c02f830a3c5f97424e0cbf8653eda6cfa674b9c8c34d95d04627e1dba8c52"
assert PLAN_STATUS == "DRAFT_NOT_EXECUTABLE"
identity = preview_protocol_identity(src_root=repo / "src")
assert identity["rq1_source_blob_sha1_match"] is True
plan = preview_market(data)
assert plan["preview_sha256"] == release["plan_preview_sha256"]
target = [e for e in plan["entries"] if e["stage_id"] == stage]
assert len(target) == 1
assert target[0]["phase"] == "discovery"
assert target[0]["logical_model"] == "gemini"
assert target[0]["case_id"] == "cloudbed-1_q032"
assert target[0]["harness"] == "A1"
assert target[0]["stage"] == "D"
journal = RQ2DiscoveryClaimJournal(data_dir=data)
audit = journal.audit_restart()
assert audit["claims"] == 0 and audit["result_archive_discovery_count"] == 0, (
    "Uno stage RQ2 risulta gia' avviato: STOP, audit manuale"
)
assert audit["unresolved_manual_review"] == 0
assert journal._read_claim(stage) is None
assert journal.store.load_discovery_stage(stage_id=stage) is None
print("PREFLIGHT_ONE_STAGE_OK_NO_CLAIMS_NO_API", flush=True)
"""
subprocess.run(
    [sys.executable, "-c", preflight_code],
    cwd=REPO, env=pre_env, check=True,
)

# Legge il segreto COLAB soltanto dopo tutti i gate offline, mai da GitHub.
def colab_secret(name):
    try:
        return userdata.get(name)
    except Exception:
        return None

key = colab_secret("GOOGLE_API_KEY") or colab_secret("GEMINI_API_KEY")
if not isinstance(key, str) or not key.strip():
    raise RuntimeError(
        "Segreto GOOGLE_API_KEY/GEMINI_API_KEY mancante: abilitarlo nei Segreti Colab"
    )
real_env = dict(pre_env)
real_env["GOOGLE_API_KEY"] = key.strip()
real_env["LANGCHAIN_TRACING_V2"] = "false"
real_env["LANGSMITH_TRACING"] = "false"
print("CREDENTIAL: PRESENT_NOT_PRINTED", flush=True)
print("AUTHORIZED_ONLY_STAGE:", STAGE, flush=True)
print("REAL_MODEL:", MODEL_ID, flush=True)

# UNICA invocazione logica D; il wrapper scrive il claim CREATE-ONLY
# prima di costruire il client. Nessun C/K/test, nessun auto-retry.
# In caso di eccezione NON ritentare la cella: verificare claim in Drive.
run_code = """
from pathlib import Path
import json
from evaluation.rq2_discovery_d_provider_transport import run_one_claimed_discovery_d
from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal

data = Path("/content/drive/MyDrive/Tesi_OpenRCA")
repo = Path("/content/Tesi_OpenRCA_RQ2")
sid = "rq2_dryrun_workflow_preview_v0:cloudbed-1_q032:gemini:A1:D"
try:
    output = run_one_claimed_discovery_d(
        data_dir=data, repo_dir=repo, stage_id=sid, confirm_paid_api=True
    )
except Exception as exc:
    print("RQ2_D_EXCEPTION_TYPE:", type(exc).__name__, flush=True)
    try:
        review = RQ2DiscoveryClaimJournal(data_dir=data).audit_restart()
        print("CLAIM_AUDIT:", json.dumps({
            k: review.get(k) for k in (
                "claims", "finished_with_matching_result",
                "unresolved_manual_review", "result_archive_discovery_count"
            )
        }), flush=True)
    except Exception as audit_exc:
        print("CLAIM_AUDIT_EXCEPTION_TYPE:", type(audit_exc).__name__, flush=True)
    print("STOP_NO_RETRY_MANUAL_AUDIT_REQUIRED", flush=True)
    raise SystemExit(2)
else:
    metrics = output["observed_run_metrics"]
    safe_metrics = {
        k: metrics[k] for k in (
            "llm_calls", "tool_rounds", "input_tokens", "output_tokens",
            "total_tokens", "token_usage_complete", "total_seconds"
        ) if k in metrics
    }
    print("RQ2_D_RESULT:", json.dumps({
        "stage_id": output["stage_id"],
        "status": output["status"],
        "model_id": output["model_id"],
        "record_sha256": output["record_sha256"],
        "original_d_json_status": output["original_d_json_status"],
        "metrics": safe_metrics,
        "automatic_retry": output["automatic_retry"],
        "can_execute_test": output["can_execute_test"],
    }, ensure_ascii=False), flush=True)
    print("STATUS: SINGLE_REAL_D_FINISHED_NO_CK_NO_TEST", flush=True)
"""
completed = subprocess.run(
    [sys.executable, "-c", run_code],
    cwd=REPO, env=real_env, check=False,
)
# Non stampare o salvare real_env / key nei log.
real_env.pop("GOOGLE_API_KEY", None)
del key
if completed.returncode:
    raise RuntimeError(
        "Esecuzione D non completata: NON rilanciare. "
        "Condividere solo status e audit, esaminare il claim create-only."
    )
print("REAL_D_INVOCATIONS_FROM_CELL: 1")
print("OTHER_DISCOVERY_STAGES: NOT_LAUNCHED")
print("OOD_TEST: LOCKED")
~~~

## Dopo la cella

Condividere **soltanto**: GIT_HEAD, PREFLIGHT_ONE_STAGE_OK_NO_CLAIMS_NO_API,
RQ2_D_RESULT, STATUS finale, oppure tipo di eccezione e CLAiM_AUDIT
in caso di errore. **Non** incollare token, API key, dump di
Market.zip, output raw non necessario o etichette ground truth.

Interpretazione: il programma esegue **un solo stage D**; il numero
di invocazioni HTTP può essere maggiore di uno all'interno del
runner D. I dettagli diagnostici e la traiettoria tool sono
conservati dall'archivio create-only dedicato RQ2 su Drive.
Un `PROVIDER_ERROR` archiviato è un risultato di tentativo,
**non** autorizzazione a ripeterlo. Nessun avvio automatico di
stage C o K.

**ATTENZIONE AL RIAVVIO:** se Colab si disconnette dopo che è
stato scritto un claim ma prima di salvare un risultato, NON
rieseguire la cella. Lo stato `CLAIM_WITHOUT_ARTIFACT` richiede
audit manuale. Conservare il freeze separato dei K prima di
accedere agli 11 test OOD.
