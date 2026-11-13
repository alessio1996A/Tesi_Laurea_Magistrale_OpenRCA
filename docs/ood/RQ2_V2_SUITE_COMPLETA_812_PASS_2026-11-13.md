# RQ2-V2 — Intera suite locale PyCharm superata: 812/812

**Data:** 13 novembre 2026.
**Fonte:** output test PowerShell/PyCharm condiviso dall'utente.
**Branch sperimentale:** `experiment/rq2-provenance-v2-offline-2026-11-13`.
**Commit prima della registrazione:** `9860c5f2ca5ef4a62a7d8989c0cb8e14f2802cea`.

## Esito realmente osservato

L'utente ha eseguito nel proprio ambiente locale:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_*.py" -v
```

Output finale fornito:

```text
Ran 812 tests in 78.601s

OK
```

**812 test su 812 superati**, senza failure o error
segnalati dal riepilogo. Non è disponibile in questo
scambio il log dettagliato di ogni test, quindi
l'evidenza documentale di esecuzione si basa sul
riepilogo restituito dall'utente.

Precedentemente l'utente aveva confermato:
- 7/7 test della provenance V2;
- 14/14 test del bundler evidenze RQ2;
- 13/13 integrazione LangGraph con modelli finti;
- 14/14 preflight dell'identità di protocollo.

Non sommare automaticamente 48 + 812: la suite completa
include già i test mirati.

## Interpretazione e limiti

Sono confermati i risultati dei test automatici
eseguiti su branch sperimentale; non sono emerse
regressioni negli scenari coperti dalla suite.

Questo **non** costituisce ancora:
- validazione di un nuovo provider transport V2;
- validazione scientifica della correttezza diagnostica;
- autorizzazione di chiamate API a pagamento;
- evidenza di corretta generalizzazione sui guasti OOD;
- motivo per aggiornare retroattivamente risultati V1.

Il modulo `src/agent/rq2_v2_graph_engine.py`
conserva nella traiettoria gli ID originali delle
tool call e tool result; la sua esistenza nel
repository non equivale a un adapter V2 end-to-end.

## Gate successivo

Preparare, sempre sul branch sperimentale,
una integrazione V2 end-to-end **solo con fake LLM,
fake tool e nessun dato OpenRCA reale** che verifichi:
- runner → grafo originale → esecutore V2;
- invarianza degli output/metriche attese fra V1 e V2;
- matching univoco ID call/result anche con più call
  omonime nello stesso round;
- validazione e binding D→C senza invocare provider;
- fail closed in presenza di call ID errati/mancanti;
- nessuna scrittura su archivio risultati V1;
- nessun accesso a GT e OOD test.

Il codice e la logica V1 devono rimanere byte-identici.
Solo dopo la completa regressione di integrazione
si potrà definire una distinta preregistrazione V2
e discutere un piccolo pilot reale, con spesa approvata.
