# Continuità dopo revisione relatore — 10 novembre 2026

> **Documento di stato e decisioni, NON protocollo sperimentale.** Non cambia codice, dati, scorer, selezione, score né risultati congelati. Le formulazioni delle richieste del relatore sulla seconda fase provengono dal documento di continuità del 5 novembre e dalla comunicazione dell'utente del 10 novembre; **non sono citazioni letterali della registrazione**.

## Novità confermate dall'utente il 10 novembre 2026
- Il relatore ha **approvato il progetto presentato finora**, dichiarando **conclusa la prima parte** sperimentale su harnessing e confronto modelli.
- Il prossimo lavoro riguarda la **seconda domanda di ricerca**, su classi di guasto non coperte dalle regole esistenti, possibilità di proporre una nuova regola deterministica e verifica della sua generalizzazione a incidenti ulteriori.
- **Scadenza massima di consegna: 5 dicembre 2026** (aggiorna la vecchia data 1 dicembre presente nei documenti di novembre precedenti).

## Ricostruzione del colloquio del 5 novembre
Fonte: `CONTINUITA_TESI_OpenRCA_post_colloquio_2026-11-05.md` nel Drive dell'utente.
1. Prima domanda: ablazioni controllate fra livelli di harness e modelli (ora dichiarata completata dal relatore).
2. Seconda domanda: misurare che cosa succede su **classi non codificate nel motore di regole**, distinguendo riconoscimento del guasto, spiegazione tecnica e possibile pseudoregola.
3. **Human-in-the-loop, notifica/approvazione e auto-integrazione di regole: future work, non implementare**, salvo nuova decisione espressa dal relatore.
4. Una pseudoregola candidata non equivale a una regola validata; servono validazione tecnica indipendente e, per affermare generalizzazione, incidenti separati dalla scoperta.
5. Le classi sono nuove rispetto alla copertura delle regole, **non necessariamente sconosciute al modello LLM**.

## Stato tecnico della prima parte
- Repository: `alessio1996A/Tesi_Laurea_Magistrale_OpenRCA`.
- Commit sperimentale EVALUATION20: `e4845e7fe9a399e10dd2db6f320dfeaeeddf3379`.
- Campagna EVALUATION20: 20 incidenti (10 cloudbed-1, 10 cloudbed-2), 5 harness, 3 modelli, 300 tentativi, 295 completi, 5 errori provider conservati come missing.
- Freeze: `f53effaa81fada14bab31b50ba0983e3642ff818294ac43550587e6982e4ee5f`; scoring ufficiale Microsoft post-freeze.
- Report dettagliato: `docs/relatore_2026-11-09/RELAZIONE_EVALUATION20.md`.
- Dati raw, piani, output e score immutabili sono in Google Drive `MyDrive/Tesi_OpenRCA/data`; non supporre che siano tutti versionati come blob Git.
- **Le 8 regole implementate non equivalgono alle 11 classi della partizione 11+4.** Le quattro classi tenute fuori sono annotate nelle note precedenti come: node CPU spike, container write I/O load, container process termination e container packet loss. Verificare la tassonomia sui manifest prima di selezionare nuovi incidenti.
- Il confronto con l'RCA-agent Microsoft storico è contestuale, non una prova causale a parità di modello, prompt, strumenti e budget.

## Seconda fase: punti ancora da progettare (non impegnano a esecuzioni)
- Inventario GT-free dei casi realmente disponibili per le quattro classi riservate, senza leggere etichette nei flussi decisionali dell'agente.
- Definizione esplicita del livello minimo: diagnosi e spiegazione/pseudoregola **oppure** anche codifica e test offline di una regola candidata, soltanto se scientificamente fattibile e concordato.
- Separazione netta **discovery vs verifica su incidenti mai impiegati per derivare la regola**, con guardie contro leakage; valutare se i dati permettono davvero una prova di generalizzazione.
- Nuovo protocollo/versioni/branch, preregistrazione, test PyCharm prima di campagna Colab; niente chiamate API a pagamento senza autorizzazione dell'utente.
- Non modificare l'esperimento EVALUATION20, non ritoccare le soglie sulla coorte finale, non usare scoring o ground truth durante l'inferenza.
- Human-in-the-loop e auto-installazione come future work secondo indicazioni recuperate dal colloquio del 5 novembre.

## Pianificazione della scrittura voluta dall'utente
- **Prima concludere esperimenti e discussione delle due domande di ricerca**; nel frattempo curare solo la tracciabilità tecnica, non stendere anticipatamente tutti i capitoli.
- **Dopo** risultati finali: proporre al professore indice, capitoli e paragrafi, scegliere il template accettato dall'Università/relatore e ottenere feedback sull'impostazione.
- Riservare orientativamente **circa dieci giorni** alla stesura e alla revisione, senza perdere di vista la consegna massima del 5 dicembre.
- Conservare come fonti primarie codice, commit, documenti di progettazione, log, dataset, protocolli, run, hash, grafici, scoring e le motivazioni delle decisioni; **la memoria della chat non sostituisce Git e Drive**.

## Metodo di archiviazione da seguire nella fase 2
Per ogni nuova decisione/esperimento produrre: `docs/` (domanda, motivazione, design, change log, limiti), `src/` e `tests/` (codice e test su branch nuovo), `notebooks/` (Colab riproducibile), Google Drive (manifest/piani/claim/risultati in create-only), freeze SHA e `docs/` (scoring, tabelle, interpretazione). Questo è un **impegno di metodo per i prossimi passi**, non una dichiarazione che materiali futuri esistano già.

## Fonti documentali e riferimenti
- `docs/HANDOFF_NUOVA_CHAT_TESI_OPENRCA_2026-11-02.md` sul branch `presentation/relatore-2026-11-02`.
- `CONTINUITA_TESI_OpenRCA_post_colloquio_2026-11-05.md` in Google Drive.
- `docs/relatore_2026-11-09/RELAZIONE_EVALUATION20.md` e notebook Colab associato sul branch documentale.

> **Da verificare prima di finalizzare il protocollo:** eventuale trascrizione letterale di nuove indicazioni del professore dopo l'approvazione del 10 novembre. La prima parte è chiusa per decisione del relatore riportata dall'utente.
