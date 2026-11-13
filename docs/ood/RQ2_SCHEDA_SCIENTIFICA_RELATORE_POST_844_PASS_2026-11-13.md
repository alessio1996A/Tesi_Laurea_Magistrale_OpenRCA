# RQ2 — Scheda scientifica per il relatore dopo il gate tecnico V2

**Data:** 13 novembre 2026  
**Tesi:** Harness Engineering per LLM applicato alla Root Cause Analysis — OpenRCA  
**Stato del documento:** bozza di discussione con il relatore, **non** un nuovo protocollo firmato, **non** un'autorizzazione API  
**Branch:** `experiment/rq2-provenance-v2-offline-2026-11-13`  
**Scadenza consegna:** 1 dicembre 2026

## 1. Messaggio centrale (una frase)

La prima campagna RQ1 ha prodotto un confronto reale e valutato con lo scorer ufficiale; la seconda linea RQ2 esplora la diagnosi su classi escluse e la generazione di regole candidate. Durante la discovery RQ2 è emerso un problema di tracciamento delle chiamate ai tool, per il quale è stata sviluppata una variante V2 **tecnicamente verificata offline**, ma **la generalizzazione e il trasferimento operativo delle regole non sono ancora dimostrati**.

## 2. Quello che è stato realmente ottenuto

### RQ1 — confronto harness/modelli sul benchmark

- Evaluation20: 20 incidenti × 5 varianti harness (A0, A1, A1_8R, A1_8R_Planning, A1_PAVE) × 3 modelli = **300 tentativi pianificati**.
- **295 run complete e 5 errori provider Gemini**, non trasformati in punteggi fittizi.
- Scoring Microsoft ufficiale già eseguito, analisi pairwise con denominatori e intervalli; **i risultati RQ1 sono congelati**.
- Questa parte della tesi documenta l'effetto delle diverse configurazioni dell'harness sulla qualità diagnostica e il loro trade-off operativo. I dati di accuratezza e token devono essere riportati con gli effettivi denominatori di ogni confronto, senza confondere token con costo fatturato.

### RQ2 V1 — discovery su classi riservate (parziale, eseguita davvero)

- Split originario: **4 casi discovery** e **11 query test OOD** (in **10 gruppi temporali test**, perché due query condividono la finestra). I casi OOD test rimangono **LOCKED**.
- Modelli candidati Gemini, Sonnet, Haiku; harness A1 e A1_8R; stadi **D = diagnosi**, **C = cause probe su evidenze**, **K = regola candidata**.
- Discovery pianificata: **72 stage logici**, non 72 chiamate HTTP. Stato reale osservato: **39/72 stage**, di cui **28 RECORDED_COMPLETE, 4 INVALID_OUTPUT, 7 BLOCKED_DEPENDENCY**; 24 stage Gemini, 15 Sonnet, 0 Haiku.
- **32 tentativi provider** e 7 stage bloccati offline, senza secondo tentativo sui claim esistenti. Dal report di audit V1 risultano **823.656 token osservati** (363.753 Gemini, 459.903 Sonnet): non sono un costo USD certificato.
- Tre D Sonnet hanno restituito JSON finale valido ma sono state registrate `INVALID_OUTPUT` perché il bundle di evidenze non poteva associare senza ambiguità tool call e tool result omonimi in parallelo. Il fallimento è **di provenance**, non prova di diagnosi errata.
- I 39 record e gli status V1 rimangono **immutabili**. Non si reinterpretano retroattivamente le tre D come valide né si ritentano richieste già reclamate.

### RQ2 V2 — correzione tecnica, non nuova campagna empirica

