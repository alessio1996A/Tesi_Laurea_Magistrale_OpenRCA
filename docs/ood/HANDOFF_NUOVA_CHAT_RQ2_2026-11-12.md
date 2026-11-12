# HANDOFF BREVE — Tesi OpenRCA RQ1/RQ2 — 12 novembre 2026

**Scopo:** riprendere il lavoro in una nuova chat senza riaprire decisioni,
ripetere prove già verificate o perdere i risultati congelati. Questo
documento è una sintesi; il registro completo è
`docs/ood/CONTINUITA_RQ2_E_REGISTRO_DECISIONI_2026-11-11.md`
(sezioni finali 76–84), da leggere insieme alla preregistrazione.
**Non autorizza richieste LLM a pagamento.**

## Contesto, branch e calendario

- Repository: `alessio1996A/Tesi_Laurea_Magistrale_OpenRCA`.
- Branch sperimentale RQ2 attuale:
  `feature/ood-knowledge-transfer-audit-2026-11-10`;
  leggere sempre il **commit HEAD corrente** da GitHub, senza
  presumere che il commit menzionato in una chat precedente sia
  quello definitivo.
- Laurea magistrale Ingegneria Informatica, Università di Catania;
  **consegna tesi 1 dicembre 2026**.
- Il relatore ha escluso l'implementazione di human-in-the-loop
  diagnostico. Claim con audit manuale dei crash != human-in-loop RCA.
- Modalità di lavoro: assistente modifica su GitHub, utente
  `git pull` in PyCharm e invia test, poi un'unica cella Colab
  quando serve una verifica runtime o esperimento esplicitamente
  autorizzato. Niente API a pagamento senza consenso specifico.

## RQ1 CONCLUSA E FROZEN

- 5 harness `A0`, `A1`, `A1_8R`,
  `A1_8R_Planning`, `A1_PAVE`.
- 3 modelli: `gemini-3.5-flash-lite`,
  `claude-sonnet-5-5`, `claude-haiku-5-5`.
- Cohort Evaluation20: 20 incidenti × 5 harness × 3 modelli
  = **300 tentativi, 295 risultati completi, 5 errori provider
  Gemini**. Scoring Microsoft ufficiale, analisi pairwise e tradeoff
  token/accuracy già raccolti. Non rifare RQ1.
- Per Sonnet score medio ufficiale per harness
  A0 .1165, A1 .3960, A1_8R .4335,
  Planning .3665, PAVE .5040; non
  dichiarare che ogni configurazione migliori ogni modello.
- Commit protocollo RQ1:
  `e4845e7fe9a399e10dd2db6f320dfeaeeddf3379`.
  I **13 blob** RQ1 sono stati verificati invariati;
  `src/agent/model_factory.py` Git blob
  `05308d5740763db0444556dcb7330d8fb4c308ec`.

## RQ2 — FINALITÀ E PIANO NON ANCORA ESEGUITO

**Separare due conclusioni:** RQ2-A misura generalizzazione
diagnostica su classi OOD; RQ2-C richiede applicazione di
regole verificate e frozen per parlare di knowledge transfer
operativo. La correttezza delle diagnosi, da sola, non lo dimostra.

Quattro classi held-out dal gruppo di 15:
1. `node CPU spike`
2. `container write I/O load`
3. `container process termination`
4. `container packet loss`

Cohort selezionata in audit GT isolato e aggregato:
- **Discovery 4:** `cloudbed-1_q032`, `cloudbed-1_q050`,
  `cloudbed-2_q026`, `cloudbed-2_q045`.
- **Test OOD 11, ancora chiusi:** `cloudbed-1_q014`,
  `cloudbed-1_q021`, `cloudbed-1_q030`,
  `cloudbed-1_q059`, `cloudbed-2_q014`,
  `cloudbed-2_q021`, `cloudbed-2_q040`,
  `cloudbed-2_q041`, `cloudbed-2_q058`,
  `cloudbed-2_q076`, `cloudbed-2_q077`.
- 4 gruppi temporali discovery e 10 test; due query
  `cloudbed-1_q014/q030` condividono una finestra.
  Il gap cross-phase minimo osservato è 90 minuti;
  finestre distinte NON dimostrano iniezioni causalmente indipendenti.
- Modelli × harness: 3 × 2 (`A1`, `A1_8R`).
- D (diagnosis agent con tool RQ1), C (classificazione
  fault-type tool-free), K (candidata pseudoregola tool-free).
- 4 × 2 × 3 × (D,C,K) = **72 stage discovery**;
  11 × 2 × 3 × (D,C) = **132 stage test**;
  **204 stage totali**, NON 204 richieste API.
- RQ2-C ha arm dimostrativo proposto ex ante
  `A1_8R + claude-sonnet-5-5`; scelta definitiva
  ancora da firmare nel release.

## EVIDENZA TECNICA GIÀ SUPERATA — NON RIPETERE

- Preflight GT-free reale Colab su CSV originali: 4+11,
  4+10 gruppi, 204 stage, 13 blob RQ1; file
  `docs/ood/RQ2_PREFLIGHT_GT_FREE_REALE_VERIFICATO_2026-11-12.md`.
- Source audit Colab: `langchain-core 1.7.1`,
  `langgraph 1.2.18`, `langchain-google-genai 4.4.2`,
  `google-genai 2.34.0`, `langchain-anthropic 1.7.7`,
  `anthropic 2.6.0`. Quattro SHA sorgente annotati
  in `docs/ood/RQ2_PROVIDER_POLICY_SOURCE_AUDIT_2026-11-12.md`.
