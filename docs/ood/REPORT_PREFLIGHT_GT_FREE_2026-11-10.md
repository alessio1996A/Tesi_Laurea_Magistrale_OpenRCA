# Fase 2 — Risultato del primo preflight OOD (10 novembre 2026)

**Fonte:** stdout Colab condiviso dall'utente, commit verificato `7ae250fc420048f36853ed56e18ea1ecbe15f5d3`, script `src/evaluation/ood_holdout_preflight.py`. Questo documento registra risultati osservati, **non** costituisce un piano discovery/test già congelato.

## Integrità

- `source_verified: true`.
- SHA256 `split_market_v1.csv`: `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`.
- SHA256 `benchmark_inputs_market.csv`: `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`.
- Split: `development=92`, `evaluation=23`, `mixed_quarantine=18`, `ood_holdout=15` (148 query).
- Quindici query OOD: 6 cloudbed-1, 9 cloudbed-2; tutte le sette task presenti, con conteggi `1/4/1/1/5/1/2` per task_1..task_7.
- Finestre tutte di 1800 s; 14 gruppi con finestre sovrapposte (connected components) e una sola coppia di overlap interna OOD: `cloudbed-1_q014` e `cloudbed-1_q030`, stessa finestra 1647766800–1647768600, task differenti.
- **Nessun overlap di finestra fra `ood_holdout` e gli altri tre split** nel manifest verificato.
- Audit di sola lettura: ground truth, `record.csv`, `query.csv`, telemetria, predizioni non letti; zero chiamate modelli; zero modifiche ai dati.

## Interpretazione

1. 15 è il numero delle **query OOD**, non di guasti, classi né episodi statisticamente indipendenti. Le 14 componenti senza sovrapposizioni interne rappresentano un limite superiore operativo di gruppi di finestra disgiunti, **non** una prova di indipendenza causale: incidenti separati possono essere correlati.
2. `cloudbed-1_q014` e `cloudbed-1_q030` **non devono essere assegnati a bracci discovery e test distinti**; condivisione della finestra implica possibilità di contaminazione.
3. L'assenza di overlap con altri split supporta l'isolamento temporale previsto, ma non elimina leakage da altre fonti (annotazioni, analisi precedenti, stesso fault injection o consultazione di GT).
4. I task sono diversi e non tutti chiedono la `root cause reason`; il solo score Microsoft task-specifico non basta a misurare la scoperta di una regola o la qualità della spiegazione.
5. **Non conosciamo ancora la cardinalità per ciascuna delle quattro classi riservate**, né se esistano abbastanza episodi indipendenti per discovery e test. Non introdurre stime arbitrarie.
6. Il protocollo deve essere stabilito prima delle inferenze Gemini e lasciato fisso anche per Sonnet/Haiku, se vogliamo chiamare il confronto cross-model indipendente. Un pilot Gemini sui casi OOD può consumare quegli stessi casi come sviluppo e non va successivamente presentato come prova indipendente dopo avervi ottimizzato il sistema.

## Passo successivo, limitato allo schema

Verificare **solo intestazioni e locazioni** di `record.csv` e `query.csv` per ciascun cloudbed, senza leggere alcuna riga, causa radice, prediction o score. Controllare presenza di file separati già estratti nel Drive e membri nell'archivio originale `Market.zip`, senza estrarre telemetria. I file `record.csv` e `query.csv` della root di Drive, eventualmente presenti, non possono essere assunti come rappresentativi di entrambi i cloudbed senza controllo del percorso/provenienza.

Solo dopo decidere come fare un **audit controllato delle etichette per la partizione statistica**, rigorosamente separato dal ramo d'inferenza, senza visualizzare etichette per caso nel prompt né scegliere incidenti in base alla facilità diagnostica. Qualsiasi accesso al GT in quell'eventuale audit deve essere dichiarato come tale: il presente preflight resta GT-free.

## Fonte archivistica

File nel branch `feature/ood-knowledge-transfer-audit-2026-11-10`; commit sorgente della prima parte `e4845e7fe9a399e10dd2db6f320dfeaeeddf3379`. Nessun dato sperimentale, run o risultato della fase 1 modificato.
