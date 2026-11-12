# RQ2 — Prova locale dei retry SDK con trasporto finto (12 novembre 2026)

**Milestone:** dopo esito `7/7 OK` su Colab e impronte sorgente esatte
di Anthropic, Google e integrazioni LangChain. **Non è una chiamata a LLM**.

## Cosa testa e cosa NON testa

- `google-genai 2.34.0`: invoca `retry_args` e `tenacity.Retrying`
  con una *funzione Python in memoria* che simula `httpx.ConnectError`.
  Verifica i conteggi `None→1`, `attempts=1→1`, `attempts=2→2`.
  Non crea `genai.Client`.
- `anthropic 2.6.0`: costruisce un SDK client con **solo**
  `httpx2.MockTransport`, chiave e base URL sintetici, e risposta
  artificiale HTTP 503. Con `max_retries=0` attende **un solo invio al mock**.
  Il dominio `no-network.invalid` non è raggiunto.
- La CLI è fail-closed: prima controlla la factory RQ1, esatte sei versioni
  Colab e le quattro impronte provider già osservate.
- Non testa ancora **LangChain→SDK end-to-end**, l'esatto wiring di
  `ChatGoogleGenerativeAI.max_retries`, i percorsi streaming,
  l'eventuale `aiohttp` implicit retry, la gestione dei veri timeout o
  il timeout effettivo su stalli di rete. Restano da bloccare e verificare
  prima della firma del release, eventualmente con wrapper RQ2-only.
- Nessuna chiave real-world, nessun accesso a Market/GT/predizioni,
  nessun rilascio di stage o attività a pagamento. `RELEASE_SHA256=None`
  resta invariato. **8 test sintetici PyCharm non ancora attestati.**

## Prima parte: PyCharm Windows

Dalla root del progetto:

```powershell
git status --short
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_sdk_retry_mock_probe.py" -v
```

**Attesi 8 test unitari**, tutti in stdlib e senza importare SDK;
l'esito deve essere confermato dall'utente.

Non lanciare la CLI reale di `rq2_sdk_retry_mock_probe` in PyCharm:
le versioni installate sono differenti e il gate fail-closed
rifiuterà l'ambiente locale.

## Seconda parte: Colab — unica cella

Questa cella si esegue nella **stessa sessione Colab** preparata in
`RQ2_COLAB_SDK_POLICY_SOURCE_AUDIT_2026-11-12.md`.
I percorsi vanno verificati; non installare pacchetti per silenziare
eventuali scostamenti di versione.

```python
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path("/content/Tesi_OpenRCA_RQ2")
DEPS = Path("/content/rq2_prefreeze_packages_py313")
BRANCH = "feature/ood-knowledge-transfer-audit-2026-11-10"

assert (REPO / ".git").is_dir(), "Ripristinare prima il repository RQ2"
assert DEPS.is_dir(), "Ripristinare prima i pacchetti Colab già isolati"
status = subprocess.check_output(
    ["git", "status", "--porcelain"], cwd=REPO, text=True
).strip()
assert not status, "Checkout Colab non pulito: controllare prima lo stato Git"

subprocess.run(["git", "fetch", "origin", BRANCH], cwd=REPO, check=True)
head = subprocess.check_output(
    ["git", "rev-parse", "FETCH_HEAD"], cwd=REPO, text=True
).strip()
subprocess.run(["git", "checkout", "--detach", head], cwd=REPO, check=True)
print("GIT_RQ2_COMMIT:", head)

env = dict(os.environ)
env["PYTHONPATH"] = os.pathsep.join([str(DEPS), str(REPO / "src")])

unit = subprocess.run(
    [sys.executable, "-m", "unittest", "discover",
     "-s", "src/tests", "-p", "test_rq2_sdk_retry_mock_probe.py", "-v"],
    cwd=REPO, env=env, capture_output=True, text=True
)
print("=== TEST RQ2 SDK MOCK ===")
print(unit.stderr[-7000:])
if unit.returncode:
    print(unit.stdout[-2000:])
    raise RuntimeError("Test unitari SDK mock non superati")

result = subprocess.run(
    [sys.executable, "-m", "evaluation.rq2_sdk_retry_mock_probe",
     "--repo-dir", str(REPO)],
    cwd=REPO, env=env, capture_output=True, text=True,
)
if result.returncode:
    # Stampare errori, ma NON ritentare automaticamente.
    print("STDOUT:", result.stdout[-2000:])
    print("STDERR:", result.stderr[-5000:])
    raise RuntimeError("Prova locale SDK fallita, controllare il dettaglio")

report = json.loads(result.stdout)
print("=== SDK OFFLINE MOCK REPORT ===")
print(json.dumps(report, ensure_ascii=False, indent=2))
assert report["google"]["sdk_retry_args_local_attempts"] == {
    "default_no_options": 1,
    "explicit_attempts_1": 1,
    "explicit_attempts_2": 2,
}
assert report["anthropic"]["sdk_mock_503_attempts"] == 1
assert report["real_provider_requests"] == 0
assert report["scientific_release_signed"] is False
assert report["can_execute_D"] is False
assert report["can_execute_CK"] is False
assert report["can_execute_test"] is False
print("SDK OFFLINE MOCK: CONTROLLI LOCALI SUPERATI")
print("ATTENZIONE: LANGCHAIN END-TO-END/STREAMING/TIMEOUT NON CERTIFICATI")
```

L'output può essere riportato integralmente all'assistente, senza
chiavi o token. Una failure locale non autorizza retry su provider reali;
il tool non contiene tale funzionalità. **Prima del release** resta
obbligatorio il successivo audit su wiring LangChain, eventuali retry
impliciti e timeout.

Riferimenti upstream esatti: Google `python-genai/v2.34.0`
`google/genai/_api_client.py`; Anthropic
`anthropic-sdk-python/v2.6.0` `src/anthropic/_base_client.py`.
