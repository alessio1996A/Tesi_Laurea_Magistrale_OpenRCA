# Bozza del Capitolo 2 — Benchmark e protocollo sperimentale (22 novembre 2026)

Stato: bozza di Claude da riscrivere con parole di Alessio (flusso concordato: Claude scrive e verifica sulle fonti, Alessio
riscrive e deve saper spiegare, Claude ricontrolla fatti, numeri e riferimenti, poi revisione indipendente GPT).
Convenzioni del modello del dipartimento: forma impersonale, citazioni autore-anno nella bozza (convertite in numeriche nel Word,
come nel Capitolo 1), figure e tabelle numerate per capitolo con didascalia autosufficiente e senza note sotto.
Il capitolo non contiene risultati: quelli stanno nei Capitoli 4 (RQ1) e 5 (RQ2). Descrive il banco di prova, le coorti,
le condizioni di esecuzione, le misure e i controlli. Le minacce alla validità specifiche dei risultati sono nei Capitoli 4 e 5;
qui stanno solo i limiti del protocollo.

Punti aperti (non fanno parte del testo del capitolo):
1. Formula esatta del punteggio parziale e modo in cui lo scorer confronta il motivo: da leggere in `main/evaluate.py`
   (SHA-256 `9a1c2351…`); il testo dice solo ciò che è documentato (criteri soddisfatti, non soddisfatti, punteggio tra 0 e 1;
   1 se tutti gli elementi richiesti coincidono).
2. Numero di estrazioni bootstrap del confronto primario del 9 novembre (relazione su Drive): il testo indica 10.000 estrazioni
   e seme fisso solo per l'analisi normalizzata del 19 novembre, dove sono documentati.
3. Popolazione appaiata di Gemini (18 coppie nel confronto primario, n = 19 in A0 e A1 nella normalizzazione): da chiarire prima del Capitolo 4.
4. Il fuso orario di risposta (Asia/Shanghai) è quello del prompt di sistema; il benchmark indica UTC+8.

<!-- CAP2:INIZIO -->
# Benchmark e protocollo sperimentale

Questo capitolo descrive il banco di prova e il protocollo con cui sono condotti gli esperimenti. Si presenta anzitutto il sistema Market di OpenRCA, con le sue query e lo scorer ufficiale. Si illustra poi la ripartizione dei casi nelle coorti usate per le due domande di ricerca e si descrivono i modelli e le condizioni comuni di esecuzione dell'agente. Seguono le misure, l'analisi statistica e i controlli adottati per garantire la riproducibilità. Il capitolo si chiude con i limiti del protocollo. Le cinque configurazioni dell'harness sono descritte nel Capitolo 3, mentre i risultati e la loro discussione si trovano nei Capitoli 4 e 5.

## Il sistema Market di OpenRCA

### Il sistema e la telemetria

Gli esperimenti usano la parte Market di OpenRCA 1.0 (Xu et al., 2025). Market è un sistema di commercio elettronico composto da 6 nodi, 40 pod e 10 servizi; ogni servizio è distribuito su 4 pod, in modo da tollerare il guasto di uno di essi. Possono essere causa radice tutti i nodi, tutti i pod e tutti i servizi. Se si guastano tutti i pod che ospitano un servizio, il guasto è considerato di livello servizio e non del singolo pod. Le cause possibili sono 15 e riguardano CPU, memoria, disco, rete e terminazione di processo. Nei casi di Market i componenti distinti indicati come causa radice sono 44 (Xu et al., 2025).

La telemetria comprende metriche, trace e log, in formato CSV, per circa 24,5 GB e 121 milioni di righe, ed è raccolta con fuso orario UTC+8 (Xu et al., 2025). I casi provengono da due ambienti di esecuzione, indicati come cloudbed-1 e cloudbed-2, con 70 e 78 casi rispettivamente, per un totale di 148.

### Query e obiettivi

Ogni caso è una query in linguaggio naturale. La query indica una finestra di 30 minuti e il numero di guasti che vi sono avvenuti, e chiede di individuare alcuni elementi della causa radice: il componente, l'istante o il motivo. Gli autori precisano che in una finestra di mezz'ora i guasti non sono di norma più di tre (Xu et al., 2025). I sette obiettivi del benchmark, riportati nella Tabella 2.1, combinano questi tre elementi. La risposta è un oggetto JSON con una voce numerata per ciascun guasto.

