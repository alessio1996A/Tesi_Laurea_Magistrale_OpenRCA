# RQ2-V2 — Regressioni mirate superate: 41/41

**Data:** 13 novembre 2026.
**Origine:** output PowerShell/PyCharm trasmesso dall'utente.
**Branch:** `experiment/rq2-provenance-v2-offline-2026-11-13`.
**Head prima della registrazione:** `909e248b384e280edfa21d8628adc2a44c5a4291`.

## Esiti realmente osservati

| Suite | Esecuzione | Esito |
|---|---|---|
| `test_rq2_evidence_bundle.py` | Ran 14 tests in 0.420s | **OK (14/14)** |
| `test_rq2_real_langgraph_fake_llm.py` | Ran 13 tests in 0.697s | **OK (13/13)** |
| `test_rq2_protocol_identity_preflight.py` | Ran 14 tests in 0.009s | **OK (14/14)** |
| **Totale tre suite** | 41 | **OK (41/41)** |

La precedente suite sperimentale
`test_rq2_v2_tool_provenance_offline.py`
aveva riportato **7/7 OK** in 0.021s dopo la
correzione del solo fixture sintetico.
**Totale test mirati verificati: 48**, senza
affermare che 48 siano necessariamente casi univoci
su tutto il progetto o che siano già passati nella
suite globale.

## Cosa significa — e cosa non significa

Confermati:
- il bundler fail-closed vigente passa i propri test;
- il percorso LangGraph con fake LLM passa la regressione;
- i controlli d'identità del protocollo RQ1/RQ2
  congelato passano la suite mirata;
- la provenance V2 passa i test sintetici su
  ID, associazione di risposte invertite e compatibilità
  legacy.

Non ancora dimostrati:
- esito della **suite completa** `test_*.py`;
- correttezza del collegamento V2 all'intero
  `experiment_runner` e alla nuova registrazione
  scientifica, non ancora implementati come
  percorso reale V2;
- validità diagnostica e generalizzazione su
  ground truth / test OOD;
- correttezza o convenienza di una campagna
  reale con provider Anthropic/Google.

## Prossimo gate locale

Con `git status --short` pulito, eseguire
nel branch sperimentale:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_*.py" -v
```

Conservare il riepilogo `Ran N tests...` e `OK`
oppure l'intero traceback se ci sono errori.
**Nessuna modifica preventiva e nessuna API**.

Se tutti i test passano, prima di qualsiasi
nuova esecuzione provider resta necessario
un nuovo gate tecnico: progettazione
di un adapter V2 distinto, test end-to-end fake
con il runner RQ1 originale, source pin,
nuovi claim create-only, budget e
preregistrazione separata, test OOD locked.

Il branch V1 e i 39 artefatti RQ2 registrati
restano invariati, senza tentativi ripetuti o
rivalutazione retroattiva.
