# RQ2-V2 Opzione A — dossier prerelease Colab GT-free PASS (no API, no release)

**Data:** 15 novembre 2026. **Evidenza:** output Google Colab riportato integralmente dall'utente nella conversazione; verificato rispetto al contratto del dossier e ai digest attesi. Non equivale a una release, a una firma/autorizzazione di spesa o a un run LLM.

## Identita' della verifica reale

- Repository: `alessio1996A/Tesi_Laurea_Magistrale_OpenRCA`
- Branch: `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`
- Checkout temporaneo Git **clean** al commit `4733eb90a67a784410d911ec227061b0a68a48e9`.
- Preflight sorgenti e dossier in-memory con due CSV GT-free di `/content/drive/MyDrive/Tesi_OpenRCA`; checkout temporaneo rimosso.
- SDK isolati `/content/rq2_v2_pinned_sdk_py313`, controllo runtime pinned PASS.
- Esito: `RQ2_V2_REAL_GT_FREE_PRERELEASE_DOSSIER_PASS_NO_API` e riga `DOSSIER PRERELEASE: PASS — 0 API LLM`.
- Stato del dossier: `PRERELEASE_DOSSIER_REVIEW_ONLY_NO_AUTHORITY`.
- Le 14 verifiche offline del modulo dossier erano gia' PASS su PyCharm (`Ran 14 tests in 0.841s — OK`), insieme a 18 K-rubric e 55 suite dipendenti (totale nuovi test mirati 87/87 PASS). Non ripeterli senza motivo tecnico.

## Digest dell'output Colab (valori esatti)

| Campo | SHA-256 |
| --- | --- |
| source_inventory_sha256 | `8c2d022efed45214fec27b31ab4d7215f2912cd494aa6e16d3afaa55d8e891a1` |
| k_rubric_sha256 | `d8b969d33e2e042ab44121a9b6e089fa96a4aa2b8be03cb31b3edeede6f83f52` |
| source_plan_sha256 | `e6f797c4ca01ed422b80e928854469b9f8c7f7cc4215835bf91f9f7305425a00` |
| blueprint_sha256 | `22005361b35c9873822fec37163cd55f00d4a2a1c697a5939ac0a5a4ec3b9270` |
| split_sha256 | `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724` |
| manifest_sha256 | `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13` |
| C_system_prompt_sha256 | `81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42` |
| K_system_prompt_sha256 | `0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71` |

Versioni runtime confermate: `anthropic=2.6.0`, `google-genai=2.34.0`, `langchain-anthropic=1.7.7`, `langchain-core=1.7.1`, `langchain-google-genai=4.4.2`, `langgraph=1.2.18`.

## Invarianti scientifiche e di sicurezza

- 30 sorgenti source-bound; `source_file_count=30`.
- 4 discovery, 5 harness, 3 modelli; per modello `D=20, C=20, K=20`. Totale **180 stage logici** (60 D, 60 C, 60 K). Nessuno ancora lanciato su provider reale.
- Primo stage pianificato, **NON autorizzato**: `rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:D`.
- `ood_test_cases_locked=11`, `can_run_ood_test=false`, `ground_truth_read=false`.
- `ledger_namespace_absent=true`, `scientific_release_frozen=false`, `release_sha256=null`.
- `provider_requests_sent=0`, `scientific_claims_written=0`, `can_execute_api=false`.
- Le versioni SDK sono provate come snapshot pinned, non come garanzie di costo, request count o timeout globale D.
- Confronto GitHub del commit sorgente precedente `feb7b7c9684138f348d8a6e3e6e9d4eb61798ae7` con `4733eb90a67a784410d911ec227061b0a68a48e9`: 8 commit intermedi e nessun file di `src/evaluation/` o `src/agent/` modificato, solo `docs/` e due moduli sotto `src/tests/`. Gli hash sorgenti condivisi sono coerenti; la verifica Colab e' riferita **esattamente** a `4733eb90...`.

## Gate ancora aperti, nell'ordine corretto

1. **Preparazione non autorizzativa del freeze**: verifica e review del dispatcher G4K, contratto G4E e release create-only G4F; evitare cambiamenti inutili a RQ1, RQ2 V1, rubric K o OOD. `LIVE_API_ENABLED=False` resta immutato. Non scrivere `release_v1.json` prima dei consensi.
2. **Futuro sorgente live-capable e commit clean definitivo**: solo dopo scelta esplicita dell'utente, apportare una modifica circoscritta e revisionata al gate live. Poiche' il dispatcher e' incluso tra i 30 sorgenti, una sua modifica **invalida il vecchio inventory SHA** e rende necessario un nuovo preflight source/runtime/CSV GT-free sul commit finale (non ripetere suite storiche prive di dipendenze mutate).
3. **Budget e release**: fissare un importo positivo USD reale e un riferimento esterno di approvazione; stabilire policy di stop manuale. Il budget NON e' un hard cap del provider. Validare G4E a schema esatto, costruire il digest SHA canonico e ottenere approvazione esterna del digest distinto dal commit. Solo allora un processo autorizzato potra' creare create-only `data/rq2_v2_unified_scientific_v1/release_v1.json`, con single-writer, fsync e readback.
4. **Consenso separato per 1 stage**: richiedere autorizzazione esplicita per `cloudbed-1_q032:gemini:A0:D`, non per C/K o il resto della campagna. Solo 1 writer, claim pre-request, no auto retry, audit post-run. Se claim orfano/crash/provider error, stop manuale.
5. **Opzione B**: 11 OOD intatti e locked fino a protocollo indipendente post-valutazione K. RQ1 frozen, refactoring solo dopo campagne/audit su branch separato.

**Questo documento non abilita API, non congela scientificamente una release e non crea claim.** Il prossimo passo concreto e' prendere una decisione esplicita sul perimetro del freeze/live e sul budget operativo, NON lanciare uno stage.
