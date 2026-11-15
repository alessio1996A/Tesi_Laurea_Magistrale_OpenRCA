# RQ2-V2 — Colab SDK RUNTIME PINNED: 6/6 versioni e 4/4 SHA PASS

Data 2026-11-15. Evidenza realmente fornita dall'utente
dopo SDK isolation con `pip --target` sotto
`/content/rq2_v2_pinned_sdk_py313`, Python Colab 3.13.18.
Non è un aggiornamento in-place del Python globale Colab.
```text
=== RQ2-V2: RIPRISTINO SDK ISOLATO ===
PYTHON: 3.13.18
Installazione in /content (NON su Drive)
=== AUDIT SDK NEL PROCESSO ISOLATO ===
"status": "RQ2_V2_PINNED_SDK_AUDIT_NO_API"
"runtime_snapshot_ready": true
"frozen_rq1_factory_unchanged": true
"provider_requests_sent": 0
"can_execute_api": false
=== SDK SNAPSHOT ISOLATO: PASS ===
API LLM ESEGUITE: 0
```

Versioni effettivamente osservate:
- langchain-core 1.7.1 **MATCH**
- langgraph 1.2.18 **MATCH**
- langchain-anthropic 1.7.7 **MATCH**
- langchain-google-genai 4.4.2 **MATCH**
- anthropic 2.6.0 **MATCH**
- google-genai 2.34.0 **MATCH**

SHA dei quattro file SDK osservati sul subprocess isolato:
- anthropic: `a42ef507300287261fe0b215023672a97f8a9b01216a135d614bbede72fff680` **MATCH**
- google-genai: `b179b80a126a35c98b98aeefa701950304c38c8a1e117136a2270a0901fd93e4` **MATCH**
- langchain-anthropic: `c55a0cb8fed75b3d310dbddf03a455f95c3c1d47aab650317bf3c9e4bab62544` **MATCH**
- langchain-google-genai: `589106719f2038805a27ddd0c44c23d5e4a4486ea0d7116b38a83d37722ac27f` **MATCH**

`source_hashes_match` tutte true, `versions_match`
tutte true, `frozen_rq1_factory_unchanged=true`, nessuna
richiesta LLM, nessun file Drive modificato dall'installazione.

Il controllo precedente con Python GLOBALE era correttamente
`runtime_snapshot_ready=false`; NON va attribuito al target isolato.
Il reporter del target verifica metadata/versioni e byte SHA
*solo* in un sottoprocesso con `PYTHONPATH=DEPS:REPO/src`.
Non è una prova di disponibilità remota dei modelli.

**Nota sui vecchi mock RQ2 V1**:
`rq2_langchain_bridge_source_trace.py` richiede nel source
`RELEASE_SHA256 = None` di V1, mentre nel branch corrente il
file `rq2_ck_provider_transport.py` presenta una release V1
già pin (`a35c...`) di una campagna distinta. Non usare
i vecchi `rq2_langchain_fake_http_invoke` e
`rq2_langchain_parameter_mock_probe` come gate obbligatori
diretti RQ2-V2, né modificare V1 a None per bypassare il controllo.

**Prossimo check mirato consentito**:
`rq2_model_factory.assert_exact_runtime_snapshot()` nel
subprocess isolato e
`rq2_sdk_retry_mock_probe.run_offline_mock_probe` (SDK-only,
fake transport, non dipende da `RELEASE_SHA256=None`).
Questi non creano SDK client reali collegati alla rete:
Google retry_args pura in memoria; Anthropic chiave finta con
`httpx2.MockTransport`; nessuna API reale.
La versione/policy `TIMEOUT_SECONDS=300`, `GOOGLE_HTTP_ATTEMPTS=1`,
`ANTHROPIC_MAX_RETRIES=0` rimane RQ2-only.
I test precedenti no-network end-to-end sync del 12/11 restano
un precedente su QUESTA coppia di versioni/SDK SHA, non una nuova
prova di integrazione del dispatcher unificato in Colab.

**Stato**: G4A/F/G/H/I/J/K offline PASS (145 metodi),
Colab source preflight 29 file su commit
`601dc7c2f971b919962ff190e6feb192c4dd237a` PASS,
scratch lock + O_EXCL same-session PASS, SDK snapshot isolato PASS;
`LIVE_API_ENABLED=False`, RQ2-V2 Option A 0/180 reali, 11 OOD
locked, nessuna release scientifica unificata autorizzata.
Il branch GitHub è avanzato SOLO nei docs dopo il source preflight:
non presentare il nuovo HEAD come già verificato.
