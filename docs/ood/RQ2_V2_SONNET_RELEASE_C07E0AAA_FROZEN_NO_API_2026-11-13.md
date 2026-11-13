# RQ2 V2 — Release Sonnet 5.5 congelata su Drive, nessuna API ancora chiamata

Data: 13 novembre 2026. **Report scientifico post-release, pre-run.** Documentazione in un branch separato dal commit di codice verificato.

## Evidenza test e fonte

- PyCharm suite integrata: **867/867 PASS** in 77.935 s.
- Colab source-bound: `SONNET_V2_FINAL_PREFLIGHT_OK` su commit `bf2b0a0a67977a65c79d47ada4b07e825eaf8dff`.
- Source binding SHA-256: `05c1c12072432e6ee7332802142dd709a6a9adfbf71845615274bbd927240f0b`.
- Split SHA-256: `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`.
- Manifest SHA-256: `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`.
- V2 graph SHA-256: `c630ac3bef1c25465783e68854ad11cf24935b5a98dce9244308523c86f93df3`.

## La release realmente creata dall'utente in Colab

```text
STATUS: SONNET_V2_RELEASE_FROZEN_NO_API
RELEASE_SHA256: c07e0aaa19b6cc1826e532c7da89e856c68e73975be84f572a727c09c7580813
STAGE_ID: rq2_v2_sonnet_q050_d_sourcebound_pilot_v1:cloudbed-1_q050:sonnet:A1:D
CODE_COMMIT: bf2b0a0a67977a65c79d47ada4b07e825eaf8dff
SOURCE_BINDING_SHA256: 05c1c12072432e6ee7332802142dd709a6a9adfbf71845615274bbd927240f0b
APPROVED_OPERATIONAL_LIMIT_USD: 5.0
API_CALLS: 0
CLAIM_CREATED: FALSE
RECORD_CREATED: FALSE
OOD_TEST: LOCKED
```

La release e' `release_v1.json` nel namespace dedicato
`data/rq2_v2_provenance/sonnet_q050_d_pilot_v1/`, su Drive.
Usa `authorization=approved_for_one_pilot`; non equivale a esecuzione.
Input e codice sono gia' certificati nel preflight. La release canonical
e' riletta e verificata con `read_frozen_release`.

## Protocollo run futura (NON ancora eseguita in questo report)

Una e una sola run autentica su `cloudbed-1_q050 / sonnet / A1 / D` per provenance, non test di generalizzazione:
- `claude-sonnet-5-5`, `v2_enforce`, max 6 tool round, 7 invocazioni LLM, max output 4096, timeout 300s *per chiamata*, max_retries=0.
- Limite operativo di costo stimato USD 5.00, **non hard cap USD**. Pricing base Anthropic (2026-11-13) USD 2 per MTok input, USD 10 per MTok output, differenze possibili per caching.
- Il driver crea il claim *prima* della prima API; archivia il risultato una volta in JSON canonico con SHA/readback. Il meter e' persistito in `diagnostic_run.metrics.rq2_v2_execution_meter`.
- Fail-closed: provider error, crash, timeout, record invalido o claim orfano sono preservati, **MAI** riprovare lo stesso stage automaticamente.
- LLM secret tramite Colab Secrets; non salvarlo in file, stamparlo o includerlo nel report. Nessuna C/K; OOD test locked; V1 non letto/scritto durante il pilot V2.
- La futura cella live richiede ulteriore preflight read-only e un comando esplicito `confirm_paid_api=True` deciso dall'utente.

Nessun esito D reale puo' essere dichiarato in questo report.
