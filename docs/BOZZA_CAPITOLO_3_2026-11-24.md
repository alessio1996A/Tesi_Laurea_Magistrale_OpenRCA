# Capitolo 3 — Architettura dell'harness e delle cinque configurazioni (bozza del 24 novembre 2026)

> Bozza scritta da Claude a partire dal codice e dalla documentazione del repository. Alessio la riscrive con la propria voce e deve poterla spiegare. Nessun commit, codice o gergo del repository nel testo finale. Nessuna nota sotto figure e tabelle.

## 3 Architettura dell'harness e delle cinque configurazioni

Questo capitolo descrive l'harness progettato per la RCA sul sistema Market e le cinque configurazioni confrontate nella RQ1. Si presentano anzitutto i principi di progetto e il flusso di un'esecuzione, quindi le cinque configurazioni. Seguono i singoli componenti: gli strumenti e il ciclo dell'agente, la preparazione deterministica delle evidenze, le otto regole diagnostiche, la pianificazione delle verifiche e il contesto strutturale e temporale ispirato a PAVE. Il capitolo si chiude con la corrispondenza fra il sistema realizzato e le sei responsabilità dell'harness del Capitolo 1 e con i limiti dell'harness. Il benchmark e il protocollo sperimentale sono descritti nel Capitolo 2, i risultati nei Capitoli 4 e 5.

## 3.1 Panoramica dell'architettura

### 3.1.1 Principi di progetto

L'harness è progettato attorno a quattro principi.

Il primo è la separazione fra la parte deterministica e il modello. La preparazione delle evidenze, le regole, la pianificazione delle verifiche e il contesto strutturale sono codice che, a parità di telemetria, restituisce sempre lo stesso risultato. Non chiama il modello e non legge la verità di riferimento, che è usata soltanto nella valutazione.

Il secondo è che l'harness fornisce osservazioni e non cause. Le evidenze e le regole segnalano anomalie come candidati da verificare, e la richiesta lo dichiara in modo esplicito: le osservazioni non sono verità di riferimento, la correlazione temporale non prova la causalità, l'assenza di anomalie non prova che un componente sia sano e alcune evidenze possono essere state escluse dai limiti di selezione. La scelta della causa radice resta al modello.

Il terzo è che ogni configurazione differisce dalla precedente per un solo componente. Prompt di sistema, strumenti, modelli, limite di round e contratto di output sono gli stessi in tutte le configurazioni. Una differenza di risultato tra due configurazioni successive può quindi essere riferita a quel componente, con le cautele statistiche indicate nel Capitolo 2.

Il quarto è l'indipendenza dal provider. La creazione del modello è separata dal resto del sistema, mentre il motore dell'agente, gli strumenti e l'harness usano soltanto interfacce comuni e non dipendono dal provider. Lo stesso codice esegue quindi i tre modelli dei due provider.

### 3.1.2 Il flusso di un'esecuzione

La Figura 3.1 riassume il flusso di una run. L'agente riceve l'istruzione ufficiale della query, il nome del cloudbed e l'intervallo di tempo. Nelle configurazioni con evidenze, prima che l'agente parta, l'harness legge le metriche della finestra, costruisce il report di evidenze e lo aggiunge alla richiesta. L'agente alterna ragionamento e chiamate agli strumenti entro il limite di sei round. Al termine, una sola chiamata al modello, senza strumenti, produce la risposta in formato JSON. Lo scorer ufficiale viene eseguito dopo, fuori dall'esecuzione, e confronta la risposta con la verità di riferimento.

[FIGURA fig3_1.png]
Figura 3.1. Flusso di un'esecuzione e componenti introdotti dalle cinque configurazioni.

## 3.2 Le cinque configurazioni

Le cinque configurazioni sono cumulative: ciascuna contiene tutti i componenti della precedente e ne aggiunge uno, come mostra la Tabella 3.1.

A0 è la configurazione di base. L'agente dispone soltanto dell'istruzione, del cloudbed, dell'intervallo e dei cinque strumenti e deve cercare da sé le anomalie nella telemetria. A1 aggiunge alla richiesta un report deterministico di evidenze, ricavato dalle metriche di nodi e container e dai segnali del service mesh e del runtime. A1_8R aggiunge al report le otto regole diagnostiche, che propongono candidati con classe di guasto, componente e primo istante del segnale.

