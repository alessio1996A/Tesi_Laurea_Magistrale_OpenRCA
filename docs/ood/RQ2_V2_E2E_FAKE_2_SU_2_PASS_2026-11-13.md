# RQ2-V2 — Integrazione end-to-end simulata: 2/2 PASS

**Data:** 13 novembre 2026.
**Fonte:** output del terminale locale PyCharm condiviso dall'utente.
**Branch:** `experiment/rq2-provenance-v2-offline-2026-11-13`.
**Git HEAD prima della registrazione:** `28097578774be54145c902189cb0a1d74b8eaab9`.

## Esito osservato

Dopo la correzione del solo fixture dell'istruzione
sintetica nel file
`src/tests/test_rq2_v2_runner_fake_e2e.py`,
l'utente ha eseguito:

```powershell
python -m unittest discover -s src/tests -p "test_rq2_v2_runner_fake_e2e.py" -v
```

Output:

```text
Ran 2 tests in 0.291s

OK
```

**Entrambi i test superati**, senza errori riportati.
Il primo comprende due subtest per `A1` e `A1_8R`;
il secondo confronta gli output V1/V2 e
l'identità della traiettoria proiettata senza gli ID.

Il test usa il vero `run_experiment`, il grafo
LangGraph e il validatore RQ2, sostituendo soltanto
il preparatore del caso, il modello e il tool con
oggetti finti, e l'esecutore V1 con V2 temporaneamente
nel solo contesto del test.

**Limitazioni:** non dimostra ancora validità
diagnostica, affidabilità di un provider remoto,
conservazione di claim/artefatti V2 create-only
o l'intero ciclo D→C→K end-to-end: la preparazione
del pacchetto C è offline e K non viene eseguito.
Nessun dispatcher V2 reale è integrato.
Non sono autorizzate nuove API o il test OOD.

## Sequenza dei test confermati

- Provenance V2: 7/7.
- Regressioni mirate: 41/41.
- Suite globale precedente: 812/812,
  **prima dell'aggiunta dei due nuovi test**.
- Test end-to-end sintetici nuovi: 2/2.

La nuova suite completa deve essere rieseguita
dopo questi ultimi cambiamenti di fixture/test.
La previsione, a parità di test discovery, è
**814 test**, ma il conteggio effettivo verrà
determinato soltanto dall'output locale.

## Prossimo gate: suite globale

Solo su working tree pulita e branch giusto:

```powershell
git branch --show-current
git status --short
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_*.py" -v
```

Se fallisce, conservare traceback e fermarsi.
Se passa, aggiornare il gate e procedere alla
progettazione di un adapter V2 autonomo,
preregistrazione, audit dei file, budget e
test successivi con fake provider, prima di
discutere qualunque pilot a pagamento.

Il protocollo V1, i suoi 39 record RQ2 discovery
e i casi OOD test rimangono immutati/bloccati.
