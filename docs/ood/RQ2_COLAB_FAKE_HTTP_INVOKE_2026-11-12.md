# RQ2 — Ultimo audit tecnico mirato: LangChain invoke, HTTP finto, nessuna API

**12 novembre 2026 — PREPARATO, NON ANCORA ATTESTATO SU COLAB.**
Questa prova chiude il solo dubbio sul numero di richieste HTTP *sincrone*
nel percorso LangChain → SDK quando il server restituisce 503.

## Scopo e limiti

- Usa esattamente le sei versioni già verificate in Colab, con SHA-256
  dei quattro sorgenti già verificati dal preflight.
- Per Google `gemini-3.5-flash-lite` crea un `ChatGoogleGenerativeAI`
  con credenziale letterale falsa, `max_retries=1` e `timeout=300s`;
  sostituisce il client HTTP sottostante con **httpx/httpx2.MockTransport**
  che risponde soltanto 503.
- Per Claude Sonnet 5.5 crea `ChatAnthropic` con credenziale falsa,
  `max_retries=0`, `max_tokens=4096`, `timeout=300s`, e sostituisce
  il client Anthropic con uno che può usare **soltanto** `httpx2.MockTransport`.
- Per ciascun provider esegue due chiamate `model.invoke` con testo
  sintetico: una **senza tool** (analoga a C/K), l'altra `bind_tools`
  (analoga alla D). **Nessun tool viene eseguito.**
- Blocca a livello `socket` le connessioni, anche ai nomi locali,
  sia all'interno dei helper sia al livello della CLI. Nessun uso di
  API key reali; non legge ground truth, Market.zip o predizioni.
- Un esito `503` proveniente dal MockTransport con **esattamente 1
  invio per chiamata** è un successo del test. Se il numero è 0 o >1,
  si considera fallito e si conservano i gate chiusi.
- Non esercita LangGraph completo con telemetria, né `ainvoke`,
  `stream`, `astream`, né timeout fisico sotto socket stall: non
  sostenere quelle proprietà. I timeout 300s restano **proposta**.
- `RELEASE_SHA256=None` e `PLAN_STATUS=DRAFT_NOT_EXECUTABLE`
  devono rimanere tali anche se il test è positivo.

## Errore dei test PyCharm e correzione circoscritta (12 novembre 2026)

**Primo output effettivo PyCharm:** `Ran 8 tests in 0.010s`,
`FAILED (failures=1, errors=1)`; 6 test passati,
`test_mocked_503_must_be_observed_once` ERROR e
`test_nonerror_fake_transport_response_is_rejected` FAIL.

**Causa precisa nel test:** `type("FakeMessages", (), {"HumanMessage":
lambda **kwargs: ...})()` inserisce una funzione dentro una classe;
l'accesso tramite istanza produce un **metodo bound** e Python gli passa
`self` anche se il lambda accetta solo keyword arguments. La costruzione
del messaggio genera `TypeError` prima di `model.invoke`; l'handler
generico osserva quindi un conteggio HTTP finto pari a zero. **Non è
un errore del provider** e non esiste una richiesta API reale in questo test.

**Fix:** sostituiti i tre finti moduli messaggi con un vero
`types.ModuleType("langchain_core.messages")` e funzioni assegnate
all'istanza ModuleType: non c'è più il binding `self` imprevisto.
Il fix riguarda **solo** `src/tests/test_rq2_langchain_fake_http_invoke.py`.
La funzione di prova HTTP vera, factory RQ1 e gate release non cambiano.
Una riproduzione sintetica con sole librerie standard ha superato
entrambi i percorsi prima difettosi; **non è ancora l'attestazione
dell'intera suite PyCharm**.

**Azione:** prima ripetere gli 8 test PyCharm sul nuovo commit.
Solo se sono tutti `OK`, utilizzare la successiva cella Colab.
Non reinstallare pacchetti e non attivare API a pagamento.

## Fase A: PyCharm (unit test stdlib, nessun provider)

```powershell
git status --short
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_langchain_fake_http_invoke.py" -v
```

Sono predisposti **8 test nuovi**, non ancora attestati dall'utente.
Se falliscono, non passare alla fase Colab.

## Fase B: Colab (unica cella, sessione esistente)

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
assert DEPS.is_dir(), "Ripristinare il pacchetto isolato RQ2"
dirty = subprocess.check_output(
    ["git", "status", "--porcelain"], cwd=REPO, text=True
).strip()
assert not dirty, "Checkout Colab non pulito: controllare prima"

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
    [sys.executable, "-m", "unittest", "discover",
     "-s", "src/tests", "-p", "test_rq2_langchain_fake_http_invoke.py", "-v"],
    cwd=REPO, env=env, text=True, capture_output=True,
)
print("=== UNIT TEST FINTI (offline) ===")
print(tests.stderr[-6000:])
if tests.returncode:
    print(tests.stdout[-3000:])
    raise RuntimeError("Unit test falliti — NON eseguire la prova SDK")

probe = subprocess.run(
    [sys.executable, "-m", "evaluation.rq2_langchain_fake_http_invoke",
     "--repo-dir", str(REPO)],
    cwd=REPO, env=env, text=True, capture_output=True,
)
if probe.returncode:
    print("STDERR:", probe.stderr[-6000:])
    print("STDOUT:", probe.stdout[-1500:])
    raise RuntimeError("Prova HTTP fake non riuscita; NESSUNA API reale invocata")

result = json.loads(probe.stdout)
print("=== RQ2 LANGCHAIN SDK MOCK HTTP ===")
print(json.dumps(result, indent=2, ensure_ascii=False))

assert result["status"] == "SYNC_FAKE_HTTP_503_INVOKE_VERIFIED_AS_TESTED_NOT_RELEASED"
for name in ("google", "anthropic"):
    provider = result[name]
    assert provider["fake_total_http_503_sends"] == 2, name
    assert len(provider["sync_invoke_modes"]) == 2, name
    assert [r["fake_http_503_sends"] for r in provider["sync_invoke_modes"]] == [1, 1]
    assert provider["external_provider_requests"] == 0
assert result["api_requests_to_real_providers"] == 0
assert result["credentials_real"] is False
assert result["model_outputs_generated"] == 0
assert result["real_tools_executed"] == 0
assert result["scientific_release_signed"] is False
assert result["can_execute_D"] is False
assert result["can_execute_CK"] is False
assert result["can_execute_test"] is False

print("RQ2 SYNC FAKE-HTTP INVOCAZIONI: CONTROLLI SUPERATI")
print("DISCOVERY E TEST OOD ANCORA BLOCCATI")
```

Riportare **sia l'output dei test che il JSON**. Se fallisce un
percorso, non cambiare versioni né provare API reali: il risultato è
una failure di compatibilità del probe da correggere prima del freeze.

**Dopo esito positivo:** aggiornare la proposta di timeout/retry
RQ2-only e concludere i gate scientifici rimasti aperti (alias
scoring, KPI, GT-isolated audit, arm dimostrativo). Non moltiplicare
altri audit tecnici generici. RQ1 resta congelata.
