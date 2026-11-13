# RQ2 — Sonnet: tre D invalid per ambiguità della provenienza dei tool

**Data:** 13 novembre 2026. Fonte: output di Google Colab
`SONNET_CONT02_READ_ONLY_AUDIT` fornito dall'utente.
GIT_HEAD nell'output:
`c9ef50c2cb85c04bf1838c6dd4cbff169c5a4e18`.

## Stato di integrità confermato

- `claims=32`, `finished_with_matching_result=32`.
- `unresolved_manual_review=0`.
- `result_archive_discovery_count=37`.
- `gemini_records_verified=24`, `sonnet_records_verified=13`.
- Quattro dipendenze C/K q050 per Sonnet, due harness,
  correttamente bloccate offline e prive di claim.
- `sonnet_remaining_unattempted=11`,
  `haiku_remaining_unattempted=24`.
- Test OOD: `test_unlocked=false`.
- Audit read-only: `provider_api_requests=0`,
  `data_files_written=0`.

## Tre D Sonnet invalidate: evidenza comparativa

| Stage | SHA-256 record | JSON D originale | Provider error | Codice causa | Eventi / call / result |
|---|---|---|---|---|---|
| `cloudbed-1_q050 / A1 / D` | `03c51f1260d0981a691bc8af381b1ed736220a54883919033250e14d37f66d10` | `valid_json` | false | `AMBIGUOUS_TOOL_RESULT` | 24 / 12 / 12 |
| `cloudbed-1_q050 / A1_8R / D` | `d6d3c14cc1359b010b9320d17655c0a2b3db893235922cf9c7369bc2fdac6eea` | `valid_json` | false | `AMBIGUOUS_TOOL_RESULT` | 12 / 6 / 6 |
| `cloudbed-2_q026 / A1 / D` | `7882f3db492d3659239349f0459c4b38e75f498fa216885aedda1569d5ee85ec` | `valid_json` | false | `AMBIGUOUS_TOOL_RESULT` | 20 / 10 / 10 |

Per ognuno l'eccezione è `EvidenceBundleError`;
`three_invalid_d_same_reason=true`.
Il log non certifica correttezza della diagnosi,
ma esclude errori di sintassi JSON finale e
errori segnalati dal provider come spiegazioni
di questi specifici tre stati `INVALID_OUTPUT`.

## Meccanismo tecnico nel codice RQ1/RQ2 congelato

- `src/agent/graph_engine.py` costruisce la traiettoria legacy
  dei `tool_call` con `tipo`, `nome`,
  `parametri` e i `tool_result` con
  `tipo`, `nome`, `risposta`, ma non copia
  i rispettivi `tool_call_id` nella traiettoria.
- `src/evaluation/rq2_evidence_bundle.py`, funzione
  `build_evidence_bundle`, associa risultati senza ID
  soltanto quando esiste una singola chiamata pendente
  con lo stesso nome e nessun ID. Se ne trova più di una,
  solleva `EvidenceBundleError` con messaggio
  `Ambiguous/missing legacy tool result association`.
- Il controllo è scientificamente conservativo:
  evita di inventare riferimenti alle evidenze o
  attribuire valori alla chiamata sbagliata.
- L'osservazione di tre casi con lo stesso motivo
  dimostra un problema ricorrente di compatibilità/
  tracciabilità **per questi tentativi**, non
  l'invalidità di tutti i modelli e non la
  correttezza delle loro diagnosi.

## Decisione prudenziale

- NON ripetere, normalizzare, correggere o sovrascrivere
  questi tre claim/result già congelati.
- NON alterare `graph_engine.py`, il bundle RQ2
  o il prompt nel mezzo della stessa coorte.
- C/K `cloudbed-2_q026/sonnet/A1` devono essere
  marcate `BLOCKED_DEPENDENCY` offline, senza
  chiamate Anthropic, dopo audit di integrità.
- Prima di spendere altri token per le 11 fasi Sonnet
  ancora intatte, considerare che il problema
  potrebbe ripetersi: una successiva correzione
  delle tracce richiede versione/campagna
  distinta e confronto separato.
- Tutti i test OOD restano `LOCKED` fino
  alla verifica e al freeze scientifico.

Questo report è solo documentale. Non ha modificato i
risultati scientifici sul Drive e non ha avviato API.
