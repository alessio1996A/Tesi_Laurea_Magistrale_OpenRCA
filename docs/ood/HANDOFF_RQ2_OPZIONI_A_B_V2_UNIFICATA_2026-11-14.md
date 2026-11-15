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

## 22. G4H Windows prima prova 17 OK/2 errori SHA FIXTURE; G4F/G4G PASS (15 novembre)

**Output utente da log PyCharm (reale):**
- G4H: `Ran 19 tests in 4.967s — FAILED (errors=2)`. Due soli
  errori nella preview positiva degli stage C e K:
  `UnifiedStagePreviewBlocked: Frozen C/K prompt SHA drift`.
- G4F: `Ran 22 tests in 20.972s — OK`.
- G4G: `Ran 17 tests in 19.580s — OK`.

**Diagnosi:** G4H in `setUp` eredita `source_fixture()` del G4E,
che imposta C/K prompt SHA all'hash **FAKE_SHA** generico per test
contratto. Ma G4H invoca davvero `prepare_cause_probe` e
`prepare_candidate_rule`, la cui fonte sono gli immutati
`CAUSE_SYSTEM` e `RULE_SYSTEM`. Il gate SHA correttamente
rifiuta il release finto incongruente. **Non modificare il controllo
G4H né i prompt reali**.

**Fix GitHub mirato** soltanto
`src/tests/test_rq2_v2_unified_live_stage_preflight_offline.py`:
la `setUp` sostituisce i due fake prompt hash con lo SHA256 calcolato
dai due prompt REALI prima di costruire blueprint e release fake.
Aggiunto test negativo `test_actual_prompt_drift_still_fails_closed_for_both_stages`
per dimostrare che un prompt veramente alterato continua a fallire.
Commit fix: `bbdfcff3d1628db409072835cc13440f195d2d1f`.
G4H ora contiene **20 metodi**, PENDING verifica dell'utente;
nessun file di codice G4H produttivo, ledger G4F/G4G, RQ1 o
sorgente GT-free alterato.

Documento:
`docs/ood/RQ2_V2_UNIFIED_G4H_WINDOWS_PROMPT_SHA_FIX_2026-11-15.md`.

**Prossimo comando PyCharm su checkout pulito:**
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_live_stage_preflight_offline.py" -v
```
Attesi 20 e OK, **non attestati**. G4F 22 PASS e G4G 17 PASS
attestati sul codice corrente. Nessuna API/OOD autorizzata.

## 23. G4H seconda prova 19 pass, 1 fail per test negativo staged male (15 novembre)

Output PyCharm condiviso:
`Ran 20 tests in 7.460s; FAILED (failures=1)`.
Tutti i 19 precedenti test G4H sono PASS, comprese le preview
positive C/K dopo correzione del pin SHA fixture. Il solo
`test_actual_prompt_drift_still_fails_closed_for_both_stages`
falliva nel sottotest C con
`Stage already claimed or recorded` invece di
`Frozen C/K prompt SHA drift`: la fixture aveva chiamato
`save_d(); save_c()` prima di testare la preview di C. Il guard
blocca correttamente riuso di un C gia' registrato; questo
test NON poteva raggiungere il codice SHA. Nessun problema
di ledger/produzione dimostrato.

**Fix SOLO test** commit
`ce0001abe1980664f97203e48bc607e233e7cbdf`:
ora verifica C SHA drift **dopo D e prima di salvare C**;
poi salva C valido e verifica K SHA drift **prima di salvare K**.
In entrambe le prove asserisce nessun claim nuovo; lascia
immutati il blocco di stage gia' registrati, G4F, G4G, RQ1,
fonti GT-free, release e OOD.

Doc aggiornato:
`docs/ood/RQ2_V2_UNIFIED_G4H_WINDOWS_PROMPT_SHA_FIX_2026-11-15.md`.

**Prossimo PyCharm** (checkout clean, 20 test da rieseguire):
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_live_stage_preflight_offline.py" -v
```
**Non** dichiarare G4H PASS prima dell'output aggiornato.
Ultime regressioni G4F 22 PASS e G4G 17 PASS; non serve
ripeterle perche' la sola variazione funzionale e' nel test G4H.
API e 11 OOD ancora bloccati. Dopo G4H preparare G4I.

## 24. G4H 20/20 PASS; G4I dispatcher per singolo stage fake-only — 15 novembre

**Esito PyCharm utente dopo correzione dell'ordine nel test negativo:**
`Ran 20 tests in 7.090s; OK` — **G4H PASS**.
I test SHA dei prompt C/K rimangono attivi e verificati anche contro
tamper. Ultime regressioni G4F 22/22 e G4G 17/17 PASS. Nessuna
modifica agli archivi scientifici congelati RQ1/RQ2 V1.

**Nuovo G4I aggiunto, NON ancora eseguito in PyCharm**:
`src/evaluation/rq2_v2_unified_single_stage_dispatcher.py`
`src/tests/test_rq2_v2_unified_single_stage_dispatcher_offline.py`
(**24 metodi PENDING**).

Diversamente dall'orchestratore G4G a tripla, G4I coordina
UN SOLO stage D/C/K per chiamata. Rilegge G4H (source-bound
manifest GT-free, release/commit, parent D/C immutabili),
ricostruisce C/K con prompt SHA esatto, scrive claim tramite
ledger G4F **prima** dell'LLM fake, vieta le socket tramite
`network_forbidden()`, registra record/stati/errori nel G4F.
Se D/C fallisce, registra gli stage figli come
`BLOCKED_DEPENDENCY` senza nuovi claim/chiamate; errori
inattesi dopo claim lasciano orphan, stop al retry. Testano tre
bracci di modelli/harness con veri grafi RQ1 e backend fake,
provider error, SHA package mutato, root non temporanea,
marker assente, file Market vietato, OOD, e token completi ma
prezzo sconosciuto.

**G4I NON HA BACKEND API REALE**. Richiede marker fisico
`.rq2_v2_unified_single_stage_fake_only`, root sotto il
TemporaryDirectory OS e una release **FAKE** con riferimento
`SYNTHETIC_APPROVAL_NOT_REAL`. Il gateway dei test usa fake LLM,
non provider remoti. Nessun nuovo consenso a chiamate a pagamento.
Non prendere G4I come release scientifica.

Documento:
`docs/ood/RQ2_V2_UNIFIED_G4H_PASS_G4I_SINGLE_STAGE_FAKE_DISPATCH_2026-11-15.md`.

**Prossimo comando PyCharm (git status pulito):**
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_single_stage_dispatcher_offline.py" -v
```
Attesi `Ran 24 tests` e `OK` ma NON ancora provati.
Se fallisce, riportare il traceback prima di modificare codice.
Poi adapter provider reale, lock Drive, metering/timeout, nuovo
source inventory completo + SHA e approvazione esplicita del
singolo pilot, non 180 stage API. 11 OOD ancora locked.

## 25. G4I primo test 23 PASS/1 ERROR release fake; test-only fix (15 novembre 2026)

**Output utente effettivo**: `Ran 24 tests in 13.179s; FAILED (errors=1)`.
23 test G4I positivi; unico errore nel
`test_fake_release_required_even_if_marker_exists`, dove
la fixture altera volontariamente il file release e poi invoca
`self.ledger.audit_restart()` per contarne i claim. Questo
audit giustamente ferma l'esecuzione con
`UnifiedScientificLedgerBlocked: Missing/different scientific release`
perche' la release SHA NON corrisponde. Non e' corretto
aggirare questo guard per ottenere un conteggio.

**Fix chirurgico SOLO test**:
`src/tests/test_rq2_v2_unified_single_stage_dispatcher_offline.py`,
commit `e57f4955ea1f343339deb4ed02285116df118335`.
Ora asserisce che sia `run_stage()` sia `audit_restart()`
rifiutino esplicitamente una release manomessa; verifica
direttamente che sul filesystem temporaneo siano assenti
directory claim/record senza invocare audit in stato invalido.
Nessun modulo di produzione, protocollo, prompt, RQ1 o fonte GT-free
modificato.

Report:
`docs/ood/RQ2_V2_UNIFIED_G4I_FIRST_WINDOWS_23_PASS_1_ERROR_FIX_2026-11-15.md`.

**Prossimo PyCharm** su checkout clean:
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_single_stage_dispatcher_offline.py" -v
```
**24 test PENDING** dopo fix: non dichiarare G4I PASS fino
all'output. G4F 22 PASS, G4G 17 PASS, G4H 20 PASS
gia' attestati. Nessuna API eseguita, test OOD 11 locked.

## 26. G4I 24 PASS e G4J provider receipt adapter (15 novembre 2026)

