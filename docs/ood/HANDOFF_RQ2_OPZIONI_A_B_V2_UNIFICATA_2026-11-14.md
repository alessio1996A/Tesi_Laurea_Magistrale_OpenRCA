# HANDOFF DI CONTINUITÀ — RQ2: Opzione A, Opzione B, V2 unificata

**Data:** 14 novembre 2026. **Tesi:** Harness Engineering per LLM applicati a Root Cause Analysis, Microsoft OpenRCA (Market), Università di Catania. **Consegna:** 1 dicembre 2026. **Incontro relatore:** martedì 17 novembre 2026.
**Decisione utente, vincolante per il prossimo lavoro:** procedere metodicamente e senza scorciatoie; usare **OPZIONE A PRIMA**, mantenendo **OPZIONE B COME FASE SUCCESSIVA**; sperimentare **tutti e cinque gli agenti e tutti e tre i LLM mediante UNA SOLA infrastruttura V2 comune**, non versioni separate per modello, non confondere readiness con campagne realmente eseguite.
**Nessun desiderio di accelerare a scapito della qualità**: l'obiettivo è prima garantire comparabilità e tracciabilità, poi valutare se avviare API.
**Branch di sviluppo attivo:** `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`, basato sul commit `c2bed47a9f61ac6ac67223c47a9b55e680d6f0ee`. Per il commit corrente leggere `git rev-parse HEAD`; non presumere che il SHA di questo handoff coincida con HEAD.
**Protocollo draft associato:** `docs/ood/RQ2_V2_UNIFIED_OPTION_A_PROTOCOL_DRAFT_2026-11-14.md`. Si tratta di **BOZZA NON ESEGUIBILE**: mancano orchestratore/release comune, integrazione E2E su tutte le varianti, test e autorizzazione API.

## 0. Quello che è stato davvero misurato

**RQ1 (domanda diagnostica):** campagna development su 8 casi, 5 agenti, 3 LLM per 120 run complessive, inclusi i 40 run Gemini iniziali; nuova coorte Evaluation20 di 20 incidenti × 5 agenti × 3 LLM = 300 tentativi, **295 completi e 5 errori Gemini**; scorer Microsoft offline e freeze preservati. Per Sonnet Evaluation20: score medio A0 0.1165, A1 0.3960, A1_8R 0.4335, A1_8R_Planning 0.3665, A1_PAVE 0.5040 (non affermare un miglioramento monotono).

**RQ2 V1 (domanda conoscenza):** 4 incidenti discovery × 2 harness `A1`, `A1_8R` × 3 LLM × 3 fasi D/C/K = 72 stage previsti; realmente archiviati **39/72**: Gemini 24/24 (22 complete, 1 invalid, 1 blocked), Sonnet 15/24, Haiku 0/24. Totale 28 complete, 4 invalid, 7 blocked; 32 tentativi provider. Errore metodologico di provenance V1 per alcune D Sonnet con chiamate parallele allo stesso tool e `tool_call_id` non conservato: esiti originari restano immutabili, NON attribuire diagnosi errate al modello.
**Gemini V1:** fra 8 K, 2 `candidate` (q026/A1, q045/A1), 5 `insufficient_evidence`, 1 `BLOCKED_DEPENDENCY`; 0 regole formalmente congelate/test-ready. Candidate q026: iowait+io.await finestre richieste 60s vs evidenze aggregate 400s/1800s; candidate q045: `service_log_warnings > 0` in 60s troppo generica per concludere DNS, maintenance/transport delay non verificati. Audit development q045 reale GT-free: 92 casi ammessi, 116 righe del servizio, 100 warning in 7 cloudbed×60s bucket; prova osservabilità non causalità o accuratezza.
**RQ2 V2 pilot già fatto:** Sonnet A1, caso discovery q050, D→C→K reale su ledger/source-bound V2 con provenance ID. K termina validamente con `insufficient_evidence`; il pilot **non** è una replica né una campagna factorial completa. Non ripeterlo alla cieca, non confrontarlo come se condividesse il futuro protocollo unificato.

**Classi:** in origine 15 classi di guasto, 11 studiate prima e **4 escluse** e tenute per RQ2. Sono quattro **classi**, NON quattro regole. Le pseudoregole K possono essere zero/una/più; non vi è apprendimento dei pesi del modello.

## 1. OPZIONE A — PRIORITARIA E DECISA DALL'UTENTE

**Domanda:** l'harnessing e il modello LLM modificano la propensione e la qualità della **conoscenza diagnostica candidata** estratta da evidenze, mantenendo un protocollo uniforme?

