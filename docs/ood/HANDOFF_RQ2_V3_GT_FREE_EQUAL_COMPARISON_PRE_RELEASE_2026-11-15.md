# HANDOFF AGGIORNATO — Tesi OpenRCA, RQ2-V3, 15 novembre 2026 (post Colab)

> **Questo documento sostituisce operativamente il precedente handoff V3 dell'11/15**, precedentemente fermo a 83 test. Fonte di continuità per aprire una nuova chat: leggere integralmente, recuperare da GitHub i file rilevanti e verificare HEAD prima di ogni modifica. **Nessuna API LLM V3 eseguita; release V3 NON congelata; test/OOD BLOCCATI.**

## Contesto e vincoli operativi

- Università di Catania, tesi magistrale Ingegneria Informatica: **Harness Engineering per LLM in Root Cause Analysis (Microsoft OpenRCA)**. **Consegna 1 dicembre 2026**: non dilatare inutilmente l'ingegnerizzazione, iniziare scrittura dei capitoli RQ1/metodologia in parallelo alla chiusura di RQ2.
- Metodologia concordata: GitHub branch non congelato → modifica isolata spiegata → PyCharm con **soli test pertinenti** → Colab read-only pin → singolo pilot reale SOLO dopo approvazione esplicita del nuovo commit, SHA release, specifico stage e budget. Mai autorizzare API dalla sola conferma dei test; non inventare esiti; GT-free sempre.
- RQ1 e RQ2-V2 congelati, **non modificarli né ripetere campagne**. Human-in-the-loop NON richiesto dal professore (solo discussione conclusiva). In chiusura: refactoring e commenti italiani, rimozione prudentissima dei file superflui su branch separato, grafici token/accuratezza, stesura tesi.
- Avvertire spontaneamente quando la chat diventa lunga; aggiornare handoff GitHub e fornire messaggio pronto da incollare nella chat successiva. Chiedere paper o trascrizioni del relatore **solo se realmente necessari**, indicando perché. **Non servono per il prossimo step tecnico**.

## RQ1 — risultati scientifici già congelati

- Evaluation20: 20 incidenti, 5 harness × 3 modelli = 300 tentativi, 295 completati e 5 errori Gemini; scoring ufficiale Microsoft già eseguito; non rescore, non sovrascrivere, non rifare.
- Sonnet A0: mean score 0.1165, strict 1/20; Sonnet A1_PAVE: mean score 0.5040, strict 8/20. Pairwise e trade-off token già presenti nel progetto. Limitare conclusioni alla coorte e ai provider osservati, non confondere l'incremento accuratezza con un trasferimento della conoscenza già dimostrato.

## RQ2-V2 congelata e origine di V3

- RQ2-V2 source commit `f0b64a36b08c2ae5db424b544965db5362190377`, release SHA-256 `af1867e2539edbb42cf27ae92c602dfacca1c12968475235955fb1cf0ed2dac4`. Il pilot reale `cloudbed-1_q032:gemini:A0` ha D `RECORDED_COMPLETE`, C `INVALID_OUTPUT`, K `BLOCKED_DEPENDENCY`; **NON** rifarlo o reinterpretarlo.
- In C osservata una newline non escapata nel JSON salvato. Un test riproduce il potenziale effetto di `"\n".join(parti)` su content-block, ma **non dimostra** che abbia causato l'errore originale: content-block SDK non grezzi nel record congelato.
- V3 affronta SOLO il rischio di disomogeneità nell'estrazione del testo finale su D/C/K: concatenare frammenti visibili senza separatori, non riparare JSON, escludere thinking/tool uses, mantenere provenienza. Stessi prompt C/K, cinque harness, modelli, budget e coorte. Nessun riuso di output D/C/K V2.

## V3 — identità e stato sorgenti

