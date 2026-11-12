# RQ2 — PREREGISTRAZIONE SCIENTIFICA CANDIDATA V1 (discovery)

**12 novembre 2026** · Laurea magistrale OpenRCA / Harness Engineering.  
**Stato: CANDIDATA, NON FROZEN, NON ESEGUIBILE, TEST OOD CHIUSI.**

Questo documento è un'istanza specifica del protocollo `PROTOCOLLO_RQ2_BOZZA_V0_2026-11-11.md`, fondata sui controlli tecnici eseguiti. Non è un permesso per chiamare i provider. Serve a fissare senza ambiguità le decisioni metodologiche prima di aprire qualunque discovery e a separare i blocchi scientifici dai costi (che **non** hanno un tetto prefissato, su indicazione del professore riferita dall'utente).

## 1. Fonti e integrità di partenza

- RQ1 originale congelata, commit `e4845e7fe9a399e10dd2db6f320dfeaeeddf3379`. **13 blob di sorgente RQ1** riesaminati con il preflight `rq2_protocol_identity_preflight.py`, parità esatta locale confermata.
- Split Market GT-free **SHA-256**: `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`.
- Manifest GT-free di query/finestra/task **SHA-256**: `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`.
- Piano di fase: `src/evaluation/rq2_dryrun_plan.py`, ancora `DRAFT_NOT_EXECUTABLE`; il suo `preview_sha256` deve essere **riletto dai veri CSV originali** tramite `preview_market`, registrato e approvato prima di creare un release.
- **Non importare** file di scoring, mapping case→fault, `record.csv`, ground truth o suggerimenti di classe nel runtime D/C/K. Lo scorer Microsoft e il valutatore RQ2 agiscono solo offline, separati.

## 2. Partizione immutabile candidata e denominatori

**4 discovery (4 gruppi singleton, 1 candidato per classe selezionato in precedenti audit isolati):**
- `cloudbed-1_q032`
- `cloudbed-1_q050`
- `cloudbed-2_q026`
- `cloudbed-2_q045`

**11 test OOD, ancora preclusi ai provider e alle nuove regole:** `cloudbed-1_q014`, `cloudbed-1_q021`, `cloudbed-1_q030`, `cloudbed-1_q059`, `cloudbed-2_q014`, `cloudbed-2_q021`, `cloudbed-2_q040`, `cloudbed-2_q041`, `cloudbed-2_q058`, `cloudbed-2_q076`, `cloudbed-2_q077`.

**Regola di isolamento:** 14 gruppi temporali OOD in totale; 4 nella discovery, **10 nel test**. `cloudbed-1_q014` e `cloudbed-1_q030` condividono una finestra e **non** sono osservazioni indipendenti; stesso gruppo per stratificazione, intervalli e valutazione multi-fault. Gap temporale cross-phase, sullo stesso cloudbed, **strettamente superiore a 1 ora**, verificato dal preflight, non inferito dai nomi.

**Due harness:** `A1`, `A1_8R`. **Tre modelli:** `gemini-3.5-flash-lite`, `claude-sonnet-5-5`, `claude-haiku-5-5`.

**Denominatori completi per studio:**
- Discovery: 4 casi × 2 harness × 3 modelli × (D, C, K) = **72 stage**, ciascuna D potenzialmente multi-richiesta.
- Test dopo freeze delle regole: 11 casi × 2 harness × 3 modelli × (D, C) = **132 stage**.
- Totale pianificato **204 stage logici**, di cui **90 D, 90 C, 24 K**. **Non** sono 204 chiamate API. I fallimenti e le astensioni restano nel denominatore pianificato.

## 3. Esatta configurazione D (parità RQ1)

Riutilizzo del runner `evaluation.experiment_runner.run_experiment` non modificato, tramite `rq2_discovery_d_provider_transport`:
- `variant_scheme=current`, `output_contract_mode=v2_enforce`, `max_tool_rounds=6`, `recursion_limit=30`, `salva=False`.
- I cinque tool originali RQ1 sono i soli permessi; preprocessing originale RQ1 vincolato a cloudbed, finestra e task. Nessun aumento occulto del budget round.
- Factory originale RQ1 `crea_modello`, con ID esatti. Per Claude `max_tokens=4096`, `max_retries=0` nel codice della factory; i parametri di sampling non sono esplicitamente assegnati. Per Gemini i default del client storico non sono assegnati esplicitamente. **Congelare le versioni delle dipendenze ed esplicitare la policy dei retry anche nel backend Google prima delle API, senza alterare RQ1 a posteriori.**
- Il task JSON D originale è un outcome diverso dal nuovo fault-type probe C. **Regola candidata per fissaggio ex ante:** se il JSON D finale è invalido ma i tool-observation della D formano un bundle E### valido, registrare D come `RECORDED_COMPLETE` ai fini della disponibilità delle osservazioni per C, mantenendo `original_d_json_status` invalido; NON riscrivere la risposta D e NON accreditarla come diagnosi giusta. Se provider/trajectory fallisce, D `PROVIDER_ERROR` o `INVALID_OUTPUT`; le fasi a valle `BLOCKED_DEPENDENCY`, senza chiamata provider.