Le ultime due configurazioni cambiano il modo in cui l'agente è eseguito. In A1_8R_Planning il limite di sei round è ripartito in al più quattro round di esplorazione libera e al più due di verifica. Le verifiche sono scelte da un pianificatore deterministico fra i candidati delle regole non ancora controllati dall'agente. A1_PAVE aggiunge a questa struttura un contesto strutturale e temporale, ispirato a PAVE, che è fornito al modello nella risposta finale.

Tabella 3.1. Componenti presenti nelle cinque configurazioni.

| Configurazione | Report di evidenze | Otto regole | Verifiche pianificate | Contesto strutturale e temporale | Round di esplorazione + verifica |
| --- | --- | --- | --- | --- | --- |
| A0 | no | no | no | no | fino a 6 + 0 |
| A1 | sì | no | no | no | fino a 6 + 0 |
| A1_8R | sì | sì | no | no | fino a 6 + 0 |
| A1_8R_Planning | sì | sì | sì | no | fino a 4 + 2 |
| A1_PAVE | sì | sì | sì | sì | fino a 4 + 2 |

## 3.3 Gli strumenti e il ciclo dell'agente

### 3.3.1 I cinque strumenti

Lo stesso insieme di cinque strumenti è disponibile in tutte le configurazioni. Il primo legge le metriche dei servizi: tasso di risposta, tasso di successo e tempo di risposta. Il secondo e il terzo leggono le metriche dei container e dei nodi. Per ogni coppia componente e KPI restituiscono statistiche sull'intervallo richiesto: numero di campioni, media, minimo e massimo con il rispettivo istante, primo e ultimo valore. Si possono filtrare per componente e per KPI, anche con espressioni regolari, e occorre indicare almeno uno dei due filtri. Gli ultimi due leggono i log, di servizio o del proxy, e le trace distribuite. I log sono restituiti in ordine cronologico e le trace sono quelle più lente, con un numero massimo di righe.

Ogni strumento è vincolato al cloudbed dell'incidente e alla finestra ufficiale. Una richiesta esterna all'intervallo è rifiutata con un messaggio di errore e non restituisce dati. Gli strumenti restituiscono dati e non diagnosi: non eseguono alcun rilevamento di anomalie.

### 3.3.2 Il ciclo dell'agente

Il motore dell'agente è un grafo di stati costruito con la libreria LangGraph e realizza il paradigma ReAct [7]. In questo paradigma il modello alterna ragionamento e azioni e dopo ogni azione riceve il risultato come osservazione. Qui l'azione è la chiamata a uno strumento. Un round è una risposta del modello che contiene almeno una chiamata a strumenti, e più chiamate nella stessa risposta contano come un solo round. Il limite è di sei round per tutte le configurazioni.

Se il modello risponde senza chiamare strumenti prima del limite, la sua risposta è quella finale. Se raggiunge il limite, gli strumenti dell'ultimo round sono eseguiti e il modello è invocato una sola volta, senza strumenti, per la risposta finale. Questa chiamata riceve in forma di testo la richiesta originale, con l'eventuale report, e le osservazioni degli strumenti, presentate come dati e non come istruzioni. I risultati molto lunghi sono abbreviati e, se lo spazio complessivo non basta, si conservano le osservazioni più recenti, dichiarando le omissioni. Se in questa chiamata il modello richiede ancora strumenti o risponde con un testo vuoto, la run è registrata come errore, non viene eseguito nessun altro strumento e non si effettuano nuovi tentativi.

Il prompt di sistema è lo stesso nelle cinque configurazioni. Prescrive l'uso dell'intervallo in secondi Unix e chiede di basare la diagnosi sulle evidenze raccolte, senza inventare misure o identificatori. Chiede di distinguere i sintomi dalla causa radice, considerando l'ordine temporale, le relazioni fra nodi, container e servizi e le spiegazioni alternative, e di trattare un eventuale report di evidenze come osservazioni da verificare con gli strumenti. Il motivo deve indicare il tipo di guasto in modo specifico, e l'istante del guasto va stimato senza copiare automaticamente il primo segnale anomalo. La richiesta contiene inoltre un promemoria sulla completezza: se l'istruzione indica più guasti, ciascuno va indagato e riportato separatamente. Le istruzioni sul formato della risposta, legate all'obiettivo della query (Capitolo 2), sono identiche per tutte le configurazioni.