- GitHub: `alessio1996A/Tesi_Laurea_Magistrale_OpenRCA`, branch `feature/rq2-v3-gtfree-equal-comparison-design-2026-11-15`.
- **Commit CODICE effettivamente testato in PyCharm e Colab**: `e564d49eeba392d4001b29a62c32a5693fc2c028`. L'aggiornamento di QUESTO handoff fa avanzare HEAD con **docs-only**: per le successive prove di source-bound release rileggere HEAD e rifare il solo inventory/commit-bound gate sul definitivo nuovo pin. Non presentare l'HEAD docs-only come commit già provato in Colab.
- Protocollo `rq2_v3_unified_equal_ck_extraction_discovery_v0`, namespace futuro `data/rq2_v3_unified_scientific_v1`. 4 discovery × 5 harness `A0, A1, A1_8R, A1_8R_Planning, A1_PAVE` × 3 modelli `gemini, sonnet, haiku` × D/C/K = **180 stage logici**. **11 OOD/test sigillati**. Nessuna API V3, 0/180 stage tentati.
- Componenti V3 ora implementati come codice **candidate/pre-release**:
  - `src/evaluation/rq2_v3_unified_gtfree_discovery_plan.py` — piano.
  - `src/evaluation/rq2_v3_d_final_stream_candidate.py`, `rq2_v3_d_runner_capture_candidate.py` — D final text + provenance per motori ReAct e Planning/PAVE.
  - `src/evaluation/rq2_v2_ck_text_extraction_candidate.py`, `rq2_v2_ck_provider_transport_candidate.py` — estrazione/trasporto C/K, versione successore senza impatto V2.
  - `src/evaluation/rq2_v3_scientific_receipt_adapter_candidate.py` — riceve D/C/K e controlla provenienza/status.
  - `src/evaluation/rq2_v3_scientific_ledger.py` — ledger V3 separato con claim-before-request, create-only, parent hash, readback, orphan senza retry.
  - `src/evaluation/rq2_v3_scientific_source_inventory.py` e `rq2_v3_scientific_source_release_gate.py` — verifica source inventory/release; **non creano una release**.
  - `src/evaluation/rq2_v3_scientific_live_stage_preflight.py` — preview runtime; **`verify_v3_live_runtime_gate` al 15/11 termina SEMPRE in NO-GO**; NON contrassegnare sdk_retries_disabled_verified/per_request_timeout_verified/single_writer_drive_verified come veri per semplice input esterno.
  - `src/evaluation/rq2_v3_scientific_single_stage_dispatcher.py` — collega D/C/K a ledger, commit/release/approvazione stage, opt-in esatto off per default. Senza release+runtime gate funzionante **non può eseguire API**. Il dispatcher NON equivale a campagna reale già validata.
- **PyCharm: 147 test mirati distinti PASS forniti dall'utente**, non 147 test in un unico run: 83 precedenti + 10 ledger + 12 source inventory + 12 source release gate + 12 live runtime preview + 18 dispatcher. Dopo un fix mirato V3, ledger 10/10 e gate 12/12 confermati; successivamente runtime 12/12 e gate 12/12, dispatcher 18/18. **Non ripeterli per inerzia**. La suite globale `Ran 1434 tests` aveva failure 1 + errors 2 + skipped 2; i due errori V3 furono corretti e riconsolidati con test mirati, la failure AST del vecchio `test_rq2_v2_sync_429_retry_guard_offline.py` è preesistente: cerca assegnazione letterale `LIVE_API_ENABLED=False` benché la produzione V2 usi opt-in ambientale esatto. V2 rimane intatto. Non dichiarare l'intera suite globale verde.

## Colab V3 — risultati REALMENTE comunicati dall'utente il 15/11

**Repository su Colab**: `/content/Tesi_OpenRCA`, commit clean `e564d49eeba392d4001b29a62c32a5693fc2c028`; **dati** `/content/drive/MyDrive/Tesi_OpenRCA`. Condurre le prossime prove solo sul pin finale verificato; non cambiare branch automaticamente.

1. **GT-free reale source inventory PASS**:
   `gt_free_verified=true`, `rq1_source_verified=true`, `discovery_stages=180`, `ood_cases_locked=11`, `missing_future_sources=[]`.
   Inventory candidate SHA256 (solo per il commit testato): `e13bc96871a39ccaae4f25fd3f4ba99b263a40ced08a48d29d4c52a0d9c1be06`.
   `release_frozen=false`, `real_llm_calls=0`, `can_execute_api=false`.
