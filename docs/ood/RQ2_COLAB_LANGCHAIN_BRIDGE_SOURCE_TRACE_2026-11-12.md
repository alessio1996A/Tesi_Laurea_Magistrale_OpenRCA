# RQ2 — Tracciamento statico del collegamento LangChain → SDK in Colab

**Stato:** eseguito realmente in Colab dall'utente il 12 novembre 2026, sorgenti SHA-256 verificati, ma trasporto effettivo non ancora certificato.

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


## Risultato reale Colab — output riportato dall'utente (12/11/2026)

Commit eseguito `8cc62f6f7c7c39f26258a44808ad228aa5113704`.
Status `EXACT_SOURCE_BRIDGE_INSPECTED_FOR_REVIEW_NOT_SDK_HTTP_CERTIFIED`.
La cella è terminata con `RQ2 SOURCE TRACE: CONTROLLI SUPERATI`.
Le seguenti righe si riferiscono ai **sorgenti installati SHA-pinned**,
non a un differente snapshot della repository upstream.

| Modulo | SHA-256 verificato |
|---|---|
| `langchain_google_genai/chat_models.py` | `589106719f2038805a27ddd0c44c23d5e4a4486ea0d7116b38a83d37722ac27f` |
| `langchain_anthropic/chat_models.py` | `c55a0cb8fed75b3d310dbddf03a455f95c3c1d47aab650317bf3c9e4bab62544` |
| `google/genai/_api_client.py` | `b179b80a126a35c98b98aeefa701950304c38c8a1e117136a2270a0901fd93e4` |
| `anthropic/_base_client.py` | `a42ef507300287261fe0b215023672a97f8a9b01216a135d614bbede72fff680` |

**Tracciamento Google LangChain:**
- L3867–L3868: `max_retries = kwargs.pop("max_retries", None)`, segue fallback alla proprietà del modello se `None`.
- L4100–L4108: se `max_retries` non nullo viene costruito `HttpRetryOptions(attempts=max_retries)`, insieme all'opzione `timeout`.
- L4112: merge per-request `http_options`.
- L4188 / L4231: `generate_content` sync/async; L4274 / L4335: stream sync/async.

**Tracciamento SDK Google:**
- L667 `retry_args` controlla configurazione retry.
- L1831–L1849: `_request` sync; override per-request con `retry_options`.
- L2030–L2052: `_async_request` include distinzione tra retry esplicito e percorso base.
- L1856, L1906 e L1988: nei percorsi async esiste la logica `implicit_retry`.
  **Non basta** l'output del mock `retry_args(None)=1` per escludere
  ritentativi nascosti nell'intera invocazione dell'agente.

**Tracciamento Anthropic:**
- `langchain-anthropic` L1414 default `max_retries=2`, ma la nostra factory RQ1
  lo sovrascrive con `0`; L1752 lo inoltra al client; L1758–L1759
  determinano l'inoltro del timeout. Nessun valore timeout esplicito nel
  sorgente RQ1 congelato.
- `anthropic` L442–L454 definisce retry e timeout lato SDK;
  L1247 / L2029 contengono `_request` sync/async;
  L1409 / L2195 contengono `_attempt_request` sync/async.

**Conclusione minima supportata dal codice:** il forwarding di retry e
timeout è presente nei sorgenti LangChain esaminati, ma nessuna invocazione
LangChain è stata esercitata dal trace. Per certificare i parametri
osservabili nel nostro utilizzo serve una prova *runtime* con chiavi
fittizie e connessione bloccata, su versioni SHA-identiche. I timeout
di rete reali e il funzionamento end-to-end di eventuali streaming restano
non verificati. Lo stato del piano rimane `DRAFT_NOT_EXECUTABLE`,
`RELEASE_SHA256=None`, zero API.
