# RQ2 — Ablazione D→K: L1 e L2 sulle 8 candidate senza causa (risultati, 18 novembre 2026)

**Stato.** L1 eseguito su Colab (commit `570d831`, report `data/rq2_dk_l1_l2_v1/l1_report_dk.json` su Drive, create-only). **L2 non eseguito: nessuna candidata D→K è ammessa**, come dichiarato in anticipo (protocollo, sezione 8.2). Analisi esplorativa e post hoc (Emendamento 1, sezione 8 di `RQ2_ABLAZIONE_DK_PROTOCOLLO_2026-11-18.md`). Codice, parametri, tabella semantica e catalogo sono quelli congelati il 16 novembre; gli hash dei moduli sono stati verificati prima di eseguire.

## 1. Risposta in breve

D→K **non ha prodotto un risultato concreto in più** di D→C→K. Con le definizioni fissate prima di leggere i dati:

| Livello | D→C→K (congelato) | D→K (senza causa) |
|---|---|---|
| 0. candidate proposte da K | 8 | 8 |
| 1. eseguibili e formalizzabili (nodo/container, una sola classe) | 1 | 1 |
| 2. ammesse a L2 | 1 | **0** |
| 3. verdetto L2 `VERIFICATA_OPERATIVAMENTE` | 0 (`NON_VERIFICATA`, 2 FP su 7) | non applicabile |

Nessuna delle due pipeline ha prodotto una regola verificata. Nel run con C la regola ammessa è stata respinta da L2; nel run senza C l'unica candidata formalizzabile non è arrivata a L2.

## 2. Confronto L1

| | D→C→K | D→K |
|---|---:|---:|
| candidate | 8 | 8 |
| non formalizzabili (KPI di servizio, log o trace) | 5 | 5 |
| eseguibili (solo nodo/container) | 3 | 3 |
| — non classificabili (nessuna firma diretta delle 4 classi) | 2 | 2 |
| — formalizzabili (una sola classe) | 1 | 1 |
| ammissibili a L2 (unità, storia, condizioni) | 1 | 0 |
| ammesse a L2 (ammissibili e L1 passato) | 1 | 0 |

I conteggi sono identici a ogni livello tranne l'ammissione. È una coincidenza dei numeri, non una prova di equivalenza: le celle coinvolte sono in gran parte diverse.

## 3. Le 8 candidate D→K

| # | Caso | Modello / harness | Regola (sintesi) | Esito L1 |
|---|---|---|---|---|
| 1 | cloudbed-2_q026 | Haiku A0 | tasso di successo di adservice-grpc sotto baseline con eccezioni nei log | non formalizzabile (log e metriche di servizio) |
| 2 | cloudbed-1_q032 | Sonnet A0 | memoria alta, throttling CPU e span lunghi di cartservice-0 | non formalizzabile (include `span_duration`, una traccia) |
| 3 | cloudbed-1_q050 | Sonnet A0 | throttling CFS del container diverso da zero | eseguibile, **non classificabile**; L1 passato; scatta su 15-21 dei 40 container, a seconda del caso |
| 4 | cloudbed-2_q045 | Sonnet A0 | timeout DNS nei log di productcatalogservice e successo gRPC degradato | non formalizzabile (log, metrica di servizio) |
| 5 | cloudbed-2_q026 | Sonnet A1 | picco di `system.io.util` e salto di `system.disk.used` sul nodo | eseguibile, **non classificabile**; L1 passato; scatta su 2 componenti in q026 e q045, su nessuno in q032 e q050 |
| 6 | cloudbed-2_q045 | Sonnet A1 | burst di errori di connessione al DB nei log di productcatalogservice | non formalizzabile (log) |
| 7 | cloudbed-1_q032 | Sonnet A1_8R | throttling CPU di cartservice-0 e latenza `mrt_max` | non formalizzabile (metrica di servizio) |
| 8 | cloudbed-1_q032 | Sonnet A1_8R_Planning | cambio di `container_start_time_seconds` (riavvio osservabile) | **formalizzabile** (container process termination); L1 passato; **non ammissibile: `unita_incoerente`** |

