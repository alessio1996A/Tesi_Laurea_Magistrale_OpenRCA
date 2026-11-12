# RQ2 — Evidenza del preflight GT-free reale Colab (12 novembre 2026)

**Fonte:** JSON riportato integralmente dall'utente nella conversazione dopo l'esecuzione della CLI `evaluation.rq2_discovery_prereg_readiness` su Google Colab, seguito da `PREFLIGHT RQ2: CONTROLLI SUPERATI`.

**Stato:** `REAL_GT_FREE_SOURCE_CHECKED_PREFREEZE_NOT_EXECUTABLE`. **Questo è un controllo di provenienza superato, NON una preregistrazione scientifica frozen, NON un release firmato e NON un'autorizzazione API.**

## Esito osservato

- `version = rq2_discovery_prereg_readiness_v0`
- `data_source_checks = ORIGINAL_GT_FREE_HASH_AND_PHASE_AUDIT`
- RQ1 frozen reference: `e4845e7fe9a399e10dd2db6f320dfeaeeddf3379`; `rq1_13_blob_match = true`.
- `rq1_D_output_contract_mode = v2_enforce`; `D_variant_scheme = current`; `D_max_tool_rounds = 6`; `D_recursion_limit = 30`.
- `plan_preview_sha256 = ecd6d926933a5ad056ad1a581fa7e490c0a13eee18070c7dac8627c1b19c062e`.
- `preview_sha256 = 189ff35c0bbd444ca178c2846cd71c283ba60de3ebf783d0d1f356783a49c4d2` (digest *riportato dalla CLI*, non firmato indipendentemente da questo file).
- Split GT-free originale SHA-256: `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`.
- Manifest GT-free originale SHA-256: `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`.
- `discovery_window_groups = 4`; `test_window_groups = 10`.
- `discovery_stages = 72`; `test_stages_locked = 132`; `total_stages = 204`.
- `C_system_prompt_sha256 = 81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42`.
- `K_system_prompt_sha256 = 0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71`.
- `kpi_source_catalog_sha256 = 81958222ebe027c6f205e9b6d8fc6c562b386eba20a05436b35522dfd92cf2eb`; 29 nomi KPI noti nel sorgente, **unità e semantica fisica non certificate**.
- Python `3.13.18`; `langchain-core 1.7.1`, `langgraph 1.2.18`, `langchain-anthropic 1.7.7`, `langchain-google-genai 4.4.2`, `anthropic 2.6.0`, `google-genai 2.34.0`.
- Modelli candidati (non disponibilità remota verificata): `gemini-3.5-flash-lite`, `claude-sonnet-5-5`, `claude-haiku-5-5`; harness `A1`, `A1_8R`.

### Partizione identificata senza rilascio di etichette

Discovery: `cloudbed-1_q032`, `cloudbed-1_q050`, `cloudbed-2_q026`, `cloudbed-2_q045`.

Test chiuso: `cloudbed-1_q014`, `cloudbed-1_q021`, `cloudbed-1_q030`, `cloudbed-1_q059`, `cloudbed-2_q014`, `cloudbed-2_q021`, `cloudbed-2_q040`, `cloudbed-2_q041`, `cloudbed-2_q058`, `cloudbed-2_q076`, `cloudbed-2_q077`.

La precedente verifica GT **isolata e aggregata**, distinta da questo preflight GT-free, è descritta in `REPORT_ANTEPRIMA_PARTIZIONE_RQ2_V1_2026-11-11.md` e attesta una discovery per classe senza esporre `case_id → fault_type` al runtime. Non importare il mapping GT nei messaggi C/K né nella discovery.

## Gate e confini confermati dal JSON

- `provider_calls_executed = 0`; `read_ground_truth = false`; `read_market_telemetry = false`; `read_llm_predictions = false`; `files_written = false` (riferito al modulo CLI).
- `scientific_discovery_release_signed = false`.
- `release_sha256_pinned_in_production = false`.
- `can_execute_D = false`, `can_execute_CK = false`, `can_execute_test = false`.
- `effective_Google_SDK_retry_timeout_verified = false`; `effective_Anthropic_SDK_retry_timeout_verified = false`.
- `no_cost_ceiling_required = true`, ma il primo stage API richiede **separata autorizzazione esplicita** dopo tutti i gate scientifici e tecnici.

## Impronte dei sette file RQ2 riportate dall'utente

| File relativo a `src/` | SHA-256 osservato |
|---|---|
| `evaluation/rq2_probe_adapter.py` | `42f1d56d2e8bc22ddb245a9aa8028ce5c82219220a3fce4902191ca2c10269db` |
| `evaluation/rq2_output_contracts.py` | `e466a23330fd818c7c7c9093e127411943bcfc8e56b4d5259e8806611a33ced2` |
| `evaluation/rq2_evidence_bundle.py` | `d3bab4d8fdbad9b7f97da7d761963be18f5592a391379a1bc1904f1461c640a6` |
| `evaluation/rq2_stage_binding.py` | `0a2b249ade77752059f7d483e3215f4739094d1f38274a522487ead3cf69c51a` |
| `evaluation/rq2_discovery_stage_recorder.py` | `28c5a3172c4b25257855d05f376fb8d5a6d4d1e8e85f235574fa13dc518ce84b` |
| `evaluation/rq2_discovery_claim_journal.py` | `0c792f02d2afc2b6ea4e63017702f77fe6b4cc0f6fc67710c9d4ca5c5fe6ef0e` |
| `evaluation/rq2_stage_artifact_store.py` | `ab6ac91f7eb98f0b98aec55818b2e7b3fdbe6fb39e582630cedf7263ada276ca` |

**Avvertenza di deriva:** nella precedente bozza il digest di `rq2_probe_adapter.py` era `60de1f73...`, mentre il preflight reale ora riporta `42f1d56d...`. Verificare e documentare le modifiche intermedie prima di pin definitivo: il confronto non costituisce da solo prova di problema, ma vieta di riciclare il vecchio digest come corrente.

## Gate successivi (NON attestati da questa evidenza)

1. Registrare il commit Git esatto del sorgente eseguito e verificare che le impronte corrispondano al checkout finalizzato (la CLI non stampa l'HEAD Git).
2. Congelare ID, versioni e policy effettiva di retry/timeout dei trasporti Google e Anthropic, compresi i retry impliciti; mantenere intatta RQ1.
3. Definire prima delle predizioni la policy di alias della classe nello scorer **offline**, i denominatori di errori/astensioni e il criterio statico di formalizzabilità delle K (incluso arm illustrativo).
4. Verificare i documenti di approvazione GT isolata per una discovery per classe, senza incorporare mappe per-caso nella release pubblica.
5. Firmare/create-only `RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json`, registrare SHA-256 e pin nel codice **solo dopo** gli audit, verificare con readback e mantenere `test_unlocked=false`.
6. Autorizzare separatamente un singolo stage D reale discovery. Gli 11 test OOD restano chiusi fino al freeze successivo delle K.

**Non** alterare RQ1, non avviare provider, non trasformare `REAL_GT_FREE_SOURCE_CHECKED_PREFREEZE_NOT_EXECUTABLE` in `SCIENTIFIC_DISCOVERY_RELEASE` per il solo codice di uscita zero.
