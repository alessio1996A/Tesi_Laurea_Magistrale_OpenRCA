# RQ2 — Audit offline Sonnet Batch 01 interrotto su D q050/A1

**13 novembre 2026; cella preparata, non eseguita.**

Il Batch 01 Sonnet ha effettuato 7 tentativi reali:
6 `RECORDED_COMPLETE` e 1 `INVALID_OUTPUT`, e poi
ha interrotto il batch prima degli ultimi tre stage.
Il settimo stage `cloudbed-1_q050/sonnet/A1/D` ha consumato
157.030 token e ha già un claim e un record create-only.

La cella qui sotto effettua **soltanto audit di lettura**.
Non costruisce client LLM, non accede ad Anthropic, non crea
claim o stage, non tenta di riparare output e non consulta
la ground truth. Il `git fetch` e l'eventuale `pip install`
interessano esclusivamente `/content` di Colab;
**non scrivono su Drive**.

La verifica controlla:
- SHA release originale sul Drive;
- blob frozen del trasporto;
- versione Python e dipendenze pinned;
- stato 30 claim + 31 record senza unresolved;
- tutti i **24 hash Gemini** e i **7 hash Sonnet**;
- assenza di claim/record per i rimanenti 17 stage Sonnet
  e tutti i 24 Haiku;
- categoria tecnica di errore `tool_trajectory_issue`,
  riprodotta richiamando **solo la funzione locale**
  `build_evidence_bundle` con la traiettoria già salvata;
- validità JSON finale D come metadato **distinto**
  (`original_d_json_status`, solo se valore breve e sicuro).

**Non riporta raw_response, fault type, prompt, telemetria
né segreti. Non rieseguire il batch Sonnet precedente.**

## Unica cella Colab — audit offline, zero API

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
from evaluation.rq2_ck_provider_transport import _read_release
from evaluation.rq2_model_factory import assert_exact_runtime_snapshot
from evaluation.rq2_protocol_identity_preflight import preview_protocol_identity
from evaluation.rq2_dryrun_plan import preview_market
from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal
from evaluation.rq2_discovery_stage_recorder import ALLOWED_TOOLS
from evaluation.rq2_evidence_bundle import build_evidence_bundle, EvidenceBundleError
import json, re

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
assert audit["claims"] == audit["finished_with_matching_result"] == 30
assert audit["unresolved_manual_review"] == 0
assert audit["result_archive_discovery_count"] == 31

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
}
assert len(known_gemini) == 24 and len(known_sonnet) == 7
prefix = "rq2_dryrun_workflow_preview_v0:"

for logical_model, known in (("gemini", known_gemini), ("sonnet", known_sonnet)):
    for short, digest in known.items():
        case, harness, stage = short.split(":")
        sid = f"{prefix}{case}:{logical_model}:{harness}:{stage}"
        record = journal.store.load_discovery_stage(stage_id=sid)
        assert record is not None and record["record_sha256"] == digest
        claim = journal._read_claim(sid)
        if logical_model == "gemini" and short == "cloudbed-1_q032:A1_8R:K":
            assert claim is None and record["status"] == "BLOCKED_DEPENDENCY"
        else:
            assert claim is not None
        if logical_model == "sonnet":
            expected = "INVALID_OUTPUT" if short == "cloudbed-1_q050:A1:D" else "RECORDED_COMPLETE"
            assert record["status"] == expected

sonnet = [
    e["stage_id"] for e in plan["entries"]
    if e["phase"] == "discovery" and e["logical_model"] == "sonnet"
]
assert len(sonnet) == 24
assert sonnet[6] == f"{prefix}cloudbed-1_q050:sonnet:A1:D"
for sid in sonnet[7:]:
    assert journal._read_claim(sid) is None, "Other Sonnet claim exists"
    assert journal.store.load_discovery_stage(stage_id=sid) is None, (
        "Other Sonnet result exists"
    )
haiku = [
    e["stage_id"] for e in plan["entries"]
    if e["phase"] == "discovery" and e["logical_model"] == "haiku"
]
assert len(haiku) == 24
for sid in haiku:
    assert journal._read_claim(sid) is None, "Haiku claim unexpectedly present"
    assert journal.store.load_discovery_stage(stage_id=sid) is None, (
        "Haiku result unexpectedly present"
    )