<!-- TABELLA:2.1 -->

Nel benchmark originale il prompt fornisce l'elenco dei componenti e dei motivi possibili, così che le risposte non differiscano per formulazione (Xu et al., 2025). In questa tesi l'agente non riceve tali elenchi. Riceve l'istruzione ufficiale della query, il nome del cloudbed e l'intervallo di tempo, espresso in secondi Unix, e deve ricavare gli identificatori dei componenti dalla telemetria. Il motivo è quindi un testo scritto dall'agente. Le etichette ufficiali dei motivi possono raggiungere l'agente solo attraverso le regole dell'harness descritte nel Capitolo 3, e per le quattro classi della RQ2 queste regole non esistono. La differenza va tenuta presente nel confronto con i valori riportati in (Xu et al., 2025) ed è ripresa tra i limiti del protocollo.

### La valutazione ufficiale

Le risposte sono valutate con lo scorer rilasciato con il benchmark, cioè il file main/evaluate.py del repository ufficiale di OpenRCA. La versione è fissata dal commit 2a481ae6 e il file è identificato dal suo hash SHA-256 (9a1c2351), che le analisi verificano prima di usarlo. Lo scorer riceve la risposta dell'agente e i punti di valutazione associati al caso, e restituisce i criteri soddisfatti, quelli non soddisfatti e un punteggio compreso tra 0 e 1. Il punteggio vale 1 quando tutti gli elementi richiesti coincidono con la verità di riferimento. Un istante è considerato corretto se cade entro un minuto da quello di riferimento (Xu et al., 2025).

Nel resto della tesi, per diagnosi esatta si intende una run con punteggio 1. L'accuratezza del lavoro originale è la quota di casi risolti (Xu et al., 2025), mentre il punteggio medio usato in questa tesi comprende anche i punteggi parziali; per questo le due misure sono riportate separatamente.

## Le coorti

### La partizione dei casi

I 148 casi di Market erano stati ripartiti dal progetto in quattro gruppi prima degli esperimenti riportati in questa tesi. La partizione, identificata da un hash SHA-256, non è stata modificata. La Tabella 2.2 riporta i gruppi e il loro uso, la Figura 2.1 ne mostra il flusso.

<!-- TABELLA:2.2 -->

<!-- FIGURA:2.1 -->

I casi coprono 15 classi di guasto. Otto sono coperte dalle regole diagnostiche descritte nel Capitolo 3: container CPU load, container memory load, container read I/O load, node CPU load, node memory consumption, node disk read I/O consumption, node disk write I/O consumption e node disk space consumption. Quattro sono state tenute deliberatamente fuori dallo sviluppo per la RQ2: node CPU spike, container write I/O load, container process termination e container packet loss. Le restanti tre sono classi di rete, cioè container network packet retransmission, packet corruption e latency; non hanno regole affidabili e non sono state riservate. Un controllo di separazione, eseguito sulla verità di riferimento in un processo distinto dall'inferenza e in forma aggregata, ha escluso le quattro classi della RQ2 dai gruppi di sviluppo e di valutazione. Esse compaiono soltanto nel gruppo riservato, dove sono tutti i 15 casi, e in 9 dei 18 casi del gruppo di quarantena.

### La coorte della RQ1

Per la RQ1 si distinguono due coorti. La prima è di sviluppo e comprende 8 incidenti del gruppo omonimo, sui quali l'harness e i protocolli sono stati messi a punto. Le 120 esecuzioni corrispondenti, cioè 3 modelli per 5 configurazioni per 8 incidenti, sono esplorative e sono riportate separatamente dalle altre.

La seconda coorte, chiamata EVALUATION20, comprende 20 incidenti scelti tra i 23 del gruppo di valutazione. La scelta è avvenuta prima di qualsiasi esecuzione sui nuovi incidenti, senza leggere verità di riferimento, telemetria, risposte o punteggi. I requisiti sono quattro: nessuna sovrapposizione temporale con i casi di sviluppo, di quarantena e riservati, né tra i casi scelti; 10 casi per ciascun cloudbed; tutti i sette obiettivi rappresentati; almeno un caso con più guasti per cloudbed. Nessuno dei 23 casi si sovrappone nel tempo ai casi degli altri gruppi. La selezione è deterministica: si prende il primo insieme di 20 casi che rispetta i requisiti, scorrendo i casi in un ordine fissato dall'hash SHA-256 di un seme e dell'identificativo del caso, quindi la scelta non dipende dall'accuratezza. I 20 incidenti scelti comprendono tre casi con più guasti. La disgiunzione temporale delle finestre non prova che gli incidenti siano statisticamente indipendenti.