- Il nuovo esecutore preserva il vero `tool_call_id` negli eventi tool-call e tool-result, senza costruire ID fittizi; i validatori conservano la logica **fail-closed**.
- Runner reale RQ1 usato **con preparazione del caso e LLM/tool simulati**; provati end-to-end D→C→K e il nuovo store/journal V2 create-only, separato dal V1 e **deliberatamente synthetic-only**.
- Il 13/11/2026 la suite completa PyCharm ha restituito `Ran 844 tests in 80.612s / OK` — **844/844 test software superati**, non 844 diagnosi.
- Rispetto al commit V1 di partenza, confronto Git verificato: **28 file aggiunti, 0 file preesistenti modificati** alla chiusura del gate tecnico; nessun protocollo V1 alterato.
- **Non** è stata svolta una campagna provider V2, non sono stati acquisiti nuovi risultati RCA reali V2 e non sono state valutate le 11 query OOD test.

## 3. Domande scientifiche da NON confondere

Le definizioni qui sotto **riprendono i criteri precedenti** di `RQ2_REVIEW_SCIENTIFICO_PRIMA_RELEASE_2026-11-12.md` e
`RQ2_SCORING_E_FORMALIZZABILITA_PREREG_CANDIDATE_2026-11-12.md`, senza presentarle come protocollo V2 già firmato.

| Domanda | Misura proposta | Quale conclusione consentirebbe |
|---|---|---|
| **RQ2-A — riconoscimento OOD** | Classe di guasto proposta in **C**, derivata da evidenze D, confrontata con le reference ufficiali solo in scorer offline separato; accuratezza primaria `correct / 11` per arm, errori/missing/astensioni nel denominatore | Generalizzazione della **classificazione fault-type** sulle query OOD definite, con incertezza elevata; **non** di per sé successo del trasferimento di regole |
| **RQ2-B — generazione delle K** | Conteggio di `candidate`, `insufficient_evidence`, errori, blocked; citazioni E### corrette; verifiche statiche di metrica, unità, aggregazione, soglia, missing e controesempi | Capacità di **proporre** regole strutturate; JSON valido **non** è un detector eseguibile né causalmente validato |
| **RQ2-C — uso delle regole K** | Solo dopo freeze delle K formalizzabili: regole deterministiche verificate, confronto su gruppi OOD (10 gruppi temporali; attenzione a multi-guasto), TP/FP/TN/FN/abstain dove valutabili | Primo test diretto di trasferibilità operativa; se **zero** K formalizzabili, il risultato negativo è informativo e **non** va nascosto |

**Importante:** nel piano originario si prevedevano **132 stage test OOD** (11 casi × 2 harness × 3 modelli × D/C) oltre ai 72 discovery, per un totale di 204 stage *logici*; tali stage test **non sono stati eseguiti**. Non dare per scontato che debbano essere tutti eseguiti prima della tesi.

Il denominatore di 11 query non coincide con 11 episodi fisici indipendenti: `cloudbed-1_q014` e `cloudbed-1_q030` condividono la stessa finestra. I risultati eventuali vanno descritti con cautela e, per la variabilità, aggregati per gruppo temporale quando opportuno.

## 4. Perché i test V2 NON sono una prova di knowledge transfer

Il test V2 riproduce chiamate parallele omonime tramite LLM finto e risposte note. Verifica che **il software non perda la provenienza** ed eviti attribuzioni spurie di evidenze. Non verifica se un LLM remoto:
1. formuli una causa corretta;
2. estragga una regola rilevante rispetto ai guasti reali;
3. produca segnali con unità/aggregazioni effettivamente disponibili;
4. trasferisca la regola a un incidente mai utilizzato nello sviluppo.

Il salto inferenziale «844 test OK → knowledge transfer dimostrato» sarebbe metodologicamente errato.

Anche un singolo pilot remoto sui **4 discovery già osservati** verificherebbe soprattutto la tenuta tecnica e l'uso reale della provenance, **non** una replica indipendente su classi/test mai visti.

## 5. Scelte da discutere con il relatore — proposta operativa

### Opzione A — fermare gli esperimenti RQ2 e documentare lo studio esplorativo