Il motore non ha memoria persistente. Ogni run parte dalla propria richiesta e non conserva nulla per le successive.

## 3.4 La preparazione deterministica delle evidenze

Dalla configurazione A1 in poi il report di evidenze è costruito prima dell'avvio dell'agente, leggendo le metriche di nodi e container della finestra. Il tempo di questa preparazione è compreso nel tempo di ogni run (Capitolo 2). La costruzione procede in cinque passi.

Il primo passo valuta la qualità delle serie, segnalando quelle con pochi campioni o costanti, e calcola le statistiche per ogni coppia componente e KPI. Il secondo individua variazioni persistenti. Per ciascun KPI di un catalogo di segnali delle famiglie CPU, memoria, disco e I/O il catalogo indica la direzione sospetta, cioè un aumento o una diminuzione. Una variazione è segnalata, per le serie con almeno 10 campioni, quando per almeno tre campioni consecutivi il valore supera la mediana della serie di oltre 3,5 volte una stima robusta della dispersione. Questa stima è la MAD moltiplicata per 1,4826, fattore che la rende confrontabile con una deviazione standard, con un valore minimo che evita soglie nulle. La MAD, o scarto assoluto mediano, è la mediana degli scarti dei valori dalla loro mediana: insieme alla mediana è una statistica robusta, cioè poco influenzata da pochi valori estremi. Il terzo passo raggruppa le anomalie dello stesso componente che iniziano a meno di 180 secondi l'una dall'altra e coinvolgono almeno due KPI, formando pattern strutturali. Il quarto passo compatta gli episodi correlati, per esempio le anomalie simultanee delle repliche dello stesso servizio, e annota la qualità delle evidenze: variazione relativa, possibili discontinuità della capacità del disco, vicinanza al bordo della finestra. Il quinto passo esamina i segnali del service mesh, cioè durata e numero delle richieste, e del runtime Java, cioè memoria heap e garbage collection.

Il report unificato contiene al più 10 evidenze. La selezione segue un ordine fisso e non causale: dà precedenza alle correlazioni fra repliche e ai segnali dello stesso host e della stessa famiglia di risorse entro 60 secondi, quindi completa lo spazio rimasto con le altre evidenze. Per ogni evidenza il report riporta la provenienza e dichiara quante evidenze sono state omesse. Il report è aggiunto alla richiesta con un'avvertenza che ricorda quanto detto nel secondo principio di progetto.

## 3.5 Le otto regole diagnostiche

Le otto regole sono scritte a mano e coprono le otto classi di guasto del Capitolo 2. Sono indicate come R01, R02 e da R06 a R11. Le sigle da R03 a R05 corrispondono alle tre classi di rete per le quali non esistono regole affidabili. Ogni regola esamina un KPI principale del livello corrispondente, container o nodo, per ogni componente osservato nella finestra (Tabella 3.2). Le classi sono indicate con le stesse etichette del benchmark.

Tabella 3.2. Le otto regole diagnostiche, il livello di telemetria e il KPI principale.

| Regola | Classe di guasto | Livello | KPI principale |
| --- | --- | --- | --- |
| R01 | container CPU load | container | container_cpu_usage_seconds |
| R02 | container memory load | container | container_memory_working_set_MB |
| R06 | container read I/O load | container | container_fs_reads_MB./dev/vda |
| R07 | node CPU load | nodo | system.cpu.pct_usage |
| R08 | node memory consumption | nodo | system.mem.pct_usage |
| R09 | node disk read I/O consumption | nodo | system.io.r_s |
| R10 | node disk write I/O consumption | nodo | system.io.w_s |
| R11 | node disk space consumption | nodo | system.disk.pct_usage |