Il disegno è 20 incidenti per 3 modelli per 5 configurazioni, con una replica per condizione, per un totale di 300 run.

### Le coorti della RQ2

La RQ2 usa il gruppo riservato, che contiene soltanto guasti delle quattro classi. I 15 casi sono divisi in due insiemi disgiunti. Quattro sono incidenti di scoperta, uno per classe, scelti in un audit separato dall'inferenza: su di essi gli agenti investigano e la pipeline produce le pseudoregole candidate. Gli altri undici sono incidenti sigillati, riservati al secondo livello di verifica e non consultati prima del congelamento delle regole.

I 15 casi formano 14 gruppi di finestre temporali disgiunte, perché due di essi condividono la stessa finestra. Casi che condividono la finestra sono trattati come un unico gruppo e non vengono separati tra le due fasi, quindi gli incidenti di scoperta sono 4 gruppi e quelli sigillati 10. Le finestre di scoperta distano più di un'ora da quelle sigillate sullo stesso cloudbed, come verificato da un controllo preliminare. Le finestre di questo gruppo non si sovrappongono a quelle degli altri gruppi, ma ciò non dimostra l'indipendenza causale dei guasti. Inoltre solo 8 dei 15 casi chiedono il motivo del guasto, e per gli altri la classe non è misurata dallo scorer ufficiale.

Sui quattro incidenti di scoperta la pipeline è eseguita per ciascuno dei tre modelli e delle cinque configurazioni, per un totale di 4 × 3 × 5 × 3 = 180 stadi, cioè diagnosi (D), interpretazione della causa (C) e proposta della regola (K). Un'ablazione esplorativa rilegge gli stessi record di D ed esegue K senza il passo C, per altri 60 stadi. I due livelli di verifica sono descritti nel Capitolo 5.

## Modelli e condizioni di esecuzione

### I modelli

Per la RQ1 e per il passo diagnostico della RQ2 si usano gli stessi tre modelli, riportati nella Tabella 2.3. I modelli e i loro identificativi sono fissati nel piano preregistrato e non sono ottimizzati per modello. Appartengono a due provider, Google e Anthropic, che conteggiano i token in modo diverso: i token si confrontano quindi soltanto tra configurazioni dello stesso modello, e le differenze tra modelli non sono lette come una graduatoria.

<!-- TABELLA:2.3 -->

### L'agente e gli strumenti

In tutte le configurazioni l'agente riceve l'istruzione ufficiale della query, il nome del cloudbed e l'intervallo di tempo in secondi Unix, e può leggere la telemetria soltanto entro quell'intervallo. Dispone di cinque strumenti, che leggono rispettivamente le metriche dei servizi, dei container e dei nodi, i log e le trace del cloudbed della query. Il prompt di sistema è lo stesso per le cinque configurazioni. Le differenze, descritte nel Capitolo 3, riguardano il report di evidenze fornito all'agente e, per le ultime due configurazioni, il grafo di esecuzione e il contesto di finalizzazione. Il budget è di sei round di invocazione degli strumenti, uguale per tutte le configurazioni, al termine dei quali l'agente produce la risposta finale.

La risposta deve rispettare un contratto di output legato all'obiettivo della query. Deve essere un oggetto JSON con voci numerate consecutive, una per ciascun guasto indicato nell'istruzione, che contengono i campi richiesti dall'obiettivo. L'istante è nel formato locale YYYY-MM-DD HH:MM:SS, con fuso Asia/Shanghai, e quando l'obiettivo richiede l'istante e i guasti sono più di uno le voci sono in ordine cronologico. Campi non richiesti sono ammessi e sono ignorati dallo scorer (Xu et al., 2025). Una risposta non conforme non viene riparata né ritentata. Lo scorer ufficiale è applicato alla risposta grezza dell'agente, mentre la conformità al contratto è misurata a parte e non modifica il punteggio.

