# RQ2 — Sonnet Continuazione 02: blocco C/K offline, poi dieci stage reali

**13 novembre 2026. STATO: cella preparata, NON eseguita.**

L'audit precedente `SONNET_CONT01_READ_ONLY_AUDIT` ha validato
**34 record, 31 claim con risultato e zero irrisolti**.
Su `cloudbed-1_q050`, le D Sonnet A1 e A1_8R
hanno `original_d_json_status=valid_json`, nessun errore
del provider e identico motivo di `INVALID_OUTPUT`:
`AMBIGUOUS_TOOL_RESULT` nel bundle di evidenze.
Non ripetere nessuna delle due D.

La cella fa prima un preflight che verifica gli SHA-256 di
**tutti i 24 artefatti Gemini e i 10 artefatti Sonnet**
esistenti, release e codice pinned, split/manifest, journal,
ordine del piano e assenza dei nuovi stage. Il test OOD
rimane chiuso e Haiku non viene invocato.

**Fase A, senza API:** registra `cloudbed-1_q050/sonnet/A1_8R/C`
e poi K come `BLOCKED_DEPENDENCY`. Vengono creati
due nuovi artefatti logici senza claim; il journal deve
salire da **34 a 36 record**, mantenendo 31 claim.
La cella si arresta se uno dei record risultasse già
salvato; non rilanciarla se qualcosa fallisce.

**Fase B, API reali:** al massimo dieci stage Sonnet
mai tentati, nell'ordine esatto del piano:

| # | Caso | Harness | Stage |
|---:|---|---|---|
| 1 | cloudbed-2_q026 | A1 | D |
| 2 | cloudbed-2_q026 | A1 | C |
| 3 | cloudbed-2_q026 | A1 | K |
| 4 | cloudbed-2_q026 | A1_8R | D |
| 5 | cloudbed-2_q026 | A1_8R | C |
| 6 | cloudbed-2_q026 | A1_8R | K |
| 7 | cloudbed-2_q045 | A1 | D |
| 8 | cloudbed-2_q045 | A1 | C |
| 9 | cloudbed-2_q045 | A1 | K |
| 10 | cloudbed-2_q045 | A1_8R | D |

Modello `claude-sonnet-5-5`, segreto di Colab
`ANTHROPIC_API_KEY`. Il runner **non ha hard cap di costo**;
una D comprende più chiamate LLM e token, quindi controllare
il budget Anthropic prima di avviare. Il batch è
sequenziale, un solo tentativo per stage e arresto al
primo errore, output invalido o claim irrisolto.
**Non eseguire in parallelo e non ripetere la cella
dopo errore o disconnessione**, anche se qualche riga
di output manca: prima audit read-only del Drive.

## Unica cella Google Colab

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
    f"{PREFIX}cloudbed-2_q026:sonnet:A1:D",
    f"{PREFIX}cloudbed-2_q026:sonnet:A1:C",
    f"{PREFIX}cloudbed-2_q026:sonnet:A1:K",
    f"{PREFIX}cloudbed-2_q026:sonnet:A1_8R:D",
    f"{PREFIX}cloudbed-2_q026:sonnet:A1_8R:C",
    f"{PREFIX}cloudbed-2_q026:sonnet:A1_8R:K",
    f"{PREFIX}cloudbed-2_q045:sonnet:A1:D",
    f"{PREFIX}cloudbed-2_q045:sonnet:A1:C",
    f"{PREFIX}cloudbed-2_q045:sonnet:A1:K",
    f"{PREFIX}cloudbed-2_q045:sonnet:A1_8R:D",
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
assert len(sonnet) == 24 and target == sonnet[12:22], (
    "Continuation order differs from frozen Sonnet plan"
)
journal = RQ2DiscoveryClaimJournal(data_dir=root)
summary = journal.audit_restart()
assert summary["claims"] == summary["finished_with_matching_result"] == 31
assert summary["result_archive_discovery_count"] == 34
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
    "cloudbed-1_q050:A1:C": "597af38f53d185206053d8f0cfc9a42e697e3b3a913e80c68c72a88975900868",
    "cloudbed-1_q050:A1:K": "e9a203b60c5eb40d449cf8d1c953c6bce1f7127865ac133a07ca39a1938f94bf",
    "cloudbed-1_q050:A1_8R:D": "d6d3c14cc1359b010b9320d17655c0a2b3db893235922cf9c7369bc2fdac6eea",
}
assert len(known_sonnet) == 10
for short, digest in known_sonnet.items():
    case, harness, stage = short.split(":")
    sid = f"rq2_dryrun_workflow_preview_v0:{case}:sonnet:{harness}:{stage}"
    item = journal.store.load_discovery_stage(stage_id=sid)
    assert item is not None and item["record_sha256"] == digest
    if short in ("cloudbed-1_q050:A1:C", "cloudbed-1_q050:A1:K"):
        assert journal._read_claim(sid) is None
        assert item["status"] == "BLOCKED_DEPENDENCY"
        assert item["artifact"] == {}
    else:
        assert journal._read_claim(sid) is not None
        if short in ("cloudbed-1_q050:A1:D", "cloudbed-1_q050:A1_8R:D"):
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