Le ipotesi di guasto scritte dal modello sono solo provenienza: tutte dichiarano di non essere una causa verificata. I numeri di scatto sono sui 4 incidenti di discovery, gli stessi che hanno prodotto le regole: non dicono nulla sulla selettività.

## 4. Celle in comune con il run con C

Tre celle sono candidate in entrambi i run: Sonnet A0 su q050, Sonnet A1 su q045, Sonnet A1_8R_Planning su q032. In tutte e tre **il tipo di regola è lo stesso** (throttling CFS; errori di connessione MySQL nei log; riavvio del container) e quindi anche la categoria L1, ma **nessuna regola ha lo stesso hash**: il testo, le soglie o le etichette cambiano.

Le altre 5 candidate di D→C→K (Gemini 4, Haiku 1) non ci sono più in D→K, e le 5 nuove di D→K (4 non formalizzabili, 1 non classificabile) non c'erano prima. Nessuna delle celle che cambiano ha prodotto una candidata formalizzabile, in nessuna direzione.

## 5. Perché la candidata formalizzabile non è ammessa

L'ammissione a L2 richiede, oltre a L1 passato, che l'unità dichiarata nella regola non sia incoerente con il nome del KPI. `container_start_time_seconds` suggerisce «secondi»; il modello ha dichiarato un'etichetta che il controllo congelato non riconosce, quindi la candidata è segnata `unita_incoerente` e non è ammessa. Il controllo è quello pre-registrato e non è stato modificato.

- Il blocco dipende dall'etichetta scritta dal modello, non dal comportamento della regola: la regola ha passato L1 (esegue, popolazione 40 container su 42, valutabili al 100%).
- L'etichetta esatta e le altre condizioni (aggregazione, finestra, soglia) **non sono nel report stampato**: vanno lette dal record K. Fino a quel momento non si può dire se la regola sia equivalente a quella del run con C, né che cosa darebbe L2.
- Sui 4 incidenti di discovery la regola scatta su 1 componente in q032 (10 celle vere su 1200) e in q045 (2 su 1200), su nessuno in q050 e q026.

## 6. Che cosa si può e non si può dire

**Si può dire**
- Con le stesse evidenze, K senza la causa di C ha prodotto lo stesso numero di candidate (8) e la stessa ripartizione L1 (5 / 3 / 2 / 1) del run con C.
- Nessuna candidata D→K è arrivata a L2; quindi non c'è nessun risultato di verifica operativa da confrontare con quello del run congelato.
- In entrambi i run, la quota di candidate che usa solo KPI di nodo/container è 3 su 8, e quella con una sola classe 1 su 8.

**Non si può dire**
- Che C sia utile o inutile (4 incidenti, una esecuzione per cella, nessuna replica).
- Che la candidata bloccata sarebbe stata verificata o respinta da L2.
- Che la differenza di ammissione (1 contro 0) sia dovuta a C: dipende da un'etichetta di unità, in una sola esecuzione.
- Che L2 su D→K sarebbe cieco: i sigillati erano già stati aperti.

## 7. Seguito possibile (non eseguito)

1. **Leggere la regola bloccata** (sola lettura dei due record K, quello con C e quello senza) per vedere etichetta di unità, aggregazione, finestra e soglia, e dire se le due regole sono equivalenti nel contenuto.
2. **Solo se** le condizioni risultano equivalenti e con un secondo emendamento dichiarato post hoc: un'analisi di sensibilità che esegue L2 sulla candidata ignorando **solo** il controllo sull'etichetta, riportata a parte e mai al posto del risultato di questo documento.
3. Replica dei 60 K senza C per stimare la variabilità tra due esecuzioni dello stesso passo (60 chiamate a pagamento).