Nella RQ2 il passo D riusa lo stesso agente, con gli stessi cinque strumenti, il budget e i modelli. I passi C e K sono invece singole chiamate al modello, senza strumenti, con un contratto di output proprio descritto nel Capitolo 5. A C e K arrivano le evidenze raccolte da D, ma non la risposta finale di D, per non ancorare i passi successivi alla diagnosi di D.

## Misure e analisi

### Le misure

Per la RQ1 l'accuratezza è il punteggio ufficiale di ciascuna run, tra 0 e 1, e la sua media per modello e configurazione. Si riportano anche le diagnosi esatte, cioè le run con punteggio 1, e la conformità al contratto di output. L'efficienza è misurata con due grandezze. I token totali di una run sono la somma dei token in ingresso e in uscita di tutte le chiamate al modello, come restituiti dal provider. Il tempo è la durata totale della run in secondi e comprende la preparazione deterministica delle evidenze, la creazione del modello e l'esecuzione del grafo. Si registrano inoltre il numero di chiamate al modello e agli strumenti e il numero di round di esplorazione, per descrivere l'utilizzo degli strumenti. Le run senza risposta per errore del provider sono conservate come mancanti e non come zero, e restano fuori da punteggi, token e tempi.

Per la RQ2 le misure sono conteggi: gli stadi completati, non validi o con astensione, le pseudoregole candidate prodotte, l'esito del primo livello di verifica e, per il secondo, i veri e i falsi positivi e negativi rispetto alla verità di riferimento, con un intervallo di confidenza binomiale esatto per i tassi. Le diagnosi prodotte da D sugli incidenti di scoperta sono valutate a posteriori con lo scorer ufficiale, solo in forma descrittiva. Sono studi di fattibilità su un solo sistema, con una sola esecuzione per cella, e non se ne traggono inferenze statistiche sugli effetti del modello o della configurazione.

### I confronti e l'analisi statistica

Il confronto primario della RQ1 è stato fissato prima delle esecuzioni. È la differenza di punteggio tra A1 e A0, appaiata per incidente, all'interno di ciascun modello, e misura il contributo della selezione deterministica delle evidenze. Le differenze tra configurazioni successive, cioè A1_8R rispetto ad A1, A1_8R_Planning rispetto ad A1_8R e A1_PAVE rispetto ad A1_8R_Planning, sono confronti secondari. Per ciascun confronto si riportano la differenza media, il numero di incidenti in cui la configurazione è migliore, uguale o peggiore, e un intervallo di confidenza al 95% calcolato con il bootstrap. Si ricampionano gli incidenti e non le singole run, perché le run dello stesso incidente non sono indipendenti. Non si applica alcuna correzione per confronti multipli, e gli intervalli dei confronti secondari vanno letti come descrittivi.

Su indicazione del relatore, i risultati sono anche normalizzati rispetto ad A0. Ogni valore di punteggio, token e tempo è affiancato al rapporto con la media di A0 dello stesso modello, e il valore assoluto e il numero di run restano sempre riportati accanto al rapporto. A0 è la configurazione con il punteggio medio più basso in tutti e tre i modelli, ma non quella con meno token e tempo: per Sonnet e Haiku è anzi la più costosa. Un rapporto inferiore a 1 indica quindi un risparmio rispetto ad A0. Gli intervalli della normalizzazione sono calcolati con il bootstrap sugli incidenti, con 10.000 estrazioni e seme fisso, e non sono corretti per confronti multipli. Non si confrontano modelli o provider diversi.

## Riproducibilità e integrità

Prima di ogni chiamata a pagamento il protocollo di EVALUATION20 è stato preregistrato. Il piano fissa le 300 run con il loro ordine di esecuzione, che ruota modello e configurazione tra i casi, ed è identificato da un hash SHA-256 e dal commit del codice. Fissa inoltre i modelli, il budget di round, la versione dello scorer, il confronto primario e quelli secondari. Il piano elenca anche i controlli richiesti prima di autorizzare le chiamate: test con modelli simulati, verifica dell'assenza di tentativi nascosti, conteggio completo dei token su tutte le configurazioni, controllo di versioni e identificativi dei modelli, stima dei costi e approvazione esplicita del budget. Il codice eseguito è quello del commit registrato.

