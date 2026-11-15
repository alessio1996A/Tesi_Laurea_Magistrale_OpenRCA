# RQ2-V2 — Factory runtime e SDK-only mock PASS (15 novembre 2026)

## Esito effettivamente ricevuto dall'utente

Il subprocess Colab con Python 3.13.18 e `PYTHONPATH` isolato
`/content/rq2_v2_pinned_sdk_py313:/content/Tesi_OpenRCA_RQ2_Unified_Preflight/src`,
checkout PINNATO
`601dc7c2f971b919962ff190e6feb192c4dd237a`,
ha eseguito senza eccezioni
`evaluation.rq2_model_factory.assert_exact_runtime_snapshot()`
seguita da
`evaluation.rq2_sdk_retry_mock_probe.run_offline_mock_probe()`
dentro `network_forbidden()`.

Output letterale:
```text
RQ2_FACTORY_RUNTIME: PASS
=== SDK MOCK REPORT ===
"status": "SDK_LOCAL_MOCK_CHECKED_LANGCHAIN_NETWORK_POLICY_NOT_FROZEN"
"version": "rq2_sdk_retry_mock_probe_v0"
"source_snapshot_sha256": "79d209cd7678b9ca036699cfa572579a20c2a62c4fd021042adf9d5b90f5ee98"
"google": {
  "sdk_retry_args_local_attempts": {
    "default_no_options": 1,
    "explicit_attempts_1": 1,
    "explicit_attempts_2": 2
  },
  "client_constructed": false,
  "external_requests": 0,
  "langchain_google_forwarding_verified": false,
  "google_async_streaming_retry_verified": false,
  "google_internal_aiohttp_implicit_retry_verified": false
}
"anthropic": {
  "sdk_mock_503_attempts": 1,
  "requested_timeout_seconds": 15.0,
  "external_requests": 0,
  "external_credentials_used": false,
  "langchain_anthropic_forwarding_verified": false,
  "timeout_enforcement_under_network_stall_verified": false
}
"real_provider_requests": 0
"scientific_release_signed": false
"can_execute_D": false
"can_execute_CK": false
"can_execute_test": false
SDK MOCK: PASS — 0 API REALI
```

Altri flag reali: `read_market=false`,
`read_ground_truth=false`, `read_predictions=false`,
`files_written=false`. Nessun token acquistato, nessuna
richiesta provider, nessun GT. 11 OOD non sbloccati.

## Interpretazione corretta

**PASS** factory snapshot e comportamento SDK-only simulato.
Non certifica l'intero forwarding LangChain in questo specifico
test, effettivo timeout su rete bloccata, Google async/stream,
automatic aiohttp retry. Il vecchio gate V1
`rq2_langchain_bridge_source_trace` ha la precondizione
`RELEASE_SHA256 = None`, mentre nel branch attuale V1 ha un
release storico pin: non modificarlo per eseguire test V2.

Nel progetto esiste una precedente prova LangChain→SDK→HTTP
sincrona con MockTransport su identiche versioni e SHA,
documentata il 12/11 in
`docs/ood/RQ2_COLAB_FAKE_HTTP_INVOKE_2026-11-12.md`:
1 invio fake 503 per CK_tool_free e D_bound_tools per
entrambi i provider, 0 API; questa non dimostra la
singola richiesta per TUTTI i possibili metodi/percorsi
né il funzionamento di Gemini/Claude remoti attuali.
No claim a hard cap fatturazione, no approvazione API.

## Gating scientifico ancora aperto

`src/evaluation/rq2_v2_unified_scientific_release_contract.py`
richiede `transport_retries_proven_no_implicit_http_retry=true`
e `per_request_timeout_verified=true` prima di accettare
la futura release: **non impostare queste prove a true soltanto
sulla base dell'attuale SDK-only mock**.
La decisione del campo deve includere evidenza circoscritta
ai percorsi reali e limitazioni; non sbloccare un comando live
basandosi su precedenti test generici.

I 29 path source originali e source inventory SHA report
si riferiscono a commit 601dc7; i nuovi documenti GitHub
dopo tale commit fanno avanzare HEAD, ma non alterano
il codice sorgente fino a esplicito nuovo commit tecnico.
Prima del pilot: freeze source HEAD clean, price review,
budget operativo/consenso per uno specifico stage
D, release create-only con SHA esterno, single-writer
stessa sessione Drive. Dispatcher `LIVE_API_ENABLED=False`,
0/180 stage reali e 11 OOD locked.

**Nessuna necessità di ripetere 145 test offline o
riaprire il protocollo** per annotare questo SDK PASS.
