# RQ2-V2 — G4L: REAL GT-FREE prerelease preflight PASS

**Data:** 15 novembre 2026. **Evidenza:** JSON e terminale Google Colab restituiti dall'utente; non un esperimento API, non una release, non uno scoring di correttezza e non un'autorita' di spesa.

## Provenienza e ambiente

- Branch `feature/rq2-v2-scientific-release-writer-prep-2026-11-15`
- Commit clean verificato `5fa6a4af36821e5c038cf9b4f22237cb3326d9cc` (HEAD uguale al branch al momento del run).
- Checkout temporaneo pulito `/content` e rimosso dopo l'audit; input originali GT-free (split + manifest) sotto `/content/drive/MyDrive/Tesi_OpenRCA`; SDK pinned `/content/rq2_v2_pinned_sdk_py313`.
- Source preview G4A, blueprint G4B, ledger preflight G4D, `build_prerelease_dossier` in memoria e assert del runtime; nessuna modifica a Drive o ai risultati sperimentali, nessuna API LLM.
- Status esatto: `RQ2_V2_G4L_REAL_GT_FREE_PREFLIGHT_PASS_NO_API`; console `G4L PREFLIGHT: PASS — 0 API LLM` e `CHECKOUT TEMPORANEO: RIMOSSO`.
- `dossier_status=PRERELEASE_DOSSIER_REVIEW_ONLY_NO_AUTHORITY`.
- Preregressione: 9/9 test G4L `Ran 9 tests in 10.624s — OK` e 22/22 regressione G4F `Ran 22 tests in 15.074s — OK` (31/31 test mirati).

## SHA-256 esatti restituiti dal preflight

| Campo | SHA-256 |
| --- | --- |
| source_inventory_sha256 **NUOVO** | `205f6dd4c6fc89af4ec69bf64f4d4ad85d4416a67d6f28d5899212d1eb457c4d` |
| blueprint_sha256 **NUOVO** | `13cac143d4eea5aad297d0b642e358f55d5f50ae53a8622e44fa488d6de7f3e7` |
| g4l_ledger_source_sha256 **NUOVO** | `91194f1a451180dd828c93a577f4bcd8fe6339adf1277f1089050216d6fa175e` |
| k_rubric_sha256 **INVARIATO** | `d8b969d33e2e042ab44121a9b6e089fa96a4aa2b8be03cb31b3edeede6f83f52` |
| source_plan_sha256 **INVARIATO** | `e6f797c4ca01ed422b80e928854469b9f8c7f7cc4215835bf91f9f7305425a00` |
| split_sha256 **INVARIATO** | `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724` |
| manifest_sha256 **INVARIATO** | `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13` |
| C_system_prompt_sha256 **INVARIATO** | `81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42` |
| K_system_prompt_sha256 **INVARIATO** | `0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71` |

Pinned Python 3.13 e SDK:
`anthropic=2.6.0`, `google-genai=2.34.0`, `langchain-anthropic=1.7.7`, `langchain-core=1.7.1`, `langchain-google-genai=4.4.2`, `langgraph=1.2.18`.
`runtime_snapshot_verified=true`.

## Identita' scientifica e negative controls

- `source_file_count=30`. Matrice Opzione A 4 discovery x 5 harness x 3 provider, `logical_stages=180`, per ciascun provider 20 D + 20 C + 20 K.
- Primo candidato futuro, **non autorizzato**: `rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:D`.
- `ood_locked=11`, `can_run_ood_test=false`, `ground_truth_read=false`.
- `live_api_enabled=false`, `release_writer_enabled=false`, `can_execute_api=false`.
- `ledger_namespace_absent=true`, `release_sha256=null`, `claims_written=0`, `provider_requests_sent=0`.
- Non usare vecchie fingerprint del commit `4733eb90...`: la sola modifica al file ledger G4L ha cambiato l'inventario aggregato e il blueprint. I precedenti hash restano corretti per il rispettivo checkout.

## Prossimi gate (NON ancora compiuti)

1. Review della versione live-capable e decisione esplicita separata sull'eventuale attivazione dei gate. Oggi il dispatcher `LIVE_API_ENABLED=False` e il writer `SCIENTIFIC_RELEASE_WRITE_ENABLED=False` devono restare disabilitati. Qualunque patch di queste source cambia il fingerprint e richiede nuovo clean HEAD + audit G4A/G4B reale GT-free; non riciclare gli hash G4L.
2. Budget operativo positivo USD, policy di stop, verifica listini/quota provider (senza garanzia hard cap USD né timeout stage D). Il costo teorico Gemini D da documento preflight `0.0575 USD` NON costituisce spesa massima osservata né autorizzazione.
3. Dopo consenso economicamente valido, manifesto G4E canonico create-only con SHA approvato esternamente e commit finale pinned; release `release_v1.json` **non** creata.
4. Consenso **ulteriore** per esatto pilot `cloudbed-1_q032:gemini:A0:D`; un solo claim prima dell'SDK invoke, no auto retry, audit usi/errori. Restanti 179 stage, C/K e 11 OOD ancora vietati.

Nessuna modifica a RQ1, RQ2 V1, prompt, rubrica K, 11 OOD o risultati congelati. Per il gate tecnico non servono al momento nuovi paper o trascrizioni del professore. Priorita': arrivare al pilot senza inventare nuove suite o ridurre arbitrariamente la campagna.
