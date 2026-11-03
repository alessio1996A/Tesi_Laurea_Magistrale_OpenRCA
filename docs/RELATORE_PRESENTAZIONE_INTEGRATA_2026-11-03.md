# Presentazione integrata per il relatore — OpenRCA Market (3 novembre 2026)

**Obiettivo:** presentare l'architettura dell'harness, i due confronti sperimentali già congelati e il risultato di fattibilità GT-free delle tre regole di rete R03/R04/R05.  
**Branch documentale:** `presentation/relatore-2026-11-02`.  
**Notebook di grafici:** [Colab_Relatore_Risultati_e_Regole_2026_11_03.ipynb](../notebooks/Colab_Relatore_Risultati_e_Regole_2026_11_03.ipynb).  
**Nota tecnica dettagliata rete:** [network_r03_r05_feasibility_relatore_2026-11-03.md](network_r03_r05_feasibility_relatore_2026-11-03.md).  
**Esperimenti storici immutabili:** primo commit `6927fcfa18fc29fce64ad65eac98231b2ba42184`; secondo `138fb523efec4a665a2424ab2faedb698f10562e`.

> **Regola di lettura:** un grafico da scoring congelato è un risultato sperimentale ufficiale *development*; un grafico da audit dei KPI è una caratterizzazione *GT-free di osservabilità*, non una misura di accuratezza. Nessun dato del secondo studio va mescolato con il primo per ricavare un confronto tra cinque varianti.

## Scaletta proposta (circa 15 minuti, indicativa)

| Parte | Cosa mostrare | Messaggio centrale |
|---|---|---|
| 1. Problema e ipotesi | RCA in microservizi, Market 1.0, tool e harness | Preparare evidenze attendibili può cambiare qualità ed efficienza dell'agente |
| 2. Architetture | A0, A1_V2, A1-R8, A1_VERIFY, A1_VERIFY_ST | Evoluzione incrementale; cinque tool e otto regole hanno ruoli distinti |
| 3. Esperimento 1 | Grafici per caso, token e tempi | Il planner riduce token e tempi ma non migliora lo score medio |
| 4. Esperimento 2 | Grafico delta appaiato, token e tempi | ST dà un delta medio positivo, non robusto: 1 vittoria, 1 sconfitta, 6 pareggi |
| 5. Fattibilità R03/R04/R05 | Grafici KPI A/4–A/6 | I segnali disponibili non bastano per aggiungere detector causali container-level |
| 6. Discussione | Contributo e lavoro futuro | Concordare scopo finale e priorità della tesi prima del 1 dicembre |

## 1. Architettura dei cinque agenti

| Variante | Caratteristica | Stato della valutazione rappresentata |
|---|---|---|
| **A0** | LLM esplora la telemetria tramite cinque tool | Versione di riferimento, **nessuno score appaiato congelato da rappresentare qui** |
| **A1_V2** | Preprocessing/evidence engineering, senza otto regole | Passaggio architetturale, **nessuno score appaiato congelato da rappresentare qui** |
| **A1-R8** (nello scoring storico: `A1`) | A1_V2 + otto regole deterministiche | Esperimento 1 |
| **A1_VERIFY** | Stesso harness R8, più planner con max 4 round esplorativi e 2 verifiche mirate | Esperimenti 1 e 2 **su coorti diverse** |
| **A1_VERIFY_ST** | Come VERIFY, con contesto strutturale-temporale aggiunto solo nella finalizzazione | Esperimento 2 |

Gli strumenti di telemetria sono **cinque**; i detector R01, R02, R06–R11 sono **otto**. Sono livelli architetturali differenti. Il verificatore ST associa lessicalmente nodo e container e confronta alcuni segnali temporali/cross-layer: non ricostruisce un percorso causale RPC validato e non equivale a PAVE completo.

### Le otto regole implementate

- R01: container CPU load; R02: container memory load; R06: container read I/O load.
- R07: node CPU load; R08: node memory consumption; R09: node disk read I/O consumption.
- R10: node disk write I/O consumption; R11: node disk space consumption.

**Quattro altre categorie restano riservate OOD** nel protocollo: node CPU spike, container write I/O load, container process termination e container packet loss. Non vanno recuperate come nuovi casi per tarare i tre detector mancanti.

## 2. Primo confronto congelato — A1-R8 vs A1_VERIFY

**Commit del codice eseguito:** `6927fcfa18fc29fce64ad65eac98231b2ba42184`.  
**Coorte:** 8 casi development appaiati, 16 run, `gemini-3.5-flash-lite`; evidenze iniziali controllate e scoring ufficiale dopo freeze.