target = journal.store.load_discovery_stage(
    stage_id=f"{prefix}cloudbed-1_q050:sonnet:A1:D"
)
a = target["artifact"]
run = a["diagnostic_run"]
assert run["error"] is None, "This source branch would mark errors PROVIDER_ERROR"
assert a["evidence_bundle_sha256"] is None
assert a["tool_trajectory_issue"] in (
    "EvidenceBundleError", "KeyError", "TypeError", "ValueError"
)
trajectory = run["tool_trajectory"]
assert type(trajectory) is list
issue_kind = a["tool_trajectory_issue"]
detail_code = "UNKNOWN_FAILURE_KIND"

try:
    build_evidence_bundle(trajectory, allowed_tool_names=ALLOWED_TOOLS)
except (EvidenceBundleError, KeyError, TypeError, ValueError) as exc:
    assert type(exc).__name__ == issue_kind
    msg = str(exc)
    # Classify without showing unsafe free-form tool outputs or exceptions.
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
    for prefix_, label in labels:
        if msg.startswith(prefix_):
            detail_code = label
            break
else:
    raise AssertionError("Stored D invalid, but evidence builder now accepts trajectory")

json_status = a["original_d_json_status"]
safe_json_status = (
    json_status if type(json_status) is str
    and re.fullmatch(r"[A-Za-z0-9_:.+-]{1,70}", json_status)
    else "NOT_EXPOSED_OR_NOT_SIMPLE"
)
events = {
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

print(json.dumps({
    "audit": "SONNET_BATCH01_READ_ONLY_AUDIT",
    "claims": audit["claims"],
    "finished_with_matching_result": audit["finished_with_matching_result"],
    "unresolved_manual_review": audit["unresolved_manual_review"],
    "result_archive_discovery_count": audit["result_archive_discovery_count"],
    "gemini_records_verified": len(known_gemini),
    "sonnet_records_verified": len(known_sonnet),
    "sonnet_d_invalid_record_sha256": target["record_sha256"],
    "d_invalid_reason_code": detail_code,
    "d_invalid_issue_type": issue_kind,
    "original_d_json_status": safe_json_status,
    "d_provider_error_present": run["error"] is not None,
    **events,
    "sonnet_unattempted_stages": len(sonnet[7:]),
    "sonnet_next_C_K_must_be_blocked_offline": True,
    "sonnet_next_independent_D": sonnet[9],
    "haiku_unattempted_stages": len(haiku),
    "can_reinvoke_invalid_d": False,
    "test_unlocked": False,
}, ensure_ascii=False, allow_nan=False, indent=2), flush=True)

"""
res = subprocess.run(
    [sys.executable, "-c", script], env=env, cwd=REPO,
    capture_output=True, text=True,
)
if res.returncode != 0:
    print("SONNET_BATCH01_AUDIT_FAILED_NO_API")
    print("Non rieseguire gli stage; invia solo il tipo di errore.")
    raise RuntimeError("Audit offline failed; no retry")
print("\n=== AUDIT SONNET BATCH01 (SOLO LETTURA) ===")
print(res.stdout)
print("PROVIDER_API_REQUESTS: 0")
print("DATA_FILES_WRITTEN: 0")
print("STATUS: SONNET_BATCH01_READ_ONLY_AUDIT_COMPLETE")
~~~

## Come proseguire dopo il controllo

Inviare il JSON stampato sotto
`=== AUDIT SONNET BATCH01 (SOLO LETTURA) ===`
e la riga `STATUS: SONNET_BATCH01_READ_ONLY_AUDIT_COMPLETE`.

Se l'audit conferma l'integrità:
1. Registrare `cloudbed-1_q050/sonnet/A1/C` come
   `BLOCKED_DEPENDENCY` in sola modalità offline,
   senza claim o Anthropic API, usando `record_c`.
2. Solo dopo, registrare
   `cloudbed-1_q050/sonnet/A1/K` come
   `BLOCKED_DEPENDENCY` offline via `record_k`.
3. La D `cloudbed-1_q050/sonnet/A1_8R/D` non è stata tentata
   ed è indipendente dal ramo A1: potrà essere eseguita
   in una **nuova cella di continuazione** pre-verificata,
   senza ripetere stage Sonnet o Gemini precedenti.

Lo stato `INVALID_OUTPUT` di D deriva da una
violazione delle invarianti di costruzione dell'evidence bundle,
non necessariamente da un errore JSON finale di D:
il metadato del recorder lo distingue. I risultati
non vanno modificati a posteriori.

I test OOD rimangono `LOCKED`; nessuna nuova regola K
è approvata per il trasferimento.
