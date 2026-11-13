# RQ2 V2 — Sonnet q050/A1/C ContentBlocks V2, primo output reale RECORDED_COMPLETE

**Data:** 13 novembre 2026. **Fonte:** output del run Colab fornito dall'utente. Report nel branch documentale indipendente; NON modificare il commit sorgente, i record su Drive o la C precedente.

## Protocollo tecnico successore e storia

- D originale q050/A1/Sonnet: `RECORDED_COMPLETE`, parent SHA `521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009`.
- C precedente `rq2_v2_sonnet_q050_c_sourcebound_v1`: una richiesta reale, `INVALID_OUTPUT/C_JSON_CONTRACT`, `raw_response=""` (0 chars), record SHA `39364800134f3713302a6f314822930b501a4300af6d62a12f7ce376a93f0579`. Non ritentata, non reinterpretata.
- Bug di estrazione C precedente: il codice impostava raw vuota per ogni `response.content` non stringa. I 1019 output token del precedente run non determinano se ci fosse testo; la forma non era preservata.
- Branch tecnico V2 `feature/rq2-v2-sonnet-c-contentblocks-v2-offline-2026-11-13`, HEAD `73927d747430bf79e36cb65ecdcba632d9561f9d`; 21/21 mirati e 904/904 regressione software OK; preflight Colab source bound OK.
- C package invariato SHA256 `49422ee1f91909514acc3cdf5868aa5c4e73990392804fe7b1fa8dec950e333f`, 8 evidenze D (3 troncate per budget visibile), contenuto prompt invariato.
- Binding nuovo SHA256 `344ce9ba435176e5ab48f1fabe139e470d739933b344ef0bfc35dcc404e2ede8`.
- Release successore dedicata, frozen SHA256 `7053f040afa04cdf9e63d91722e1ac7594e2da3965502a83234a9fa21c75e849`.

## Output reale del successore (unica API)

```text
LIVE_STAGE: C_CONTENTBLOCKS_V2_ONLY
MODEL: claude-sonnet-5-5
CASE: cloudbed-1_q050
HARNESS: A1
MAX_MODEL_REQUESTS: 1
AUTOMATIC_RETRY: FALSE
RELEASE_SHA256: 7053f040afa04cdf9e63d91722e1ac7594e2da3965502a83234a9fa21c75e849

STATUS: SONNET_V2_C_CONTENTBLOCKS_REAL_RECORDED
STAGE_STATUS: RECORDED_COMPLETE
DECISION: diagnosis
ISSUE: None
STAGE_ID: rq2_v2_sonnet_q050_c_contentblocks_v2:cloudbed-1_q050:sonnet:A1:C
CLAIM_SHA256: 1c87f64f92ff7487b647cfd7beb430cda26a5e6d34db98caf1021e843d980591
RECORD_SHA256: 8e853074e69f1718ae1a8ebda3f67954bc495fa0d14651e0dfa8a3f03744a49b
PARENT_RECORD_SHA256: 521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009
C_PACKAGE_SHA256: 49422ee1f91909514acc3cdf5868aa5c4e73990392804fe7b1fa8dec950e333f
MODEL_REQUESTS: 1
INPUT_TOKENS: 7702
OUTPUT_TOKENS: 754
USAGE_COMPLETE: True
ESTIMATED_COST_USD: 0.022944
RESPONSE_CONTENT_KIND: list
TEXT_BLOCKS_OBSERVED: 1
NONTEXT_BLOCKS_OBSERVED: 1
CLAIM_EXISTS: True
RECORD_EXISTS: True
AUTOMATIC_RETRY: False
K_EXECUTED: False
OOD_TEST_LOCKED: True
```

## Interpretazione scientifica

- **Evidenza positiva engineering:** in una chiamata reale il provider ha restituito `AIMessage.content` come lista, 1 blocco testuale e 1 blocco non testuale; la nuova estrazione ha conservato il testo, e il contratto C ha validato la risposta `diagnosis`. L'esecutore ha persistito record e claim con SHA. Questa è prova live dell'utilità tecnica dell'estrattore sui blocchi.
- **Non dimostrato:** correttezza della causa rispetto a reference; trasferimento di una regola K; accuratezza su classi/incidenti OOD; motivo esatto del fallimento di prima C (raw non preservato).
- La nuova C è un esperimento tecnico motivato a posteriori dall'errore della vecchia C, **NON un campione indipendente** né una rietichettatura di quella invalida.
- Costi: 7702 input + 754 output token; USD 0.022944 stimati e non fattura. Un solo tentativo e zero retry, soglia release 5 USD non hard cap.

## Prossimo gate (no API)

Audit read-only su Drive:
1. ricalcolare e validare release, claim, record, source binding, parent D, package C;
2. verificare l'immutabilità della C precedente `INVALID_OUTPUT`;
3. richiamare `validate_cause_probe(raw_response,allowed_evidence_ids=E001..E008)` senza cambiare il record; controllare decisione, numero riferimenti E###, confidence, alternative e limitazioni; eventuale fault-type e component rimangono ipotesi non-GT;
4. niente invocazioni API o scritture, niente score/GT/OOD.
Solo dopo valutare protocollo scientifico nuovo per K, con nuovo freeze D+C e namespace, non autorizzato dalla release C. Una K formalmente valida non prova di per sé generalizzazione. Utenza desidera poi refactoring in italiano e pulizia file superflui prima della stesura; scadenza tesi 2026-12-01.