**Esito utente PyCharm:** `Ran 24 tests in 11.480s; OK` per
`test_rq2_v2_unified_single_stage_dispatcher_offline.py`.
**G4I PASS 24/24** dopo correzione chirurgica del solo test
di manomissione release, senza cambiare codice G4I/G4F/GT-free.
I gate recenti G4F=22 PASS, G4G=17 PASS, G4H=20 PASS, G4I=24 PASS.

**Nuovo G4J aggiunto (PENDING test PyCharm):**
`src/evaluation/rq2_v2_unified_provider_result_adapter.py` +
`src/tests/test_rq2_v2_unified_provider_result_adapter_offline.py`
(**25 metodi da lanciare**). Non importa/crea SDK, non invoca
API, non crea claim, non legge GT o Market. Normalizza ricevute
gia' ottenute da D `run_experiment` e C/K
`rq2_ck_provider_transport._one_call` in
`status+artifact` compatibili col nuovo ledger G4F.
RIUSA il medesimo validatore G4F per status complete/invalid;
identita' stage/LLM/harness source-bound, preserva errori
provider e JSON non valido senza repair. Distinzione:
logical invocations osservate NON hard cap HTTP;
token osservati NON costo accertato: USD sempre UNKNOWN,
usage_complete indipendente. Testano 3 modelli, errori/usage,
forged E### e write/readback D/C/K su ledger create-only FAKE.
No provider pagati. I vecchi trasporti V1 NON sono autorizzati
ad usare il namespace G4F senza adattamento.

**Documento completo:**
`docs/ood/RQ2_V2_UNIFIED_G4I_PASS_G4J_PROVIDER_RECEIPTS_2026-11-15.md`.

**Prossimo PyCharm** su checkout clean:
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_provider_result_adapter_offline.py" -v
```
Attesi 25 e OK, non attestati. Poi il nuovo transport/dispatcher
effettivamente live per singolo stage iniettando factory fake
negli UNITTEST, source inventory completo (G4F/G4H/G4I/G4J e
adapter/factory) + freeze SHA/commit, lock Drive e
consenso esplicito al singolo pilot reale. 11 OOD locked.

## 27. G4J 25 PASS; G4K provider live-capable HARD-DISABLED, inventory 29 sorgenti (15 novembre)

**Esito test utente:** `Ran 25 tests in 1.037s; OK`
per `test_rq2_v2_unified_provider_result_adapter_offline.py`.
Il modulo G4J normalizza D/C/K verso G4F senza SDK e mantiene token
osservati separati dal prezzo `UNKNOWN`. Ultimi gate G4F 22,
G4G 17, G4H 20, G4I 24, G4J 25 **tutti PASS =108 test**.

**Nuovo G4K scritto sul branch, NON ancora eseguito:**
`src/evaluation/rq2_v2_unified_live_dispatcher.py`
`src/tests/test_rq2_v2_unified_live_dispatcher_mock_offline.py`
(18 metodi offline da lanciare).
Il dispatcher `run_one_claimed_unified_stage` e' **hard-disabled**
con `LIVE_API_ENABLED=False`, e rifiuta invocazioni persino con
`confirm_paid_api=True`. Un futuro stage reale richiedera'
codice sbloccato in un nuovo commit, release SHA external, checkout
clean, ref approvazione non fake, approved_stage_id = stage_id,
preflight G4H, claim G4F **prima** del client, D via
`crea_modello_rq2` + RQ1 `run_experiment(..., salva=False)`,
C/K via `rq2_ck_provider_transport._one_call` tool-free, normalize
G4J → record G4F; errori/invalidi, figli blocked, no auto-retry.
I test G4K patchano solo nel processo Python `LIVE_API_ENABLED=True`,
sostituendo il runner D e la chiamata C/K con MOCK in
TemporaryDirectory e con release sintetica. **Non esiste consenso a
spendere o API autorizzata**.

**Source inventory G4A aggiornato da 15 a 29 file** in
`src/evaluation/rq2_v2_unified_release_preflight.py`: include
ora ledger, release, G4H/I/J/K, factory RQ2-only, trasporto CK,
policy di retry e costi. Aggiunto un test a
`src/tests/test_rq2_v2_unified_release_preflight_offline.py`
(19 test attesi). L'esito G4C pregresso con 15 source rimane storico,
non valida questo nuovo commit. Nessun source RQ1 congelato, prompt
C/K o split/manifest modificato.

Documento:
`docs/ood/RQ2_V2_UNIFIED_G4J_PASS_G4K_BLOCKED_LIVE_TRANSPORT_2026-11-15.md`.

**Prossimo PyCharm dopo git status pulito:**
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_live_dispatcher_mock_offline.py" -v
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_release_preflight_offline.py" -v
```
Attesi rispettivamente **18** e **19**, entrambi PENDING.
Non chiamare API o creare release vera prima del nuovo audit GT-free
Colab 29 source/commit, prova lock Drive e approvazione singolo pilot.
Lo stimatore USD e il 492 graph invoke candidati non sono hard cap HTTP.
11 OOD / Opzione B sempre LOCKED.

## 28. G4A inventario 29 file PASS; G4K import SyntaxError, correzione fixture (15 novembre)

**Output effettivo utente PyCharm:**
- G4A `test_rq2_v2_unified_release_preflight_offline.py`:
  `Ran 19 tests in 0.379s; OK`. Include test obbligatorio
  delle **29 sorgenti** nel piano source-bound. G4A aggiornato PASS.
- G4K `test_rq2_v2_unified_live_dispatcher_mock_offline.py`:
  `Ran 1 test in 0.002s; FAILED (errors=1)`, ma nessun
  test G4K effettivo e' stato eseguito; `unittest.loader._FailedTest`
  segnala **SyntaxError alla riga 185** del file test,
  `patch.object(subject, "crea_modello_rq2") as factory`.

**Diagnosi e correzione GitHub, SOLO file test:**
```python
# prima, non sintatticamente valido
with patch.object(subject, "LIVE_API_ENABLED", False), (
    patch.object(subject, "crea_modello_rq2") as factory
):
    ...
# dopo, Python 3.12 valido
with (
    patch.object(subject, "LIVE_API_ENABLED", False),
    patch.object(subject, "crea_modello_rq2") as factory,
):
    ...
```
Commit fix `e4c3e29187f5aaa199da17e19b2a57beb7e3e042`.
Nessuna modifica a `rq2_v2_unified_live_dispatcher.py`,
`LIVE_API_ENABLED=False`, ledger G4F, G4H/G4I/G4J, RQ1,
prompt, source inventory 29, casi OOD o protocollo 180 stage.

