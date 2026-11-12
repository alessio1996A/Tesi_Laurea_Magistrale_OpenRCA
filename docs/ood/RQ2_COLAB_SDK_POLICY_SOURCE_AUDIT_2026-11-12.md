# RQ2 — Cella Colab di audit delle versioni SDK e sorgenti (12 novembre 2026)

**Uso:** una sola cella Colab, su repository e pacchetti **già preparati** dalla
cella prefreeze GT-free del 12/11. Non modifica RQ1 frozen, non legge Market
o GT, non istanzia SDK, non invia chiamate API e non sblocca discovery/test.

Se hai riconnesso Colab e i percorsi seguenti non esistono, ripeti prima
il bootstrap precedente documentato in
`RQ2_COLAB_PREFREEZE_REALE_SOLO_LETTURA_2026-11-12.md`; questa cella
**non** esegue installazioni nuove per evitare drift di versioni.

## Cella da incollare in Colab

```python
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path("/content/Tesi_OpenRCA_RQ2")
DEPS = Path("/content/rq2_prefreeze_packages_py313")
BRANCH = "feature/ood-knowledge-transfer-audit-2026-11-10"

assert (REPO / ".git").exists(), "Repository assente: prima ripristinare il bootstrap RQ2"
assert DEPS.is_dir(), "Pacchetti isolati assenti: prima ripristinare il bootstrap RQ2"
status = subprocess.run(
    ["git", "status", "--porcelain"],
    cwd=REPO, capture_output=True, text=True, check=True,
)
assert not status.stdout.strip(), (
    "Checkout Colab non pulito: non aggiornare automaticamente. "
    "Controllare git status prima di proseguire."
)

# Solo aggiornamento codice da GitHub: NON chiama API LLM e NON apre il Market.
subprocess.run(["git", "fetch", "origin", BRANCH], cwd=REPO, check=True)
head = subprocess.check_output(
    ["git", "rev-parse", "FETCH_HEAD"], cwd=REPO, text=True
).strip()
subprocess.run(["git", "checkout", "--detach", head], cwd=REPO, check=True)
print("GIT_RQ2_COMMIT:", head)

# Eseguiamo su Python Colab, usando SOLO le dipendenze isolate gia' installate.
env = dict(os.environ)
env["PYTHONPATH"] = os.pathsep.join([str(DEPS), str(REPO / "src")])
test_cmd = [
    sys.executable, "-m", "unittest", "discover",
    "-s", "src/tests", "-p", "test_rq2_provider_policy_source_audit.py", "-v"
]
tests = subprocess.run(
    test_cmd, cwd=REPO, env=env, capture_output=True, text=True,
)
print("=== TEST RQ2 PROVIDER POLICY (offline) ===")
print(tests.stderr[-7000:])
if tests.returncode:
    print(tests.stdout[-3000:])
    raise RuntimeError("Test offline provider falliti")

cli = subprocess.run(
    [sys.executable, "-m", "evaluation.rq2_provider_policy_source_audit",
     "--repo-dir", str(REPO)],
    cwd=REPO, env=env, capture_output=True, text=True,
)
if cli.returncode:
    print(cli.stderr[-5000:])
    raise RuntimeError("Audit SDK Colab fallito")

report = json.loads(cli.stdout)
print("=== REPORT SDK DAL RUNTIME COLAB ===")
print(json.dumps(report, indent=2, ensure_ascii=False))

assert report["original_factory_unchanged"] is True
assert report["anthropic_zero_retries_in_factory_source"] is True
assert report["gemini_retry_timeout_unspecified_in_factory_source"] is True
assert report["matches_previous_colab_versions"] is True, (
    "VERSION DRIFT: confrontare i pacchetti osservati con il preflight precedente"
)
assert report["api_calls_executed"] == 0
assert report["read_ground_truth"] is False
assert report["read_market"] is False
assert report["read_predictions"] is False
assert report["scientific_release_signed"] is False
assert report["sdk_transports_dynamically_exercised"] is False
for gate in (
    "effective_google_sdk_retry_timeout_verified",
    "effective_anthropic_sdk_retry_timeout_verified",
    "can_execute_D", "can_execute_CK", "can_execute_test",
):
    assert report[gate] is False, gate

print("RQ2 COLAB SDK SOURCE AUDIT: CONTROLLI SUPERATI")
print("NOTA: RETRY E TIMEOUT REALI ANCORA DA VERIFICARE CON HTTP FALSO")
```

## Interpretazione attesa

Se tutti i controlli sono superati, l'output conterrà le versioni e le
impronte *del runtime scientifico Colab effettivo*; inviarlo completo
all'assistente. `matches_previous_colab_versions=true` sarà la
prova che l'ambiente è lo stesso snapshot di pacchetti atteso, **non**
la prova che i retry automatici siano disabilitati.

Se `matches_previous_colab_versions=false`, fermarsi. Non installare,
aggiornare o eliminare pacchetti per forzare il verde: occorre documentare
prima lo scostamento. Se `git status` non è pulito, verificare la causa
prima di cambiare checkout.

**Vincolo scientifico invariato:** dopo questo audit il release
`RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json` NON è ancora firmato,
`RELEASE_SHA256=None` resta tale, e le API discovery/test sono chiuse.
