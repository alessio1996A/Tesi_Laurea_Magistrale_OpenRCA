# RQ2 — Sonnet Batch 01 parziale: 7 tentativi, stop D q050/A1

**Data:** 13 novembre 2026. **Fonte:** output Colab comunicato dall'utente,
con `GIT_HEAD=c97b7527ee8b3ceda68c3a47d7ae4ddd08988723`
e `SONNET_BATCH01_PREFLIGHT_OK_10_NEW_STAGES_NO_API`.
Il presente report è documentale; non ha chiamato Anthropic,
modificato sorgenti, corretto risposte o scritto sul Drive.

## Stato del batch autorizzato

Il piano autorizzava 10 stage Sonnet discovery in sequenza.
I primi 6 sono `RECORDED_COMPLETE`, il settimo è
`INVALID_OUTPUT` ed ha arrestato immediatamente il batch
(`SONNET_BATCH01_STOP_NONCOMPLETE_NO_RETRY`).
Gli ultimi tre non sono stati avviati:
`cloudbed-1_q050/sonnet/A1/C`,
`cloudbed-1_q050/sonnet/A1/K`,
`cloudbed-1_q050/sonnet/A1_8R/D`.
Sono 30 claim con risultato e 31 archivi totali (inclusi
23 tentativi Gemini e una K bloccata senza claim).

| # | Caso | Harness | Stage | Stato | Token | SHA-256 record |
|---:|---|---|---|---|---:|---|
| 1 | cloudbed-1_q032 | A1 | D | RECORDED_COMPLETE | 21.764 | `77c5213484351bbb447d8b5e71adac5c986fb563d80b0be3a030c68fc2d1dbb8` |
| 2 | cloudbed-1_q032 | A1 | C | RECORDED_COMPLETE; decision=diagnosis | 4.573 | `dab2ad70fbfe65ffec3dd114b20d12190f813e482804b4f5fc6416441ef639f8` |
| 3 | cloudbed-1_q032 | A1 | K | RECORDED_COMPLETE; insufficient_evidence | 5.554 | `b3b3e0759856991f6fc51326b5024f555547efb0b24c18988f5454081b1f1c0a` |
| 4 | cloudbed-1_q032 | A1_8R | D | RECORDED_COMPLETE | 53.755 | `9328673bb87ba79a51f1d686d36879b822046ea4e52ec3982fd8a6ab8cef899f` |
| 5 | cloudbed-1_q032 | A1_8R | C | RECORDED_COMPLETE; decision=diagnosis | 7.282 | `6e2ff1935e784b105de8624c99b74ff31f57bfba0acb27cf7dc1643b5da5c956` |
| 6 | cloudbed-1_q032 | A1_8R | K | RECORDED_COMPLETE; insufficient_evidence | 8.510 | `b7cca8069ef3049491f6905cf3aa8f88c5efcdb4eebbc3a65f2275d2409ae08a` |
| 7 | cloudbed-1_q050 | A1 | D | INVALID_OUTPUT | 157.030 | `03c51f1260d0981a691bc8af381b1ed736220a54883919033250e14d37f66d10` |

**Totale nuovi token Sonnet: 258.468**,
di cui 154.344 input e 2.686 output appartengono alla sola
D invalida (157.030 token complessivi).
I 6 stage iniziali hanno utilizzato 101.438 token.

## Diagnosi tecnica: distinguere JSON D e traiettoria tool

Nel recorder immutabile
`src/evaluation/rq2_discovery_stage_recorder.py`,
`record_d` assegna `PROVIDER_ERROR` quando
`diagnostic_run["error"]` è non nullo. Quando non vi è errore
e `build_evidence_bundle(diagnostic_run["tool_trajectory"])`
solleva `EvidenceBundleError`, `KeyError`,
`TypeError` o `ValueError`, salva `INVALID_OUTPUT`
e `tool_trajectory_issue=type(exc).__name__`.
La validità del JSON finale della D è memorizzata
separatamente in `original_d_json_status`. Pertanto
**non** considerare D `INVALID_OUTPUT` una prova di
output JSON finale invalido: serve leggere il campo del
recorder e verificare l'integrità del journal in audit offline.
Non correggere né normalizzare i byte originali.

Con D `INVALID_OUTPUT`, la C dipendente q050/A1
**non** deve invocare Anthropic: il percorso esistente
`record_c(raw_response=None,provider_error=None)`
può salvare `BLOCKED_DEPENDENCY` senza claim/provider.
Successivamente anche K q050/A1 può essere
`BLOCKED_DEPENDENCY` offline via `record_k`,
senza claim/provider. Questi passaggi richiedono
prima l'audit e una cella separata: non sono ancora stati eseguiti.

La D q050/A1_8R è indipendente dagli stage q050/A1
e non è stata tentata. Può essere avviata in un nuovo
blocco, soltanto dopo verifica dello stato preesistente.
I dati non certificano esattezza vs GT o utilità di K.
La test phase OOD rimane `LOCKED`.
