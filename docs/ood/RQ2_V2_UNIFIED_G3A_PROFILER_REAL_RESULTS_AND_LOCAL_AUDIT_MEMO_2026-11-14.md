# RQ2-V2 unificata — profiler reale Windows e ottimizzazione audit (14/11/2026)

## Dato reale osservato (PyCharm / Windows)

Comando utente: `python -B src/tests/profile_rq2_v2_unified_journal_offline.py`

Output:
```text
STATUS: OFFLINE_PROFILE_INTEGRITY_OK
ALL_STAGES_SEC: 29.887
FINAL_AUDIT_SEC: 2.067
PROFILE_TOTAL_SEC: 31.956
CLAIMS_AND_RECORDS: 15 / 15
UNRESOLVED_CLAIMS: 0
6381829 function calls (6327440 primitive calls) in 31.955 seconds
31 audit_restart calls => cumulative 30.085s
load_record 2560/685 calls => cumulative 27.450s
Path.stat 213431 calls => cumulative 24.280s
_paths 5676 calls => cumulative 23.710s
load_claim 3025 calls => cumulative 15.836s
Windows nt.stat 213431 calls => own time 20.057s
MODEL_API_CALLS: 0; MARKET_READ: FALSE; GT_READ: FALSE
```

Nota: tempi *cumulativi* fra loro sovrapposti, non sommabili.
Per stage, la durata cresce da 0.102s (A0 D) a 3.822s (PAVE K).
Questi numeri costituiscono **baseline concreta per il solo sottoinsieme di 15
stage sintetici**, non un benchmark provider e non una dimostrazione causale di
quanto ogni singola funzione rallenti sulla piattaforma reale.

**Diagnosi:** `audit_restart` viene eseguito prima di ogni claim e record,
rilegge ogni file, e `load_record/load_claim` validano ripetutamente gli stessi
parent e claim attraverso chiamate ricorsive. Sulla macchina Windows questa
ridondanza genera moltissimi accessi `stat`, piu' costosi della logica JSON/SHA.

## Modifica tecnica circoscritta

Unico modulo modificato:
`src/evaluation/rq2_v2_unified_synthetic_journal.py`.

- `audit_restart` verifica una volta la guardia path e avvia un dizionario
  locale `_memo = {"claims": {}, "records": {}}`.
- `load_claim/load_record` possono ricevere `_memo` soltanto dalle chiamate
  interne dell'audit. Un elemento viene memoizzato **SOLO dopo** aver superato
  controlli di identita', SHA, claim, parent, GT e payload.
- I parent e i claim vengono riutilizzati dentro la **medesima scansione**,
  invece di ripetere migliaia di accessi allo stesso file.
- Ogni nuova `audit_restart`, ogni scrittura `claim_stage`/`record_stage`
  e ogni `load_record/load_claim` pubblico senza argomento opzionale usano
  una nuova verifica; **nessuna cache attraversa gli audit**.
- Restano immutati `O_EXCL`, create-only, controllo D task-aware,
  provenance `tool_call_id`, controllo `origine` Planning/PAVE,
  contratto C/K, no-auto-retry, 4 discovery / 11 OOD locked, e namespace
  synthetic-only.

**Limite consapevole:** anche il sistema originale non offre una
transazione filesystem globale né protezione assoluta contro modifiche
esterne concorrenti in un audit. Questo miglioramento e' SOLO nel codice
offline/sintetico; prima di una release live si dovranno valutare
serializzazione/lock e race multi-processo, anziche' presumere correttezza
dalle sole fixture.

## Test aggiunti

Nel file `src/tests/test_rq2_v2_unified_synthetic_journal.py`:
1. `test_audit_reads_each_stored_file_bounded_times`: tre stage
   D/C/K producono sei file; l'audit deve rileggere ciascun file un numero
   limitato di volte (max 18 letture totali); niente asserzioni basate
   su secondi e quindi non flaky.
2. `test_new_audit_detects_disk_corruption_after_previous_pass`:
   dopo un audit PASS, manomissione del record D deve fallire.
3. `test_new_audit_detects_claim_corruption_after_previous_pass`:
   dopo un audit PASS, alterazione dell'autorizzazione di un claim deve fallire.

Suite aggiornata da 20 a **23 test**, ancora NON eseguita dall'utente.
I precedenti 20/20 PASS appartengono al codice anteriore alla patch.
Anche il profiler precedente e' baseline, non una misura post-patch.

## Prossima verifica riproducibile

```powershell
git status --short
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_synthetic_journal.py" -v
python -B src/tests/profile_rq2_v2_unified_journal_offline.py
```

**Gate decisionale**: confermare 23/23 test e confrontare esattamente il profilo
15 stage Windows prima/dopo: 31.956s baseline, 213431 stat, 31 audit.
L'ottimizzazione si considera accettata soltanto se tutti i controlli di
integrita' continuano a passare. In caso di nuova failure, NO API e analisi
del contratto senza bypass dei gate.

**G3B ancora assente:** runner reale con fake model/tool collegato al journal
unificato create-only. **G4/G5 BLOCCATI:** zero live API in questa modifica,
nessun test OOD, nessuna pretesa di generalizzazione o scoring.
