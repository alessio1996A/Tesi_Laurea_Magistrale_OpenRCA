# Aggiornamento per il revisore (GPT) — 16 novembre 2026, ore 11:40

Leggere prima `docs/CONTESTO_ALLINEAMENTO_GPT_2026-11-16.md` (quadro completo,
scritto alle 10:30). Questo file contiene solo ciò che è cambiato da allora e le
domande di revisione, ordinate per utilità. Ogni affermazione sul repository va
controllata nei file; ciò che non è verificato è scritto come tale.

## 1. Cosa è cambiato dalle 10:30

Fatti, con la fonte:

- **Pilota v1** (18 stage, commit `926356e`). Il D di Sonnet con A1_PAVE è stato
  rifiutato: la risposta conteneva un blocco ```json valido seguito da un commento
  finale. Non era un troncamento. Il K di Gemini è finito in `PROVIDER_ERROR`;
  una sonda di sola diagnosi (non memorizzata) sullo stesso input ha dato 3
  chiamate riuscite su 3, quindi l'errore era transitorio.
- **Politica di formato V5.1** `rq2_v5_1_single_json_fence_outside_text_v1`:
  accetta esattamente un blocco json (o senza lingua), con le righe di fence su
  righe proprie; il testo fuori dal blocco è scartato ma conservato (SHA-256).
  Etichette: `NONE`, `SINGLE_JSON_FENCE`, `FENCE_WITH_OUTSIDE_TEXT`,
  `REJECTED_WRAPPER`. Non ripara mai il JSON. Stessa funzione per tutti i modelli.
- **Politica di retry** `rq2_v5_one_transport_retry_v1`: al più un tentativo in
  più per stage, pausa 10 s, **solo** per errori di trasporto senza output del
  modello. Mai su output invalido, ricevuta rifiutata, errore di protocollo. Il
  primo tentativo resta registrato; del messaggio d'errore si conservano tipo e SHA.
- **`release-orphan`**: sblocca un claim orfano solo con comando esplicito,
  motivazione di almeno 10 caratteri e log. Il runner non lo chiama mai.
- **Pilota v2** (commit `b1dac2b`, A1_PAVE × 3 modelli × `cloudbed-1_q032`):
  9/9 `RECORDED_COMPLETE`. Conformità strict: Gemini 3/3, Sonnet 2/3, Haiku 2/3
  (un fence ciascuno per Sonnet e Haiku). Nessun retry è scattato. I tre K sono
  tutti `insufficient_evidence`.
- **Codice congelato** per il run di discovery: SHA
  `ddb2ca499c4b41aa32a36fdc2f9850cb09bb75c3`, branch
  `release/rq2-v5.1-discovery-v1`. Il remoto rifiuta i tag (HTTP 403), quindi il
  congelamento è per SHA. La cella Colab si ferma se il checkout non coincide.
- **Test**: 98 test offline, tutti OK su PyCharm (Windows, con LangChain);
  nella sandbox senza LangChain 98 passano e 21 sono saltati.
- **Stato del run vero** (`data/rq2_v5_format_fair_v1`, 180 stage): predisposto.
  Al momento della scrittura non ho visto nessun suo output: non so quanti stage
  siano registrati.

Non verificato: il retry contro un provider reale; il percorso "testo fuori dal
fence" in una chiamata reale (coperto solo da test offline con i contratti veri);
la durata del run (2–3 ore è una stima dai piloti).

## 2. Fatti RQ1 che servono per rispondere alle domande di progetto

Fonte: `docs/ARCHITETTURA_E_RISULTATI_V3.md`. Otto incidenti development, **una
sola replica**, scorer ufficiale; i documenti parlano di un solo modello (Gemini).

| Variante | Score medio | Esatte | Token medi | Tempo (s) |
| --- | ---: | ---: | ---: | ---: |
| A0 | 0,0000 | 0/8 | 35.286 | 157,84 |
| A1 | 0,4062 | 2/8 | 48.659 | 170,76 |
| A1_8R | 0,5000 | 3/8 | 48.177 | 191,14 |
| A1_8R_Planning | 0,4375 | 2/8 | 32.144 | 101,67 |
| A1_PAVE | 0,2812 | 1/8 | 36.100 | 109,91 |

Differenze tra varianti: da 1 a 2 incidenti su 8. Con n=8 e una replica non sono
distinguibili dal rumore. Il documento già dichiara che la finestra development è
stata analizzata anche tramite ground truth e non va riusata come test indipendente.

## 3. Osservazioni di progetto verificate nel codice

1. **8R e PAVE lavorano sui candidati delle 8 regole.** In
   `src/harness/structural_temporal_verifier.py` le classi ammesse sono solo
   quelle delle regole R01, R02, R06, R07, R08, R09, R10, R11 (container CPU,
   memoria, read I/O; nodo CPU load, memoria, read I/O, write I/O, spazio disco)
   e il contesto strutturale-temporale confronta segnali della stessa famiglia
   sullo stesso host. Sulle 4 classi di RQ2 (nodo CPU spike, container write I/O,
   terminazione di processo, packet loss) le regole non sono progettate per
   scattare. Se scattano, riportano una classe vicina ma diversa (per esempio
   "node CPU load" su un incidente "node CPU spike"). Non ho verificato quante
   volte accada sui 4 incidenti discovery.
2. **Il budget totale è uguale, la ripartizione no.** Le cinque varianti
   condividono `max_tool_rounds=6`, ma Planning e PAVE usano 4 round esplorativi e
   2 di verifica (`docs/ARCHITETTURA_E_RISULTATI_V3.md`, sezione Planner). Meno
   esplorazione potrebbe spiegare in parte il calo, ma è un'ipotesi non testata.
3. **A1_PAVE non è PAVE.** Il documento lo dice: ispirato a PAVE, non
   implementa PAVE per intero e non certifica causalità. Un risultato basso
   riguarda questa implementazione, non il metodo PAVE.
4. Motivi puntuali già documentati: `cloudbed-2_q034` (A1_PAVE indica un
   timestamp con 14 min 9 s di scarto), `cloudbed-2_q071` (criterio temporale
   perso). Sono due casi: indicano un meccanismo possibile, non lo dimostrano.

## 4. Cosa chiedo al revisore, in ordine di utilità

**R1. Criterio di "regola verificata" (da scrivere prima di toccare i dati sigillati).**
Bozza mia, **non approvata**: una regola candidata, nata da un incidente
discovery di classe X, è "verificata" se scatta su almeno metà degli incidenti
sigillati della classe X e su nessun negativo. Positivi: incidenti sigillati di
classe X (2/2/3/4 per le quattro classi). Negativi: incidenti sigillati di altre
classi e finestre precedenti al guasto. Si riportano sempre i conteggi grezzi.
Domande: con 2 positivi "almeno metà" significa 1 su 2, è troppo permissivo?
"Scatta" richiede il componente giusto o basta un componente qualsiasi? Quale
tolleranza temporale intorno alla finestra del guasto? Serve una soglia sui
falsi positivi per ora di telemetria, non solo "nessun negativo"?

**R2. Semantica dell'esecutore delle regole K (non ancora scritto).** Proposta:
valutare le condizioni su ogni nodo/container che ha il KPI; finestre scorrevoli
(t−window, t]; con `all` le condizioni devono valere allo stesso t; `delta` =
ultimo − primo valore della finestra; KPI assente → astensione, non falso;
la classe della regola è quella dell'incidente discovery da cui nasce, perché il
campo `hypothesized_fault_type` è testo libero e non mappabile in automatico.
Domande: l'astensione per KPI assente è corretta o nasconde regole inutilizzabili?
La classe assegnata dall'incidente di origine introduce circolarità?

**R3. Come riportare numeri piccoli.** Proposta: conteggi esatti (k su n),
intervalli esatti di Clopper-Pearson, nessuna percentuale senza il denominatore,
nessun test di significatività tra varianti. Va bene? Come formulare la lettura
di RQ1 (3/8, 2/8, 1/8) in modo onesto?

**R4. Dichiarazione post hoc.** V5, V5.1 e il retry sono motivati da osservazioni
fatte durante i piloti, non decisi a priori. Proposta di testo per la sezione di
metodo, con la cronologia in `docs/RQ2_V5_1_POLITICHE_DICHIARATE_2026-11-16.md`.
Il doppio report strict/tollerante basta a neutralizzare il rischio?

**R5. Conflitto di interesse.** Claude ha scritto il codice di valutazione ed è
anche uno dei tre modelli soggetti (`claude-sonnet-5-5`, `claude-haiku-5-5`).
Quali controlli indipendenti mettereste: revisione di sola lettura dello scorer e
dei contratti, controlli a campione dei record grezzi, altro?

**R6. Lettura attesa dei risultati.** Per il capitolo RQ2: quali affermazioni sono
difendibili con 4 incidenti discovery, 3 modelli e una replica, e quali no
(per esempio sull'astensione frequente di K, sull'effetto di A1_PAVE, sul
confronto di token tra provider, che non è a parità di ragionamento esteso)?

## 5. Vincoli per chi legge

- Non ci sono accesso ai dati, alle chiavi o ai record su Drive: ragionare solo
  su questo testo e sul repository.
- Non leggere ground truth, scorer o i 11 incidenti sigillati per la discovery.
- Non proporre modifiche ai file congelati (V2–V5.1, risultati RQ1) né al SHA
  `ddb2ca4`. Proposte di codice solo su un branch `gpt/<tema>`, annunciato ad
  Alessio.
- Se un numero non è nel repository o in questo testo, scrivere "non verificato".
- Le risposte sono un secondo parere. Le scelte scientifiche le conferma Alessio
  e, per la parte di metodo, il relatore (Giovanni Morana).
