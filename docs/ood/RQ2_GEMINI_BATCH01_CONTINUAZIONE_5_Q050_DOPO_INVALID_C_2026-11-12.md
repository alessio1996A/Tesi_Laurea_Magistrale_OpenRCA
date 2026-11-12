# RQ2 — Continuazione del Batch 01: K bloccata offline + 5 stage q050 reali

**12 novembre 2026. Stato: cella predisposta, NON eseguita.**
Scopo: recuperare i **5 stage non tentati** di cloudbed-1_q050,
senza ripetere alcuno dei precedenti cinque claim. L'utente ha
consentito esperimenti discovery in batch fino a dieci stage,
senza autorizzare l'apertura del test OOD.
Questo documento non modifica il release scientifico né il codice RQ1/RQ2.

## Risultato consolidato del primo blocco

- 5 claim, 5 artefatti; zero tentativi irrisolti.
- C q032/A1_8R: INVALID_OUTPUT, `ContractError`,
  `INVALID_JSON_SYNTAX_OR_WRAPPING`;
  nessuna riparazione e nessun nuovo tentativo.
- Registrazione **offline**, senza claim API, di
  q032/A1_8R/K come `BLOCKED_DEPENDENCY`, usando il percorso
  `RQ2DiscoveryStageRecorder.record_k` già implementato.
  Questo è un esito logico del piano, **non** un'invocazione LLM.
- Soltanto dopo il readback del blocco K, avviare in sequenza:
  q050/A1/D, q050/A1/C, q050/A1/K,
  q050/A1_8R/D, q050/A1_8R/C.
- Stop immediato al primo errore o allo status diverso
  da `RECORDED_COMPLETE`; nessun retry.
- Dopo questa cella gli altri stage e la K q050/A1_8R
  rimangono **non avviati**. Il batch successivo non parte da solo.

**ATTENZIONE:** la cella effettua fino a cinque stage Gemini REALI,
con possibili addebiti API. Gli stage D contengono più chiamate LLM,
quindi il numero di HTTP request non è limitato a cinque. Colab può
disconnettersi; **non rieseguire** la cella se esiste un claim/stage
precedente. Fare solo audit del Drive dopo un crash.

## Istruzioni d'uso

Nel pannello Segreti di Colab abilitare `GOOGLE_API_KEY`
(o `GEMINI_API_KEY`). Non incollare né condividere il segreto.
Non eseguire simultaneamente due notebook sullo stesso dataset.
La cella ripristina automaticamente solo le cartelle temporanee
in /content dopo un reset del runtime. I file create-only restano
sempre su Drive e non vengono sovrascritti.

## Unica cella Python Colab

~~~python
from pathlib import Path
from google.colab import drive, userdata
import hashlib, json, os, subprocess, sys

ROOT = Path("/content/drive/MyDrive/Tesi_OpenRCA")
REPO = Path("/content/Tesi_OpenRCA_RQ2")
DEPS = Path("/content/rq2_prefreeze_packages_py313")
BRANCH = "feature/ood-knowledge-transfer-audit-2026-11-10"
REMOTE = "https://github.com/alessio1996A/Tesi_Laurea_Magistrale_OpenRCA.git"
RELEASE_SHA = "a35c02f830a3c5f97424e0cbf8653eda6cfa674b9c8c34d95d04627e1dba8c52"
PIN_BLOB = "84c33c05b198d1dc483f7fef466d8df52942f000"
MODEL = "gemini-3.5-flash-lite"
PREFIX = "rq2_dryrun_workflow_preview_v0:"
BLOCKED_K = f"{PREFIX}cloudbed-1_q032:gemini:A1_8R:K"
INVALID_C = f"{PREFIX}cloudbed-1_q032:gemini:A1_8R:C"
STAGES = [
    f"{PREFIX}cloudbed-1_q050:gemini:A1:D",
    f"{PREFIX}cloudbed-1_q050:gemini:A1:C",
    f"{PREFIX}cloudbed-1_q050:gemini:A1:K",
    f"{PREFIX}cloudbed-1_q050:gemini:A1_8R:D",
    f"{PREFIX}cloudbed-1_q050:gemini:A1_8R:C",
]
assert len(STAGES) == len(set(STAGES)) == 5
assert BLOCKED_K not in STAGES and INVALID_C not in STAGES

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