**Quando è corretta:** se non c'è tempo per completare un protocollo realmente source-bound, il freeze delle regole e un test indipendente prima del 1 dicembre.

**Risultato difendibile:** RQ1 come evidenza quantitativa principale; RQ2 come analisi di fattibilità D→C→K, failure analysis V1, correzione provenance V2 verificata offline, limiti e lavori futuri. **Non chiamare questa opzione dimostrazione di generalizzazione.**

### Opzione B — un pilot reale V2 circoscritto (solo dopo nuovo gate)

**Scopo legittimo:** dimostrare su un caso discovery un `tool_call_id` acquisito realmente dal provider, ricostruzione delle evidenze, schema D/C e registrazione integra nel **nuovo** archivio scientifico V2; preferire un caso scelto *a priori* e documentare che la scelta può essere motivata da un errore V1 già visto.

**Necessario prima del pilot:** implementare e testare un release/store V2 realmente source-bound (quello attuale rifiuta Market e dati reali); verificare code/requirements/SDK pin, manifest GT-free, prompt/contract, identità del run, politica retry/timeout, claim create-only, log token e costo, stop conditions, readback; nuova preregistrazione e approvazione esplicita all'uso dell'API. **Nessun retry degli stage V1**: si tratta, eventualmente, di un altro protocollo.

**Limite:** una D di pilot non completa da sola le fasi C/K, e una tripla D/C/K non dimostra RQ2-C né un miglioramento di accuratezza sul test OOD. Non promettere un certo numero di chiamate HTTP senza conoscere il comportamento multi-round e il prezzo/versione del provider.

### Opzione C — testare scientificamente il knowledge transfer (RQ2-C)

Si può proporre **solo** con tempo, formalizzazione e approvazione adeguati:
- scegliere ex ante arm dimostrativo (nei precedenti criteri: **A1_8R + Sonnet**), senza selezionarlo dopo avere visto i punteggi K;
- completare o dichiarare l'attrition della discovery, congelare le K e la policy di promozione a regola;
- verificare metriche/units/threshold esclusivamente su development autorizzato GT-free; **mai eseguire direttamente lo pseudocodice generato dall'LLM**;
- test OOD sbloccati solo dopo release scientifica autonoma, con scorer GT isolato *dopo* il freeze dei risultati modello;
- confrontare baseline e regole congelate sulle stesse unità/episodi, contabilizzando errore, astensione e costi senza selezione opportunistica.

**Vincolo:** 4 discovery già osservati, 11 query/10 gruppi test e scadenza ravvicinata rendono forti conclusioni statistiche non giustificate; una piccola dimostrazione deve essere chiamata per quello che è.

### Raccomandazione attuale (non decisione del relatore)

**Preparare la tesi RQ1 subito e tenere RQ2 in forma esplorativa fino a quando un pilot sia scientificamente giustificato e autorizzato.** Chiedere al relatore se ritiene necessario **un solo pilot tecnico** per documentare la correzione su provider reale. Non avviare automaticamente tutte le 72/204 stage, né sbloccare le 11 query OOD.

## 6. Testo breve da presentare oralmente (circa 90–120 secondi)

«Per la prima domanda di ricerca ho completato una valutazione su 20 incidenti OpenRCA, cinque configurazioni harness e tre modelli: 300 tentativi complessivi, 295 completati e 5 errori provider. I risultati sono stati valutati con lo scorer Microsoft e le differenze fra configurazioni sono analizzate separando accuratezza, token ed errori.

Per la seconda domanda avevo pianificato una fase di discovery e una fase test riservata, con una pipeline di diagnosi D, identificazione della causa C e proposta di regola K. Sui quattro casi discovery sono stati registrati 39 dei 72 stage pianificati. Tre diagnosi Sonnet, pur con risposta JSON valida, non hanno potuto superare l'audit delle evidenze perché nelle chiamate parallele allo stesso tool si perdevano gli identificativi delle invocazioni.

