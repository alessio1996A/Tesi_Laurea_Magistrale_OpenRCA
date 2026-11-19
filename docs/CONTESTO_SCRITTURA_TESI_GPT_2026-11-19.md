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
- **Normalizzare i risultati di RQ1** quando si presentano: il valore più basso (A0 dello stesso
  modello) come riferimento e gli altri come multipli, per mostrare il vantaggio. *Interpretazione:*
  non è chiaro se il riferimento sia «zero» o «uno»; si adotta il rapporto rispetto ad A0, affiancato
  sempre ai punteggi assoluti.
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

1. Le 8 regole di K sono state **proposte**, non «validate». Nessuna è verificata.
2. Esito L2: **TP 0, FN 0, TN 5, FP 2** (5 veri negativi, 2 falsi positivi). Non «5 veri positivi».
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
