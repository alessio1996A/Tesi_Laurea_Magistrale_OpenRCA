# Contesto per GPT — scrittura della tesi (19 novembre 2026)

Questo documento si affianca a `CONTESTO_ALLINEAMENTO_GPT_2026-11-18.md`, che resta la fonte per i
fatti sperimentali (RQ1, RQ2, L1, L2, ablazione D→K). Qui c'è solo ciò che riguarda **come si scrive la
tesi**: ruoli, direttive del relatore, cose da non dire, regole sui numeri e sui riferimenti, cosa
chiediamo a GPT.

## 1. Ruoli

- **Alessio** è l'autore. Supervisiona tutto, riscrive con le proprie parole e deve saper spiegare a
  voce ogni paragrafo. La tesi deve essere sua e riconoscibile come tale, non un testo prodotto da un
  modello e solo approvato.
- **Claude** prepara le bozze a partire dalle prove nel repository, costruisce il file Word sul
  template e controlla numeri e riferimenti. Prende le decisioni di lavoro; quelle che cambiano cosa la
  tesi può affermare le approva Alessio.
- **GPT** è un **revisore indipendente**: controlla, contesta, propone. Non decide e non riscrive il
  testo definitivo. Ogni suo suggerimento passa da Alessio e da Claude prima di entrare nella tesi.

## 2. Direttive del relatore (colloquio del 19 novembre, da trascrizione)

Il testo della trascrizione è parlato e in alcuni punti confuso; dove ho interpretato, lo dico.

- Il lavoro sperimentale e l'impostazione vanno bene. Il relatore ha confermato il ragionamento di
  Alessio: gli esperimenti non si ripetono dopo aver visto i risultati, perché sarebbe come addestrare
  sui dati di test.
- **Normalizzare i risultati**, in generale (non solo RQ1), quando si presentano: il valore più basso
  come riferimento e gli altri come multipli, per mostrare il vantaggio. *Interpretazione di Alessio,
  da lui confermata:* il riferimento è A0 dello stesso modello. Si adotta il rapporto rispetto ad A0,
  affiancato sempre ai punteggi assoluti. Dove A0 vale zero (per esempio i punteggi di D in RQ2) il
  rapporto non è definito: lì si riportano i valori assoluti. **Eseguito per RQ1 il 19 novembre: sezione 10.**
- **Prima si invia al relatore** (per mail, in settimana, anche nel weekend): **abstract e
  introduzione**, circa 1,5–2 pagine. L'introduzione contiene contesto del problema, motivazioni,
  teoria di base, che cosa si farà, e la **suddivisione in capitoli**. Dopo l'accordo si scrive il
  resto; le conclusioni si riguardano insieme alla fine.
- Template: nessuno obbligatorio per la magistrale, ognuno scrive come preferisce. Non serve stampare
  la tesi per il relatore.
- **Consegna 5 dicembre 2026.** Eventuali giorni extra per correzioni dopo un rifiuto sono stati
  accennati ma **non sono chiari** nella trascrizione: non si conta su di essi.
- Sulle **repliche** degli esperimenti il relatore ha risposto «No tranquillo». *Interpretazione:*
  non servono. Non si pianificano; restano un'opzione.
- Il relatore ha accolto l'idea del supervisore umano come sviluppo futuro e il limite del dataset
  piccolo come limite da dichiarare.

## 3. Tre imprecisioni dette a voce, da non portare nella tesi

Le prime due sono errori di Alessio nell'esposizione orale; il relatore non le ha corrette, quindi
vanno corrette nel testo scritto. La terza è una formulazione troppo forte.

1. Le 8 regole di K sono state **proposte**, non «validate». Nessuna è verificata.
2. Esito L2: **TP 0, FN 0, TN 5, FP 2** (5 veri negativi, 2 falsi positivi). Non «5 veri positivi»
   (errore di esposizione).
   Solo 1 regola su 8 è arrivata a L2.
3. «L'agente ha sempre bisogno di un supervisore umano» è troppo forte. I dati mostrano che **generare
   non equivale a validare** e motivano una fase di supervisione; non dimostrano che serva un umano.

