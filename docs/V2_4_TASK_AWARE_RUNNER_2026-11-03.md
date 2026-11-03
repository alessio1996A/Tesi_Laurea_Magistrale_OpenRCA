# V2.4 — Output conforme al task e integrazione nel runner comune

**Data:** 3 novembre 2026. **Stato:** implementazione sul branch V2, test PyCharm ancora da eseguire. Nessun nuovo run Gemini eseguito.

## Perché è necessario

L'audit sulle 32 predizioni V1 ha mostrato 30 validazioni legacy, 28 risposte conformi a struttura/cardinalità del contratto canonico e 8 predizioni fuori dalla finestra di telemetria. Il contratto canonico richiede **sempre** tre elementi, mentre il benchmark OpenRCA 1.0 ne valuta solo il sottoinsieme richiesto dal task. La finestra è un limite di lettura della telemetria e il timestamp della diagnosi fuori intervallo viene **segnalato**, non riscritto né considerato automaticamente una violazione del formato benchmark.

La guida originale di OpenRCA ([README](https://github.com/microsoft/OpenRCA)) ammette campi aggiuntivi nel JSON; l'articolo ICLR 2025, Appendix A.7, chiarisce che sono ignorati dallo scorer quando non richiesti. In presenza di più guasti, il README richiede ordine cronologico.

## Mappatura GT-free delle sette task

Derivata da `task_index` e dall'istruzione del file `benchmark_inputs_market.csv`, **non** da `query.csv`, `record.csv` o `scoring_points`. La mappatura è stata controllata sul manifest GT-free Market del progetto.

| Task | Campi obbligatori in ciascuna voce |
|---|---|
| task_1 | root cause occurrence datetime |
| task_2 | root cause reason |
| task_3 | root cause component |
| task_4 | root cause occurrence datetime; root cause reason |
| task_5 | root cause occurrence datetime; root cause component |
| task_6 | root cause component; root cause reason |
| task_7 | root cause occurrence datetime; root cause component; root cause reason |

## Contratto V2 task-aware

- Il JSON deve essere un oggetto con chiavi consecutive `"1"` ... `"N"`, senza chiavi duplicate.
- `N` si ricava solo dalla richiesta ufficiale visibile all'agente; il parsing è fail-closed su richieste ambigue.
- I **campi richiesti dal task** devono esistere, essere testuali/non vuoti, e i timestamp richiesti devono essere in formato locale `YYYY-MM-DD HH:MM:SS`.
- **Campi non richiesti** sono ammessi e non diventano surrogati per quelli obbligatori. I campi extra vengono registrati nell'audit.
- Un timestamp (se presente) fuori da `[start_unix, end_unix)` comporta un **warning di plausibilità** con offset, non una riparazione automatica né rifiuto del JSON task-aware.
- Quando il task richiede la data e ci sono almeno due guasti, l'ordine cronologico è obbligatorio in modalità enforce; l'audit registra separatamente il problema.
- Il validatore non conferma l'identificazione della vera causa. Nessun modello/ground truth/scorer viene invocato.

## Due modalità nuove nel runner esistente

- **`v2_audit`**: osserva la conformità task-aware e allega `output_contract_v2`. **Non modifica** `prediction`, `raw_response` o `json_status` del parser storico.
- **`v2_enforce`**: applica lo stesso contratto ai cinque agenti. Se l'output è valido, ricodifica **senza modificare i valori predetti**. Se non valido, `prediction=None` e `json_status` esplicito; **nessun retry LLM o riparazione**. Prima dell'esecuzione aggiunge al prompt soltanto le istruzioni sul formato e numero di cause derivati da `task_index` e `instruction` GT-free.

La modalità **`legacy` rimane il default** e i precedenti freeze/resti di esperimento sono immutati. Il nuovo prompt è applicato uniformemente a tutte le varianti in V2-enforce e viene identificato dal suo SHA nel risultato.

Quando `salva=True`, i nuovi output V2 vengono creati esclusivamente in `data/results/v2/`, con suffix `_v2_audit` o `_v2_enforce`. Il salvataggio usa `open("x")` e rifiuta sovrascritture. Non utilizzare il runner V1 paired per una nuova campagna V2: la campagna V2 richiede un protocollo e run ID nuovi, a loro volta da verificare e congelare.

## Test offline aggiunti

- `src/tests/test_v2_task_contract.py`: 15 test sui 7 task, cardinalità, extra campi, duplicati, timestamp e ordine cronologico;
- `src/tests/test_v2_runner_offline.py`: 6 test con runner e output sintetici (tutte le cinque varianti e protezione da sovrascritture);
- `src/tests/test_v2_frozen_prediction_audit.py`: 7 test, estesi con confronto task-aware.

Da root del repository, branch `feature/harness-v2-clean-2026-11-03`:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_v2_task_contract.py" -v
python -m unittest discover -s src/tests -p "test_v2_runner_offline.py" -v
python -m unittest discover -s src/tests -p "test_v2_frozen_prediction_audit.py" -v
```

**Non sono ancora stati eseguiti localmente**. La fase successiva è eseguire test PyCharm e, se passano, il medesimo audit Colab su 32 risultati **immutabili** per calcolare la nuova conformità task-aware. Dopo quei gate il runner V2 sarà pronto per la preregistrazione della nuova coorte.
