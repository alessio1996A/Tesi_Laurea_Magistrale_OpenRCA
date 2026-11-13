# RQ2 — Sonnet: continuazione dopo D ambigua (2 blocchi offline + 10 stage reali)

**13 novembre 2026. Stato: cella preparata, non eseguita.**

L'audit Sonnet ha confermato `31` record integri, `30` claim
con risultato e nessuna anomalia irrisolta. L'esperimento
`cloudbed-1_q050/sonnet/A1/D` ha prodotto JSON finale valido,
senza errori provider, ma la traiettoria contiene un
**`AMBIGUOUS_TOOL_RESULT`**: non è possibile associare
in modo verificabile tutti i risultati alle chiamate tool.
Quella D rimane `INVALID_OUTPUT`, create-only e **non
viene ritentata**. Non alteriamo il protocollo o l'evidence bundler.

## Cosa viene fatto nell'ordine corretto

La cella avvia un preflight completamente offline:
versioni pinned, hash release Git/Drive, codice RQ1/RQ2
congelato, 24 hash Gemini, 7 hash Sonnet, 30 claim,
31 record e 17 Sonnet/24 Haiku ancora intatti.
Dopo il preflight verifica che la chiave Anthropic sia presente,
senza stamparla.

**Poi registra in modo create-only e senza API** la C e
la K di `cloudbed-1_q050/sonnet/A1` come
`BLOCKED_DEPENDENCY`. Sono due risultati logici
non corrispondenti a tentativi LLM. Se una scrittura
fallisce, la cella si ferma per audit e non si riesegue.

Solo dopo avvia in sequenza i seguenti **10 stage REALI
Sonnet non ancora tentati**, con stop al primo errore:

| # | Caso | Harness | Stage |
|---:|---|---|---|
| 1 | cloudbed-1_q050 | A1_8R | D |
| 2 | cloudbed-1_q050 | A1_8R | C |
| 3 | cloudbed-1_q050 | A1_8R | K |
| 4 | cloudbed-2_q026 | A1 | D |
| 5 | cloudbed-2_q026 | A1 | C |
| 6 | cloudbed-2_q026 | A1 | K |
| 7 | cloudbed-2_q026 | A1_8R | D |
| 8 | cloudbed-2_q026 | A1_8R | C |
| 9 | cloudbed-2_q026 | A1_8R | K |
| 10 | cloudbed-2_q045 | A1 | D |

Il modello è `claude-sonnet-5-5`; il provider Anthropic
prevede **costi reali senza hard-cap finanziario**.
Una D può effettuare più chiamate LLM e molti token;
10 stage non equivalgono necessariamente a 10 richieste API.
Controllare i crediti Anthropic. Nessuna chiamata viene
fatta finché non si esegue la cella in Colab.

**Non eseguire in parallelo ad altri notebook. Non ripetere
la cella dopo crash o errore**: il claim create-only può
indicare un tentativo già fatturato anche se il risultato
non è stato salvato. In quel caso effettueremo un audit
read-only. L'originale Gemini e la D Sonnet invalida
restano intatti. Nessun test OOD e nessuna GT.

## Cella unica Google Colab

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
MODEL = "claude-sonnet-5-5"