**Fattori esatti:**
- Harness: `A0`, `A1`, `A1_8R`, `A1_8R_Planning`, `A1_PAVE`.
- Modelli: `gemini-3.5-flash-lite`, `claude-sonnet-5-5`, `claude-haiku-5-5`.
- Casi `discovery` originali: `cloudbed-1_q032`, `cloudbed-1_q050`, `cloudbed-2_q026`, `cloudbed-2_q045`.
- **60 combinazioni caso × harness × modello**, tre stage logici D/C/K ciascuna = **180 stage logici pianificati** (60 D, 60 C, 60 K). Non sono 180 HTTP: ogni D può usare molte chiamate; C/K una chiamata ciascuno solo se dipendenze valide; fallimenti e blocchi rimangono nel denominatore.

**Workflow comune:** D raccoglie telemetria/tool observations senza GT → C produce `diagnosis` o `abstain` dalla istruzione originale e dalle sole evidenze D → K propone una pseudoregola `candidate` oppure `insufficient_evidence`. Non correggere JSON a posteriori, non eseguire il pseudocodice LLM, non trattare la causa C come GT.
**Comparabilità:** stesso caso, stesso modello per confronti di harness; stesso caso/harness per confronti fra provider. I cinque agenti conservano le loro differenze intenzionali di preprocessing/rules/planning. Prompt C/K e validatori, tool, max 6 round D, schema task-aware, gestione di errore, budget e misure sono comuni. Planning/PAVE utilizzano **4+2**; ReAct A0/A1/A1_8R usano i 6 round complessivi. Non integrare 5+1 in questa matrice.
**Output:** rate di K candidate sui pianificati, validità JSON e grounding E###, possibilità reale di formalizzazione (metriche/unità/finestra/aggregazione/condizioni/abstain), controesempi e falsificabilità, astensioni/errori, token, numero di requests, tempo e stima costo. Non ottimizzare le metriche una volta letti gli output. Non definire 'migliore' il modello con più candidate senza specificità/validità.
**Cosa A NON dimostra:** accuratezza causale, affidabilità di regole operative, recall/precision su fault nuovi, trasferimento/generalizzazione. Con quattro incidenti evitare conclusioni statistiche forti e pseudorepliche.

## 2. OPZIONE B — SUCCESSIVA E NON ANCORA AUTORIZZATA

**Domanda:** una regola candidata, prodotta e poi formalizzata/frozen SENZA guardare i test, riconosce realmente nuovi incidenti dello stesso tipo e distingue controesempi o fault alternativi?
Prerequisiti: Opzione A completata; almeno una K formalizzabile con segnali verificati, unità/finestre/aggregazioni, falsi positivi e astensione operazionalizzabili, sorgenti non contaminate; scorer e normalizzazione fissati prima di test; necessario valutare l'opportunità di **più incidenti indipendenti per classe** in una nuova coorte. Se nessuna K passa i criteri, B si arresta e il risultato è `non verificabile`, NON 'generalizzazione fallita'.
**11 casi test OOD ATTUALMENTE LOCKED**: `cloudbed-1_q014`, `cloudbed-1_q021`, `cloudbed-1_q030`, `cloudbed-1_q059`, `cloudbed-2_q014`, `cloudbed-2_q021`, `cloudbed-2_q040`, `cloudbed-2_q041`, `cloudbed-2_q058`, `cloudbed-2_q076`, `cloudbed-2_q077`. Sono solo **10 gruppi temporali test indipendenti a livello di finestra**: q014 e q030 di cloudbed-1 condividono una finestra.
Per B: protocollo separato e preregistrato, congelamento della regola e del codice prima di valutare i test; eventuale nuovo dataset o coorte indipendente, scoring isolato GT-only post-run, denominatori, TP/FP/TN/FN, coverage, abstain, accuratezza per fault e intervalli di incertezza per gruppi. **Non usare gli 11 OOD per modificare prompt, scegliere soglie o ampliare discovery**; nessun human-in-the-loop implementato (solo eventuale discussione finale).

## 3. REGOLA D'ORO — UNA V2 COMUNE, NON UN'ALTRA V1→V2 A METÀ CAMPAGNA

**Rischio riconosciuto dall'utente:** nella V1 le D Sonnet erano invalide per la perdita dell'associazione tool_call/result. Non dichiarare che la nuova V2 e' affidabile soltanto perché 25 test unitari, una D A1 Sonnet o un pilot singolo risultano validi. Non promettere zero problemi API in assoluto: gli errori sono eventi ammessi dal protocollo.

