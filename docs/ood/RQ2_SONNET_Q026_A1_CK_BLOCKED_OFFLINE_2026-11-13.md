# RQ2 — Sonnet q026/A1: C e K bloccate in modalità offline

**13 novembre 2026. Cella preparata, NON eseguita.**

L'audit ricevuto `SONNET_CONT02_READ_ONLY_AUDIT`
ha confermato **32 claim**, **37 record**,
zero manual review irrisolti e tre D Sonnet invalidate
per `AMBIGUOUS_TOOL_RESULT`, pur con
`original_d_json_status=valid_json` e senza
errori segnalati da Anthropic.

## Scopo e limiti

La cella non invoca alcun modello o provider, non carica
chiavi API, non tenta di riparare o ripetere la D
`cloudbed-2_q026/sonnet/A1/D`, non consulta GT,
non esegue OOD test e non modifica file sorgenti
o la release.

Prima di scrivere, riesegue un audit di sola lettura:
controlla package pinned, release, sorgenti, piano,
**tutti gli SHA-256 dei 24 record Gemini e 13 Sonnet**,
32 claim matched, 37 record, quattro dipendenze
q050 Sonnet precedentemente bloccate, e l'assenza
di tutti gli altri stage non tentati Sonnet/Haiku.
Ricalcola localmente la classe di errore delle tre
D invalidate e richiede `AMBIGUOUS_TOOL_RESULT`
per tutte e tre.

Successivamente crea **soltanto due artefatti
logici** con il recorder RQ2 congelato, in ordine:
- `cloudbed-2_q026/sonnet/A1/C` → `BLOCKED_DEPENDENCY`,
  senza claim provider.
- `cloudbed-2_q026/sonnet/A1/K` → `BLOCKED_DEPENDENCY`,
  senza claim provider.

Alla fine il journal deve avere **32 claim**
e **39 record**. Se la procedura si arresta dopo
la prima scrittura, non rieseguire la cella:
i file sono create-only e serve un nuovo audit.

Questa cella è un'operazione offline per completare
la registrazione dello stato sperimentale; **non
autorizza ulteriori chiamate Anthropic**.

## Cella unica Colab — no provider API

~~~python




from pathlib import Path
from google.colab import drive
import hashlib, json, os, subprocess, sys

drive.mount("/content/drive")
REPO = Path("/content/Tesi_OpenRCA_RQ2")
DEPS = Path("/content/rq2_prefreeze_packages_py313")
DATA = Path("/content/drive/MyDrive/Tesi_OpenRCA")
BRANCH = "feature/ood-knowledge-transfer-audit-2026-11-10"
URL = "https://github.com/alessio1996A/Tesi_Laurea_Magistrale_OpenRCA.git"
EXPECTED_RELEASE_SHA = "a35c02f830a3c5f97424e0cbf8653eda6cfa674b9c8c34d95d04627e1dba8c52"
EXPECTED_PIN_BLOB = "84c33c05b198d1dc483f7fef466d8df52942f000"

assert sys.version.split()[0] == "3.13.18", "Python drift"
assert DATA.is_dir() and not DATA.is_symlink()
assert not REPO.is_symlink() and not DEPS.is_symlink()
if not REPO.exists():
    subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch",
         "--branch", BRANCH, URL, str(REPO)],
        check=True, env=dict(os.environ, GIT_TERMINAL_PROMPT="0"),
    )
    print("REPO: CLONED")
else:
    assert (REPO / ".git").is_dir()
    print("REPO: REUSED")

PINS = [
    "langchain==1.4.7", "langchain-core==1.7.1",
    "langgraph==1.2.18", "langchain-google-genai==4.4.2",
    "langchain-anthropic==1.7.7", "google-genai==2.34.0",
    "anthropic==2.6.0", "google-auth==2.56.0",
    "pandas", "networkx", "python-dotenv",
]
sig = hashlib.sha256(("\n".join(PINS) + "\n" + sys.version).encode()).hexdigest()
marker = DEPS / ".rq2_packages_ready"
if not DEPS.exists():
    DEPS.mkdir(parents=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install",
         "--disable-pip-version-check", "--upgrade", "--target", str(DEPS), *PINS],
        check=True,
    )
    marker.write_text(sig + "\n", encoding="utf-8")
else:
    assert DEPS.is_dir() and marker.is_file() and not marker.is_symlink()
    assert marker.read_text().strip() == sig, "Package drift"

