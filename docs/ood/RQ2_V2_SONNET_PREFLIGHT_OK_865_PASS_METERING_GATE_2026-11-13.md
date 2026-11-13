# RQ2 V2 — Sonnet: 865/865 PASS, Colab source preflight PASS, gate metering da rieseguire

**Data:** 13 novembre 2026  
**Branch verificato dall'utente:** `feature/rq2-v2-sonnet-sourcebound-pilot-2026-11-13`  
**Commit verificato su Drive/Colab:** `31217e77bc7795a746fd23c6e47afd5ac75fd0eb`  
**Branch nuovo di hardening:** `feature/rq2-v2-sonnet-metering-audit-2026-11-13`  
**Stato:** `GO_OFFLINE_VERIFIED_PREVIOUS_COMMIT`, `METERING_TEST_PENDING`, `NO_LIVE_API_RELEASE`, `OOD_LOCKED`.

## Evidenza locale PyCharm fornita dall'utente

- `Ran 13 tests in 0.583s / OK`: gate mirato del pilot source-bound.
- `Ran 865 tests in 78.499s / OK`: regressione completa.
- I test verificano il software offline; **non** sono 865 diagnosi o 865 run provider.

## Evidenza Colab reale — PRE-FLIGHT, zero API

L'utente ha eseguito una sola cella Colab read-only, con output:

```text
GIT_HEAD: 31217e77bc7795a746fd23c6e47afd5ac75fd0eb
STATUS: SONNET_V2_SOURCE_PREFLIGHT_OK
STAGE_ID: rq2_v2_sonnet_q050_d_sourcebound_pilot_v1:cloudbed-1_q050:sonnet:A1:D
SOURCE_BINDING_SHA256: e3eba68226b4efcca0c16025f10f2f7dcaa4f14dcce5b615ce36ca6835f60c73
SPLIT_SHA256: c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724
MANIFEST_SHA256: 5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13
V2_GRAPH_SHA256: c630ac3bef1c25465783e68854ad11cf24935b5a98dce9244308523c86f93df3
API_CALLS: 0
V1_WRITES: 0
RELEASE_CREATED: FALSE
CLAIM_CREATED: FALSE
OOD_TEST: LOCKED
```

Il preflight verifica la coerenza snapshot, ma **NON** verifica l'effettivo HTTP, le
credenziali o la disponibilita del modello e non autorizza una run.
La cartella dati su Drive resta separata dal checkout Git in `/content`.
Non ripetere l'audit Gemini V1 gia' effettuato.

## Hardening additivo sul nuovo branch (non ancora testato localmente)

Il driver V2 ora aggiunge, prima di `record_stage`, una ricevuta
`diagnostic_run.metrics.rq2_v2_execution_meter` con:
numero di richieste provider *tentate* osservate dal meter,
input/output token osservati, flag `token_usage_complete`,
stima costo USD non fattura, soglia operativa approvata,
indicatore soglia raggiunta e `usd_hard_cap_guaranteed=false`.

Questi dati finiscono nel record source-bound create-only, autenticato con
SHA256 e readback. Rimangono visibili anche se la risposta HTTP ha
metadati usage incompleti o la soglia operativa arresta una richiesta
successiva. Le richieste senza risposta potrebbero costare ma non avere
usage affidabile: NON dichiarare esatto il costo stimato.

Sono stati aggiunti **2 test offline** per errori e soglia operativa;
un test esistente ora verifica che il meter sia realmente persistito
nel record. Nuovo gate PyCharm previsto: **15 test mirati** e **867 totali**
(se la discovery non cambia). Non attribuire PASS prima dell'output utente.

Nessuna modifica a `src/evaluation/experiment_runner.py`,
`src/agent/graph_engine.py`, al protocollo V1/RQ1, agli artefatti
congelati, allo store sintetico V2 o al test OOD.

## Release, spesa e scelte scientifiche

Modello `claude-sonnet-5-5`, una sola D reale
`cloudbed-1_q050/sonnet/A1/D`, massimo 6 tool round,
7 invocazioni provider possibili, timeout 300 secondi *per HTTP request*,
zero retry stage, niente C/K.
Prezzi base verificati nelle specifiche ufficiali Sonnet 5.5:
USD 2/milione token input e USD 10/milione token output.
Caching e altri dettagli di fatturazione possono incidere;
l'operational stop **non e' un hard cap USD**.

**Non** creare release approvata, claim o chiamate provider finche':
1. i nuovi test PyCharm non sono superati;
2. il nuovo commit finale Git e il source binding reale non sono ricontrollati
   con preflight Colab read-only;
3. e' eseguita la revisione finale di policy, fonte e budget;
4. l'utente non autorizza esplicitamente la singola spesa API.

Il vecchio `SOURCE_BINDING_SHA256=e3eba...` e il vecchio HEAD sono validi
**solo per il commit preflight precedente**; il nuovo branch crea una
nuova identita di sorgente e richiedera nuovi hash. Gli hash del CSV e
del grafo V2 restano invariati se i relativi byte non cambiano.

Risultati V1 e 11 query OOD test sempre LOCKED.
