# RQ2 — Audit batch01 interrotto su C INVALID_OUTPUT (offline)

Data: 12 novembre 2026. Questa procedura NON richiama LLM, non crea claim,
non crea o modifica artefatti, non consulta ground truth e non esegue stage K.
È una lettura dei file create-only gia' conservati su Drive.

## Evidenza riportata dopo la prima tranche reale

- GIT_HEAD esecuzione: b1241f73c92aac051e4f6dbe4bfbd68e7d19447c.
- 1/10 q032 gemini A1 C: RECORDED_COMPLETE, 5.615 token.
- 2/10 q032 gemini A1 K: RECORDED_COMPLETE, 6.036 token.
- 3/10 q032 gemini A1_8R D: RECORDED_COMPLETE, 35.105 token.
- 4/10 q032 gemini A1_8R C: INVALID_OUTPUT, 3.429 token.
- 5/10 q032 gemini A1_8R K: NON TENTATO e dipendenza C non valida;
  nessuna chiamata consentita. Possibile futuro BLOCKED_DEPENDENCY
  create-only, in una procedura separata e dopo audit.
- 6/10–10/10: NON TENTATI; eventuale ripresa deve essere a piano esplicito,
  senza il quinto stage dipendente e senza ripetere 1–4.
- I quattro nuovi tentativi hanno 50.185 token aggregati.
- Insieme alla D iniziale: 5 claim, 5 artefatti, 0 irrisolti,
  come da output dell'utente.
- I record non provano accuratezza contro GT; K RECORDED_COMPLETE
  significa formato valido, non regola deterministica certificata.

## Colab — una cella di audit di sola lettura

La cella funziona anche dopo reset del runtime (ripristina solo /content);
non invoca provider né legge output grezzi a video. L'analisi del contratto
usa la stessa funzione originale `validate_cause_probe` e l'allowlist E###
ricostruita dalla traiettoria D (senza GT). Stampa solo un'etichetta
di errore non sensibile e un motivo breve filtrato: **non** stampa
`raw_response`, `prediction`, prompt, telemetria o segreti.

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
import json
from evaluation.rq2_ck_provider_transport import _read_release
from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal
from evaluation.rq2_output_contracts import validate_cause_probe, ContractError
from evaluation.rq2_evidence_bundle import build_evidence_bundle, evidence_ids
from evaluation.rq2_discovery_stage_recorder import ALLOWED_TOOLS

root = Path("/content/drive/MyDrive/Tesi_OpenRCA")
release = _read_release(root)
assert release["test_unlocked"] is False
journal = RQ2DiscoveryClaimJournal(data_dir=root)
overview = journal.audit_restart()
assert overview["claims"] == overview["finished_with_matching_result"] == 5
assert overview["unresolved_manual_review"] == 0
assert overview["result_archive_discovery_count"] == 5

prefix = "rq2_dryrun_workflow_preview_v0:"
names = [
    ("cloudbed-1_q032", "A1", "D", "RECORDED_COMPLETE"),
    ("cloudbed-1_q032", "A1", "C", "RECORDED_COMPLETE"),
    ("cloudbed-1_q032", "A1", "K", "RECORDED_COMPLETE"),
    ("cloudbed-1_q032", "A1_8R", "D", "RECORDED_COMPLETE"),
    ("cloudbed-1_q032", "A1_8R", "C", "INVALID_OUTPUT"),
]
expected_record_sha = {
    "A1:D": "73c1006d134ffef5bad7cba380925546c84d58c2ed20ba1730f75f1f42bbdfe7",
    "A1:C": "611358878be6cd439bd2d66cf20607d0653a099ba6ad75dbceed4a3fe8b34a06",
    "A1:K": "200fd07a480f6e4c47a283c9e4dd39db707f4cb5b1a70acb5974e29b857a9742",
    "A1_8R:D": "f3b92c3722ff0f19d91159431b9923e63dfeb0423d147ebb71468004d5ef4a67",
    "A1_8R:C": "fb4e321c63452fed5ef632dcd2f3a6c2e10459d2d31ebf136678439595478bd9",
}
observed = []
for case, harness, stage, status in names:
    sid = f"{prefix}{case}:gemini:{harness}:{stage}"
    claim = journal._read_claim(sid)
    record = journal.store.load_discovery_stage(stage_id=sid)
    assert claim is not None and record is not None
    assert record["record_sha256"] == expected_record_sha[f"{harness}:{stage}"]
    assert record["status"] == status
    observed.append({"stage": f"{harness}:{stage}", "status": status,
                     "record_sha256": record["record_sha256"]})