**G4K ancora PENDING: 18 metodi non sono mai stati testati.**
Prossimo comando PyCharm su checkout pulito:
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m py_compile src/tests/test_rq2_v2_unified_live_dispatcher_mock_offline.py
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_live_dispatcher_mock_offline.py" -v
```
Attesi 18 e OK, non attestati. Se compaiono failure runtime
differenti, valutare primo traceback, NON dichiarare G4K PASS.
G4A 19 test PASS senza bisogno di nuova esecuzione. Nessuna API
reale, autorizzazione o test OOD.

## 29. G4K 18/18 PASS; G4A 19/19 PASS; prossimo Colab reale 29 source (15 novembre)

**Output reale utente PyCharm:** dopo fix puramente sintattico fixture
G4K, `Ran 18 tests in 6.276s; OK`. Il dispatcher
`rq2_v2_unified_live_dispatcher.py` continua ad avere
`LIVE_API_ENABLED=False`; tutti i test G4K usano mock per runner
e trasporti, release sintetica in TemporaryDirectory.
L'altra suite `test_rq2_v2_unified_release_preflight_offline.py`
ha riportato `Ran 19 tests in 0.379s; OK`, quindi
G4A inventario **29 sorgenti** PASS. Totale ultime sette suite
G4F/G4G/G4H/G4I/G4J/G4K/G4A: **145 PASS** (offline).

**Nessuna nuova chiamata API della RQ2-V2 unificata** e nessuna
autorizzazione spesa. Il documento
`docs/ood/RQ2_V2_UNIFIED_G4K_PASS_NEXT_REAL_29_SOURCE_COLAB_PREFLIGHT_2026-11-15.md`
registra il prossimo passo: **preflight Colab READ-ONLY sulla HEAD
esatta PINNATA esternamente**, usando i veri CSV GT-free in
`/content/drive/MyDrive/Tesi_OpenRCA/data/processed/`.
La nuova cella ChatGPT deve:
- clone/fetch sul checkout temporaneo separato,
  confermare `FETCH_HEAD==EXPECTED_COMMIT` PRIMA del checkout,
  verificare Git clean;
- importare solo source preflight e blueprint,
  richiedere 29 source, SHA source, split/manifest, prompt C/K,
  4 discovery, 11 OOD metadata locked, `can_execute_api=False`;
- stampare JSON con SHA aggregated e nessuna richiesta API,
  no claim, no scientific release, no GT;
- STOP su qualunque mismatch. Non forzare file, hash o branch.

Il precedente G4C reale `33d5d8...` con 15 sorgenti rimane
prova storica, NON valida il nuovo checkout. Dopo JSON reale:
verifica lock Drive/FUSE su scratch, runtime/timeout e tariffe,
freeze e autorizzazione del singolo pilot D. I test OOD/Opzione B
restano LOCKED 11/11; niente scoring o GT.

## 30. Colab G4 reale 29-source PINNED PASS, JSON integrale (15 novembre)

**Output utente Colab realmente completo:** due CSV originali GT-free
verificati, HEAD del checkout separato
`601dc7c2f971b919962ff190e6feb192c4dd237a`, cella
`check=True` uscita normalmente senza API. Seconda cella di recupero
ha stampato JSON e `json.loads` lo ha accettato.

`status = RQ2_V2_29_SOURCE_REAL_GT_FREE_PREFLIGHT_OK_NO_API`;
`source_file_count=29`;
`source_inventory_sha256=32457ec256e0fc430580f6d2205a50983811784f5ce87917ca3d2f79ea0fbe9e`;
`source_plan_sha256=e6f797c4ca01ed422b80e928854469b9f8c7f7cc4215835bf91f9f7305425a00`;
`blueprint_sha256=d5bfe9872b2497bea19b3aec7f4c93635f3444679e11856b9a5975c8a2a929da`;
`split_sha256=c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`;
`manifest_sha256=5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`.
C prompt SHA `81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42`;
K prompt SHA `0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71`.
3 modelli Gemini/Sonnet/Haiku × 5 harness × 4 discovery × D/C/K:
**180 stage logici** (60 ciascuno). `ood_locked=11`,
`ledger_namespace_absent=true`, `ground_truth_read=false`,
`scientific_release_frozen=false`, `can_execute_api=false`,
`model_requests_sent=0`.

**Report dettagliato**:
`docs/ood/RQ2_V2_UNIFIED_COLAB_29_SOURCE_REAL_GT_FREE_PASS_2026-11-15.md`.
Il report verifica il commit 601dc7..., NON il futuro HEAD dopo
modifiche alla documentazione. RQ2 V2 unified: **0/180 stage reali**,
nessuna release o spesa API. Passi successivi: test FUSE lock e
create-only su **scratch MyDrive esterna a Tesi_OpenRCA**, valutare
se la semantica consente ledger create-only su Drive, runtime e tariffe,
nuova approvazione SHA esterno finale, quindi consenso specifico per
UN pilot D. 11 OOD sempre locked. NON modificare code RQ1 frozen.

## 31. Colab Drive/FUSE scratch esclusività PASS (15 novembre 2026)

**Output reale dell'utente:**
`status=DRIVE_SAME_RUNTIME_SINGLE_WRITER_SCRATCH_PASS_NO_API`;
`concurrent_processes=8`;
`exclusive_file_creators=1`;
`lock_second_process_denied=true`;
`lock_released_and_reacquired=true`;
`other_colab_sessions_or_vms_verified=false`;
`model_requests_sent=0`;
`data_root_modified=false`;
`SCRATCH_REMOVED=True`.

Sono PASS una prova `fcntl.flock(LOCK_EX|LOCK_NB)` con un
secondo processo negato e reacquire dopo unlock, e una
`os.open(O_CREAT|O_EXCL)` tra otto processi sullo stesso
Drive MyDrive scratch; una sola creazione, sette esclusioni.
La scratch era
`/content/drive/MyDrive/rq2_v2_lock_probe_vxgwo2a8`
ed è stata eliminata automaticamente. I risultati scientifici,
Market e i namespace RQ2 reali NON sono stati modificati.

**Limite**: solo isolamento nella stessa VM/sessione di Colab.
Non certifica semantica cross-VM/cross-session, remote durability,
startup recoverability, hard cap monetario o idempotenza remota.
Decisione operativa: UN SOLO processo/writer Colab per un singolo
stage, nessuna seconda sessione concorrente; orphan => audit manuale,
non retry automatico. Il test PASS non abilita API e non crea release.

Report:
`docs/ood/RQ2_V2_UNIFIED_COLAB_DRIVE_SCRATCH_LOCK_PASS_2026-11-15.md`.

**Preflight scientifico reale precedente** (29 file, manifest+split GT-free)
`HEAD=601dc7c2f971b919962ff190e6feb192c4dd237a`,
`source_inventory_sha256=32457ec256e0fc430580f6d2205a50983811784f5ce87917ca3d2f79ea0fbe9e`,
`blueprint_sha256=d5bfe9872b2497bea19b3aec7f4c93635f3444679e11856b9a5975c8a2a929da`,
`can_execute_api=false`, 11 OOD locked, nessuna release.
La documentazione successiva avanza il branch ma NON rimpiazza
il commit effettivamente verificato.

**Next**: audit stdlib read-only di versioni e SHA delle sorgenti
SDK effettivamente installate nel runtime Colab attuale, senza
pip/SDK client/rete; fermarsi se versioni assenti/diverse e non
installare automaticamente. Seguiranno pin SDK + policy retry/timeout
su mock transport, stima spesa, release G4F e consenso esplicito
stage D prima di UNA API pagata. RQ2 V2 = 0/180 stage API reali;
Opzione B = 11 OOD LOCKED.

## 32. SDK runtime Colab nuovo NON conforme — STOP corretto (15 novembre)

**Audit reale dell'utente, SDK source-only** nella nuova sessione Colab
Python 3.13.18: `runtime_snapshot_ready=false`, mentre
`frozen_rq1_factory_unchanged=true`, `model_requests_sent=0`
e `can_execute_api=false`.

Versioni attese → osservate: langchain-core 1.7.1→1.7.4;
langgraph 1.2.18→1.2.19; langchain-anthropic 1.7.7→missing;
langchain-google-genai 4.4.2→missing; anthropic 2.6.0→missing;
google-genai 2.34.0→2.12.1. Hash Google GenAI source
osservato `d0209bc9b335c6e8c440ed0a6f3b46af367785a4e5743aedc51b46e395e5e205`,
expected `b179b80a126a35c98b98aeefa701950304c38c8a1e117136a2270a0901fd93e4`.
Il resto dei quattro SHA provider è null. 6/6 versioni NON
coincidenti e 4/4 SHA NON coincidenti.

**Interpretazione:** la cella usa il Python GLOBALE di Colab e
non il target dipendenze isolato dei precedenti audit; NON è
evidenza di mutazione dei CSV, RQ1 frozen, release o split.
La factory RQ2-only fa esattamente ciò che deve: rifiuta lo
snapshot sbagliato. **STOP per qualunque API**, no modifica
automatica di dipendenze globali/SDK pin.

**Prossima azione proposta**: ripristino riproducibile su cartella
temporanea NUOVA `/content/rq2_v2_pinned_sdk_py313` con
`pip --target`, stesse versioni storiche (compresi
langchain==1.4.7 e google-auth==2.56.0) e audit subprocess con
`PYTHONPATH` composto da DEPS+REPO/src. Verificare 6 versioni e
4 SHA sorgenti, NO API, prima di dichiarare SDK PASS.
**Ripristino non ancora attestato** e nessun commit sorgete modificato.

Dettagli:
`docs/ood/RQ2_V2_UNIFIED_COLAB_SDK_RUNTIME_DRIFT_AND_PIN_RESTORE_2026-11-15.md`.

Restano PASS il Colab source preflight 29 file sul commit
`601dc7...` e l'esclusivita' lock/O_EXCL scratch nella
stessa sessione. `LIVE_API_ENABLED=False`; 0/180 stage reali,
11 OOD locked. Dopo ripristino eventuale: audit runtime,
policy retry/timeout, release pin finale, consenso singolo pilot.

## 33. RQ2-V2 isolated Colab SDK snapshot PASS (15 novembre)

**Output utente realmente attestato** nella nuova sessione Colab:
`=== SDK SNAPSHOT ISOLATO: PASS ===`,
`runtime_snapshot_ready=true`,
`frozen_rq1_factory_unchanged=true`,
`provider_requests_sent=0`, `can_execute_api=false`.
Python 3.13.18, `pip --target` in
`/content/rq2_v2_pinned_sdk_py313`, nessun aggiornamento global
Colab e nessuna modifica Drive. Audit nel subprocess
`PYTHONPATH=DEPS:REPO/src`.
**6/6 versioni MATCH**: langchain-core=1.7.1,
langgraph=1.2.18, langchain-anthropic=1.7.7,
langchain-google-genai=4.4.2, anthropic=2.6.0,
google-genai=2.34.0.
**4/4 SHA sorgenti SDK MATCH**:
anthropic `a42ef507300287261fe0b215023672a97f8a9b01216a135d614bbede72fff680`;
google-genai `b179b80a126a35c98b98aeefa701950304c38c8a1e117136a2270a0901fd93e4`;
langchain-anthropic `c55a0cb8fed75b3d310dbddf03a455f95c3c1d47aab650317bf3c9e4bab62544`;
langchain-google-genai `589106719f2038805a27ddd0c44c23d5e4a4486ea0d7116b38a83d37722ac27f`.
Il precedente failure usando Python Colab GLOBALE e' spiegato
dalla mancanza dei pacchetti isolati, non da drift RQ1.
`READY` marker scritto SOLO nel `DEPS` /content temporaneo.

**Report:**
`docs/ood/RQ2_V2_UNIFIED_COLAB_SDK_PINNED_SNAPSHOT_PASS_2026-11-15.md`.

**ATTENZIONE:** legacy `rq2_langchain_bridge_source_trace.py`
ha assert testuale `RELEASE_SHA256 = None` su
`rq2_ck_provider_transport.py`, ma il branch RQ2 corrente
presenta release V1 pin storico. NON forzare quel vecchio
guard per eseguire un test legacy in RQ2-V2; non toccare
V1, RQ1 o il protocollo scientifico frozen.
Il prossimo controllo mirato e' `assert_exact_runtime_snapshot()`
del RQ2-only `rq2_model_factory` e, se utile, SDK-only
`rq2_sdk_retry_mock_probe.run_offline_mock_probe`
con Google retry_ARGS in-memory e Anthropic HTTP finto.
Sempre `PYTHONPATH=DEPS:REPO/src`, checkout commit testato
`601dc7...`, no live SDK provider request.

G4K live remains `LIVE_API_ENABLED=False`. Dopo audit SDK:
freeze di nuovo commit finale, review prezzo/budget,
approval SHA release e user consent per UN pilot D,
no 11 OOD; zero run RQ2-V2 API.

## 34. SDK-only mock Colab PASS e tariffe ufficiali ricontrollate (15 novembre)

**Output esatto utente Colab:** `RQ2_FACTORY_RUNTIME: PASS`;
`SDK MOCK: PASS — 0 API REALI`.
Il report `SDK_LOCAL_MOCK_CHECKED_LANGCHAIN_NETWORK_POLICY_NOT_FROZEN`
è uscito con
`source_snapshot_sha256=79d209cd7678b9ca036699cfa572579a20c2a62c4fd021042adf9d5b90f5ee98`.
Google `retry_args` local counts = default 1, attempts=1→1,
attempts=2→2. Anthropic SDK synthetic 503 con
`sdk_mock_503_attempts=1`, timeout CONFIGURATO nella
sola prova mock = 15 secondi. Factory RQ2 exact snapshot PASS
sul target isolato; socket network deny-all; 0 credenziali reali,
0 modello, 0 GT e 0 OOD. `scientific_release_signed=false`
e tutti i gate API ancora false.

**Limiti dichiarati dallo stesso report:** LangChain forwarding
non verificato DA QUESTO test; stall timeout, streaming/async,
aiohttp implicit retry NON provati. Un precedente test del 12/11
`docs/ood/RQ2_COLAB_FAKE_HTTP_INVOKE_2026-11-12.md`
aveva verificato LangChain→SDK sincrono con HTTP 503 finto,
un send per invoke CK e D-bound in Gemini e Anthropic, sullo
stesso snapshot di versioni/sha, ma non autorizza da solo
assumptions di hard cap per tutti i trasporti/condizioni.
Non impostare arbitrariamente `transport_retries_proven_no_implicit_http_retry`
o `per_request_timeout_verified` nella release basandosi SOLO
sull'SDK-only test; il contratto G4E richiede tali flag TRUE
con evidenza sufficiente per il percorso davvero usato.

**Prezzi ufficiali base paid standard ricontrollati sul web
il 15/11/2026** rispetto ai valori sorgente
`rq2_budget_preflight.py` del 12/11:
- Gemini 3.5 Flash-Lite $0.30 input / $2.50 output
  per milione token; output incluso thinking.
  `https://ai.google.dev/gemini-api/docs/pricing`