drive.mount("/content/drive")
assert sys.version.split()[0] == "3.13.18", "Python runtime drift: STOP"
assert ROOT.is_dir() and not ROOT.is_symlink()
assert (ROOT / "Market.zip").is_file() and not (ROOT / "Market.zip").is_symlink()
assert not REPO.is_symlink() and not DEPS.is_symlink()

# Recovery delle sole risorse effimere (mai pulire Drive).
if not REPO.exists():
    subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch",
         "--branch", BRANCH, REMOTE, str(REPO)],
        env=dict(os.environ, GIT_TERMINAL_PROMPT="0"), check=True,
    )
    print("REPO: CLONED", flush=True)
else:
    assert (REPO / ".git").is_dir(), "Invalid checkout: STOP"
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
         "--target", str(DEPS), *PINS], check=True,
    )
    marker.write_text(signature + "\n", encoding="utf-8")
    print("DEPS: INSTALLED", flush=True)
else:
    assert DEPS.is_dir() and marker.is_file() and not marker.is_symlink()
    assert marker.read_text().strip() == signature, "Pinned deps drift: STOP"
    print("DEPS: REUSED", flush=True)

assert not subprocess.check_output(
    ["git", "-C", str(REPO), "status", "--porcelain"], text=True
).strip(), "Dirty checkout: STOP"
origin = subprocess.check_output(
    ["git", "-C", str(REPO), "remote", "get-url", "origin"], text=True
).strip()
assert origin in (REMOTE, REMOTE[:-4]), "Unexpected Git remote"
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
).strip(), "Checkout changed after fetch"
print("GIT_HEAD:", head, flush=True)

release_path = "data/rq2/RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json"
assert sha256(REPO / release_path) == sha256(ROOT / release_path) == RELEASE_SHA
release = json.loads((ROOT / release_path).read_text(encoding="utf-8"))
assert release["status"] == "SCIENTIFIC_DISCOVERY_RELEASE"
assert release["test_unlocked"] is False
assert release["live_provider_stage_authorization_granted"] is False
assert release["requires_explicit_confirmation_for_each_stage"] is True
assert release["model_ids"]["gemini"] == MODEL
assert release["plan_preview_sha256"] == (
    "ecd6d926933a5ad056ad1a581fa7e490c0a13eee18070c7dac8627c1b19c062e"
)
blob = subprocess.check_output(
    ["git", "-C", str(REPO), "rev-parse",
     "HEAD:src/evaluation/rq2_ck_provider_transport.py"], text=True
).strip()
assert blob == PIN_BLOB, "Source pin drift: STOP"
for rel, expected in release["rq2_pre_pin_code_sha256"].items():
    if rel == "evaluation/rq2_ck_provider_transport.py":
        continue
    p = REPO / "src" / rel
    assert p.is_file() and not p.is_symlink() and sha256(p) == expected, (
        "Source drift: " + rel
    )
for rel, expected in (
    ("data/processed/split_market_v1.csv", release["source_split_sha256"]),
    ("data/processed/benchmark_inputs_market.csv", release["source_manifest_sha256"]),
):
    p = ROOT / rel
    assert p.is_file() and not p.is_symlink() and sha256(p) == expected

base_env = dict(os.environ)
base_env["PYTHONPATH"] = os.pathsep.join((str(DEPS), str(REPO / "src")))
base_env["PYTHONDONTWRITEBYTECODE"] = "1"
for k in (
    "GOOGLE_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
    "GOOGLE_GENAI_USE_VERTEXAI", "LANGCHAIN_API_KEY", "LANGSMITH_API_KEY",
    "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING",
):
    base_env.pop(k, None)