## 4. Esatta configurazione C/K

- Entrambe tool-free; una `SystemMessage` e una `HumanMessage` da package source-bound; **una sola** chiamata LLM per stage, senza `bind_tools`, senza retry automatico, senza ground truth, senza lista delle quattro classi target.
- C riceve **solo** task originale GT-free ed evidenze E### osservate dalla D; la risposta diagnostica finale D non viene usata come causa “vera” o suggerimento di classe. Contract validato da `validate_cause_probe` (`schema_version=rq2_cause_probe_v0`), campi `decision`, `predicted_fault_type`, `predicted_component`, `confidence`, `evidence_ids`, `alternatives`, `limitations`. `diagnosis` senza evidenze non valida; astensione con causa nulla valida. Raw JSON non viene riparato.
- K riceve le stesse evidenze e la probe C come **ipotesi non verificata**, esclusivamente dopo una C `RECORDED_COMPLETE` dei quattro casi discovery; validate con `schema_version=rq2_candidate_rule_v0` e `status=candidate` o `insufficient_evidence`. `required_signals`, `conditions`, `combination`, `abstain_when`, `counterexamples`, `limitations` e `pseudocode` rimangono dati non fidati: **non eseguire pseudocodice LLM**.
- Hash sistema C dal preflight verificato in PyCharm: `81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42`.
- Hash sistema K: `0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71`.
- C/K devono conservare `package_sha256` / `binding_sha256` del contenuto *dinamico* per ogni stage. L'hash di sistema da solo non autentica l'intero messaggio.
- Codice `rq2_probe_adapter.py` SHA-256 catturato: `60de1f73af15609a4328532dacd54b20b42701836bd6d6c4b60128ef9e6a4e53`. Prima del release verificare drift su codice/contratti/storage, poi registrare repository commit e versioni pacchetti.

## 5. KPI e interpretazione delle pseudoregole: criterio **prima** di vedere la test

Il catalogo `rq2_kpi_formalizability_preflight.py` contiene indicatori noti dal sorgente RQ1, **non** una certificazione di unità e trasformazioni fisiche. L'audit numerico su development non dimostra la correttezza fisica dei KPI né la copertura delle finestre test.

**Regola conservativa ex ante:** ciascuno dei 24 K viene riportato come `candidate`, `insufficient_evidence`, `invalid_contract`, `provider_error`, `blocked_dependency`, o `requires_verification`. La mera validità JSON non autorizza una regola operativa. Qualsiasi segnale con unità, disponibilità, semantica counter/gauge/level, aggregazione o finestra **non verificata da documentazione e development autorizzato** resta `not_formalizable`; non inventare MB/s, rate, threshold o unità per sbloccarla.

**RQ2-C, solo esplorativa:** se un sottoinsieme K supera un criterio statico preregistrato e documentato **prima di vedere gli 11 test**, la specifica verificata può essere implementata offline con operatori deterministici (non il testo di `pseudocode`) e congelata prima dell'apertura test. Se **nessuna K** è formalizzabile, riportare chiaramente questo risultato negativo: non rilassare i criteri sulla base della test.

**Contrasto secondario di esempio da preregistrare**: per la dimostrazione implementativa primaria usare l'arm `A1_8R + Sonnet` scelto **prima** della discovery, con reporting descrittivo delle **tutte e 24** K e analisi secondarie sugli altri arm. Questa scelta non autorizza selezione della “migliore regola” in base a score test. Eventuali nuove forme di regole richiedono nuovo protocollo e cohort separata.

## 6. Scoring e confini inferenziali

**RQ2-A primaria:** `predicted_fault_type` C confrontato offline con tipo di guasto ufficiale sulle **11 query test**: tabella raw, astensioni ed errori separati; accuratezza sia su pianificati sia su validi; confronto **appaiato** A1 vs A1_8R per stesso caso e modello, win/tie/loss, breakdown per classe e cloudbed. Normalizzazione alias **da congelare indipendentemente dalle predizioni** nel valutatore isolato, non in prompt. Causa/test originale D valutata separatamente con scorer Microsoft e relativo task (alcuni task non chiedono `reason`). CI/dispersione eventuali devono raggruppare le finestre temporali, non trattare q014/q030 come indipendenti; con 10 gruppi, evitare affermazioni forti di significatività.

**RQ2-B:** qualità strutturale dei 24 candidati K, grounding sulle evidenze E###, falsificabilità, formalizzabilità, astensioni, errori, non-implementabilità. Niente accuratezza di regole senza implementazione verificata.

