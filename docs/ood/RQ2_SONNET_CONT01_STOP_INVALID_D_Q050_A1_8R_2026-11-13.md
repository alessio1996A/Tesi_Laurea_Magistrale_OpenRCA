# RQ2 — Sonnet continuazione 01: arresto dopo D invalida q050/A1_8R

**13 novembre 2026. Fonte:** output di Google Colab condiviso dall'utente.
`GIT_HEAD=f9b5424d86ab298a0e1a5f4a35673a24a892fd2d`.
Registrazione documentale; nessun accesso API o scrittura dei risultati
scientifici attraverso questo report.

## Esito del preflight e delle dipendenze

- `Q050_A1_8R_C_ABSTENTION_WITH_ZERO_EVIDENCE_CONFIRMED`.
- `SONNET_CONT01_PREFLIGHT_OK_10_NEW_STAGES_NO_API`.
- `AUTHORIZED_SONNET_CONT01_COUNT=10`.
- C `cloudbed-1_q050/sonnet/A1/C` marcata
  `BLOCKED_DEPENDENCY` offline, senza claim né chiamate API.
  SHA record:
  `597af38f53d185206053d8f0cfc9a42e697e3b3a913e80c68c72a88975900868`.
- K `cloudbed-1_q050/sonnet/A1/K` marcata
  `BLOCKED_DEPENDENCY` offline, senza claim né chiamate API.
  SHA record:
  `e9a203b60c5eb40d449cf8d1c953c6bce1f7127865ac133a07ca39a1938f94bf`.
- Totale record dopo i due blocchi: 33. Nessuna chiamata
  provider per queste due registrazioni logiche.

## Nuovo tentativo Sonnet

| Stage | Stato | SHA-256 record | Token input | Token output | Totale |
|---|---|---|---:|---:|---:|
| `cloudbed-1_q050/sonnet/A1_8R/D` | `INVALID_OUTPUT` | `d6d3c14cc1359b010b9320d17655c0a2b3db893235922cf9c7369bc2fdac6eea` | 108.135 | 2.045 | **110.180** |

- SHA-256 claim:
  `6731a3d56b714ab54bc425252d645c188da7acf13cce0bc7d8a509b8c64c8020`.
- 5 chiamate LLM; 4 round tool; usage completo;
  28,353 secondi end-to-end.
- Arresto:
  `SONNET_CONT01_STOP_NONCOMPLETE_NO_RETRY`.
- Risultato salvato; il journal nell'ultima riga riporta
  **31 claim** e **34 artefatti**.
- Gli stage q050/A1_8R/C e K sono ancora *non tentati*;
  NON devono chiamare Anthropic dopo D invalida.
- Nessuno degli altri 9 stage del blocco è stato avviato.
- Nessuno dei 24 stage Haiku è stato avviato.
- I casi test OOD restano locked.

## Stato aggregato RQ2 al momento dell'arresto

- Gemini: 24 stage con artefatto,
  23 tentativi reali (22 `RECORDED_COMPLETE`,
  1 `INVALID_OUTPUT`) e una K bloccata offline.
- Sonnet: 10 stage con artefatto:
  7 D/C/K reali (6 `RECORDED_COMPLETE`,
  1 `INVALID_OUTPUT`), 2 blocchi logici C/K offline
  e una nuova D reale `INVALID_OUTPUT`.
- Totali: 34 artefatti, 31 tentativi reali con claim,
  3 blocchi logici offline.
- Sonnet usa ora 368.648 token osservati
  (258.468 nei primi 7 stage + 110.180).
- Gemini ha contabilizzato 363.753 token: il totale
  RQ2 osservato finora è **732.401 token**.
  Questa non è una fattura di costo in USD.

## Attenzione all'interpretazione dell'errore

Il log mostra soltanto `status=INVALID_OUTPUT` della D.
Il recorder D, diversamente dal recorder C,
considera la **validità dell'evidence bundle** costruito
dalla traiettoria dei tool; un JSON finale valido può
coesistere con `INVALID_OUTPUT` se il bundle fallisce.
Per la D q050/A1 del batch precedente sappiamo da audit
che la causa era `AMBIGUOUS_TOOL_RESULT` e il JSON
era `valid_json`. Per la D q050/A1_8R **non dobbiamo
presumere** la stessa causa senza audit diretto.

## Decisione operativa

1. Preservare immutati claim e record D q050/A1_8R;
   nessun retry o normalizzazione.
2. Eseguire soltanto audit read-only dell'archivio
   completo (24 Gemini, 10 Sonnet), riproducendo
   localmente e senza chiamate modello l'errore
   dell'evidence builder e mostrando metadati filtrati.
3. Dopo l'audit, registrare C e K q050/A1_8R
   `BLOCKED_DEPENDENCY` offline e riprendere
   dai soli stage mai tentati di `cloudbed-2_q026`.
4. Nessun adattamento di parser, prompt, runner o regole
   in questa coorte. Qualunque revisione futura dovrà
   essere una nuova versione/campagna tracciata,
   senza reimpiegare i test OOD per ottimizzazione.
