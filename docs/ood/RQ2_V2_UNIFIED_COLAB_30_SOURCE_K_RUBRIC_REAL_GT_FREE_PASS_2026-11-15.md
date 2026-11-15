# RQ2-V2 — Colab preflight reale GT-free: 30/30 sorgenti PASS, 0 API

Data prova: **15 novembre 2026**. Evidenza: report integrale fornito dall'utente dopo il nuovo preflight Colab, su checkout Git worktree isolato dal branch di sviluppo.

**Commit esatto sottoposto a verifica:** `feb7b7c9684138f348d8a6e3e6e9d4eb61798ae7`.  
**Stato:** `RQ2_V2_30_SOURCE_REAL_GT_FREE_PASS_NO_API`.  
**Provenienza:** audit reale sui due CSV GT-free sotto `/content/drive/MyDrive/Tesi_OpenRCA`, SDK isolati sotto `/content/rq2_v2_pinned_sdk_py313`; nessuna lettura di ground truth, scorer o Market.zip. Il checkout temporaneo di sola lettura e' stato rimosso.

## Output attestato

```json
{
  "C_system_prompt_sha256": "81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42",
  "K_system_prompt_sha256": "0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71",
  "blueprint_sha256": "22005361b35c9873822fec37163cd55f00d4a2a1c697a5939ac0a5a4ec3b9270",
  "can_execute_api": false,
  "ground_truth_read": false,
  "k_rubric_sha256": "d8b969d33e2e042ab44121a9b6e089fa96a4aa2b8be03cb31b3edeede6f83f52",
  "ledger_namespace_absent": true,
  "logical_stages": 180,
  "manifest_sha256": "5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13",
  "model_requests_sent": 0,
  "ood_locked": 11,
  "per_model_stage_counts": {
    "gemini": {"C": 20, "D": 20, "K": 20},
    "haiku": {"C": 20, "D": 20, "K": 20},
    "sonnet": {"C": 20, "D": 20, "K": 20}
  },
  "runtime_snapshot_verified": true,
  "scientific_release_frozen": false,
  "source_commit": "feb7b7c9684138f348d8a6e3e6e9d4eb61798ae7",
  "source_file_count": 30,
  "source_inventory_sha256": "8c2d022efed45214fec27b31ab4d7215f2912cd494aa6e16d3afaa55d8e891a1",
  "source_plan_sha256": "e6f797c4ca01ed422b80e928854469b9f8c7f7cc4215835bf91f9f7305425a00",
  "split_sha256": "c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724",
  "status": "RQ2_V2_30_SOURCE_REAL_GT_FREE_PASS_NO_API"
}
```

Estratto terminale: `GIT PIN: OK`, `INPUT GT-FREE: PRESENTI`, `SDK ISOLATI: PRESENTI`, `RQ2-V2 30 SOURCE: PASS — 0 API REALI`, `CHECKOUT TEMPORANEO RIMOSSO`, `RELEASE SCIENTIFICA: ANCORA BLOCCATA`.

## Cosa dimostra

- I 30 sorgenti `SOURCE_PATHS` sono stati realmente letti e hashati nel checkout pulito al commit fissato. Il nuovo modulo preregistrato `evaluation/rq2_v2_k_quality_rubric.py` e' incluso; il suo digest esatto e' sopra.
- `preview_unified_source_bound`, `build_unified_release_blueprint` e `preview_scientific_ledger_gate` hanno superato i controlli effettivi con gli SDK source-pinned e i CSV split/manifest originali.
- Il piano resta composto da 5 harness × 3 LLM × 4 discovery × D/C/K = 180 stage, 20 D+20 C+20 K per modello; 11 casi test OOD sono LOCKED.
- Il source plan SHA rimane `e6f797...` e split/manifest/prompt SHA non variano rispetto alla precedente verifica a 29 sorgenti; source inventory e blueprint SHA cambiano come previsto per l'introduzione della rubrica K.
- Non e' stato creato il namespace della release: `ledger_namespace_absent=true`.

## Test PyCharm gia' superati, non da rifare

- Rubrica K: 18/18 PASS.
- Suite dipendenti da `SOURCE_PATHS` (source preflight, blueprint e G4E): 19/19 + 18/18 + 18/18 = **55/55 PASS**, riportati dall'utente su output completo.
- Test G4 precedenti, mock SDK/503/429/stallo, single-writer scratch e 29-source audit restano prove storiche relative ai rispettivi commit, non vengono sovrascritti o reinterpretati come run live.

## Gate ancora aperti (da NON falsificare)

1. **Release scientifica reale non creata:** `scientific_release_frozen=false`, `can_execute_api=false`, `model_requests_sent=0`, `LIVE_API_ENABLED=False`.
2. Le conferme sync fake HTTP 503, HTTP 429 e stall timeout mostrano una sola richiesta in ogni scenario testato, NON hard cap universale HTTP, costo USD o timeout dell'intero stage D.
3. La release richiede commit finale clean pinned, budget operativo positivo e riferimento esplicito di approvazione, review single-writer/ledger e SHA canonico approvato esternamente, più consenso *separato* per il singolo stage D; la scelta del relatore di non ottimizzare per costi non autorizza automaticamente chiamate provider.
4. Primo stage previsto dal piano, **candidato non autorizzato**: `rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:D`. Non creare claim/record finche' non si passa il gate reale.
5. Nessun OOD fino a protocollo Opzione B indipendente e frozen, dopo valutazione di K in Opzione A.
6. Refactoring/commenti in italiano/pulizia file soltanto dopo gli esperimenti con preservazione di Git, output grezzi e manifest.

**Prossimo lavoro consentito:** preparare e revisionare una release candidate **puramente offline e non autorizzativa**, senza scrivere nella root scientifica Drive e senza sbloccare il dispatcher. Non ripetere altre verifiche gia' passate in assenza di cambiamenti scientifici.