assert not subprocess.check_output(
    ["git", "-C", str(REPO), "status", "--porcelain"], text=True
).strip(), "Dirty checkout"
origin = subprocess.check_output(
    ["git", "-C", str(REPO), "remote", "get-url", "origin"], text=True
).strip()
assert origin in (URL, URL[:-4]), "Unexpected Git origin"
subprocess.run(
    ["git", "-C", str(REPO), "fetch", "--depth", "1", "origin", BRANCH],
    check=True, env=dict(os.environ, GIT_TERMINAL_PROMPT="0"),
)
head = subprocess.check_output(
    ["git", "-C", str(REPO), "rev-parse", "FETCH_HEAD"], text=True
).strip()
subprocess.run(
    ["git", "-C", str(REPO), "checkout", "--detach", head], check=True
)
print("GIT_HEAD:", head)
pin = subprocess.check_output(
    ["git", "-C", str(REPO), "rev-parse",
     "HEAD:src/evaluation/rq2_ck_provider_transport.py"], text=True
).strip()
assert pin == EXPECTED_PIN_BLOB, "Changed provider source pin"
release_path = DATA / "data/rq2/RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json"
assert release_path.is_file() and not release_path.is_symlink()
assert hashlib.sha256(release_path.read_bytes()).hexdigest() == EXPECTED_RELEASE_SHA

env = dict(os.environ)
env["PYTHONPATH"] = os.pathsep.join((str(DEPS), str(REPO / "src")))
env["PYTHONDONTWRITEBYTECODE"] = "1"
for key in (
    "GOOGLE_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
    "GOOGLE_GENAI_USE_VERTEXAI", "LANGSMITH_API_KEY",
    "LANGCHAIN_API_KEY", "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING",
):
    env.pop(key, None)

