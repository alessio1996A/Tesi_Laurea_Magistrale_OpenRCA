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

## 8. G3A — esito Windows non-PASS, fixture corretta (14 novembre)

Output PyCharm test G3A originale:
```text
Ran 19 tests in 121.164s
FAILED (failures=1, errors=6)
```
Sei errori nel test dei 15 arm: Planning e PAVE per tutti e tre i modelli;
il FAIL `27 != 45` è derivato dai sei arm mancanti. Diagnosi verificata
tramite codice: `fake_run` ometteva `origine`, obbligatoria per i due
harness con planner. **Nessun problema dimostrato nei grafi reali o nei
provider**. Corretto **solo il test** aggiungendo `"origine":"llm"`
per Planning e PAVE e un test negativo fail-closed che rifiuta origin
missing. File `src/tests/test_rq2_v2_unified_synthetic_journal.py`,
**nuova suite 20 test NON ancora eseguita dall'utente**. I gate G1 e G2
restano validi.

Documento completo:
`docs/ood/RQ2_V2_UNIFIED_G3A_WINDOWS_FIXTURE_ORIGIN_FAILURE_2026-11-14.md`.

**Attenzione alle prestazioni:** 121.164 secondi sul journal sintetico sono
troppi. Le verifiche integrali `audit_restart` per ogni stage potrebbero
essere costose; profilare/ottimizzare dopo aver ristabilito la correttezza,
senza allentare l'integrita' o il no-retry.

**Prossimo comando:**
```powershell
git status --short
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_synthetic_journal.py" -v
```
Attesi `Ran 20 tests` e `OK`, non ancora attestati. Nessuna API/GT/OOD
e nessuna autorizzazione per G4 o G5.

## 9. G3A 20/20 PASS e profiling delle performance (14 novembre)

Output autentico PyCharm utente: `Ran 20 tests in 250.763s; OK`.
Il fix fixture `origine="llm"` per Planning/PAVE è quindi passato, incluso
il test negativo che rifiuta la stessa traiettoria senza origine. **G3A
correttezza PASS**. Precedenti: G1 25/25 PASS; G2 9/9 PASS. Non attribuire
il test G3A a run reali, provider API o test OOD. **G3B** orchestratore
fake runner→journal unificato non ancora realizzato.

Criticità: 250.763s per suite synthetic (costo operativo eccessivo).
Ipotesi da verificare con cProfile: `audit_restart` invocato prima
di ogni claim/record, con ricariche ricorsive di parent e SHA.
Documentazione:
`docs/ood/RQ2_V2_UNIFIED_G3A_20_PASS_PERFORMANCE_PROFILE_2026-11-14.md`.

Nuovo profiler source-free, non eseguito:
`src/tests/profile_rq2_v2_unified_journal_offline.py`.
**Comando PyCharm:**
```powershell
git status --short
git pull --ff-only
$env:PYTHONPATH = "src"
python -B src/tests/profile_rq2_v2_unified_journal_offline.py
```
Crea 15 stage sintetici in TemporaryDirectory, stampa tempi e 22 hot spots.
Non sostituisce i controlli, non chiama API e non accede ai dati reali.
Dopo output, correggere efficienza solo con prova di equivalenza
integrale, no bypass O_EXCL/sha/orphan/race. Opzione B ancora sospesa.

## 10. Profiler Windows confermato, ottimizzazione G3A in attesa dei test

Output autentico profiler sintetico utente (stessa macchina Windows):
`STATUS: OFFLINE_PROFILE_INTEGRITY_OK`, 15/15 records,
`PROFILE_TOTAL_SEC: 31.956`, `ALL_STAGES_SEC: 29.887`,
`FINAL_AUDIT_SEC: 2.067`, 31 invocazioni
`audit_restart` (30.085s cumulativi), 213431 invocazioni `stat`
(24.280s cumulativi), 5676 chiamate `_paths` (23.710s cumulativi).
Non sommare tempi cumulativi sovrapposti.

Modifica **solo** journal sintetico unificato: memoizzazione limitata a
ogni singolo audit (dopo verifica SHA/parent/claim/provenance) e guardia
di namespace prima della scansione, senza memo persistente, senza
modificare D/C/K/RQ1/API. Aggiunti 3 nuovi test di anti-regressione
(read bound, corruption after successful audit, claim tampering).
Suite G3A ora **23 test da eseguire**, NON ancora PASS.
Documento specifico:
`docs/ood/RQ2_V2_UNIFIED_G3A_PROFILER_REAL_RESULTS_AND_LOCAL_AUDIT_MEMO_2026-11-14.md`.

