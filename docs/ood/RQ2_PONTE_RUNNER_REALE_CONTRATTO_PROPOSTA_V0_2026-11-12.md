# RQ2 — Ponte fra runner storico e orchestrazione reale D→C→K (proposta V0)

**12 novembre 2026** — **DESIGN NON CONGELATO; NESSUNA API AUTORIZZATA**.  
L'analisi riguarda solo le interfacce sorgente e il log di test, non le risposte OOD. Il presente documento non abilita esecuzione e non cambia alcun protocollo RQ1.

## Base realmente verificata

- `test_rq2_mock_pipeline_integration.py`: l'utente ha prodotto `Ran 32 tests in 1.150s — OK`. I nomi nel log documentano **16 test di integrazione più 16 test dei contratti C/K importati per errore nel discovery**. Tutti superati. L'import della classe `unittest.TestCase` è stato corretto nel commit `0256dc7642f65b881dfe57034c4c3c2d4f3e94da`; ci si attendono 16 test solo integrazione alla prossima esecuzione, **non ancora ripetuta dopo la correzione**.
- Colab KPI development: 92 casi, 29/29 KPI in codice presenti numericamente, 123 nomi KPI complessivi in unione finestre, 6.722.921 righe numeriche. Questa osservazione non valida soglie/unità fisiche né dati OOD test.
- Componenti mock: `rq2_mock_journal.py` e `rq2_mock_pipeline_integration.py` **non** eseguono provider e **non** possono essere convertiti implicitamente in runner live.

## 1. Riutilizzo del codice senza cambiare RQ1

Le interfacce sorgente attuali sono:

- `evaluation.rq2_dryrun_plan.preview_market(root)` — verifica gli hash **dei due CSV GT-free** e costruisce il piano D/C/K candidato; `source_verified=True` vale **solo** qui dopo la lettura delle sorgenti, non in una copia arbitraria del piano.
- `evaluation.experiment_config.ExperimentConfig` — rappresenta `variant`, `case_id`, `model_name`, `model_provider`, `max_tool_rounds`, `variant_scheme`, `output_contract_mode` e percorsi dati. Nessuna chiave API dentro la configurazione.
- `evaluation.experiment_runner.run_experiment(config, llm=None, verbose=True, salva=False)` — **unica** implementazione D da riusare. Con `salva=False` restituisce il record in memoria, che il futuro orchestratore deve salvare in cartella RQ2 separata; i modi di salvataggio storici RQ1 non vanno riutilizzati sulla cartella dei risultati congelati.
- `evaluation.rq2_stage_binding.prepare_bound_c` e `prepare_bound_k` — preparano input C/K verificando il piano, l'identità della D, i riferimenti E###, lo status discovery e il binding con la precedente C. Restano **solo preparatori**, `can_execute_api=False`, non diventano guardiani di budget/credibilità del provider.
- `evaluation.rq2_output_contracts.validate_cause_probe` e `validate_candidate_rule` — validano i JSON dei risultati, non garantiscono verità della diagnosi o validità fisica delle regole.

## 2. Requisiti del successivo orchestratore live, in ordine

1. **Preflight reale delle sorgenti**: rileggere gli hash dei CSV GT-free congelati prima di ogni sessione; controllare `stage_id, case_id, phase, cloudbed, task_index, start_unix, end_unix, instruction` esattamente contro il manifest originale. Non accettare la sola presenza di una stringa `sha256` dichiarata in un oggetto.
2. **D solo dalla configurazione congelata**: selezionare `A1` oppure `A1_8R`, `variant_scheme=current`, `max_tool_rounds=6`, modello/provider in allowlist di **ID precisi e fissati**. Usare il runner esistente `run_experiment(..., salva=False)` e validarne identità, errore e traiettoria dopo il ritorno. Le chiamate effettive a provider rimangono bloccate finché manca autorizzazione esplicita e budget.
3. **C separata, senza tool**: solo dopo D con record integro (oppure produrre `blocked_due_to_D_error`), costruire il messaggio dal bundle osservativo, registrare input/system prompt hash e verificare output JSON o errore di provider. La C non deve vedere l'output finale D, il GT o le regole ricavate dalla coorte test.
4. **K separata, senza tool e solo discovery**: soltanto dopo C valida. Persistenza dell'output grezzo, esito JSON, evidenze, catalogo KPI e motivi di insufficiente formalizzabilità; `insufficient_evidence` è un risultato scientifico, non un errore da riscrivere.
5. **Artefatti create-only**: usare una radice nuova fuori dai risultati RQ1, nome stage derivato da identificatore hash, record sorgente e modello, risposta grezza e eventuali errori **distinti e immodificabili**. Scrittura con `O_EXCL` o modalità `x`, eventuale stato claim/in_progress tracciabile, audit di digest a riavvio. I file non devono essere sovrascritti dopo failure; serve una policy documentata per retry.
6. **Due gate separati**: il `MOCK_ONLY_NOT_RULE_FREEZE` del journal sintetico **non può mai sbloccare i test reali**. L'esecuzione reale dei casi test richiede la lista K discovery raccolta, un rapporto deterministico di formalizzabilità, la scelta del criterio primario, il catalogo operativo congelato e **il freeze scientifico prima di leggere i dati di test**. Evitare dinamiche di selezione in base allo score.
7. **Budget e controllo provider**: usare una stima basata su RQ1 con massimali distinti per discovery e test; memorizzare modello esatto, versione, temperatura, limiti token, retry e costi effettivi. Un piano con 204 stage può produrre più di 204 chiamate reali. Errori 503, timeout, output vuoto e JSON invalido rimangono stati espliciti; nessuna sostituzione silenziosa o retry che modifichi il protocollo.
8. **Valutazione GT isolata**: per RQ2-A/C usare scorer offline separati con input identificati solo al momento della valutazione. Il processo agent/tool/LLM non legge mai record di riferimento, etichette o score ufficiali.

## 3. Prima implementazione da affrontare

A. **Source-bound adapter read-only** che carichi da `preview_market` e manifest SHA-verificato il solo stage D discovery e validi la configurazione RQ1 senza chiamare modello. Deve rifiutare test prima del freeze, casi non pianificati, source non verificata, identità di modello non pinned e differenze di istruzione/finestra.

B. **Archivio persistente RQ2** create-only (con test di crash/restart), che conservi esiti anche invalidi. Non riutilizzare il mock journal per risultati reali, ma riusare il pattern di integrità già testato.

C. **Provider adapter C/K** implementato solo quando A/B sono verdi e gli ID esatti, costo, parametri, protocollo e autorizzazioni sono congelati.

Questo ordine mira a ridurre il rischio sperimentale senza creare un secondo sistema di esecuzione RCA. Nel frattempo la campagna RQ2 mantiene **stato DRAFT_NOT_EXECUTABLE** e nessuna API è chiamata.
