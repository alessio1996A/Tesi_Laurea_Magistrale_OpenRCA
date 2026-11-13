# RQ2 — Sonnet Continuazione 02: arresto su q026/A1/D

**Data:** 13 novembre 2026. **Fonte:** log di Google Colab comunicato
dall'utente dopo l'esecuzione della cella
`RQ2_SONNET_CONT02_BLOCCO_CK_E_10_STAGE_2026-11-13.md`.
Questo documento non modifica alcun risultato scientifico o prompt.
Il GIT_HEAD del runtime era
`6d2cdeb60a01272b738e42c289e88a72000defa8`.

## Preflight e blocchi offline

- `Q050_A1_8R_C_ABSTENTION_WITH_ZERO_EVIDENCE_CONFIRMED`.
- `SONNET_CONT02_PREFLIGHT_OK_10_NEW_STAGES_NO_API`.
- `AUTHORIZED_SONNET_CONT02_COUNT=10`.
- `q050 / Sonnet / A1_8R / C` è stato registrato
  `BLOCKED_DEPENDENCY`, **senza claim e senza API**;
  SHA-256 record:
  `f3f4aa409b25cdd92fe4bea5eb10aa84b558342e0e4b867aac14b37c54611167`.
- `q050 / Sonnet / A1_8R / K` è stato registrato
  `BLOCKED_DEPENDENCY`, **senza claim e senza API**;
  SHA-256 record:
  `a9b6c001e2d98b315cb0b2767848b4b60f83d8f897136c77c2d7f2b82be6942b`.
- Dopo i due blocchi: 36 record, 31 claim.

## Unico nuovo tentativo reale

- Stage: `rq2_dryrun_workflow_preview_v0:cloudbed-2_q026:sonnet:A1:D`.
- Stato: **`INVALID_OUTPUT`**. Record create-only SHA-256:
  `7882f3db492d3659239349f0459c4b38e75f498fa216885aedda1569d5ee85ec`.
- Claim create-only SHA-256:
  `fb7f25e0c60381f27f128a93874b05c33413a1ef506cf1f0a92b62eec7ca32fb`.
- 7 chiamate LLM, 6 round tool;
  88.534 input token, 2.721 output token,
  **91.255 token totali**; metrica token completa;
  39,993 secondi end-to-end.
- `SONNET_CONT02_STOP_NONCOMPLETE_NO_RETRY`.
- Journal finale della riga: **32 claim, 37 record**.
  Non è stato eseguito nessuno dei rimanenti
  9 stage reali del batch.

## Contabilità e limiti

- Gemini discovery completata: 24 record,
  di cui 23 tentativi reali e 1 blocco offline.
- Sonnet: 13 record dopo questo arresto,
  di cui 9 tentativi reali (6 `RECORDED_COMPLETE`,
  3 D `INVALID_OUTPUT`) e 4 `BLOCKED_DEPENDENCY`
  offline, tutti q050/A1 oppure q050/A1_8R.
- Haiku: zero tentativi.
- In totale RQ2: **37 record, 32 claim reali,
  5 stage bloccati offline**.
- Sonnet: 258.468 + 110.180 + 91.255 =
  **459.903 token osservati**.
  Gemini: 363.753 token osservati.
  RQ2: **823.656 token osservati**. Questo non è
  un rendiconto bancario dei costi.
- Il log della D q026/A1 non fornisce ancora
  `tool_trajectory_issue`, `original_d_json_status`
  né una classificazione della causa.
  **Non presumere** che sia `AMBIGUOUS_TOOL_RESULT`:
  per le due D q050 l'audit ha confermato tale causa
  e JSON finale valido, ma la D q026 richiede
  un audit proprio.
- L'insieme dei casi test OOD rimane `LOCKED`.
  Non sono disponibili risultati per valutare
  correttezza della diagnosi o successo del transfer.

## Decisione

Nessuna riesecuzione della D q026/A1 né dei precedenti
tentativi Sonnet. Nessuna modifica post hoc all'evidence
bundle, al protocollo, al modello o ai prompt.
Prima di ulteriori API a pagamento, eseguire
**audit read-only** su tutti i 37 record, verificare
zero claim irrisolti e la causa precisa dell'invalidità.
Dopo tale audit, registrare C e K q026/A1
`BLOCKED_DEPENDENCY` offline e valutare il rischio
di ulteriori D Sonnet prima di continuare la raccolta.
La ripresa dal caso indipendente
`cloudbed-2_q026/sonnet/A1_8R/D`
richiede un nuovo blocco con gate create-only.
