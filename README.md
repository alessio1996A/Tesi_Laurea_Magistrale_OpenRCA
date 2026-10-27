
# Tesi_OpenRCA

## Harnessing di agenti LLM per la Root Cause Analysis nei sistemi distribuiti

Progetto di tesi magistrale sperimentale in Ingegneria Informatica.

L'obiettivo è studiare se e in quale misura un harness progettato per la Root
Cause Analysis (RCA) possa migliorare la qualità diagnostica e l'efficienza
di un agente basato su Large Language Model (LLM).

Il progetto utilizza inizialmente il dataset Market di OpenRCA 1.0.

---

## 1. Domanda di ricerca

In che misura la preparazione deterministica e la selezione delle evidenze
attraverso un harness specifico per RCA migliorano la qualità diagnostica
e l'efficienza di un agente LLM rispetto a un agente che esplora autonomamente
la telemetria?

La domanda nasce dall'osservazione che la Root Cause Analysis richiede di
correlare informazioni eterogenee, come metriche, log, trace e dipendenze
tra componenti.

L'ipotesi da verificare è che un contesto selezionato, strutturato e supportato
da evidenze verificabili possa aiutare il modello a formulare diagnosi migliori.

Il miglioramento non viene assunto come garantito: deve essere dimostrato
attraverso esperimenti controllati.

## 2. Riferimenti scientifici

### OpenRCA 1.0

Viene utilizzato come benchmark principale per la valutazione delle diagnosi.
Il dataset Market contiene 148 casi, 44 componenti di root cause distinti
e 15 categorie di guasto.

Il paper originale costituisce il riferimento per comprendere i task
diagnostici, la struttura dei dati e i criteri di valutazione.

### OpenRCA 2.0 e PAVE

PAVE fornisce principi da studiare per una possibile estensione dell'harness:
topologia delle dipendenze, deviazioni rispetto a una baseline, compatibilità
temporale e verifica dei percorsi di propagazione.

L'obiettivo iniziale non è replicare integralmente PAVE.
Le sue idee saranno adattate soltanto se compatibili con le informazioni
effettivamente disponibili in OpenRCA 1.0.

### Agent Harnessing e Harness Engineering

Le tecniche di harnessing saranno selezionate in funzione del problema RCA.
Ogni meccanismo introdotto dovrà avere una responsabilità esplicita e
un effetto misurabile.

Il progetto seguirà un processo iterativo:
baseline, osservazione degli errori, modifica dell'harness, test e confronto
con la versione precedente.

## 3. Architetture sperimentali

### A0 — Agente di riferimento

L'agente riceve una richiesta diagnostica e accede alla telemetria attraverso
strumenti di consultazione.

L'agente decide quali dati esplorare, come recuperarli e come costruire
il contesto necessario alla diagnosi.

### A1 — Agente con harness deterministico

Un componente esterno all'LLM recupera e prepara le evidenze necessarie
alla diagnosi.

L'harness può includere, progressivamente:
- selezione delle finestre temporali pertinenti;
- estrazione e sintesi delle metriche, dei log e dei trace;
- controlli di coerenza e provenienza delle evidenze;
- rilevamento deterministico delle anomalie;
- eventuale verifica della compatibilità temporale e topologica.

Il modello riceve quindi un contesto strutturato e formula la diagnosi.

Le funzionalità verranno aggiunte progressivamente, in modo da poter
valutare il contributo delle singole tecniche.

## 4. Principi di confronto equo

Per confrontare A0 e A1 si cercherà di mantenere costanti:
- il modello LLM e la sua versione;
- i casi diagnostici e le richieste;
- il formato dell'output;
- le condizioni di valutazione;
- i budget di esecuzione, per quanto comparabili.

Le differenze inevitabili tra le due architetture saranno documentate.
Saranno registrate le versioni del codice e dell'harness, le configurazioni
del modello, gli errori e i costi di esecuzione.

Il modello non viene addestrato durante gli esperimenti iniziali:
l'oggetto dello studio è il comportamento del sistema a pesi invariati.

