# RQ2 V2 — Sonnet q050/A1/C, preflight Colab reale superato (senza API)

Data: 13 novembre 2026. **Report in branch documentale separato**, non alterare commit C congelato.

## Evidenza utente
- `Ran 16 tests in 0.601s / OK`
- `Ran 883 tests in 87.286s / OK`
- `STATUS: SONNET_V2_C_SOURCEBOUND_PREFLIGHT_OK`
- Commit C: `d1d1d2eb20d030a2bb0da76ebc3c1d9f82e469ce`
- Stage: `rq2_v2_sonnet_q050_c_sourcebound_v1:cloudbed-1_q050:sonnet:A1:C`
- C binding SHA256: `08bc3e1d7e8e4b793cf559e7a5fdc9f5d91d4e0bf50fb2af2dd12b7ee89f231c`
- Parent D record SHA256: `521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009`
- Parent D bundle SHA256: `f63f1f0fd744497acc92814d8aabf80fb30cb08d8e5244ec62501d29052154d6`
- C package SHA256: `49422ee1f91909514acc3cdf5868aa5c4e73990392804fe7b1fa8dec950e333f`
- C system prompt SHA256: `81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42`
- C prompt characters: `18084`
- Zero API, zero Drive writes, no C claim, OOD test locked.

## Prossimo passo: release C write-once (NON una nuova API)

Creare **soltanto** `data/rq2_v2_provenance/sonnet_q050_c_v1/release_v1.json` sul Drive in JSON canonico, con esatto codice/binding C e parent D, modello `claude-sonnet-5-5`, stage C, 1 richiesta, `max_retries=0`, `max_tokens=4096`, timeout HTTP 300 sec, soglia operativa USD 5.0 (non hard cap) e token usage persistente. Verificare SHA256 con `read_c_release` e assenza di claim/record C. Non riutilizzare release D per C, non modificare D, V1, RQ1, test OOD.

L'effettiva API C deve essere un passo **successivo e separato** con consenso e gate ripetuti. Nessuna diagnosi C o regola K è ancora stata ottenuta con questa run.
