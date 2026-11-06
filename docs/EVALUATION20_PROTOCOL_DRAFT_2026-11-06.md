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
