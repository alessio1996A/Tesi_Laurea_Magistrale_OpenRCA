# Bozza del Capitolo 1 — RCA, agenti LLM e Harness Engineering (20 novembre 2026)

Stato: bozza di Claude da riscrivere con parole di Alessio (flusso concordato: Claude scrive e verifica sulle fonti, Alessio
riscrive e deve saper spiegare, Claude ricontrolla fatti, numeri e riferimenti, poi revisione indipendente GPT).
Convenzioni del modello del dipartimento: forma impersonale, citazioni autore-anno, bibliografia in ordine alfabetico
(«Cognome Nome, anno, Titolo, sede»), figure numerate per capitolo con didascalia autosufficiente.
Il capitolo non contiene risultati sperimentali della tesi: quelli stanno nei Capitoli 4 (RQ1) e 5 (RQ2). I numeri citati
qui sono tutti della letteratura e riferiti ai benchmark degli autori originali.

<!-- CAP1:INIZIO -->
# RCA, agenti LLM e Harness Engineering

Questo capitolo introduce i concetti su cui poggia il resto della tesi. Si definisce anzitutto la Root Cause Analysis (RCA) nei sistemi distribuiti e la telemetria da cui parte l'analisi; si ricordano poi gli approcci classici e l'arrivo degli agenti basati su modelli linguistici (LLM), con il benchmark OpenRCA come banco di prova; si presenta quindi l'Harness Engineering, cioè la progettazione dello strato di esecuzione che circonda il modello. Il capitolo si chiude con la richiesta di spiegazioni verificabili posta da OpenRCA 2.0 e con il posizionamento della tesi rispetto alla letteratura.

## La Root Cause Analysis nei sistemi distribuiti

Le applicazioni cloud moderne sono spesso organizzate come insiemi di servizi debolmente accoppiati, che possono essere distribuiti e scalati in modo indipendente e che comunicano attraverso la rete (Soldani e Brogi, 2021). I microservizi ne sono un esempio. Questa organizzazione rende il sistema più modulare, ma complica la diagnosi dei guasti: un malfunzionamento in un componente può propagarsi ai servizi che da esso dipendono e manifestarsi lontano dal punto in cui ha avuto origine (Fang et al., 2026). Xu et al. (2025) ne danno un esempio: il disco pieno di un nodo può rendere non rispondenti i servizi ospitati nei container di quel nodo, e questa mancata risposta coinvolge a sua volta i servizi che ne dipendono, fino a produrre un guasto visibile a livello di applicazione. Zhou et al. (2021) hanno studiato, con un'indagine presso professionisti del settore e un sistema di prova che riproduce 22 guasti industriali, quali guasti sono più comuni nei sistemi a microservizi e quali difficoltà incontrano gli sviluppatori nel diagnosticarli.

Soldani e Brogi (2021) distinguono tra guasto e anomalia: il guasto (*failure*) è l'incapacità effettiva di un servizio di svolgere le proprie funzioni; l'anomalia è un sintomo osservabile del guasto, per esempio tempi di risposta più lunghi, throughput ridotto o messaggi di errore nei log. In questa terminologia la Root Cause Analysis è il processo che individua perché si sia osservata un'anomalia a livello di applicazione o di servizio, a partire da informazioni raccolte durante l'esecuzione, come log o dati di monitoraggio, senza rieseguire l'applicazione: ciò la distingue dal debugging.

Il risultato di una RCA non ha una forma unica. Xu et al. (2025) descrivono una causa radice mediante tre elementi: il componente di origine (quale parte del sistema è guasta), l'istante di inizio (quando il guasto è cominciato) e il motivo (perché è avvenuto, per esempio un sovraccarico della CPU o un throughput eccessivo del disco). Gli stessi autori osservano che la letteratura non adotta una definizione condivisa dell'output, perché questo dipende dallo scenario: a chi deve solo dirottare il traffico verso un altro contenitore basta conoscere il componente guasto, senza il motivo. Per questa ragione OpenRCA considera ogni obiettivo come una combinazione dei tre elementi.

### La telemetria