La logica è comune a tutte le regole. Il periodo di riferimento è il primo 40% della finestra, cioè i primi 12 minuti su 30, e la ricerca riguarda il restante 60%. Dal periodo di riferimento si calcolano la mediana e la MAD. La soglia è il maggiore fra la mediana più 3,5 volte la stessa stima robusta della dispersione e un incremento minimo prefissato, diverso da regola a regola. Una regola propone un candidato quando il KPI supera la soglia per almeno tre campioni consecutivi nel periodo di ricerca, e registra il primo e l'ultimo istante del segnale. L'esito di una regola per un componente è uno fra tre: candidato da verificare, nessun candidato oppure evidenza insufficiente, per esempio quando i campioni del periodo di riferimento sono pochi o la serie non ha dispersione. Le soglie sono esplorative e non sono state calibrate sulla verità di riferimento.

Tutti i componenti sono valutati, ma il report delle regole ne riporta al più 16, in ordine fisso per regola e componente. L'ordine non rappresenta una graduatoria causale e il numero dei candidati omessi è dichiarato. Per ogni regola il report indica anche quanti componenti sono stati valutati e quanti candidati sono emersi. Il report contiene infine le avvertenze seguenti: i candidati non sono verità di riferimento, l'ordine temporale non implica causalità, il periodo di riferimento appartiene alla stessa finestra e potrebbe già contenere il guasto, e l'assenza di un candidato non esclude un guasto.

## 3.6 La pianificazione delle verifiche

In A1_8R_Planning e in A1_PAVE il grafo dell'agente ha quattro fasi: esplorazione, pianificazione, verifica e risposta finale. Nella prima fase il modello sceglie liberamente gli strumenti per al più quattro round. Quando li ha esauriti, oppure risponde senza chiamare strumenti, interviene il pianificatore.

Il pianificatore è codice deterministico e non chiama il modello. Legge i candidati riportati dalle regole e le chiamate agli strumenti già eseguite dall'agente. Un candidato è considerato già controllato se esiste una chiamata mirata allo strumento di metriche del suo livello, con il suo componente e con un intervallo che comprende il periodo del segnale. Per gli altri propone una chiamata allo stesso strumento, con il componente, il KPI e la finestra del candidato. Evita richieste duplicate, ripartisce le verifiche in modo equilibrato fra i componenti, alterna container e nodi e ne propone al più due, o meno se i round restanti sono meno di due. Se non ci sono candidati da controllare, non propone nulla. Le proposte sono un criterio di copertura investigativa e non una stima della gravità o della probabilità causale dei guasti.

Le verifiche sono eseguite con gli stessi strumenti dell'agente. Ciascuna consuma un round, ma non una decisione del modello, e nella registrazione della run è attribuita al pianificatore. I round di verifica non utilizzati non sono restituiti all'esplorazione. Infine una sola chiamata al modello, senza strumenti, riceve la richiesta, il report e le osservazioni, insieme a un'avvertenza. I controlli deterministici sono soltanto osservazioni e non cause confermate. Occorre confrontare le ipotesi alternative, l'ambito dei componenti e la cronologia, senza dedurre la causalità dall'ordine temporale, e un segnale assente o inconcludente non prova l'assenza di un guasto.

## 3.7 Il contesto strutturale e temporale ispirato a PAVE

Il contesto strutturale e temporale della configurazione A1_PAVE riprende da PAVE [4] soltanto due principi, la coerenza strutturale e l'ordine temporale dei segnali. Non implementa il protocollo. Come detto nel Capitolo 1, PAVE richiede un intervento controllato noto, un grafo di dipendenze dei servizi, una firma di propagazione e una linea di base precedente al guasto, e OpenRCA 1.0 non dispone delle annotazioni causali necessarie.

Il contesto è calcolato prima della risposta finale a partire dai candidati delle regole. Associa un segnale del nodo a un segnale del container quando i due appartengono allo stesso host e alla stessa famiglia di risorse misurata a entrambi i livelli, cioè CPU, memoria e lettura su disco. L'host è ricavato dall'identificatore del container, che ha la forma node-N seguita dal nome del container. Per ogni coppia il contesto riporta le regole coinvolte, la differenza in secondi fra il primo segnale del container e quello del nodo e un'etichetta: segnali quasi contemporanei, se distano meno di 60 secondi, segnale del nodo anteriore a quello del container, oppure segnale del container anteriore a quello del nodo. Le coppie sono ordinate in modo fisso e limitate a 8, con il totale e il numero delle omesse dichiarati. I candidati delle regole R10 e R11 restano nel report ma non formano coppie, perché le scritture su disco e lo spazio del disco sono misurati soltanto sul nodo.