- Claude Sonnet 5.5 $2.00 input / $10.00 output;
  `https://platform.claude.com/docs/en/about-claude/pricing`
- Claude Haiku 5.5 $0.10 input / $0.50 output con
  prompt per chiamata <=100K, $0.50/$2.50 per prompt >100K.
  Stessa fonte Anthropic. Nessuna cache/Batch, tassa, conversione
  né tier gratuito presunti. Sono **tariffe, non un budget
  autorizzato né un limite massimo a consumo**. Non assumere
  che le API remote/quote dei tre modelli siano confermate senza
  una vera chiamata; la campagna unificata è ancora a 0/180 stage.

**Next decisione, senza ricominciare il progetto**:
- valutare se le prove esistenti sul PERCORSO sync effettivamente
  utilizzato dal dispatcher G4K (non streaming) + policy
  `TIMEOUT_SECONDS=300`, retry Google=1, Anthropic=0,
  sono sufficienti e quali garanzie restano false; non mentire
  nel release contract;
- ricostruire release/preregistration finale sul commit **NUOVO**
  (il report Colab 29 sorgenti è vincolato a HEAD `601dc7...`);
- stabilire budget operativo iniziale e 1 stage D discovery
  con consenso esplicito user, e solo allora creare release
  create-only + pin SHA esterno, audit manuale, sbloccare con nuovo
  commit G4K `LIVE_API_ENABLED=False` mantenendo safe gate;
- D puo' richiedere più invoke, stimare ma niente hard cap USD
  o HTTP certificato; no retry su orphan e writer seriale;
- non avviare 11 OOD, non scrivere RQ1, non rimuovere documenti
  prima del refactoring finale successivo alla raccolta dati.

Report:
`docs/ood/RQ2_V2_UNIFIED_COLAB_SDK_LOCAL_MOCK_PASS_2026-11-15.md`.
La chat è lunga: prima del cambio successivo usare questo handoff
e fornire all'utente un messaggio di trasferimento con branch,
ultimo HEAD, output Colab/SDK, source SHA, gates aperti e singola
azione successiva. Non confondere SHA del commit preflight 601dc7
con HEAD successivo dei soli commit documentali.

## 35. Timeout sync loopback RQ2-V2 PASS; freeze e budget ancora aperti (15 novembre)

**Nuova evidenza reale dell'utente:**
- PyCharm `test_rq2_v2_sync_timeout_loopback_guard_offline.py`: `Ran 8 tests in 0.009s — OK`.
- Colab checkout clean pinned `d67141ad0ef1e0b4f258c2667372e9aca8ff6292`, SDK pinned isolato, test HTTP **solo server fittizio 127.0.0.1**.
- `status=SYNC_LOCAL_STALL_TIMEOUT_CHECKED_NO_API_NO_RELEASE`; `loopback_sends_total=4`, `external_api_requests=0`, `actual_model_calls=0`.
- Google: C/K una richiesta locale e timeout dopo `0.3071s`; D-bound una e timeout dopo `0.3057s`.
- Anthropic: C/K una richiesta e timeout dopo `0.3041s`; D-bound una e timeout dopo `0.3037s`.
- `async_streaming_tested=false`, `full_stage_timeout_guaranteed=false`, `usd_hard_cap_guaranteed=false`, `scientific_release_frozen=false`, `can_execute_api=false`, `can_run_ood_test=false`. Nessun claim scientifico.

**Limite fondamentale:** prova con timeout test 0.3s, NON con i 300s configurati nella factory RQ2-only e NON per durata complessiva D. La precedente prova 503 fake del 12/11 e quella SDK-only del 15/11 completano l'evidenza sync per gli scenari osservati, ma non certificano ogni altro errore/status (es. 429), ogni trasporto, async/stream, hard HTTP count o fatturazione. Non impostare flag G4E a True in senso universale senza perimetro verificabile.

La documentazione dettagliata e' `docs/ood/RQ2_V2_UNIFIED_SYNC_LOOPBACK_TIMEOUT_PASS_NEXT_RELEASE_2026-11-15.md`. Nessun modulo di produzione o RQ1 e' stato modificato: soltanto i due test nuovi e questo aggiornamento documentale dopo il preflight 29-source su `601dc7...`.

