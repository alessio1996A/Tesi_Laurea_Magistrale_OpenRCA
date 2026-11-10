# Allineamento della fase 2 alle due trascrizioni del relatore (10 novembre 2026)

> **Documento interpretativo, non trascrizione integrale e NON protocollo operativo congelato.** Fonte: due trascrizioni condivise dall'utente il 10 novembre 2026, una introdotta come `REGIS 3`, la seconda allegata come `Markdown incollato(20261110-164412).md`. Le trascrizioni sono parafrasi da parlato e contengono stime preliminari. Nessun codice, risultato o dataset storico è stato modificato da questo documento. Non committare in un repository potenzialmente pubblico i testi integrali di conversazioni private senza verifica del consenso.

## Stato e domanda di ricerca 1

- Il relatore, dopo aver visto la campagna EVALUATION20, ha comunicato all'utente che la **prima parte è approvata e conclusa** (10/11/2026).
- RQ1: come cambia la qualità della Root Cause Analysis quando si aggiungono progressivamente strumenti di harnessing (raccolta/filtraggio deterministico della telemetria, evidenze, regole, planning, contesto strutturale-temporale) rispetto ad A0?
- La procedura è una *ablation in costruzione* / studio incrementale delle componenti. Le metriche includono score Microsoft, esattezza, token, latenza, validità, errori e confronti nello stesso modello.
- Le trascrizioni evocano l'ipotesi che un modello più forte possa trarre un beneficio marginale diverso dall'harness; i risultati effettivi sono **model-dependent**, non necessariamente monotoni né sempre più favorevoli ai modelli piccoli.
- Esperimento approvato EVALUATION20: commit codice `e4845e7fe9a399e10dd2db6f320dfeaeeddf3379`, 20 incidenti nuovi, 300 tentativi, 295 completi. Non ritoccare freeze, scorer, output o selection.

## Domanda di ricerca 2 — perimetro principale

**RQ2 formulata in modo testabile:** su incidenti di classi **non codificate dal motore di otto regole**, un agente con harness riesce (a) a diagnosticare il guasto, (b) a motivarlo tramite segnali osservati e (c) a proporre una procedura/pseudoregola deterministica candidata che possa essere verificata **indipendentemente**?

