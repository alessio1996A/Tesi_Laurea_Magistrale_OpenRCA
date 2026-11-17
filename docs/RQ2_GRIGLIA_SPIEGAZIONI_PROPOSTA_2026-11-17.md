# RQ2, analisi delle spiegazioni e dello pseudocodice: griglia (PROPOSTA, non ancora congelata)

Data: 17 novembre 2026. Stato: **CONGELATA il 17 novembre 2026, approvata da Alessio, prima di leggere qualsiasi testo.**
Fonte unica delle richieste: trascrizione del relatore (REGIS 3). Nessun uso del protocollo L1/L2.

## Cosa chiede il relatore (da REGIS 3)

1. far spiegare all'LLM perché ha identificato l'errore (la regola);
2. farsi dare uno pseudocodice per implementare la regola;
3. confrontare quanto sono dettagliate le spiegazioni dei diversi modelli;
4. usare casi non usati nello sviluppo (gli incidenti di discovery, già fuori dallo sviluppo).

## Materiale (nessuna nuova chiamata a modelli)

60 testi del passo C (spiegazione) e 60 record del passo K (regola candidata, pseudocodice):
3 modelli (Gemini, Sonnet, Haiku) x 5 harness x 4 incidenti di discovery. I record sono quelli già congelati.

## Griglia del passo C (spiegazione), 5 criteri, 0 o 1 ciascuno

- C1 nomina un tipo di guasto (anche con parole proprie);
- C2 cita almeno un segnale concreto (nome della metrica o del componente);
- C3 spiega perché quel segnale indica quel guasto (meccanismo);
- C4 indica quando (orario o intervallo) coerente con le evidenze citate;
- C5 dichiara incertezza o ciò che manca.

Punteggio di dettaglio C = somma 0-5.

## Griglia del passo K (pseudocodice), 5 criteri, 0 o 1 ciascuno

- K1 condizione di attivazione esplicita (metrica e operatore);
- K2 soglia o criterio quantitativo (non solo "alto");
- K3 finestra temporale, durata o baseline;
- K4 componente o livello a cui si applica;
- K5 implementabile senza ambiguità da un altro lettore.

Punteggio di dettaglio K = somma 0-5. Le astensioni (`insufficient_evidence`) si contano a parte, con il motivo.

## Due passate, in questo ordine

1. **Dettaglio**, senza conoscere la classe vera dell'incidente (sola lettura dei testi e dei campi C1-C5, K1-K5).
2. **Correttezza**, dopo: la classe nominata coincide con la vera, con un elenco di sinonimi fissato prima della passata.

## Regole di lettura (fissate ora)

- si riportano tutti i risultati, qualunque sia la direzione, per modello e per harness;
- solo conteggi e medie descrittive, nessun test inferenziale (n = 20 per modello e per passo);
- il confronto per modello non può essere cieco sul modello (è l'oggetto del confronto);
- limite dichiarato: il lettore è un modello della famiglia Claude e potrebbe favorire il proprio stile;
  per questo Alessio rilegge un campione di 12 testi (20%) e si riporta l'accordo;
- la griglia non cambia dopo aver visto i testi; se un criterio si rivela ambiguo si dichiara, non si corregge.

## Dichiarazioni aggiunte il 17 novembre, DOPO il congelamento (non cambiano i criteri)

1. **Dove si applica C1-C5.** Letti i testi estratti, il passo C contiene solo una breve etichetta della causa
   e il componente; la spiegazione estesa e' nel testo libero del passo D. I criteri C1-C5 si applicano quindi
   al **testo libero del passo D** (e l'etichetta del passo C si riporta a parte). I criteri non cambiano; cambia
   l'oggetto a cui si applicano, per errore di individuazione dell'oggetto nella proposta.
2. **La passata 1 non e' del tutto cieca.** Per i due incidenti di cloudbed-1 (q032, q050) la classe vera
   l'ho ricavata io da `record.csv` in questa sessione, e in precedenza ho fatto una lettura non cieca. Si
   dichiara. Mitigazione: il campione di 12 testi riletto da Alessio con la classe nascosta deve includere
   testi di tutti e quattro gli incidenti.
3. **K non letto.** Al momento della dichiarazione i record K non erano ancora stati letti.