# Sono stati archiviati esattamente i primi 10 stage Sonnet:
# 8 claim live e 2 C/K BLOCKED_DEPENDENCY offline.
assert len(sonnet) == 24
expected_ids = {
    f"rq2_dryrun_workflow_preview_v0:{short.split(':')[0]}:sonnet:"
    f"{short.split(':')[1]}:{short.split(':')[2]}"
    for short in known_sonnet
}
assert set(sonnet[:10]) == expected_ids
for sid in sonnet[10:]:
    assert journal._read_claim(sid) is None, "Sonnet already claimed: NO RETRY"
    assert journal.store.load_discovery_stage(stage_id=sid) is None, (
        "Sonnet already stored: NO REEXECUTION"
    )
haiku = [e["stage_id"] for e in plan["entries"] if (
    e["phase"] == "discovery" and e["logical_model"] == "haiku"
)]
assert len(haiku) == 24
for sid in haiku:
    assert journal._read_claim(sid) is None
    assert journal.store.load_discovery_stage(stage_id=sid) is None
assert sonnet[10] == "rq2_dryrun_workflow_preview_v0:cloudbed-1_q050:sonnet:A1_8R:C"
assert sonnet[11] == "rq2_dryrun_workflow_preview_v0:cloudbed-1_q050:sonnet:A1_8R:K"
assert sonnet[12] == "rq2_dryrun_workflow_preview_v0:cloudbed-2_q026:sonnet:A1:D"
old = "rq2_dryrun_workflow_preview_v0:cloudbed-1_q050:sonnet:A1:"
d = journal.store.load_discovery_stage(stage_id=old+"D")
c = journal.store.load_discovery_stage(stage_id=old+"C")
k = journal.store.load_discovery_stage(stage_id=old+"K")
assert c["dependency_record_hashes"] == {old+"D": d["record_sha256"]}
assert k["dependency_record_hashes"] == {old+"C": c["record_sha256"]}
for sid in target:
    assert journal._read_claim(sid) is None
    assert journal.store.load_discovery_stage(stage_id=sid) is None