**Prossimi comandi PyCharm**, repository su branch unificato e
`git status --short` vuoto:
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_synthetic_journal.py" -v
python -B src/tests/profile_rq2_v2_unified_journal_offline.py
```
Confrontare la nuova misura contro i 31.956s originali e
`Ran 23 tests ... OK`, senza inventare speedup prima dell'output.
G3B fake runner→journal e G4/G5 release/API ancora bloccati.

## 11. G3A performance PASS, G3B runner→journal integrato fake (14 novembre)

**Output reale utente:** `Ran 23 tests in 20.434s; OK`.
Il profiler Windows sintetico identico a prima mostra
`STATUS: OFFLINE_PROFILE_INTEGRITY_OK`,
`PROFILE_TOTAL_SEC: 3.546` (prima 31.956s),
`FINAL_AUDIT_SEC: 0.096` (prima 2.067s),
`Path.stat: 17219` (prima 213431), 15 claim/record, 0 orfani.
La scansione con cache temporanea locale è quindi confermata nei test
G3A; controlli di corruzione e no-retry restano PASS.
**Non** assumere che questo misuri la scalabilità a 180 stage o race
multi-processo.

**Nuovo codice G3B, test NON ancora eseguito:** 
`src/tests/test_rq2_v2_unified_runner_to_journal_fake_e2e.py`
(9 metodi unittest; uno attraversa 15 arm × D/C/K, fino a 45 stage
archiviati). Usa `run_experiment` + LangGraph veri con fake LLM/tool,
C/K adapters veri, content blocks Claude fake, claim pre-run,
journal create-only unificato, invalid D/C/K, astensioni, provider error
simulato e orphan claim no retry. **Il test simula l'orchestrazione,
NON è il dispatcher live**. Nessun Market, GT, API, OOD o Drive.

Documento aggiornamento:
`docs/ood/RQ2_V2_UNIFIED_G3A_PROFILE_PASS_G3B_RUNNER_JOURNAL_FAKE_GATE_2026-11-14.md`.

**Prossimo comando PyCharm:**
```powershell
git status --short
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_runner_to_journal_fake_e2e.py" -v
```
Attesi `Ran 9 tests` e `OK`, non ancora attestati.
Se G3B passa, il successivo passo e' sviluppare uno solo dispatcher
source-bound (nuovo codice/release separate dai dati frozen), con
concorrenza, error accounting, dry-run Colab e policy spesa prefreeze.
Opzione B sempre riservata; 11 OOD test locked.

## 12. G3B PASS; G4A source-bound offline predisposto (14 novembre)

**Output PyCharm fornito dall'utente:** `Ran 9 tests in 23.395s; OK` 
per `src/tests/test_rq2_v2_unified_runner_to_journal_fake_e2e.py`.
Questa suite ha superato le 15 combinazioni di agenti/modelli nel test
centrale e 45 stadi D/C/K **sintetici** registrati con il journal comune.
**G3B integrazione FAKE PASS**, non una campagna su provider remoti.
Complessivamente G1 25, G2 9, G3A 23, G3B 9 metodi unittest superati
nelle rispettive suite; non rappresentano incidenti reali.

**Nuovo sottogate G4A:** creati
`src/evaluation/rq2_v2_unified_release_preflight.py` e
`src/tests/test_rq2_v2_unified_release_preflight_offline.py` (18 test
scritti, **NON ancora eseguiti**). Validano parita' dei 5 harness/3 model
IDs/4 discovery, SHA split+manifest GT-free, sorgenti RQ1 frozen,
impronte delle sorgenti V2, prompt C/K, contratto D e flag OOD LOCKED.
Anche un report pienamente verificato resta `NO_RELEASE_NO_API`, senza
ledger production, dispatcher/SDK, budget approvato o release scientifica.
Lo store synthetic-only **NON** viene promosso a ledger live.

Documento:
`docs/ood/RQ2_V2_UNIFIED_G3B_PASS_G4A_SOURCE_BOUND_OFFLINE_GATE_2026-11-14.md`.

**Prossimi comandi PyCharm** (controllare prima che git status sia vuoto):
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_release_preflight_offline.py" -v
```
Attesi 18 test e `OK`, non ancora attestati. 
Poi proseguire con G4B: un solo journal/dispatcher scientifico comune,
source-bound e con quote API, provato prima con fake LLM sull'intera
matrice; non confondere G4A con autorizzazione API. Opzione B non avviata,
11 casi test OOD intatti.