Il contesto è inserito, in forma strutturata, nella chiamata finale. Dichiara esplicitamente che né la causa né la propagazione sono verificate. Le associazioni derivano dai nomi degli identificatori e non da una topologia dei servizi verificata, l'ordine dei segnali non è causalità e non determina l'istante del guasto, e l'assenza di una coppia non esclude un guasto. Il contesto non giudica e non modifica la risposta dell'agente.

## 3.8 Sintesi e limiti dell'harness

### 3.8.1 Corrispondenza con le responsabilità dell'harness

La Tabella 3.3 associa i componenti descritti in questo capitolo alle sei responsabilità dell'harness presentate nella Tabella 1.1. La corrispondenza è una lettura dell'autore.

Tabella 3.3. Corrispondenza fra le responsabilità dell'harness e i componenti realizzati.

| Responsabilità | Componenti realizzati |
| --- | --- |
| Interfaccia di osservazione | I cinque strumenti, che trasformano la telemetria grezza in statistiche per componente e KPI, e la preparazione deterministica delle evidenze |
| Gestore del contesto | Il report di evidenze con il limite di 10 evidenze, le otto regole, il contesto strutturale e temporale e il riepilogo testuale delle osservazioni nella chiamata finale |
| Ciclo di controllo | Il grafo ReAct con limite di sei round, la fase di pianificazione e verifica e la risposta finale in un'unica chiamata |
| Interfaccia di azione | La chiamata agli strumenti, vincolata al cloudbed e alla finestra dell'incidente |
| Archivio di stato e artefatti | Lo stato della singola esecuzione, cioè messaggi e conteggio dei round, e il salvataggio della risposta grezza e delle misure di ogni run; nessuna memoria fra incidenti |
| Verifica e governo | Il vincolo sulla finestra, il contratto di output, il rifiuto di nuovi strumenti dopo il limite, le verifiche pianificate e le avvertenze sul valore delle evidenze; nessuna riparazione della risposta |

### 3.8.2 Limiti dell'harness

I limiti riguardano la progettazione dell'harness e si aggiungono a quelli del protocollo del Capitolo 2.

La copertura è parziale. Le regole riguardano otto delle quindici classi di guasto: le altre sono le quattro riservate alla RQ2 e le tre classi di rete senza regole affidabili. L'assenza di candidati non esclude un guasto, e per un guasto non coperto il pianificatore non propone verifiche mirate.

Un'anomalia non è una causa. Un candidato può essere un sintomo, la conseguenza di un altro guasto o una variazione normale, e l'harness non è in grado di distinguere questi casi. Le regole usano un periodo di riferimento interno alla finestra, che non è necessariamente privo di guasto: se il guasto inizia nei primi 12 minuti, la soglia può includerlo e il segnale può non emergere.

I limiti di selezione possono escludere segnali. Il report contiene al più 10 evidenze, le regole ne riportano al più 16, il contesto al più 8 relazioni e il pianificatore propone al più 2 verifiche. Le omissioni sono dichiarate, ma l'agente può comunque non vedere un segnale escluso.

Le relazioni del contesto strutturale derivano dai nomi degli identificatori e non da una topologia dei servizi. La pianificazione sottrae due dei sei round all'esplorazione libera e riguarda soltanto i candidati delle regole.

Le etichette delle classi usate dalle regole coincidono con quelle del benchmark. Questo può favorire la corrispondenza lessicale con il motivo atteso e va tenuto presente nella lettura dei risultati (Capitolo 4). Infine, l'harness non corregge la risposta dell'agente e non conserva conoscenza fra incidenti: il trasferimento della conoscenza dall'agente alle regole è l'oggetto della RQ2 (Capitolo 5).
