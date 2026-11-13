# RQ2-V2 — Suite globale aggiornata: 814/814 PASS

**Data:** 13 novembre 2026.
**Fonte:** output finale PowerShell/PyCharm comunicato dall'utente.
**Branch:** `experiment/rq2-provenance-v2-offline-2026-11-13`.

```text
Ran 814 tests in 64.991s

OK
```

Il riepilogo conferma **814 test superati su 814**,
inclusi i due nuovi test di integrazione fake fra
`experiment_runner`, esecutore V2, provenance degli
ID e preparazione del C. La precedente suite era
812/812 prima dell'aggiunta dei nuovi due test;
**non sommare** conteggi della suite piena e delle
suite mirate.

## Significato circoscritto

- I test automatici nel branch sperimentale non
  segnalano regressioni per gli scenari coperti.
- La V2 conserva `tool_call_id` per chiamate e
  risposte e preserva il comportamento V1 negli
  esempi sintetici già testati.
- Nessun esperimento reale, token provider,
  diagnosi GT o sblocco OOD è provato da ciò.
- Il trasporto D/C/K reale V2, il namespace
  degli artefatti e il protocollo di esecuzione
  **non sono ancora implementati o autorizzati**.

## Audit architetturale preliminare

I moduli V1 `rq2_stage_artifact_store.py`,
`rq2_discovery_claim_journal.py` e
`rq2_discovery_stage_recorder.py`
sono vincolati alla specifica coorte del piano V1
e alle directory `data/rq2/stage_artifacts_v0` e
`data/rq2/stage_claims_v0`.

**Non riutilizzare il loro namespace reale per una
campagna V2**: si mescolerebbero protocolli, claim,
denominatori e dati storici. Si possono usare le
classi con fixture temporanei e mock di sorgente
**soltanto per test offline**; una V2 scientifica
richiede manifest, claim journal, source pin e
artifact store dedicati e versionati.

## Passo successivo

Progettare e testare il binding D→C→K con
`tool_call_id` usando esclusivamente dati sintetici
e directory temporanee; distinguere questo test
dall'integrazione ancora mancante dello store
dedicato V2.

Nessun aggiornamento a V1, nessuna nuova API e
OOD test `LOCKED`.