## 13. G4A PASS e G4B blueprint proposto (14 novembre, 18:44 Europe/Rome)

**Output utente G4A:** `Ran 18 tests in 0.353s; OK`.
Questo conferma la suite con **source preview mockata**, non una lettura
reale del manifest/split tramite G4A. Totali G1 25, G2 9, G3A 23,
G3B 9, G4A 18 = **84 metodi PASS** su cinque suite, senza API.
I dataset frozen e i test OOD restano intatti.

Nuovi file:
`src/evaluation/rq2_v2_unified_release_blueprint.py`,
`src/tests/test_rq2_v2_unified_release_blueprint_offline.py`
(**18 unit test SCRITTI, da eseguire in PyCharm**). Generano
descrizione non eseguibile degli **180 stage** con stessa provenienza,
i cinque agenti, tre modelli e quattro discovery. Ogni modello
ha 20 D + 20 C + 20 K; le 5 varianti condividono la stessa policy
C/K, D conserva la propria architettura e budget 6 round,
planning 4+2. Invocazioni logiche massime candidate:
ReAct D 7, Planning D 5, C/K 1 a stage, somma upper bound logico
**492**, NON cap HTTP o USD. Remote retries/timeout sono ancora
incerti (factory Google candidate passa `max_retries=1`).
Nessuna credenziale, SDK o Market letto, niente store scientifico.

**Distinzione necessaria:** la vecchia funzione
`rq2_budget_preflight.estimate_campaign_cost` presume la coorte RQ2
V1 (30/30/8 stage per modello), non può essere applicata alla Opzione A
5-harness. Per questa usare i conteggi 20/20/20 per modello.

Documento:
`docs/ood/RQ2_V2_UNIFIED_G4A_PASS_G4B_BLUEPRINT_180_STAGE_GATE_2026-11-14.md`.

**Prossimo comando PyCharm, status clean:**
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_release_blueprint_offline.py" -v
```
Attesi 18 PASS, **non ancora attestati**. Successivamente
verifica GT-free G4A su CSV veri e realizzazione ledger/dispatcher
source-bound scientifici con blocchi, fake regression e controllo
no-retry/concorrenza. G4B NON è una release e non permette API.

## 14. G4B PASS; prossima prova Colab GT-free unificata (14 novembre)

**Output PyCharm G4B utente:** `Ran 18 tests in 0.485s; OK`.
Le sei suite G1 (25) + G2 (9) + G3A (23) + G3B (9) + G4A (18)
+ G4B (18) sono **102 metodi di unittest PASS**. G4B usa
`fake_verified_g4a()`, quindi non significa che il nuovo protocollo
abbia già letto i CSV reali split/manifest.

La verifica successiva e' il preflight **Colab reale, read-only,
GT-free** già predisposto in:
`docs/ood/RQ2_V2_UNIFIED_G4B_PASS_COLAB_GT_FREE_SOURCE_READONLY_2026-11-14.md`.
Il documento contiene **una sola cella Colab** completa e pronta, senza
dipendenze pip né SDK: monta Drive, verifica i due CSV congelati,
clona/fetch branch unificato in checkout Colab **separato** e pulito,
esegue `preview_unified_source_bound` e
`build_unified_release_blueprint` in subprocess `PYTHONPATH=src`.
Output atteso: `RQ2_V2_UNIFIED_REAL_GT_FREE_SOURCE_PREFLIGHT_OK_NO_API`,
hash source plan e blueprint, SHA manifest/split, 4 discovery,
11 test OOD locked, 60 D+60 C+60 K. NON legge Market.zip/GT/scorer,
NON chiama LLM, NON scrive su Drive e NON apre test OOD come osservazioni.
**Non dichiarare PASS prima dell'output Colab reale**.

I 102 test PASS sono risultato di verifiche sintetiche; non sono
102 run su incidenti OpenRCA. Nessuna campagna reale Option A eseguita,
nessuna release scientifica firmata né ledger/dispatcher live comune;
Opzione B ancora sospesa. Dopo la verifica dei CSV reali costruire
ledger/dispatcher scientifici source-bound, prove provider fake e
guard di budget / no retry, quindi chiedere consenso esplicito API.

## 15. G4C Colab terminale OK (JSON omesso) e G4D ledger preflight draft — 14 novembre 2026

Utente ha riportato dopo cella Colab GT-free:
```text
FOUND: data/processed/split_market_v1.csv
FOUND: data/processed/benchmark_inputs_market.csv
CODE_COMMIT: 33d5d8b28494d5bf41168d0a709854aa3134ea6a
=== 3/3: RQ2 V2 UNIFIED SOURCE GATE — NO API ===
G4 REAL GT-FREE SOURCE PREFLIGHT: TERMINATO (0 API)
```
L'originale cella usa `subprocess.run(check=True)`, e la stampa della
riga finale mostra che non e' emerso un errore di processo. **Manca
tuttavia il JSON atteso**, che documenterebbe hash split/manifest, prompt
C/K e blueprint, per cui non dichiarare gli hash G4C certificati
dall'output incollato. Volendo recuperare il report senza clone né
alcuna API, nella stessa sessione Colab e dopo aver eseguito la cella
originale, rieseguire solo:
```python
subprocess.run([sys.executable, "-B", "-c", code],
               cwd=REPO, env=env, check=True)
