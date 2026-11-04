# Architettura e risultati OpenRCA V3 — presentazione al relatore

**Data:** 3 novembre 2026 · **Dataset:** Market, OpenRCA 1.0  
**Protocollo:** `openrca_harness_v2_five_agents_development_v3`  
**Commit sperimentale congelato:** `6747eecc77c1b2fff7d581c7284578b5c574b4f7`  
**Scorer originale Microsoft:** commit `2a481ae63cb045c3eadbeca9eddaa10ec1151979`  
**Campagna:** 8 incidenti development × 5 agenti × 1 replica = 40 run; 40 output salvati.

## Architettura del sistema

La pipeline separa l'elaborazione deterministica delle evidenze dal modello LLM.

1. `evaluation.experiment_runner` legge il manifest **senza ground truth**.
2. `agent.tool_factory` crea i cinque tool per service metrics, container
   metrics, node metrics, log e trace, vincolati a cloudbed e finestra ufficiale.
3. Per tutte le varianti tranne A0, `harness` costruisce un report compatto
   di metriche node/container, segnali mesh/runtime e qualità delle evidenze.
4. Per A1_8R e le varianti successive, `harness.rule_batch` aggiunge otto
   regole: R01, R02, R06, R07, R08, R09, R10, R11.
5. LangGraph gestisce il ciclo agente → tool → agente e la finalizzazione JSON.
   Il motore `graph_engine.py` è ReAct-style basato su tool calling;
   `verify_graph.py` aggiunge planner, verifica e finale.
6. L'output viene controllato in base ai sette task e salvato senza retry
   automatico. La ground truth è disponibile **solo nello scoring offline**.

## Denominazioni per la presentazione

| Nome leggibile | ID congelato | Funzionalità |
| --- | --- | --- |
| A0 | `A0` | Baseline + cinque tool |
| A1 | `A1_V2` | Evidenze deterministiche |
| A1_8R | `A1` | Evidenze + otto regole |
| A1_8R_Planning | `A1_VERIFY` | Otto regole + planner di verifiche mirate |
| A1_PAVE | `A1_VERIFY_ST` | Planning + contesto strutturale/temporale |

**A1_PAVE** rimane una denominazione sintetica: la variante è *ispirata*
a PAVE, ma **non implementa PAVE nella sua interezza e non certifica causalità**.

Dal 4 novembre 2026 i nomi della prima colonna sono anche quelli
**operativi per le nuove esecuzioni**. La mappa in
`agent.variant_names` mantiene la conversione con la seconda colonna.
Il runner usa `ExperimentConfig.variant_scheme="current"` per nuove run;
i runner dei piani esistenti dichiarano `"historic_v3"` e mantengono
i valori originali di `variant`, `run_id` e gli hash. Per evitare
collisioni, nuovi output V2 salvati dal runner finiscono nella
directory `data/results/v2/final_names_v1/`.

## Planner e verifica

Il planner di `harness.investigation_planner` è **deterministico**:
non invoca un modello. Identifica anomalie candidate già presenti nel report,
confronta le tool call precedenti, evita controlli duplicati, alterna
componenti node/container e propone fino a due verifiche mirate.
Per A1_8R_Planning e A1_PAVE il budget massimo totale resta 6 round:
fino a 4 round esplorativi e fino a 2 di verifica, più la finalizzazione.

Il contesto strutturale-temporale di A1_PAVE associa segnali della stessa
famiglia (CPU, memoria, read I/O) osservati sullo stesso host e ne registra
l'ordine temporale. Non ricostruisce una dipendenza applicativa certificata,
non è un giudice della risposta e non dimostra propagazione del guasto.

## Risultati ufficiali della coorte development

| Variante | Score medio | Diagnosi esatte | Token medi | Tempo medio (s) |
| --- | ---: | ---: | ---: | ---: |
| A0 | 0,0000 | 0/8 | 35.286 | 157,84 |
| A1 | 0,4062 | 2/8 | 48.659 | 170,76 |
| A1_8R | **0,5000** | **3/8** | 48.177 | 191,14 |
| A1_8R_Planning | 0,4375 | 2/8 | **32.144** | **101,67** |
| A1_PAVE | 0,2812 | 1/8 | 36.100 | 109,91 |

Conformità: 39/40 output accettati; unico errore di ordinamento
cronologico su `cloudbed-1_q027` di A1_8R, il cui score grezzo è comunque 0.
Costo complessivo **stimato** della campagna: $0,5122, non una fattura.

## Lettura critica dei risultati

- A0 → A1: miglioramento in 5/8 incidenti, peggioramento in 0/8.
- A1 → A1_8R: miglioramento in 2/8, peggioramento in 0/8.
- A1_8R → A1_8R_Planning: nessun miglioramento, un peggioramento,
  7/8 casi invariati; token medi −33,3%, tempo medio −46,8%.
- A1_8R_Planning → A1_PAVE: nessun miglioramento, due peggioramenti.
- `cloudbed-1_q066`: la regola R07 ha una denominazione
  `node CPU load` corrispondente all'etichetta ufficiale; il match
  lessicale è un possibile fattore del miglioramento.
- `cloudbed-2_q034`: A1_PAVE indica 00:32:40 anziché il riferimento
  00:46:49, con uno scarto di 14 minuti e 9 secondi.
- `cloudbed-2_q071`: la variante PAVE-inspired perde un criterio temporale.
- `cloudbed-1_q005` e `q027`: nessun agente identifica le classi
  di guasto di rete richieste; le otto regole non coprono queste classi.
- `cloudbed-1_q013`: nessun agente individua il componente richiesto
  e tutti sbagliano il timestamp oltre la tolleranza.

## Limiti metodologici da dichiarare

- Otto incidenti development, una sola replica: sono risultati preliminari,
  non una stima robusta di generalizzazione a tutto il benchmark.
- Le motivazioni dello scorer originale sono confrontate come stringhe esatte;
  sinonimi o denominazioni con suffissi possono perdere punti.
- La finestra development è stata valutata e analizzata anche tramite
  ground truth: **non riutilizzarla come test indipendente** di revisioni future.
- Le otto regole monitorano solo parte delle 15 classi di guasto.
- Non usiamo un checkpointer persistente LangGraph né trasferimento
  automatico di conoscenza fra incidenti.
- `v2_enforce` applica controlli cronologici ulteriori rispetto alla logica
  di permutazione dello scorer ufficiale; mantenere separati conformità e score.

## Demo e riproducibilità

Il notebook di presentazione è
`Tesi_OpenRCA/demo_relatore/Demo_Relatore_OpenRCA_V3.ipynb` su Google Drive.
Mostra telemetria, componenti, replay della tool trajectory, punteggi e grafici
**senza nuove chiamate Gemini**.

Gli artefatti di scoring sono su Drive in:
`data/results/scoring/v2/openrca_harness_v2_five_agents_development_v3/`.
Il commit congelato del 3 novembre rimane il riferimento degli output.

## Compatibilità della rinomina

- `ExperimentConfig(variant="A1")`: **nuovo** A1 senza otto regole.
- `ExperimentConfig(variant="A1_8R")`: A1 con le otto regole.
- `ExperimentConfig(variant="A1", variant_scheme="historic_v3")`:
  vecchio A1 delle run congelate, interpretato come A1_8R.
- Lo score già calcolato resta associato agli ID originali. La modifica
  del codice non equivale a una nuova validazione sperimentale.
- Eseguire la suite di test prima di impiegare il refactoring per
  un'eventuale nuova campagna.
