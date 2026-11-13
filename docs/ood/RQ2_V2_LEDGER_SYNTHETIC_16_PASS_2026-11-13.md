# RQ2-V2 — Store e journal sintetici indipendenti: 16/16 PASS

**Data:** 13 novembre 2026.
**Branch:** `experiment/rq2-provenance-v2-offline-2026-11-13`.
**HEAD prima della registrazione:** `e3484d5e794a80f4e680ec1bb78a0339ba61adb3`.
**Fonte:** riepilogo di esecuzione locale PyCharm comunicato dall'utente.

## Esecuzione osservata

Comando:

```powershell
python -m unittest discover -s src/tests -p "test_rq2_v2_synthetic_ledger.py" -v
```

Output finale ricevuto:

```text
Ran 16 tests in 7.207s

OK
```

**16 test su 16 superati.** Si tratta di test di
software con dati sintetici e `TemporaryDirectory`,
non di diagnosi corrette sul benchmark e non di una
convalida di esecuzione con provider remoto.

Il file test copre: catena D/C/K, namespace indipendenti,
controllo parent hash e restart, claim create-only,
duplicati, errori e bloccati, status coerenti con
provenance e JSON contracts, file corrotti, assenza
di marker, GT keys vietate, symlink e blocco OOD test.

Il progetto V1 resta congelato. I nuovi moduli
`rq2_v2_artifact_store.py` e
`rq2_v2_claim_journal.py` sono **solo sintetici**:
nessuna release V2 scientifica è autorizzata,
nessun dato OpenRCA reale o file V1 viene scritto,
nessuna API provider viene invocata.

## Gate successivo: regressione globale

La precedente suite completa aveva riportato:

```text
Ran 817 tests in 69.351s

OK
```

Questa suite precede i sedici nuovi casi di
`test_rq2_v2_synthetic_ledger.py`.
Il nuovo totale atteso è **833**, ma va verificato
sull'output locale senza affermare PASS in anticipo.

Su branch sperimentale e working tree pulito:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_*.py" -v
```

Se PASS: valutare una decisione GO/NO-GO su
un'eventuale release V2 vera, fissando identità,
versioni, archivi create-only reali, coorte,
metodologia, budget e criteri pre-registrati.
Non riutilizzare claim V1, non riparare artefatti
V1 e non eseguire la coorte OOD test `LOCKED`.

**Il gate attuale non autorizza alcun esperimento
reale o chiamata a pagamento.**