print("SONNET_CONT02_PREFLIGHT_OK_10_NEW_STAGES_NO_API", flush=True)
"""
pre = subprocess.run(
    [sys.executable, "-c", precheck, *STAGES],
    cwd=REPO, env=base_env, text=True, capture_output=True,
)
if pre.returncode:
    print("SONNET_CONT02_PREFLIGHT_FAILED_NO_API", flush=True)
    raise RuntimeError("Offline integrity/abstention preflight failed: STOP")
print(pre.stdout.strip(), flush=True)
print("AUTHORIZED_SONNET_CONT02_COUNT: 10", flush=True)
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
base = "rq2_dryrun_workflow_preview_v0:cloudbed-1_q050:sonnet:A1_8R:"
journal = RQ2DiscoveryClaimJournal(data_dir=root)
recorder = RQ2DiscoveryStageRecorder(data_dir=root)
initial = journal.audit_restart()
assert initial["claims"] == initial["finished_with_matching_result"] == 31
assert initial["result_archive_discovery_count"] == 34
assert initial["unresolved_manual_review"] == 0
d = journal.store.load_discovery_stage(stage_id=base+"D")
assert d is not None and d["status"] == "INVALID_OUTPUT"
assert d["record_sha256"] == "d6d3c14cc1359b010b9320d17655c0a2b3db893235922cf9c7369bc2fdac6eea"
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
assert final["claims"] == final["finished_with_matching_result"] == 31
assert final["result_archive_discovery_count"] == 36
assert final["unresolved_manual_review"] == 0
print("SONNET_OFFLINE_BLOCK_K:"+json.dumps({
    "status": k["status"], "record_sha256": k["record_sha256"],
    "claim_created":False, "api_calls":0,
    "total_stored_records":36
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
    print("RQ2_SONNET_CONT02_STAGE:" + json.dumps(
        outcome, ensure_ascii=False, allow_nan=False
    ), flush=True)
except BaseException as exc:
    print("RQ2_SONNET_CONT02_ERROR:" + json.dumps({
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
        print(f"\n=== SONNET_CONT02 STAGE {index}/10: {sid} ===", flush=True)
        p = subprocess.run(
            [sys.executable, "-c", driver, sid],
            cwd=REPO, env=paid_env, text=True, capture_output=True,
        )
        results = [
            line[len("RQ2_SONNET_CONT02_STAGE:"):]
            for line in p.stdout.splitlines()
            if line.startswith("RQ2_SONNET_CONT02_STAGE:")
        ]
        errors = [
            line[len("RQ2_SONNET_CONT02_ERROR:"):]
            for line in p.stdout.splitlines()
            if line.startswith("RQ2_SONNET_CONT02_ERROR:")
        ]
        if p.returncode or len(results) != 1 or errors:
            for line in errors:
                print("SONNET_CONT02_STAGE_ERROR:", line, flush=True)
            print("SONNET_CONT02_STOP_NO_RETRY_MANUAL_AUDIT_REQUIRED", flush=True)
            raise RuntimeError("Sonnet continuation stopped: do not rerun this cell")
        result = json.loads(results[0])
        assert result["stage_id"] == sid
        finished.append(result)
        print("SONNET_CONT02_STAGE:", json.dumps(result, ensure_ascii=False), flush=True)
        if result["status"] != "RECORDED_COMPLETE":
            print("SONNET_CONT02_STOP_NONCOMPLETE_NO_RETRY", flush=True)
            raise RuntimeError("Noncomplete stage: audit before any continuation")
finally:
    # Rimuove la chiave dal dizionario anche in caso di errore.
    paid_env.pop("ANTHROPIC_API_KEY", None)

print("\nSTATUS: SONNET_CONT02_10_REAL_DISCOVERY_STAGES_COMPLETED")
print("SONNET_CONT02_COMPLETED:", len(finished))
print("NO_OTHER_STAGES_AUTORUN: TRUE")
print("OOD_TEST: LOCKED")
~~~

## Output atteso

Inviami `SONNET_CONT02_PREFLIGHT_OK_10_NEW_STAGES_NO_API`,
`SONNET_OFFLINE_BLOCK_C` e `SONNET_OFFLINE_BLOCK_K`,
le righe `SONNET_CONT02_STAGE` e l'eventuale stato:

```text
STATUS: SONNET_CONT02_10_REAL_DISCOVERY_STAGES_COMPLETED
SONNET_CONT02_COMPLETED: 10
NO_OTHER_STAGES_AUTORUN: TRUE
OOD_TEST: LOCKED
```

Se il batch completa, avremo 46 artefatti
(24 Gemini e 22 Sonnet), **41 claim** e
gli ultimi due stage Sonnet ancora non eseguiti
`cloudbed-2_q045 / A1_8R / C,K`.
Se il batch si interrompe, conservare tutti i risultati
e inviare lo stop: non rieseguire la cella.

Una risposta con `RECORDED_COMPLETE` è valida per
provenienza e contratto, non necessariamente corretta
rispetto alla ground truth. Ogni K `candidate`
richiede verifica indipendente per il knowledge transfer.
