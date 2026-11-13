# RQ2 — Sonnet q050/A1/D: audit read-only verificato

**Data:** 13 novembre 2026. **Fonte:** output Colab di
`RQ2_SONNET_BATCH01_D_Q050_INVALID_AUDIT_READONLY_2026-11-13.md`
inviato dall'utente. `GIT_HEAD=c9d1b8fba77cf94a57990a253ed917c29d0998f7`.
Questo file è soltanto documentazione: nessuna chiamata API o
scrittura/modifica di dati scientifici è stata effettuata dal
processo di redazione.

## Integrità archivio

- `audit=SONNET_BATCH01_READ_ONLY_AUDIT`.
- `claims=30` e `finished_with_matching_result=30`.
- `unresolved_manual_review=0`.
- `result_archive_discovery_count=31`.
- **24 record Gemini + 7 record Sonnet** verificati contro SHA-256.
- `sonnet_unattempted_stages=17`; `haiku_unattempted_stages=24`.
- `test_unlocked=false`.
- Il controllo ha effettuato `PROVIDER_API_REQUESTS=0` e
  `DATA_FILES_WRITTEN=0`.

## Natura dell'INVALID_OUTPUT

Stage:
`rq2_dryrun_workflow_preview_v0:cloudbed-1_q050:sonnet:A1:D`

- Record SHA-256:
  `03c51f1260d0981a691bc8af381b1ed736220a54883919033250e14d37f66d10`.
- `d_invalid_reason_code=AMBIGUOUS_TOOL_RESULT`.
- `d_invalid_issue_type=EvidenceBundleError`.
- `original_d_json_status=valid_json`.
- `d_provider_error_present=false`.
- Traccia: **24 eventi** (12 `tool_call`, 12 `tool_result`).
- Il parser del bundle RQ2 non riesce ad associare in modo
  non ambiguo almeno un risultato tool alla sua chiamata nel
  formato legacy privo di associazione sufficiente.
  Il semplice conteggio numerico 12/12 **non** garantisce
  una mappatura univoca.
- Non è un malfunzionamento HTTP di Anthropic; non è
  neppure dimostrato un JSON D finale invalido, anzi
  `original_d_json_status=valid_json`.
- Questa anomalia indica **integrità insufficiente della
  provenienza delle osservazioni**, non prova la correttezza
  o l'incorrettezza della diagnosi originale.

## Decisione metodologica e prossimo passo

Il record originario D e il suo claim rimangono create-only
e non possono essere ritentati nella campagna congelata.

La C e la K q050/sonnet/A1 non devono invocare Anthropic:
registrare prima C, quindi K come `BLOCKED_DEPENDENCY`
offline, con `raw_response=None`, `provider_error=None`,
nessun nuovo claim. Tali record sono esiti logici, **non**
nuovi tentativi LLM.

La D `cloudbed-1_q050/sonnet/A1_8R/D` è indipendente,
non tentata ed è la successiva in ordine preregistrato,
seguita dagli stage fino a `cloudbed-2_q045/sonnet/A1/D`.
Il prossimo batch di 10 tentativi reali può essere preparato
soltanto dopo il gate di integrità di tutti i 31 record
esistenti, verifica dell'assenza di altri claim, protezione
della release immutabile e consenso per i costi API.

Non modificare l'evidence bundler RQ2, il protocollo RQ1
o gli esperimenti precedenti per correggere post hoc
l'anomalia. Una eventuale ripetizione è una nuova
campagna motivata e separata, mai una sovrascrittura.
Gli undici casi test OOD rimangono chiusi.