```
Dovrebbe stampare integralmente il JSON. Nessun Market.zip, scorer o
credenziale LLM coinvolti. Non ripristinare vecchi protocolli per
aggirare il controllo.

**G4D implementato SOLO come GUARD DI LETTURA, non ledger live:**
`src/evaluation/rq2_v2_unified_scientific_ledger_preflight.py`;
`src/tests/test_rq2_v2_unified_scientific_ledger_preflight_offline.py`
con **19 unittest SCRITTI, in attesa dell'output PyCharm**. Namespace
scientifico proposto `data/rq2_v2_unified_scientific_v1`, assente
allo stato attuale. La guardia richiede commit Git **pin esterno** e
checkout clean, file sorgenti/source SHA e blueprint, GT-free e OOD
locked; rifiuta directory preoccupate, symlink e campi che autorizzano
API. Non crea release, claim, file, token, client o API.

Documento di stato:
`docs/ood/RQ2_V2_UNIFIED_G4C_COLAB_EXIT_G4D_SCIENTIFIC_LEDGER_PREFLIGHT_2026-11-14.md`.

**Comando PyCharm G4D (git status clean):**
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_scientific_ledger_preflight_offline.py" -v
```
Attesi 19, non ancora PASS. Vecchi 102 test PASS. Nessun nuovo
esperimento pagato e 11 OOD test rimangono locked.

## 16. G4C returncode0, G4D 17 PASS 2 SKIP e G4E release-contract pending — 14 novembre

Nuovi output concreti:
`CompletedProcess(... returncode=0)` in Colab eseguendo lo script
GT-free `preview_unified_source_bound`→`build_unified_release_blueprint`
sul checkout `33d5d8...`; gli assert su 180 stage, 492 invoke graph e
blocchi API/OOD sono stati completati. **JSON con valori SHA omesso
dal testo condiviso**, da acquisire con `capture_output=True` (vedi
documento G4E sotto).

PyCharm G4D:
`Ran 19 tests in 0.485s; OK (skipped=2)`.
**17 test effettivamente PASS**, due verifiche symlink Windows non
eseguite; non dichiarare 19 PASS. La guardia scientific namespace è
ancora read-only, non un ledger.

**G4E nuovo codice**: 
`src/evaluation/rq2_v2_unified_scientific_release_contract.py`
e
`src/tests/test_rq2_v2_unified_scientific_release_contract_offline.py`
(**18 test da eseguire**). Verificatore puro di FUTURA release
source/blueprint-bound e hash release/commit esterno, con budget
e approvazione esplicita, flag retry/timeout/meter/single-writer
obbligatori, 11 test locked. Anche quando restituisce OK
`can_create_scientific_claim=False`,
`can_execute_api=False`, `production_ledger_implemented=False`.
Le approvazioni negli UNITTEST sono **INVENTATE**: non autorizzano la
campagna reale; il modulo non apre file, firma release o usa API.
Non sostituisce l'implementazione successiva del ledger create-only
e del dispatcher unico.

