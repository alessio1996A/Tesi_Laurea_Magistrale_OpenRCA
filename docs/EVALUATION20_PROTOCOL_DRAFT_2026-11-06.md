# Protocollo EVALUATION20 — bozza del 6 novembre 2026

**STATO: PROPOSTA GT-FREE, NON CONGELATA, NESSUNA API AUTORIZZATA.**

## Coorti distinte

Gli 8 incidenti development già misurati (120 run, 3 modelli, 5 harness) rimangono parte dello studio esplorativo. Il freeze dello scoring ufficiale è conservato su Drive: data/results/scoring/v2/openrca_cross_model_dev8_official_comparison_v1.json, SHA256 975ff3b8f28aea16a94a9ca8cb1e69c36c7bdf818d855c1c4be274c34ab76e71.

Il nuovo obiettivo è selezionare **20 incidenti non utilizzati** tra i 23 dello split evaluation. Non usare quarantine o OOD holdout: rimangono riservati. La disponibilità di 20 casi eleggibili NON è ancora verificata.

## Selezione blind (prima di ogni nuova API)

Eseguire il nuovo modulo evaluation.evaluation20_preflight. Usa solo split, manifest e piano V3 congelati, con verifica delle fingerprint. Non legge query.csv, record.csv, Market.zip, telemetria, risposte o score. Applica il criterio conservativo di assenza di overlap temporale con qualsiasi development, quarantine e OOD, oltre che tra i nuovi casi. Richiede 10+10 cloudbed, tutti i sette task e almeno un multi-guasto per cloudbed. La selezione deterministica usa uno SHA256 di seed fisso e case_id; non sceglie casi in funzione dell'accuratezza.

Se la selezione è impossibile, fermarsi e discuterne: non indebolire in silenzio i criteri. La disgiunzione temporale da sola non prova indipendenza statistica.

## Disegno sperimentale da preregistrare

20 casi × 3 modelli (Gemini, Claude Sonnet, Claude Haiku) × 5 harness (A0, A1, A1_8R, A1_8R_Planning, A1_PAVE) × 1 replica = **300 nuove run previste**. Una sola replica limita la ripetibilità. Tutte le condizioni usano gli stessi casi, tool, budget di massimo 6 round, prompt diagnostico e logica dell'harness non ottimizzati sui nuovi risultati. I modelli e le versioni effettivamente disponibili devono essere registrati; le differenze di provider vanno dichiarate. L'eventuale modifica comportamentale non può essere descritta come sola correzione strumentale.

Prima di autorizzare API a pagamento: test unitari e fake LLM, pianificazione create-only con claim e output per run, resume senza retry ambiguo, SHA e provenienza, misura completa dei token per ogni chiamata su tutte le varianti, tempi comparabili, verifica output JSON, stima dei costi e approvazione esplicita del budget. Non inserire lo scoring nella pipeline di inferenza.

## Analisi dopo il freeze

Usare lo scorer ufficiale Microsoft sulla raw_response originale, separandolo da conformità JSON e score della predizione accettata. Ipotesi principale: differenza appaiata A1-A0 entro ciascun modello; altre ablation come confronti secondari, riportando win/tie/loss, score medio, strict, incertezza e compromessi di efficienza. La baseline storica Microsoft sui medesimi casi è solo un confronto retrospettivo, non controllato a parità di modello. Rendicontare development ed evaluation **separatamente**.

La domanda sulla conoscenza non codificata nelle otto regole rimane un secondo studio da discutere con il relatore, senza assumere apprendimento automatico implementato.

## Esito audit GT-free in Colab (6 novembre 2026)

L'utente ha eseguito l'audit nel proprio Colab; output riportato:
status PROPOSED_GT_FREE_NOT_FROZEN_NOT_EXECUTED, evaluation_rows_checked=23,
strict_candidate_count=23, cloudbed-1=12, cloudbed-2=11. Tutti i sette
task rappresentati: task_1=3, task_2=3, task_3=1, task_4=3,
task_5=4, task_6=7, task_7=2.

La proposta seleziona 10+10 casi e **tre istruzioni multi-guasto**
(q006, q023 cloudbed-1; q031 cloudbed-2). Elenco dei 20 ID, vincolato
anche nel modulo di preregistrazione:

- cloudbed-1_q000, q003, q006, q012, q015, q019, q023, q026, q058, q062.
- cloudbed-2_q028, q031, q036, q039, q044, q047, q054, q064, q069, q074.

Nessuna API chiamata, nessuna scrittura e nessuna lettura di ground truth
durante la selezione. I 20 casi non sono ancora stati eseguiti né
valutati. **Prima di creare il piano create-only e autorizzare API,
finalizzare il runner, collaudarlo e congelare il commit definitivo**:
il piano registra il commit e deve corrispondere al codice di esecuzione.
