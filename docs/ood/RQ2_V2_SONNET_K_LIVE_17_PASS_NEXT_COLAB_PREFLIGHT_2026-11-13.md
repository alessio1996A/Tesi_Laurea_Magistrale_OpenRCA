# RQ2 V2 — K one-call runner: targeted 17/17 PASS, Colab gate pending

Data 2026-11-13. User confirmed `Ran 17 tests in 0.359s / OK` on the feature branch.
Confirmed GitHub HEAD `e3b4ce869e2e005ea3b2c0f7b1b287e819e96a6f` for `feature/rq2-v2-sonnet-k-single-live-2026-11-13`.

## State
- 17/17 targeted K runner tests PASS, 18/18 K preview targeted PASS, and earlier regression 904/904 PASS. Full regression including new tests **not executed**; deferred until final freeze by user request. Do not claim 939/939 PASS.
- K preview Colab `SONNET_V2_K_SOURCEBOUND_PREFLIGHT_OK`, code HEAD `55d146e7bc859ec3f332f97e65471b8dd41805f3`, binding `236700ed2ae85fc2fa9d8094215d3a624869d0c374ad1392b29d3cbb85cfaca0`, package `d8a2c7193a60f7e577fb3243ff27276428e164ea0a42eb124443396e6c8d875a`, system prompt `0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71`, prompt 19,971 chars.
- K single-live driver added in new commit, requires NEW code HEAD binding. Its release does NOT exist. No K claim or record, no K API.
- Frozen parent D: `521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009`.
- Frozen valid parent C: `8e853074e69f1718ae1a8ebda3f67954bc495fa0d14651e0dfa8a3f03744a49b`, decision diagnosis with confidence low, E001,E008, type Node CPU spike, component node-6: not GT verified.
- Old invalid C: `39364800134f3713302a6f314822930b501a4300af6d62a12f7ce376a93f0579`, unchanged and invalid.
- 11 OOD test remain LOCKED; K can be `candidate` or `insufficient_evidence`, with no pseudocode execution.

## Next gate
Colab read-only preflight on NEW HEAD `e3b4ce869e2e005ea3b2c0f7b1b287e819e96a6f` with separate checkout and pinned deps, no secrets, no API. Validate `preview_k`, `require_fresh_k_namespace`, original SHA parent D/C, K package and system prompt unchanged from the previous source-bound preview, 19,971 prompt chars, binding derived from NEW head and not the previous binding. Print new `K_BINDING_SHA256` only if all gates pass; no release or Drive write. Then separately create-only K release and 1 paid call only after verified frozen release.