Documento:
`docs/ood/RQ2_V2_UNIFIED_G4E_RELEASE_CONTRACT_GATE_2026-11-14.md`.

**Prossimo comando PyCharm, git status pulito:**
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_scientific_release_contract_offline.py" -v
```
Attesi 18, non attestati. G1+G2+G3A+G3B+G4A+G4B 102
PASS, G4D 17 PASS+2 skipped, G4E 18 pending. Fase Option A
non ha nuovi run pagati; Opzione B e test OOD ancora chiusi.

## 17. G4C JSON reale e G4E 18/18 PASS; G4F ledger create-only — 14 novembre

**Nuova evidenza utente:**
`Ran 18 tests in 0.651s; OK` (G4E, release contract offline).
Ricevuto anche **JSON Colab G4C completo**, riferito a checkout
`33d5d8b28494d5bf41168d0a709854aa3134ea6a`, con
`status=RQ2_V2_UNIFIED_REAL_GT_FREE_SOURCE_PREFLIGHT_OK_NO_API`:
- source plan SHA256:
`e6f797c4ca01ed422b80e928854469b9f8c7f7cc4215835bf91f9f7305425a00`;
- blueprint SHA256:
`a2874e9771eb50899afd15d55cecf239493f44077e16e937b5276f8a07e8fb61`;
- split `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`;
- manifest `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`;
- C prompt SHA `81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42`;
- K prompt SHA `0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71`.
4 discovery, 11 OOD locked, 5 harness, 3 modelli, 60/60/60
D/C/K = 180 stage. 492 invoke massime candidate NON richieste HTTP
garantite. API 0, nessuna release frozen.
Report completo:
`docs/ood/RQ2_V2_UNIFIED_G4C_G4E_VERIFIED_SHA_REPORT_2026-11-14.md`.

**Nuovo G4F: vero ledger scientifico create-only in CODICE, ancora
NON VALIDATO DALL'UTENTE**:
`src/evaluation/rq2_v2_unified_scientific_ledger.py`
+ `src/tests/test_rq2_v2_unified_scientific_ledger_offline.py`
(**22 test da eseguire**). Richiede release scientifica preesistente
SHA approvato esternamente e Git commit esatto clean, ripete
source-bound GT-free e blueprint, isola namespace scientifico,
scrive claim/record O_EXCL+fsync+readback, verifica stage D/C/K e
provenance, parent SHA, meter usage/costo e no-retry. Ha un
lock OS per singola operazione da testare sul filesystem reale Drive
prima del freeze. **Nessun LLM/API nel modulo**.
La release e il pin presenti nei test sono **FAKE** e restano dentro
TemporaryDirectory: non si è creato alcun claim scientifico vero.
Non usare questo ledger su Drive fino all'avvenuta verifica completa
e al freeze del codice/approvazione. La vera release non esiste.

Dettagli:
`docs/ood/RQ2_V2_UNIFIED_G4F_REAL_LEDGER_IMPLEMENTED_NO_API_GATE_2026-11-14.md`.

**Prossimi comandi PyCharm** dopo `git status --short` pulito:
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_scientific_ledger_offline.py" -v
```
Attesi 22 test, non attestati. Poi **un solo dispatcher D/C/K**
con fake SDK + prove error/metering e lockdown provider; non avviare
API reali, non sbloccare OOD. Infine freeze e pilot esplicitamente
autorizzato. Non confondere i precedenti test offline con run reali.

## 18. G4F 22 PASS e G4G fake-only dispatcher su ledger scientifico (14 novembre 2026)

**Esito reale utente PyCharm:** `Ran 22 tests in 22.053s; OK`
per `src/tests/test_rq2_v2_unified_scientific_ledger_offline.py`.
G4F **PASS su TemporaryDirectory con release fittizia**, inclusi
O_EXCL claim/record, SHA parent, readback, errori, astensione, no
auto-retry e lock OS locale. Non prova un lock efficace su Drive/FUSE,
né una release approvata, né la disponibilità remota degli LLM.