# PRECHECK senza segreti, senza SDK, senza scrivere nulla nel Drive.
precheck = """
import sys
from pathlib import Path
from evaluation.rq2_dryrun_plan import preview_market, PLAN_STATUS
from evaluation.rq2_model_factory import assert_exact_runtime_snapshot
from evaluation.rq2_ck_provider_transport import _read_release
from evaluation.rq2_protocol_identity_preflight import preview_protocol_identity
from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal

root = Path("/content/drive/MyDrive/Tesi_OpenRCA")
repo = Path("/content/Tesi_OpenRCA_RQ2")
rel = _read_release(root)
assert rel["test_unlocked"] is False
assert rel["enable_discovery_D"] is True
assert rel["enable_discovery_CK"] is True
assert PLAN_STATUS == "DRAFT_NOT_EXECUTABLE"
assert_exact_runtime_snapshot()
assert preview_protocol_identity(src_root=repo / "src")[
    "rq1_source_blob_sha1_match"
] is True
plan = preview_market(root)
assert plan["preview_sha256"] == rel["plan_preview_sha256"]
gemini = [e["stage_id"] for e in plan["entries"] if (
    e["phase"] == "discovery" and e["logical_model"] == "gemini"
)]
target = sys.argv[1:]
assert len(gemini) == 24
assert len(target) == 5 and target == gemini[6:11], (
    "Wrong q050 batch against frozen plan"
)
journal = RQ2DiscoveryClaimJournal(data_dir=root)
audit = journal.audit_restart()
assert audit["claims"] == audit["finished_with_matching_result"] == 5
assert audit["result_archive_discovery_count"] == 5
assert audit["unresolved_manual_review"] == 0
known = {
    "A1:D": "73c1006d134ffef5bad7cba380925546c84d58c2ed20ba1730f75f1f42bbdfe7",
    "A1:C": "611358878be6cd439bd2d66cf20607d0653a099ba6ad75dbceed4a3fe8b34a06",
    "A1:K": "200fd07a480f6e4c47a283c9e4dd39db707f4cb5b1a70acb5974e29b857a9742",
    "A1_8R:D": "f3b92c3722ff0f19d91159431b9923e63dfeb0423d147ebb71468004d5ef4a67",
    "A1_8R:C": "fb4e321c63452fed5ef632dcd2f3a6c2e10459d2d31ebf136678439595478bd9",
}
prefix = "rq2_dryrun_workflow_preview_v0:cloudbed-1_q032:gemini:"
for short, digest in known.items():
    sid = prefix + short
    assert journal._read_claim(sid) is not None
    rec = journal.store.load_discovery_stage(stage_id=sid)
    assert rec is not None and rec["record_sha256"] == digest
invalid = journal.store.load_discovery_stage(stage_id=prefix + "A1_8R:C")
assert invalid["status"] == "INVALID_OUTPUT"
assert invalid["artifact"]["contract_error_type"] == "ContractError"
blocked = prefix + "A1_8R:K"
assert journal._read_claim(blocked) is None
assert journal.store.load_discovery_stage(stage_id=blocked) is None
for sid in target:
    assert journal._read_claim(sid) is None, "Already claimed: NO RETRY"
    assert journal.store.load_discovery_stage(stage_id=sid) is None, (
        "Already recorded: NO REEXECUTION"
    )
print("BATCH01_CONTINUATION_PREFLIGHT_OK_NO_API", flush=True)
"""
result = subprocess.run(
    [sys.executable, "-c", precheck, *STAGES],
    cwd=REPO, env=base_env, text=True, capture_output=True,
)
if result.returncode != 0:
    print("BATCH01_CONTINUATION_PREFLIGHT_FAILED_NO_API", flush=True)
    raise RuntimeError("Preflight failed: audit before any change")
print(result.stdout.strip(), flush=True)

