# RQ2 V2 — C ContentBlocks V2, 904/904 PyCharm PASS, next Colab GT-free preflight

Data 2026-11-13; branch di documentazione separato, nessuna modifica alla HEAD sperimentale.

## Evidenza osservata
- Mirati V2: `Ran 21 tests in 0.495s / OK`
- Suite completa: `Ran 904 tests in 87.479s / OK`
- Branch codice V2: `feature/rq2-v2-sonnet-c-contentblocks-v2-offline-2026-11-13`
- HEAD GitHub (verificata dopo output): `73927d747430bf79e36cb65ecdcba632d9561f9d`
- 21 test software (non diagnosi) per contenuti Anthropic text + thinking e nuovi record, nessuna API.

## Vincoli scientifici congelati
- D origin `cloudbed-1_q050/sonnet/A1/D` sul commit `bf2b0a0a67977a65c79d47ada4b07e825eaf8dff`, `RECORDED_COMPLETE`, record SHA `521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009`, bundle SHA `f63f1f0fd744497acc92814d8aabf80fb30cb08d8e5244ec62501d29052154d6`.
- Prima C su codice commit `d1d1d2eb20d030a2bb0da76ebc3c1d9f82e469ce`, release `a98dd76b962cf6ae37978c9fc362fa354ec375fd1f69f5d6ab605963c7f7853c`; claim `071ab6c3b860b875bcf9fd2b2ac21a0e10c3cc80a7a6f79aaf64e33c78aac3a5`, record `39364800134f3713302a6f314822930b501a4300af6d62a12f7ce376a93f0579`, `INVALID_OUTPUT/C_JSON_CONTRACT`, raw_response 0 chars, 7702 input / 1019 output, USD 0.025594 stimati. Questa C e la sua dipendenza K restano congelate e non vanno ritentate.
- La causa tecnica **dimostrata nel codice** C V1 era l'estrazione `raw=""` per qualsiasi `response.content` non string; la natura esatta della risposta Anthropic della run passata NON e' nota, quindi l'attribuzione causale del fallimento rimane ipotesi.
- C ContentBlocks V2 e' un **nuovo protocollo tecnico**, non una replica indipendente, non ha ancora release o claim, non autorizza chiamate API.
- C package SHA conservato `49422ee1f91909514acc3cdf5868aa5c4e73990392804fe7b1fa8dec950e333f`; system prompt SHA `81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42`, 18084 caratteri, otto tool evidence di cui tre troncate.
- OOD 11 query restano LOCKED, niente scorer, GT, human in loop, K.

## Prossimo gate, non ancora realizzato
Preflight sola lettura su checkout temporaneo nuovo `/content/Tesi_OpenRCA_Sonnet_C_ContentBlocks_V2_Preflight`, runtime pins gia' disponibili. Nessuna API o chiave. Riconvalidare HEAD pulito, la source V2 con parent D e package C; hash della release/claim/record della C V1 `INVALID_OUTPUT`, `raw_response=""`, status e contatori immutati; la nuova directory V2 deve ancora essere assente. Stampare solo SHA nuovi e contatori, non dati grezzi. Se passa, progettare release create-only su altro namespace, autorizzazione separata a una eventuale nuova C engineering. Non usare release C V1.
