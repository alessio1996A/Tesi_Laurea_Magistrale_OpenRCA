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

Nessuna delle due pipeline ha prodotto una regola verificata. Nel run con C la regola ammessa è stata respinta da L2; nel run senza C l'unica candidata formalizzabile non è arrivata a L2, ma **è operativamente la stessa regola** (stessa metrica, stesso operatore, stessa soglia, stessa aggregazione, stessa finestra; stessi numeri in L1): la differenza di ammissione dipende solo dall'etichetta dell'unità (sezione 5). Due delle tre candidate eseguibili di D→K riproducono rilevatori già presenti nel run con C; una sola è diversa (sezione 4).

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

I conteggi sono identici a ogni livello tranne l'ammissione. Le celle coinvolte sono in gran parte diverse (sezione 4), ma due delle tre candidate eseguibili sono operativamente le stesse del run con C.

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
| 8 | cloudbed-1_q032 | Sonnet A1_8R_Planning | cambio di `container_start_time_seconds` (riavvio osservabile) | **formalizzabile** (container process termination); L1 passato; **non ammissibile: `unita_incoerente`**; eseguibilmente identica alla regola congelata (sezione 5) |

Le ipotesi di guasto scritte dal modello sono solo provenienza: tutte dichiarano di non essere una causa verificata. I numeri di scatto sono sui 4 incidenti di discovery, gli stessi che hanno prodotto le regole: non dicono nulla sulla selettività.

## 4. Celle in comune con il run con C

Tre celle sono candidate in entrambi i run: Sonnet A0 su q050, Sonnet A1 su q045, Sonnet A1_8R_Planning su q032. In tutte e tre **il tipo di regola è lo stesso** (throttling CFS; errori di connessione MySQL nei log; riavvio del container) e quindi anche la categoria L1. **Nessuna regola ha lo stesso hash**, perché l'hash copre anche nome, testo ed etichette.

Per le due eseguibili il confronto con il report L1 congelato (`data/rq2_k_l1_v1/l1_report.json`) è numerico, caso per caso:

| Regola | Celle vere su 1200 (q032 / q050 / q026 / q045) | Componenti che scattano | Congelato | D→K |
|---|---|---|---|---|
| throttling CFS del container | 503 / 503 / 366 / 279 | 21 / 20 / 20 / 15 | identici | identici |
| riavvio del container (`container_start_time_seconds`) | 10 / 0 / 0 / 2 | 1 / 0 / 0 / 1 | identici | identici |

Numeri identici sui 4 incidenti vogliono dire stessa regola operativa. Per il riavvio l'ho verificato leggendo i due record (sezione 5); per il throttling CFS non ho letto le condizioni dai record, ma i dodici numeri coincidono esattamente. Il terzo caso in comune (log MySQL) non è eseguibile e non è confrontabile.

La terza candidata eseguibile di D→K, il picco di `system.io.util` con salto di `system.disk.used` (Sonnet A1, q026), è invece diversa dall'unica nodo del run con C (iowait, Gemini): vere 0 / 0 / 3 / 3 celle su 180 contro 1 / 3 / 3 / 0. Non è classificabile in nessuno dei due casi.

Le altre 5 candidate di D→C→K (Gemini 4, Haiku 1) non ci sono più in D→K, e le 5 nuove di D→K (4 non formalizzabili, 1 non classificabile) non c'erano prima. Nessuna delle celle che cambiano ha prodotto una candidata formalizzabile, in nessuna direzione.

## 5. Perché la candidata formalizzabile non è ammessa

Letti i due record K della stessa cella (`V5_RECORD_bca571e4…`, uno per archivio, sola lettura):

| | D→C→K (congelato) | D→K (senza causa) |
|---|---|---|
| nome della regola | `container_start_time_advance_restart_detector` | `cartservice_container_start_time_changed` |
| metrica | `container_start_time_seconds` | uguale |
| operatore e soglia | `> 0` | uguale |
| aggregazione e finestra | `delta`, 600 s | uguale |
| combinazione | `all` | uguale |
| **unità dichiarata** | `seconds` | `unverified (values look like Unix epoch seconds)` |

L'ammissione a L2 richiede che l'unità dichiarata non sia incoerente con il nome del KPI. `container_start_time_seconds` suggerisce «secondi»: l'etichetta `seconds` è riconosciuta, quella scritta senza C no, quindi la candidata D→K è segnata `unita_incoerente`. Il controllo è quello pre-registrato e non è stato modificato.

- **L'unità non entra nell'esecuzione.** L'esecutore delle regole non legge il campo (zero occorrenze nel sorgente). Con condizioni identiche e L1 identico, le decisioni di L2 sarebbero **per costruzione le stesse** della regola congelata: `NON_VERIFICATA`, 2 falsi positivi su 7. È una deduzione dal codice e dai record, non una misura: L2 non è stato eseguito su D→K.
- **Che cosa mostra il controllo.** Senza C il modello ha scritto l'unità come non verificata, coerentemente con il pacchetto di evidenze che dichiara le unità non verificate. Con C ha scritto `seconds` e nei limiti ha dichiarato che l'unità è presa solo dal nome del KPI. Il controllo premia l'etichetta che coincide con il nome, non la prudenza. È un limite della procedura di ammissione da dichiarare nella tesi; non cambia il risultato, perché l'esito non dipende dall'etichetta.
- Sui 4 incidenti di discovery la regola scatta su 1 componente in q032 (10 celle vere su 1200) e in q045 (2 su 1200), su nessuno in q050 e q026, come la regola congelata.

## 6. Che cosa si può e non si può dire

**Si può dire**
- Con le stesse evidenze, K senza la causa di C ha prodotto lo stesso numero di candidate (8) e la stessa ripartizione L1 (5 / 3 / 2 / 1) del run con C.
- Due delle tre candidate eseguibili di D→K (riavvio del container, throttling CFS) sono operativamente identiche a quelle del run con C, con numeri L1 identici sui 4 incidenti. La terza (nodo, I/O) è diversa e non classificabile.
- La candidata formalizzabile di D→K non è arrivata a L2 per un'etichetta di unità; il suo contenuto eseguibile è lo stesso della regola che L2 ha respinto.
- Nessuna candidata D→K ha prodotto un risultato di livello 2 o 3: quindi nessun risultato concreto in più rispetto a D→C→K.

**Non si può dire**
- Che C sia utile o inutile (4 incidenti, una esecuzione per cella, nessuna replica).
- Che L2 «ha respinto» la regola D→K: L2 non è stato eseguito; l'esito identico è dedotto dall'equivalenza esecutiva.
- Che la differenza di ammissione (1 contro 0) sia dovuta a C: dipende da un'etichetta di unità, in una sola esecuzione.
- Che L2 su D→K sarebbe cieco: i sigillati erano già stati aperti.

## 7. Seguito

1. ~~Leggere la regola bloccata~~ **Fatto** (sezione 5): condizioni identiche, differisce solo l'etichetta dell'unità.
2. **Analisi di sensibilità con L2: non necessaria.** Con condizioni identiche e un esecutore che ignora l'unità darebbe lo stesso verdetto della regola congelata; richiederebbe un Emendamento 2 post hoc senza aggiungere informazione. Non si esegue, salvo diversa decisione.
3. Replica dei 60 K senza C per stimare la variabilità tra due esecuzioni dello stesso passo (60 chiamate a pagamento): è l'unico passo che potrebbe dire quanto di questi confronti sia rumore.
