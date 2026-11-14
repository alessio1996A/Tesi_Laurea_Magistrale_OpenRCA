# RQ2-V2 unificata — G4E contratto release scientifica (offline, nessuna autorità)

Data: 14 novembre 2026. Branch: `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.

## Evidenze confermate prima del nuovo codice

- Colab G4C `CompletedProcess(... returncode=0)`; check `preview_unified_source_bound` e `build_unified_release_blueprint` superati con due CSV GT-free, 180 stage, 492 invoke graph candidati e tutti i gate API/OOD spenti. **Valori SHA JSON non copiati in chat**, da recuperare con `capture_output=True, text=True`.
- PyCharm G4D `Ran 19 tests in 0.485s; OK (skipped=2)`: **17 superati realmente, 2 skip legati a permessi symlink Windows** (da verificare eventualmente su Linux).
- G1, G2, G3A, G3B, G4A, G4B: 102 unittest metodi PASS già osservati nei turni precedenti. Nessuna nuova API RQ2-V2 pagata, nessuna campagna Option A; 11 casi test OOD ancora LOCKED.

## Nuovo G4E — codice e test scritti, NON ancora eseguiti

- `src/evaluation/rq2_v2_unified_scientific_release_contract.py`
- `src/tests/test_rq2_v2_unified_scientific_release_contract_offline.py` (**18 metodi test**).

Il modulo è **puro, read-only, no network, no filesystem I/O, nessuna API**. Definisce un contratto STRICT per una **futura release** con source Git commit esterno, release SHA-256 approvato esternamente, stesso piano 180-stage, SHA di split e manifest, SHA dei sorgenti e prompt C/K, modelli esatti, 5 harness, 4 discovery/11 test locked, 6 round D e 2 checks Planning, runtime version pin, policy provata retry/timeout/usage, single-writer proven, budget USD Decimal positivo e riferimento ad approvazione esplicita.

La funzione `validate_future_release` fa solo controlli sintattici/di coerenza con report G4A e blueprint; **NON verifica direttamente Git, real CSV, runtime, rete o reale consenso**. I due report devono provenire da verifiche effettive, non fake. Anche dopo un ritorno OK la ricevuta impone:
`can_create_scientific_claim=False`,
`can_execute_api=False`,
`can_run_ood_test=False`,
`production_ledger_implemented=False`,
`production_dispatcher_implemented=False`,
`usd_hard_cap_guaranteed=False`.

**ATTENZIONE CRITICA:** negli unittest G4E, l'approval_reference e il budget sono deliberatamente inventati (etichetta `SYNTHETIC_APPROVAL_NOT_REAL`) per testare il contratto. NON rappresentano alcuna approvazione del proprietario reale. Le verifiche provider/retry sono simulate con boolean TRUE nei fixture, ma in Colab sono ancora da certificare per davvero. Nessuna release e nessun claim sono creati.

Il contratto è il **primo blocco progettuale** del ledger scientifico futuro, NON il ledger scientifico live. Il successivo passo richiede:
1. vero ledger create-only separato con claim, record, sha parent, readback e gestione di errori, orfani, race/concurrency;
2. un solo dispatcher D/C/K con provider adapter e audit; fake E2E del dispatcher VERO;
3. vincoli quota/usage, timeout/retries effettivi, costi aggiornati; freeze del codice incluso il ledger stesso;
4. real source bound + release esterna create-only approvata, e solo dopo consenso API esplicito;
5. OOD test non toccati finché le K discovery non sono congelate.

## Prossimo test PyCharm

Controllare `git status --short` vuoto, poi:
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_scientific_release_contract_offline.py" -v
```
Attesi **18 test**, NON ANCORA ATTESTATI. Se falliscono, correggere il contratto/fixture in un commit nuovo senza alterare RQ1 o i 102 test pregressi.

## Come acquisire gli SHA del G4C sulla stessa sessione Colab

```python
import json, subprocess, sys
result = subprocess.run(
    [sys.executable, "-B", "-c", code],
    cwd=REPO, env=env,
    capture_output=True, text=True, check=True
)
report = json.loads(result.stdout)
print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
```

Non rilanciare il clone, non aggiornare i CSV o il commit del preflight per forzare una risposta. È normale che questo codice mostri l'HEAD G4C `33d5d8b28494d5bf41168d0a709854aa3134ea6a` mentre GitHub avanza su un branch di sviluppo: ogni preflight deve conservare il proprio commit.