Altre cautele già concordate: non «C è inutile»; L2 **non è cieco** (sigillati già aperti); un solo
caso di studio per L2; gli intervalli di A1 meno A0 per Haiku e Gemini includono lo zero; il numero
di incidenti di development davvero usati non è 92 (la coorte dei confronti congelati è di 8 casi,
più casi di prova): citare dal protocollo, non a memoria.

## 4. Regole di scrittura

- **Ogni numero ha una fonte** nel repository (file, riga del registro, commit). Se non è verificato
  si scrive «non verificato» o non si scrive.
- **Nessun riferimento bibliografico entra senza un controllo su fonte reale** (articolo, DOI, pagina
  ufficiale). GPT può proporre piste, ma **non deve inventare** autori, anni, titoli o numeri di
  pagina: se non è sicuro, lo scrive.
- Punto di partenza bibliografico: i tre documenti del Project (paper OpenRCA, paper con PAVE,
  documento sull'agent harnessing). Il file `2606.27154v2.pdf` è OpenRCA 2.0, **non** il benchmark
  usato: i dati sono OpenRCA 1.0, sistema Market.
- Lingua: italiano (salvo diversa indicazione di Alessio). Terminologia fissa: D, C, K, L1, L2,
  harness, discovery, sigillati, OOD.
- Mai affermare più di quanto i dati permettano: fattibilità, non generalizzazione.

## 5. Che cosa chiediamo a GPT

1. **Controllo dei fatti**: confronta ogni affermazione con il contesto del 18 novembre e segnala
   incoerenze.
2. **Affermazioni troppo forti** rispetto ai dati: citarle con la frase esatta.
3. **Coerenza e chiarezza**: struttura dell'argomentazione, ordine delle sezioni, terminologia.
4. **Stile**: segnalare passaggi poco chiari o ripetitivi, **senza riscrivere** il testo.
5. **Piste bibliografiche**, ciascuna marcata «da verificare».

Formato della risposta: problemi in ordine di gravità, ciascuno con la frase citata, il motivo e la
correzione proposta; poi i suggerimenti; infine ciò che non ha potuto verificare.

## 6. Flusso per ogni sezione

1. Claude scrive una bozza con le fonti dei numeri accanto.
2. Alessio la legge e la riscrive con la propria voce, o la discute a voce con Claude; si verifica
   che sappia spiegarla.
3. Claude ricontrolla fatti, numeri e riferimenti sul testo di Alessio.
4. GPT fa la revisione indipendente; le osservazioni passano da Alessio e Claude.
5. Si inserisce nel Word.

## 7. Calendario proposto (non concordato col relatore)

- Entro il 22 novembre: abstract, introduzione e indice dei capitoli, da inviare al relatore.
- Dopo il suo accordo: capitoli 1–2 (contesto e fondamenti), poi RQ1 con la normalizzazione, poi RQ2.
- Entro il 4 dicembre: conclusioni, limiti, revisione complessiva. Consegna il 5 dicembre.
- Rimandati a dopo la scrittura: pulizia del repository, correzione di 3 test obsoleti, commento dei
  moduli rimasti.

## 8. Regole di lavoro invariate

Decide Claude, GPT affianca; nessuna email a nome di Alessio senza il suo permesso (solo bozze);
nessuna modifica ai risultati congelati; si resta nel tema (miglioramento della RCA tramite
harnessing).

## 9. Template: tesi triennale di Alessio (solo impaginazione, struttura, tono)

Alessio ha fornito il Word della triennale (Ingegneria Informatica, relatore prof. Ascia, a.a.
2022/2023; circa 92 pagine nella conversione in PDF e circa 15.000 parole nei paragrafi). Serve come
modello di struttura e impaginazione: **il contenuto non si riusa**.

- **Ordine delle parti:** copertina, abstract (una pagina, 181 parole, in italiano), indice con numeri di
  pagina, introduzione, capitoli numerati, conclusioni, ringraziamenti, indice delle figure, indice delle
  tabelle, bibliografia numerata [n].
- **Copertina:** logo dell'Università di Catania, Dipartimento di Ingegneria Elettrica Elettronica e
  Informatica, Corso di Laurea in Ingegneria Informatica, nome, titolo in maiuscolo corsivo, relatore
  («Chiar.mo Prof.»), anno accademico.
- **Formato:** A4; Times New Roman 12 pt, giustificato, interlinea 1,5, spazio dopo il paragrafo 10,5 pt.
  Titolo di capitolo 17 pt grassetto centrato (spazio prima 54 pt, dopo 30 pt); titolo di sezione 15 pt
  grassetto a sinistra; didascalie 9 pt grassetto centrate sotto la figura («Figura 1.1 …»). Margini 3 cm
  sopra e sotto, 3,5 cm a sinistra e a destra; numero di pagina in basso al centro.
- **Introduzione della triennale:** 356 parole in un solo paragrafo (circa 1,3 pagine) che contiene
  contesto, obiettivo e descrizione capitolo per capitolo. Il relatore della magistrale chiede un'introduzione di
  1,5–2 pagine con i contenuti elencati nella sezione 2: a questo formato (circa 270 parole per pagina)
  sono circa 400–540 parole. *Interpretazione:* l'abstract è a parte, su una pagina propria come nella
  triennale (circa 180 parole); la trascrizione non dice se il limite di pagine lo includa.
- **Tono:** italiano espositivo. Il modello di tesi del dipartimento (inviato da Alessio il 19 novembre)
  suggerisce la forma impersonale («è stata condotta un'analisi», «si sono ottenute prestazioni migliori») e
  sconsiglia la prima persona («abbiamo ottenuto»). La triennale usava «andremo a descrivere»; per la magistrale
  si segue il modello. Citazioni nel testo «Cognome (anno)» o «Cognome et al. (anno)», con pagina dopo i due
  punti se si cita un passo; bibliografia in ordine alfabetico «Cognome Nome, anno, Titolo, sede».
- **Ordine delle parti nel modello:** copertina, riassunto (abstract), indice, introduzione (non numerata), capitoli
  numerati, conclusioni, ringraziamenti, indici di figure/grafici/tabelle (se ci sono), bibliografia. Numerazione
  delle pagine da 1 a partire dall'introduzione; copertina, abstract e indice senza numero. Figure e tabelle
  numerate per capitolo («Figura 2.1»), con didascalia autosufficiente. L'introduzione non deve anticipare le
  conclusioni.
- **Da non replicare:** la triennale contiene alcuni refusi e una bibliografia fatta di pagine web. Per la
  magistrale ogni riferimento deve essere una fonte verificata (articolo, DOI, pagina ufficiale).
- **Deciso da Alessio (19 novembre):** lingua della tesi italiano; anno accademico in copertina 2025/2026.

## 10. Risultati RQ1 normalizzati rispetto ad A0 (eseguiti il 19 novembre)

Fonte: `docs/RQ1_NORMALIZZAZIONE_RISULTATI_2026-11-19.md` e riga 50 del registro delle decisioni.
Analisi descrittiva post hoc dei 300 tentativi di EVALUATION20 (20 incidenti, 3 modelli, 5 varianti; 295
con punteggio). Le 15 medie già riportate sono state riprodotte prima di usare qualsiasi numero. Il
riferimento è A0 dello stesso modello. Ogni cella riporta il multiplo rispetto ad A0 e se l'intervallo
bootstrap al 95% della **differenza** da A0 esclude o include lo zero (non corretto per confronti
multipli). I valori assoluti originali sono nel documento sorgente e non sono stati modificati.

| Misura | Modello | A0: media (n) | A1 | A1_8R | A1_8R_Planning | A1_PAVE |
|---|---|---|---|---|---|---|
| Punteggio medio | sonnet | 0,117 (20) | ×3,40 (IC esclude 0; n=20) | ×3,72 (IC esclude 0; n=20) | ×3,15 (IC esclude 0; n=20) | ×4,33 (IC esclude 0; n=20) |
| Punteggio medio | haiku | 0,142 (20) | ×1,62 (IC include 0; n=20) | ×1,94 (IC include 0; n=20) | ×1,71 (IC include 0; n=20) | ×2,27 (IC include 0; n=20) |
| Punteggio medio | gemini | 0,079 (19) | ×2,11 (IC include 0; n=19) | ×1,46 (IC include 0; n=18) | ×2,79 (IC include 0; n=20) | ×2,72 (IC include 0; n=19) |
| Token medi | sonnet | 122215 (20) | ×0,77 (IC esclude 0; n=20) | ×0,77 (IC esclude 0; n=20) | ×0,55 (IC esclude 0; n=20) | ×0,60 (IC esclude 0; n=20) |
| Token medi | haiku | 132416 (20) | ×0,60 (IC esclude 0; n=20) | ×0,54 (IC esclude 0; n=20) | ×0,64 (IC esclude 0; n=20) | ×0,58 (IC esclude 0; n=20) |
| Token medi | gemini | 34864 (19) | ×1,23 (IC esclude 0; n=19) | ×1,54 (IC esclude 0; n=18) | ×1,11 (IC include 0; n=20) | ×1,07 (IC include 0; n=19) |
| Tempo end-to-end medio (s) | sonnet | 158,6 (20) | ×0,81 (IC include 0; n=20) | ×0,79 (IC include 0; n=20) | ×0,62 (IC esclude 0; n=20) | ×0,70 (IC esclude 0; n=20) |
| Tempo end-to-end medio (s) | haiku | 216,5 (20) | ×0,57 (IC esclude 0; n=20) | ×0,45 (IC esclude 0; n=20) | ×0,52 (IC esclude 0; n=20) | ×0,44 (IC esclude 0; n=20) |
| Tempo end-to-end medio (s) | gemini | 83,8 (19) | ×0,93 (IC include 0; n=19) | ×1,00 (IC include 0; n=18) | ×0,82 (IC include 0; n=20) | ×0,77 (IC esclude 0; n=19) |

**Letture consentite**
- Accuratezza: il multiplo è maggiore di 1 in tutte le 12 combinazioni (da 1,46 a 4,33), ma l'intervallo
  della differenza esclude lo zero solo per Sonnet. Per Haiku e Gemini sono stime puntuali non
  distinguibili da un effetto nullo con 20 incidenti; la mediana del punteggio è 0 in tutte le loro
  varianti. «3 volte» vale solo per Sonnet.
- Token: con Sonnet e Haiku ogni variante con harness ne usa meno di A0 (0,54–0,77 volte); con Gemini ne
  usa di più (1,07–1,54 volte).
- Tempo: Haiku sempre più veloce; Sonnet solo con Planning e PAVE in modo distinguibile; Gemini solo con
  PAVE.

**Cautele da rispettare nel testo**
- I multipli con A0 basso (Gemini 0,079) ingigantiscono differenze piccole: gli intervalli dei rapporti
  arrivano fino a 19,5. Si riporta sempre anche la differenza assoluta con il suo intervallo.
- Nessun confronto tra modelli (i token dei provider diversi non sono confrontabili).
- Il confronto primario preregistrato A1 − A0 è **appaiato** e si cita dalla relazione del 9 novembre
  (Sonnet +0,2795, Haiku +0,0875, Gemini +0,0928 su 18 coppie). Le tabelle normalizzate usano le medie di
  cella sugli incidenti con punteggio (Gemini 19 e 19) e per Gemini danno +0,088: la differenza è
  dichiarata. Anche per Gemini le variazioni A1_8R → Planning di token e tempo (−28,3% e −17,8%) differiscono
  da quelle della relazione (−27,8% e −17,2%); la causa probabile è la popolazione appaiata, **non
  verificata**. Per Sonnet e Haiku i valori della relazione sono riprodotti esattamente.
- Una sola esecuzione per cella, un solo sistema (Market), analisi post hoc: nessuna generalizzazione.