# No get_secret, no invoke, no stage claim, no raw output disclosure.
script = """

from pathlib import Path
import json, re
from evaluation.rq2_ck_provider_transport import _read_release
from evaluation.rq2_model_factory import assert_exact_runtime_snapshot
from evaluation.rq2_protocol_identity_preflight import preview_protocol_identity
from evaluation.rq2_dryrun_plan import preview_market
from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal
from evaluation.rq2_discovery_stage_recorder import ALLOWED_TOOLS
from evaluation.rq2_evidence_bundle import build_evidence_bundle, EvidenceBundleError

root = Path("/content/drive/MyDrive/Tesi_OpenRCA")
repo = Path("/content/Tesi_OpenRCA_RQ2")
release = _read_release(root)
assert release["test_unlocked"] is False
assert release["model_ids"]["sonnet"] == "claude-sonnet-5-5"
assert_exact_runtime_snapshot()
assert preview_protocol_identity(src_root=repo / "src")[
    "rq1_source_blob_sha1_match"
] is True
plan = preview_market(root)
assert plan["preview_sha256"] == release["plan_preview_sha256"]
journal = RQ2DiscoveryClaimJournal(data_dir=root)
audit = journal.audit_restart()
assert audit["claims"] == audit["finished_with_matching_result"] == 32
assert audit["unresolved_manual_review"] == 0
assert audit["result_archive_discovery_count"] == 37

known_gemini = {

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
    "cloudbed-1_q050:A1_8R:C": "f3f4aa409b25cdd92fe4bea5eb10aa84b558342e0e4b867aac14b37c54611167",
    "cloudbed-1_q050:A1_8R:K": "a9b6c001e2d98b315cb0b2767848b4b60f83d8f897136c77c2d7f2b82be6942b",
    "cloudbed-2_q026:A1:D": "7882f3db492d3659239349f0459c4b38e75f498fa216885aedda1569d5ee85ec",
}
assert len(known_gemini) == 24 and len(known_sonnet) == 13

prefix = "rq2_dryrun_workflow_preview_v0:"
blocked_gemini = {"cloudbed-1_q032:A1_8R:K"}
blocked_sonnet = {
    "cloudbed-1_q050:A1:C", "cloudbed-1_q050:A1:K",
    "cloudbed-1_q050:A1_8R:C", "cloudbed-1_q050:A1_8R:K",
}
invalid_gemini = {"cloudbed-1_q032:A1_8R:C"}
invalid_sonnet = {
    "cloudbed-1_q050:A1:D", "cloudbed-1_q050:A1_8R:D",
    "cloudbed-2_q026:A1:D",
}
for model, known in (("gemini", known_gemini), ("sonnet", known_sonnet)):
    for short, digest in known.items():
        case, harness, stage = short.split(":")
        sid = f"{prefix}{case}:{model}:{harness}:{stage}"
        record = journal.store.load_discovery_stage(stage_id=sid)
        assert record is not None and record["record_sha256"] == digest
        is_blocked = short in (
            blocked_gemini if model == "gemini" else blocked_sonnet
        )
        is_invalid = short in (
            invalid_gemini if model == "gemini" else invalid_sonnet
        )
        assert record["status"] == (
            "BLOCKED_DEPENDENCY" if is_blocked
            else "INVALID_OUTPUT" if is_invalid
            else "RECORDED_COMPLETE"
        )
        claim = journal._read_claim(sid)
        if is_blocked:
            assert claim is None and record["artifact"] == {}
        else:
            assert claim is not None
        if model == "sonnet" and is_invalid:
            assert record["artifact"]["evidence_bundle_sha256"] is None

# Verifica catena di provenienza dei due rami q050, senza API.
for harness in ("A1", "A1_8R"):
    base = f"{prefix}cloudbed-1_q050:sonnet:{harness}:"
    d = journal.store.load_discovery_stage(stage_id=base+"D")
    c = journal.store.load_discovery_stage(stage_id=base+"C")
    k = journal.store.load_discovery_stage(stage_id=base+"K")
    assert c["dependency_record_hashes"] == {base+"D": d["record_sha256"]}
    assert k["dependency_record_hashes"] == {base+"C": c["record_sha256"]}

sonnet = [
    e["stage_id"] for e in plan["entries"]
    if e["phase"] == "discovery" and e["logical_model"] == "sonnet"
]
haiku = [
    e["stage_id"] for e in plan["entries"]
    if e["phase"] == "discovery" and e["logical_model"] == "haiku"
]
assert len(sonnet) == len(haiku) == 24
actual_known = {
    f"{prefix}{short.split(':')[0]}:sonnet:{short.split(':')[1]}:{short.split(':')[2]}"
    for short in known_sonnet
}
assert set(sonnet[:13]) == actual_known
assert len(sonnet[13:]) == 11
assert sonnet[12] == f"{prefix}cloudbed-2_q026:sonnet:A1:D"
assert sonnet[13] == f"{prefix}cloudbed-2_q026:sonnet:A1:C"
assert sonnet[14] == f"{prefix}cloudbed-2_q026:sonnet:A1:K"
assert sonnet[15] == f"{prefix}cloudbed-2_q026:sonnet:A1_8R:D"
for sid in sonnet[13:] + haiku:
    assert journal._read_claim(sid) is None, "Unexpected claim"
    assert journal.store.load_discovery_stage(stage_id=sid) is None, (
        "Unexpected previously stored stage"
    )

# Classificazione dell'errore senza stampare messaggi raw o telemetry.
labels = (
    ("Unmatched tool calls", "UNMATCHED_TOOL_CALLS"),
    ("Unmatched tool result", "UNMATCHED_TOOL_RESULT"),
    ("Ambiguous/missing legacy", "AMBIGUOUS_TOOL_RESULT"),
    ("Tool call/result origin", "ORIGIN_MISMATCH"),
    ("Duplicate tool result", "DUPLICATE_TOOL_RESULT"),
    ("Duplicate tool_call_id", "DUPLICATE_TOOL_CALL_ID"),
    ("Tool result must be text", "NON_TEXT_TOOL_RESULT"),
    ("Tool result too large", "TOOL_RESULT_OVERSIZE"),
    ("Too many results", "TOO_MANY_RESULTS"),
    ("Trajectory event must", "MALFORMED_EVENT"),
    ("Unexpected trajectory event", "UNSUPPORTED_EVENT_KIND"),
    ("Unknown trajectory fields", "UNKNOWN_EVENT_FIELDS"),
    ("Tool not in explicit telemetry", "DISALLOWED_TOOL_NAME"),
    ("Tool arguments must", "MALFORMED_TOOL_ARGS"),
    ("Tool arguments too large", "TOOL_ARGS_OVERSIZE"),
    ("Potential scoring/ground-truth", "SENSITIVE_CONTENT_FILTER"),
    ("Trajectory contains non-JSON", "NONJSON_TRAJECTORY"),
    ("Invalid tool_call_id", "INVALID_TOOL_ID"),
    ("Invalid trajectory origin", "INVALID_ORIGIN"),
    ("Trajectory must be a bounded", "INVALID_TRAJECTORY_SHAPE"),
    ("Too many results for minimum", "EVIDENCE_TRUNCATION_GUARD"),
)
def classify(case, harness):
    sid = f"{prefix}{case}:sonnet:{harness}:D"
    record = journal.store.load_discovery_stage(stage_id=sid)
    assert record["status"] == "INVALID_OUTPUT"
    a = record["artifact"]
    trajectory = a["diagnostic_run"]["tool_trajectory"]
    assert type(trajectory) is list
    assert a["diagnostic_run"]["error"] is None
    assert a["tool_trajectory_issue"] in (
        "EvidenceBundleError", "KeyError", "ValueError", "TypeError"
    )
    result = "UNKNOWN_FAILURE_KIND"
    try:
        build_evidence_bundle(trajectory, allowed_tool_names=ALLOWED_TOOLS)
    except (EvidenceBundleError, KeyError, ValueError, TypeError) as exc:
        assert type(exc).__name__ == a["tool_trajectory_issue"]
        for prefix_, label in labels:
            if str(exc).startswith(prefix_):
                result = label
                break
    else:
        raise AssertionError("The stored invalid D was accepted by evidence bundler")
    status = a["original_d_json_status"]
    status = (
        status if type(status) is str and
        re.fullmatch(r"[A-Za-z0-9_:.+-]{1,70}", status)
        else "NOT_EXPOSED_OR_NOT_SIMPLE"
    )
    return {
        "record_sha256": record["record_sha256"],
        "reason_code": result,
        "issue_type": a["tool_trajectory_issue"],
        "original_d_json_status": status,
        "provider_error_present": False,
        "trajectory_events": len(trajectory),
        "tool_call_events": sum(
            type(e) is dict and e.get("tipo") == "tool_call"
            for e in trajectory
        ),
        "tool_result_events": sum(
            type(e) is dict and e.get("tipo") == "tool_result"
            for e in trajectory
        ),
    }

q050_a1 = classify("cloudbed-1_q050", "A1")
q050_a1_8r = classify("cloudbed-1_q050", "A1_8R")
q026_a1 = classify("cloudbed-2_q026", "A1")
assert q050_a1["reason_code"] == "AMBIGUOUS_TOOL_RESULT"
assert q050_a1_8r["reason_code"] == "AMBIGUOUS_TOOL_RESULT"
assert q026_a1["reason_code"] == "AMBIGUOUS_TOOL_RESULT"
print(json.dumps({
    "audit": "SONNET_CONT02_READ_ONLY_AUDIT",
    "claims": audit["claims"],
    "finished_with_matching_result": audit["finished_with_matching_result"],
    "unresolved_manual_review": audit["unresolved_manual_review"],
    "result_archive_discovery_count": audit["result_archive_discovery_count"],
    "gemini_records_verified": len(known_gemini),
    "sonnet_records_verified": len(known_sonnet),
    "sonnet_q050_a1_d": q050_a1,
    "sonnet_q050_a1_8r_d": q050_a1_8r,
    "sonnet_q026_a1_d": q026_a1,
    "three_invalid_d_same_reason": (
        q050_a1["reason_code"] == q050_a1_8r["reason_code"] == q026_a1["reason_code"]
    ),
    "q050_four_blocked_dependencies_verified": True,
    "sonnet_remaining_unattempted": len(sonnet[13:]),
    "sonnet_next_q026_a1_c_k_blocked_offline": True,
    "sonnet_next_independent_d": sonnet[15],
    "haiku_remaining_unattempted": len(haiku),
    "provider_api_requests": 0,
    "data_files_written": 0,
    "test_unlocked": False
}, ensure_ascii=False, allow_nan=False, indent=2), flush=True)
"""