# K q032/A1_8R: create-only BLOCKED_DEPENDENCY, nessuna richiesta Google.
offline_block = """
import json
from pathlib import Path
from evaluation.rq2_discovery_stage_recorder import RQ2DiscoveryStageRecorder
from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal
root = Path("/content/drive/MyDrive/Tesi_OpenRCA")
sid = "rq2_dryrun_workflow_preview_v0:cloudbed-1_q032:gemini:A1_8R:K"
recorder = RQ2DiscoveryStageRecorder(data_dir=root)
journal = RQ2DiscoveryClaimJournal(data_dir=root)
prior = journal.store.load_discovery_stage(
    stage_id=sid[:-1] + "C"
)
assert prior is not None and prior["status"] == "INVALID_OUTPUT"
assert journal._read_claim(sid) is None
assert journal.store.load_discovery_stage(stage_id=sid) is None
saved = recorder.record_k(
    stage_id=sid, model_id_proposed="gemini-3.5-flash-lite",
    raw_response=None, provider_error=None, transport_receipt=None
)
assert saved["status"] == "BLOCKED_DEPENDENCY"
item = journal.store.load_discovery_stage(stage_id=sid)
assert item is not None and item["record_sha256"] == saved["record_sha256"]
assert item["artifact"] == {}
assert item["dependency_record_hashes"] == {
    sid[:-1] + "C": prior["record_sha256"]
}
assert journal._read_claim(sid) is None
audit = journal.audit_restart()
assert audit["claims"] == audit["finished_with_matching_result"] == 5
assert audit["result_archive_discovery_count"] == 6
assert audit["unresolved_manual_review"] == 0
print("BLOCKED_K_OFFLINE:" + json.dumps({
    "stage_id": sid, "status": item["status"],
    "record_sha256": item["record_sha256"],
    "claim_created": False, "llm_calls": 0,
    "total_stored_records": audit["result_archive_discovery_count"],
}, allow_nan=False), flush=True)
"""
record = subprocess.run(
    [sys.executable, "-c", offline_block],
    cwd=REPO, env=base_env, text=True, capture_output=True,
)
if record.returncode != 0:
    print("BLOCKED_K_OFFLINE_AUDIT_REQUIRED_NO_RETRY", flush=True)
    # K create-only may already have been written prior to a later assertion.
    raise RuntimeError("K offline block did not pass readback; audit Drive first")
print(record.stdout.strip(), flush=True)

# Segreto solo DOPO i gate e la registrazione offline K.
def secret(name):
    try:
        return userdata.get(name)
    except Exception:
        return None

key = secret("GOOGLE_API_KEY") or secret("GEMINI_API_KEY")
if not isinstance(key, str) or not key.strip():
    raise RuntimeError(
        "Google secret non disponibile. Non ripetere la cella: "
        "la K bloccata potrebbe gia' essere salvata su Drive."
    )
paid_env = dict(base_env)
paid_env["GOOGLE_API_KEY"] = key.strip()
paid_env["LANGCHAIN_TRACING_V2"] = "false"
paid_env["LANGSMITH_TRACING"] = "false"
del key
print("GOOGLE_CREDENTIAL: PRESENT_NOT_PRINTED", flush=True)

# UN stage per processo. Il wrapper effettua claim create-only
# prima di costruire il modello; nessun retry in caso di errore.
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
            output = run_one_claimed_discovery_d(
                data_dir=root, repo_dir=repo, stage_id=sid,
                confirm_paid_api=True
            )
            metrics = output["observed_run_metrics"]
            use = {
                k: metrics[k] for k in (
                    "llm_calls", "tool_rounds", "input_tokens",
                    "output_tokens", "total_tokens", "token_usage_complete",
                    "end_to_end_seconds"
                ) if k in metrics and type(metrics[k]) in (int, float, bool)
            }
        elif sid.endswith((":C", ":K")):
            output = run_one_claimed_ck(
                data_dir=root, stage_id=sid, confirm_paid_api=True
            )
            use = {
                k: v for k, v in output["usage"].items()
                if k in ("complete", "input_tokens", "output_tokens", "total_tokens")
                and type(v) in (int, bool)
            }
        else:
            raise RuntimeError("Unexpected stage")

    journal = RQ2DiscoveryClaimJournal(data_dir=root)
    saved = journal.store.load_discovery_stage(stage_id=sid)
    claim = journal._read_claim(sid)
    assert saved is not None and claim is not None
    assert saved["record_sha256"] == output["record_sha256"]
    assert saved["status"] == output["status"]
    counts = journal.audit_restart()
    assert counts["unresolved_manual_review"] == 0
    print("BATCH01_CONTINUATION_RESULT:" + json.dumps({
        "stage_id": sid,
        "status": saved["status"],
        "record_sha256": saved["record_sha256"],
        "claim_sha256": claim["claim_sha256"],
        "metrics": use,
        "claims": counts["claims"],
        "stored_records": counts["result_archive_discovery_count"],
        "ood_test_locked": True,
    }, ensure_ascii=False, allow_nan=False), flush=True)
