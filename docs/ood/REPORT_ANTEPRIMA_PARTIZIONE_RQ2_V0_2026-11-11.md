# RQ2 — Esito dell'anteprima partizione V0 (non congelata)

**Data:** 11 novembre 2026  
**Stato:** `DRAFT_NOT_EXECUTABLE`. Output Colab fornito dall'utente; codice eseguito al commit `ce7463fcbe19046399f6a6186a73aa40885a6f6c`. Sei test su dati sintetici in PyCharm: `Ran 6 tests in 1.059s — OK`. **Nessuna chiamata LLM, nessun file scritto, nessun piano di esecuzione autorizzato**.

## Risultati realmente osservati

- `audit=rq2_stratified_partition_preview_v0`, `source_verified=true`.
- Split SHA256: `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`.
- Manifest SHA256: `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`.
- Selettore: `min_sha256_over_singleton_windows_per_gt_class`, sale fisso `openrca-rq2-singleton-stratified-preview-v0-2026-11-11`.
- 4 query in discovery, **4 gruppi singleton**; 11 query in test, **10 gruppi**. Totale 15 query e 14 gruppi.
- **Distribuzione aggregata per classe:**

| Classe | Discovery | Test |
|---|---:|---:|
| node CPU spike | 1 | 2 |
| container write I/O load | 1 | 2 |
| container process termination | 1 | 3 |
| container packet loss | 1 | 4 |

- **ID discovery V0:** `cloudbed-2_q021`, `cloudbed-2_q040`, `cloudbed-2_q041`, `cloudbed-2_q076`.
- **ID test V0:** `cloudbed-1_q014`, `cloudbed-1_q021`, `cloudbed-1_q030`, `cloudbed-1_q032`, `cloudbed-1_q050`, `cloudbed-1_q059`, `cloudbed-2_q014`, `cloudbed-2_q026`, `cloudbed-2_q045`, `cloudbed-2_q058`, `cloudbed-2_q077`.
- La coppia multi-fault `cloudbed-1_q014`/`cloudbed-1_q030` resta **insieme nel test**.
- L'output NON mostra alcun mapping `case_id → classe`; il GT è stato letto soltanto dal modulo offline di partizionamento per stratificare. `read_ground_truth=true`, `read_telemetry=false`, `read_predictions=false`, `model_api_calls=0`, `files_written=false`.

## Revisione metodologica motivata prima di risultati LLM

La V0 soddisfa gli invarianti **minimi** di class balance e non-sovrapposizione dei gruppi, ma ha due proprietà non ideali:

1. **Tutte le quattro discovery sono su cloudbed-2**: potenziale sbilanciamento ambientale. Con questa selezione non viene esplorata in discovery la varietà di cloudbed-1, pur potendo conservare il test sui due cloudbed per varie classi.
2. **`cloudbed-2_q040` e `cloudbed-2_q041` sono finestre contigue**, cioè la seconda inizia nel momento in cui termina la prima. Non si sovrappongono, ma la continuità temporale è un potenziale fattore di dipendenza non colto dall'audit che raggruppava eventi solo quando erano anche della stessa classe e dello stesso componente.

**Decisione:** conservare integralmente il risultato V0 come evidenza di un controllo riuscito e della sua limitazione. **Non congelare la V0.** Prima di qualsiasi run o accesso ad output LLM, predisporre una V1 con:
- uno singleton discovery per classe;
- divieto di selezionare per discovery finestre contigue ad altre query OOD dello stesso cloudbed, anche di cause differenti;
- mantenimento di almeno un test per ogni classe in ciascun cloudbed in cui compare;
- bilanciamento quanto più possibile equo delle quattro discovery fra cloudbed-1 e cloudbed-2;
- tie-break deterministico e documentato, nessun adattamento a predizioni o score di modelli.

**V1 predisposta ma non ancora testata sul Market reale:** `src/evaluation/rq2_partition_preview_v1.py`, `src/tests/test_rq2_partition_preview_v1.py` e `notebooks/Colab_RQ2_Balanced_Partition_Preview_2026_11_11.ipynb`. La versione originale resta nel repository immutata; il protocollo di RQ2 non è stato congelato.

**Cautela:** il bilanciamento fra cloudbed e l'assenza di adiacenze non provano che le fault injection siano fisicamente indipendenti; l'evidenza resta esplorativa con 2/2/3/4 positivi test per classe.