2. **Runtime SDK inizialmente globale Colab fallito correttamente** (Python 3.13.18; 1.7.4 core / 1.2.19 langgraph, 3 SDK assenti, google-genai 2.12.1). Ripristinato senza cambiare Colab globale, con **`pip --target /content/rq2_v2_pinned_sdk_py313`**: `langchain=1.4.7`, `langchain-core=1.7.1`, `langgraph=1.2.18`, `langchain-google-genai=4.4.2`, `langchain-anthropic=1.7.7`, `google-genai=2.34.0`, `anthropic=2.6.0`, `google-auth=2.56.0` + dipendenze. Nuovo subprocess `PYTHONPATH=DEPS:REPO/src` verifica **6/6 versioni esatte, 4/4 hash source SDK esatti, factory RQ1 invariata, factory RQ2 `assert_exact_runtime_snapshot(): PASS`**. Non reinstallare per inerzia.
3. **Google Drive V3 scratch PASS**, stesso runtime Colab: lock concorrente respinto, lock rilasciato/riacquisito, **8 writer concorrenti → 1 O_EXCL successo, 7 collisioni**, readback corretto, scratch eliminato, `scientific_data_root_modified=false`, zero API. Stato `V3_DRIVE_SAME_RUNTIME_SCRATCH_PASS`. **NON provato fra sessioni/VM diverse**; ammettere SOLO una sessione Colab writer e uno stage seriale.
4. **Trasporto SDK nel medesimo snapshot/pin V3: test HTTP 429 MOCK PASS e read timeout LOOPBACK PASS** (risultato utente):
   - `SDK_SOURCE_AND_VERSION: PASS`
   - `HTTP_429_MOCK: PASS`, stato `SYNC_HTTP_429_MOCK_ONE_SEND_EACH_NO_API_NOT_RELEASED`, 4 fake HTTP sends totali, **1 per provider (Google, Anthropic) × tipo (`CK_tool_free`, `D_bound_tools`)**.
   - `SYNC_LOOPBACK_TIMEOUT: PASS`, stato `SYNC_LOCAL_STALL_TIMEOUT_CHECKED_NO_API_NO_RELEASE`, 4 invii loopback e 4 timeout observed, in secondi: Google CK **0.305**, Google D **0.3044**, Anthropic CK **0.3033**, Anthropic D **0.3036**; un invio ciascuno. Credenziali fittizie, loopback `127.0.0.1` o HTTP finto, zero chiamate LLM.
   - Le sonde esistenti sono `src/tests/rq2_v2_sync_429_retry_probe.py` e `src/tests/rq2_v2_sync_timeout_loopback_probe.py` usate con `PYTHONPATH=DEPS:REPO/src:REPO/src/tests` e commit V3. Storica prova 503 finto sui medesimi SDK con SHA della fonte (12/11), senza bisogno di ripeterla, documentata `docs/ood/RQ2_COLAB_FAKE_HTTP_INVOKE_2026-11-12.md`.
   - Il `graph.stream()` in RQ1 cicla gli eventi del grafo, ma i nodi LLM usano `llm.invoke()` / `llm.bind_tools(...).invoke()` sincroni. I test 429/503/stallo coprono quei **percorsi di trasporto**, non tutte le traiettorie reali del grafo, né async/streaming HTTP, massimo globale numero richieste, timeout dell'intero D, né hard cap USD. `async_streaming_tested=false`, `full_stage_timeout_guaranteed=false`, `usd_hard_cap_guaranteed=false`.
5. Tutte le evidenze Colab V3 riportano **`real_llm_calls=0`, `can_execute_api=false`, `release_frozen=false`**. I test con chiavi fake non autorizzano alcun pilot.

## BLOCCANTI REALI E NEXT STEP — NO-GO FINCHÉ NON RISOLTI