except BaseException as err:
    print("BATCH01_CONTINUATION_ERROR:" + json.dumps({
        "stage_id": sid, "error_type": type(err).__name__,
        "action": "STOP_NO_RETRY_AUDIT_DRIVE",
    }), flush=True)
    raise SystemExit(2)
"""

results = []
try:
    for n, sid in enumerate(STAGES, 1):
        print(f"\n=== Q050 STAGE {n}/5: {sid} ===", flush=True)
        completed = subprocess.run(
            [sys.executable, "-c", driver, sid],
            cwd=REPO, env=paid_env,
            capture_output=True, text=True,
        )
        messages = [
            line[len("BATCH01_CONTINUATION_RESULT:"):]
            for line in completed.stdout.splitlines()
            if line.startswith("BATCH01_CONTINUATION_RESULT:")
        ]
        errors = [
            line[len("BATCH01_CONTINUATION_ERROR:"):]
            for line in completed.stdout.splitlines()
            if line.startswith("BATCH01_CONTINUATION_ERROR:")
        ]
        if completed.returncode or len(messages) != 1 or errors:
            for error in errors:
                print("STAGE_ERROR:", error, flush=True)
            print("STOP_NO_RETRY_Q050_AUDIT_REQUIRED", flush=True)
            raise RuntimeError("Q050 stopped, DO NOT repeat this cell")
        item = json.loads(messages[0])
        assert item["stage_id"] == sid
        results.append(item)
        print("Q050_STAGE:", json.dumps(item, ensure_ascii=False), flush=True)
        if item["status"] != "RECORDED_COMPLETE":
            print("STOP_Q050_NONCOMPLETE_KEEP_ORIGINAL", flush=True)
            raise RuntimeError("Noncomplete stage: no retry or repair")
finally:
    paid_env.pop("GOOGLE_API_KEY", None)

print("\nSTATUS: Q050_FIVE_REAL_STAGES_COMPLETED")
print("Q050_COMPLETED:", len(results))
print("Q032_INVALID_C_PRESERVED: TRUE")
print("Q032_BLOCKED_K_HAS_NO_API: TRUE")
print("NEXT_STAGE_NOT_AUTO_LAUNCHED: TRUE")
print("OOD_TEST: LOCKED")
~~~

## Output da inviare e interpretazione

Se la cella riesce, inviare `BATCH01_CONTINUATION_PREFLIGHT_OK_NO_API`,
`BLOCKED_K_OFFLINE`, le cinque righe `Q050_STAGE` e
`STATUS: Q050_FIVE_REAL_STAGES_COMPLETED`.

Se si interrompe, **non rieseguire** questa cella.
Condividere le righe già stampate (senza raw outputs).
Gli artefatti già salvati si verificano con una cella
separata di sola lettura e si pianifica una prosecuzione
soltanto per gli stage non tentati. Una K `BLOCKED_DEPENDENCY`
non è un successo LLM e conta come stage logicamente bloccato.

Nessuna chiamata Gemini in questo documento fino a quando
l'utente non esegue esplicitamente la cella.
Nessuno scoring, GT, nuove regole di inferenza, modifica del
freeze di output o apertura degli 11 casi OOD.
