# RQ2 — Batch Gemini 01 interrotto alla C invalida: audit reale acquisito

**Data:** 12 novembre 2026. **Evidenza:** output della cella Colab
`RQ2_GEMINI_BATCH01_STOP_INVALID_C_AUDIT_2026-11-12.md`
eseguita dall'utente; zero API e zero scritture durante l'audit.

## Stato journal dopo l'interruzione

- Checkout audit: `44c63212c203af898d66ebb4d652cdd36ea366b2`.
- `claims=5`; `finished_with_matching_result=5`;
  `unresolved_manual_review=0`.
- Cinque record RQ2 persistiti, tutti riletti e verificati.
- `test_unlocked=false`: nessun test OOD avviato.
- `remaining_not_started=6` nel primo batch di dieci.
- `can_reinvoke_invalid_c=false`; la C non valida **non deve
  essere ripetuta**, riparata o riqualificata a posteriori.

| Caso | Harness | Stage | Esito registrato | SHA-256 record |
|---|---|---|---|---|
| cloudbed-1_q032 | A1 | D | RECORDED_COMPLETE | `73c1006d134ffef5bad7cba380925546c84d58c2ed20ba1730f75f1f42bbdfe7` |
| cloudbed-1_q032 | A1 | C | RECORDED_COMPLETE | `611358878be6cd439bd2d66cf20607d0653a099ba6ad75dbceed4a3fe8b34a06` |
| cloudbed-1_q032 | A1 | K | RECORDED_COMPLETE | `200fd07a480f6e4c47a283c9e4dd39db707f4cb5b1a70acb5974e29b857a9742` |
| cloudbed-1_q032 | A1_8R | D | RECORDED_COMPLETE | `f3b92c3722ff0f19d91159431b9923e63dfeb0423d147ebb71468004d5ef4a67` |
| cloudbed-1_q032 | A1_8R | C | INVALID_OUTPUT | `fb4e321c63452fed5ef632dcd2f3a6c2e10459d2d31ebf136678439595478bd9` |

## Diagnosi del contratto C invalido

- Codice offline di classificazione:
  `INVALID_JSON_SYNTAX_OR_WRAPPING`.
- Tipo errore di contratto conservato: `ContractError`.
- SHA-256 risposta originale C:
  `d85c5a8ebca888e2dba937c8654633d956a641c8f9f6466fa28b03cd002d259d`.
- Il trasporto ha riportato usage completo, con 3.429 token.
- La categoria `INVALID_JSON_SYNTAX_OR_WRAPPING` è una famiglia
  di possibili errori: non identifica con certezza un Markdown fence
  rispetto a una sintassi JSON errata, né prova che il fault type
  semanticamente corretto fosse presente nel testo. La risposta raw
  è conservata senza normalizzazioni in Drive, non divulgata in chat.
- Non è stato verificato alcun confronto con ground truth.

## Conseguenze preregistrate

1. La K dello stesso arm `cloudbed-1_q032 / Gemini / A1_8R`
   non può essere invocata, poiché la C non è
   `RECORDED_COMPLETE`. La API K **non** sarà chiamata.
2. La K può essere registrata **offline** una sola volta come
   `BLOCKED_DEPENDENCY`, con `artifact={}` e **nessun claim API**,
   rispettando il controllo già implementato in
   `rq2_discovery_stage_recorder.record_k`. Il record è un esito
   logico della fase K, non un nuovo tentativo LLM.
3. Gli altri 5 stage `cloudbed-1_q050` mai avviati rimangono
   eleggibili a un nuovo batch che riusa il release originale, la
   stessa politica di modello e il medesimo protocollo. Stop
   immediato al primo status non `RECORDED_COMPLETE`.
4. La C invalida contribuisce agli errori nelle analisi RQ2,
   mantenendo il denominatore e senza inventare successi. Nessuna
   modifica a prompt, parser, retry policy o freeze RQ1.
5. Stage K già `RECORDED_COMPLETE` altrove significa formato
   valido, non regola formalizzata o trasferimento riuscito;
   le regole K richiedono verifica di semantica/unita/KPI e
   successivo freeze indipendente prima di qualsiasi test.

## Costi/consumi osservati per i 4 nuovi tentativi del batch

| Stage nuovo | Token totali |
|---|---:|
| q032 / A1 / C | 5.615 |
| q032 / A1 / K | 6.036 |
| q032 / A1_8R / D | 35.105 |
| q032 / A1_8R / C | 3.429 |
| **Totale** | **50.185** |

Aggiungendo la D iniziale q032/A1 (63.571 token)
il totale RQ2 osservato finora è **113.756 token**
su **5 tentativi live registrati**. Questo non equivale
a un costo USD certificato: richiede i prezzi effettivi
del modello/periodo e la lettura dei dettagli di usage.

Nessuna nuova API e nessuna scrittura nei dati persistenti
sono state effettuate per redigere il presente report.
