# RQ2 — Sonnet q026 A1, C/K bloccate offline: esito verificato

**Data:** 13 novembre 2026.
**Fonte:** stdout della cella Google Colab
`RQ2_SONNET_Q026_A1_CK_BLOCKED_OFFLINE_2026-11-13.md`
fornito dall'utente. Il runtime ha eseguito:
`GIT_HEAD=f44db56e9424ff3a7304581dffd3fe0717dd867a`.

## Integrità pre-write

La cella ha confermato
`STATUS: SONNET_Q026_BLOCK_PREFLIGHT_READ_ONLY_OK`
con 32 claim tutti accoppiati a risultato,
zero unresolved manual review e 37 record:
24 Gemini e 13 Sonnet, tutti verificati SHA-256.
Ha confermato anche che tutte e tre le D Sonnet
invalidate risultano `AMBIGUOUS_TOOL_RESULT`,
`original_d_json_status=valid_json`, senza
errori provider.

## Record nuovi — zero provider

| Stage logico | Status | SHA-256 record | Claim | API provider |
|---|---|---|---|---|
| `cloudbed-2_q026 / sonnet / A1 / C` | `BLOCKED_DEPENDENCY` | `bd79c329f58f1124b7ea59b111f390dae24a8669440e359a615dc8a86d53be36` | assente | 0 |
| `cloudbed-2_q026 / sonnet / A1 / K` | `BLOCKED_DEPENDENCY` | `6012b929b3405460e74e3d89aef7b38959eca4db24cadee54f8074bcc57e2bb1` | assente | 0 |

Output:
`STATUS: SONNET_Q026_CK_BLOCKED_OFFLINE_COMPLETED`,
`PROVIDER_API_REQUESTS_FOR_BLOCK=0`, `OOD_TEST=LOCKED`.

## Stato aggregato dopo la chiusura

- **39/72** stage logici discovery registrati.
- **32** tentativi provider con claim e risultato.
- **7** `BLOCKED_DEPENDENCY` offline, senza claim.
- Gemini: **24/24** stage (22 completi, 1 invalid C, 1 blocked K).
- Sonnet: **15/24** stage (6 completi, 3 D invalid, 6 blocked C/K).
- Haiku: **0/24**.
- I **9** stage Sonnet mai tentati, in ordine, partono da
  `cloudbed-2_q026/sonnet/A1_8R/D`; gli altri 8
  completano q026 A1_8R e q045 A1 e A1_8R.
- Totale token osservati delle chiamate eseguite:
  Gemini **363.753**, Sonnet **459.903**,
  complessivi RQ2 **823.656**. Nessun nuovo token
  consumato per C/K blocked offline.

## Limite tecnico documentato nelle D Sonnet

Le D Sonnet invalidate conservano risultati JSON
finali validi ma falliscono il controllo RQ2 di
associazione univoca delle evidenze: il runner legacy
`src/agent/graph_engine.py` salva eventi senza
`tool_call_id`, mentre `src/evaluation/rq2_evidence_bundle.py`
respinge più chiamate pendenti allo stesso tool
senza ID associabili con certezza.

Questa spiegazione è supportata dal codice congelato
e dall'audit `AMBIGUOUS_TOOL_RESULT`, ma NON
dimostra che ogni futura D avrà lo stesso errore,
né che le diagnosi siano corrette vs GT.

## Guardrail e decisioni future

Preservare tutti i claim e i record create-only.
Non rilanciare D invalidate e non riparare il
JSON/telemetria post hoc. OOD test resta LOCKED.
Un eventuale adeguamento della registrazione
`tool_call_id` richiederebbe versione e campagna
distinta, con policy, source pin e protocollo
preregistrati prima di nuove esecuzioni.

Si può proseguire nella coorte attuale soltanto
con i 9 stage Sonnet **mai tentati**,
preferibilmente in piccoli blocchi controllati
per contenere il rischio di spesa improduttiva.
È vietato presentare la registrazione di
`BLOCKED_DEPENDENCY` come un successo diagnostico.

Questo documento è solo archivio testuale: nessuna
scrittura dei dati di Google Drive da GitHub e
nessuna chiamata API.
