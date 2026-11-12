# RQ2 — Esito reale preflight finale GT-free dopo approvazione scientifica

**Data:** 12 novembre 2026. **Origine:** output integrale di Google Colab comunicato dall'utente in chat dopo l'esecuzione della cella documentata in `RQ2_COLAB_PREFLIGHT_FINALE_DOPO_APPROVAZIONE_2026-11-12.md`.

**Esito osservato:** `STATUS: OFFLINE_FINAL_PREFLIGHT_OK_RELEASE_NOT_SIGNED`.
**Non** è un release, **non** autorizza richieste Gemini/Claude, **non** sblocca il test OOD.

## Identità del checkout e ambiente di esecuzione

- `RQ2_GIT_HEAD = 792dd97e5beefda8ed1c86aa39410115e419432b`.
- Python Colab `3.13.18`.
- Versioni osservate:
  - `langchain-core=1.7.1`
  - `langgraph=1.2.18`
  - `langchain-anthropic=1.7.7`
  - `langchain-google-genai=4.4.2`
  - `anthropic=2.6.0`
  - `google-genai=2.34.0`
- La cella ha completato senza eccezioni anche il controllo
  `assert_exact_runtime_snapshot()` della factory RQ2-only, con
  verifica delle versioni e dei quattro file sorgente SDK/LangChain
  pre-registrati nel modulo. Non è stata riportata una stampa distinta
  del messaggio del subprocess; questo gate è verificato dal successivo
  completamento della cella con `check=True`.

## Coorte e identità protocollare effettivamente osservate

- `status=REAL_GT_FREE_SOURCE_CHECKED_PREFREEZE_NOT_EXECUTABLE`.
- `rq1_frozen_reference_commit=e4845e7fe9a399e10dd2db6f320dfeaeeddf3379`.
- `rq1_13_blob_match=true`, `rq1_D_output_contract_mode=v2_enforce`,
  `D_variant_scheme=current`, `D_max_tool_rounds=6`,
  `D_recursion_limit=30`.
- 4 discovery: `cloudbed-1_q032`, `cloudbed-1_q050`,
  `cloudbed-2_q026`, `cloudbed-2_q045`.
- 11 test OOD: `cloudbed-1_q014`, `cloudbed-1_q021`,
  `cloudbed-1_q030`, `cloudbed-1_q059`, `cloudbed-2_q014`,
  `cloudbed-2_q021`, `cloudbed-2_q040`, `cloudbed-2_q041`,
  `cloudbed-2_q058`, `cloudbed-2_q076`, `cloudbed-2_q077`.
- 4 gruppi temporali discovery, 10 gruppi test.
- 72 stage discovery, 132 stage test bloccati, 204 stage totali.
- `plan_preview_sha256=ecd6d926933a5ad056ad1a581fa7e490c0a13eee18070c7dac8627c1b19c062e`.
- `preview_sha256=189ff35c0bbd444ca178c2846cd71c283ba60de3ebf783d0d1f356783a49c4d2`
  della CLI di readiness, **diverso** da `plan_preview_sha256`.
- Split originale GT-free:
  `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`.
- Manifest GT-free:
  `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`.
- Sistema C:
  `81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42`.
- Sistema K:
  `0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71`.
- Catalogo KPI source-only (29 nomi):
  `81958222ebe027c6f205e9b6d8fc6c562b386eba20a05436b35522dfd92cf2eb`;
  `kpi_units_semantics_certified=false`.

## Impronte SHA-256 dei sette file RQ2 osservati in Colab

| Percorso relativo a `src/` | SHA-256 |
|---|---|
| `evaluation/rq2_probe_adapter.py` | `42f1d56d2e8bc22ddb245a9aa8028ce5c82219220a3fce4902191ca2c10269db` |
| `evaluation/rq2_output_contracts.py` | `e466a23330fd818c7c7c9093e127411943bcfc8e56b4d5259e8806611a33ced2` |
| `evaluation/rq2_evidence_bundle.py` | `d3bab4d8fdbad9b7f97da7d761963be18f5592a391379a1bc1904f1461c640a6` |
| `evaluation/rq2_stage_binding.py` | `0a2b249ade77752059f7d483e3215f4739094d1f38274a522487ead3cf69c51a` |
| `evaluation/rq2_discovery_stage_recorder.py` | `28c5a3172c4b25257855d05f376fb8d5a6d4d1e8e85f235574fa13dc518ce84b` |
| `evaluation/rq2_discovery_claim_journal.py` | `0c792f02d2afc2b6ea4e63017702f77fe6b4cc0f6fc67710c9d4ca5c5fe6ef0e` |
| `evaluation/rq2_stage_artifact_store.py` | `ab6ac91f7eb98f0b98aec55818b2e7b3fdbe6fb39e582630cedf7263ada276ca` |

**Nota drift storica:** non riutilizzare digest più vecchi, incluso
`rq2_probe_adapter.py` `60de1f73...`. Questo report si riferisce
al checkout Git esatto riportato sopra.

## Gate di sicurezza letti nell'output

- `provider_calls_executed=0`,
  `REAL_GEMINI_CLAUDE_REQUESTS: 0`.
- `read_ground_truth=false`, `read_market_telemetry=false`,
  `read_llm_predictions=false`, `files_written=false` per la CLI.
- `release_sha256_pinned_in_production=false`;
  `scientific_discovery_release_signed=false`.
- `can_execute_D=false`, `can_execute_CK=false`,
  `can_execute_test=false`; `TEST_OOD: LOCKED`.
- I campi legacy `effective_Google_SDK_retry_timeout_verified=false`
  e `effective_Anthropic_SDK_retry_timeout_verified=false`
  nella CLI di readiness **non rappresentano** il risultato
  dell'audit separato HTTP503 mock successivamente completato.
  Il mock prova solo le invocazioni sincrone nel contesto testato,
  non timeout fisico di una connessione bloccata.

## Prossimo gate, non eseguito da questo report

L'approvazione scientifica dell'utente è documentata in
`RQ2_REVIEW_SCIENTIFICO_PRIMA_RELEASE_2026-11-12.md`.
Prima di abilitare API bisogna:

1. Catturare/registrare nel release gli hash finali anche di factory,
   scorer, trasporti e policy non elencati nei sette SHA della CLI
   GT-free, insieme all'HEAD sperimentale esatto (distinguendo il
   commit documentale successivo dal checkout sorgente già validato).
2. Preparare un release scientifico **create-only**
   `RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json` con
   `test_unlocked=false`; rispettare il contratto effettivo
   di `rq2_ck_provider_transport._read_release`.
3. Eseguire readback e verifica hash SHA-256 indipendente,
   poi un pin coerente con l'esatto file di release, mantenendo
   immutati i 13 sorgenti RQ1.
4. Solo dopo i gate, richiedere consenso specifico per la
   prima D discovery Gemini, proposta `cloudbed-1_q032 / A1 /
   gemini-3.5-flash-lite`. Nessun tentativo già autorizzato.

Nessun nuovo unit test e nessuna API reale sono richiesti per la
registrazione del presente report.
