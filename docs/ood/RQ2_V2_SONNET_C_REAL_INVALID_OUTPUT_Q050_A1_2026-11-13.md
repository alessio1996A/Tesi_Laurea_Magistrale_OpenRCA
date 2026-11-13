# RQ2 V2 — Sonnet q050/A1/C reale: INVALID_OUTPUT, record congelato

Data: 13 novembre 2026. Fonte: output della cella Colab live fornito dall'utente.
**Documento nel branch documentale separato. Non modifica codice e risultati congelati.**

## Contesto, gate scientifici precedenti

- Suite PyCharm: 16/16 mirati e 883/883 regressione OK.
- C source preflight Colab: `SONNET_V2_C_SOURCEBOUND_PREFLIGHT_OK`, nessuna API.
- Commit codice C: `d1d1d2eb20d030a2bb0da76ebc3c1d9f82e469ce`.
- Binding C SHA256: `08bc3e1d7e8e4b793cf559e7a5fdc9f5d91d4e0bf50fb2af2dd12b7ee89f231c`.
- Release create-only C SHA256: `a98dd76b962cf6ae37978c9fc362fa354ec375fd1f69f5d6ab605963c7f7853c`.
- Parent D record SHA256: `521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009`.
- C prompt package SHA256: `49422ee1f91909514acc3cdf5868aa5c4e73990392804fe7b1fa8dec950e333f`.
- D aveva 8 tool evidences, di cui 3 troncate intenzionalmente. Le 11 OOD test sono LOCKED.

## Esito della prima e sola C reale

```text
LIVE_STAGE: C_ONLY
MODEL: claude-sonnet-5-5
CASE: cloudbed-1_q050
HARNESS: A1
MAX_MODEL_REQUESTS: 1
AUTOMATIC_RETRY: FALSE
RELEASE_SHA256: a98dd76b962cf6ae37978c9fc362fa354ec375fd1f69f5d6ab605963c7f7853c

STATUS: SONNET_V2_C_REAL_RECORDED
STAGE_STATUS: INVALID_OUTPUT
DECISION: None
ISSUE: C_JSON_CONTRACT
STAGE_ID: rq2_v2_sonnet_q050_c_sourcebound_v1:cloudbed-1_q050:sonnet:A1:C
CLAIM_SHA256: 071ab6c3b860b875bcf9fd2b2ac21a0e10c3cc80a7a6f79aaf64e33c78aac3a5
RECORD_SHA256: 39364800134f3713302a6f314822930b501a4300af6d62a12f7ce376a93f0579
PARENT_RECORD_SHA256: 521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009
C_PACKAGE_SHA256: 49422ee1f91909514acc3cdf5868aa5c4e73990392804fe7b1fa8dec950e333f
MODEL_REQUESTS: 1
INPUT_TOKENS: 7702
OUTPUT_TOKENS: 1019
USAGE_COMPLETE: True
ESTIMATED_COST_USD: 0.025594
CLAIM_EXISTS: True
RECORD_EXISTS: True
AUTOMATIC_RETRY: False
OOD_TEST_LOCKED: True
K_EXECUTED: False
```

Token totali della C: 8721; costo stimato USD 0.025594 (non fattura).

## Interpretazione corretta

- `SONNET_V2_C_REAL_RECORDED` significa che l'artefatto e' stato persistito e riletto.
- `INVALID_OUTPUT/C_JSON_CONTRACT` significa mancata conformità al contratto C; **non** dimostra, da solo, causa diagnostica erronea. Il sottotipo dell'errore JSON non e' ancora stato stabilito.
- `decision=None` non e' un'astensione del modello. Un'astensione valida avrebbe `RECORDED_COMPLETE` e `c_decision=abstain`.
- La K di questo ramo D→C→K e' **blocked_dependency**, senza alcun claim e senza provider.
- Claim/record C originali vanno mantenuti come INVALID_OUTPUT, senza retry e senza 'repair' retroattivo. Non sbloccare OOD.
- Il budget API ampio comunicato dall'utente non autorizza retry di questo stage ne' nuovi stage di batch senza preregistrazione.

## Gate successivo — audit locale read-only

Riaprire soltanto il record C congelato, verificare digest `39364800...` e il source-bound parent, chiamare il parser esistente `validate_cause_probe(raw_response, allowed_evidence_ids={E001..E008})` e riportare **soltanto classe/categoria tecnica dell'errore** (non testo raw, prompt, ipotesi di diagnosi, dati o GT). Verificare claim readback e contabilità. La distinzione e' fra JSON non parsabile, schema/chiavi, riferimenti a evidenze fuori allowlist, mancata astensione valida o altro vincolo.

Se il problema e' soltanto di formato, valutarne le implicazioni nel protocollo **futuro**; non dichiarare la C valida né ripeterla. Eventuali nuovi C richiedono nuovo protocollo/identità/namespace e gate, conservando il fallimento originale nel denominatore.
