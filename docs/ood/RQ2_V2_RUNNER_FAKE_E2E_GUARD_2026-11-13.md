# RQ2-V2 — Gate di integrazione runner→provenance→bundle→C (solo fake)

**Data:** 13 novembre 2026. Stato: codice test su GitHub; **non eseguito ancora in PyCharm**.

## Situazione consolidata

Nel branch sperimentale `experiment/rq2-provenance-v2-offline-2026-11-13`, l'utente
ha verificato `Ran 812 tests in 78.601s\nOK`,
comprendente sette nuovi test V2 e 41 test mirati.
La funzione `esegui_grafo_rca_v2` non è ancora
connessa a un dispatcher scientifico V2 reale.

## Nuovo test end-to-end sintetico

File:
`src/tests/test_rq2_v2_runner_fake_e2e.py`.

Il test invoca davvero `evaluation.experiment_runner.run_experiment`
di V1 **senza modificare quel file**.
Il preparatore del caso è sostituito soltanto nel test,
con un incidente artificiale `cloudbed-1_q999`,
un fake LLM e un tool finto `tool_get_node_metrics`.
Nel contesto del test, l'esecutore
`agent.graph_engine.esegui_grafo_rca` viene sostituito
**temporaneamente in memoria** con
`esegui_grafo_rca_v2`. Non viene scritta una
modifica nei sorgenti V1 o in un dispatcher di produzione.

Verifica:
1. A1 e A1_8R percorrono il vero runner e LangGraph;
   il fake LLM produce due richieste parallele allo
   stesso tool con ID differenti. Il bundle registra
   esattamente le due osservazioni attribuite alle
   rispettive richieste e genera E001/E002.
2. `prepare_cause_probe` crea offline l'input C
   collegato allo SHA del bundle, senza vedere il
   JSON diagnostico D, e marca `model_api_calls=0`
   e `ready_for_api=false`.
3. Con gli stessi dati fake, V1 e V2 hanno output,
   errori e metriche identici, escludendo soltanto
   le durate; rimuovendo gli ID dalla traiettoria
   V2, questa deve coincidere con V1.
4. Il bundle V1 rifiuta la traccia parallela
   omonima ambigua; il bundle V2 con ID validi
   accetta due osservazioni senza attribuzione
   arbitraria.
5. Nessun file/claim/split/Market/GT; nessun client
   provider. I dati fittizi sono fuori dalla
   coorte RQ2, e la richiesta di scrittura del
   runner è `salva=False`.

## Esecuzione locale PyCharm (PowerShell)

Controllare branch e working tree pulita:

```powershell
git branch --show-current
git status --short
```

Se pulita e il branch coincide:

```powershell
git fetch origin
git pull --ff-only origin experiment/rq2-provenance-v2-offline-2026-11-13
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_runner_fake_e2e.py" -v
```

**Esito atteso solo come ipotesi:** 2 test.
Non dichiararli PASS prima dell'output.
Se falliscono, congelare il traceback e
correggere soltanto la causa identificata,
senza alterare il protocollo V1 e senza API.

Dopo un PASS effettivo, rieseguire l'intera
suite perché è stato aggiunto nuovo codice di test:

```powershell
python -m unittest discover -s src/tests -p "test_*.py" -v
```

## Limiti metodologici

Questi test **non** costituiscono un runner scientifico
V2 autorizzato. L'eventuale adattamento reale della
pipeline richiederà nuova release, source pin,
claim create-only, preregistrazione separata,
budget dei provider e approvazione distinta.
La soluzione non può essere applicata a risultati V1
già registrati o al test OOD LOCKED.
