# RQ2 — Gemini Discovery Batch 02: 10/10 stage reali, esito consolidato

**Data di acquisizione:** 12 novembre 2026.
**Fonte:** output Colab trasmesso dall'utente in chat dopo esecuzione
della cella `RQ2_GEMINI_DISCOVERY_BATCH02_10_STAGE_2026-11-12.md`;
registrazione documentale, non ripetizione dei tentativi.

## Identità e controlli

- GIT_HEAD del runtime: `62732d39138eb598ecfe662d584c49f7330fbbae`.
- `Q050_A1_8R_C_ABSTENTION_WITH_ZERO_EVIDENCE_CONFIRMED`.
- `BATCH02_PREFLIGHT_OK_10_NEW_STAGES_NO_API`.
- `AUTHORIZED_BATCH02_COUNT: 10`.
- `STATUS: BATCH02_10_REAL_DISCOVERY_STAGES_COMPLETED`.
- `BATCH02_COMPLETED: 10`; `NO_OTHER_STAGES_AUTORUN: TRUE`;
  `OOD_TEST: LOCKED`.
- Tutte le 10 fasi sono `RECORDED_COMPLETE`; hash dei record e
  dei claim restituiti dal journal; nessun errore osservato nel blocco.
  Il journal alla decima fase riporta 20 claim e 21 artefatti.

## Risultati osservati

| # | Caso | Harness | Stage | Token | SHA-256 record |
|---:|---|---|---|---:|---|
| 1 | cloudbed-1_q050 | A1_8R | K | 1.066 | `8938bb9c14e6eee9ef4fea616f4ef67034a575a79fc28c732698a416424993fc` |
| 2 | cloudbed-2_q026 | A1 | D | 31.876 | `12ffca57087cdfbda237ecc78cb77df9324ee4aba287ceb7f3e9356b4c6b9e59` |
| 3 | cloudbed-2_q026 | A1 | C | 2.464 | `dff54a14f6edc932b6498efa3085f7ee7824c013f92491984329f5177f5090ff` |
| 4 | cloudbed-2_q026 | A1 | K | 3.133 | `9d969ca0cce8974c3cd70a67043c2c0039aa53ae7f6dcbafd76e427d9f0d6009` |
| 5 | cloudbed-2_q026 | A1_8R | D | 51.116 | `9c86a91f061bd71c251dd083e60f3b54b4c7584d86096eca5c7a5c00a8dca3d8` |
| 6 | cloudbed-2_q026 | A1_8R | C | 2.778 | `7dc7d262c12e86dd9638d8b2d0472ada7df834ed77b96cbf60c475d4d87ad70a` |
| 7 | cloudbed-2_q026 | A1_8R | K | 3.148 | `4042ca2e27ba98cba99d5b7110c5da454237593ba100ff08be400b35533097a0` |
| 8 | cloudbed-2_q045 | A1 | D | 44.135 | `b8eac499f484e65a59ac9088e65e3b34c3151a37d964519691a06085986cf0ca` |
| 9 | cloudbed-2_q045 | A1 | C | 4.396 | `7e0b9a8966d073d8626795a887e1616680489f6832d7dac4e601a02daebf9a81` |
| 10 | cloudbed-2_q045 | A1 | K | 4.911 | `32ddf6815e4216f0a46070950252852cec984f4456a0bb3758c86b16d1296add` |
| **Totale** | | | | **149.023** | |

### Distinzione diagnosi/classificazione/regole candidate

- q050 / A1_8R / K: `status=RECORDED_COMPLETE`,
  `k_status=insufficient_evidence`,
  `k_preflight_status=insufficient_evidence`,
  `scientific_freeze=false`. La D precedente aveva zero
  osservazioni di tool e C aveva correttamente `decision=abstain`.
- q026 / A1 / D: 7 LLM calls, 6 tool rounds, 31.876 token,
  54,530 secondi end-to-end. C: `decision=diagnosis`.
  K: `status=candidate`, `preflight=requires_verification`,
  `scientific_freeze=false`.
- q026 / A1_8R / D: 5 LLM calls, 4 tool rounds,
  51.116 token, 19,638 secondi. C: `decision=abstain`.
  K: `insufficient_evidence`, `scientific_freeze=false`.
- q045 / A1 / D: 6 LLM calls, 5 tool rounds, 44.135
  token, 52,448 secondi. C: `decision=diagnosis`.
  K: `candidate` e `requires_verification`,
  `scientific_freeze=false`.

**Limiti:** lo stato `RECORDED_COMPLETE` è validità del contratto
e della provenienza, non scoring della diagnosi rispetto a GT.
Una K `candidate` non è un detector deterministico verificato,
né una regola pronta per test. `insufficient_evidence` non è
un successo di knowledge transfer. I 132 stage test rimangono
LOCKED; nessuna etichetta GT è stata consultata.

## Stato progressivo e prossimo passo

- Su 24 stage Gemini discovery: 21 hanno un artefatto,
  di cui 19 `RECORDED_COMPLETE`, 1 `INVALID_OUTPUT`
  (q032/A1_8R/C), 1 `BLOCKED_DEPENDENCY`
  (q032/A1_8R/K, offline, nessun claim).
- Tentativi reali: 20; claim: 20; artefatti: 21;
  nessun claim irrisolto segnalato.
- Token precedenti osservati: 187.951; nuovi: 149.023;
  totale osservato: **336.974 token**. Nessuna stima USD
  ufficiale viene derivata dai soli contatori token.
- Ultimi tre stage Gemini ancora non tentati:
  `cloudbed-2_q045 / A1_8R / D, C, K`.
  La loro esecuzione richiede nuovi gate su hash, journal,
  contratto di progetto, assenza claim/artefatti preesistenti
  e consenso dell'utente al batch (già dato per blocchi fino a 10).
  Gli stage Sonnet/Haiku non vengono avviati automaticamente.

Nessun codice RQ1/RQ2, prompt, release firmato o risultato
create-only è stato modificato nella redazione di questo rapporto.
