# RQ2 V2 — Sonnet K source-bound read-only Colab preflight OK

Data: 2026-11-13. Report separato; non tocca risultati congelati.

## Output utente
```text
STATUS: SONNET_V2_K_SOURCEBOUND_PREFLIGHT_OK
API_CALLS: 0
CODE_COMMIT: 55d146e7bc859ec3f332f97e65471b8dd41805f3
DRIVE_WRITES: 0
K_BINDING_SHA256: 236700ed2ae85fc2fa9d8094215d3a624869d0c374ad1392b29d3cbb85cfaca0
K_CLAIM_EXISTS: False
K_PACKAGE_SHA256: d8a2c7193a60f7e577fb3243ff27276428e164ea0a42eb124443396e6c8d875a
K_RELEASE_EXISTS: False
K_SYSTEM_PROMPT_SHA256: 0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71
OOD_TEST_LOCKED: True
PARENT_C_RECORD_SHA256: 8e853074e69f1718ae1a8ebda3f67954bc495fa0d14651e0dfa8a3f03744a49b
PARENT_D_RECORD_SHA256: 521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009
PHASE: discovery
PROMPT_CHARS: 19971
STAGE_ID: rq2_v2_sonnet_q050_k_contentblocks_v2_v1:cloudbed-1_q050:sonnet:A1:K
```

- Mirati K offline 18/18 PASS; suite precedente 904/904 PASS, regressione 922 non eseguita per accelerare su richiesta utente.
- K preview 19971 caratteri, source-bound da D q050 e C ContentBlocks V2, già con validazione parent; valid K C status `RECORDED_COMPLETE/diagnosis` confidenza low, E001/E008, 3 alternative, 6 limitazioni. Il fault type `Node CPU spike (high user-space CPU load)` e componente `node-6` sono solo ipotesi LLM non GT.
- L'HEAD del futuro esecutore K **differirà** dalla HEAD della preview, dunque avrà binding K SHA differente pur mantenendo identici package K e system prompt. NON riusare `236700...` se cambia HEAD; rifare read-only preflight prima di release, mai modificare log frozen.
- Vecchia C invalida e V1 immutabili; 11 casi OOD locked; nessun K claim, K reale o K rule.
- Passo successivo: codice live K su nuovo branch, test mirati, Colab read-only new HEAD, release K create-only, singola API solo dopo nuovo freeze. `candidate` o `insufficient_evidence` sono validi. No pseudocode execution, no GT, no scorer.
