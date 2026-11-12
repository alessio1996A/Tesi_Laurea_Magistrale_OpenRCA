# RQ2 — Gemini Discovery Batch 02: dieci nuovi stage, senza retry

**Data:** 12 novembre 2026.
**Stato:** cella preparata su GitHub, **NON eseguita**.
L'utente ha esplicitamente autorizzato esperimenti discovery reali
a blocchi fino a dieci, con costi API e protezione create-only.
Questa cella prepara soltanto i **10 stage successivi del piano
scientifico immutabile**. Non rilancia uno stage già tentato,
non consulta la ground truth e non esegue test OOD.

## Stato di partenza verificato dall'utente

Dopo la prima D, il batch01 interrotto e la continuazione q050:
- `claims=10`, `finished_with_matching_result=10`;
  `unresolved_manual_review=0`.
- `result_archive_discovery_count=11`: 9 RECORDED_COMPLETE,
  1 INVALID_OUTPUT e 1 BLOCKED_DEPENDENCY senza claim API.
- C q032/A1_8R INVALID_OUTPUT è immutabile e senza retry.
- K q032/A1_8R BLOCKED_DEPENDENCY è stata già registrata
  create-only offline con SHA
  `68a4829f57212a36067ccd05a224e39b03133469a89a0fdae1fc552760cd3d63`.
- D q050/A1_8R: 1 chiamata LLM e **0 round di tool**;
  C q050/A1_8R: RECORDED_COMPLETE. Il preflight di questo
  batch controlla che `C.decision=abstain` ed E### sia vuoto.
  Se non è così: **STOP senza API**.
- 11/24 stage logici Gemini discovery già registrati,
  restanti 13.

### Elenco esatto degli stage del batch02 (10)

| # | Caso | Harness | Stage |
|---:|---|---|---|
| 1 | cloudbed-1_q050 | A1_8R | K |
| 2 | cloudbed-2_q026 | A1 | D |
| 3 | cloudbed-2_q026 | A1 | C |
| 4 | cloudbed-2_q026 | A1 | K |
| 5 | cloudbed-2_q026 | A1_8R | D |
| 6 | cloudbed-2_q026 | A1_8R | C |
| 7 | cloudbed-2_q026 | A1_8R | K |
| 8 | cloudbed-2_q045 | A1 | D |
| 9 | cloudbed-2_q045 | A1 | C |
| 10 | cloudbed-2_q045 | A1 | K |

Sono tutti stage `gemini-3.5-flash-lite`.
La K q050/A1_8R **non deve inventare evidenze**: la sua
uscita può essere `insufficient_evidence` e tale esito
non prova la formalizzabilità di una regola. Se fallisce
il contratto, viene archiviato come INVALID_OUTPUT e
il batch si ferma.

**Nota:** dieci stage non sono dieci richieste HTTP.
Ogni D può contenere più chiamate LLM; questi stage possono
generare costi. Solo un tentativo per stage, nessun retry
automatico in caso di errore provider, crash, JSON invalid
o claim senza artefatto.

## Uso

Abilitare nei **Segreti di Google Colab** il segreto
`GOOGLE_API_KEY` (o `GEMINI_API_KEY`) e l'accesso
al notebook. Non incollare la chiave nel codice/chat.
Non eseguire in parallelo a un altro notebook RQ2.
**Eseguire una sola volta.** In caso di arresto,
non rieseguire la cella: i claim/risultati persistenti
richiedono prima un audit offline separato.

## Cella Colab unica: 10 stage Gemini reali con preflight

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
PREFIX = "rq2_dryrun_workflow_preview_v0:"
MODEL = "gemini-3.5-flash-lite"

STAGES = [
    f"{PREFIX}cloudbed-1_q050:gemini:A1_8R:K",
    f"{PREFIX}cloudbed-2_q026:gemini:A1:D",
    f"{PREFIX}cloudbed-2_q026:gemini:A1:C",
    f"{PREFIX}cloudbed-2_q026:gemini:A1:K",
    f"{PREFIX}cloudbed-2_q026:gemini:A1_8R:D",
    f"{PREFIX}cloudbed-2_q026:gemini:A1_8R:C",
    f"{PREFIX}cloudbed-2_q026:gemini:A1_8R:K",
    f"{PREFIX}cloudbed-2_q045:gemini:A1:D",
    f"{PREFIX}cloudbed-2_q045:gemini:A1:C",
    f"{PREFIX}cloudbed-2_q045:gemini:A1:K",
]
assert len(STAGES) == len(set(STAGES)) == 10

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as inp:
        for block in iter(lambda: inp.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

drive.mount("/content/drive")
assert sys.version.split()[0] == "3.13.18", "Python Colab diverso: STOP"
assert ROOT.is_dir() and not ROOT.is_symlink(), "Drive non montato"
assert (ROOT / "Market.zip").is_file() and not (ROOT / "Market.zip").is_symlink()
assert not REPO.is_symlink() and not DEPS.is_symlink()

# Ripristino SOLO della risorsa temporanea /content, senza toccare Drive.
if not REPO.exists():
    subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch",
         "--branch", BRANCH, REMOTE, str(REPO)],
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
         "--disable-pip-version-check", "--upgrade", "--target", str(DEPS),
         *PINS], check=True,
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
assert origin in (REMOTE, REMOTE[:-4]), "Unexpected git origin"
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
).strip(), "Checkout changed: STOP"
print("GIT_HEAD:", head, flush=True)

