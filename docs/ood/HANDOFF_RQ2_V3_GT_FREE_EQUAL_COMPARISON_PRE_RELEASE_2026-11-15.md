# HANDOFF — TESI OPENRCA / RQ2-V3, 15 novembre 2026

## Come proseguire e regole di lavoro

Questo documento è il punto di continuità per la prossima chat. Tesi magistrale in Ingegneria Informatica (Università di Catania), **Harness Engineering per LLM applicati a Root Cause Analysis su Microsoft OpenRCA**. Consegna prevista: **1 dicembre 2026**. Procedere con attenzione scientifica; preferire verifiche necessarie a rapidità e ripetizioni inutili.

Collaborazione concordata: modificare il codice su branch GitHub nuovo/non congelato; chiedere all'utente un comando PowerShell unico per test locali PyCharm; esaminare gli output; passare a Colab solo con preflight e autorizzazione separata. Non fare chiamate a pagamento prima dell'opt-in esatto. In fase finale: scrittura tesi, grafici accuratezza/token, confronto con paper OpenRCA 1.0, analisi della conoscenza K, refactoring e commenti italiani, rimozione file superflui senza toccare gli artifact. Avvisare spontaneamente quando conviene aprire nuova chat e preparare handoff, e quando servono paper/trascrizioni del professore; **non servono in questa fase ingegneristica**. Il professore NON vuole implementazione human-in-the-loop (solo discussione finale).

## Risultati e vincoli congelati

- RQ1 Evaluation20: 20 incidenti, 5 harness × 3 modelli = 300 tentativi, 295 complete e 5 errori provider. Scoring ufficiale Microsoft e analisi appaiate già congelati: **non ripetere, rescore o sovrascrivere**. Risultato Sonnet A1_PAVE medio 0.5040 vs A0 0.1165, strict 8 vs 1 sui 20 casi. In tesi distinguere effetti harness, variazioni tra modelli, token e limiti statistici.
- RQ2-V2 **sorgente pin** `f0b64a36b08c2ae5db424b544965db5362190377`; **release SHA256** `af1867e2539edbb42cf27ae92c602dfacca1c12968475235955fb1cf0ed2dac4`. Architettura D (diagnosi), C (ipotesi causale), K (regola candidata).
- Pilot reale V2 `cloudbed-1_q032:gemini:A0`: D `RECORDED_COMPLETE` (D SHA `8628b902aaa4a5955d8527ba6151eb1dc4d004aa9722cc11302a0c20fca98fb1`); C `INVALID_OUTPUT` (record SHA `51946d926aa2a5a0f9dd2ba997d8565116ef8158a2af44df5d0051d73ee3f4b1`); K `BLOCKED_DEPENDENCY`, zero API. D 7 model call, 30,332 input e 409 output token; C 1 call, 3,151 input e 257 output token.
- In C il testo estratto contiene una newline NON escapata dentro il campo JSON `schema_version`. Il codice originale `agent.graph_engine.testo_messaggio()` usa `"\\n".join(parti)` su liste di content block; un test offline riproduce l'introduzione artificiale di newline. **NON sappiamo se sia stato questo a causare l'errore reale Gemini**, perché il record originale non salva i content block SDK non elaborati. Non riparare, rigiocare o riclassificare il record V2.
- Discovery RQ2: **4 incidenti, 5 harness (A0, A1, A1_8R, A1_8R_Planning, A1_PAVE), 3 modelli (Gemini, Sonnet, Haiku)**; totale 180 stage D/C/K. **11 casi OOD/test BLOCCATI**; nessun GT/Market.zip/scorer disponibile al percorso discovery. Il budget approvato V2 era USD 100 operativo **non hard cap**; **non trasferire approvazione o pin V2 a una release V3**. Nessun retry automatico dopo claim e chiamata API ambigua.
- La fase GT-free non prova la correttezza causale; analisi scientifica separa validità JSON, abstention, errori provider, qualità diagnosi, consumo token, qualità K, blocco dipendenze, e non fonde versioni sperimentali distinte.

## Perché serve V3

Lo stesso difetto potenziale di estrazione interessa **C/K e anche la risposta finale D** nei motori `agent/rq2_v2_graph_engine.py` (A0/A1/A1_8R) e `agent/verify_graph.py` (Planning/PAVE). La soluzione candidata usa una politica **uniforme per le risposte finali D/C/K**: concatenare esattamente i frammenti testuali visibili senza inserire spazi/newline; non includere thinking/signatures/tool use; NON riparare JSON realmente malformati. Non alterare log dei tool, promps, metering, budget o grafi originali. Metadata: tipo contenuto, politica, numero di blocchi testuali e non testuali; non memorizzare thinking.

Il trasporto V2 e ledger V2 sono congelati e non devono essere modificati. L'adattatore V2 normalizza solo stage ID V2, e il ledger V2 scarta i metadati aggiunti; quindi V3 richiede stage ID, ricevute, nuovo ledger, source inventory e release propri.

## Test mirati già SUPERATI in PyCharm — 74/74 PASS

