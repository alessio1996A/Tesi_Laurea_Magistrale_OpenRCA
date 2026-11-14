# RQ2-V2 unificata — Opzione A: cinque harness × tre LLM (BOZZA NON ESEGUIBILE)

**Data:** 14 novembre 2026.
**Scopo:** confronto controllato delle capacita' di generazione di conoscenza diagnostica da evidenze, **non** dimostrazione di trasferimento/generalizzazione OOD.
**Base git:** commit precedente `c2bed47a9f61ac6ac67223c47a9b55e680d6f0ee`, ramo `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.
**Stato:** `DRAFT_NO_API_NO_SCIENTIFIC_FREEZE`; nessuna release, nessun modello, nessun claim su Drive, nessun GT, nessun test OOD.

## 1. Perche' una versione comune

Il pilot `cloudbed-1_q050 / A1 / Sonnet` ha dimostrato il funzionamento reale della provenance D V2 con ID tool e della pipeline tool-free C/K, con esito K `insufficient_evidence`. Tale pilot **non** prova il comportamento di altre varianti o provider.

Lo storico RQ2 V1 (39/72 stage: Gemini 24, Sonnet 15, Haiku 0) e' **conservato e distinto**: le D Sonnet V1 con chiamate parallele ripetute allo stesso tool erano invalide per assenza dell'associazione univoca `tool_call_id` nella traiettoria. Non ripetere o reinterpretare i record V1.

RQ1 ha gia' comparato tutti i cinque harness e i tre provider su Evaluation20. RQ2 e' una domanda differente: verificare se l'harness modifica la capacita' di estrarre conoscenza **strutturata, evidentially grounded, falsificabile e potenzialmente formalizzabile**.

## 2. Disegno della discovery RQ2-V2

Quattro incidenti *discovery* preregistrati nella precedente coorte OOD:
- `cloudbed-1_q032`
- `cloudbed-1_q050`
- `cloudbed-2_q026`
- `cloudbed-2_q045`

**Non sostituire o aggiungere** gli 11 test OOD bloccati: non sono esempi di discovery. Da split GT-free, le 11 query test corrispondono a 10 gruppi temporali; lo scoring RQ2-C e' fuori da questa Opzione A.

Fattori:
- **5 harness** (nomi CANONICI): A0, A1, A1_8R, A1_8R_Planning, A1_PAVE;
- **3 modelli**: `gemini-3.5-flash-lite`, `claude-sonnet-5-5`, `claude-haiku-5-5`;
- **4 casi** indipendenti per selezione di discovery nella coorte, senza assumere indipendenza causale delle iniezioni;
- **3 stadi** logici per arm: D (diagnosi/strumenti), C (cause probe uniforme e tool-free), K (knowledge candidate uniforme e tool-free).

**Matrice totale prevista**: 4 × 5 × 3 = **60 D**; fino a **60 C** e **60 K** dipendenti, per **180 stage logici previsti** (non 180 HTTP). Per modello 20 D + 20 C + 20 K, per harness 12 D + 12 C + 12 K. Se D o C non completa, la K dipendente resta `BLOCKED_DEPENDENCY`, **resta nel denominatore** e non comporta un'API.

La coorte scelta non e' nuova rispetto agli output RQ2 V1; per questo non dire 'repliche indipendenti'. Le nuove run V2, se autorizzate, appartengono a un **nuovo protocollo e nuovo archivio**. Pilot Sonnet V2 q050/A1 gia' archiviato: non ricontarlo come prova V2 unificata o ritentarlo in assenza di un confronto formale/piano nuovo approvato.

## 3. Parita' nel trattamento

- `src/evaluation/experiment_runner.py` invariato, `ExperimentConfig.variant_scheme="current"`, `output_contract_mode="v2_enforce"`, 6 round tool totali, `recursion_limit=30`; per Planning/PAVE budget di verifica fissato `max_verification_checks=2` (**4+2**). Planner deterministicamente generato, **nessuna chiamata LLM aggiuntiva per generare il piano**. Non usare la variante 5+1 all'interno di questa matrice; e' ablation distinta.
- `A0`, `A1`, `A1_8R`: stesso `agent.graph_engine.crea_grafo_rca` e motore di esecuzione D `agent.rq2_v2_graph_engine.esegui_grafo_rca_v2` che preserva gli ID.
- `A1_8R_Planning`, `A1_PAVE`: `agent.verify_graph.crea_grafo_rca_verify` e `esegui_grafo_rca_verify` che gia' espongono `tool_call_id`, `origine=llm/planner`; NON farli passare per `crea_grafo_rca` generico per comodita'.
- Tool, prompt originale di diagnosi, regole standard e relative procedure rimangono quelli congelati RQ1. A0 differisce proprio per assenza dell'harness extra.
- D restituisce raw output e traiettoria; conservare anche `json_status`, errori, token, tempo. Il task originale della D puo' NON coincidere con il riconoscimento della classe di guasto: C e' la sonda uniforme sulla causa.
- **C** e **K** utilizzano esattamente gli stessi testi sistema, JSON contract e budget 1 richiesta tool-free per stage, indipendenti da modello/harness; K riceve la **C come ipotesi**, non come ground truth, e puo' astenersi legittimamente.
- Non passare al modello lo scorer Microsoft, etichette fault, `record.csv`, ragioni ufficiali o risposte di altri arm. Non inserire nomi delle classi come suggerimento di prompt.
- La verifica di K e' structurale, semantica e di formalizzabilita': il solo JSON valido non e' una buona regola. Pseudocodice LLM non viene eseguito.

## 4. Misure da predefinire (senza tuning sui risultati)

**Outcome di pipeline e K** per ogni arm/caso:
1. D: `RECORDED_COMPLETE / INVALID_OUTPUT / PROVIDER_ERROR` e integrita' della provenance; no falsi successi da JSON riparato.
2. C: `diagnosis / abstain / invalid / blocked`; conteggio delle evidenze E### citate, fallimenti preservati.
3. K: `candidate / insufficient_evidence / invalid / blocked`; `candidate` non significa accuratezza.
4. K: percentuale con riferimenti E### validi, condizioni e segnali non contraddittori, controesempi e astensioni presenti, `requires_verification` vs `not_formalizable`; policy di **formalizzabilita'** bloccata indipendentemente dalle candidate.
5. Costi: requests, input/output token anche con failure per singolo stage, latenza, stime USD quando verificabili, incompletezza usage.
6. Confronti **appaiati** tra harness sullo stesso caso+modello e tra modelli sullo stesso caso+harness. Riportare tutti e 15 gli arm e le astensioni, senza cherry-picking.

**Denominatori**: primaria la matrice pianificata (20 triplette per provider / 12 per harness) e report per outcome. Le percentuali `candidate` su sole K valide sono secondarie, per non favorire un modello che fallisce prima della K. Se report CI, bootstrap a livello di incidenti/gruppi temporali (non a livello di stage), intervalli ampi e confronti esplorativi per 4 casi.

**Non misuriamo ancora:** correttezza causa DNS/I/O, tassi TP/FP/TN/FN, precision/recall del trasferimento, robustezza a OOD, migliore generalizzazione, miglioramento significativo con n=4. Se vogliamo testare la generalizzazione serve un protocollo RQ2-C successivo e regole indipendentemente verificate/frozen.

## 5. Sicurezza, archiviazione e confini

- Una futura release **nuova** dovra' fissare code commit, split/manifest SHA, dipendenze, provider ID, configurazione per harness, prompt C/K hashes, policy no-retry/timeout, stage order, metering e per-stage spending authorization.
- Nuovo namespace di storage, create-only con claim durabile prima di ogni richiesta pagata e record immutabile dopo; separato da V1, dal pilot Sonnet V2 precedente e dai risultati RQ1. Audits readback e verifica SHA per ripartenze.
- Niente API o file su Drive fino a test PyCharm offline, audit GT-free su Colab, verifica di parita' dei **due motori** (ReAct/planner) con fake LLM che riproducano chiamate parallele duplicate, e consenso esplicito ai batch pagati.
- `src/evaluation/rq2_v2_unified_discovery_plan.py` genera soltanto piano offline e puo' verificare la partizione con `preview_gt_free_sources(data_dir)`; NO API, NO GT.
- `src/evaluation/rq2_v2_unified_provenance_gate.py` controlla `tool_call_id` nativi e pairing su una D gia' in memoria; NO esecuzione, NO scoring. Un'assenza di evidenze non e' diagnosis positiva; puo' portare ad astensione.
- Se un source gate fallisce, **stop senza indebolire il criterio**; la soluzione corretta e' determinare la causa e versionare il cambiamento tecnico, non alterare il protocollo o sovrascrivere un record.

## 6. Gate e milestone tecnici per l'implementazione unificata

1. **G1 — Ora**: piano 180 stage e provenance gate, entrambi offline, con test unitari sintetici. Non ancora una campagna V2.
2. **G2**: verifica con fake LLM di `run_experiment` su **tutte le 5 varianti e i 3 modelli**, dimostrando parita' di output/contatori e corretta gestione delle coppie `tool_call_id` anche nei due graph executor; controllo source-only e hash, nessuna API/Market reale.
3. **G3**: dispatcher unificato di D/C/K, release source-bound immutabile, record/claim create-only, error accounting, isolamento GT/OOD, policy finanziaria, test fake end-to-end su tutti gli arm. Nessuna API prima di questo gate.
4. **G4**: preregistrazione scientifica approvata e preflight Colab della coorte/ambiente; possibile piccolo pilot V2 di connettivita' prima della campagna, secondo autorizzazione.
5. **G5**: campagna completa **solo discovery** e analisi K appaiata; nessuna applicazione OOD.
6. **Fase successiva, distinta**: se davvero esistono K scientificamente formalizzabili, progettazione di generalizzazione con holdout indipendente e nuovo freeze.

## 7. Decisioni da portare al relatore

- Validare RQ2-A/B come studio *comparativo esplorativo* sulla produzione di conoscenza, non prova di trasferimento.
- Con solo 4 incidenti discovery nessun confronto statistico forte; decidere in anticipo se nuova coorte davvero indipendente e' disponibile. **Non** riassegnare le 11 OOD test alla discovery.
- Discutere se investire in un validatore semantico indipendente delle K oppure riportare soltanto grounding/astensione/formalizzabilita'. Una valutazione umana ad hoc post-hoc non deve essere descritta come metrica oggettiva non preregistrata.
- La scadenza 1 dicembre 2026 e' un vincolo, ma non autorizza scorciatoie o rigonfiamento dei risultati.

## 8. Test PyCharm mirati, ancora da eseguire

```powershell
git status --short
git fetch origin feature/rq2-v2-unified-five-harness-three-models-2026-11-14
git switch feature/rq2-v2-unified-five-harness-three-models-2026-11-14
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_discovery_offline.py" -v
```

**25 test attesi, PASS non ancora attestato.** Dopo l'output utente, procedere a G2 su un nuovo commit/branch.