- Mock HTTP SDK LangChain completo **Colab VERDE**:
  `Ran 8 tests in 0.004s — OK`, quattro
  `model.invoke()` sincroni con risposte 503 **sintetiche**,
  per ciascun provider una richiesta tool-free e una con
  tool associati: **1 send HTTP finto per invocazione**,
  nessuna API reale. Non provati async/streaming né timeout
  fisico sotto stallo. Documentato in
  `docs/ood/RQ2_COLAB_FAKE_HTTP_INVOKE_2026-11-12.md`.
- Nuova factory `src/evaluation/rq2_model_factory.py`
  **solo RQ2**: Google `max_retries=1` (=1 tentativo
  complessivo nelle versioni pin), Claude
  `max_retries=0`, entrambi timeout *candidato*
  `300.0s` per richiesta; Claude `max_tokens=4096`.
  D inietta l'LLM nel runner RQ1 invariato
  con `run_experiment(config,llm=...)`; C/K
  usano la factory RQ2-only; nessuna modifica
  ai sorgenti originali RQ1.
- Unit test **reali PyCharm** superati:
  `test_rq2_model_factory.py` 10/10 (0.055s),
  `test_rq2_discovery_d_provider_transport.py` 12/12 (0.963s),
  `test_rq2_ck_provider_transport.py` 15/15 (8.137s),
  `test_rq2_fault_type_eval_policy.py` 16/16 (0.004s).
  Totale **53/53** delle ultime quattro suite.
  Tutte sono verifiche offline sintetiche, NON risultati RCA reali.

## SCORING/K — ancora scientificamente CANDIDATI

- `src/evaluation/rq2_fault_type_eval_policy.py`:
  normalizzazione **strettamente lessicale** delle 4
  classi ufficiali (case, spazi, punteggiatura,
  `IO` vs `I/O`); non aggiungere alias dopo
  vedere predizioni. `unmatched_diagnosis` è errata,
  non astensione. Metrica primaria: corretti/11 per
  ogni modello×harness, mantenendo errori, astensioni
  e missing nel denominatore; confronti appaiati
  A1 vs A1_8R. GT letto solo dal valutatore isolato,
  MAI esposto a C/K, tool o prompt.
- `src/evaluation/rq2_kpi_formalizability_preflight.py`
  cataloga 29 KPI noti nel *codice*, ma **non**
  certifica unità fisiche, tipo gauge/counter, presenza
  sulle finestre o aggregazioni. Un JSON K valido
  non è un detector eseguibile. Se non dimostrabile
  su documentazione e development GT-free autorizzato,
  marcare `requires_verification`/`not_formalizable`.
  Non eseguire pseudocodice LLM e non inventare
  soglie, semantiche o negativi. Zero K formalizzabili
  = esito negativo legittimo.

## DOCUMENTI DI LAVORO E NEXT ACTION

1. `docs/ood/RQ2_REVIEW_SCIENTIFICO_PRIMA_RELEASE_2026-11-12.md`:
   proposta completa da approvare ex ante; **NON firmata**.
2. `docs/ood/RQ2_DISCOVERY_PREREG_V1_CANDIDATE_2026-11-12.md`:
   elenco gate con checklist. Le scelte scientifiche
   residue includono partizione finale, alias scorer,
   regole K conservative, arm primario e policy timeout.
3. Dopo approvazione: preflight unico OFFLINE sul
   checkout Colab che eseguirà RQ2, acquisizione
   e pin SHA finali degli script/CSV/protocollo,
   review dei gate reali, release scientifico
   **create-only**, readback SHA.
4. **Non sbloccare ora**:
   `src/evaluation/rq2_ck_provider_transport.py`
   mantiene `RELEASE_SHA256=None` e
   `src/evaluation/rq2_dryrun_plan.py`
   mantiene `PLAN_STATUS="DRAFT_NOT_EXECUTABLE"`.
   Non ci sono ancora chiamate API RQ2 reali.
5. Dopo review, release e preflight, chiedere
   **autorizzazione esplicita a una singola D discovery**
   (caso, provider, harness) prima di consumare token
   o spendere denaro. Il test OOD resta precluso
   fino al freeze scientifico delle K.

## ACCORDO FINALE CON L'UTENTE

**Dopo gli esperimenti reali e freeze dei risultati**, e
**prima della stesura definitiva della tesi**, svolgere
una fase di **refactoring su nuovo branch post-freeze**:
migliorare leggibilità, commenti/docstring/spiegazioni
**in italiano**, verificare dipendenze e import,
inventariare le directory e rimuovere solo file
davvero superflui dopo aver controllato riferimenti.
NON cancellare artefatti necessari a riproducibilità,
protocolli, output congelati, log, claim e hash;
conservare i commit sperimentali originali e i
test di regressione. Poi procedere alla scrittura
definitiva della tesi. Consegna 1 dicembre;
non trasformare il refactoring in una riscrittura.

**Gestione chat:** l'utente desidera che l'assistente
suggerisca esplicitamente un passaggio a una nuova chat
quando la conversazione diventa ingombrante. In nuova
chat: prima leggere questo file e i documenti linkati
via **connettore GitHub**, poi controllare HEAD e
continuare SENZA ripetere l'intera analisi da zero.
Non assumere che la memoria del modello contenga
ogni riga di tutte le chat.