STAGES = [
    f"{PREFIX}cloudbed-1_q050:sonnet:A1_8R:D",
    f"{PREFIX}cloudbed-1_q050:sonnet:A1_8R:C",
    f"{PREFIX}cloudbed-1_q050:sonnet:A1_8R:K",
    f"{PREFIX}cloudbed-2_q026:sonnet:A1:D",
    f"{PREFIX}cloudbed-2_q026:sonnet:A1:C",
    f"{PREFIX}cloudbed-2_q026:sonnet:A1:K",
    f"{PREFIX}cloudbed-2_q026:sonnet:A1_8R:D",
    f"{PREFIX}cloudbed-2_q026:sonnet:A1_8R:C",
    f"{PREFIX}cloudbed-2_q026:sonnet:A1_8R:K",
    f"{PREFIX}cloudbed-2_q045:sonnet:A1:D",
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
assert release["model_ids"]["sonnet"] == MODEL
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
sonnet = [e["stage_id"] for e in plan["entries"] if (
    e["phase"] == "discovery" and e["logical_model"] == "sonnet"
)]
target = sys.argv[1:]
assert len(sonnet) == 24 and target == sonnet[9:19], (
    "Continuation order differs from frozen Sonnet plan"
)
journal = RQ2DiscoveryClaimJournal(data_dir=root)
summary = journal.audit_restart()
assert summary["claims"] == summary["finished_with_matching_result"] == 30
assert summary["result_archive_discovery_count"] == 31
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
    "cloudbed-1_q050:A1_8R:K": "8938bb9c14e6eee9ef4fea616f4ef67034a575a79fc28c732698a416424993fc",
    "cloudbed-2_q026:A1:D": "12ffca57087cdfbda237ecc78cb77df9324ee4aba287ceb7f3e9356b4c6b9e59",
    "cloudbed-2_q026:A1:C": "dff54a14f6edc932b6498efa3085f7ee7824c013f92491984329f5177f5090ff",
    "cloudbed-2_q026:A1:K": "9d969ca0cce8974c3cd70a67043c2c0039aa53ae7f6dcbafd76e427d9f0d6009",
    "cloudbed-2_q026:A1_8R:D": "9c86a91f061bd71c251dd083e60f3b54b4c7584d86096eca5c7a5c00a8dca3d8",
    "cloudbed-2_q026:A1_8R:C": "7dc7d262c12e86dd9638d8b2d0472ada7df834ed77b96cbf60c475d4d87ad70a",
    "cloudbed-2_q026:A1_8R:K": "4042ca2e27ba98cba99d5b7110c5da454237593ba100ff08be400b35533097a0",
    "cloudbed-2_q045:A1:D": "b8eac499f484e65a59ac9088e65e3b34c3151a37d964519691a06085986cf0ca",
    "cloudbed-2_q045:A1:C": "7e0b9a8966d073d8626795a887e1616680489f6832d7dac4e601a02daebf9a81",
    "cloudbed-2_q045:A1:K": "32ddf6815e4216f0a46070950252852cec984f4456a0bb3758c86b16d1296add",
    "cloudbed-2_q045:A1_8R:D": "ab1cefe335b1f7cfd749a94732615775a6e840b3f7571d69ab4863be3adff0de",
    "cloudbed-2_q045:A1_8R:C": "c3bd313c83fcd967881ff7c425a5bd68b1bef8596696afac91b1855aa7454aac",
    "cloudbed-2_q045:A1_8R:K": "be785b7e143bcbc80ef2fa9cb3de6a4daa15dc2471c5530d285f143321be7239",
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

known_sonnet = {
    "cloudbed-1_q032:A1:D": "77c5213484351bbb447d8b5e71adac5c986fb563d80b0be3a030c68fc2d1dbb8",
    "cloudbed-1_q032:A1:C": "dab2ad70fbfe65ffec3dd114b20d12190f813e482804b4f5fc6416441ef639f8",
    "cloudbed-1_q032:A1:K": "b3b3e0759856991f6fc51326b5024f555547efb0b24c18988f5454081b1f1c0a",
    "cloudbed-1_q032:A1_8R:D": "9328673bb87ba79a51f1d686d36879b822046ea4e52ec3982fd8a6ab8cef899f",
    "cloudbed-1_q032:A1_8R:C": "6e2ff1935e784b105de8624c99b74ff31f57bfba0acb27cf7dc1643b5da5c956",
    "cloudbed-1_q032:A1_8R:K": "b7cca8069ef3049491f6905cf3aa8f88c5efcdb4eebbc3a65f2275d2409ae08a",
    "cloudbed-1_q050:A1:D": "03c51f1260d0981a691bc8af381b1ed736220a54883919033250e14d37f66d10",
}
assert len(known_sonnet) == 7
for short, digest in known_sonnet.items():
    case, harness, stage = short.split(":")
    sid = f"rq2_dryrun_workflow_preview_v0:{case}:sonnet:{harness}:{stage}"
    item = journal.store.load_discovery_stage(stage_id=sid)
    assert item is not None and item["record_sha256"] == digest
    assert journal._read_claim(sid) is not None
    if short == "cloudbed-1_q050:A1:D":
        assert item["status"] == "INVALID_OUTPUT"
        assert item["artifact"]["tool_trajectory_issue"] == "EvidenceBundleError"
        assert item["artifact"]["original_d_json_status"] == "valid_json"
        assert item["artifact"]["diagnostic_run"]["error"] is None
    else:
        assert item["status"] == "RECORDED_COMPLETE"

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

# Tutti e soltanto i primi 7 stage Sonnet sono stati tentati.
assert len(sonnet) == 24
known_ids = set(sonnet[:7])
assert len(known_ids) == 7
for sid in sonnet[:7]:
    assert journal._read_claim(sid) is not None
for sid in sonnet[7:]:
    assert journal._read_claim(sid) is None, "Sonnet claim inatteso"
    assert journal.store.load_discovery_stage(stage_id=sid) is None, (
        "Sonnet artefatto inatteso"
    )
haiku = [e["stage_id"] for e in plan["entries"] if (
    e["phase"] == "discovery" and e["logical_model"] == "haiku"
)]
assert len(haiku) == 24
for sid in haiku:
    assert journal._read_claim(sid) is None
    assert journal.store.load_discovery_stage(stage_id=sid) is None
assert sonnet[7] == "rq2_dryrun_workflow_preview_v0:cloudbed-1_q050:sonnet:A1:C"
assert sonnet[8] == "rq2_dryrun_workflow_preview_v0:cloudbed-1_q050:sonnet:A1:K"
print("SONNET_CONT01_PREFLIGHT_OK_10_NEW_STAGES_NO_API", flush=True)
"""
pre = subprocess.run(
    [sys.executable, "-c", precheck, *STAGES],
    cwd=REPO, env=base_env, text=True, capture_output=True,
)
if pre.returncode:
    print("SONNET_CONT01_PREFLIGHT_FAILED_NO_API", flush=True)
    raise RuntimeError("Offline integrity/abstention preflight failed: STOP")
print(pre.stdout.strip(), flush=True)
print("AUTHORIZED_SONNET_CONT01_COUNT: 10", flush=True)
for n, sid in enumerate(STAGES, 1):
    print(f"  {n:02d}/10 {sid}", flush=True)

# Legge i Segreti Colab SOLO dopo tutti i gate offline.
def get_secret(name):
    try:
        return userdata.get(name)
    except Exception:
        return None

key = get_secret("ANTHROPIC_API_KEY")
if not isinstance(key, str) or not key.strip():
    raise RuntimeError("Abilitare ANTHROPIC_API_KEY nei Segreti Colab")
paid_env = dict(base_env)
paid_env["ANTHROPIC_API_KEY"] = key.strip()
paid_env["LANGCHAIN_TRACING_V2"] = "false"
paid_env["LANGSMITH_TRACING"] = "false"
del key
print("ANTHROPIC_CREDENTIAL: PRESENT_NOT_PRINTED", flush=True)
# Primo passaggio: due blocchi logici, senza claim e senza Anthropic.
blocked_worker = """
import json
from pathlib import Path
from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal
from evaluation.rq2_discovery_stage_recorder import RQ2DiscoveryStageRecorder
root = Path("/content/drive/MyDrive/Tesi_OpenRCA")
base = "rq2_dryrun_workflow_preview_v0:cloudbed-1_q050:sonnet:A1:"
journal = RQ2DiscoveryClaimJournal(data_dir=root)
recorder = RQ2DiscoveryStageRecorder(data_dir=root)
initial = journal.audit_restart()
assert initial["claims"] == initial["finished_with_matching_result"] == 30
assert initial["result_archive_discovery_count"] == 31
assert initial["unresolved_manual_review"] == 0
d = journal.store.load_discovery_stage(stage_id=base+"D")
assert d is not None and d["status"] == "INVALID_OUTPUT"
assert d["record_sha256"] == "03c51f1260d0981a691bc8af381b1ed736220a54883919033250e14d37f66d10"
assert d["artifact"]["tool_trajectory_issue"] == "EvidenceBundleError"
assert d["artifact"]["original_d_json_status"] == "valid_json"
for suffix in ("C","K"):
    assert journal._read_claim(base+suffix) is None
    assert journal.store.load_discovery_stage(stage_id=base+suffix) is None
receipt_c = recorder.record_c(
    stage_id=base+"C", model_id_proposed="claude-sonnet-5-5",
    raw_response=None, provider_error=None, transport_receipt=None
)
c = journal.store.load_discovery_stage(stage_id=base+"C")
assert receipt_c["status"] == c["status"] == "BLOCKED_DEPENDENCY"
assert receipt_c["record_sha256"] == c["record_sha256"]
assert c["dependency_record_hashes"] == {base+"D": d["record_sha256"]}
assert c["artifact"] == {} and journal._read_claim(base+"C") is None
print("SONNET_OFFLINE_BLOCK_C:"+json.dumps({
    "status": c["status"], "record_sha256": c["record_sha256"],
    "claim_created":False, "api_calls":0
}),flush=True)
receipt_k = recorder.record_k(
    stage_id=base+"K", model_id_proposed="claude-sonnet-5-5",
    raw_response=None, provider_error=None, transport_receipt=None
)
k = journal.store.load_discovery_stage(stage_id=base+"K")
assert receipt_k["status"] == k["status"] == "BLOCKED_DEPENDENCY"
assert receipt_k["record_sha256"] == k["record_sha256"]
assert k["dependency_record_hashes"] == {base+"C": c["record_sha256"]}
assert k["artifact"] == {} and journal._read_claim(base+"K") is None
final = journal.audit_restart()
assert final["claims"] == final["finished_with_matching_result"] == 30
assert final["result_archive_discovery_count"] == 33
assert final["unresolved_manual_review"] == 0
print("SONNET_OFFLINE_BLOCK_K:"+json.dumps({
    "status": k["status"], "record_sha256": k["record_sha256"],
    "claim_created":False, "api_calls":0,
    "total_stored_records":33
}),flush=True)
"""
blocked = subprocess.run(
    [sys.executable,"-c",blocked_worker],
    cwd=REPO,env=base_env,text=True,capture_output=True,
)
for line in blocked.stdout.splitlines():
    if line.startswith(("SONNET_OFFLINE_BLOCK_C:","SONNET_OFFLINE_BLOCK_K:")):
        print(line,flush=True)
if blocked.returncode != 0 or "SONNET_OFFLINE_BLOCK_K:" not in blocked.stdout:
    paid_env.pop("ANTHROPIC_API_KEY", None)
    print("SONNET_OFFLINE_BLOCK_STOP_NO_RETRY_AUDIT_REQUIRED",flush=True)
    raise RuntimeError("Blocked dependency audit required; do not re-run")


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
    print("RQ2_SONNET_CONT01_STAGE:" + json.dumps(
        outcome, ensure_ascii=False, allow_nan=False
    ), flush=True)
except BaseException as exc:
    print("RQ2_SONNET_CONT01_ERROR:" + json.dumps({
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
        print(f"\n=== SONNET_CONT01 STAGE {index}/10: {sid} ===", flush=True)
        p = subprocess.run(
            [sys.executable, "-c", driver, sid],
            cwd=REPO, env=paid_env, text=True, capture_output=True,
        )
        results = [
            line[len("RQ2_SONNET_CONT01_STAGE:"):]
            for line in p.stdout.splitlines()
            if line.startswith("RQ2_SONNET_CONT01_STAGE:")
        ]
        errors = [
            line[len("RQ2_SONNET_CONT01_ERROR:"):]
            for line in p.stdout.splitlines()
            if line.startswith("RQ2_SONNET_CONT01_ERROR:")
        ]
        if p.returncode or len(results) != 1 or errors:
            for line in errors:
                print("SONNET_CONT01_STAGE_ERROR:", line, flush=True)
            print("SONNET_CONT01_STOP_NO_RETRY_MANUAL_AUDIT_REQUIRED", flush=True)
            raise RuntimeError("Sonnet continuation stopped: do not rerun this cell")
        result = json.loads(results[0])
        assert result["stage_id"] == sid
        finished.append(result)
        print("SONNET_CONT01_STAGE:", json.dumps(result, ensure_ascii=False), flush=True)
        if result["status"] != "RECORDED_COMPLETE":
            print("SONNET_CONT01_STOP_NONCOMPLETE_NO_RETRY", flush=True)
            raise RuntimeError("Noncomplete stage: audit before any continuation")
finally:
    # Rimuove la chiave dal dizionario anche in caso di errore.
    paid_env.pop("ANTHROPIC_API_KEY", None)

print("\nSTATUS: SONNET_CONT01_10_REAL_DISCOVERY_STAGES_COMPLETED")
print("SONNET_CONT01_COMPLETED:", len(finished))
print("NO_OTHER_STAGES_AUTORUN: TRUE")
print("OOD_TEST: LOCKED")
~~~

## Interpretazione dell'output

Se il preflight passa:
`SONNET_CONT01_PREFLIGHT_OK_10_NEW_STAGES_NO_API`.
Poi devono comparire
`SONNET_OFFLINE_BLOCK_C` e `SONNET_OFFLINE_BLOCK_K`
con `api_calls=0`.

Per gli stage reali verranno emesse fino a dieci righe
`SONNET_CONT01_STAGE`. Se tutti hanno completato:

```text
STATUS: SONNET_CONT01_10_REAL_DISCOVERY_STAGES_COMPLETED
SONNET_CONT01_COMPLETED: 10
NO_OTHER_STAGES_AUTORUN: TRUE
OOD_TEST: LOCKED
```

In quel caso il totale sarà di **40 claim reali** e
**43 record**, inclusi tre blocchi logici senza API
(uno Gemini e due Sonnet). Resteranno **5 stage Sonnet**
ancora non tentati.

Se compare `SONNET_CONT01_STOP_...` o
`SONNET_OFFLINE_BLOCK_STOP_...`, **non riavviare
la cella**: inviaci gli stati stampati e faremo audit
del Drive prima di qualsiasi prosecuzione.

`RECORDED_COMPLETE` attesta integrità formale,
non accuratezza vs ground truth. Una K candidate
richiede verifica indipendente prima di qualsiasi
freeze di knowledge transfer.