res = subprocess.run(
    [sys.executable, "-c", script], env=env, cwd=REPO,
    capture_output=True, text=True,
)
if res.returncode != 0:
    print("SONNET_CONT02_AUDIT_FAILED_NO_API")
    print("Non rieseguire gli stage; invia solo il tipo di errore.")
    raise RuntimeError("Audit offline failed; no retry")
print("\n=== AUDIT SONNET CONT02 (SOLO LETTURA) ===")
print(res.stdout)
print("PROVIDER_API_REQUESTS: 0")
print("DATA_FILES_WRITTEN: 0")
print("STATUS: SONNET_Q026_BLOCK_PREFLIGHT_READ_ONLY_OK")

# La D originale è INVALID_OUTPUT e non viene richiamata.
# Solo registrazione di C e K come BLOCKED_DEPENDENCY.
block_worker = """
from pathlib import Path
import json
from evaluation.rq2_discovery_stage_recorder import RQ2DiscoveryStageRecorder
from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal

root = Path("/content/drive/MyDrive/Tesi_OpenRCA")
prefix = "rq2_dryrun_workflow_preview_v0:cloudbed-2_q026:sonnet:A1:"
model = "claude-sonnet-5-5"
journal = RQ2DiscoveryClaimJournal(data_dir=root)
recorder = RQ2DiscoveryStageRecorder(data_dir=root)
audit = journal.audit_restart()
assert audit["claims"] == audit["finished_with_matching_result"] == 32
assert audit["result_archive_discovery_count"] == 37
assert audit["unresolved_manual_review"] == 0

d = journal.store.load_discovery_stage(stage_id=prefix+"D")
assert d is not None and d["status"] == "INVALID_OUTPUT"
assert d["record_sha256"] == (
    "7882f3db492d3659239349f0459c4b38e75f498fa216885aedda1569d5ee85ec"
)
assert d["artifact"]["tool_trajectory_issue"] == "EvidenceBundleError"
assert d["artifact"]["original_d_json_status"] == "valid_json"
assert d["artifact"]["diagnostic_run"]["error"] is None

for suffix in ("C", "K"):
    sid = prefix+suffix
    assert journal._read_claim(sid) is None, "Unexpected C/K claim"
    assert journal.store.load_discovery_stage(stage_id=sid) is None, (
        "C/K already stored: do not retry"
    )

rc = recorder.record_c(
    stage_id=prefix+"C", model_id_proposed=model,
    raw_response=None, provider_error=None, transport_receipt=None
)
c = journal.store.load_discovery_stage(stage_id=prefix+"C")
assert rc["status"] == c["status"] == "BLOCKED_DEPENDENCY"
assert rc["record_sha256"] == c["record_sha256"]
assert c["artifact"] == {}
assert c["dependency_record_hashes"] == {prefix+"D": d["record_sha256"]}
assert journal._read_claim(prefix+"C") is None
print("SONNET_Q026_BLOCK_C:" + json.dumps({
    "stage_id": prefix+"C",
    "status": c["status"],
    "record_sha256": c["record_sha256"],
    "claim_created":False,
    "provider_api_calls":0
}, allow_nan=False),flush=True)

rk = recorder.record_k(
    stage_id=prefix+"K", model_id_proposed=model,
    raw_response=None, provider_error=None, transport_receipt=None
)
k = journal.store.load_discovery_stage(stage_id=prefix+"K")
assert rk["status"] == k["status"] == "BLOCKED_DEPENDENCY"
assert rk["record_sha256"] == k["record_sha256"]
assert k["artifact"] == {}
assert k["dependency_record_hashes"] == {prefix+"C": c["record_sha256"]}
assert journal._read_claim(prefix+"K") is None

end = journal.audit_restart()
assert end["claims"] == end["finished_with_matching_result"] == 32
assert end["result_archive_discovery_count"] == 39
assert end["unresolved_manual_review"] == 0
print("SONNET_Q026_BLOCK_K:" + json.dumps({
    "stage_id": prefix+"K",
    "status": k["status"],
    "record_sha256": k["record_sha256"],
    "claim_created":False,
    "provider_api_calls":0,
    "total_claims":end["claims"],
    "total_stored_records":end["result_archive_discovery_count"]
}, allow_nan=False),flush=True)
"""
b_result = subprocess.run(
    [sys.executable, "-c", block_worker],
    cwd=REPO, env=env, capture_output=True, text=True
)
for line in b_result.stdout.splitlines():
    if line.startswith(("SONNET_Q026_BLOCK_C:","SONNET_Q026_BLOCK_K:")):
        print(line,flush=True)
if b_result.returncode or "SONNET_Q026_BLOCK_K:" not in b_result.stdout:
    print("STATUS: SONNET_Q026_BLOCK_STOP_NO_RETRY_AUDIT_REQUIRED",flush=True)
    raise RuntimeError("Create-only offline block interrupted; DO NOT rerun")
print("PROVIDER_API_REQUESTS_FOR_BLOCK: 0")
print("STATUS: SONNET_Q026_CK_BLOCKED_OFFLINE_COMPLETED")
print("OOD_TEST: LOCKED")

~~~

## Output da inoltrare

Condividere le righe
`SONNET_Q026_BLOCK_C`, `SONNET_Q026_BLOCK_K`
e:

```text
STATUS: SONNET_Q026_CK_BLOCKED_OFFLINE_COMPLETED
OOD_TEST: LOCKED
```

Dopo il risultato, il successivo stage Sonnet
indipendente rimane `cloudbed-2_q026/sonnet/A1_8R/D`,
ancora **non tentato**. Prima di ulteriori spese API
si valuterà il rischio di incorrere nello stesso
problema di identificazione dei risultati tool.
