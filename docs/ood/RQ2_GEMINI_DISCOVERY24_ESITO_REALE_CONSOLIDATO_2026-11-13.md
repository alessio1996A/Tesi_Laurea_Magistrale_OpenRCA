# RQ2 — Discovery Gemini: 24/24 stage registrati, esito reale consolidato

**Data del report:** 13 novembre 2026.
**Fonte:** stdout della cella Google Colab `RQ2_GEMINI_DISCOVERY_BATCH03_3_STAGE_2026-11-12.md`
condiviso dall'utente; conserva gli esiti riportati dai precedenti
Batch 01, continuazione q050 e Batch 02.

## Provenienza Batch 03

- Runtime Colab: `GIT_HEAD=6b717eacf573afcd8f8c1629c16f10842d574b84`.
- `REPO: CLONED`, `DEPS: INSTALLED` dopo ripristino sessione.
- `Q050_A1_8R_C_ABSTENTION_WITH_ZERO_EVIDENCE_CONFIRMED`.
- `BATCH03_PREFLIGHT_OK_3_NEW_STAGES_NO_API`.
- `AUTHORIZED_BATCH03_COUNT=3`.
- `STATUS: BATCH03_3_REAL_DISCOVERY_STAGES_COMPLETED`.
- `BATCH03_COMPLETED=3`, `NO_OTHER_STAGES_AUTORUN=TRUE`.
- `OOD_TEST=LOCKED`; release non modificato.

## Nuove acquisizioni reali

| Stage | Stato | Input token | Output token | Totale | SHA-256 record |
|---|---|---:|---:|---:|---|
| `cloudbed-2_q045 / Gemini / A1_8R / D` | RECORDED_COMPLETE | 23.004 | 99 | 23.103 | `ab1cefe335b1f7cfd749a94732615775a6e840b3f7571d69ab4863be3adff0de` |
| `cloudbed-2_q045 / Gemini / A1_8R / C` | RECORDED_COMPLETE, `decision=diagnosis` | 1.515 | 150 | 1.665 | `c3bd313c83fcd967881ff7c425a5bd68b1bef8596696afac91b1855aa7454aac` |
| `cloudbed-2_q045 / Gemini / A1_8R / K` | RECORDED_COMPLETE, `insufficient_evidence` | 1.789 | 222 | 2.011 | `be785b7e143bcbc80ef2fa9cb3de6a4daa15dc2471c5530d285f143321be7239` |
| **Somma** | | **26.308** | **471** | **26.779** | |

Il primo stage D ha eseguito 2 chiamate LLM, 1 round tool e
19,342 secondi end-to-end. Nello stage C l'output rispetta
il contratto ed esprime una diagnosi, non una verifica GT.
Nello stage K la risposta rispetta il contratto ma non propone
un detector formalizzabile: `k_status=insufficient_evidence`,
`k_preflight_status=insufficient_evidence`,
`scientific_freeze=false`. Nessuna regola viene promossa
al test sulla base di questi risultati.

## Stato di Gemini al termine di tutti i batch

- Quattro casi discovery preregistrati:
  `cloudbed-1_q032`, `cloudbed-1_q050`,
  `cloudbed-2_q026`, `cloudbed-2_q045`.
- Due harness: `A1`, `A1_8R`.
- Tre stage logici per arm: D, C, K.
- **24/24 stage logici hanno un artefatto**.
- **23 tentativi reali** con claim: **22 `RECORDED_COMPLETE`**
  e **1 `INVALID_OUTPUT`**.
- **1 K `BLOCKED_DEPENDENCY`** è stata registrata offline,
  **senza claim e senza chiamata API**: q032/A1_8R/K dopo
  C `INVALID_OUTPUT` (errore `ContractError`,
  classificato `INVALID_JSON_SYNTAX_OR_WRAPPING`).
- L'ultimo log mostra `claims=23`,
  `stored_records=24`; tutte le precedenti esecuzioni
  hanno avuto `unresolved_manual_review=0`.
  Un controllo read-only globale verrà comunque richiesto
  come gate prima delle esecuzioni Anthropic.
- Costi di token contabilizzati da Colab:
  * prima D q032/A1: 63.571;
  * Batch 01 parziale: 50.185;
  * prosecuzione q050: 74.195;
  * Batch 02: 149.023;
  * Batch 03: 26.779.
  **Totale osservato Gemini = 363.753 token**.
- Questi token non sono automaticamente una fattura verificata
  né attestano la qualità delle diagnosi.
- I risultati Gemini non sbloccano i casi OOD test:
  `test_unlocked=false` e `scientific_freeze=false`.

## Cosa sappiamo e cosa NON sappiamo

I risultati attestano il funzionamento del percorso di
persistenza, dei contratti JSON, dei riferimenti alle
evidenze osservate e dell'astensione quando necessario.
Sono emerse regole K strutturalmente valide con
`k_status=candidate` e `requires_verification`, ma
nessuna ha ancora superato una verifica indipendente
di segnali, unità, soglie, condizioni e generalizzazione.

Non è scientificamente corretto asserire da questi log
che A1 sia più accurato di A1_8R, che le diagnosi siano
corrette rispetto alla GT, che le candidate K siano regole
sicure da eseguire o che il knowledge transfer migliori
l'accuratezza sui test. I casi test sono deliberatamente
separati e bloccati.

## Prossimo passo preregistrato

La discovery Sonnet (`claude-sonnet-5-5`) e Haiku
(`claude-haiku-5-5`) copre **24 stage logici ciascuna**
sugli stessi quattro casi e due harness.
Ogni nuova campagna deve:
- verificare i 24 record Gemini con SHA-256 e i 23 claim;
- verificare release, source SHA, split e manifest;
- essere autorizzata come consumo API Anthropic;
- usare claim e artefatti create-only, senza retry;
- fermarsi alla prima anomalia;
- non avviare stage test né promuovere regole K.

Nessun codice del protocollo, freeze o file dati
originale è stato modificato per questo report.