| Indicatore | A1-R8 | A1_VERIFY |
|---|---:|---:|
| Score medio ufficiale | **0,3850** | 0,3225 |
| Score esattamente 1 | 2/8 | 1/8 |
| JSON validi | 7/8 | **8/8** |
| Token totali | 474.590 | **258.649** |
| Tempo end-to-end totale | 709,365 s | **598,321 s** |

**Interpretazione:** la nuova policy riduce i token del **45,50%** e il tempo del **15,65%**; **non** migliora lo score medio, che diminuisce di 0,0625. La policy ha modificato il percorso investigativo, non ha prodotto una verifica causale. Il campione di 8 casi non giustifica dichiarazioni di generalizzazione.

**Artefatti:**  
Freeze `data/protocols/a1_verify_paired_development_v1_results_freeze_v1.json`, SHA-256 `e8c350d3e3372d0e4afb6fd63d60f2f5632394bc7e2a4b996ca0ff864ae2ccf0`.  
Scoring `data/results/scoring/a1_verify_paired_development_v1_official_scoring_v1.json`, SHA-256 `2504295d89f49c20c5e14da552ee176e54e52286cc2f86c417755367a814fb5f`.

**Grafici Colab:** `01_score_casi_r8_verify.png`, `02_token_r8_verify.png`, `03_tempo_r8_verify.png`.

## 3. Secondo confronto congelato — A1_VERIFY vs A1_VERIFY_ST

**Commit del codice eseguito:** `138fb523efec4a665a2424ab2faedb698f10562e`.  
**Coorte:** **otto casi development diversi** dal primo confronto, 16 run, stesso modello, stessi otto detector e stesso budget 4+2. Cambia solo il contesto ST aggiunto alla finalizzazione.

| Indicatore | A1_VERIFY | A1_VERIFY_ST |
|---|---:|---:|
| Score medio ufficiale | 0,2288 | **0,2913** |
| Score esattamente 1 | 0/8 | 1/8 |
| JSON validi (parser legacy) | 7/8 | **8/8** |
| Token totali | **318.154** | 349.266 |
| Tempo end-to-end totale | 536,519 s | **520,649 s** |

**Delta score medio:** +0,0625 ST−VERIFY. **Esito appaiato:** 1 miglioramento, 1 peggioramento e 6 pareggi. Il miglioramento complessivo dipende in misura importante dal caso `cloudbed-2_q053`: **non** rimuovere questo caso dal risultato ufficiale. Token ST **+9,78%**, tempo **−2,96%**.

**Limite essenziale:** non c'è evidenza di superiorità stabile su nuovi incidenti. ST aggiunge contesto osservativo, non la prova di un nesso causale o una verifica della propagazione.

**Artefatti:**  
Freeze `data/protocols/a1_verify_st_paired_development_v1_predictions_frozen_v1.json`, SHA-256 `43e646792685b1cde03052cadc2c8a82749d058a4e04ee0b01f607a7384fd104`.  
Scoring `data/results/a1_verify_st_paired_development_v1_official_scoring_v1.json`, SHA-256 `26f10169e379f9a8ceabcd83923ae7daa72ca90f705e021d77e6eb5772027f45`.

**Grafici Colab:** `04_delta_score_st.png`, `05_token_st.png`, `06_tempo_st.png`.

### Come NON interpretare i numeri

Lo score 0,3225 di A1_VERIFY del primo confronto e quello 0,2288 di A1_VERIFY del secondo **non** significano che l'agente sia peggiorato tra due versioni: sono **due coorti diverse**. Non esiste un confronto appaiato su tutti e cinque gli agenti; A0 e A1_V2 compaiono nella mappa architetturale, non in grafici di performance con valori inventati.

## 4. Le tre regole proposte: risultati dell'audit GT-free A/1–A/6

**Audit A/1–A/6:** quattro finestre development selezionate (due per cloudbed), senza riutilizzo come valutazione blind. A/4 è riepilogo di profili; A/6 legge nuovamente solo le metriche di nodo e mesh sulle **stesse** finestre per accoppiare valori allo stesso timestamp. Nessuna nuova chiamata Gemini e nessuna etichetta letta nell'audit. Le statistiche sono **quelle comunicate dagli output Colab** il 3 novembre; i JSON integrali vanno conservati per una riproducibilità completa.

### R03 — Container network packet retransmission

Metriche trovate: `system.net.tcp.retrans_segs` e `system.tcp.retrans_pct`; contesto `system.net.tcp.in_segs`, `system.net.tcp.out_segs`.

**A/6:** 720/720 coppie numeriche sullo stesso nodo e allo stesso timestamp, tutte con contesto TCP. **274** entrambe positive, **116** solo `retrans_segs` positiva, **146** solo `retrans_pct` positiva, **184** entrambe non positive.