**Nuovo G4G aggiunto**, NON ancora testato:
`src/evaluation/rq2_v2_unified_dispatcher_offline.py`
`src/tests/test_rq2_v2_unified_dispatcher_offline_e2e.py`
(**17 metodi unittest da lanciare**). Test centrale: tutti i 15 arm
su un caso fittizio × D/C/K = 45 record nel ledger **G4F scientifico**,
con reali `run_experiment`, ReAct/verify LangGraph e ToolNode ma
LLM/telemetria fake. Il modulo G4G è un **orchestratore FAKE-ONLY**,
non il dispatcher provider di produzione: richiede marker sintetico e
release di prova con `approval_reference=SYNTHETIC_APPROVAL_NOT_REAL`,
rifiuta un root che contenga Market.zip/data processed e non importa
client SDK. Verifiche negative D/C/K invalidi, provider failure fake,
ID nativi incoerenti, meter errato, claim orfano, nessun retry,
OOD LOCKED e no API. **Tutti i 17 test G4G sono PENDING**.

Documento:
`docs/ood/RQ2_V2_UNIFIED_G4F_PASS_G4G_FAKE_DISPATCH_SCIENTIFIC_LEDGER_GATE_2026-11-14.md`.

**Comando PyCharm, git status pulito:**
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_dispatcher_offline_e2e.py" -v
```
Attesi 17 e OK, non attestati. Dopo il passaggio G4G occorre creare
il vero dispatcher comune e certificarne retry/timeout/uso/costi/lock
prima del freeze e di qualsiasi API. Gli hash della G4C provano il
preflight del vecchio HEAD, non includono G4F/G4G. Opzione B e
11 OOD sempre chiusi.

## 19. G4G: prima suite FALLITA per typo fixture, fix 1 riga — 14 novembre

Output Windows/PyCharm completo da file incollato utente:
`Ran 17 tests in 3.162s; FAILED (failures=1, errors=25)`.
La causa iniziale e' localizzata: nel fake gateway
`src/tests/test_rq2_v2_unified_dispatcher_offline_e2e.py`, alla
riga 101, `self.assertEqual_case(...)` richiama un metodo inesistente.
Il metodo dichiarato e' `assert_equal_case(...)`. La prima D crea
il claim prima del fake-runner, poi l'AttributeError blocca la
scrittura del record; il journal G4F rileva il claim orfano e blocca
correttamente tutte le 14 subtest seguenti `Unresolved claim:
manual review, no new stage`. Il fallimento finale `1 != 45`
e' quindi una cascata del primo errore, NON un motivo per rilassare
il controllo no-retry.

**Fix GitHub solo test:** sostituito il nome metodo alla chiamata,
commit `9c494ed8f6d1aad93bdf057e7f4eb88c8eef3d07`.
Nessun cambiamento a ledger G4F, dispatcher, RQ1, hash,
prompt, dati frozen o policy di sicurezza.

Report:
`docs/ood/RQ2_V2_UNIFIED_G4G_FAKE_GATE_WINDOWS_FAILURE_FIX_2026-11-14.md`.

**Prossimo comando PyCharm su checkout clean:**
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_dispatcher_offline_e2e.py" -v
```
G4G **ancora NON PASS**, test da rieseguire su TemporaryDirectory
nuova. Se appare una failure successiva differente, diagnosi prima
di nuove modifiche. Nessuna API/OOD abilitata.

## 20. G4G PASS 17/17; priorita' nuovo dispatcher reale UNICO — 14 novembre 2026

**Esito reale PyCharm:** `Ran 17 tests in 22.415s; OK`,
dopo la correzione di una sola chiamata `assert_equal_case` nella
fixture G4G. Il runner RQ1/ToolNode/verify_graph con fake LLM,
orchestrazione D→C→K e ledger scientifico G4F create-only sono
integrati in TemporaryDirectory: 15 combinazioni × 3 stage=45 record
nel test principale. Fallimento precedente G4G era solo typo fixture
seguito dal blocco previsto sui claim orfani; protezioni intatte.

