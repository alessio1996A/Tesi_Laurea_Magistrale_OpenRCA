# RQ2 V2 — Sonnet: regressione 867 PASS, source preflight Colab OK, release ancora assente

Data: 2026-11-13. **Questo è un documento di continuità, NON un'autorizzazione a chiamate API.**

## Evidenza osservata dall'utente

Sul branch source-only `feature/rq2-v2-sonnet-metering-audit-2026-11-13`:
- PyCharm mirato: `Ran 15 tests in 0.606s / OK`.
- PyCharm globale: `Ran 867 tests in 77.935s / OK`.
- Preflight Colab sui veri file GT-free: `SONNET_V2_FINAL_PREFLIGHT_OK`.
- `COMMIT=bf2b0a0a67977a65c79d47ada4b07e825eaf8dff`
- `STAGE_ID=rq2_v2_sonnet_q050_d_sourcebound_pilot_v1:cloudbed-1_q050:sonnet:A1:D`
- `SOURCE_BINDING_SHA256=05c1c12072432e6ee7332802142dd709a6a9adfbf71845615274bbd927240f0b`
- `SDK_RUNTIME=PINNED`, `API_CALLS=0`, `CLAIM_CREATED=FALSE`, `OOD_TEST=LOCKED`.
- Freeze degli input originali: split SHA256 `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`, manifest SHA256 `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`, V2 graph SHA256 `c630ac3bef1c25465783e68854ad11cf24935b5a98dce9244308523c86f93df3`.

La suite offline supera i gate tecnici, ma non prova ancora una D autentica né la generalizzazione RQ2.

## Decisione budget e disciplina sperimentale

L'utente riferisce che il professore ha consentito un budget API ampio e preferirebbe, dopo la validazione del pilot, esecuzioni controllate in gruppi di 5 o 10. Il primo pilot resta UNA sola D tecnica, nessun C/K, nessun OOD, no retry, max 7 richieste LLM, max 6 tool round, timeout per richiesta 300s, max output token 4096, `v2_enforce`. Soglia operativa PROPOSTA per il pilot: USD 5.00, non hard cap di fatturazione; il listino Anthropic Sonnet 5.5 al 13 novembre e' USD 2/MTok input e USD 10/MTok output. La scelta di 5 o 10 run future richiede piano e freeze separati.

## Separazione della documentazione dal commit scientifico

Il presente documento vive SOLO su un **branch documentale separato** (`docs/rq2-v2-sonnet-final-prefreeze-2026-11-13`), creato a partire dal commit sorgente sopra. Non aggiornare il branch sorgente verificato, altrimenti il `SOURCE_BINDING_SHA256` cambia e si deve ripetere il preflight.

## Azione successiva

Creare su Google Drive, con una cella Colab senza credenziali e senza provider, solo
`data/rq2_v2_provenance/sonnet_q050_d_pilot_v1/release_v1.json`
in JSON canonico create-only e ottenerne SHA256; verificarlo con `read_frozen_release`. Non creare claim né invocare il modello nello stesso passo. Conservare il pin della release per la fase live successiva, con nuova attivazione esplicita. Mai toccare i file V1.

Il commit source-bound `bf2b0a0...` e gli hash elencati restano invariati nel branch scientifico.