L'analisi parte dalla telemetria, cioè dai dati con cui si monitora lo stato interno del sistema, che comprende metriche, trace e log (Xu et al., 2025). Le metriche sono serie temporali di valori numerici che seguono indicatori chiave di prestazione, come l'uso della CPU o il tempo di risposta. Le trace registrano le interazioni tra i componenti e ne mostrano le dipendenze, spesso con la struttura di un grafo. I log registrano gli eventi e i messaggi di esecuzione di ciascun componente, con livelli di dettaglio come *info*, *warn* ed *error*. I tre tipi di dato hanno quindi forme diverse (serie numeriche, grafi, testo semi-strutturato) e chi analizza un guasto deve metterli in relazione tra loro. La Figura 1.1 riassume la situazione: il guasto nasce in un componente, si propaga lungo le dipendenze e lascia tracce nei tre tipi di telemetria, mentre l'analisi percorre il cammino inverso, dal sintomo alla causa.

<!-- FIGURA:1.1 -->

## Approcci classici alla RCA

Prima dell'avvento degli LLM la ricerca ha prodotto una grande varietà di tecniche. La rassegna di Soldani e Brogi (2021) separa il rilevamento delle anomalie dall'analisi della causa radice e, per entrambi, distingue tre classi a seconda del dato usato: tecniche basate sui log, sulle trace distribuite e sul monitoraggio. Per il rilevamento delle anomalie gli autori elencano metodi di apprendimento non supervisionato e supervisionato, confronto di trace, controllo di obiettivi sul livello di servizio e heartbeating. Per l'analisi della causa radice elencano l'analisi di grafi di causalità, l'analisi basata su visualizzazione, l'analisi diretta di trace o indicatori e l'analisi del grafo di topologia.

Xu et al. (2025) rilevano che l'obiettivo della RCA varia con la telemetria disponibile. Se si dispone solo di metriche e topologia, si cerca il componente d'origine o il motivo del guasto; se si hanno solo log, si individuano i log rilevanti al momento del guasto; se si hanno solo trace, l'operazione di servizio guasta; se sono disponibili più tipi di dato, l'obiettivo dipende dalle esigenze. I dataset di valutazione, sempre secondo gli autori, si concentrano in genere su un solo obiettivo, con etichette costruite per scenari specifici: ne derivano metodi tarati sul singolo dataset e con scarsa generalità. A ciò si aggiunge una seconda limitazione, segnalata da Fang et al. (2026): i dataset esistenti etichettano soltanto la causa radice e non il percorso di propagazione che la collega al sintomo osservato, e la valutazione guarda solo all'esito, non al ragionamento che lo ha prodotto. Entrambi i punti, la definizione dell'obiettivo e la verifica del ragionamento, riemergeranno nelle scelte della tesi.

## Agenti basati su LLM per la RCA

### Dal modello all'agente

Un LLM, usato da solo, produce una risposta a partire dal testo che riceve. Un agente lo inserisce invece in un ciclo in cui il modello alterna ragionamento e azioni su una fonte esterna, e ogni azione restituisce un'osservazione di cui il modello tiene conto al passo successivo. Yao et al. (2023) hanno proposto questo schema con il nome ReAct: il modello genera in modo intercalato tracce di ragionamento e azioni specifiche del compito, interrogando fonti esterne, e gli autori mostrano che l'alternanza migliora la capacità di risolvere i problemi e l'interpretabilità rispetto ai metodi che usano soltanto il ragionamento o soltanto l'azione. Nella RCA le azioni sono tipicamente la lettura e l'analisi di telemetria (per esempio estrarre una serie di metriche, calcolare una soglia, seguire le trace di un componente) e le osservazioni ne sono il risultato.

### Il benchmark OpenRCA

OpenRCA (Xu et al., 2025) è il benchmark pubblico che ha reso confrontabili agenti e modelli sulla RCA con telemetria reale. Comprende 335 casi di guasto raccolti da tre sistemi software eterogenei, con oltre 68 GB di telemetria. Ogni caso è accompagnato da una domanda in linguaggio naturale, e il modello deve analizzare la telemetria per produrre gli elementi della causa radice richiesti, in formato JSON strutturato. Gli autori definiscono sette obiettivi, ottenuti combinando sottoinsiemi dei tre elementi (componente, istante, motivo): tre obiettivi chiedono un solo elemento, tre ne chiedono due e uno li chiede tutti e tre. Per ogni caso la risposta vale un punto se tutti gli elementi richiesti coincidono con la verità di riferimento e zero in caso contrario; l'accuratezza complessiva è la media dei punteggi.