**Perché NON implementarla ora:** le metriche sono **node-level** e la classe è **container-level**. Le variazioni e i valori decimali di `retrans_segs` non consentono di affermare che si tratti di un contatore cumulativo grezzo; le unità e la trasformazione del KPI non sono accertate. La co-positività di due segnali nello stesso secondo non attribuisce la root cause a un container.

**Possibile impiego futuro:** indizio node-level con provenienza, senza diagnostica di causa container automatica.

### R04 — Container network packet corruption

**A/4:** tutti i **336** profili errori RX/TX container, i **336** profili pacchetti scartati container e i **48** profili errori packet a livello nodo hanno massimo pari a zero. Totale **720/720 profili sempre nulli** nelle finestre ispezionate.

**Perché NON implementarla ora:** manca variabilità discriminante nelle evidenze osservate; errori/drop generici, anche se fossero diversi da zero, non distinguerebbero necessariamente corruzione da altre cause. Questo risultato negativo non dimostra che i KPI siano sempre nulli sull'intero dataset.

### R05 — Container network latency

**A/6:** `istio_request_duration_milliseconds.*` e `istio_requests.*` combaciano per cloudbed, finestra, componente, suffisso KPI e timestamp. **33.960/33.960** coppie numeriche: **14.679** entrambe positive, **4** solo durata positiva, **2.558** solo richieste positive, **16.719** entrambe non positive.

**Perché NON implementarla ora:** la durata della richiesta RPC può incorporare computazione lato server e code applicative. Quindi non coincide necessariamente con sola latenza di rete. Per isolare una latenza di comunicazione servirebbe una verifica semantica e uno studio di trace parent/child, separato dall'attuale ablation.

**Grafici Colab:** `07_r03_tcp_node.png`, `08_r04_segnali_zero.png`, `09_r05_istio.png`.

## 5. Le conclusioni, senza oltrepassare l'evidenza

1. **Software realizzato:** A0, A1_V2, A1-R8, A1_VERIFY e A1_VERIFY_ST, cinque tool e otto regole deterministiche; pipeline di protocolli, freeze, scorer, audit e test offline.
2. **Risultato misurato 1:** la policy VERIFY riduce costo in token e tempo nel primo studio, ma non aumenta la media dello score.
3. **Risultato misurato 2:** ST migliora la media nel secondo studio, ma l'effetto è instabile e concentrato su pochissimi casi.
4. **Risultato di fattibilità R03–R05:** esistono segnali di rete osservabili, ma nessuna delle tre classi è **validata** come nuova diagnosi deterministica. R04 costituisce un *negative result* utile.
5. **Non ancora dimostrati:** migliore accuratezza su holdout/OOD, causalità del verificatore ST, replica di PAVE, knowledge transfer automatico in nuove regole.

## 6. Domande al relatore e proposta di lavoro

- Consideriamo il **contributo principale** l'engineering misurabile dell'harness (evidenze, regole, planner, contesto ST), invece di raggiungere a ogni costo 11 detector?
- È corretto documentare **R04 come risultato negativo** e R03/R05 come limiti/possibili estensioni?
- È più utile un *piccolo studio GT-free delle trace* per R05, separato e preregistrato, oppure dedicare il tempo residuo alla stesura e alla revisione?
- Possiamo inserire un capitolo prospettico sul possibile **trasferimento della conoscenza** dall'harness a nuove regole, con un protocollo futuro che richieda conferma indipendente, **senza** rivendicarlo come implementato?
- Confermiamo il perimetro necessario prima della **consegna della tesi del 1 dicembre 2026**?

## 7. Uso pratico dei materiali

1. In PyCharm mostrare `src/agent/tool_factory.py`, `src/harness/rule_batch.py`, `src/agent/verify_graph.py` e `src/harness/structural_temporal_verifier.py`.
2. Aprire il notebook `notebooks/Colab_Relatore_Risultati_e_Regole_2026_11_03.ipynb` tramite Colab/GitHub sul branch di presentazione.
3. Montare Drive con i risultati storici già archiviati. Le prime sezioni falliscono in modo esplicito se gli hash degli scoring e freeze non coincidono.
4. Eseguire le celle in ordine. I 9 grafici vengono salvati solo in `/content/relatore_grafici_2026_11_03/` e archiviati in `/content/relatore_grafici_2026_11_03.zip`; non ci sono chiamate Gemini.
5. Per verificare i tre grafici KPI dai report integrali, conservare i JSON A/4 e A/6 in `/content` oppure (se si desidera una copia distinta e non congelata) sotto `Tesi_OpenRCA/demo_relatore/audit_2026_11_03`. In assenza di questi file il notebook dichiara esplicitamente di visualizzare il riepilogo delle stampe Colab, non una rianalisi autonoma.

**Vincolo:** nessun output delle coorti originali viene sovrascritto, nessun test evaluation/OOD eseguito e nessuna regola R03–R05 aggiunta automaticamente.
