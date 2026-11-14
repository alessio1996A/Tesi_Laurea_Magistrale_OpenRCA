# RQ2-V2 unificata — G4G prima prova PyCharm: errore fixture, correzione mirata

Data: 14 novembre 2026. Branch: `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.

## Output reale dell'utente

Esecuzione PyCharm:
```powershell
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_dispatcher_offline_e2e.py" -v
```

Risultato esatto:
```text
Ran 17 tests in 3.162s

FAILED (failures=1, errors=25)
```

Il primo errore è ripetuto su tutti gli arm:
```text
AttributeError: 'OfflineLangGraphFakeGateway' object has no attribute
'assertEqual_case'. Did you mean: 'assert_equal_case'?
```

Localizzato nel solo file
`src/tests/test_rq2_v2_unified_dispatcher_offline_e2e.py`,
metodo `OfflineLangGraphFakeGateway.run_d`, riga 101.

Il metodo statico definito esattamente sotto si chiama
`assert_equal_case`, ma era stato chiamato erroneamente
`self.assertEqual_case` (mancano gli underscore). Gli errori
successivi `Unresolved claim: manual review, no new stage` non
rappresentano una seconda causa indipendente: il test centrale
condivide lo stesso ledger tra 15 subtest. Il primo claim D viene
correttamente creato prima del fake runner; l'AttributeError interrompe
la pipeline prima del record D; i tentativi successivi vengono
giustamente bloccati dalla policy fail-closed del ledger. Per questo
il test centrale conclude anche con `AssertionError: 1 != 45`.

## Fix effettuato su GitHub

Una sola sostituzione nell'**unico file di test**, nessun cambiamento
al ledger G4F, dispatcher G4G o protocollo sperimentale:

```python
# prima
self.assertEqual_case(result, case_id, model, harness)
# dopo
self.assert_equal_case(result, case_id, model, harness)
```

Commit:
`9c494ed8f6d1aad93bdf057e7f4eb88c8eef3d07`.

Non disattivare il controllo orphan/no-retry, non ritentare su alcun
archivio reale. La suite G4G usa un TemporaryDirectory; una nuova
invocazione unittest crea un ambiente di prova pulito.

## Prossimo gate locale, non ancora attestato

Assicurarsi `git status --short` vuoto; dal branch:
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_dispatcher_offline_e2e.py" -v
```

Attesi 17 metodi, ma NON dichiarare PASS prima di ricevere un output.
Se dopo il typo compare un problema diverso (p.es. contratto D,
metering, evidence bundle), registrare la nuova traccia e correggere
solo dopo ispezione. Nessuna API, GT/Market, Colab live o OOD è stata
eseguita.

## Stato

G4F 22/22 PASS; G4G **PENDING rerun**, prima esecuzione fallita.
La futura release resta non congelata; il dispatcher live e il
pilot pagato non sono autorizzati. Gli 11 test OOD restano locked.
