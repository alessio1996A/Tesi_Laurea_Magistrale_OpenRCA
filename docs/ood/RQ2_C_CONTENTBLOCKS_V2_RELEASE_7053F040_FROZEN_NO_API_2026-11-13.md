# RQ2 V2 — C ContentBlocks V2 release frozen, no API yet

**Data:** 2026-11-13. **Branch di documentazione:** docs/rq2-v2-sonnet-final-prefreeze-2026-11-13. Nessuna modifica al codice scientifico o agli esperimenti congelati.

## Output Colab verificato dall'utente

```text
STATUS: SONNET_V2_C_CONTENTBLOCKS_RELEASE_FROZEN_NO_API
RELEASE_SHA256: 7053f040afa04cdf9e63d91722e1ac7594e2da3965502a83234a9fa21c75e849
STAGE_ID: rq2_v2_sonnet_q050_c_contentblocks_v2:cloudbed-1_q050:sonnet:A1:C
CODE_COMMIT: 73927d747430bf79e36cb65ecdcba632d9561f9d
C_BINDING_SHA256: 344ce9ba435176e5ab48f1fabe139e470d739933b344ef0bfc35dcc404e2ede8
PARENT_RECORD_SHA256: 521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009
C_PACKAGE_SHA256: 49422ee1f91909514acc3cdf5868aa5c4e73990392804fe7b1fa8dec950e333f
CONTENT_EXTRACTION_POLICY: text_blocks_only_v1
MAX_LLM_REQUESTS: 1
OPERATIONAL_LIMIT_USD: 5.0
OLD_C_STATUS: INVALID_OUTPUT
API_CALLS: 0
CLAIM_CREATED: FALSE
RECORD_CREATED: FALSE
OOD_TEST: LOCKED
```

Code HEAD confermata sul branch `feature/rq2-v2-sonnet-c-contentblocks-v2-offline-2026-11-13`: `73927d747430bf79e36cb65ecdcba632d9561f9d`.

## Stato e limiti

- Python suite mirata: 21/21 PASS; regressione: 904/904 PASS.
- Nuova release su Drive create-only: `data/rq2_v2_provenance/sonnet_q050_c_contentblocks_v2/release_v1.json`; SHA `7053f...`. Il messaggio dell'utente riporta validazione e readback superati, nessun claim.
- La C precedente conserva `INVALID_OUTPUT`, record SHA `39364800134f3713302a6f314822930b501a4300af6d62a12f7ce376a93f0579`, no retry. Parent D originale `RECORDED_COMPLETE`, record SHA `521ed...`.
- Questa release autorizza secondo il suo file **una sola nuova C tecnica Sonnet 5.5**, sul caso discovery q050 e harness A1, con `max_retries=0`, `max_tokens=4096`, timeout 300 s per richiesta, un tentativo, budget USD 5.0 solo soglia **non un hard cap**. Il valore di $5 non è enforcement economico nella funzione C che stima solo dopo la risposta.
- La nuova C non è una replica scientifica indipendente: protocollo successore creato dopo fallimento V1. Non aggregare score tra C vecchia e nuova senza spiegazione. Il record C precedente non viene rietichettato.
- Per una nuova esecuzione live mantenere HEAD pulito, pin runtime/source, assenza claim/record nuovi, SHA frozen release e parent D+package C, credenziale via Colab Secrets. Scrivere claim prima della richiesta e record anche per risposta vuota/invalid/errore; no retry.
- La risposta nuova avrà `response_content_kind`, `text_blocks_observed`, `nontext_blocks_observed`; non stampare reasoning, raw response, evidenze o GT. Scorer/11 OOD test non vengono letti.
- K resta vietata per la vecchia C invalida. Nessuna regola K ottenuta finora da questo percorso.
