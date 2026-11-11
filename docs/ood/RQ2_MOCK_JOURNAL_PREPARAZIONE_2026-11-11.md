# RQ2 — Journal create-only di **sola simulazione** (non runner API)

**Data:** 11 novembre 2026. **Stato:** progetto non congelato; simulazione di transizioni offline.  
**Nessuna API Gemini/Claude, nessuna esecuzione D/C/K reale, nessuna modifica RQ1.**

## Contesto verificato

Colab dell'utente, commit `5a254dc6f5cbf6a03f89aa2ce12df251553e388a`, ha confermato il preflight `rq2_dryrun_workflow_preview_v0` sul Market reale: hash split/manifest conformi, 4 discovery + 11 test, 90 D + 90 C + 24 K = **204 stage logici**, `preview_sha256=ecd6d926933a5ad056ad1a581fa7e490c0a13eee18070c7dac8627c1b19c062e`. `DRAFT_NOT_EXECUTABLE`, `can_execute_api=false`, `api_budget_approved=false`, `model_api_calls=0`, nessun piano scritto.

## Nuovo modulo e garanzie testabili

`src/evaluation/rq2_mock_journal.py` è una classe di **sola simulazione**, deliberatamente sprovvista di invocatori modello/tool, credenziali, calcolo di score e accesso a Market. È un laboratorio di ingegneria della persistenza e dello stato, **non un runner sperimentale**. Accetta solo un piano `DRAFT_NOT_EXECUTABLE` con flags API bloccate, 204 stage, dipendenze D→C→K e SHA di anteprima coerente.

- Ogni chiamata `mark_mock_complete(stage_id)` produce una ricevuta **sintetica** `MOCK_COMPLETE` con `journal_version`, `plan_sha256`, `stage_id`, `phase`, `stage`, dipendenze e SHA del record. **Non** genera, legge o riproduce diagnosi, telemetria o regole.
- Una ricevuta è scritta con `O_CREAT|O_EXCL` (create-only), nome derivato da SHA256 dello `stage_id`. Una seconda scrittura sullo stesso ID è rifiutata. I record parziali, non canonici o manomessi fanno fallire il riavvio in modalità chiusa; non c'è cancellazione/riparazione automatica.
- I 24 stage K di **discovery** devono essere stati simulati e completati prima di creare `MOCK_DISCOVERY_FREEZE.json` create-only, contenente i relativi digest. Questo è un **blocco simulato**, NON un congelamento scientifico di pseudoregole valide. Se un record K cambia dopo il receipt di freeze, il journal fallisce il controllo.
- Nessuno stage in **test** può essere simulato prima del freeze **mock**. In un futuro runner reale servirà un freeze scientifico con criteri e file hash diversi, più guardie indipendenti: **non riutilizzare la ricevuta mock come autorizzazione per le API**.
- Il metodo `resume_audit()` legge **solo la cartella journal fornita** e verifica schemi, ordinamento dei predecessori, file inattesi, SHA e blocco dei test; non legge GT. Le ricevute indicano esplicitamente `MOCK_ONLY_NEVER_API`, `model_api_calls=0`.
- La creazione di file avviene **soltanto nei test in directory temporanee locali**: non in Drive, repository di risultati o dataset Market, e non costituisce una campagna.
- I controlli sugli hash rilevano alterazioni accidentali e non sono firme crittografiche/autenticazioni contro attaccanti capaci di modificare anche i digest.

## Verifiche predisposte, non ancora eseguite dall'utente

`src/tests/test_rq2_mock_journal.py`: **18 test sintetici** con `tempfile.TemporaryDirectory()`; controllano ordinamento D/C/K, K solo discovery, blocco del test, freeze simulato dopo 24 K, create-only, doppio freeze, ripresa dopo restart, file sconosciuti, ricevute e freeze corrotti, modifica dell'hash del piano, tentata abilitazione API e completamento simulato di 204 stage.

Comando PyCharm:

```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_mock_journal.py" -v
```

**Risultato atteso:** `Ran 18 tests` e `OK`. Un errore va analizzato prima di procedere. Non serve Colab per questi test: sono deliberatamente isolati da Drive e API.

## Restano aperti prima del runner reale

Gli schemi esatti dei risultati D/C/K reali, estrazione delle metriche e delle unità osservate dai tool, integrità del vero piano create-only e delle dipendenze con errori/astensioni, coerenza del freeze scientifico, policy di valutazione senza leakage GT, versioni provider, costo API e consenso esplicito. L'esperimento scientifico deve ancora validare l'implementabilità dei detector e distinguere esempi di test indipendenti. I moduli mock **non autorizzano nulla**.
