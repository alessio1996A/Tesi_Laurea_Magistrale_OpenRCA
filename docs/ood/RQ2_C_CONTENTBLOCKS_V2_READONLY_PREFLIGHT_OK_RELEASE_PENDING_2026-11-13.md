# RQ2 V2 — C ContentBlocks V2: Colab preflight OK, release ancora da congelare

Data: 2026-11-13; branch documentale (non modificare sorgenti esperimento).

## Risultati osservati dall'utente

- Gate PyCharm mirato: `Ran 21 tests in 0.495s / OK`.
- Regressione completa PyCharm: `Ran 904 tests in 87.479s / OK`.
- Colab sola lettura:
```text
STATUS: SONNET_V2_C_CONTENTBLOCKS_PREFLIGHT_OK
CODE_COMMIT: 73927d747430bf79e36cb65ecdcba632d9561f9d
STAGE_ID: rq2_v2_sonnet_q050_c_contentblocks_v2:cloudbed-1_q050:sonnet:A1:C
C_BINDING_SHA256: 344ce9ba435176e5ab48f1fabe139e470d739933b344ef0bfc35dcc404e2ede8
PARENT_RECORD_SHA256: 521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009
PARENT_BUNDLE_SHA256: f63f1f0fd744497acc92814d8aabf80fb30cb08d8e5244ec62501d29052154d6
C_PACKAGE_SHA256: 49422ee1f91909514acc3cdf5868aa5c4e73990392804fe7b1fa8dec950e333f
CONTENT_EXTRACTION_POLICY: text_blocks_only_v1
PROMPT_CHARS: 18084
OLD_C_STATUS: INVALID_OUTPUT
OLD_C_RECORD_SHA256: 39364800134f3713302a6f314822930b501a4300af6d62a12f7ce376a93f0579
NEW_RELEASE_EXISTS: False
NEW_CLAIM_EXISTS: False
API_CALLS: 0
DRIVE_WRITES: 0
OOD_TEST: LOCKED
```

## Stato metodologico e step seguente

Il test in sola lettura conferma code HEAD, parent D, pacchetto C, vecchia C INVALID_OUTPUT congelata e assenza del nuovo archivio. La V1-C con raw_response vuota resta immutable: non reinterpretare né fare retry. L'origine della raw string vuota nella singola prima C resta incerta (il vecchio driver scartava i blocchi, ma non era conservato il tipo originario).

**Prossimo passo autorizzato dal workflow:** esclusivamente congelare un file `data/rq2_v2_provenance/sonnet_q050_c_contentblocks_v2/release_v1.json` create-only, con SHA ricalcolato e `read_c_release` + `CauseLedger.audit_restart` senza API. HEAD `73927d747430bf79e36cb65ecdcba632d9561f9d`, binding `344ce9ba435176e5ab48f1fabe139e470d739933b344ef0bfc35dcc404e2ede8`, parent D record `521ed...`, package C `49422...`, `content_extraction_policy=text_blocks_only_v1`. Pin modello Sonnet 5.5, 1 request, 0 retry, max_tokens 4096, timeout 300 sec, soglia USD operativa proposta 5.00 (non hard cap). Il protocollo successore è engineering correction, NON una replica indipendente.

Non dare un ulteriore comando API live prima della restituzione della SHA release e controllo. Nessuna nuova C o K, e 11 casi OOD ancora LOCKED. Il codice C ContentBlocks V2 e il branch vanno mantenuti immutabili durante release/run.
