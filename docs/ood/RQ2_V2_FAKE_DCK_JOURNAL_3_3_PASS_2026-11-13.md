# RQ2-V2 — Gate D→C→K sintetico: 3/3 PASS

**Data:** 13 novembre 2026.
**Fonte:** stdout locale di PyCharm comunicato dall'utente.
**Branch:** `experiment/rq2-provenance-v2-offline-2026-11-13`.
**HEAD prima della registrazione:** `70a10b7ac1b3774d79548effb77406b98ef5ccc4`.

## Risultato osservato

Il file `src/tests/test_rq2_v2_fake_dck_journal.py`
è stato eseguito localmente:

```powershell
python -m unittest discover -s src/tests -p "test_rq2_v2_fake_dck_journal.py" -v
```

Output finale comunicato:

```text
Ran 3 tests in 5.727s

OK
```

Tutti e tre i test passano. Coprono:
1. Il vero grafo LangGraph con fake LLM/tool, l'esecutore V2 con
   `tool_call_id`, associazione univoca delle evidenze,
   registrazione D/C/K in journal sintetico e audit dopo restart.
2. ID errato di risultato tool → D `INVALID_OUTPUT`,
   C/K `BLOCKED_DEPENDENCY` senza nuovi claim.
3. Rifiuto di claim ripetuti dopo D/C/K completati,
   senza secondo tentativo.

Queste conclusioni si riferiscono agli assert presenti
nella suite e al suo esito globale, non a un benchmark reale.
Il test utilizza uno store V1 **soltanto in directory temporanea**,
con piano e sorgenti fittizi: ciò NON autorizza la V2 a
scrivere negli archivi congelati della V1.

## Stato dei test fino a oggi

La suite completa precedente ha restituito:

```text
Ran 814 tests in 64.991s
OK
```

Essa è stata eseguita **prima** dell'aggiunta dei tre test
D/C/K appena passati. Il nuovo totale previsto è 817,
ma il totale effettivo deve essere verificato da unittest.

## Passo successivo

Nel branch sperimentale, working tree pulita,
eseguire di nuovo l'intera suite:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_*.py" -v
```

Poi, prima di qualunque API, progettare e verificare
un protocollo e un artifact store V2 **separati**
dal V1, con:
- identificativo di campagna e namespace indipendenti;
- claim create-only, no retry e crash/restart audit;
- release e sorgenti SHA pinned;
- decisioni su split/coorte, denominatori, KPI,
  gestione di invalid/blocked/abstention e budget;
- test provider finti prima di un pilot reale;
- divieto di riclassificare retroattivamente claim V1
  e di sbloccare gli 11 casi OOD.

**Nessun provider API chiamato e nessun risultato
scientifico creato da questa registrazione.**