invalid_sid = f"{prefix}cloudbed-1_q032:gemini:A1_8R:C"
c = journal.store.load_discovery_stage(stage_id=invalid_sid)
d = journal.store.load_discovery_stage(
    stage_id=f"{prefix}cloudbed-1_q032:gemini:A1_8R:D"
)
a = c["artifact"]
raw = a["raw_response"]
assert type(raw) is str and a["provider_error"] is None
bundle = build_evidence_bundle(
    d["artifact"]["diagnostic_run"]["tool_trajectory"],
    allowed_tool_names=ALLOWED_TOOLS
)
allowed = evidence_ids(bundle)
reason_code = "UNKNOWN"
try:
    validate_cause_probe(raw, allowed_evidence_ids=allowed)
except ContractError as exc:
    msg = str(exc)
    if msg.startswith("Invalid strict JSON response"):
        reason_code = "INVALID_JSON_SYNTAX_OR_WRAPPING"
    elif msg.startswith("cause probe: expected fields"):
        reason_code = "WRONG_JSON_FIELDS"
    elif "evidence" in msg.lower():
        reason_code = "EVIDENCE_IDS_INVALID_OR_MISSING"
    elif "confidence" in msg.lower():
        reason_code = "INVALID_CONFIDENCE"
    elif "predicted_fault_type" in msg.lower():
        reason_code = "INVALID_PREDICTED_TYPE_FIELD"
    elif "decision" in msg.lower() or "diagnosis" in msg.lower() or "abstain" in msg.lower():
        reason_code = "INVALID_DECISION_CONTRACT"
    else:
        reason_code = "OTHER_CONTRACT_VIOLATION"
else:
    reason_code = "RECHECK_VALIDATION_DISAGREEMENT"

remaining = [
    f"{prefix}cloudbed-1_q032:gemini:A1_8R:K",
    *[
      f"{prefix}cloudbed-1_q050:gemini:{h}:{st}"
      for h, st in (
          ("A1", "D"), ("A1", "C"), ("A1", "K"),
          ("A1_8R", "D"), ("A1_8R", "C")
      )
    ]
]
for sid in remaining:
    assert journal._read_claim(sid) is None
    assert journal.store.load_discovery_stage(stage_id=sid) is None
print(json.dumps({
    "audit": "BATCH01_STOP_READ_ONLY_AUDIT",
    "claims": overview["claims"],
    "finished_with_matching_result": overview["finished_with_matching_result"],
    "unresolved_manual_review": overview["unresolved_manual_review"],
    "preserved_records": observed,
    "invalid_c_reason_code": reason_code,
    "invalid_c_record_contract_error_type": a["contract_error_type"],
    "invalid_c_raw_response_sha256": c["artifact"].get("transport_receipt", {}).get(
        "raw_response_sha256"
    ),
    "invalid_c_usage_complete": a.get("transport_receipt", {}).get("usage", {}).get("complete"),
    "remaining_not_started": len(remaining),
    "k_after_invalid_c_requires_blocked_dependency": True,
    "can_reinvoke_invalid_c": False,
    "test_unlocked": False,
}, indent=2, ensure_ascii=False, allow_nan=False), flush=True)
"""
res = subprocess.run(
    [sys.executable, "-c", script], env=env, cwd=REPO,
    capture_output=True, text=True,
)
if res.returncode != 0:
    print("BATCH01_AUDIT_FAILED_NO_API")
    print("Non rieseguire gli stage; invia solo il tipo di errore.")
    raise RuntimeError("Audit offline failed; no retry")
print("\n=== AUDIT BATCH01 (SOLO LETTURA) ===")
print(res.stdout)
print("PROVIDER_API_REQUESTS: 0")
print("DATA_FILES_WRITTEN: 0")
print("STATUS: BATCH01_READ_ONLY_AUDIT_COMPLETE")
~~~

## Dopo l'audit

Se i cinque record sono integri: nessuna ripetizione di C invalida,
mai eseguire K q032/A1_8R. Essa può essere marcata offline come
`BLOCKED_DEPENDENCY` con una successiva operazione create-only
idempotente nel senso **no-overwrite** (una volta sola), senza claim
provider, e con verifica dell'identità C. I cinque stage q050
non tentati richiedono una nuova cella di continuazione che verifichi
la stessa lista congelata, gli stessi hash e lo stato corrente del
journal, con stop alla prima anomalia. L'esito C non valido resta
nelle statistiche di denominatore; non aggiungere fix post-hoc.

**NON** modificare il file del release firmato, né il prompt, né la
normalizzazione delle etichette o gli esperimenti RQ1.
