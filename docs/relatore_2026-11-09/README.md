# Materiale per la revisione del relatore — 10 novembre 2026

**Branch documentale:** `docs/evaluation20-relatore-2026-11-09`

Questo branch deriva dal commit sperimentale immutato `e4845e7fe9a399e10dd2db6f320dfeaeeddf3379`. **Nessuna modifica a runner, prompt, harness, test o protocollo congelato.** Non far ripartire le 300 run.

## Materiali in questo branch

- [RELAZIONE_EVALUATION20.md](RELAZIONE_EVALUATION20.md) — relazione e tabelle complete: coorte, score Microsoft, ablazioni appaiate, conformità V2, risorse, limiti e domande per il professore.
- [confronto_openrca1.svg](confronto_openrca1.svg) — grafico dello score medio, baseline storica Microsoft vs tre modelli su cinque harness.

**Altri allegati disponibili nella conversazione ChatGPT (non ancora pubblicati su GitHub):** PDF con grafici, immagini PNG, notebook Colab di validazione comparativa e script Python. Non assumere che il `git pull` recuperi tali allegati.

## Aggiornare PyCharm senza alterare i risultati

Da terminale, nella copia locale del repository:

```bash
git status
git fetch origin
git switch --track origin/docs/evaluation20-relatore-2026-11-09
```

Se la branch esiste già localmente: `git switch docs/evaluation20-relatore-2026-11-09 && git pull --ff-only`.

Se hai modifiche locali non salvate, **non** fare uno switch forzato: completa commit o stash dopo averle riviste.

Il notebook Colab allegato va eseguito solo con i dati già congelati in Google Drive: prima verifica il commit e gli SHA, poi controlla `row_id`, istruzioni e task dei 20 incidenti negli archivi Microsoft e ricalcola gli score con il codice Microsoft. Nessuna chiamata LLM o riscrittura delle 900 sorgenti.

**Interpretazione:** superiore all'archivio storico non significa superiorità causale di harness rispetto a RCA-agent, perché cambiano modello, prompt, tool, budget/epoca. Evitare claim sul benchmark intero o sui quattro guasti OOD non ancora studiati.
