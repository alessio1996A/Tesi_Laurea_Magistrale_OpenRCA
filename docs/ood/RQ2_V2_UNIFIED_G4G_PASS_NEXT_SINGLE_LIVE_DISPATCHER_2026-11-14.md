# RQ2-V2 — G4G 17/17 PASS; prossimo blocco: dispatcher scientifico unificato

Data: **14 novembre 2026**. Branch: `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.

## Evidenza G4G effettivamente ricevuta

Dopo la correzione del typo `assertEqual_case`→`assert_equal_case` nell'unica fixture, l'utente ha comunicato:
```text
Ran 17 tests in 22.415s

OK
```

**G4G PASS**. Il test centrale attraversa `run_experiment`, i grafi ReAct/verify, ToolNode, fake LLM, preparazione C/K e il nuovo **ledger scientifico G4F**, usando release e dati esclusivamente sintetici in TemporaryDirectory. Per un caso discovery fittizio vengono archiviati 15 arm × D/C/K = 45 record con claim create-only, SHA di dipendenze, meter sintetici, readback. Le 17 prove includono errori D/C/K, forged E###, C abstain/K insufficient, crash/orphan, no-retry, blocco OOD, marker sintetico e assenza SDK/rete. Non rappresentano esperimenti OpenRCA con modelli remoti, non dimostrano lock su Google Drive.

La prima esecuzione G4G era fallita `FAILED (failures=1, errors=25)` esclusivamente per typo nel test, con cascading orphan fail-closed. Il PASS qui sopra è **nuova esecuzione dopo commit correttivo**; la protezione orphan non è stata allentata. Dettagli: `RQ2_V2_UNIFIED_G4G_FAKE_GATE_WINDOWS_FAILURE_FIX_2026-11-14.md`.

## Audit dei componenti RIUSABILI (niente nuovo framework parallelo)

Lettura diretta del repository:
- `src/evaluation/rq2_model_factory.py`: factory RQ2-only con controlli di package/versioni e source SHA, costruttori separati Google/Anthropic, parametri max_retries/timeout; non invoca API durante construction. Source storica RQ1 invariata.
- `src/evaluation/rq2_discovery_d_provider_transport.py`: già contiene pattern **claim PRIMA di creare il client** → `run_experiment` RQ1 → persistenza. Va **adattato** da plan/ledger/namespace RQ2 V1 al nuovo piano da 180 stage e al ledger G4F, **non riusato tale e quale**: le sue verifiche/source identity si riferiscono alla coorte e ai recorder V1.
- `src/evaluation/rq2_ck_provider_transport.py`: contiene approccio di chiamata tool-free (C/K) con `crea_modello_rq2`, recupero del raw text dai content blocks, ricevute metadati/token/errore. Anche questo usa il protocollo V1 e una sua release/recorder: **non chiamarlo direttamente su G4F**.
- `src/evaluation/rq2_langchain_parameter_mock_probe.py`: forwarding locale LangChain→SDK testato su versioni Colab pinned.
- `src/evaluation/rq2_langchain_fake_http_invoke.py`: il 12 novembre 2026 il test Colab con real LangChain e SDK, HTTP 503 **finto** e socket deny-all è stato **PASS**; Google e Anthropic hanno registrato un solo HTTP mock send per `CK_tool_free` e uno per `D_bound_tools` in modalità **sincrona**. `api_requests_to_real_providers=0`.
- `src/evaluation/rq2_sdk_retry_mock_probe.py`: SDK mock locale già testato, utile come prova complementare, senza costituire release.
- `src/evaluation/rq2_v2_unified_scientific_ledger.py`: G4F 22/22 PASS e G4G 17/17 PASS sui fake. È l'archivio scientifico della nuova coorte, con release SHA, parent e claim.

**LIMITE INVARIATO della prova trasporto 12/11**: certifica soltanto `model.invoke` sincrono tramite HTTP finto 503 con versioni e SHA testate. Non dimostra streaming/async, timeout sotto stallo reale, eventuali cambi di versione, metering fatturato, spesa hard-cap o semantiche lock in Google Drive/FUSE. Non dichiarare `492` come HTTP hard cap: sono invoke candidate a livello dei grafi.

## Decisione architetturale per il successivo sviluppo

Creare **un solo dispatcher reale per lo stage selezionato** con il piano RQ2-V2 unificato e ledger G4F, riutilizzando in modo controllato le funzioni RQ2-only già disponibili; NON duplicare i contratti D/C/K:
1. Prima del primo client: checkout clean, source inventory comprendente ledger, dispatcher e factory, SHA release esterno/immutabile, manifest/split GT-free reali, solo uno dei 60 D/C/K discovery e consenso API esplicito riferito allo specifico stage.
2. Claim esclusivo per lo stage **prima del client/provider invoke**. Nessun retry: crash dopo claim → orphan da revisione operativa; non trasformare quell'errore in una diagnosi valida.
3. Per D: `run_experiment(config,llm=...,salva=False)` originale e corretta selezione dei due motori ReAct/verify_graph come G2/G4G. Audit provenance tool_call_id/origine/contratto V2, salvare risultato o errore senza GT.
4. Per C/K: prompt source-bound da D/C archiviati e tool-free; mai eseguire `bind_tools`, verificare SHA prompt e E###, conservare `raw_response` e uso originale del provider, anche in presenza di risposta invalida.
5. Ricevute: distingui *invoke logico*, tentativo HTTP osservato, token disponibili e costo stimato. Un errore ambiguo non deve essere fatturato `0` per default. Limite di spesa/stop policy da chiarire e provare prima della release; l'API non fornisce necessariamente hard cap.
6. Testare **questo stesso dispatcher reale** con factory patchata fake e release fittizia in TemporaryDirectory, controllando che non si possa creare SDK reale e che non ci siano aperture OOD.
7. Riconciliare lock multiprocesso/Drive e crash, poi **congelare tutte le sorgenti includendo il dispatcher** (non riciclare il blueprint SHA G4C del checkout più vecchio).
8. Solo infine, previo consenso esplicito e limiti operativi, un **singolo pilot pagato** della Opzione A. Non avviare 180 stage insieme.

**Non ripartire da zero** e non rifare gli audit SDK già completati solo perché il branch è nuovo. RQ1 / RQ2 V1 / pilot Sonnet pregressi restano immutati e separati. L'Opzione B e gli **11 casi OOD** restano bloccati finché le K discovery non siano congelate e la procedura di valutazione approvata.

## Stato complessivo

G1 25, G2 9, G3A 23, G3B 9, G4A 18, G4B 18, G4D 17 effettivi +2 skipped, G4E 18, G4F 22, G4G 17: tutti i gate offline sottoposti a test risultano PASS con le riserve specificate. G4C con report GT-free reale e SHA conservate nel documento `RQ2_V2_UNIFIED_G4C_G4E_VERIFIED_SHA_REPORT_2026-11-14.md`. **Nuove richieste API della RQ2-V2 unificata = 0**, nessuna release scientifica live firmata, nessuna autorizzazione al pilot concessa.
