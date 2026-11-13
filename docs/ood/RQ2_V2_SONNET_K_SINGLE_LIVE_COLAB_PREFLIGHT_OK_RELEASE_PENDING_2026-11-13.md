# RQ2 — K Sonnet single-live, Colab read-only source-bound gate OK

**Data:** 2026-11-13. **Fonte:** output Colab fornito dall'utente. **Stato:** RELEASE K NON CREATA, ZERO CHIAMATE API.

```text
API_CALLS: 0
CODE_COMMIT: e3b4ce869e2e005ea3b2c0f7b1b287e819e96a6f
CONTENT_EXTRACTION_POLICY: text_blocks_only_v1
DRIVE_WRITES: 0
K_BINDING_SHA256: 67ab6e43519d6ec8d9ad09d65daa524b295e962e95dd4827828d9d008c2c28c6
K_NAMESPACE_EXISTS: False
K_PACKAGE_SHA256: d8a2c7193a60f7e577fb3243ff27276428e164ea0a42eb124443396e6c8d875a
K_SYSTEM_PROMPT_SHA256: 0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71
OOD_TEST_LOCKED: True
PARENT_C_RECORD_SHA256: 8e853074e69f1718ae1a8ebda3f67954bc495fa0d14651e0dfa8a3f03744a49b
PARENT_D_RECORD_SHA256: 521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009
PROMPT_CHARS: 19971
STAGE_ID: rq2_v2_sonnet_q050_k_contentblocks_v2_v1:cloudbed-1_q050:sonnet:A1:K
STATUS: SONNET_V2_K_SINGLE_LIVE_PREFLIGHT_OK
```

Il commit GitHub del branch `feature/rq2-v2-sonnet-k-single-live-2026-11-13` è stato verificato e coincide con `e3b4ce869e2e005ea3b2c0f7b1b287e819e96a6f`.

## Next
Creazione create-only dell'unico file `data/rq2_v2_provenance/sonnet_q050_k_contentblocks_v2_v1/release_v1.json` con `K_BINDING_SHA256=67ab6e...`, parent C/D congelati e pacchetto K invariato. 1 request, 0 retries, Anthropic Sonnet 5.5, max_tokens 4096, timeout 300 sec, soglia approvata a livello operativo $5 NON hard cap. Release da rileggere mediante `read_k_release` e `KLedger.audit_restart`; no claim, no record, no provider. La release da sola NON costituisce l'esecuzione.

La K candidata non implica correttezza causale; `insufficient_evidence` è valido. La diagnosi C `Node CPU spike (high user-space CPU load)` / `node-6` ha confidenza LOW e non è GT. Vecchia C `INVALID_OUTPUT` è invariata, 11 casi OOD test bloccati.
