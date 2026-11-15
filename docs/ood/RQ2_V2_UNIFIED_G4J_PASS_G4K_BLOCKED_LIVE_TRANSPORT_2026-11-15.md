# RQ2-V2 unificata — G4J PASS, G4K live-capable BLOCCATO + source inventory esteso

**Data**: 15 novembre 2026. **Branch**:
`feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.

## Esito PyCharm appena confermato

```text
Ran 25 tests in 1.037s

OK
```

**G4J 25/25 PASS**: adattatore ricevute per D (runner RQ1) e C/K
(tool-free) compatibile col ledger scientifico G4F, anche in presenza
di JSON invalidi, errori del provider e token incompleti. Solo dati
fake nei test. Gate recenti: G4F 22 PASS, G4G 17 PASS, G4H 20 PASS,
G4I 24 PASS, G4J 25 PASS = 108 test attestati. Nessun nuovo
tentativo API della campagna unificata.

## G4K: nuovo dispatcher LIVE-CAPABLE ma HARD-DISABLED

Nuovi file:
- `src/evaluation/rq2_v2_unified_live_dispatcher.py`
- `src/tests/test_rq2_v2_unified_live_dispatcher_mock_offline.py`
  (**18 test scritti, da eseguire**).

`run_one_claimed_unified_stage` collega la stessa pipeline usata
dalla campagna reale:
1. **gate pre-claim**: `LIVE_API_ENABLED=False` DI DEFAULT nel sorgente
   (quindi una chiamata non puo' iniziare); `confirm_paid_api=True`
   da solo NON autorizza la rete; richiede un solo `stage_id` e
   `approved_stage_id` identici, commit clean e hash release esterno,
   `approval_reference` non-placeholder e coorte discovery;
2. G4F verifica **release già presente**, fonte GT-free reale,
   commit Git identico, e piano 180 stage/5 harness/3 provider;
3. G4H ricostruisce istruzione dal CSV verificato e per C/K
   package SHA da D/C precedenti, verifica il blocco OOD;
4. il claim create-only avviene **PRIMA** di costruire il client
   e prima di un eventuale `model.invoke`;
5. D: riusa `crea_modello_rq2` e `run_experiment(...,salva=False)`
   di RQ1, sostituendo solo contestualmente l'esecutore del grafo
   ReAct con `esegui_grafo_rca_v2` per conservare tool_call_id;
   Planning/PAVE usano il proprio verify_graph immutato;
6. C/K: messaggi system+user della `rq2_probe_adapter`, con
   `SystemMessage`/`HumanMessage`, trasporto sincrono tool-free
   `_one_call` di `rq2_ck_provider_transport` gia' testato;
   la sua factory usa `rq2_model_factory` RQ2-only;
7. normalizzazione su G4J e salvataggio G4F; un errore D/C
   correttamente registrato blocca K/C dipendenti;
   malformazioni post-claim restano **orphan/manual audit**, mai
   retry automatico; eccezioni non riportano credenziali;
8. ricevute conservano contatori invocazioni LOGICHE osservate,
   input/output token disponibili, `usage_complete` e
   `cost_estimate_usd_not_invoice="UNKNOWN"`. **Nessun limite USD
   o HTTP hard-cap dimostrato**, né questo codice ne impone uno;
   occorre approvazione separata prima del pilot.

Il test G4K usa soltanto `TemporaryDirectory`, release e manifest
sintetici e **patch di `LIVE_API_ENABLED=True` strettamente
nel processo unittest, con entrambi i trasporti D/C/K mockati**.
Verifica factory solo dopo claim, D→C→K, stato
`RECORDED_COMPLETE`, JSON invalido, errori 503 finti, pre-request,
orphan/no retry, OOD e sorgenti legate. Un PASS di G4K **NON abilita
la produzione**: nel file versionato `LIVE_API_ENABLED=False`.

## Source inventory G4A esteso, ma non ancora congelato

`src/evaluation/rq2_v2_unified_release_preflight.py`
ora elenca **29 percorsi** (15 precedenti +14 nuovi):
G4F/G4H/G4I/G4J/G4K, release schema/blueprint, SDK factory e policy,
CK trasporto RQ2-only, contabilità preliminare, SHA source audit.
I 29 file devono essere ricontrollati in Colab sulla **HEAD finale**,
con un preflight GT-free REALMENTE basato su manifest/split veri.
Il vecchio G4C con `source_file_count=15` è valido per QUEL checkout
storico, ma non è una prova sufficiente per questa release.

Aggiornato anche
`src/tests/test_rq2_v2_unified_release_preflight_offline.py`
con un test di regressione obbligatoria sull'inclusione dei nuovi
moduli; la suite G4A attesa ora contiene **19** test. I file RQ1,
prompt C/K e protocollo 180 stage non sono stati modificati.
Se vengono aggiunti altri moduli runtime prima del freeze, aggiornare
l'inventario e rieseguire il preflight su commit clean.

## Prossimi due test offline in PyCharm

Su branch e checkout puliti, eseguire:
```powershell
git status --short
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_live_dispatcher_mock_offline.py" -v
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_release_preflight_offline.py" -v
```

Risultati **attesi, NON ancora testimoniati**: G4K 18,
G4A inventory 19, entrambi `OK`. Se falliscono correggere
il problema localizzato e ripetere, senza attivare API.

## Prima del primo pilot API: gate rimanenti e stop

- Preflight reale in Colab sul checkout finale: split/manifest,
  source SHA 29 file e RQ1 source identity; pin repo clean.
- Verifica semantica lock/single-writer sul vero filesystem Drive,
  stallo e crash; un orphan non deve causare nuove chiamate.
- Test preciso dello stesso dispatcher G4K su factory mock,
  gestione errori e usage; controllo runtimes/versioni SDK reali.
- Prezzi del provider aggiornati, stima per lo STAGE D e budget
  operativo approvato; il sistema NON garantisce hard cap USD,
  né il 492 candidate graph invocations è un limite HTTP.
- Una release **non sintetica** indipendentemente autorizzata,
  SHA esterno e un solo stage discovery esplicitamente approvato
  dall'utente. La flag G4K resta False fino a nuovo commit/freeze.
- 11 casi OOD dell'Opzione B rimangono locked; non accedere a
  ground truth/scoring prima delle condizioni metodologiche.

**Non eseguire API live in questo gate.** La fonte di sicurezza
è il no-retry + single-stage claim prima del client e la release
source-bound, NON un limite monetario tecnicamente garantito.