Ho isolato quindi la correzione in una V2 separata, conservando il comportamento precedente e aggiungendo il tracciamento degli identificativi originali. Il gate offline ha superato 844 test, compreso un flusso completo simulato fino a journal e archivio indipendenti. Non ho modificato né reinterpretato i risultati V1.

La questione ancora aperta è scientifica: questa correzione dimostra la consistenza della provenance, ma non dimostra ancora che le regole K si trasferiscano a nuove classi. Vorrei concordare se un piccolo pilot reale V2 abbia valore aggiunto per la tesi, oppure se presentare RQ2 come studio esplorativo e dare priorità alla scrittura e ai risultati RQ1 già consolidati».

## 7. Le tre decisioni concrete da ottenere

1. **Obiettivo essenziale della tesi:** è sufficiente RQ1 consolidata + RQ2 esplorativa con failure analysis e proof-of-engineering, oppure il relatore richiede una prova live V2?
2. **Eventuale pilot:** quale singolo caso discovery/arm e quale outcome tecnico si vogliono verificare? Perché il risultato aggiungerebbe conoscenza rispetto al gate sintetico? Se non c'è un beneficio chiaro, **non eseguire API**.
3. **Test OOD e regole K:** esiste davvero il tempo per freeze e valutazione indipendente? Se no, dichiarare il limite apertamente. Il relatore aveva escluso l'implementazione human-in-the-loop: menzionarla soltanto tra sviluppi futuri.

## 8. Checklist di integrità prima di qualsiasi nuovo tentativo

- V1, 39 record e scoring RQ1 immutati; nessun `INVALID_OUTPUT` retroattivamente corretto.
- Release V2 separata con commit, SHA input/source/runtime e layout di claim create-only: **ancora da implementare**, l'archivio corrente è synthetic-only.
- Nessun provider, telemetria o scorer letto dal solo documento.
- Quattro discovery già viste: eventuale pilot non è generalizzazione indipendente.
- Undici query test OOD **LOCKED** fino a freeze separato; nessuna label/test nel prompt, tool, selezione delle regole o sviluppo.
- Scorer separato solo dopo freezing di output; criterio fault-type lessicale e denominatore pianificato invariati se si conferma il protocollo precedente.
- Unità, soglie, missing e aggregazioni devono essere fisicamente verificati prima di promuovere K; `0` regole formalizzabili è possibile.
- Budget e token osservati distinti; assenza di hard cap USD preregistrato non è assenza di costo e non sostituisce un'autorizzazione di spesa.

## 9. Fonti e cronologia

**Rapporti interni del repository, non pubblicazioni esterne:**
- `docs/ood/RQ2_V2_844_844_GATE_TECNICO_CHIUSO_DECISIONE_SCIENTIFICA_2026-11-13.md` — gate tecnico e NO-GO API.
- `docs/ood/RQ2_DECISION_GATE_AFTER_39_DISCOVERY_RECORDS_2026-11-13.md` — audit reali RQ2 V1, token, tre D Sonnet e decisione di isolamento.
- `docs/ood/RQ2_REVIEW_SCIENTIFICO_PRIMA_RELEASE_2026-11-12.md` — proposta RQ2-A/B/C, 4 discovery/11 test, definizioni.
- `docs/ood/RQ2_DISCOVERY_PREREG_V1_CANDIDATE_2026-11-12.md` — piano 72/132 stage, pipeline D/C/K, source pin e limiti.
- `docs/ood/RQ2_SCORING_E_FORMALIZZABILITA_PREREG_CANDIDATE_2026-11-12.md` — scoring fault-type, formalizzabilità K, 10 gruppi temporali.
- `docs/ood/HANDOFF_RQ2_V2_CONTINUITA_2026-11-13.md` — stato operativo e passaggio di chat.

**Questo documento sintetizza evidenze già congelate e propone decisioni. Non modifica code, runtime, dataset, risultati o protocollo scientifico.**
