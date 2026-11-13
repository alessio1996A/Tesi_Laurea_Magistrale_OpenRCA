# RQ2-V2 — 7/7 test di provenance offline superati

**Data:** 13 novembre 2026.
**Fonte:** output Python di PyCharm comunicato dall'utente:

```text
Ran 7 tests in 0.021s

OK
```

## Ambito della conferma

Suite eseguita:

```powershell
python -m unittest discover -s src/tests -p "test_rq2_v2_tool_provenance_offline.py" -v
```

Dopo il fix di fixture sul branch sperimentale
`experiment/rq2-provenance-v2-offline-2026-11-13`,
commit sorgente/fixture `37350fd7948af7cce04147548b6e9f53c6c7a09a`,
l'utente ha eseguito la suite, riportando **7 test completati,
tutti OK**.

Test inclusi:
1. `test_duplicate_call_ids_fail_closed`;
2. `test_missing_ids_are_never_fabricated_and_fail_closed`;
3. `test_real_langgraph_toolnode_with_two_parallel_same_name_calls`;
4. `test_reverse_result_order_maps_exact_original_arguments`;
5. `test_single_legacy_call_remains_supported`;
6. `test_v1_v2_same_answer_metrics_and_original_event_fields`;
7. `test_wrong_result_id_rejected_not_mapped_by_name`.

Questo è un PASS limitato all'ambiente di test sintetico
e all'integrazione LangGraph con LLM e tool finti.
Non prova ancora la correttezza di RQ2 V2 in ambiente provider,
né la validità delle diagnosi rispetto alla ground truth,
né l'assenza di regressioni nell'intero progetto.

## Vincoli ancora attivi

- Sorgenti del protocollo V1, scorer, split GT-free
  e archivio Drive invariati.
- 39/72 stage RQ2-V1 registrati: 24 Gemini,
  15 Sonnet, 0 Haiku; 32 claim reali e 7 stage
  `BLOCKED_DEPENDENCY` offline.
- OOD test `LOCKED`.
- Nessun dispatcher V2 per API reali ancora autorizzato.
- Nessun cambio retroattivo dei risultati V1.

## Test di regressione successivi

Da eseguire **nell'ambiente locale PyCharm**, in ordine:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_evidence_bundle.py" -v
python -m unittest discover -s src/tests -p "test_rq2_real_langgraph_fake_llm.py" -v
python -m unittest discover -s src/tests -p "test_rq2_protocol_identity_preflight.py" -v
```

Questi file hanno rispettivamente 14, 13 e 14 test
identificati nel repository corrente, ma gli esiti
**non sono ancora stati verificati**.

Solo dopo il PASS di tutte le suite mirate si potrà
considerare la suite completa:

```powershell
python -m unittest discover -s src/tests -p "test_*.py" -v
```

Nessuna chiamata API, nessun Colab, nessun riuso
di claim V1. In caso di errore, bloccare la progressione
e conservare stdout/stderr per audit.