release_rel = "data/rq2/RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json"
assert sha256(REPO / release_rel) == sha256(ROOT / release_rel) == RELEASE_SHA
release = json.loads((ROOT / release_rel).read_text(encoding="utf-8"))
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
assert blob == PIN_BLOB, "Provider source pin drift"
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

# PRECHECK offline, senza segreti, SDK provider, nuovo claim, o GT.
precheck = """
import sys
from pathlib import Path
from evaluation.rq2_dryrun_plan import preview_market, PLAN_STATUS
from evaluation.rq2_model_factory import assert_exact_runtime_snapshot
from evaluation.rq2_ck_provider_transport import _read_release
from evaluation.rq2_protocol_identity_preflight import preview_protocol_identity
from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal
from evaluation.rq2_evidence_bundle import build_evidence_bundle, evidence_ids
from evaluation.rq2_discovery_stage_recorder import ALLOWED_TOOLS

root = Path("/content/drive/MyDrive/Tesi_OpenRCA")
repo = Path("/content/Tesi_OpenRCA_RQ2")
r = _read_release(root)
assert r["enable_discovery_D"] and r["enable_discovery_CK"]
assert r["test_unlocked"] is False
assert PLAN_STATUS == "DRAFT_NOT_EXECUTABLE"
assert_exact_runtime_snapshot()
assert preview_protocol_identity(src_root=repo / "src")[
    "rq1_source_blob_sha1_match"
] is True
plan = preview_market(root)
assert plan["preview_sha256"] == r["plan_preview_sha256"]
gemini = [e["stage_id"] for e in plan["entries"] if (
    e["phase"] == "discovery" and e["logical_model"] == "gemini"
)]
target = sys.argv[1:]
assert len(gemini) == 24 and target == gemini[11:21], (
    "Batch02 order disagrees with frozen Gemini discovery plan"
)
journal = RQ2DiscoveryClaimJournal(data_dir=root)
summary = journal.audit_restart()
assert summary["claims"] == summary["finished_with_matching_result"] == 10
assert summary["result_archive_discovery_count"] == 11
assert summary["unresolved_manual_review"] == 0

# SHA-256 immutabili di tutte le fasi già archiviate.
known = {
    "cloudbed-1_q032:A1:D": "73c1006d134ffef5bad7cba380925546c84d58c2ed20ba1730f75f1f42bbdfe7",
    "cloudbed-1_q032:A1:C": "611358878be6cd439bd2d66cf20607d0653a099ba6ad75dbceed4a3fe8b34a06",
    "cloudbed-1_q032:A1:K": "200fd07a480f6e4c47a283c9e4dd39db707f4cb5b1a70acb5974e29b857a9742",
    "cloudbed-1_q032:A1_8R:D": "f3b92c3722ff0f19d91159431b9923e63dfeb0423d147ebb71468004d5ef4a67",
    "cloudbed-1_q032:A1_8R:C": "fb4e321c63452fed5ef632dcd2f3a6c2e10459d2d31ebf136678439595478bd9",
    "cloudbed-1_q032:A1_8R:K": "68a4829f57212a36067ccd05a224e39b03133469a89a0fdae1fc552760cd3d63",
    "cloudbed-1_q050:A1:D": "86874d575a848dfea505c9f4a7d768820a88aed147c104c77c98b29a586e3bab",
    "cloudbed-1_q050:A1:C": "5d4dedf8be13e976b57638e599eee77161263b230aafeffe983158ee602e3d61",
    "cloudbed-1_q050:A1:K": "757acfdabc5842961d07c48431af826896b3e4008e535af0bb831e2f980e90e8",
    "cloudbed-1_q050:A1_8R:D": "afd932403b3a1cfe38cb676c048875fbf968336d8f786a5dbed56c4a78cf5f9a",
    "cloudbed-1_q050:A1_8R:C": "b982a1ee1dd111e7e6f1f5ea552cde6e55a9d7c3011eadaccb1b33a9b942d987",
}
for key, digest in known.items():
    case, harness, stage = key.split(":")
    sid = f"rq2_dryrun_workflow_preview_v0:{case}:gemini:{harness}:{stage}"
    item = journal.store.load_discovery_stage(stage_id=sid)
    assert item is not None and item["record_sha256"] == digest
    if stage != "K" or harness != "A1_8R" or case != "cloudbed-1_q032":
        assert journal._read_claim(sid) is not None
    else:
        assert item["status"] == "BLOCKED_DEPENDENCY"
        assert journal._read_claim(sid) is None

# Gate scientifico: q050/A1_8R D non ha osservazioni tool;
# C valida deve essere astensione (non diagnosi inventata).
p = "rq2_dryrun_workflow_preview_v0:cloudbed-1_q050:gemini:A1_8R:"
d = journal.store.load_discovery_stage(stage_id=p + "D")
c = journal.store.load_discovery_stage(stage_id=p + "C")
assert d["status"] == c["status"] == "RECORDED_COMPLETE"
trajectory = d["artifact"]["diagnostic_run"]["tool_trajectory"]
ids = evidence_ids(build_evidence_bundle(
    trajectory, allowed_tool_names=ALLOWED_TOOLS
))
assert ids == set(), "Expected no captured tool observations"
cv = c["artifact"]["validated_c"]
assert cv is not None and cv["decision"] == "abstain"
assert cv["evidence_ids"] == []
assert cv["predicted_fault_type"] is None
print("Q050_A1_8R_C_ABSTENTION_WITH_ZERO_EVIDENCE_CONFIRMED", flush=True)

for sid in target:
    assert journal._read_claim(sid) is None, "Stage already claimed: NO RETRY"
    assert journal.store.load_discovery_stage(stage_id=sid) is None, (
        "Stage already stored: create-only"
    )
print("BATCH02_PREFLIGHT_OK_10_NEW_STAGES_NO_API", flush=True)
"""
pre = subprocess.run(
    [sys.executable, "-c", precheck, *STAGES],
    cwd=REPO, env=base_env, text=True, capture_output=True,
)
if pre.returncode:
    print("BATCH02_PREFLIGHT_FAILED_NO_API", flush=True)
    raise RuntimeError("Offline integrity/abstention preflight failed: STOP")
