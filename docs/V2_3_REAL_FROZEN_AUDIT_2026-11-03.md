# Harness V2.3 — Risultati reali dell'audit sulle 32 risposte storiche

**Data:** 3 novembre 2026  
**Fonte:** output originale di Colab dell'audit `evaluation.v2_frozen_prediction_audit`, riferito dall'autore, più ispezione di alcuni JSON congelati.  
**Campioni:** 32 run su due protocolli **development**, non valutazione indipendente.  
**Nessuna API, nessun nuovo scoring, nessuna modifica dei file originali.**

## 1. Risultato V2.3 prima della scomposizione dei controlli

| Variante | Esecuzioni | Validità parser legacy | Tutti i controlli V2 |
|---|---:|---:|---:|
| A1-R8 (`A1`) | 8 | 7 | 5 |
| A1_VERIFY (nei due esperimenti) | 16 | 15 | 10 |
| A1_VERIFY_ST | 8 | 8 | 5 |
| **Totale** | **32** | **30** | **20** |

### Tipologia delle 12 non conformità V2

- **8 run:** almeno un `root cause occurrence datetime` fuori dall'intervallo semiaperto `[start_unix, end_unix)`, interpretato in `Asia/Shanghai`. Sono **violazioni della policy temporale interna V2**, non necessariamente JSON non validi o errori secondo lo scorer ufficiale.
- **2 run:** numero di guasti predetti diverso dal numero espresso nell'istruzione ufficiale (uno predetto per due richiesti e viceversa).
- **2 run:** manca il campo canonico `root cause reason`; appaiono al suo posto `root cause connection` oppure `root cause resource consumption`. Il parser legacy li marcava invalidi.

I conteggi per categoria derivano dalla prima esecuzione Colab; il nuovo audit che separa struttura e tempo deve ancora essere eseguito per produrre il breakdown ricontrollato.

## 2. Esempi di timestamp vicino al confine (NON ground truth)

- `cloudbed-2_q033`, A1-R8 e A1_VERIFY nello studio 1: entrambe le predizioni includono un guasto alle **00:30:20** rispetto a una finestra che termina alle **00:30:00**: **+20 secondi**. Formato/schema/campo presenti; fuori finestra di 20 s.
- `cloudbed-2_q073`, A1_VERIFY_ST nello studio 2: timestamp **00:01:20** rispetto a fine finestra **00:00:00** del giorno 22 marzo: **+80 secondi**.

Le previsioni originali non devono essere corrette usando questi confini né confrontate qui con etichette. Il controllo interno più severo va distinto dalle regole effettivamente richieste dal benchmark, che impongono uno schema JSON-like con le informazioni richieste e accettano elementi aggiuntivi. I benchmark task e lo scorer sono la fonte autorevole per misurare l'accuratezza; un controllo di plausibilità della finestra non è una misura di accuratezza causale.

## 3. Correzione metodologica

Il report V2 ora presenta campi distinti:

- `schema_cardinality_valid`: struttura canonica rigorosa + cardinalità dalla sola istruzione GT-free;
- `timestamp_in_window`: se le date predette ricadono nell'intervallo semiaperto;
- `temporal_outliers`: indice del guasto, data locale predetta, offset firmato dalla più vicina estremità e verso;
- `valid`: preserva il risultato del contratto V2 originale, cioè conformità a **tutti** i controlli interni;
- `error_breakdown`: errori strutturali/cardinalità separati da violazioni solo temporali.

La separazione consente di decidere se il confine temporale sia un vincolo **hard** del formato V2 o un avvertimento di plausibilità. La scelta va formalizzata **prima** dei nuovi esperimenti; non adattare la policy in funzione degli score vecchi.

## 4. Prossimo gate

1. Eseguire i nuovi test offline per V2.3 in PyCharm.
2. Rieseguire l'audit Colab sullo stesso freeze e leggere il **nuovo breakdown** e gli offset temporali **senza** cambiare raw_response.
3. Concordare la policy in V2: schema/cardinalità obbligatori, finestra di telemetria obbligatoria, data predetta fuori finestra da segnalare separatamente, salvo giustificazione formale di un vincolo hard.
4. Solo allora aggiungere la modalità di output V2 nel runner comune, con nuovi run ID e cartelle separate.

## 5. Vincoli da mantenere

Freeze V1, predizioni originali e scoring già eseguiti restano **immutabili**. R03–R05 non vengono promosse a regole diagnostiche. Nessun set `evaluation` o `ood_holdout` viene consultato per progettare la policy.