## 5. Integrità della valutazione

Le etichette di riferimento contenute in record.csv sono riservate
alla valutazione finale.

Non devono essere fornite all'agente né utilizzate per costruire il contesto
diagnostico del caso che si sta valutando.

Le predizioni archiviate del precedente agente possono essere analizzate
come riferimento storico, ma non saranno considerate automaticamente
un confronto sperimentale diretto con il nuovo agente.

Gli eventuali errori di caricamento, le righe ignorate, i casi esclusi e
le trasformazioni applicate ai dati dovranno essere documentati.

## 6. Metriche

Le metriche iniziali da valutare sono:

- Exact Match: tutti i campi richiesti dalla diagnosi sono corretti.
- Accuratezza per componente e per categoria di guasto.
- Falsi positivi e altre tipologie di errore diagnostico.
- Latenza dell'intera esecuzione.
- Token utilizzati e, quando disponibile, costo delle chiamate LLM.

Le metriche saranno definite in modo coerente con il task OpenRCA selezionato.
Non verranno confrontati punteggi ottenuti con task o condizioni differenti
senza esplicitare le differenze.

## 7. Piano di lavoro

### Fase 1 — Fattibilità e conoscenza dei dati
- Verificare struttura, schema e dimensioni dei file.
- Comprendere le relazioni tra query, record e telemetria.
- Selezionare un primo caso diagnostico senza utilizzare le etichette
  di riferimento durante l'analisi.

### Fase 2 — Baseline
- Definire il contratto di input e output dell'agente.
- Implementare ed eseguire la prima versione di riferimento.
- Registrare diagnosi, errori, latenza e consumo di token.

### Fase 3 — Harness iniziale
- Implementare la raccolta e la preparazione deterministica delle evidenze.
- Fornire all'LLM un contesto strutturato.
- Confrontare A1 con A0 sugli stessi casi.

### Fase 4 — Miglioramenti misurati
- Analizzare gli errori osservati.
- Aggiungere una tecnica di harnessing alla volta.
- Condurre ablation test e test di regressione.

### Fase 5 — Estensioni
Se i risultati iniziali saranno promettenti, valutare la verifica causale
ispirata a PAVE e la possibilità di trasformare diagnosi validate
in regole deterministiche.

L'eventuale generalizzazione a classi di guasto non utilizzate nella fase
iniziale richiederà una suddivisione documentata dei dati e incidenti
indipendenti per la verifica.

## 8. Struttura del progetto

- src/agent/: logica dell'agente LLM.
- src/harness/: raccolta, trasformazione e verifica delle evidenze.
- src/evaluation/: confronto con le etichette di riferimento e calcolo
  delle metriche.
- src/utils/: funzioni di supporto riutilizzabili.
- data/raw/: dati originali, non modificati.
- data/processed/: dati derivati e intermedi.
- notebooks/: notebook per eseguire gli esperimenti su Google Colab.
- results/: risultati sperimentali e riepiloghi.

I dati originali e le credenziali non devono essere pubblicati nel repository
del codice.

## 9. Ambiente di sviluppo

PyCharm viene utilizzato per sviluppare, organizzare e verificare il codice.

Google Colab viene utilizzato per l'esecuzione degli esperimenti che richiedono
risorse computazionali non disponibili sul PC locale.

Google Drive viene utilizzato per conservare dataset, notebook e risultati
persistenti.

L'elaborazione della telemetria dovrà essere progettata per leggere i dati
a blocchi e limitare il consumo di memoria.

## 10. Stato attuale

- [x] Creazione della struttura iniziale in PyCharm.
- [x] Creazione del file .gitignore.
- [x] Documentazione del progetto e delle ipotesi sperimentali.
- [ ] Verifica dell'ambiente e delle dipendenze.
- [ ] Ispezione completa di query.csv, record.csv e telemetria.
- [ ] Definizione rigorosa del task diagnostico.
- [ ] Prima baseline sperimentale.
- [ ] Implementazione dell'harness iniziale.
- [ ] Confronto A0/A1 e analisi degli errori.