print(pre.stdout.strip(), flush=True)
print("AUTHORIZED_BATCH02_COUNT: 10", flush=True)
for n, sid in enumerate(STAGES, 1):
    print(f"  {n:02d}/10 {sid}", flush=True)

# Legge i Segreti Colab SOLO dopo tutti i gate offline.
def get_secret(name):
    try:
        return userdata.get(name)
    except Exception:
        return None

key = get_secret("GOOGLE_API_KEY") or get_secret("GEMINI_API_KEY")
if not isinstance(key, str) or not key.strip():
    raise RuntimeError("Abilitare GOOGLE_API_KEY nei Segreti Colab")
paid_env = dict(base_env)
paid_env["GOOGLE_API_KEY"] = key.strip()
paid_env["LANGCHAIN_TRACING_V2"] = "false"
paid_env["LANGSMITH_TRACING"] = "false"
del key
print("GOOGLE_CREDENTIAL: PRESENT_NOT_PRINTED", flush=True)

# Singolo stage per processo; solo la funzione wrapper produce claim
# prima del provider. Nessun SDK retry e nessun tool C/K.
# stdout del runner non viene riprodotto (nessun raw/prompt/GT a video).
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
            answer = run_one_claimed_discovery_d(
                data_dir=root, repo_dir=repo, stage_id=sid,
                confirm_paid_api=True
            )
            m = answer["observed_run_metrics"]
            usage = {k: m[k] for k in (
                "llm_calls", "tool_rounds", "input_tokens", "output_tokens",
                "total_tokens", "token_usage_complete", "end_to_end_seconds"
            ) if k in m and type(m[k]) in (int, float, bool)}
        elif sid.endswith((":C", ":K")):
            answer = run_one_claimed_ck(
                data_dir=root, stage_id=sid, confirm_paid_api=True
            )
            m = answer["usage"]
            usage = {k: m[k] for k in (
                "complete", "input_tokens", "output_tokens", "total_tokens"
            ) if k in m and type(m[k]) in (int, bool)}
        else:
            raise ValueError("Unexpected stage")
    journal = RQ2DiscoveryClaimJournal(data_dir=root)
    record = journal.store.load_discovery_stage(stage_id=sid)
    claim = journal._read_claim(sid)
    assert record is not None and claim is not None
    assert record["record_sha256"] == answer["record_sha256"]
    assert record["status"] == answer["status"]
    counts = journal.audit_restart()
    assert counts["unresolved_manual_review"] == 0
    outcome = {
        "stage_id": sid,
        "status": record["status"],
        "record_sha256": record["record_sha256"],
        "claim_sha256": claim["claim_sha256"],
        "usage": usage,
        "claims": counts["claims"],
        "stored_records": counts["result_archive_discovery_count"],
        "ood_test_locked": True,
    }
    if sid.endswith(":K") and record["status"] == "RECORDED_COMPLETE":
        # K può dichiarare insufficient_evidence, NON una regola test-ready.
        k = record["artifact"]
        outcome["k_status"] = k["validated_k"]["status"]
        outcome["k_preflight_status"] = k["preflight_status"]
        outcome["scientific_freeze"] = k["scientific_freeze"]
    if sid.endswith(":C") and record["status"] == "RECORDED_COMPLETE":
        outcome["c_decision"] = record["artifact"]["validated_c"]["decision"]
    print("RQ2_BATCH02_STAGE:" + json.dumps(
        outcome, ensure_ascii=False, allow_nan=False
    ), flush=True)
