# RQ2-V2 — Primo test offline: 5 PASS, 2 FAIL per fixture senza ID

**Data:** 13 novembre 2026.
**Fonte:** output locale PyCharm/Python condiviso dall'utente.
Nessun token/provider reale o Market.zip coinvolto.

## Primo risultato effettivo

Comando:
```powershell
python -m unittest discover -s src/tests -p "test_rq2_v2_tool_provenance_offline.py" -v
```
Output: **7 test eseguiti, 5 OK e 2 FAIL**, in circa 0,078 secondi.

PASS:
- `test_duplicate_call_ids_fail_closed`;
- `test_real_langgraph_toolnode_with_two_parallel_same_name_calls`;
- `test_reverse_result_order_maps_exact_original_arguments`;
- `test_v1_v2_same_answer_metrics_and_original_event_fields`;
- `test_wrong_result_id_rejected_not_mapped_by_name`.

FAIL:
- `test_missing_ids_are_never_fabricated_and_fail_closed`:
  `EvidenceBundleError not raised`.
- `test_single_legacy_call_remains_supported`:
  osservazioni attese 1, osservazioni effettive 0.

## Analisi circoscritta

Entrambi i test falliti usano il costruttore
`_call(query, call_id=None)`, poi `_SyntheticGraph`
costruisce `AIMessage(content="", tool_calls=calls)`.
Quando una `tool_call` non ha un ID conforme, il
parsing/normalizzazione di `AIMessage` può
non conservare la chiamata nel campo
`tool_calls` utilizzato dall'esecutore. In quel
caso l'esecutore non vede alcun evento tool, il
bundle contiene zero osservazioni e il controllo
di ambiguità non viene raggiunto.

Questa è una **spiegazione del comportamento
del fixture da verificare con la riesecuzione**;
i log di unittest dimostrano che il bundle
vede zero osservazioni nel test legacy,
non dimostrano ancora da soli l'esatta
implementazione interna del validator LangChain.

## Correzione isolata, senza codice di produzione

Commit di correzione test:
`37350fd7948af7cce04147548b6e9f53c6c7a09a`.

Modificato esclusivamente
`src/tests/test_rq2_v2_tool_provenance_offline.py`.
Il fixture `_SyntheticGraph`, solo nel caso
degradato con ID mancante, fornisce direttamente
un `SimpleNamespace(tool_calls=...)` con
chiamate originali, per testare il comportamento
difensivo dell'esecutore. Per chiamate normali
con ID continua a usare un vero `AIMessage`.
I due test fanno ora un'asserzione esplicita
sugli eventi della traiettoria prima del bundle:
- doppia chiamata legacy: due `tool_call` +
  due `tool_result`, poi `EvidenceBundleError`;
- singola chiamata legacy: un `tool_call` +
  un `tool_result`, poi una osservazione valida.

**Non** sono cambiati:
`src/agent/graph_engine.py`,
`src/agent/rq2_v2_graph_engine.py`,
`src/evaluation/rq2_evidence_bundle.py`,
il protocollo congelato, i dati, gli hash,
gli artefatti o i claim V1.

## Gate di verifica successivo

Non dichiarare successo prima della riesecuzione
locale. Recuperare il nuovo commit nel branch
sperimentale con `git fetch origin` e
`git pull --ff-only` solo a working tree pulita,
poi rieseguire tutti i sette test.

Se qualche test fallisce ancora, **stop** e
analisi; niente Colab né API. Se passano tutti,
eseguire test mirati V1, RQ2 e successivamente
suite completa, conservando l'output.
La costruzione di una campagna V2 con provider
reali resta in una fase separata.