Ogni esecuzione ha un file di prenotazione (claim), creato prima della chiamata al provider, e un file di risultato creato in sola creazione, che conserva la risposta grezza e i dati di provenienza. Il protocollo della RQ1 non prevede tentativi automatici: un errore del provider lascia la run mancante, e nessuna delle 5 run di Gemini fallite con errore 503 è stata rieseguita. Nella RQ2 è ammesso un solo secondo tentativo, e solo per un errore di trasporto senza risposta. Un claim senza risultato segnala un'esecuzione interrotta e non viene riavviato automaticamente. I risultati congelati non sono mai stati modificati: le analisi successive li leggono in sola lettura, ne verificano gli hash e, quando riguardano risultati già riportati, devono prima riprodurne i valori.

La verità di riferimento è separata dall'esecuzione. La preparazione delle evidenze e gli strumenti non leggono la verità di riferimento né i punti di valutazione, che sono usati solo da moduli di valutazione eseguiti dopo, in processi distinti dall'inferenza. Nella RQ2 le regole candidate e i parametri di verifica sono congelati con un hash prima di aprire gli incidenti sigillati. Il secondo livello è eseguito in due processi: il primo, senza verità di riferimento, salva le decisioni con il loro hash, il secondo le verifica prima di leggere il riferimento. Tra i due non si modificano né regole né soglie.

## Limiti del protocollo

I limiti legati ai singoli risultati sono discussi nei Capitoli 4 e 5. Qui si indicano quelli che dipendono dal protocollo.

Il numero di incidenti è ridotto e per ogni condizione è disponibile una sola esecuzione. Le 300 run di EVALUATION20 non sono indipendenti, perché ogni incidente è eseguito in 15 condizioni, e la variabilità tra esecuzioni dello stesso modello non è misurata. Per la RQ2 gli incidenti sono 4 di scoperta e 11 sigillati, e i risultati sono descrittivi. Gli intervalli bootstrap su pochi incidenti sono ampi e non sono corretti per confronti multipli.

Gli esperimenti riguardano un solo sistema, Market, e i valori non sono direttamente confrontabili con quelli del lavoro originale sull'intero benchmark (Xu et al., 2025): cambiano il prompt, che qui non elenca componenti e motivi possibili, i modelli, gli strumenti, il budget e la misura, che qui include i punteggi parziali. I tre modelli sono di due provider diversi, con parametri e conteggio dei token diversi. Il benchmark è pubblico e non si può escludere che i modelli ne abbiano incontrato parti durante l'addestramento. La partizione dei casi era già definita, e i gruppi sono disgiunti nel tempo, ma ciò non garantisce l'indipendenza causale degli incidenti.

Infine, il codice dell'harness e dei protocolli è stato scritto con l'assistenza di Claude Sonnet 5.5, che è anche uno dei tre modelli valutati. Si tratta di un possibile conflitto di interesse, che si dichiara e che le misure fissate prima delle esecuzioni non possono escludere del tutto.
<!-- CAP2:FINE -->

Tabella 2.1 | I sette obiettivi di OpenRCA e gli elementi della causa radice richiesti.
<!-- TABELLA-2.1 -->
Obiettivo | Elementi richiesti
task_1 | istante
task_2 | motivo
task_3 | componente
task_4 | istante, motivo
task_5 | istante, componente
task_6 | componente, motivo
task_7 | componente, istante, motivo

Tabella 2.2 | Ripartizione dei 148 casi di Market e uso dei gruppi nella tesi.
<!-- TABELLA-2.2 -->
Gruppo | Casi | Uso nella tesi
Sviluppo (development) | 92 | Messa a punto dell'harness e dei protocolli; 8 incidenti eseguiti
Valutazione (evaluation) | 23 | RQ1: 20 incidenti selezionati (EVALUATION20)
Quarantena (mixed_quarantine) | 18 | Non utilizzato
Riservato (ood_holdout) | 15 | RQ2: 4 incidenti di scoperta e 11 sigillati
Totale | 148 |

Tabella 2.3 | Modelli e configurazioni usati negli esperimenti.
<!-- TABELLA-2.3 -->
Modello | Provider | Configurazione
gemini-3.5-flash-lite | Google | Impostazioni predefinite del client
claude-sonnet-5-5 | Anthropic | Al più 4096 token in uscita per richiesta, condivisi con l'eventuale ragionamento; nessun tentativo automatico; temperatura, top_p e top_k non impostati
claude-haiku-5-5 | Anthropic | Come claude-sonnet-5-5

Figura 2.1 | Ripartizione dei 148 casi di Market e coorti degli esperimenti.
