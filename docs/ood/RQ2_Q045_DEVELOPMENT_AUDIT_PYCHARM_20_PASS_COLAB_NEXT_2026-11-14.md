# RQ2 q045 — PyCharm 20/20 PASS, autorizzato soltanto audit development read-only

Data: 2026-11-14. L'utente ha eseguito sul branch di fix portabilita' Windows i test mirati:
```text
Ran 20 tests in 2.011s

OK
```

Anche il precedente prototipo `rq2_q045_warning_detector_synthetic.py` aveva registrato separatamente `Ran 31 tests in 0.018s; OK`. Totale 51 test superati in due esecuzioni differenti, **non** 51 diagnosi, non una suite generale.

## Stato

- `src/evaluation/rq2_q045_development_log_audit.py` audit descrittivo real-source read-only, validazione SHA-256 split/manifest, isolamento sviluppo rispetto a OOD/evaluation/quarantine, conteggi aggregati dei warning nei log servizio `productcatalogservice-*`.
- `src/evaluation/rq2_q045_warning_detector_synthetic.py` resta synthetic-only e **rifiuta** real data in assenza del source gate.
- **Nessuna prova di generalizzazione, nessuna regola scientificamente congelata, nessuna accuratezza, nessuna root cause DNS verificata**.
- I test synthetic dimostrano isolamento su fixture, non l'avvenuta esecuzione dell'audit sul Market reale.
- Risultati precedenti, K Gemini V1 e K Sonnet V2 immutabili; OOD test ancora LOCKED.

## Prossimo step Colab (solo lettura)

1. Fare checkout pulito del commit HEAD esatto di questo branch (da aggiornare secondo commit documentazione); non modificare la precedente directory Colab `/content/Tesi_OpenRCA_Sonnet_K_Live`.
2. Usare runtime scientifico 3.13.18 e dipendenze pinned già preparate; se il runtime cambia, stop anziché adattare il protocollo.
3. Montare Drive in sola lettura logica (nessuna scrittura in `MyDrive/Tesi_OpenRCA`); eseguire `python -m evaluation.rq2_q045_development_log_audit --data-dir /content/drive/MyDrive/Tesi_OpenRCA` con API keys rimosse dal processo.
4. Verificare che report `status=DEVELOPMENT_ONLY_EXPLORATORY_LOG_SIGNAL_PRESENCE`, `source_verified=true`, `reads_ground_truth=false`, `model_api_calls=0`, `files_written=false`, `scientific_freeze=false`, `ready_for_ood_test=false`; mostrare soltanto conteggi aggregati.
5. Il gate puo' interrompersi per `Development interval overlaps non-development split` o ZIP member mancante: NON rilassare i controlli e NON aprire gli 11 test per forzare il risultato. Ricontrollare input e documentare.

Il valore dell'audit e' verificare la presenza del segnale su altre finestre (development) prima di decidere se intraprendere o chiudere un confronto piu' costoso. Un warning generico puo' essere non-specifico per DNS; un'assenza non e' una negative certa senza completezza dei log.