Tutti i seguenti esiti sono stati forniti dall'utente, senza SDK reali:
1. **4/4** rischio newline della funzione originale e parità fra modelli sintetici;
2. **9/9** estrattore esatto candidato;
3. **6/6** trasporto C/K originale con estrattore candidato in test;
4. **9/9** trasporto C/K candidato isolato;
5. **3/3** compatibilità con adattatore/ledger V2 sintetici, evidenziando perdita metadati;
6. **7/7** ricevuta C/K con provenienza e isolamento V2;
7. **7/7** journal create-only sperimentale in TemporaryDirectory;
8. **8/8** piano V3 GT-free distinto su 180 stage e 11 OOD bloccati;
9. **5/5** rischio newline nella diagnosi D dei due motori;
10. **9/9** `rq2_v3_d_final_stream_candidate` su stream graph sintetici;
11. **7/7** integrazione `run_experiment()` reale con modelli/grafi/caso simulati e controllo task-aware originale.

**Non ripetere questi 74 test per inerzia.** Eseguire prima i nuovi test qui sotto. NON equiparare questi successi offline a validazione delle risposte degli SDK reali.

## Branch di lavoro corrente e componenti

Branch: `feature/rq2-v3-gtfree-equal-comparison-design-2026-11-15`. Creato dal branch audit `audit/rq2-v2-ck-multiblock-fairness-2026-11-15`, che include la prima documentazione del rischio JSON. Il commit HEAD **va riletto da GitHub**, non inferito da questo documento dopo nuovi commit.

Componenti già sul branch:
- `src/evaluation/rq2_v2_ck_text_extraction_candidate.py`: politica esatta, nessuna API.
- `src/evaluation/rq2_v2_ck_provider_transport_candidate.py`: trasporto C/K candidato, no retry, metadata, non collegato al dispatcher.
- `src/evaluation/rq2_v3_ck_provenance_receipt_candidate.py`: prima ricevuta C/K; **usa stage ID V2**, solo studio di fattibilità, non usare nel dispatcher V3.
- `src/evaluation/rq2_v3_offline_provenance_journal_prototype.py`: journal sperimentale temporaneo, NON ledger scientifico produttivo.
- `src/evaluation/rq2_v3_unified_gtfree_discovery_plan.py`: piano deterministico V3 `rq2_v3_unified_equal_ck_extraction_discovery_v0`; 180 stage nuovi; **namespace proposto** `data/rq2_v3_unified_scientific_v1`; OOD 11 bloccati. No riuso di D/C/K storici V2; no release.
- `src/evaluation/rq2_v3_d_final_stream_candidate.py`: cattura l'AIMessage finale D tramite delegatore monouso del grafo; conserva copia originale, tool e token.
- `src/evaluation/rq2_v3_d_runner_capture_candidate.py`: integrazione tramite patch contestuale offline delle due funzioni chiamate da `run_experiment()`. È ancora **prototipo**; evitare globale patch in live/concorrenza senza adeguati gate e test.
- `src/evaluation/rq2_v3_scientific_receipt_adapter_candidate.py`: **NUOVO**, normalizza D e C/K con ID V3, riusa validator puri già collaudati, controlla provenance e sanitized errors, conserva in D `d_final_text_extraction` e in C/K `text_extraction`; non scrive e non esegue provider.
- `src/tests/test_rq2_v3_scientific_receipt_adapter_candidate_offline.py`: **9 NUOVI TEST ANCORA PENDING**; verifica 15 arms (5×3) D/C/K, rifiuto ID V2/altro modello/OOD, errori sicuri, JSON C malformato preservato, contatori/provenienza, trasporto SDK mock senza HTTP.

L'adattatore è una prova di contratto, **non è un ledger scientifico né una release V3**. Per K il controllo del genitore C completo va ancora gestito nel futuro ledger V3; non attribuire questo gate all'adattatore puro. Per D la validazione del record e della provenienza è distinta dai vincoli di commit/release/claim, ancora assenti.

## Prossima azione concordata

1. Eseguire *soltanto* `test_rq2_v3_scientific_receipt_adapter_candidate_offline.py` in PyCharm con `PYTHONPATH="src;src/tests"`, branch e HEAD verificati. Atteso **9 tests**, NON ancora certificato. Se fallisce, analizzare test e codice specifici, non cambiare frozen V2, non fingere che siano passati.
2. Se PASS: implementare **ledger V3 create-only indipendente** con propri stage-ID, namespace distinto, release/source-bound preflight, controllo D/C/K completo e readback metadati, dati GT-free, claim-first/no-auto-retry, audit integrità e crash, singolo writer; test esclusivamente temporanei fino a gate scientifico.
3. Dopo regressione selettiva: costruire nuovi source inventory e release V3 con commit clean, audit SDK/runtime, preflight read-only Google Colab/Drive, protezione OOD. Non fare stage pagati senza esplicita nuova approvazione per release, singolo stage e budget. Non mescolare output V2 con V3.
4. Quando la campagna RQ2 è congelata: trasferimento conoscenza/valutazione, analisi scientifica, grafici accuratezza/token, stesura, pulizia codice/commenti italiani. Non consentire che la correzione ingegneristica si trasformi in un esperimento non pianificato.

**Stato attuale: NO-GO per nuovi stage a pagamento. V2 e RQ1 completamente intatti. Paper/trascrizioni del professore non necessari adesso.**
