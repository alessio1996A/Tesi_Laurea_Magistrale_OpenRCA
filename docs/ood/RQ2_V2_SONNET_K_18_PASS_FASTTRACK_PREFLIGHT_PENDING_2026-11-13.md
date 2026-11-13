# RQ2 V2 — K preview 18/18 mirati PASS, regressione completa rinviata

Data 2026-11-13; documento in branch documentale separato.

## Evidenza utente
```text
Ran 18 tests in 0.104s
OK
```
- Nuovo K source-bound preview: branch `feature/rq2-v2-sonnet-k-sourcebound-preview-2026-11-13`, HEAD GitHub verificato `55d146e7bc859ec3f332f97e65471b8dd41805f3`.
- Suite precedente **904/904** superata prima del nuovo modulo K. Suite nuova **18/18** mirata superata.
- Su richiesta esplicita dell'utente per accelerare, non eseguire adesso l'intera regressione (stimati 922 test). **Non rappresentare come 922/922 PASS**. Riprogrammare controllo regressivo completo al gate di freeze finale.
- Preparazione attuale = solo `preview_k` read-only, zero API, zero K claim, zero K release.
- Dopo mirati: unico prossimo passo Colab read-only `preview_k` con D e C attuali; emettere `K_BINDING_SHA256` e `K_PACKAGE_SHA256`, source HEAD e stato OOD locked, no GT.
- Se Colab PASS, progettare nuovo esecutore K su branch successore separato, test mirati prima di una release e singola chiamata. No nuove D o C.
- Parent D valid `521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009`; parent C ContentBlocks V2 valid `8e853074e69f1718ae1a8ebda3f67954bc495fa0d14651e0dfa8a3f03744a49b`, release C `7053f040afa04cdf9e63d91722e1ac7594e2da3965502a83234a9fa21c75e849`. C precedente invalid `39364800134f3713302a6f314822930b501a4300af6d62a12f7ce376a93f0579`. Nessuno modificabile.
- C audit: ipotesi low confidence `Node CPU spike (high user-space CPU load)`, componente `node-6`, evidenze E001/E008, 3 alternative, 6 limitazioni. Non verificata con GT; la K può legittimamente avere `insufficient_evidence`.
- 11 OOD test locked; no new API, no scorer, no GT.
