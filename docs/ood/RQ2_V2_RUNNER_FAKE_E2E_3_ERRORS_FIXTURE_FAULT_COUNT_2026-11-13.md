# RQ2-V2 — Primo tentativo end-to-end fake: tre errori di contratto

**Data:** 13 novembre 2026.
**Origine:** log locale PowerShell/PyCharm condiviso dall'utente.
**Ambito:** test `src/tests/test_rq2_v2_runner_fake_e2e.py`, nessun provider reale.

## Risultato del primo tentativo

Comando:

```powershell
python -m unittest discover -s src/tests -p "test_rq2_v2_runner_fake_e2e.py" -v
```

Output riportato dall'utente:

```text
Ran 2 tests in 0.033s

FAILED (errors=3)
```

Gli errori sono tre perché il primo metodo usa due
`subTest`, uno per A1 e uno per A1_8R;
il secondo metodo confronta V1 con V2.
Tutti falliscono nello **stesso punto**, prima
dell'esecuzione del grafo:

```text
output.openrca_contract.OutputContractError:
Numero di guasti mancante nella richiesta
```

Stack:
`evaluation.experiment_runner.run_experiment` →
`output.v2_task_contract.task_output_instruction` →
`output.v2_contract.infer_requested_faults`.

## Analisi diretta del codice congelato

La funzione `infer_requested_faults(instruction)`
richiede un riferimento esplicito al numero di
guasti, come `one failure`, `two failures`
o `three faults`. Il fixture iniziale conteneva:

```python
INSTRUCTION = "Synthetic service issue: no ground labels available."
```

Non riportava alcuna cardinalità, quindi il
contratto ha rifiutato correttamente la richiesta.
Non è una prova di errore del tool mapping V2:
il runner si è arrestato prima dell'esecuzione
degli eventi LangGraph.

## Correzione minima

Solo il file di test
`src/tests/test_rq2_v2_runner_fake_e2e.py`
è stato modificato nel commit
`276da7be4e5ec5252ea144bc7b44f65af78e8010`.

La nuova istruzione sintetica è:

```python
INSTRUCTION = (
    "The synthetic cloud service experienced one failure "
    "in the observed time window."
)
```

Nello stesso fixture si verifica inoltre
`infer_requested_faults(INSTRUCTION) == 1`
prima di avviare `run_experiment`, con
`AssertionError` esplicito in caso contrario.

**Nessun cambiamento** a `task_output_instruction`,
`experiment_runner.py`, `graph_engine.py`,
`rq2_v2_graph_engine.py`, `rq2_evidence_bundle.py`,
scorer, GT, dati V1, prompt RCA, split o protocollo.

## Stato e prossime verifiche

La correzione è stata pubblicata sul branch
`experiment/rq2-provenance-v2-offline-2026-11-13`
ma **non è ancora stata testata localmente**.
Con working tree pulita:

```powershell
git fetch origin
git pull --ff-only origin experiment/rq2-provenance-v2-offline-2026-11-13
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_runner_fake_e2e.py" -v
```

In caso di PASS dei due test, rieseguire
`python -m unittest discover -s src/tests -p "test_*.py" -v`:
la precedente suite completa **812/812 OK**
è relativa al codice precedente all'introduzione
del nuovo file end-to-end.

Questo report non dichiara la V2 pronta
per provider reali: restano necessari un adapter
V2 indipendente, nuovi pin di sorgenti,
preflight, preregistrazione e approvazione
del budget. Test OOD sempre LOCKED.
