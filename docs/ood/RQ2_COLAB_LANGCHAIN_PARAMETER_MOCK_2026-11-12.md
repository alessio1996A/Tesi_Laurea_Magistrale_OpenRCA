# RQ2 — Prova dinamica offline LangChain → SDK: parametri di retry/timeout

**12 novembre 2026 · Stato: predisposta, non ancora eseguita.**

## Decisione tecnica

L'audit Colab statico `RQ2_COLAB_LANGCHAIN_BRIDGE_SOURCE_TRACE_2026-11-12.md`
ha mostrato nei file esattamente installati che LangChain Google costruisce
`HttpRetryOptions(attempts=max_retries)` e inoltra `timeout`; LangChain
Anthropic passa `max_retries` e `default_request_timeout` al client.

Rimane da verificare che la stessa installazione, quando configura oggetti
**locali** LangChain con parametri espliciti, costruisca realmente:
- Google, `max_retries=1` e `timeout=300s`: request config con
  `retry_options.attempts=1` e `timeout=300000ms`.
- Claude Sonnet 5.5, `max_retries=0`, `timeout=300s`,
  `max_tokens=4096`: client SDK `max_retries=0` e timeout 300s.

**300s è solo un parametro di PROVA, non un valore già deliberato per la
campagna.** Il codice di produzione continuerà ad usare RQ1 congelata
e a bloccare le API fino alla scelta e firma della policy RQ2-only.

Il nuovo modulo `src/evaluation/rq2_langchain_parameter_mock_probe.py`
verifica source SHA e package Colab, installa un blocco di tutte le
connessioni socket, utilizza chiavi letterali **fittizie**, costruisce gli
oggetti LangChain e legge esclusivamente la config SDK prima del dispatch.
**Non chiama** `model.invoke`, `generate_content`, `messages.create`
né un vero endpoint, non legge mai le chiavi Colab, Market o GT. Verifica
che `RELEASE_SHA256=None` e `PLAN_STATUS=DRAFT_NOT_EXECUTABLE`.

Questa prova **non certifica** timeout effettivi su request bloccate,
retry di rete, streaming/async/aiohttp o la piena traiettoria
`LangGraph → SDK`. Perciò tutti i gate scientifici e API restano falsi.

## Passo A: PyCharm

Da root progetto (nessun SDK Anthropic locale richiesto per gli unit test):

```powershell
git status --short
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_langchain_parameter_mock_probe.py" -v
```

**Attesi 8 test unitari**, senza provider. Attendere esito reale prima
di scrivere che sono superati.

## Passo B: Colab, nella sessione già ripristinata

```python
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path("/content/Tesi_OpenRCA_RQ2")
DEPS = Path("/content/rq2_prefreeze_packages_py313")
BRANCH = "feature/ood-knowledge-transfer-audit-2026-11-10"

assert (REPO / ".git").is_dir(), "Ripristinare il repository isolato RQ2"
assert DEPS.is_dir(), "Ripristinare prima le dipendenze Colab pinned"

dirty = subprocess.check_output(
    ["git", "status", "--porcelain"], cwd=REPO, text=True
).strip()
assert not dirty, "Git checkout non pulito: fermarsi prima del checkout"

subprocess.run(["git", "fetch", "origin", BRANCH], cwd=REPO, check=True)
head = subprocess.check_output(
    ["git", "rev-parse", "FETCH_HEAD"], cwd=REPO, text=True
).strip()
subprocess.run(["git", "checkout", "--detach", head], cwd=REPO, check=True)
print("GIT_RQ2_COMMIT:", head)

env = dict(os.environ)
env["PYTHONPATH"] = os.pathsep.join([str(DEPS), str(REPO / "src")])
env["PYTHONDONTWRITEBYTECODE"] = "1"

tests = subprocess.run(
    [sys.executable, "-m", "unittest", "discover", "-s", "src/tests",
     "-p", "test_rq2_langchain_parameter_mock_probe.py", "-v"],
    cwd=REPO, env=env, capture_output=True, text=True
)
print("=== UNIT TEST RQ2 PARAMETER MOCK ===")
print(tests.stderr[-6000:])
if tests.returncode:
    print(tests.stdout[-1500:])
    raise RuntimeError("Unit test RQ2 mock non superati")

proc = subprocess.run(
    [sys.executable, "-m", "evaluation.rq2_langchain_parameter_mock_probe",
     "--repo-dir", str(REPO)],
    cwd=REPO, env=env, capture_output=True, text=True
)
if proc.returncode:
    print("STDERR:", proc.stderr[-6000:])
    print("STDOUT:", proc.stdout[-1500:])
    raise RuntimeError("Local forwarding probe non superato, nessuna API effettuata")

report = json.loads(proc.stdout)
print("=== LANGCHAIN PARAMETER MOCK (NO NETWORK) ===")
print(json.dumps(report, indent=2, ensure_ascii=False))

assert report["status"] == (
    "LANGCHAIN_LOCAL_FORWARDING_CHECKED_NETWORK_HTTP_NOT_CERTIFIED"
)
assert report["google"]["sdk_http_retry_attempts"] == 1
assert report["google"]["sdk_http_timeout_milliseconds"] == 300000
assert report["anthropic"]["sdk_max_retries"] == 0
assert report["anthropic"]["sdk_timeout_seconds"] == 300.0
assert report["external_provider_requests"] == 0
assert report["real_credentials_used"] is False
assert report["sdk_http_transport_exercised"] is False
assert report["read_ground_truth"] is False
assert report["read_market"] is False
assert report["scientific_release_signed"] is False
assert report["can_execute_D"] is False
assert report["can_execute_CK"] is False
assert report["can_execute_test"] is False

print("RQ2 MOCK PARAMETER FORWARDING: CONTROLLI SUPERATI")
print("LIVE POLICY E RELEASE SCIENTIFICO: ANCORA BLOCCATI")
```

Riportare all'assistente output completo, soprattutto gli oggetti
`google` e `anthropic`, senza alterare i pacchetti. Se fallisce
un import o una costruzione locale, non cambiare le versioni: verificare
il traceback e correggere solo il probe prima di firmare qualsiasi release.
