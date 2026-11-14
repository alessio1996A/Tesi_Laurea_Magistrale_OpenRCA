# RQ2-V2 unificata — G2 superato e G3A journal sintetico in attesa dei test

Data: 14 novembre 2026. Sviluppo sul branch `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.

## Evidenza utente — G2 reale LangGraph con fake provider
L'utente ha eseguito `src/tests/test_rq2_v2_unified_graph_fake_e2e.py` e riportato:
```text
Ran 9 tests in 0.455s

OK
```
Questi 9 metodi includono un test che percorre **15 combinazioni** (5 harness × 3 model labels) tramite `run_experiment`, ToolNode e graph executor reali (ReAct V2 o verify_graph) ma con tool/LLM e preparazione incidente sintetici. La stessa suite genera/valida C/K con risposte di fixture, non esegue vere richieste ai provider. Il gate precedente G1 era `Ran 25 tests in 0.277s; OK`. Le due suite complessivamente contengono 34 metodi superati, non 34 incidenti reali.

## G3A — Implementato su GitHub, ancora NON testato da PyCharm
Nuovi sorgenti (create-only, non modifica gli store V1, i pilot Sonnet V2 o RQ1):
- `src/evaluation/rq2_v2_unified_synthetic_journal.py`
- `src/tests/test_rq2_v2_unified_synthetic_journal.py` (**19 metodi di test**, non ancora eseguiti).

**Architettura G3A:** ledger unico per tutte le 180 identità stage candidate, con `stage_id` esatto legato a `build_offline_discovery_plan`; rifiuto degli 11 OOD; i 3 model ID devono corrispondere esattamente alla factory; registrazione di `D`, `C`, `K` con dipendenze e SHA del parent; claim O_EXCL prima del record, no retry, registrazione di `BLOCKED_DEPENDENCY` senza provider claim, `RECORDED_COMPLETE` solo con contenuto strutturalmente valido, `INVALID_OUTPUT` e `PROVIDER_ERROR` preservati; ispezione degli archivi al riavvio e rilevazione dei claim orfani. Per D un record `RECORDED_COMPLETE` richiede provenance nativa tool ID, JSON canonico OpenRCA di base e indicazione di successo del validatore task-aware; per C/K validatori JSON strutturali con E### e astensione non forzata. I record sono una **simulazione** e non attestano verità delle cause.

**CRITICO:** codice SOLO PER FIXTURE, marcate espressamente `.rq2_v2_synthetic_only` e poste esclusivamente sotto `data/rq2_v2_unified_synthetic_v0` di una `TemporaryDirectory`. `synthetic_guard` blocca radici reali con `Market.zip`, `data/processed`, `data/rq2` o `data/results`. Nessuna funzione D/C/K contatta il provider; il modulo non ha dispatcher API, non crea release scientifica e NON deve essere invocato con `/content/drive/MyDrive/Tesi_OpenRCA`.

## Cosa dobbiamo ancora completare per G3 / G4

- G3B: orchestration D/C/K vera e **comune**, non ad hoc Sonnet, che usi lo stesso runner RQ1, release source-bound firmata, policy provider, budget per modello, contabilità token anche sulle eccezioni, alert/stop su claim irrisolti, record completi su interruzioni; nessuna chiamata live fino a tutti i gate.
- Test offline E2E **runner → nuovo ledger unificato**, 15 arm × D/C/K, con i contratti reali e mock provider, non soltanto unit test di journal. Controlli di riavvio/crash, randomizzazione ordine, chiamate same-name, planner, contenuti block per Claude.
- Test e audit integrale del codice in PyCharm e poi preflight Colab GT-free. Congelamento del protocollo e delle misure prima delle API. Pilot limitato soltanto dopo espressa autorizzazione economica.

## Comandi PyCharm per G3A (test non ancora osservati)

```powershell
git status --short
git fetch origin feature/rq2-v2-unified-five-harness-three-models-2026-11-14
git switch feature/rq2-v2-unified-five-harness-three-models-2026-11-14
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_synthetic_journal.py" -v
```

**Attesi 19 test, non dichiarare PASS senza output.** In caso di fallimento correggere fixture/code su un nuovo commit; non riprovare alcuno stage reale. Dopo G3A PASS, procedere a G3B e a un test integrato del ledger, prima di qualunque API.
