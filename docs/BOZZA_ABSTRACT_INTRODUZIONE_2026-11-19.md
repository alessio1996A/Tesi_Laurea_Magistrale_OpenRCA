# Bozza di abstract e introduzione — 19 novembre 2026

**Stato:** bozza di Claude, punto di partenza. Alessio la riscrive con la propria voce e deve saper spiegare
ogni frase; poi Claude ricontrolla fatti e numeri, poi GPT fa la revisione indipendente. Nessuna email al
relatore parte da qui senza il permesso di Alessio.

**Formato seguito:** quello della triennale (abstract su una pagina, introduzione non numerata, capitoli
numerati dopo l'introduzione, conclusioni non numerate), con il contenuto richiesto dal relatore:
contesto, problema, motivazioni, teoria di base, che cosa si farà, suddivisione in capitoli.

<!-- ABSTRACT:INIZIO -->
## Abstract

L'analisi delle cause radice (Root Cause Analysis, RCA) nei sistemi distribuiti richiede di ragionare su grandi quantità di metriche, log e trace. Sul benchmark OpenRCA il miglior risultato riportato è l'11,34% dei guasti risolti, ottenuto da un agente basato su modelli linguistici. Questa tesi studia, sul sistema Market di OpenRCA 1.0, se un harness deterministico renda un agente più accurato ed efficiente (RQ1) e se la conoscenza diagnostica prodotta dall'agente possa diventare, dopo verifica, una nuova regola deterministica (RQ2). L'harness raccoglie e seleziona le evidenze, rileva anomalie con regole e verifica le ipotesi ispirandosi ai principi di PAVE. In RQ1, su 20 incidenti e tre modelli, il punteggio medio di Claude Sonnet passa da 0,117 a 0,396 con le sole evidenze deterministiche (3,4 volte) e a 0,504 con la variante più ricca (4,3 volte); per Claude Haiku e Gemini l'intervallo al 95% della differenza include lo zero. Con Sonnet e Haiku i token scendono a 0,54–0,77 volte quelli della baseline. In RQ2, su quattro incidenti di classi di guasto non coperte dall'harness, l'agente propone otto pseudo-regole; l'unica sottoposta a verifica su incidenti sigillati non risulta verificata (due falsi positivi su sette gruppi negativi). Generare una regola non equivale a validarla. I risultati sono studi di fattibilità su un solo sistema, con un'esecuzione per condizione.
<!-- ABSTRACT:FINE -->

<!-- INTRO:INIZIO -->
## Introduzione

Nei sistemi distribuiti un guasto locale si propaga lungo le dipendenze tra i servizi e può manifestarsi lontano dal componente che lo ha causato. L'analisi delle cause radice (Root Cause Analysis, RCA) consiste nel risalire a quel componente, al momento e al motivo del guasto a partire da metriche, log e trace, dati eterogenei e voluminosi. OpenRCA, proposto da Xu et al. (2025), è un benchmark pubblico nato per misurare se i modelli linguistici (Large Language Model, LLM) sanno farlo: raccoglie 335 guasti di tre sistemi software, con oltre 68 GB di telemetria, e il miglior risultato riportato dagli autori, di Claude 3.5 con un agente dedicato, è l'11,34% dei casi risolti.

Il limite non sembra stare soltanto nel modello: secondo la rassegna sugli agenti di Guo et al. (2026), la qualità dipende anche dal runtime che lo circonda, dalla struttura del compito e dalla valutazione. Un agente RCA deve scegliere quali dati leggere, interpretarli e concludere, e può sbagliare a ognuno di questi passi. Per questo la tesi si occupa dell'harness, il runtime che media l'interazione tra modello, contesto e ambiente e ne governa osservazione, contesto, ciclo di controllo, azioni, stato e verifica (Guo et al. 2026; documento di lavoro 2026). Per harnessing si intendono le strategie con cui, a runtime e senza modificare i parametri del modello, se ne regola il comportamento; per Harness Engineering, la disciplina che le progetta, le valuta e le migliora (documento di lavoro 2026). Un secondo motivo riguarda l'affidabilità: Fang et al. (2026), con OpenRCA 2.0, introducono il protocollo di annotazione PAVE e osservano che, in media su 11 LLM, un servizio corretto è indicato nel 76,0% dei casi ma collegato al sintomo osservato con un percorso causale valido solo nel 61,5%. Una risposta giusta non basta, se non è sostenuta da evidenze controllabili.

Su queste basi la tesi pone due domande. RQ1: un harness deterministico, che raccoglie e seleziona le evidenze, rileva anomalie con regole e verifica le ipotesi ispirandosi ai principi di PAVE, rende un agente LLM più accurato ed efficiente nell'identificare la causa radice? RQ2: un agente può investigare guasti di classi che le regole dell'harness non coprono, e la conoscenza che ne ricava può diventare, dopo verifica, una nuova regola deterministica riutilizzabile? La seconda domanda nasce da un'osservazione: un sistema a regole può trattare soltanto i guasti che conosce, mentre un agente può provare a investigare anche quelli che non ha mai visto, ma ciò che propone va verificato prima di essere riutilizzato.

Il lavoro è condotto sul sistema Market di OpenRCA 1.0 (148 query), con tre modelli (Gemini, Claude Sonnet e Claude Haiku) e cinque configurazioni: la baseline A0 e quattro varianti che aggiungono, in sequenza, evidenze deterministiche, otto regole, pianificazione delle verifiche e un contesto strutturale e temporale ispirato a PAVE. Per RQ1 si misurano punteggio, token e tempo su 20 incidenti non usati nello sviluppo, con lo scorer ufficiale, e i risultati sono presentati normalizzati rispetto alla baseline. Per RQ2 si applica una pipeline di tre passi (diagnosi, spiegazione della causa, pseudo-regola candidata) a quattro incidenti di classi non coperte e le candidate sono sottoposte a una verifica su incidenti sigillati. I risultati sono studi di fattibilità su un solo sistema, con un'esecuzione per condizione, e non vanno generalizzati.

La tesi è organizzata come segue. Il Capitolo 1 presenta lo stato dell'arte: RCA nei sistemi a microservizi, OpenRCA, agenti LLM e Harness Engineering. Il Capitolo 2 descrive il benchmark e il protocollo sperimentale. Il Capitolo 3 illustra la progettazione dell'harness. I Capitoli 4 e 5 riportano i risultati di RQ1 e di RQ2. Il Capitolo 6 discute i risultati e le minacce alla validità, il Capitolo 7 i lavori futuri. Le conclusioni chiudono la tesi.
<!-- INTRO:FINE -->

<!-- BIBLIOGRAFIA:INIZIO -->
## Bibliografia

Formato del modello di tesi del dipartimento (cognome e nome, anno, titolo, sede; ordine alfabetico). Le citazioni
nel testo sono «Cognome et al. (anno)». I nomi degli autori sono quelli stampati sui PDF/pagine arXiv letti il
19 novembre.

Agent Harness, Agent Harnessing e Harness Engineering: definizioni, perimetro architetturale, tassonomia delle tecniche e analisi critica della letteratura, 2026, documento di lavoro, versione 1.0, 13 ottobre 2026. *(provenienza e citabilità da decidere, vedi «Decisioni per Alessio» n. 1)*

Fang Aoyang, Yang Yifan, Shang Jin'ao, Lu Qisheng, Xu Junjielong, Wang Rui, Zhang Songhan, Zhang Yuzhong, Yu Boxi, He Pinjia, 2026, *OpenRCA 2.0: From Outcome Labels to Causal Process Supervision*, arXiv:2606.27154v2, 30 giugno 2026.

Guo Jianyuan, Hao Zhiwei, Wang Chengcheng, Fan Cheng, Luo Tingzhang, Li Hongguang, Gao Ying, Mei Hefei, Peng Jiankun, Xu Rongjian, Dong Minjing, Wu Han, Zheng Mengyu, Han Kai, Wang Shiqi, Xu Chang, Wang Yunhe, 2026, *From Question Answering to Task Completion: A Survey on Agent System and Harness Design*, arXiv:2606.20683v1, 14 giugno 2026.

Xu Junjielong, Zhang Qinan, Zhong Zhiqing, He Shilin, Zhang Chaoyun, Lin Qingwei, Pei Dan, He Pinjia, Zhang Dongmei, Zhang Qi, 2025, *OpenRCA: Can Large Language Models Locate the Root Cause of Software Failures?*, in «International Conference on Learning Representations (ICLR)».
<!-- BIBLIOGRAFIA:FINE -->

---

## Lunghezza (misurata sul Word nel formato della triennale)

Times New Roman 12, giustificato, interlinea 1,5, margini 3,0 / 3,0 / 3,5 / 3,5 cm, titolo 17 pt grassetto
centrato. Convertito in PDF con LibreOffice il 19 novembre.

| Parte | Parole | Pagine |
|---|---:|---|
| Abstract | 215 | 1 (pagina propria; la triennale ne aveva 181) |
| Introduzione | 588 | circa 1,7 (una pagina piena più circa due terzi di pagina) |

Il relatore chiede 1,5–2 pagine: l'introduzione ci sta. Se l'abstract conta nel limite, l'insieme supera le due
pagine; la trascrizione non lo chiarisce (contesto di scrittura, sez. 9). L'abstract si può accorciare a
circa 180 parole togliendo la frase sull'harness o i numeri sui token.

## Numeri e affermazioni: fonte e come sono stati verificati

Nella colonna «Fonte» di questa tabella, [1] = Xu et al. (2025), [2] = Guo et al. (2026), [3] = documento di
lavoro, [4] = Fang et al. (2026).

| # | Affermazione nel testo | Fonte | Verifica |
|---|---|---|---|
| 1 | Miglior risultato riportato in OpenRCA: 11,34% (Claude 3.5 con RCA-agent) | [1], abstract e Tabella 2 | Letto nel PDF del Project |
| 2 | 335 guasti, tre sistemi software, oltre 68 GB di telemetria | [1], abstract e Tabella 1 | Letto nel PDF del Project |
| 3 | Market: 148 query | [1], Tabella 1; `CONTESTO_ALLINEAMENTO_GPT_2026-11-18.md` sez. 1 | Letto |
| 3b | La qualità di un agente dipende da modello, runtime, struttura del compito e valutazione, non dal solo modello | [2], abstract | Pagina arXiv letta il 19 novembre (WebFetch su arxiv.org/pdf/2606.20683): è il tema dichiarato dagli autori |
| 4 | Harness = runtime con sei responsabilità (osservazione, contesto, ciclo di controllo, azioni, stato, verifica); «media l'interazione tra modello, contesto e ambiente» | [2], sez. 2.4, e [3], sez. 2.1 | Per [2]: titolo, primo autore (J. Guo), data (14 giugno 2026, v1) e le sei componenti confermati sulla pagina arXiv il 19 novembre. La formula «media l'interazione…» è la definizione operativa di [3] |
| 5 | Harnessing = strategie a runtime senza modifica dei parametri; Harness Engineering = disciplina di progetto, valutazione, miglioramento | [3], sez. 2.2 e 2.3 | Letto nel documento del Project. **Sono definizioni «operative proposte» dal documento stesso, non di un articolo verificato** |
| 6 | In media su 11 LLM: servizio corretto indicato nel 76,0% dei casi (AnySvc), percorso valido fino al sintomo nel 61,5% (Path Reachability, PR) | [4], abstract, sez. 3.2 e Tabella 2 | Letto nel PDF del Project. Sono medie sugli 11 modelli, sistemi di OpenRCA 2.0 (TrainTicket, OTel Demo, Hotel Reservation), **non** Market. PR è calcolata su tutti i casi: 76,0 − 61,5 = 14,5 punti, come scrive il paper |
| 7 | OpenRCA 2.0 introduce il protocollo di annotazione PAVE | [4], abstract | Letto nel PDF del Project |
| 8 | Cinque configurazioni: A0 e quattro varianti cumulative (evidenze, otto regole, pianificazione, contesto strutturale e temporale ispirato a PAVE) | `ARCHITETTURA_E_RISULTATI_V3.md`, tabella delle denominazioni | Letto. «Ispirato a PAVE»: la variante non implementa PAVE per intero e non certifica causalità |
| 9 | Tre modelli: Gemini, Claude Sonnet, Claude Haiku | `CONTESTO_ALLINEAMENTO_GPT_2026-11-18.md` sez. 4 | Letto (identificativi esatti nel documento) |
| 10 | 20 incidenti non usati per lo sviluppo, scorer ufficiale | `CONSOLIDAMENTO_SCIENTIFICO_E_OPERATIVO_2026-11-16.md` sez. 1.1 | Letto |
| 11 | Sonnet: A0 0,117 → A1 0,396 (×3,40) → A1_PAVE 0,504 (×4,33) | `RQ1_NORMALIZZAZIONE_RISULTATI_2026-11-19.md`, Tabella 1 | Tabella generata dal report congelato, 15 medie riprodotte prima dell'uso |
| 12 | Haiku e Gemini: intervallo al 95% della differenza da A0 include lo zero in tutte le varianti | stessa Tabella 1 | Letto |
| 13 | Con Sonnet e Haiku i token sono 0,54–0,77 volte quelli di A0 | stessa, Tabella 2 | Letto (Sonnet 0,77 / 0,77 / 0,55 / 0,60; Haiku 0,60 / 0,54 / 0,64 / 0,58) |
| 14 | Otto pseudo-regole su quattro incidenti di discovery (60 stadi K) | Consolidamento sez. 1.2 | Letto |
| 15 | Una sola candidata sottoposta a verifica su sigillati; verdetto `NON_VERIFICATA`; TP 0, FN 0, TN 5, FP 2 → «due falsi positivi su sette gruppi negativi» | Consolidamento sez. 1.3; contesto 18 novembre sez. 7 | Letto |
| 16 | «Generare non equivale a validare» | Consolidamento sez. 1.3 | Letto. **Non** si scrive che serva un umano |
| 17 | Un solo sistema, un'esecuzione per cella | Consolidamento sez. 1.1 e 1.2 (limiti) | Letto |

## Cosa è stato evitato di proposito

- **«Validate»**: le otto pseudo-regole sono *proposte*; nessuna è verificata.
- **«5 veri positivi»**: l'esito è TP 0, FN 0, TN 5, FP 2.
- **«L'agente ha sempre bisogno di un umano»**: non è scritto. Il testo dice solo che generare non equivale
  a validare.
- **«3 volte» in generale**: vale solo per Sonnet; per Haiku e Gemini l'intervallo include lo zero.
- **Una precisione delle regole**: non si afferma che un sistema a regole sia «preciso»; l'effetto marginale
  delle otto regole è incerto e dipende dal modello (consolidamento sez. 3.1b).
- **OpenRCA 2.0 come benchmark usato**: i dati sono OpenRCA 1.0 (Market); OpenRCA 2.0 serve solo come fonte
  del principio di verifica.
- **PAVE «implementato»**: A1_PAVE è ispirata a PAVE, non lo implementa per intero.
- **Il numero 8 usato due volte**: «otto regole» sono quelle dell'harness; «otto pseudo-regole» sono quelle
  proposte dall'agente. Nel testo si distinguono sempre con «pseudo-regole» per le seconde.
- **Gemini nel confronto primario**: i valori di Gemini non compaiono nell'abstract; per Gemini resta aperta
  la differenza tra le tabelle normalizzate e la relazione del 9 novembre (ipotesi sulla popolazione, non
  verificata). Va risolta prima di scrivere il capitolo di RQ1.

## Decisioni per Alessio (non bloccanti)

1. **Provenienza del documento di lavoro [3].** Non so chi ne sia l'autore. Se è un testo del relatore o un
   lavoro di sintesi tuo, va scritto nella bibliografia; se non è citabile, si toglie [3] e si attribuisce
   la definizione di harnessing alle fonti primarie, che però vanno prima verificate una per una (nel
   documento ci sono, ma non le ho controllate).
2. **Numerazione.** Come nella triennale, l'introduzione non è numerata e i capitoli partono da 1; l'indice
   dei capitoli qui sotto segue la proposta del consolidamento (sez. 5), con questa numerazione. Se preferisci
   l'introduzione come Capitolo 1, cambia solo la numerazione.
3. **Registro.** Il modello di tesi del dipartimento (che Alessio ha inviato il 19 novembre) suggerisce la forma
   impersonale («è stata condotta un'analisi») e non la prima persona («abbiamo ottenuto»): l'introduzione è stata
   riscritta di conseguenza («la tesi si occupa», «il lavoro è condotto», «si misurano»). Anche le citazioni passano
   da [1] a «Cognome et al. (anno)», come chiede il modello.
4. **Lingua e anno accademico per la copertina**: decisi da Alessio il 19 novembre (italiano; 2025/2026).
5. **Elenco dei capitoli**: è una proposta mia; se il relatore la vuole diversa, la cambiamo.

## Controlli eseguiti il 19 novembre

- Numeri del repository: confrontati con `RQ1_NORMALIZZAZIONE_RISULTATI_2026-11-19.md` (Tabelle 1 e 2),
  `CONSOLIDAMENTO_SCIENTIFICO_E_OPERATIVO_2026-11-16.md` (sez. 1.1, 1.2, 1.3) e
  `CONTESTO_ALLINEAMENTO_GPT_2026-11-18.md`: tutti corrispondono.
- Numeri degli articoli: riletti nei PDF del Project ([1] e [4]): 11,34%, 335 guasti, 68 GB, 11 LLM, 76,0%,
  61,5%.
- Guo et al. (2026): pagina arXiv letta; titolo, elenco dei 17 autori, data (14 giugno 2026, v1) e sei
  responsabilità confermati.
- [4]: autori e data presi dal PDF del Project. La pagina arXiv non è stata aperta (accesso non consentito
  dallo strumento): il titolo è confermato da una ricerca web. Nel PDF il nome «Junjielung Xu» compare con un
  refuso rispetto a «Junjielong Xu» di Xu et al. (2025): in bibliografia si scrive «Junjielong».
- [3]: è un documento di lavoro del Project, non un articolo. Le sue fonti primarie (Osmani, Bowne-Anderson,
  Barbaste et al. e altre) **non sono state verificate**: nessuna è citata in questa bozza.
- Non verificato: l'ordine dei capitoli proposto (è una proposta, non un accordo col relatore).

## Prossimi passi

1. Leggi la bozza e dimmi che cosa non ti convince o non sapresti spiegare.
2. La riscrivi con le tue parole (o me la detti a voce e la ricostruiamo).
3. Ricontrollo numeri e riferimenti sul tuo testo; poi GPT; poi la bozza da inviare al relatore (solo bozza
   della mail, l'invio è tuo).