Le due trascrizioni convergono su questi passaggi:
1. Separare classi già considerate nello sviluppo da **quattro classi tenute fuori** (in una trascrizione i totali iniziali sono approssimativi: `14`; l'inventario Market successivo indica `15`, divisione operativa `11+4`).
2. Confrontare un sistema basato su regole note con il ramo esplorativo LLM dotato di harness, sugli stessi dati quando tecnicamente possibile; evitare di postulare che il rule-based sia infallibile.
3. Fornire all'agente un incidente di classe non codificata e misurare l'esito diagnostico con criterio preregistrato, senza mostrare il ground truth in inferenza.
4. In caso di diagnosi candidata, chiedere **spiegazione tecnica**: quali evidenze osservate, quale associazione temporale, quale discriminazione da cause alternative, e quali limiti.
5. Richiedere eventualmente una **pseudoregola deterministica proposta**, con input/metriche, aggregazioni, soglie o criteri, precondizioni, falsificatori, output, incertezze. Una proposta plausibile non è una regola già funzionante.
6. Se la disponibilità dei dati lo consente, verificare una regola formalizzata **offline** su casi nuovi e controlli negativi indipendenti dalla scoperta. Il test di generalizzazione è distinto sia dalla produzione della spiegazione sia dall'accuratezza del singolo incidente.

## Confini: cosa NON deriva dalle trascrizioni come implementazione obbligatoria

- **Human-in-the-loop**, email al supervisore, revisione/approvazione, installazione automatica e loop autonomo di aggiornamento del rule engine sono citati esplicitamente come **architettura futura da ingegnerizzare concettualmente e descrivere in Future Work, non da implementare nella tesi corrente**.
- Nella prima trascrizione compare la visione di un'architettura con ramo deterministico per condizioni conosciute e agente esplorativo per condizioni non coperte. Può essere descritta/prototipata per quanto richiesto da RQ2; **non è già stato deciso** un router autonomo in produzione, né una procedura continua di retraining.
- L'idea di progressione su blocchi di 50/100 casi in una delle trascrizioni è una **proposta esemplificativa iniziale**, non un obbligo di esperimenti a blocchi; deve essere subordinata a disponibilità dei dati e a RQ2.
- Quattro classi ignote al **rule engine** non significa mai viste dal **modello pre-addestrato**; non si può dimostrare l'assenza dal pretraining.
- Un campione OOD già usato, score noto o consultato durante lo sviluppo non è un test indipendente per la nuova regola; inventariare esposizioni e protezioni prima di scegliere i campioni.
- Scorer Microsoft: valuta risposte RCA (task specifici), **non** qualità del ragionamento né correttezza di una pseudoregola. Le due ultime dimensioni richiedono criteri di valutazione separati e riproducibili.
- La frase orale «il rule-based risponde sempre correttamente» è un'intuizione, non un risultato: misurare copertura, precisione e falsi positivi su casi compatibili.
- Le otto regole implementate non coincidono con tutte le 11 classi «non held-out»: occorre esplicitare copertura effettiva di ogni regola prima di definire i controlli.

## Partizione delle classi: da verificare sull'inventario

Otto regole esistenti: `R01` container CPU load, `R02` container memory load, `R06` container read I/O load, `R07` node CPU load, `R08` node memory consumption, `R09` node disk read I/O consumption, `R10` node disk write I/O consumption, `R11` node disk space consumption.

Quattro classi storicamente riservate nelle note: `node CPU spike`, `container write I/O load`, `container process termination`, `container packet loss`. **Confermare nomi, presenza, cardinalità, incidenti, leakage e disponibilità effettiva nel Market.zip/manifest prima di lanciare qualsiasi studio.** L'audit R03/R04/R05 sui guasti di rete, discusso in un handoff precedente, è un filone diverso e non sostituisce automaticamente la RQ2 sulle quattro classi riservate.

## Disegno metodologico da definire PRIMA del codice

1. Audit **GT-free** di dataset/split/precedenti esposizioni e inventario delle finestre disponibili; quando occorre verificare la classe per creare la coorte, farlo in una fase indipendente dal ramo di inferenza, registrando regole di accesso e hash.
2. Definire unità di analisi (incidente/finestra), classi, multi-fault, separazione temporale e indipendenza fra **discovery** e **test**. Non assumere che ci siano abbastanza incidenti per una validazione statistica sulle quattro classi.
3. Definire le condizioni minime di confronto, mantenendo invariati modello, task, prompt diagnostico e telemetria, per isolare quanto possibile il contributo harness; preregistrare eventuale scelta di un solo provider/configurazione.
4. Prima di chiedere pseudo-regole, valutare accuratezza RCA e output; poi sviluppare separatamente un **contratto strutturato di spiegazione/regola candidata**, con provenienza delle evidenze e condizioni di rifiuto/astensione.
5. Protocollo di valutazione della regola candidata: presenza realistica dei KPI, test software sintetici e reali, falsi positivi e negativi, casi indipendenti; mai chiedere all'LLM stesso di autocertificare la propria regola.
6. Nuovo branch Git, design doc e test PyCharm; new output paths **create-only** in Drive e notebook Colab per eseguire solo dopo autorizzazione esplicita del budget API. Freeze prima dello score.

## Finalità della tesi, scrittura e archivi

- L'approvazione della RQ1 non implica che la RQ2 sia già risolta; riportare anche esiti inconcludenti o negativi.
- Scrivere la tesi **dopo** aver completato gli esperimenti, proponendo poi l'indice al professore; fino a quel momento mantenere invece una documentazione tecnica continua.
- Scadenza massima dichiarata dall'utente: **5 dicembre 2026**.
- Codice/protocolli/decisioni/test e relazioni su GitHub; dataset, run, risultati e freeze in Drive. La memoria della chat non è una garanzia di recupero preciso dei dati.
- Il presente documento serve a **prevenire deriva di ambito**. Non introduce un nuovo esperimento, non avvia API, non modifica i risultati.

## Collegamenti agli artefatti già conclusi

- `docs/relatore_2026-11-10/CONTINUITA_APPROVAZIONE_FASE1_E_PIANO_FASE2.md`
- `docs/relatore_2026-11-09/RELAZIONE_EVALUATION20.md`
- `docs/HANDOFF_NUOVA_CHAT_TESI_OPENRCA_2026-11-02.md` (branch `presentation/relatore-2026-11-02`).