**Prossima decisione tecnica/scientifica:** circoscrivere il gate retry/timeout al sync effettivamente usato e decidere se l'evidenza e' sufficiente o se un SOLO caso negativo mirato ancora mancante (p.es. 429) serve prima del freeze. Poi pianificare budget stage D, verifica sorgenti finali, release SHA esterno e consenso esplicito del singolo pilot. Non creare release o abilitare G4K senza questi passaggi; `LIVE_API_ENABLED=False`; RQ2-V2 rimane 0/180 stage API, 11 OOD LOCKED.

## 36. HTTP 429 sync PASS e chiusura verifiche mirate 503/429/stallo (15 novembre)

**Utente PyCharm:** `Ran 6 tests in 0.521s — OK` per `test_rq2_v2_sync_429_retry_guard_offline.py`.

**Utente Colab pinned SHA `442bf7d61762cf5b11b58050d53aa8258ab74e0b`:**
`status=SYNC_HTTP_429_MOCK_ONE_SEND_EACH_NO_API_NOT_RELEASED`;
`synthetic_429_http_sends_total=4`; un HTTP sintetico per (Google, Anthropic) × (CK tool-free, D bound-tools), tutti con `http_error_observed=true`; `external_provider_requests=0`; `real_credentials_used=false`;
`async_streaming_tested=false`; `max_http_attempts_guaranteed=null`;
`usd_hard_cap_guaranteed=false`; `scientific_release_frozen=false`;
`can_execute_api=false`; `can_run_ood_test=false`.
Il report e' `docs/ood/RQ2_V2_UNIFIED_COLAB_SYNC_429_MOCK_PASS_2026-11-15.md`.

**Cosa risulta verificato:** configurazioni SDK source-pinned e percorsi LangChain sync per test in-memory 503, 429 e loopback timeout di 0.3s, con un invio per scenario osservato. NON ci sono prove di tutte le possibili HTTP failure, di 300s runtime effettivi, di limite stage D, di hard cap USD, di async/stream o di API reali. Non ripetere altre prove generiche. RQ1 e 29 sorgenti di produzione non modificati da questi aggiornamenti.

**Gate successivi:** verifica prezzo/quote provider; budget *esplicitamente* approvato; source freeze HEAD clean su Colab con hash dei 29 sorgenti; G4E/G4F create-only e release SHA approvato esternamente, poi consenso esplicito sullo stage D singolo (non altri). Matrice V2 per modello D/C/K = 20/20/20, NON V1 30/30/8. `LIVE_API_ENABLED=False` e OOD 11 LOCKED, stage reali V2 `0/180`.

## 37. Costi RQ2-V2: scenario ipotetico non autorizzativo (15 novembre)

Ricontrollati listini Standard pubblici Google/Anthropic il 15/11: Gemini 3.5 Flash-Lite USD 0.30/2.50 input/output per 1M; Sonnet 5.5 USD 2/10; Haiku 5.5 USD 0.10/0.50 per richieste <=100k prompt, USD 0.50/2.50 sopra soglia per *request*.

Documento con formule esatte e avvertenze:
`docs/ood/RQ2_V2_UNIFIED_BUDGET_SCENARIO_GT_FREE_NO_APPROVAL_2026-11-15.md`.
Unicamente **WHAT-IF**: D = 150k input + 5k output aggregati, C e K = 10k input + 2k output ciascuno; su V2 nuova matrice `20 D + 20 C + 20 K` per modello, costo illustrativo totale USD `10.50–11.90`, Gemini singolo D USD `0.0575`. NON forecast/hard cap; cambiare token altera radicalmente il totale. Mai usare il vecchio helper V1 `estimate_campaign_cost` 30/30/8 per la matrice V2.

Confronto GitHub fra preflight 29-source `601dc7c2f971b919962ff190e6feb192c4dd237a` e SHA documentale `c09d6bfa3c45e518a208d5d9e9029ec6512216c0`: ZERO modifiche ai file `src/` di produzione; solo quattro file di probe/test nuovi `src/tests/` e note `docs/`. Non ripetere 29-source preflight né suite storiche senza nuovo cambio sorgenti/causa scientifica; il freeze definitivo va comunque pinning su nuovo commit clean.

**Prossima decisione esterna mancante:** budget operativo esplicito USD per il singolo pilot D (non hard cap) e policy di stop; NON equivale ancora ad autorizzazione a chiamare API. Successivamente freeze/release SHA e consenso esplicito ulteriore per esatto stage. V2 0/180 reali, OOD 11 LOCKED, `LIVE_API_ENABLED=False`.

## 38. Indicazione del relatore, priorita' scientifiche e refactoring alla fine

L'utente riferisce che il relatore ha detto di **non lasciarsi frenare dai costi**: la priorita' e' realizzare RQ2 accuratamente e in modo riproducibile. Questa e' un'indicazione di priorita' progettuale e NON costituisce un'approvazione esplicita a eseguire API o spendere senza limite. Il contratto G4E esige ancora un `approved_total_usd_limit` positivo e una reale `approval_reference`, mentre ogni singolo stage D/C/K richiede una conferma distinta. Non richiedere di nuovo micro-budget mentre si procede ai gate scientifici.

L'utente conferma per la fase finale, **dopo raccolta/audit/freeze dati**: refactoring del codice, commenti/docstring in italiano, pulizia dei file e riordino dei repository. Lavoro su branch dedicata, previa analisi dipendenze e salvaguardia degli archivi scientifici. Non iniziare ora la pulizia, non cancellare dati o evidenze originali.

