# RQ2 V2 — Sonnet K release frozen, one paid live K still pending

Data: 2026-11-13. Documentazione senza alterare sorgenti frozen.

## Output Colab osservato
```text
API_CALLS: 0
APPROVED_OPERATIONAL_LIMIT_USD: 5.0
AUTOMATIC_RETRY: False
CLAIM_EXISTS: False
CODE_COMMIT: e3b4ce869e2e005ea3b2c0f7b1b287e819e96a6f
K_BINDING_SHA256: 67ab6e43519d6ec8d9ad09d65daa524b295e962e95dd4827828d9d008c2c28c6
K_PACKAGE_SHA256: d8a2c7193a60f7e577fb3243ff27276428e164ea0a42eb124443396e6c8d875a
MAX_MODEL_REQUESTS: 1
OOD_TEST_LOCKED: True
PARENT_C_RECORD_SHA256: 8e853074e69f1718ae1a8ebda3f67954bc495fa0d14651e0dfa8a3f03744a49b
PARENT_D_RECORD_SHA256: 521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009
RECORD_EXISTS: False
RELEASE_SHA256: f5700e63d15dc073f9c6eb930855a9f9f5f027d82baaaee8e171cba12c76492e
STAGE_ID: rq2_v2_sonnet_q050_k_contentblocks_v2_v1:cloudbed-1_q050:sonnet:A1:K
STATUS: SONNET_V2_K_RELEASE_FROZEN_NO_API
```

## Constraints
- Branch source K single-live `feature/rq2-v2-sonnet-k-single-live-2026-11-13`, HEAD verified on GitHub after release: `e3b4ce869e2e005ea3b2c0f7b1b287e819e96a6f`.
- Previous software tests: K runner targeted 17/17 pass; K preview 18/18 pass; older full regression 904/904 pass. New full regression deferred explicitly, not reported as passed.
- K package/system GT-free prompt frozen (19,971 chars), no API yet, one shot only, Sonnet 5.5, max_tokens=4096, 300s per-request timeout, zero retries, estimated USD 5.0 limit is NOT enforceable cost hard-cap.
- Next K call: release SHA `f5700e...` passed explicitly, `run_one_k(confirm_paid_api=True)` invoked just once, create-only claim prior to network and create-only record even for invalid response/provider error. If it stops, do not rerun, inspect claim/record read-only.
- C contentblocks predecessor valid `RECORDED_COMPLETE/diagnosis`, low confidence; hypothesized fault Node CPU spike (high user-space CPU load), node-6, evidence E001/E008; unverified correctness. Old C sourcebound remains `INVALID_OUTPUT`.
- Candidate K is exploratory rule text, not evaluated/executed, `insufficient_evidence` is a legitimate successful structured K response. OOD 11 cases still locked, GT, scorer, human-in-loop disallowed.