I risultati degli autori mostrano la difficoltà del compito. Con Claude 3.5, fornendo la telemetria corretta già selezionata, il 5,37% dei compiti è risolto; con una selezione per campionamento bilanciato della telemetria potenzialmente rilevante il valore scende al 3,88%. Per indicare una direzione, gli autori hanno sviluppato RCA-agent, un sistema multi-agente basato su sintesi ed esecuzione di programmi: il modello usa Python per recuperare e analizzare i dati e non deve quindi leggere la telemetria come un contesto troppo lungo, ma può concentrarsi sul ragionamento. Con RCA-agent l'accuratezza di Claude 3.5 sale all'11,34%. Gli autori notano anche un compromesso: l'esecuzione di programmi rende il modello scalabile su telemetria massiva, ma richiede una maggiore tolleranza agli errori durante il ragionamento. I valori citati si riferiscono all'intero benchmark e ai modelli di quel lavoro, e non sono confrontabili direttamente con le misure condotte in questa tesi sul solo sistema Market.

### Altri lavori sulla valutazione degli agenti

OpenRCA non è l'unico banco di prova. AIOpsLab (Chen et al., 2025) è un framework per sviluppare e valutare agenti di intelligenza artificiale per le operazioni di sistemi cloud lungo l'intero ciclo di vita di un incidente. Fang et al. (2026) osservano che AIOpsLab fornisce una forma parziale di annotazione di processo, cioè etichette sul tipo di problema ma non un grafo di propagazione. La differenza tra annotare solo l'esito e annotare anche il percorso causale è il punto da cui parte OpenRCA 2.0, ripreso nella sezione 1.5.

## Harness ed Harness Engineering

### Il modello non basta

Il risultato di un agente dipende dal modello, ma non solo da esso. Guo et al. (2026) esaminano gli agenti da questo punto di vista: un agente basato su LLM è un sistema accoppiato, costituito da un modello di fondazione e da un *harness* di esecuzione, cioè l'infrastruttura di runtime che circonda il modello e realizza l'esecuzione ad anello chiuso. Gli autori ritengono che il modello sia necessario ma non sufficiente e che la qualità di un agente emerga dall'interazione tra capacità del modello, infrastruttura di esecuzione, struttura del compito e modalità di valutazione. Riportano inoltre che modificare l'harness può migliorare le prestazioni anche quando il modello sottostante resta invariato (Guo et al., 2026, sez. 2.4).

Guo et al. (2026) scompongono l'harness in sei responsabilità di runtime, riportate nella Tabella 1.1: l'interfaccia di osservazione, il gestore del contesto, il ciclo di controllo, l'interfaccia di azione, l'archivio di stato e artefatti e lo strato di verifica e governo. La Figura 1.2 mostra come queste parti si dispongono attorno al modello.

<!-- TABELLA:1.1 -->

<!-- FIGURA:1.2 -->