**Cosa riutilizzare SENZA riscrivere gli agenti:** `evaluation.experiment_runner.run_experiment`, `ExperimentConfig`, `agent.rq2_v2_graph_engine.esegui_grafo_rca_v2` per A0/A1/A1_8R; `agent.verify_graph.esegui_grafo_rca_verify` per A1_8R_Planning/A1_PAVE (gia' conserva gli ID con origine `llm`/`planner`); `rq2_evidence_bundle`, `rq2_probe_adapter`, `rq2_output_contracts`, `rq2_model_factory`; i moduli di storage scientifico Sonnet V2 sono **specifici del pilot e non sono direttamente il ledger comune**.
**Non confondere** validità JSON, correct tool-id pairing, coverage K e diagnosi corretta. Una K con `insufficient_evidence` è un risultato informativo e non si ritenta per forzare un candidato.

### Gate sequenziali e condizioni GO/NO-GO

- **G1 — offline plan e unit test:** piano delle 180 stage, tutti i 5 harness e 3 model IDs, isolata la discovery, nessun test, nessun API, parser/identità D. Nuovi file `src/evaluation/rq2_v2_unified_discovery_plan.py` e `src/evaluation/rq2_v2_unified_provenance_gate.py` e `src/tests/test_rq2_v2_unified_discovery_offline.py`. **25 test scritti, NON ancora dichiarati superati**: servono output utente PyCharm.
- **G2 — vero fake end-to-end:** eseguire **tutti i 5 harness × 3 modelli** con fake LLM/tool e non con una sola funzione isolata. Verificare ReAct e planner, doppie chiamate same-name con ID diversi anche invertendo ordine risposte, output C/K content-block per Anthropic, id/prompt/accoppiamento sorgente, timeouts, error handling, JSON invalid, `abstain`, `insufficient_evidence`, K `BLOCKED_DEPENDENCY`, metering dei token, budget 6 round 4+2, no GT e no API.
- **G3 — dispatcher/ledger D-C-K comune**: stage create-only, identità stabile case/model/harness/version, single claim PRIMA di qualunque call, SHA/hash di source/prompt/runtime, readback verificato, no retry non tracciato, namespace disgiunto dai V1/pilot e risultati RQ1, 15 arm; prove di riavvio e crash, processi duplicati e claim unresolved, error receipts/provider failures.
- **G4 — protocollo/release scientificamente congelati**: fissare SHA commit, prompt, data split/manifest, versions SDK/API behavior, policy timeout/retry e quote, metriche/denominatori, inclusione/astensione; preflight Colab GT-free; autorizzazione esplicita dell'utente a ogni blocco API pagate; nessun pilot casuale di rete/discovery fuori protocollo.
- **G5 — campagna Opzione A reale**: eseguire i 60 D e i C/K dipendenti in ordine create-only, rispettando fail-closed, ogni errore come risultato, verificare archivi, produrre tabelle comparative e limiti; in nessun caso aprire test OOD per orientare le scelte.
- **G6 — Opzione B SOLO DOPO**: decidere nuova coorte/tenuta statistica e verifiche independent prefreeze; OOD test sbloccabili soltanto se formalizzazione scientifica pronta.

**Criterio per non generare una 'V3' durante gli esperimenti:** separare correzioni infrastrutturali da cambiamenti scientifici. In sviluppo si possono correggere bug con nuovi commit verificati, PRIMA del freeze; dopo la release qualunque cambiamento comportamentale a prompt/runner/provenance/metriche impone stop, valutazione di comparabilità e nuova release/campagna esplicita, senza sovrascrivere i record precedenti. L'obiettivo e' evitare nuova iterazione del protocollo, non falsificare un risultato bloccato per evitare una versione.

## 4. Stato preciso e prossimo comando

Commit sorgente del nuovo branch prima di questo handoff: `ee609858156f5deb31016eb2cc89a9c2fe2a446a`.
File già aggiunti su branch: `src/evaluation/rq2_v2_unified_discovery_plan.py`, `src/evaluation/rq2_v2_unified_provenance_gate.py`, `src/tests/test_rq2_v2_unified_discovery_offline.py`, `docs/ood/RQ2_V2_UNIFIED_OPTION_A_PROTOCOL_DRAFT_2026-11-14.md`.
**Prossimo passo concreto:** chiedere all'utente output PyCharm `python -m unittest discover -s src/tests -p "test_rq2_v2_unified_discovery_offline.py" -v` (25 test attesi); non dichiarare `OK` finché l'utente non manda output. Poi progettare G2 fake end-to-end su un nuovo commit/branch, senza API.
**Nessuna esecuzione effettiva della nuova matrice unificata** al 14 novembre: 180 = numero pianificato, non esecuzioni completate.

## 5. Future chat — promemoria da incollare

> Sto proseguendo la tesi magistrale OpenRCA Harness Engineering. Leggi INTEGRALMENTE questo handoff GitHub `docs/ood/HANDOFF_RQ2_OPZIONI_A_B_V2_UNIFICATA_2026-11-14.md` sul branch `feature/rq2-v2-unified-five-harness-three-models-2026-11-14` e il protocollo associato. Opzione A è la priorità: RQ2-V2 unificata per 5 harness × 3 LLM, 4 discovery, D-C-K, 180 stage pianificati, **senza generalizzazione e senza API finché non superati i gate**. Opzione B è successiva: validazione e test OOD di regole frozen, 11 test locked, eventuale nuova coorte indipendente. RQ1 frozen; RQ2 V1 39/72 stage storici e pilot Sonnet V2 preservati. Non riscrivere agenti originali né fare retry non tracciati. Procedi dai 25 test PyCharm del nuovo branch, poi G2 fake full-matrix. Confronti devono essere scientificamente equi, dati GT-free, commenti/refactoring in italiano al termine.

## 6. Avanzamento G1/G2 — 14 novembre 2026, aggiornamento della chat

**Nuova evidenza fornita dall'utente:** `Ran 25 tests in 0.277s; OK` per
`src/tests/test_rq2_v2_unified_discovery_offline.py`. **G1 PASS 25/25**,
piano delle 180 stage ed audit statico di provenance. Questo NON e' un
test E2E di 15 provider/harness e NON autorizza API.

**G2 codice scritto, ma test ancora da eseguire dall'utente:**
`src/tests/test_rq2_v2_unified_graph_fake_e2e.py`, **9 test method**
(compreso uno che percorre **15 combinazioni** harness×modello con
`run_experiment` e reali grafi LangGraph). Il `prepara_esperimento`
e' sostituito in modo controllato con dati sintetici; i tool sono
realmente eseguiti in ToolNode, ma rispondono da fixture e non leggono
Market/GT. La selezione del motore ReAct V2 avviene con patch in RAM;
Planning/PAVE usano il loro esecutore autentico e le verifiche
deterministiche. C e K usano gli **adapter e parser reali** con risposte
di un LLM FAKE tool-free, non i dispatcher pagati.
Test esercitano stesso-name parallel tool IDs, planner origin,
content blocks Anthropic, `abstain`, `insufficient_evidence`,
C invalida/ID E999 blocca K, task-aware D output invalido non riparato,
nessun file/GT/API reale. Il risultato positivo non proverebbe il
comportamento dei provider remoti né il ledger comune production G3.

**Prossimo test mirato:**
```powershell
git status --short
git fetch origin feature/rq2-v2-unified-five-harness-three-models-2026-11-14
git switch feature/rq2-v2-unified-five-harness-three-models-2026-11-14
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_graph_fake_e2e.py" -v
```
Attesi **9 test** (con una suite a 15 subtest), ma **NON dire PASS** prima
di leggere l'output effettivo. Se fallisce, distinguere un difetto del
fixture da un problema di compatibilita' del grafo e correggere su commit
tracciato, senza modificare la RQ1 congelata.

## 7. Avanzamento G2 PASS e G3A codice (14 novembre 2026, seconda verifica)

**Output PyCharm utente verificato:** `Ran 9 tests in 0.455s; OK` per
`src/tests/test_rq2_v2_unified_graph_fake_e2e.py`. G2 PASS per la suite
synthetic real-LangGraph: un test percorre 5 harness × 3 provider labels
(15 arm) e le altre prove coprono pairing tool IDs, planner, C/K fixture,
invalid output e astensioni. Non prova trasporto reale SDK/API né qualità
del knowledge transfer.

**G3A nuovo codice non ancora testato:** `src/evaluation/rq2_v2_unified_synthetic_journal.py`
e `src/tests/test_rq2_v2_unified_synthetic_journal.py` (19 test method).
È un journal create-only **per fixture** di una nuova release V2 unificata,
NON uno store live; riusa il guard di synthetic-only data root e non
possiede un dispatcher provider. Copre le 15 combinazioni D/C/K, con
claim O_EXCL, SHA su piano/stage/parents, blocked without claim, K astensione,
record invalid preservati, orphan claim e nessun auto-retry. Il G3B production
release/source-bound e l'E2E fake-runner→journal unificato ancora mancano.

**Prossimo comando PyCharm:**
```powershell
git status --short
git fetch origin feature/rq2-v2-unified-five-harness-three-models-2026-11-14
git switch feature/rq2-v2-unified-five-harness-three-models-2026-11-14
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_synthetic_journal.py" -v
```
Attesi 19; non dichiarare superati senza esito utente.
Per dettagli e limiti vedi
`docs/ood/RQ2_V2_UNIFIED_G2_PASS_G3_SYNTHETIC_LEDGER_GATE_2026-11-14.md`.

**NOTA DI CONTINUITÀ:** l'Opzione A e' in corso (nessuna nuova run provider
della matrice unificata), l'Opzione B resta successiva con tutti gli
11 test OOD bloccati. Non scambiare 180 stage pianificati per output reali,
né 9 test G2 per 15 esperimenti pagati.
