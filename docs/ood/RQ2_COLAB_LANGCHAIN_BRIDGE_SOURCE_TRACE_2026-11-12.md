# RQ2 — Tracciamento statico del collegamento LangChain → SDK in Colab

**Stato:** preparato per esecuzione; risultato reale ancora da raccogliere.

## Scopo

Dopo `8/8 OK` e la prova fake SDK di Google e Anthropic, dobbiamo
ispezionare **le integrazioni effettivamente installate** in Colab prima
di dichiarare verificata la policy `NO_AUTOMATIC_RETRY` del nostro agente.

Il modulo `src/evaluation/rq2_langchain_bridge_source_trace.py`:
- si rifiuta di operare se una delle **sei versioni attese** o dei **quattro
  SHA dei file sorgente** differisce dall'audit Colab;
- rifiuta repository con `RELEASE_SHA256` non nullo o piano non DRAFT;
- legge solo sorgenti installati di `langchain-google-genai`,
  `langchain-anthropic`, `google-genai`, `anthropic`, controlla la
  parseability Python AST e produce **estratti con numeri di riga** su
  retry, timeout, HTTP options e metodi di invocazione;
- non esegue neppure un `ChatGoogleGenerativeAI` o un `ChatAnthropic`,
  non usa API keys e non legge Market, ground truth o risposte LLM;
- mantiene `google_langchain_retry_forwarding_verified=false`,
  `anthropic_langchain_retry_forwarding_verified=false`,
  `request_timeout_enforcement_verified=false` finché non seguono
  controlli effettivi su trasporto fake end-to-end.

Questo **non è un altro test di performance**, né un nuovo protocollo:
è un controllo della corretta integrazione del trasporto RQ2.

## Unica cella Colab (ambiente già preparato)

```python
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path("/content/Tesi_OpenRCA_RQ2")
DEPS = Path("/content/rq2_prefreeze_packages_py313")
BRANCH = "feature/ood-knowledge-transfer-audit-2026-11-10"

assert (REPO / ".git").is_dir(), "Ripristinare il checkout RQ2"
assert DEPS.is_dir(), "Ripristinare le dipendenze isolate RQ2"
dirty = subprocess.check_output(
    ["git", "status", "--porcelain"], cwd=REPO, text=True
).strip()
assert not dirty, "Checkout Colab non pulito: fermarsi"

subprocess.run(["git", "fetch", "origin", BRANCH], cwd=REPO, check=True)
head = subprocess.check_output(
    ["git", "rev-parse", "FETCH_HEAD"], cwd=REPO, text=True
).strip()
subprocess.run(["git", "checkout", "--detach", head], cwd=REPO, check=True)
print("GIT_RQ2_COMMIT:", head)

env = dict(os.environ)
env["PYTHONPATH"] = os.pathsep.join([str(DEPS), str(REPO / "src")])
env["PYTHONDONTWRITEBYTECODE"] = "1"

result = subprocess.run(
    [sys.executable, "-m",
     "evaluation.rq2_langchain_bridge_source_trace",
     "--repo-dir", str(REPO)],
    cwd=REPO, env=env, text=True, capture_output=True
)
if result.returncode != 0:
    print("STDERR:", result.stderr[-5000:])
    print("STDOUT:", result.stdout[-1500:])
    raise RuntimeError("Trace sorgenti SDK/LangChain non superato")

report = json.loads(result.stdout)
assert report["status"] == (
    "EXACT_SOURCE_BRIDGE_INSPECTED_FOR_REVIEW_NOT_SDK_HTTP_CERTIFIED"
)
assert report["colab_package_versions_match"] is True
assert report["rq1_factory_unchanged"] is True
assert report["rq2_release_sha_unpinned"] is True
assert report["provider_api_calls"] == 0
assert report["read_ground_truth"] is False
assert report["read_market"] is False
assert report["read_predictions"] is False
assert report["files_written"] is False
assert report["scientific_discovery_release_signed"] is False
for gate in (
    "google_langchain_retry_forwarding_verified",
    "anthropic_langchain_retry_forwarding_verified",
    "google_async_streaming_no_hidden_retry_verified",
    "request_timeout_enforcement_verified",
    "can_execute_D", "can_execute_CK", "can_execute_test",
):
    assert report[gate] is False, gate

print("=== RQ2 LANGCHAIN -> SDK, SORGENTI PINNATE ===")
print("STATUS:", report["status"])
for package, max_lines in (
    ("langchain-google-genai", 60),
    ("langchain-anthropic", 40),
    ("google-genai", 25),
    ("anthropic", 20),
):
    details = report["source_trace"][package]
    assert details["python_ast_parse_ok"] is True
    print("\nPACKAGE:", package)
    print("SOURCE_SHA256:", details["sha256"])
    print("KEYWORD_COUNTS:", json.dumps(details["term_match_counts"]))
    for line in details["matched_lines"][:max_lines]:
        print(f"L{line['line']}: {line['text']}")
print("\nRQ2 SOURCE TRACE: CONTROLLI SUPERATI")
print("NESSUNA API LLM, NO LIVE RETRY/TIMEOUT CERTIFICATION")
```

Inviare il testo stampato (inclusi i numeri di riga) per un audit
dei punti in cui LangChain costruisce i client, trasmette retry/timeout
ed esegue streaming; il programma **non** stampa credenziali.

## Stato dopo questa cella

Anche se la cella riesce, `RELEASE_SHA256=None`, `PLAN_STATUS=DRAFT_NOT_EXECUTABLE`,
D/C/K/test non sono eseguibili. **Solo dopo aver compreso i quattro sorgenti**
decideremo l'eventuale wrapper RQ2-only e un test end-to-end con trasporto
finto. Nessuna modifica ai 13 blob di RQ1.
