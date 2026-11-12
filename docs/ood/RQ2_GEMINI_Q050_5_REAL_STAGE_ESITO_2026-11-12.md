# RQ2 — Esito reale q050 e chiusura coerente del Batch 01

**Data:** 12 novembre 2026.
**Fonte:** output Colab comunicato dall'utente dopo la cella create-only
`RQ2_GEMINI_BATCH01_CONTINUAZIONE_5_Q050_DOPO_INVALID_C_2026-11-12.md`.
Questa è una registrazione documentale, non un nuovo tentativo API.

## Preflight e provenienza

- Commit Colab: `d8055af8585f6a3ca1a2d1b2d6c4b5aba6b8b44b`.
- `BATCH01_CONTINUATION_PREFLIGHT_OK_NO_API`: passato.
- `GOOGLE_CREDENTIAL: PRESENT_NOT_PRINTED`.
- `STATUS: Q050_FIVE_REAL_STAGES_COMPLETED`, `Q050_COMPLETED: 5`.
- La C `INVALID_OUTPUT` di q032/A1_8R è conservata immutata.
- La K dipendente q032/A1_8R è stata registrata offline come
  `BLOCKED_DEPENDENCY`: SHA record
  `68a4829f57212a36067ccd05a224e39b03133469a89a0fdae1fc552760cd3d63`.
  Non è stato creato claim, `llm_calls=0`.
- Il controllo del batch ha continuato soltanto sui cinque stage q050
  mai tentati, senza ripetere nessuno dei cinque tentativi preesistenti.
- `NEXT_STAGE_NOT_AUTO_LAUNCHED: TRUE`; `OOD_TEST: LOCKED`.

## Risultati dei 5 stage q050 eseguiti

| Harness | Stage | Stato | Token | SHA-256 record |
|---|---|---|---:|---|
| A1 | D | RECORDED_COMPLETE | 57.506 | `86874d575a848dfea505c9f4a7d768820a88aed147c104c77c98b29a586e3bab` |
| A1 | C | RECORDED_COMPLETE | 5.187 | `5d4dedf8be13e976b57638e599eee77161263b230aafeffe983158ee602e3d61` |
| A1 | K | RECORDED_COMPLETE | 5.545 | `757acfdabc5842961d07c48431af826896b3e4008e535af0bb831e2f980e90e8` |
| A1_8R | D | RECORDED_COMPLETE | 5.238 | `afd932403b3a1cfe38cb676c048875fbf968336d8f786a5dbed56c4a78cf5f9a` |
| A1_8R | C | RECORDED_COMPLETE | 719 | `b982a1ee1dd111e7e6f1f5ea552cde6e55a9d7c3011eadaccb1b33a9b942d987` |

Il trasporto riporta `token_usage_complete=true` per le D
e `complete=true` per le C/K.

### Dettagli della D q050/A1

- 7 chiamate LLM, 6 round di tool.
- Input 57.084 token, output 422 token.
- Tempo end-to-end 53,147 secondi.

### Dettagli della D q050/A1_8R

- 1 chiamata LLM e **zero round di tool**.
- Input 5.214 token, output 24 token.
- Tempo end-to-end 7,561 secondi.
- `RECORDED_COMPLETE` indica che il contratto D/traiettoria è
  strutturalmente accettabile, **non** una diagnosi corretta e
  **non** prova l'acquisizione di osservazioni telemetriche.
- La C q050/A1_8R è `RECORDED_COMPLETE`, ma l'output riportato
  non include il suo campo `decision`. Il contratto C vigente
  esige evidence_ids per una decisione `diagnosis`.
  Con zero risultati tool, un C valido è compatibile con
  `decision=abstain`; verificarlo con audit di sola lettura
  **prima** del successivo K. Non inferire o inventare fault type.

## Stato aggregato dopo la continuazione

- **10 tentativi live Gemini** create-only (1 prima D +
  4 del blocco parziale + 5 del q050).
- **9 `RECORDED_COMPLETE`, 1 `INVALID_OUTPUT`**.
- **1 `BLOCKED_DEPENDENCY`** offline per la K q032/A1_8R,
  senza chiamate provider.
- **10 claim, 11 record** RQ2 persistiti, zero tentativi
  irrisolti secondo la sequenza di log Colab.
- Token osservati nei 5 nuovi tentativi q050: **74.195**.
- Token osservati su 10 tentativi live cumulativi: **187.951**
  (63.571 + 50.185 + 74.195). Non corrisponde automaticamente
  ad un importo in USD certificato.
- **11/24 stage logici discovery Gemini** hanno ora un record
  (10 tentativi API + un blocco logico). Ancora 13 non iniziati.
- I casi di test OOD restano chiusi e non sono stati usati
  né per i prompt né per lo scoring.

## Prossimi stage selezionati senza adaptive tuning

La posizione 12 nel piano Gemini è la K q050/A1_8R:
`rq2_dryrun_workflow_preview_v0:cloudbed-1_q050:gemini:A1_8R:K`.
Poi vengono i sei stage D/C/K su q026 (A1 e A1_8R)
e i tre D/C/K su q045/A1: esattamente 10 stage.
Il piano, l'harness, i prompt e le regole non verranno
modificati in base alla performance q032/q050.
Il nuovo batch deve essere preceduto da verifica read-only
che C q050/A1_8R è una **astensione** perché l'evidence bundle
della relativa D è vuoto. Astenersi correttamente non è
una diagnosi esatta, e non autorizza la creazione di una
regola deterministica.

Per questi stage resta l'autorizzazione utente a procedere
con batch discovery fino a dieci, con claim create-only e
stop-on-error. Nessun retry automatico o nuovo accesso ai test.
