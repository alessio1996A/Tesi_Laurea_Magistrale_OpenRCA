# RQ2-V2 unificata — G3A 20/20 PASS, performance da diagnosticare

Data: 14 novembre 2026. Sorgente dell'esito: output PyCharm riferito dall'utente.

```text
Ran 20 tests in 250.763s

OK
```

Questo supera il gate di **correttezza del journal sintetico G3A**: incluse 15 combinazioni agente-modello × D/C/K in fixture, error handling, claim create-only, rottura dipendenze, no-auto-retry e due test negativi sui metadati `origine` dei grafi con planner.

**Non** attesta 180 esecuzioni API, non costituisce una nuova campagna RQ2-V2, non dimostra il successo di trasferimento o generalizzazione, non autorizza lavoro sui test OOD. G1 25/25 PASS, G2 9/9 PASS. La suite G3A ha eseguito **20 metodi di unittest**, di cui uno con 15 sottotest, non 20 incidenti reali.

## Problema prestazionale aperto

Durata in PyCharm Windows: **250.763 s**, contro **121.164 s** nel tentativo precedente G3A con 19 test (non completamente passato). Il confronto non e' controllato: nei due tentativi sono cambiati il numero di test e soprattutto la quantita' di record conservati. Non attribuire il raddoppio esclusivamente al test negativo aggiunto.

Dall'ispezione statica di `src/evaluation/rq2_v2_unified_synthetic_journal.py`, `claim_stage()` e `record_stage()` chiamano un `audit_restart()` integrale, che per ogni record/claim invoca `load_record/load_claim` e puo' ripetere controlli ricorsivi, SHA, validatori di provenance, letture da disco. Con l'aumentare degli stage si sospetta costo superlineare; questa e' **un'ipotesi, non una misura profilata**. I singoli controlli di integrita' non devono essere eliminati per velocizzare.

## Profilazione mirata, senza ulteriori cambi al journal

Aggiunto `src/tests/profile_rq2_v2_unified_journal_offline.py`.
Esegue cProfile e stampa:
- tempi separati per i 15 stage (5 harness × D/C/K) di un solo modello-etichetta sintetico;
- tempo di audit finale e tempo totale;
- 22 funzioni piu' costose per tempo cumulativo;
- rilettura riuscita di 15 claim e 15 record, zero orfani, zero OOD, zero API, zero GT o Market.

Usa soltanto `TemporaryDirectory`, `fake_run/cause/rule` dai test sintetici e `UnifiedRQ2SyntheticJournal`; **nessun record su Google Drive**. Esecuzione PyCharm dal root di repository:

```powershell
git status --short
git pull --ff-only
$env:PYTHONPATH = "src"
python -B src/tests/profile_rq2_v2_unified_journal_offline.py
```

**Stato: profiler non ancora eseguito dall'utente**; non inventare alcun risultato di profiling. Se la diagnostica mostra una funzione dominante, proporre ottimizzazione **conservativa**, con equivalenza dimostrata su suite completa, incluso il rifiuto di corruption/race/orphan e una misura di baseline vs nuova implementazione su stessa macchina e quantità di record. Nessuna modifica RQ1, provider, scoring, test OOD o sorgenti congelati.

## Prossimo gate metodologico

- **G3A correctness: PASS**, performance: OPEN.
- **G3B** ancora non eseguito: orchestratore D/C/K di prova che colleghi runner LangGraph con fake LLM/tool allo stesso journal unificato, 15 arm, compresi failure, retry e restart, con rigida provenance.
- G4 release/code/dataset/prompt/versioni SDK congelata, G5 API reale restano BLOCCATI, anche se G3A 20/20 PASS.

Questa diagnostica aiuta a mantenere **un'unica** RQ2-V2, non a creare una variante per modello.