Prossimo gate prioritario: preregistrazione indipendente della valutazione conservativa K (grounding E###, non-contraddizione segnali/condizioni, formalizzabilita' che non equivale a JSON valido), con test offline source-bound/GT-free; poi freeze 29-source + release G4E/G4F. Confermato dal confronto GitHub: i 29 sorgenti `src/` di produzione non sono cambiati dal preflight precedente, i nuovi test 503/429/stallo sono offline e passati; non ripetere tutti i test.

Nota dettagliata: `docs/ood/RQ2_V2_RESEARCH_NEXT_STEPS_POST_RESULTS_REFACTOR_2026-11-15.md`. `LIVE_API_ENABLED=False`, 0/180 stage reali, 11 OOD LOCKED.

## 39. Rubrica K preregistrata per confronto Opzione A — NON ancora testata (15 novembre)

L'utente ha confermato l'impostazione: 4 discovery per la Opzione A, 11 OOD TEST esclusi, 5 harness e 3 modelli con D→C→K. Paper/trascrizioni precedenti non necessari adesso; chiederli solo per indicazioni del relatore non gia' documentate. In prossimita' del cambio chat aggiornare questo handoff con ultimo HEAD, esiti test ed esatta azione successiva.

**Prima dei nuovi output live** e' stata preregistrata la rubrica:
`docs/ood/RQ2_V2_K_QUALITY_RUBRIC_PREREG_2026-11-15.md`.
Il codice che la applica e' `src/evaluation/rq2_v2_k_quality_rubric.py`, SOLO post-run offline, non dentro D/C/K. Il test nuovo e' `src/tests/test_rq2_v2_k_quality_rubric_offline.py` (**18 test sintetici DA ESEGUIRE in PyCharm; non dichiararli superati**). `src/evaluation/rq2_v2_unified_release_preflight.py` include ora la rubrica in `SOURCE_PATHS`: numero di sorgenti nel prossimo preflight **30, non piu' 29**. Gli hash storici rimangono evidenza congelata del precedente checkout, non devono essere alterati.

**Semantica della rubrica:** `CANDIDATE` non significa corretta; validazione dei riferimenti E### dalla traiettoria originale, osservazioni non vuote/troncate, metriche/unità letteralmente visibili (sempre senza garanzia fisica), contraddizioni aritmetiche `all`, `REQUIRES_VERIFICATION` vs `NOT_FORMALIZABLE_CONTRADICTION`; `INSUFFICIENT_EVIDENCE` distinto da `INVALID_OUTPUT`. L'analizzatore restituisce sempre `diagnostic_correctness_verified=false`, `physical_units_verified=false`, `causal_transfer_verified=false`, `ood_test_performed=false`. Gli stati upstream `BLOCKED_DEPENDENCY`/`PROVIDER_ERROR` provengono dal ledger, non si inventano raw K. Nessuna esecuzione di pseudocodice, provider, GT, Market o file scientifici. Le 180 run rimangono non autorizzate, `LIVE_API_ENABLED=False`.

**Prossima azione singola:** verificare la nuova suite su PyCharm e poi source preflight/blueprint offline mirati sul cambiamento 29→30, senza rieseguire l'intera batteria storica. Se PASS, nuovo preflight Colab GT-free con SHA e 30 sorgenti; solo dopo congelare release/policy e chiedere approvazione pilota D. Prima di Colab e' ancora necessario approvare la versione di HEAD corretta.

## 40. Rubrica K: 18 test PyCharm PASS (15 novembre)

Dopo l'introduzione della rubrica preregistrata (sezione 39), l'utente ha eseguito:
`python -m unittest discover -s src/tests -p "test_rq2_v2_k_quality_rubric_offline.py" -v`.
Output: `Ran 18 tests in 0.206s\nOK`. Questi sono test sintetici: non equivalgono a valutazione di regole K reali, causalita' o OOD.

**Prossimo controllo mirato:** il file `src/evaluation/rq2_v2_unified_release_preflight.py` e' cambiato SOLO per includere `evaluation/rq2_v2_k_quality_rubric.py` nell'inventario source-bound (30 file). PyCharm deve ora eseguire le suite dipendenti dalla lista `SOURCE_PATHS`: `test_rq2_v2_unified_release_preflight_offline.py` (19 test), `test_rq2_v2_unified_release_blueprint_offline.py` (18), `test_rq2_v2_unified_scientific_release_contract_offline.py` (18). Sono **55 test mirati, NON ANCORA ESEGUITI**. Non rieseguire i 145 precedenti.

Solo se passano: preparare preflight su Colab dei **30 sorgenti**, runtime/source hash GT-free aggiornati e commit clean. L'ultimo check Colab valido su 29 sorgenti resta prova storica e non certifica la nuova rubrica. Ancora 0/180 stage reali; nessuna nuova approvazione economica o API; `LIVE_API_ENABLED=False` e 11 OOD LOCKED.

## 41. SOURCE GATE K: tutte e tre le suite PyCharm PASS (15 novembre)

**Output integrale dell'utente in file incollato, attestato per il checkout locale**:
- `test_rq2_v2_unified_release_preflight_offline.py`: `Ran 19 tests in 0.723s — OK`;
- `test_rq2_v2_unified_release_blueprint_offline.py`: `Ran 18 tests in 0.490s — OK`;
- `test_rq2_v2_unified_scientific_release_contract_offline.py`: `Ran 18 tests in 0.939s — OK`;
- comando PowerShell finale: `RQ2-V2 K RUBRIC SOURCE GATE: PASS`.

**55/55 PASS**, aggiunti ai precedenti **18/18 PASS** della rubrica K: **73 nuovi test mirati PASS** sul cambiamento, senza rifare le 145 verifiche già superate. Questi sono unit test offline, non certificazioni della sorgente reale su Drive e non sono esecuzioni provider.

**Prossimo e unico gate:** Google Colab, *read-only* su Drive `/content/drive/MyDrive/Tesi_OpenRCA`, checkout worktree temporaneo clean al nuovo HEAD esplicito, `PYTHONPATH` SDK pin isolato `/content/rq2_v2_pinned_sdk_py313` + checkout `src`, esecuzione effettiva `preview_unified_source_bound`, `build_unified_release_blueprint`, `preview_scientific_ledger_gate`. Richiedere 30 sorgenti fingerprint, D/C/K 60 ciascuno, 180 stage, 11 OOD locked, namespace futuro assente, nessuna ground truth, api calls 0, nessuna release. Non copiare il vecchio source inventory SHA su 29 sorgenti: e' un riferimento storico valido per un altro commit.

Se esito PASS, registrare esatti SHA 30-source/plan/blueprint e *solo poi* procedere al release freeze. Restano `LIVE_API_ENABLED=False`, 0/180 stage reali, nessun consenso API, Opzione B bloccata. RQ1 e precedenti RQ2 separati. Paper e trascrizioni del relatore non richiesti adesso; refactoring/comenti italiani/post-audit repository solo a fine raccolta dati.

## 42. Colab preflight reale 30 sorgenti PASS, rubric K inclusa (15 novembre)

Output dell'utente su Colab effettivo, checkout pulito su commit `feb7b7c9684138f348d8a6e3e6e9d4eb61798ae7`, SDK pin isolato + split/manifest GT-free reali:
`RQ2-V2 30 SOURCE: PASS — 0 API REALI`,
`status=RQ2_V2_30_SOURCE_REAL_GT_FREE_PASS_NO_API`,
`runtime_snapshot_verified=true`,
`source_file_count=30`,
`source_inventory_sha256=8c2d022efed45214fec27b31ab4d7215f2912cd494aa6e16d3afaa55d8e891a1`,
`k_rubric_sha256=d8b969d33e2e042ab44121a9b6e089fa96a4aa2b8be03cb31b3edeede6f83f52`,
`source_plan_sha256=e6f797c4ca01ed422b80e928854469b9f8c7f7cc4215835bf91f9f7305425a00`,
`blueprint_sha256=22005361b35c9873822fec37163cd55f00d4a2a1c697a5939ac0a5a4ec3b9270`,
`split_sha256=c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`,
`manifest_sha256=5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`,
`C_system_prompt_sha256=81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42`,
`K_system_prompt_sha256=0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71`.
Per modello `D=20,C=20,K=20`, 180 stage; 11 OOD LOCKED; `ledger_namespace_absent=true`, `ground_truth_read=false`, `model_requests_sent=0`, `can_execute_api=false`, `scientific_release_frozen=false`. Checkout temporaneo rimosso. Documento completo:
`docs/ood/RQ2_V2_UNIFIED_COLAB_30_SOURCE_K_RUBRIC_REAL_GT_FREE_PASS_2026-11-15.md`.

**Attenzione al commit:** la verifica reale riguarda ESATTAMENTE `feb7b7c...`; i successivi commit di SOLA documentazione non impongono nuovi test del codice ma la release operativa richiede una SHA finale clean verificata. Il preflight 29-source originale e' valido solo per il vecchio commit, non deve essere riciclato.

**Prossimo step tecnico-scientifico:** review non autorizzativa della futura release G4E/G4F e del dispatcher con `LIVE_API_ENABLED=False`, identificando ogni prerequisito prima di un singolo D pilot. Non dichiarare congelata una release che non e' stata creata. La decisione del relatore di privilegiare precisione rispetto ai costi non elimina la necessita' di un consenso esplicito e di un budget tecnico positivo della release. Non toccare RQ1, precedenti RQ2, 11 OOD; 0/180 stage reali.

## 43. Preparazione prerelease senza API (15 novembre, codice offline nuovo)

Dopo `RQ2-V2 30 SOURCE: PASS — 0 API REALI` sul commit di codice `feb7b7c9684138f348d8a6e3e6e9d4eb61798ae7` e dopo la documentazione dei digest, l'utente ha autorizzato a **proseguire nell'ingegnerizzazione**, NON a inviare chiamate API.

Per evitare di cambiare o rieseguire inutilmente i 30 sorgenti di produzione gia' verificati e' stato aggiunto **SOLO sotto src/tests/**:
- `rq2_v2_unified_release_dossier_offline.py`: dossier prerelease read-only, pure in-memory, controllo fail-closed identita' 30 source SHA, rubrica K, piano 180, blueprint SHA e runtime pinned; primo stage pianificato `cloudbed-1_q032:gemini:A0:D`. NON genera release G4E, non crea approvazione, nessun claim, nessun API; nessun `release_sha256` valido.
- `test_rq2_v2_unified_release_dossier_offline.py`: **14** test sintetici con fixture G4E gia' esistenti, inclusi gate di mancata autorizzazione, commit SHA, 30 SHA, SDK e OOD. **DA ESEGUIRE**; non dichiarare PASS prima dell'output PyCharm.

Commit prima della nota `03b8b15ba2b31168267e92d70fd9891580af58df`. Confronto GitHub rispetto al `da4b63c1561e7f656ef4aa89454ed91ae6da793a`: SOLO i due file nuovi in src/tests; zero mutazioni di SOURCE_PATHS o degli agenti, `LIVE_API_ENABLED=False`, 0/180 reali, 11 OOD locked.

**Prossima singola azione per utente**: `git pull --ff-only` del nuovo commit esatto e PyCharm `python -m unittest discover -s src/tests -p "test_rq2_v2_unified_release_dossier_offline.py" -v`; attesi 14 test, non attestati. Se PASS, un'UNICA cella Colab GT-free puo' ricostruire G4A+G4B su checkout pinned e invocare `build_prerelease_dossier` in memoria, senza file scientifici o provider. Questa review non sostituisce il futuro freeze definitivo e il consenso stage D.

**Passaggio di chat:** l'handoff resta fonte primaria. Prima di cambio, comunicare utente branch, ultimo SHA documentale, codice verificato `feb7...`, hash 30-source `8c2d022efed45214fec27b31ab4d7215f2912cd494aa6e16d3afaa55d8e891a1`, obiettivo di raccolta e gate ancora chiusi. Non ripetere le suite 73 PASS né 29/30-source Colab in assenza di nuovi sorgenti.

## 44. Dossier prerelease offline: 14/14 PyCharm PASS; trasferimento nuova chat (15 novembre)

L'utente ha eseguito la nuova suite `test_rq2_v2_unified_release_dossier_offline.py`: output esatto `Ran 14 tests in 0.841s\nOK`. **14/14 PASS**. Nelle modifiche recenti della rubrica K e del dossier sono PASS anche `18/18` e `55/55` (totale **87/87 nuovi test mirati**, senza contare altre suite storiche). Il risultato e' soltanto offline/sintetico, NON un'autorizzazione, una release reale, ne' una chiamata provider.

Ultimo commit sorgenti realmente verificato nel preflight Colab 30/30: `feb7b7c9684138f348d8a6e3e6e9d4eb61798ae7`, con `source_inventory_sha256=8c2d022efed45214fec27b31ab4d7215f2912cd494aa6e16d3afaa55d8e891a1`, `k_rubric_sha256=d8b969d33e2e042ab44121a9b6e089fa96a4aa2b8be03cb31b3edeede6f83f52`, `blueprint_sha256=22005361b35c9873822fec37163cd55f00d4a2a1c697a5939ac0a5a4ec3b9270`, `source_plan_sha256=e6f797c4ca01ed422b80e928854469b9f8c7f7cc4215835bf91f9f7305425a00`. In Colab `/content/Tesi_OpenRCA_RQ2_Unified_Preflight`, SDK isolati `/content/rq2_v2_pinned_sdk_py313` Python 3.13, Drive `/content/drive/MyDrive/Tesi_OpenRCA`. Inizio RQ2 V2 unificata: `0/180` stage reali, 11 OOD LOCKED, `LIVE_API_ENABLED=False`, nessuna release ancora congelata.

Il nuovo codice del dossier vive SOLO in `src/tests/rq2_v2_unified_release_dossier_offline.py` (pure in memory, non autorizzativo), con i 14 test `src/tests/test_rq2_v2_unified_release_dossier_offline.py`. La documentazione `RQ2_V2_UNIFIED_DISCOVERY_RELEASE_READINESS_REVIEW_2026-11-15.md` e' aggiornata. Da `feb7...` i nuovi commit hanno modificato soltanto `docs/` e i due file `src/tests/`, nessun file source-bound incluso nei 30 sorgenti.

**Una sola azione successiva nella nuova chat**: preparare un preflight Colab READ-ONLY di `build_prerelease_dossier` con i veri source_preview/blueprint rigenerati nel worktree clean al nuovo HEAD pinned, utilizzando 2 CSV GT-free, `PYTHONPATH=DEPS:worktree/src`, `assert_exact_runtime_snapshot`, `preview_unified_source_bound`, `build_unified_release_blueprint` e `preview_scientific_ledger_gate`, poi il dossier in memoria e relativo audit invarianti; stampare SHA ottenuti, nessun file scientifico o provider. Non riavviare le suite PyCharm PASS ne' 503/429/stallo o altre prove superate senza nuovi cambiamenti necessari. Dopo il dossier PASS, progettare il freeze operativo per il pilot D, con consenso esplicito utente per il singolo stage e un budget positivo autorizzato separatamente; mai attivare in anticipo `LIVE_API_ENABLED`.

Scadenza tesi 1 dicembre 2026. Il relatore preferisce precisione scientifica a micro-ottimizzazione costi, ma non significa consenso illimitato. Refactoring/commenti italiani/rimozione file solo DOPO campagna e audit su branch distinto. Non chiedere di nuovo paper/trascrizioni finche' le informazioni sono sufficienti. RQ1 e RQ2 V1 congelati, 4 discovery Opzione A, 11 OOD Opzione B ancora bloccati.

## 45. Preferenze permanenti dell'utente per la continuita' delle chat e le fonti del relatore

Richiesta esplicita dell'utente: **in ogni conversazione successiva**, monitorare proattivamente la lunghezza/complessita' della chat e segnalare quando conviene aprirne una nuova per evitare perdita di contesto. Poiche' non e' disponibile un contatore affidabile e preciso del limite tecnico, avvisare **con anticipo prudente** quando la conversazione diventa lunga, senza pretendere di conoscere l'esatta saturazione. Prima di consigliare il cambio, aggiornare l'handoff su GitHub con branch, HEAD, commit source verificato, output scientifici, gate chiusi e prossima azione; poi fornire un messaggio pronto da incollare nella nuova chat.

L'utente chiede inoltre di **indicare spontaneamente quando servono di nuovo paper, documenti, appunti o precedenti trascrizioni/registrazioni delle conversazioni con il professore** per risolvere una specifica decisione scientifica. Se il contesto verificabile e' gia' sufficiente, non richiederli inutilmente; se sono necessari, dire esattamente quale materiale manca e perche'. Queste preferenze valgono per tutte le chat in cui prosegue la collaborazione, non solo per la prossima.

Non usare queste istruzioni per avviare test, modificare protocolli scientifici o autorizzare chiamate API. Stato precedente invariato: 14/14 dossier offline PASS; next Colab read-only dossier; source preflight 30/30 PASS sul commit `feb7b7c9684138f348d8a6e3e6e9d4eb61798ae7`; RQ2-V2 0/180 API, OOD 11 LOCKED.

## 46. Dossier prerelease Colab GT-free REALE PASS; next freeze decision (15 novembre 2026)

**Output dell'utente dalla cella Colab:** `RQ2_V2_REAL_GT_FREE_PRERELEASE_DOSSIER_PASS_NO_API`; riga conclusiva `DOSSIER PRERELEASE: PASS — 0 API LLM`, `CHECKOUT TEMPORANEO: RIMOSSO`. Git pin `4733eb90a67a784410d911ec227061b0a68a48e9`, checkout clean, SDK isolati e sorgenti GT-free presenti. `build_prerelease_dossier` eseguito in memoria con `preview_unified_source_bound`, `build_unified_release_blueprint`, `preview_scientific_ledger_gate`. Dossier `PRERELEASE_DOSSIER_REVIEW_ONLY_NO_AUTHORITY`, 30 sorgenti, inventory SHA `8c2d022efed45214fec27b31ab4d7215f2912cd494aa6e16d3afaa55d8e891a1`, K SHA `d8b969d33e2e042ab44121a9b6e089fa96a4aa2b8be03cb31b3edeede6f83f52`, blueprint SHA `22005361b35c9873822fec37163cd55f00d4a2a1c697a5939ac0a5a4ec3b9270`, piano SHA `e6f797c4ca01ed422b80e928854469b9f8c7f7cc4215835bf91f9f7305425a00`, split e manifest invariati. Modelli 3, D/C/K 20 ciascuno per modello, totale 180. `runtime_snapshot_verified=true`, `ground_truth_read=false`, `can_execute_api=false`, `can_run_ood_test=false`, `ood_test_cases_locked=11`, `provider_requests_sent=0`, `scientific_claims_written=0`, `release_sha256=null`, `ledger_namespace_absent=true`. Test PyCharm 14/14, 18/18 e 55/55 PASS gia' acquisiti, non ripetere senza ragione.

**Verifica con connettore GitHub:** commit `feb7b7c9684138f348d8a6e3e6e9d4eb61798ae7` -> `4733eb90a67a784410d911ec227061b0a68a48e9`: 8 commit, solo `docs/` e 2 file `src/tests/`, nessun file dei 30 `SOURCE_PATHS` modificato. Il PASS Colab e' riferito esattamente a `4733eb90...` e non ai commit documentali successivi.

**Nuovo documento di evidenza (docs-only):** `docs/ood/RQ2_V2_UNIFIED_PRERELEASE_DOSSIER_COLAB_GT_FREE_PASS_2026-11-15.md`, creato col commit `09ac49ff63877e74cc6c06e12544e945c315a00f`. Nessun file di produzione modificato.

**PROSSIMO GATE:** review del percorso di freeze scientifico: dispatcher G4K ancora `LIVE_API_ENABLED=False`; qualunque successivo cambio di questo sorgente richiede un **nuovo** HEAD pulito, audit GT-free dei 30 sorgenti e nuove fingerprint, senza riutilizzare hash non piu' validi. Prima di release G4E/G4F servono importo USD positivo approvato, riferimento esterno autentico e SHA canonico della release approvato separatamente; il limite economico non e' un hard cap. Ulteriore consenso esplicito per solo `rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:D` prima di qualunque API. Non creare oggi release_v1.json, claim, record o stage. RQ1 e RQ2 V1 frozen; Opzione B 11 OOD LOCKED. Nessun nuovo paper del professore necessario per questo gate.

**Attenzione Git pin:** successivi commit *documentali* aggiornano HEAD senza cambiare le 30 sorgenti; quando la versione live sara' approvata occorrera' verificare sul nuovo commit finale e annotarlo prima del freeze. Non far coincidere una review non autorizzativa con un permesso di spesa/API.

## 47. G4L release create-only writer HARD-DISABLED, suite nuova PENDING (15 novembre 2026)

L'utente ha autorizzato la **preparazione tecnica** della versione necessaria al futuro pilot, esplicitamente **non** le API o una release reale. E' stato creato un **branch separato** `feature/rq2-v2-scientific-release-writer-prep-2026-11-15` dalla documentazione verificata `f08737dcfce20ef84bebc70ea1c1446c09c28bd7`.

Verifica del codice G4K: il dispatcher live era gia' implementato e aveva 18/18 test fake PASS; non e' stato riscritto o abilitato (`LIVE_API_ENABLED=False`). Per completare il prossimo gate e' stata aggiunta al modulo G4F gia' source-bound `src/evaluation/rq2_v2_unified_scientific_ledger.py` una funzione `create_authorized_scientific_release_once` e **`SCIENTIFIC_RELEASE_WRITE_ENABLED=False`**. Il blocco avviene prima di qualsiasi filesystem/SDK; la futura scrittura e' create-only + lock + O_EXCL + fsync + readback, subordinata a G4D, runtime pinned, G4A/G4B, G4E, SHA esterno, budget e approvazione reale, e comunque NON autorizza il dispatcher API. Aggiunta nuova suite `src/tests/test_rq2_v2_unified_scientific_release_writer_offline.py` con **9 test offline NON ANCORA ESEGUITI**; esercita il percorso ipotetico con mock e TemporaryDirectory, non con Drive/API reali. Documento dettagliato: `docs/ood/RQ2_V2_UNIFIED_G4L_RELEASE_WRITER_HARD_DISABLED_PREP_2026-11-15.md`.

**Nuova azione singola dell'utente:** aggiornare PyCharm sul nuovo branch e lanciare solo `python -m unittest discover -s src/tests -p "test_rq2_v2_unified_scientific_release_writer_offline.py" -v`, con `PYTHONPATH=src`. Attesi 9, ma NO dichiarazione PASS senza output. Se fallisce, diagnosticare e correggere chirurgicamente. Solo dopo il PASS valutare test G4F dipendenti dal ledger e nuovo Colab reale source-bound. Test prerelease 87/87 e 18 G4K PASS rimangono evidenza storica, non ripetere indiscriminatamente.

**Nuovo source fingerprint OBBLIGATORIO:** il numero di SOURCE_PATHS resta 30 ma il codice di `rq2_v2_unified_scientific_ledger.py` e' cambiato. Vecchi SHA `source_inventory_sha256=8c2d022...` e `blueprint_sha256=220053...` sono validi **solo per il commit `4733eb90...`**, NON per il nuovo branch. Dopo eventuale approvazione live servira' un ulteriore clean HEAD e nuovo audit 30 sorgenti GT-free: NON inventare digest o retrodatare il preflight.

**Gate ancora bloccati:** `SCIENTIFIC_RELEASE_WRITE_ENABLED=False`, `LIVE_API_ENABLED=False`; nessuna release vera, 0/180 stage reali, 11 OOD TEST locked, nessun GT, RQ1 congelata. Budget positivo USD reale, approvazione esterna di SHA release e consenso separato per `rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:D` ancora mancanti. Scadenza tesi 1 dicembre 2026; rigore prima della micro-ottimizzazione, ma nessun consenso a spesa/API implicito. Nessun nuovo paper/trascrizione del relatore richiesto per questo test.

## 48. G4L 9/9 PASS su PyCharm, prossima regressione G4F mirata (15 novembre 2026)

**Nuovo output utente:** `Ran 9 tests in 10.624s\nOK` per `src/tests/test_rq2_v2_unified_scientific_release_writer_offline.py`: **G4L 9/9 PASS** nel checkout locale. Suite test sintetici offline, nessuna release vera, API o file scientifico. Non ripetere G4L senza variazione tecnica.

**Unico passo successivo:** poiche' G4L ha modificato `src/evaluation/rq2_v2_unified_scientific_ledger.py`, eseguire **solo** regressione G4F direttamente dipendente `python -m unittest discover -s src/tests -p "test_rq2_v2_unified_scientific_ledger_offline.py" -v` (22 test esistenti, NON ancora rieseguiti su questo branch). Evitare suite storiche G4K/RQ1/87 prerelease o Colab duplicati. Prima di PyCharm controllare `git pull --ff-only origin feature/rq2-v2-scientific-release-writer-prep-2026-11-15` e `git rev-parse HEAD` contro l'ultimo commit solo documentale.

**Poi, se G4F PASS:** predisporre una nuova cella Colab *read-only* GT-free su checkout clean del commit G4L, con preflight G4A/G4B/G4D, 30 source, runtime pinned, digest G4L nuovi; **NON** confrontare con vecchio inventory/blueprint SHA validi sul commit `4733eb90...`. NON modificare flag `SCIENTIFIC_RELEASE_WRITE_ENABLED=False` e `LIVE_API_ENABLED=False`, nessuna chiamata provider, release o claim; Opzione B 11 OOD locked, RQ2-V2 0/180 reali. Per rendere possibile il pilot restano da decidere budget USD positivo operativo/stop policy, commit clean finale, release SHA approvato esternamente e consenso separato per `cloudbed-1_q032:gemini:A0:D`. Paper/trascrizioni professore non necessari ora.

## 49. G4F regressione 22/22 PASS; nuovo Colab GT-free G4L (15 novembre 2026)

**Output reale utente PyCharm** su branch di preparazione release writer: `Ran 22 tests in 15.074s\nOK` per `test_rq2_v2_unified_scientific_ledger_offline.py` (G4F). Totale controlli mirati post-modifica G4L: **9 G4L + 22 G4F = 31/31 PASS**, entrambi offline/mock, non esecuzioni provider e non firme di release. Non ripeterli senza cambiamenti correlati. Documentato anche in `docs/ood/RQ2_V2_UNIFIED_G4L_RELEASE_WRITER_HARD_DISABLED_PREP_2026-11-15.md`.

**Prossima singola azione**: una cella Google Colab, su checkout temporaneo clean al **nuovo HEAD pinned** del branch `feature/rq2-v2-scientific-release-writer-prep-2026-11-15`, con sorgenti GT-free reali `/content/drive/MyDrive/Tesi_OpenRCA` e SDK pinned `/content/rq2_v2_pinned_sdk_py313`. Eseguire `assert_exact_runtime_snapshot`, `preview_unified_source_bound` (30 SOURCE_PATHS), `build_unified_release_blueprint`, `preview_scientific_ledger_gate`, `build_prerelease_dossier` **in memoria**, stampando nuovo `source_inventory_sha256`, nuovo `blueprint_sha256`, SHA esatto del file ledger G4F, piano/split/manifest/rubrica K/prompt e condizioni negative. **Non confrontare i nuovi source inventory/blueprint SHA con i vecchi valori**: e' cambiato `src/evaluation/rq2_v2_unified_scientific_ledger.py` (G4L), che e' uno dei 30 file. Le altre identita' (rubrica K, piano, split, manifest, prompt C/K) devono essere identiche; test OOD 11 locked, 180 stage, `ground_truth_read=false`, `can_execute_api=false`, `SCIENTIFIC_RELEASE_WRITE_ENABLED=False`, `LIVE_API_ENABLED=False`. Checkout temporaneo rimosso e nessun file scientifico scritto.

La precedente release resta **NON** creata; `release_sha256=null`, namespace assente, API 0, claim 0, RQ2-V2 0/180. Il primo candidato pilot resta `rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:D`. Per il futuro freeze dopo eventuale autorizzazione a modificare i flag sara' necessario un nuovo HEAD/nuove fingerprint, approvazione economica reale distinta e consenso API specifico. Non ripetere prove storiche in massa, non toccare RQ1 né 11 OOD, non chiedere nuovi paper/trascrizioni in questa fase.
