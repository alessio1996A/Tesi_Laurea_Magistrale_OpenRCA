# RQ2-V2 — Runner → nuovo journal/store V2: primo PASS e correzione raccolta test

**Data:** 13 novembre 2026. **Branch:** `experiment/rq2-provenance-v2-offline-2026-11-13`.

## Log locale riportato dall'utente

```text
Ran 19 tests in 7.788s

OK
```

La suite invocata era:
```powershell
python -m unittest discover -s src/tests -p "test_rq2_v2_runner_to_ledger_fake_e2e.py" -v
```

È stata superata senza errori. L'ispezione dei sorgenti ha
spiegato il conteggio:
- 3 nuovi test nel modulo `test_rq2_v2_runner_to_ledger_fake_e2e.py`;
- 16 test della classe importata direttamente
  `RQ2OutputContractsTests` da `test_rq2_output_contracts.py`.

`unittest` scopre anche le classi `unittest.TestCase`
importate direttamente nello spazio nomi del modulo.
Il PASS 19/19 è reale ma include questa duplicazione; non
va presentato come 19 nuovi casi indipendenti.

## Correzione minima

Commit `73eb3fb84652e11c708b00010d1ddcb5abc83fc0`:
solo `src/tests/test_rq2_v2_runner_to_ledger_fake_e2e.py`.

Prima:
```python
from test_rq2_output_contracts import RQ2OutputContractsTests
```

Dopo:
```python
import test_rq2_output_contracts as contract_fixtures
```

Le tre chiamate ai dati sintetici ora usano
`contract_fixtures.RQ2OutputContractsTests.cause()`
o `.rule()`. Nessuna modifica alle risposte
fittizie, al runner scientifico, al grafo, alla provenance,
agli store o al journal. Nessun retry di provider.

## Copertura dei 3 nuovi test

1. Il vero `run_experiment` con LLM/tool fake e
   esecutore provenance V2 temporaneamente patchato
   soltanto nel test, per A1 e A1_8R.
   Si prepara C/K offline, si verificano due tool call
   omonime, sei record/claim nel nuovo ledger
   V2 sintetico, hash dipendenza, restart e no retry.
2. ID di un tool result alterato nel fixture ⇒ D
   `INVALID_OUTPUT` e C/K `BLOCKED_DEPENDENCY`,
   senza claim ai figli.
3. C con evidence ref inesistente `E999` ⇒
   rifiuto di `RECORDED_COMPLETE`, persistenza
   `INVALID_OUTPUT` e K bloccato.

Tutti i dati sono sintetici in `TemporaryDirectory`.
Il solo ID nominale del case è un identificativo discovery
ammesso dalla policy: nessun contenuto OpenRCA reale,
Market, GT, Drive o API provider viene letto.

## Test ancora necessari dopo correzione import

Il PASS 19/19 si riferisce al file **prima** del fix.
Eseguire dopo pull:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_runner_to_ledger_fake_e2e.py" -v
```

**Attesi 3 test, non ancora verificati dopo il fix.**
Se PASS, intera suite:

```powershell
python -m unittest discover -s src/tests -p "test_*.py" -v
```

Base globale già verificata: **841/841**.
Nuovo totale previsto dopo la correzione:
**844 test** (841 + 3), verificare dal log.

## Decisione

GO solo verifica tecnica offline.
NO-GO release scientifica V2, API a pagamento e 11 OOD test.
Non riutilizzare né correggere retroattivamente
i 39 record discovery V1. Prima di un pilot reale
occorrono freeze, source pin, coorte, protocollo
separato, budget e autorizzazione.