except BaseException as exc:
    print("RQ2_BATCH02_ERROR:" + json.dumps({
        "stage_id": sid,
        "error_type": type(exc).__name__,
        "action": "STOP_NO_RETRY_MANUAL_AUDIT",
    }), flush=True)
    raise SystemExit(2)
"""

finished = []
try:
    # Rigorosamente sequenziale: interrompe il batch alla prima anomalia.
    for index, sid in enumerate(STAGES, 1):
        print(f"\n=== BATCH02 STAGE {index}/10: {sid} ===", flush=True)
        p = subprocess.run(
            [sys.executable, "-c", driver, sid],
            cwd=REPO, env=paid_env, text=True, capture_output=True,
        )
        results = [
            line[len("RQ2_BATCH02_STAGE:"):]
            for line in p.stdout.splitlines()
            if line.startswith("RQ2_BATCH02_STAGE:")
        ]
        errors = [
            line[len("RQ2_BATCH02_ERROR:"):]
            for line in p.stdout.splitlines()
            if line.startswith("RQ2_BATCH02_ERROR:")
        ]
        if p.returncode or len(results) != 1 or errors:
            for line in errors:
                print("BATCH02_STAGE_ERROR:", line, flush=True)
            print("BATCH02_STOP_NO_RETRY_MANUAL_AUDIT_REQUIRED", flush=True)
            raise RuntimeError("Batch02 stopped: do not rerun this cell")
        result = json.loads(results[0])
        assert result["stage_id"] == sid
        finished.append(result)
        print("BATCH02_STAGE:", json.dumps(result, ensure_ascii=False), flush=True)
        if result["status"] != "RECORDED_COMPLETE":
            print("BATCH02_STOP_NONCOMPLETE_NO_RETRY", flush=True)
            raise RuntimeError("Noncomplete stage: audit before any continuation")
finally:
    # Rimuove la chiave dal dizionario anche in caso di errore.
    paid_env.pop("GOOGLE_API_KEY", None)

print("\nSTATUS: BATCH02_10_REAL_DISCOVERY_STAGES_COMPLETED")
print("BATCH02_COMPLETED:", len(finished))
print("NO_OTHER_STAGES_AUTORUN: TRUE")
print("OOD_TEST: LOCKED")
~~~

## Cosa condividere e come interpretarlo

Condividere le dieci righe `BATCH02_STAGE`, il preflight
`Q050_A1_8R_C_ABSTENTION_WITH_ZERO_EVIDENCE_CONFIRMED`
e lo `STATUS` finale. Se si interrompe, condividere
le righe `BATCH02_STOP_...` e gli stage già stampati,
**non ripetere** la cella. L'audit di sola lettura su
Drive verificherà il nuovo stato e distinguerà i claim
con output da quelli senza artefatto.

L'output `k_status=insufficient_evidence` è una
astensione epistemicamente corretta dal proporre una regola,
non un trasferimento conoscitivo riuscito. Il preflight KPI
di K non è un rilascio della fase test; soltanto un
freeze separato, indipendente e verificato potrà sbloccare
gli 11 casi OOD. Il batch03 (gli ultimi tre stage Gemini)
non parte automaticamente.
