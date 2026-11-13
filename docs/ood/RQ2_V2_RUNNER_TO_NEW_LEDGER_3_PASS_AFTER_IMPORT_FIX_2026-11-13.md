# RQ2-V2 — Runner → nuovo ledger indipendente: 3/3 PASS dopo correzione import

**Data:** 13 novembre 2026.
**Branch:** `experiment/rq2-provenance-v2-offline-2026-11-13`.
**HEAD prima della registrazione:** `b868b60848948311fead780e0be0d5406ebe0bff`.
**Fonte:** output locale di PowerShell/PyCharm riportato dall'utente.

## Esito locale

Dopo l'aggiornamento import-only nel test
`src/tests/test_rq2_v2_runner_to_ledger_fake_e2e.py`,
l'utente ha eseguito:

```powershell
python -m unittest discover -s src/tests -p "test_rq2_v2_runner_to_ledger_fake_e2e.py" -v
```

Output ricevuto:

```text
Ran 3 tests in 4.434s

OK
```

**3/3 PASS** sul file corretto, senza raccolta accidentale
dei 16 test preesistenti `test_rq2_output_contracts.py`.
La prima esecuzione (prima del fix) aveva riportato
19/19 PASS proprio per l'import diretto di una TestCase.

## Copertura sintetica

1. Flusso `run_experiment` con `salva=False`,
   preparazione fittizia, vero LangGraph/ToolNode,
   LLM/tool finti, esecutore V2 patchato solo in memoria,
   bundle provenienza tool, pacchetti C/K offline,
   **nuovo** `RQ2V2SyntheticClaimJournal` e
   `RQ2V2SyntheticArtifactStore` separati,
   su due harness A1 e A1_8R.
2. Tool result con ID alterato ⇒ D `INVALID_OUTPUT`,
   C/K `BLOCKED_DEPENDENCY`, senza claim ai figli.
3. C con `E999` non presente nelle evidenze ⇒
   rifiuto dello status complete, C `INVALID_OUTPUT`,
   K `BLOCKED_DEPENDENCY`.

Il test usa soltanto una `TemporaryDirectory` con
marker sintetico, nessun provider, Drive, Market,
GT, scorer, notebook, dati OOD o consumo API.

## Gate ancora da chiudere

La suite globale precedente, eseguita prima dei nuovi
tre test, ha riportato **841/841 OK**.
Con i tre nuovi metodi (dopo il fix) attendiamo
**844 test**, da verificare sul terminale:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_*.py" -v
```

Non dichiarare la suite completa PASS finché
l'utente non fornisce il riepilogo locale.

## Prossima decisione

Se suite globale OK, chiudere la validazione offline
coperta dai test e procedere a GO/NO-GO scientifico:
preregistrazione reale V2, coorte e confronto, source
pin, release, budget e possibile pilot circoscritto.

Il codice store/journal V2 rimane **solo sintetico**;
nessuna chiamata API autorizzata e nessun record V1
modificato. Gli undici casi OOD test sono LOCKED.