**Non ripetere gli audit SDK gia' superati**: dalla documentazione
`docs/ood/RQ2_COLAB_FAKE_HTTP_INVOKE_2026-11-12.md` risulta
che il 12/11 l'utente aveva gia' ottenuto PASS con HTTP 503 finto,
socket deny-all, Google e Anthropic sync `invoke` (con/senza tools),
un solo fake send per invoke. Pinned source e timeout/retry
configurati localmente; streaming/async e timeout sotto socket stall
non dimostrati. Anche i moduli `rq2_model_factory.py`,
`rq2_discovery_d_provider_transport.py`,
`rq2_ck_provider_transport.py` esistono gia' ma sono
legati al protocollo/stage store RQ2 V1; il passaggio a ledger G4F
richiede un **solo adattamento** correttamente source-bound, non
una nuova infrastruttura parallela.

**Decisione per la prossima implementazione:** dispatcher LIVE RQ2-V2
unico per 180 stage *discovery* con stage singolo autorizzato,
preflight reale source/commit/release, claim pre-API, D via
`run_experiment` originale, C/K via prompt tool-free e
`rq2_model_factory` versionato, registrazione errori/meter/parent
in G4F senza retry. Verificare il suo esatto percorso con fake
factory prima del pilot. Inserire ledger, contract, dispatcher e
factory nel source inventory finale, rifare SHA/Git pin e verifica
concorrenza Drive. Nessuna API ancora autorizzata.
Contenuto preciso:
`docs/ood/RQ2_V2_UNIFIED_G4G_PASS_NEXT_SINGLE_LIVE_DISPATCHER_2026-11-14.md`.
**G4G concluso; nessun test aggiuntivo richiesto all'utente ora**.
Opzione B e 11 OOD sempre LOCKED.

## 21. User authorizes continuation; G4H one-stage source-bound preview added (14 Nov)

Utente ha confermato di voler proseguire dopo G4G
`Ran 17 tests in 22.415s; OK`. L'assistente ha ricontrollato
i moduli RQ2 esistenti e ha deciso **non** duplicare i probe
`rq2_langchain_fake_http_invoke` (gia' riusciti in Colab il 12/11
con socket deny-all e 503 fake) o la vecchia RQ2 V1.

**Nuovo blocco G4H aggiunto al branch:**
`src/evaluation/rq2_v2_unified_live_stage_preflight.py` e
`src/tests/test_rq2_v2_unified_live_stage_preflight_offline.py`
(**19 test scritti, NON ancora eseguiti**). La funzione
`preview_one_unified_stage` istanzia il ledger scientifico G4F
solo per fonte/provenienza e verifica release/commit/GT-free,
stage discovery mai claimed/recorded, nessun orphan, instruction
letta **dal manifest GT-free** (non fornita dal chiamante),
`ExperimentConfig` RQ1 V2 e, per C/K, package costruito
esclusivamente dai record immutabili validi e prompt C/K SHA-pinned.
Non esegue tool, Market, SDK, reti, claim, file o API; ritorna flag
`can_execute_api=False`, `can_create_scientific_claim=False`.
I test G4H usano manifest/release fake in TemporaryDirectory.

**Correzione separata G4F:** la `stage_meter` adesso permette
`cost_estimate_usd_not_invoice="UNKNOWN"` anche quando le
quantita' token sono complete, perche' token non sono fattura:
mai registrare costo zero fittizio. Questo modifica il ledger
G4F e richiede regressione dopo G4H, NON e' stato ancora ritestato
dall'utente.

Dettagli:
`docs/ood/RQ2_V2_UNIFIED_G4G_PASS_G4H_SOURCE_BOUND_STAGE_PREFLIGHT_2026-11-14.md`.

**Prossimo comando PyCharm:**
```powershell
git status --short
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_live_stage_preflight_offline.py" -v
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_scientific_ledger_offline.py" -v
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_dispatcher_offline_e2e.py" -v
```
Attesi rispettivamente 19, 22, 17 test, ma tutti PENDING dopo
l'ultimo commit. Nessun SDK reale, nessuna chiamata pagata,
Opzione B e 11 test OOD sempre bloccati.

**G4I successivo:** implementare dispatcher effettivo source-bound
per singolo stage D/C/K con blocco pre-API e fake provider injection
nel medesimo codice che poi usera' il provider; ampliare
SOURCE_PATHS includendo G4F/G4H e dispatcher, test Drive/FUSE,
meter/retry/timeout e real freeze SHA, poi chiedere esplicita
autorizzazione ad UN SOLO pilot pagato.
