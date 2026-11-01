# Esecuzione accoppiata: preregistrazione, preflight e protezione API

**Stato:** il piano di sviluppo e' stato congelato in Google Drive
dall'utente, non ancora eseguito con Gemini.

Piano:
`/content/drive/MyDrive/Tesi_OpenRCA/data/protocols/a1_verify_paired_development_v1_cohort_v1.json`.

I file di split/manifest devono avere ancora gli SHA-256 presenti
nel piano; una differenza blocca completamente il runner.

## 1. Comando sicuro: nessuna chiamata Gemini

In Colab, nella directory del repository aggiornato:

```bash
PYTHONPATH=src python src/evaluation/manual_paired_batch.py \
  --data-dir /content/drive/MyDrive/Tesi_OpenRCA
```

Il comando predefinito:
- rilegge e ricostruisce ESATTAMENTE il piano selezionato, inclusi
  seed, ordinamento, conteggi, casi esclusi, configurazioni e hash;
- confronta gli split GT-free con i conteggi congelati (92/23/18/15);
- legge la SHA di Git HEAD del codice corrente;
- mostra le otto coppie, i 16 run IDs e lo stato di ciascuna;
- non apre Market.zip, non prepara prompt, non importa il modello,
  non legge ground truth, non usa strumenti di telemetria,
  non crea file e non fa alcuna richiesta API.

Se qualsiasi input o output esistente e' incoerente, si ferma.

## 2. Avvio esplicito della *sola* coppia q063

**Non avviare questo comando finche' non si e' discusso il
preflight e autorizzato il costo/API.**

```bash
PYTHONPATH=src python src/evaluation/manual_paired_batch.py \
  --data-dir /content/drive/MyDrive/Tesi_OpenRCA \
  --execute-pair cloudbed-1_q063 --confirm-api
```

Non esiste una modalita' `--execute-all`. L'esecuzione deve essere
autorizzata caso per caso. Per q063 l'ordine e' quello
preregistrato: A1_VERIFY poi A1.

Prima di chiamare il modello:
1. verifica che il caso appartenga alla coorte e non abbia run
   precedenti o marcatori di avvio;
2. prepara entrambi i report in offline usando gli stessi dati;
3. controlla che abbiano esattamente lo stesso SHA-256;
4. controlla finestra del caso e configurazioni comuni;
5. crea un file permanente `*.pair_started.json` in modo
   **esclusivo** (`open("x")`); non viene riciclato.

Poi il runner esegue i due bracci usando `run_experiment(...,
llm=None, salva=False)`, serializzando *direttamente* il risultato
in file distinti nel percorso:

`data/results/paired/a1_verify_paired_development_v1/`

Ogni output include predizione grezza, diagnosi, metriche, traiettoria
dei tool, errori e metadati `paired_provenance` con:
- hash del piano congelato e commit Git;
- SHA-256 dell'evidence report identico fra i bracci;
- run ID, indice dell'ordine di esecuzione;
- eventuali `integrity_issues` osservate.

**Non si valuta la ground truth** in questo modulo, neppure dopo
la scrittura: lo scoring ufficiale resta una fase separata a
predizioni congelate.

## 3. Gestione degli errori e dei costi

- Se la sessione Colab si interrompe, una chiamata API potrebbe
  essere stata fatturata anche senza output finale. Il marcatore
  blocca qualsiasi retry automatico.
- Se uno dei bracci non rispetta gli invarianti (report, variante,
  ID o budget), il runner salva il risultato con un campo di
  errore di integrita' e **non esegue l'altro braccio**.
- Se l'API solleva un'eccezione prima di restituire un risultato,
  il marcatore rimane, il run non viene rilanciato.
- `completed_never_rerun` significa che ci sono entrambi gli
  output e il marcatore, e non vanno modificati.
- `interrupted_or_partial_manual_review` richiede una revisione
  manuale; **non** cancellare il marcatore per ripartire.
- Se cambia il commit fra esecuzioni dello stesso protocollo,
  il preflight si blocca. Una nuova versione sperimentale
  richiede nuovo identificativo e protocollo.

La modalita' esclusiva `open("x")` evita le sovrascritture
intenzionali; una disconnessione durante la scrittura puo' lasciare
un JSON incompleto, che deve essere trattato come incidente e
non come invito a rilanciare l'API.

## 4. Interpretazione

Lo scopo e' confrontare l'effetto della policy di verifica
rispetto ad A1, **non dimostrare causalita' dal fatto che
un'anomalia sia stata rilevata**.

Il budget massimo di round con strumenti e' lo stesso, ma
il numero di tool call, le chiamate LLM e i token possono differire.
Servono tutti i contatori per stabilire se l'eventuale miglioramento
di accuratezza giustifica i costi. Otto casi con una sola replica
sono uno studio di fattibilita', non un test conclusivo.

I quattro piloti precedenti rimangono esclusi. Evaluation,
mixed_quarantine e OOD_holdout non vengono interrogati.

**Importante:** la suite precedente ha superato 209 test offline.
Il runner accoppiato aggiunge 18 nuovi test (totale atteso: 227)
che NON sono ancora stati eseguiti in PyCharm e vanno verificati
prima di autorizzare qualsiasi chiamata API.
