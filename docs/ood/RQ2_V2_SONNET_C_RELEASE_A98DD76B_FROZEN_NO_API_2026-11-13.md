# RQ2 V2 — Release C Sonnet frozen, live call not yet performed

Data 2026-11-13. Documento nel branch documentale separato dal commit scientifico. Non modificare HEAD dell'esecuzione C.

## Test e preflight osservati dall'utente

- PyCharm mirati: `Ran 16 tests in 0.601s\nOK`.
- Regressione completa: `Ran 883 tests in 87.286s\nOK`.
- Colab: `SONNET_V2_C_SOURCEBOUND_PREFLIGHT_OK`; no API, no Drive writes.
- Commit C: `d1d1d2eb20d030a2bb0da76ebc3c1d9f82e469ce`.
- Stage C: `rq2_v2_sonnet_q050_c_sourcebound_v1:cloudbed-1_q050:sonnet:A1:C`
- C binding SHA256: `08bc3e1d7e8e4b793cf559e7a5fdc9f5d91d4e0bf50fb2af2dd12b7ee89f231c`.
- Parent D record SHA256: `521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009`.
- Parent D bundle SHA256: `f63f1f0fd744497acc92814d8aabf80fb30cb08d8e5244ec62501d29052154d6`.
- C package SHA256: `49422ee1f91909514acc3cdf5868aa5c4e73990392804fe7b1fa8dec950e333f`.
- C system prompt SHA256: `81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42`.
- C prompt characters: `18084`; 8 evidences, 3 truncated due to explicit limit.

## Colab evidence — C release created, no API

```text
STATUS: SONNET_V2_C_RELEASE_FROZEN_NO_API
RELEASE_SHA256: a98dd76b962cf6ae37978c9fc362fa354ec375fd1f69f5d6ab605963c7f7853c
STAGE_ID: rq2_v2_sonnet_q050_c_sourcebound_v1:cloudbed-1_q050:sonnet:A1:C
CODE_COMMIT: d1d1d2eb20d030a2bb0da76ebc3c1d9f82e469ce
C_BINDING_SHA256: 08bc3e1d7e8e4b793cf559e7a5fdc9f5d91d4e0bf50fb2af2dd12b7ee89f231c
PARENT_RECORD_SHA256: 521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009
C_PACKAGE_SHA256: 49422ee1f91909514acc3cdf5868aa5c4e73990392804fe7b1fa8dec950e333f
MAX_LLM_REQUESTS: 1
OPERATIONAL_LIMIT_USD: 5.0
API_CALLS: 0
CLAIM_CREATED: FALSE
RECORD_CREATED: FALSE
OOD_TEST: LOCKED
```

Release C conservata create-only nel namespace `data/rq2_v2_provenance/sonnet_q050_c_v1/release_v1.json`; letta e verificata con `read_c_release` e `audit_restart` prima di eseguire.

## Vincoli live C da rispettare

- Nuova chiamata pagata Anthropic `claude-sonnet-5-5` *una sola volta*, max output 4096, timeout richiesta 300 secondi, SDK max_retries=0.
- La soglia $5.00 della release C e' **metadata di autorizzazione e valore di audit**, NON un hard cap o stop operativo per richiesta singola; l'attuale C driver calcola il costo **dopo** la risposta, non deve essere descritto come enforcement.
- Citta' di data root `/content/drive/MyDrive/Tesi_OpenRCA`; checkout C separato `/content/Tesi_OpenRCA_Sonnet_V2_C_Preflight` e deps `/content/rq2_sonnet_v2_preflight_deps`.
- Ricontrollare commit pulito, runtime, SHA release, parent D frozen, source C binding, assenza di C claim/record e modello. Credenziale solo Colab Secrets.
- Una volta iniziato, claim scritto O_EXCL prima dell'API, output C in nuovo record O_EXCL, SHA/readback. ERROR, INVALID_OUTPUT, abstain rimangono esiti da conservare; **MAI** ritentare lo stesso stage.
- No K, no OOD, no GT, non modificare D o 39 record V1.
- Questa release non autorizza batch di 5-10: dopo una C conclusa servira' protocollo distinto di discovery e rilascio K.

**Live C ancora non eseguita al momento di questo report.**