**RQ2-C:** solo se è stato eseguito un freeze separato delle regole prima dell'accesso al test; one-vs-rest a **livello di gruppo/finestra e componente**, contando la finestra multi-fault come positiva per ciascuna classe presente. Per ogni regola: TP/FP/TN/FN, astensioni, coverage e denominatori. Nessuna osservazione “healthy” inventata o scoring ground truth reso visibile al modello.

## 7. Operatività, budget e crash

**Budget:** su indicazione del relatore riferita dall'utente, nessun massimale USD preventivo né hard cap di spesa. Registrare sempre numero richieste, token input/output billable quando disponibili (incluso thinking), modello, durata, errori e costo tariffario osservabile, quale **KPI descrittivo, non condizione di via libera**.

**Identità e crash:** ogni stage della discovery è prenotato con `RQ2DiscoveryClaimJournal.claim_stage` prima della chiamata al modello; salvataggio create-only via `RQ2StageArtifactStore`. Un claim senza risultato resta `unresolved_manual_review`; niente ritentativi automatici né rilascio per timeout. In caso di errore fornitore, conservare esito e mancante usage (non sostituire con zero), senza riparare JSON o scartare i fallimenti dalle tabelle pianificate.

**Pilot reale:** la prima D discovery dopo un protocollo congelato è **la prima osservazione del piano**, non una prova da usare per ricalibrare prompt, scegliere modello o cambiare regole. Se si vuole un pilot tecnico di connettività **non incluso** nella campagna, usare solo un caso development autorizzato e una procedura separata, non un caso test OOD. Non avviare mai le 11 test prima del freeze *scientifico* delle K, distinto dal freeze tecnico del protocollo.

## 8. Decisioni residue da CHIUDERE prima del release

**Tutti i seguenti gate sono ancora aperti** (e NON diventano “fatti approvati” grazie a questa bozza):

- [x] Verifica reale in Colab del `preview_market(data_dir)` con hash originali GT-free: controllo 4+11, gruppi 4+10, 204 stage e `preview_sha256` della coorte. **Evidenza riportata dall'utente il 12/11:** `docs/ood/RQ2_PREFLIGHT_GT_FREE_REALE_VERIFICATO_2026-11-12.md`; questo solo gate tecnico è chiuso, mentre il release scientifico resta NON firmato.
- [ ] Impronta esatta di commit Git/pacchetti runtime e policy effettiva di retry/timeout Google/Anthropic; *nessuna* modifica RQ1 non versionata. **Avanzamento tecnico 12/11:** pacchetti Colab + quattro SHA sorgente confermati; forwarding dei parametri LangChain → SDK con chiavi sintetiche verificato (`8/8 OK`, Gemini attempts=1/timeout=300000ms; Claude max_retries=0/timeout=300s). Proposta, NON freeze né release: `RQ2_PROVIDER_RUNTIME_POLICY_CANDIDATE_2026-11-12.md`. Il trasporto `invoke` sincrono con HTTP 503 interamente finto **è ora superato in Colab** (8/8 test e 1 richiesta per ciascuno dei 4 percorsi); la factory dedicata RQ2 è stata creata e iniettata negli adapter D/C/K, ma non ancora verificata dall'utente con le suite aggiornate. Restano la formalizzazione definitiva di timeout/versioni/provenienza in release e la verifica degli altri gate scientifici: checkbox lasciata aperta finché il release non è realmente firmabile.
- [ ] Catalogo KPI versione e SHA, criteri statici conservativi di formalizzabilità e documentazione tecnica di unità/tipo/aggregazione; dove non certificabile => dichiarare not_formalizable.
- [ ] Regole del mapping alias per lo scorer offline fissate senza vedere le predizioni; denominatori per provider errors e astensioni.
- [ ] Evidenza che la partizione “1 discovery per classe” è stata approvata tramite audit GT isolato senza importare le etichette nel runtime.
- [ ] Scelta finale dell'arm dimostrativo di RQ2-C **prima** di consultare i 24 K; non scegliere a posteriori.
- [ ] Firma del release `RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json` create-only, SHA-256 pin nel codice, readback e test preflight; preservare `test_unlocked=false`.
- [ ] Conferma esplicita di quale stage discovery avviare come primo evento API e preflight offline completo, seguito da una singola invocazione autorizzata.

Il codice attuale mantiene `rq2_ck_provider_transport.RELEASE_SHA256=None` e `rq2_dryrun_plan.PLAN_STATUS=DRAFT_NOT_EXECUTABLE`: **non sbloccarli finché i gate non sono chiusi**. Non usare il release finto delle unit test come scientific freeze.

**Milestone tecnica attestata:** i 12 test di `test_rq2_discovery_d_provider_transport.py` sono passati in PyCharm: `Ran 12 tests in 1.011s — OK`. Tutte le suite D/C/K citate sono offline/sintetiche. Nessuna chiamata API RQ2 è stata ancora eseguita. **Consegna tesi: 1 dicembre 2026.**