**Non ripetere test già PASS. Proseguire dalla progettazione di una attestazione V3 effettiva, verificabile, source-bound e conservativa**:

1. Il runtime gate V3 `verify_v3_live_runtime_gate` **fa sempre raise**. Esiste soltanto preview di versioni/source. Per accettare una release occorre una logica esplicita che controlli prove credibili e loro ambito: SDK sincrono retry e timeout, limiti non provati, single writer stesso runtime (non multi-VM), gestione usage fail-closed. Evitare di impostare flag `true` basandosi soltanto su mock o report autoasseriti; valutare se il contratto richiede prove irrealistiche come HTTP hard-cap globale e progettare correzione **soltanto V3** con audit circoscritto. La revisione codice cambierà commit/source hash: nuovo preflight mirato finale.
2. Il contratto della **release V3** attualmente richiede file `data/rq2_v3_unified_scientific_v1/release_v1.json` create-only con schema rigoroso, SHA canonico, `runtime_attestation_sha256`, source inventory, futuro dispatcher/runtime hashes e commit clean, non crea automaticamente il file. Studiare verifica release + ledger per evitare circolarità/auto-approvazione e **non creare release senza revisione esplicita**; un hash non è una firma utente. Fare un dossier di prerelease GT-free e budget realistico.
3. Eseguire soltanto verifica differenziale/targeted dei nuovi componenti, poi checkout definitivo clean Colab, inventory GT-free source/runtimes finali e freeze scientifico V3. Non cambiare protocolli/fonte RQ1/V2.
4. Dopo il freeze: prezzi/quote aggiornati, costi token, rischio D multichiamata, **budget operativo non hard cap** e separata approvazione utente del **singolo stage** (identità stage, modello, commit, SHA release, USD), con opt-in esatto. Solo dopo autorizzare **una** chiamata di pilot D; claim-first prima della chiamata, nessun retry automatico, audit claim/record post-call. Se provider restituisce error o claim resta orphan: STOP e review, mai retry opportunistico.
5. Poi eventuale campagna 180 stage (non 180 chiamate HTTP: D multichiamata e K può restare bloccato), analisi K con outcome e limiti su 4 incidenti; 11 OOD non sbloccare prima di freeze/decisione metodologia di generalizzazione. Scrivere tesi parallelamente: RQ1 copre risultati quantitativi già solidi, RQ2 non è ancora evidenza di knowledge transfer.

## Messaggio da passare alla prossima chat

> Continua la mia tesi magistrale OpenRCA/RQ2-V3. Usa il connettore GitHub e leggi integralmente `docs/ood/HANDOFF_RQ2_V3_GT_FREE_EQUAL_COMPARISON_PRE_RELEASE_2026-11-15.md` sul branch `feature/rq2-v3-gtfree-equal-comparison-design-2026-11-15` del repo `alessio1996A/Tesi_Laurea_Magistrale_OpenRCA`. Il commit di **codice realmente testato su Colab** è `e564d49eeba392d4001b29a62c32a5693fc2c028`, mentre HEAD potrebbe essere avanzato per aggiornare la documentazione; verifica quello corrente. Abbiamo **147 test mirati PyCharm PASS**, inventory GT-free V3, SDK 6/6 versioni + 4/4 source hashes, factory RQ2 PASS, Drive same-runtime lock/O_EXCL scratch PASS, test SDK sincroni 429 MOCK e timeout loopback PASS sul pin V3; 0 API reali V3, 11 OOD locked. **Release V3 ancora NO-GO** perché il runtime gate è deliberatamente fail-closed e release/attestazione non sono implementate fino al punto di avvio. Non ripetere test e non modificare RQ1/RQ2-V2. Prossimo compito: completare in modo minimale e corretto l'attestazione runtime source-bound e il freeze GT-free della release V3, poi richiedere separatamente consenso per un singolo stage/budget. Consegna tesi 1 dicembre 2026: evitare nuovi audit non necessari, scrivere RQ1/metodologia in parallelo. Avvisami sempre quando cambiare chat; chiedi paper/trascrizioni solo se servono davvero.
