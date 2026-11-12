# RQ2 — Prima D reale Gemini A1 su cloudbed-1_q032: esito verificato

**Data:** 12 novembre 2026. **Fonte:** output dell'audit di sola lettura
eseguito dall'utente su Google Colab e condiviso in chat.
**Stato:** singola D discovery **RECORDED_COMPLETE**;
nessuna C/K eseguita e test OOD ancora bloccati.

## Identità del tentativo

- Commit del checkout che ha eseguito la D:
  `dbf6ba239e62ba55dfd387e6e7b02dde07d728fd`.
- Commit del checkout dell'audit successivo:
  `cc866666b2117d699c75d63512cded15d4d9e821`.
- Stage ID: `rq2_dryrun_workflow_preview_v0:cloudbed-1_q032:gemini:A1:D`.
- Provider: Google; modello: `gemini-3.5-flash-lite`;
  variante: `A1`; fase: discovery; stage: `D`.
- Release immutabile sul Drive:
  SHA-256 `a35c02f830a3c5f97424e0cbf8653eda6cfa674b9c8c34d95d04627e1dba8c52`.
- Claim:
  `a64b2f3c19e9a179975fa99db31c820fd6840b575b3dc2f42a6fa550e35394f6`.
- Record di output:
  `73c1006d134ffef5bad7cba380925546c84d58c2ed20ba1730f75f1f42bbdfe7`.
- Stato archivio: `CLAIM_AND_ARTIFACT_VERIFIED` /
  `RECORDED_COMPLETE`.
- Journal: `claims=1`, `finished_with_matching_result=1`,
  `unresolved_manual_review=0`,
  `result_archive_discovery_count=1`.
- Nessun provider/tool invocato dalla cella di audit, che è solo lettura.
  Non ripetere la D anche in presenza di modifiche del notebook.

## Misure effettivamente riportate

| Indicatore | Osservato |
|---|---:|
| Chiamate LLM nella D | 7 |
| Round di tool | 6 |
| Token input | 63.087 |
| Token output | 484 |
| Token totali | 63.571 |
| Uso token completo | true |
| Preprocessing | 9,985 s |
| Durata end-to-end | 41,398 s |
| Lunghezza tool trajectory | 12 |
| JSON D task-aware valido | true |
| Errore provider/runner | false |
| Evidence bundle presente | true |
| Problema traiettoria | null |
| Test OOD sbloccato | false |

`original_d_json_status_is_valid=true` è una validazione
**strutturale del contratto task-aware**, NON un confronto con
l'etichetta ufficiale. `RECORDED_COMPLETE` indica che la
traiettoria è utilizzabile per il successivo C: **non** prova
che la causa diagnosticata sia corretta. Non è stato effettuato
scoring offline Microsoft né consultazione della ground truth.

Il conteggio di 7 chiamate deriva dal runner e **non equivale**
a 7 stage logici: è stato eseguito esattamente un solo stage D.
La durata end-to-end comprende preprocessing e modello, non è
un tempo di singola richiesta HTTP. I costi effettivi non sono
stati accertati dal report e non vanno presentati come fattura.

## Passo successivo condizionato

Il successivo stage dello stesso arm secondo il piano congelato è:
`rq2_dryrun_workflow_preview_v0:cloudbed-1_q032:gemini:A1:C`.

Il contratto C usa **solo istruzione originale GT-free ed
evidenze dei tool D (E###)** ricostruite dal record archiviato,
non la risposta finale D; non abilita tool; prevede **una**
invocazione `invoke` sincrona separata.
La verifica delle dipendenze e il claim create-only avvengono
prima del provider nel wrapper `run_one_claimed_ck`.

**C non è ancora autorizzata dall'utente.**
Prima della singola chiamata reale C serve consenso esplicito
per questa esatta combinazione, seguito da una sola cella
con preflight di release, stato record D e assenza claim C;
nessun retry automatico. Non avviare K automaticamente,
non aprire la test OOD (11 incidenti) prima del freeze
indipendente delle regole candidate.

Il presente documento registra esclusivamente dati osservati;
nessuna modifica ai 13 sorgenti RQ1, nessun cambiamento del
release, nessun nuovo stage e nessuna valutazione GT.
