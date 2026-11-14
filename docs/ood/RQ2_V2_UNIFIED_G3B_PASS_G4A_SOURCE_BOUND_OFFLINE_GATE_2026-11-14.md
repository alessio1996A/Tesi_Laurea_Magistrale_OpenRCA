# RQ2-V2 unificata — G3B PASS, G4A source-bound preflight (non autorizzante)

**Data:** 14 novembre 2026. **Branch:** `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.
**Decisione scientifica:** Opzione A prioritaria, 5 harness × 3 LLM × 4 incidenti discovery × D/C/K = 180 stage logici proposti; 11 OOD test LOCKED. Opzione B successiva, non ancora avviata.

## 1. Evidenza PyCharm fornita dall'utente

```text
Ran 9 tests in 23.395s

OK
```

Questo è il risultato di `src/tests/test_rq2_v2_unified_runner_to_journal_fake_e2e.py` **G3B**. Nove metodi PASS, uno esegue 15 combinazioni dei cinque harness e dei tre modelli con `run_experiment` invariato, reale LangGraph/ToolNode, ma `FakeDiagnosisLLM`, fake tool senza dati OpenRCA e `prepara_esperimento` sostituito in RAM. Lo stesso test crea 45 record D/C/K synthetic-only con claim prima della simulazione, C/K adapter reali, conteggio e SHA delle dipendenze. Coperti errori sintattici D/C/K, astensioni, provider error artificiale, claim orfano e no-auto-retry. **Non** è un esperimento pagato né prova che C/K remoti funzionino per tutti i provider.

Gates precedenti verificati:
- G1 25/25 PASS — piano e provenienza offline.
- G2 9/9 PASS — grafi reali e C/K fake su 15 abbinamenti.
- G3A 23/23 PASS — journal synthetic-only ottimizzato; 15 stage profiler da 31.956 s a 3.546 s su Windows; 213431 → 17219 chiamate stat.
- G3B 9/9 PASS — vera esecuzione runner+grafo finto LLM e registrazione D-C-K unica.

## 2. Nuova fase G4A — codice aggiunto, test non ancora eseguiti

File nuovi:
- `src/evaluation/rq2_v2_unified_release_preflight.py`
- `src/tests/test_rq2_v2_unified_release_preflight_offline.py` (**18 metodi**).

**Non e' una release scientifica**: il controllo legge soltanto i due CSV originali di split/manifest tramite `preview_gt_free_sources` e sorgenti locali del repository, incrociando `preview_protocol_identity` che verifica le impronte Git congelate RQ1. Non legge Market.zip, fault labels, record.csv, scorer, predizioni, claim, Drive outputs; non chiama SDK/provider e non scrive nulla.

Condizioni richieste prima di emettere un report `OFFLINE_SOURCE_BOUND_NO_RELEASE_NO_API`:
1. Piano identico: 4 discovery, 11 OOD locked, 5 harness, 3 provider, 180 stage, 6 round D, planning 4+2, `v2_enforce`.
2. Split/manifest GT-free davvero verificati da digest attesi, e stessa SHA della preview del piano.
3. Identita' frozen RQ1 verificata con Git blob SHA (esistente `rq2_protocol_identity_preflight`), stessi model IDs, prompt C/K e algoritmo base.
4. SHA256 dei 15 sorgenti che supportano il runner e gli adapter, **da pin-nare solo in una successiva release**.
5. Il report resta sempre bloccato (`can_execute_api=False`, `can_run_ood_test=False`, `scientific_release_frozen=False`, `unified_production_ledger_implemented=False`). Non confondere osservabilita' dei dati sorgente con autorizzazione a pagare.

Lo store `rq2_v2_unified_synthetic_journal.py` non è inserito nella lista dei sorgenti della futura release scientifica: **non riutilizzare i record synthetic-only come risultati reali**. L'assenza attuale del ledger scientifico/live resta un gate aperto.

I 18 test usano source-check simulato e mock RQ1 identity per coprire allarmi su manifest, plan SHA, GT, test OOD, drift prompt C/K e modelli, data root mancante, sorgente mancante, normalizzazione CRLF Windows, mancata concessione di API. **Non equivalgono al preflight reale sui CSV del dataset**. Il check source-bound reale dovra' essere eseguito solo quando saremo pronti, con percorso GT-free isolato, dopo aver congelato gli adapter/ledger live.

## 3. Prossima verifica PyCharm

Prima verificare `git status --short` vuoto, quindi:

```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_release_preflight_offline.py" -v
```

**Attesi 18 test, NON dichiararli PASS prima di ricevere l'output utente.**

## 4. Gate ancora aperti

G4B/G4C: sviluppare un solo orchestratore e ledger per risultati REALI — separato sia da V1 sia dal pilot Sonnet e dallo store sintetico; release immutable source-bound con hash codice/manifest/plan e commit pulito; idempotenza e gestione crash/concorrenza; fattori provider C/K unificati, metering e costi verificabili, timeout e no-retry, blocchi economici e batch autorizzati. Verifica positiva su fake E2E *di questo stesso dispatcher*, non solo test-scripts. Prima del primo pilot pagato: audit del codice e della sorgente GT-free, preflight Colab, piano release preregistrato e autorizzazione utente.

La campagna reale su 60 combinazioni D→C→K non è ancora stata eseguita. Nessuna inferenza su generalizzazione/accuratezza OOD è consentita; Opzione B deve rimanere separata.