Zhong e Zhu (2026) propongono una formulazione vicina, riferita agli agenti per l'ingegneria del software. Chiamano *AI Harness Engineering* l'impostazione per cui il sistema è costituito da modello, harness e ambiente, e l'harness è un substrato di runtime esterno al modello, che governa l'intero episodio e non il singolo prompt, può essere sottoposto ad ablazione e valutazione e produce evidenze. Il lavoro individua undici responsabilità (interfaccia del compito, gestore del contesto, registro degli strumenti, memoria di progetto, stato del compito, strato di osservabilità, attribuzione dei guasti, protocollo di verifica, confine dei permessi, auditor dell'entropia e registro degli interventi) e quattro livelli di harness, da H0 a H3, che espongono progressivamente più supporto di runtime. Su un piccolo compito di validazione gli autori riportano che la struttura delle evidenze prodotte cambia con il livello di harness: ai livelli più bassi si ottiene solo una modifica del codice, ai più alti anche log di riproduzione, attribuzioni dei guasti, controlli deterministici dei requisiti e rapporti di verifica strutturati. Il dominio di quel lavoro è lo sviluppo software e non la RCA.

### Terminologia adottata in questa tesi

Le fonti citate usano i termini in modo non sempre coincidente. Nella tesi si adotta la convenzione seguente. Con *harness* si intende, in accordo con Guo et al. (2026), il runtime che circonda il modello. Con *harnessing* si intende l'insieme degli interventi, eseguiti a runtime, che regolano il comportamento dell'agente agendo su informazioni disponibili, strumenti, controllo dell'esecuzione e verifica, senza modificare i parametri del modello. Si tratta di una scelta di questa tesi, coerente con l'osservazione di Guo et al. (2026) sui miglioramenti a modello invariato. Con *Harness Engineering* si intende la progettazione e la valutazione dell'harness come oggetto d'ingegneria, comprese le ablazioni che ne misurano i singoli contributi (Zhong e Zhu, 2026).

## Spiegazioni verificabili: OpenRCA 2.0 e PAVE

Una risposta corretta non basta se non è sostenuta da un percorso causale verificabile. OpenRCA 2.0 (Fang et al., 2026) affronta questo punto con PAVE (*Path Annotation via Verified Effects*), un protocollo di annotazione che ricostruisce i percorsi causali di propagazione a partire dalle registrazioni di esperimenti di iniezione di guasti, sfruttando l'intervento noto per verificare in avanti, dalla causa agli effetti, anziché inferire all'indietro dai sintomi. Un percorso candidato è ammesso solo se soddisfa congiuntamente tre condizioni: la conformità a meccanismi di propagazione noti (strutturale), uno scostamento statisticamente significativo da una linea di base precedente all'iniezione (statistica) e l'allineamento temporale tra monte e valle (temporale).

L'applicazione di PAVE a tre sistemi a microservizi (TrainTicket, OpenTelemetry Demo e DeathStarBench Hotel Reservation) e a 27 tipi di guasto produce OpenRCA 2.0, con 500 istanze valutabili. Su undici LLM di frontiera, gli autori riportano che l'insieme esatto delle cause radice è recuperato in media solo nel 20,7% dei casi; rilassando il criterio, almeno un servizio corretto è individuato nel 76,0% dei casi, ma collegato al sintomo da un percorso causale verificato soltanto nel 61,5%. Gli autori chiamano questo scarto *diagnosi non fondata* e sostengono che la valutazione basata solo sull'esito lo nasconde.

PAVE poggia su quattro condizioni di ingresso: un intervento controllato reale, un grafo di dipendenze di servizio sufficientemente completo, una firma di propagazione nelle trace, nelle metriche o nei log e una linea di base precedente all'iniezione. Dove una di queste non vale, secondo gli autori i risultati vanno letti come un limite superiore e non come una stima trasferibile. In questa tesi si usa OpenRCA 1.0 e non OpenRCA 2.0; poiché OpenRCA 1.0 non dispone delle annotazioni causali passo per passo, il protocollo non viene implementato nella sua interezza: ne vengono ripresi alcuni principi strutturali e temporali, come illustrato nel Capitolo 3.

## Sintesi e posizionamento della tesi

La letteratura esaminata indica tre punti. Primo, nel lavoro che ha introdotto OpenRCA il miglior risultato riportato è l'11,34% dei casi risolti, e l'accuratezza varia con il modo in cui la telemetria viene resa disponibile al modello (Xu et al., 2025). Secondo, la letteratura sull'harness sostiene che le prestazioni di un agente dipendono dal runtime oltre che dal modello e che tale runtime può essere progettato e valutato come oggetto a sé (Guo et al., 2026; Zhong e Zhu, 2026); Zhong e Zhu (2026), in particolare, lo sviluppano per agenti di ingegneria del software e non per la RCA. Terzo, OpenRCA 2.0 propone di valutare la RCA anche sul percorso causale che giustifica la risposta, e non solo sull'esito (Fang et al., 2026).

La tesi si colloca nell'incontro di questi tre filoni e articola il lavoro in due domande di ricerca. La prima (RQ1) chiede se componenti di harnessing, quali la selezione deterministica delle evidenze, regole diagnostiche, la pianificazione delle verifiche e un contesto strutturale e temporale ispirato a PAVE, migliorino l'accuratezza e l'efficienza di un agente sulla RCA del sistema Market di OpenRCA 1.0. La seconda (RQ2) chiede se la conoscenza diagnostica prodotta dall'agente su classi di guasto non coperte dalle regole esistenti possa essere proposta come nuove pseudoregole deterministiche, da sottoporre a verifica prima di un eventuale riuso. Il Capitolo 2 descrive il benchmark e il protocollo sperimentale, il Capitolo 3 l'architettura delle varianti di harness, i Capitoli 4 e 5 i risultati delle due domande, ciascuno con la propria discussione e le minacce alla validità; le conclusioni chiudono la tesi.
<!-- CAP1:FINE -->

<!-- DIDASCALIE -->
Figura 1.1 | Propagazione di un guasto e telemetria disponibile per la RCA. Il guasto ha origine in un componente (in scuro) e si propaga lungo le dipendenze fino al sintomo osservato; metriche, trace e log descrivono il comportamento del sistema e l'analisi deve risalire dal sintomo alla causa, producendo componente, istante e motivo. Schema originale dell'autore, costruito sulle definizioni di Xu et al. (2025); i messaggi di log sono esempi illustrativi.
Figura 1.2 | L'agente come sistema accoppiato di modello e harness. Le sei responsabilità di runtime descritte da Guo et al. (2026) si dispongono attorno al modello e mediano ogni scambio con l'ambiente, qui rappresentato dalla telemetria del sistema da diagnosticare. Schema originale dell'autore, costruito sulla formalizzazione di Guo et al. (2026, sez. 2.4).
Tabella 1.1 | Le sei responsabilità dell'harness secondo Guo et al. (2026, sez. 2.4). Descrizioni riformulate dall'autore.

<!-- TABELLA-1.1 -->
Responsabilità | Che cosa fa
Interfaccia di osservazione | Converte i segnali grezzi dell'ambiente in osservazioni utilizzabili dal modello.
Gestore del contesto | Decide quali informazioni arrivano al contesto del modello, quando e in quale forma.
Ciclo di controllo | Guida il ciclo osservazione, ragionamento, azione e riscontro, con scansione dei passi, arresto, nuovi tentativi e delega.
Interfaccia di azione | Traduce le uscite del modello in operazioni eseguibili.
Archivio di stato e artefatti | Conserva stato e risultati dell'esecuzione tra un passo e l'altro.
Verifica e governo | Controlla, vincola e ripara l'esecuzione mediante test, permessi, ripristino e meccanismi simili.

<!-- BIBLIOGRAFIA:INIZIO -->
Chen Yinfang, Shetty Manish, Somashekar Gagan, Ma Minghua, Simmhan Yogesh, Mace Jonathan, Bansal Chetan, Wang Rujia, Rajmohan Saravan, 2025, *AIOpsLab: A Holistic Framework for Evaluating AI Agents for Enabling Autonomous Cloud*, in «MLSys 2025».
Fang Aoyang, Yang Yifan, Shang Jin'ao, Lu Qisheng, Xu Junjielong, Wang Rui, Zhang Songhan, Zhang Yuzhong, Yu Boxi, He Pinjia, 2026, *OpenRCA 2.0: From Outcome Labels to Causal Process Supervision*, arXiv:2606.27154v2.
Guo Jianyuan et al., 2026, *From Question Answering to Task Completion: A Survey on Agent System and Harness Design*, arXiv:2606.20683v1.
Soldani Jacopo, Brogi Antonio, 2021, *Anomaly Detection and Failure Root Cause Analysis in (Micro)Service-Based Cloud Applications: A Survey*, arXiv:2105.12378v1.
Xu Junjielong, Zhang Qinan, Zhong Zhiqing, He Shilin, Zhang Chaoyun, Lin Qingwei, Pei Dan, He Pinjia, Zhang Dongmei, Zhang Qi, 2025, *OpenRCA: Can Large Language Models Locate the Root Cause of Software Failures?*, in «International Conference on Learning Representations (ICLR)».
Yao Shunyu, Zhao Jeffrey, Yu Dian, Du Nan, Shafran Izhak, Narasimhan Karthik, Cao Yuan, 2023, *ReAct: Synergizing Reasoning and Acting in Language Models*, in «International Conference on Learning Representations (ICLR)».
Zhong Hailin, Zhu Shengxin, 2026, *AI Harness Engineering: A Runtime Substrate for Foundation-Model Software Agents*, arXiv:2605.13357.
Zhou Xiang, Peng Xin, Xie Tao, Sun Jun, Ji Chao, Li Wenhai, Ding Dan, 2021, *Fault Analysis and Debugging of Microservice Systems: Industrial Survey, Benchmark System, and Empirical Study*, in «IEEE Transactions on Software Engineering», 47(2), pp. 243–260.
<!-- BIBLIOGRAFIA:FINE -->
