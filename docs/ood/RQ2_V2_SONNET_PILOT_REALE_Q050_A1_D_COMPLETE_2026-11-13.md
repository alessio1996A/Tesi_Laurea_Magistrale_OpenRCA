# RQ2 V2 — Primo pilot Sonnet autentico, risultato tecnico e limiti

**Data:** 13 novembre 2026. **Tipo di evidenza:** output Colab fornito dall'utente. Documento di continuità nel **branch documentale**, separato dal commit sperimentale.

## Identità congelata

- Repo: `alessio1996A/Tesi_Laurea_Magistrale_OpenRCA`
- Commit del codice verificato: `bf2b0a0a67977a65c79d47ada4b07e825eaf8dff`
- Protocollo: `rq2_v2_sonnet_q050_d_sourcebound_pilot_v1`
- Stage: `rq2_v2_sonnet_q050_d_sourcebound_pilot_v1:cloudbed-1_q050:sonnet:A1:D`
- Provider/model: Anthropic / `claude-sonnet-5-5`
- Modello, harness, stage: sonnet / A1 / D *soltanto*
- Source binding SHA256: `05c1c12072432e6ee7332802142dd709a6a9adfbf71845615274bbd927240f0b`
- Release SHA256: `c07e0aaa19b6cc1826e532c7da89e856c68e73975be84f572a727c09c7580813`
- Release era stata creata in modalità create-only, senza claim o API; preregistrazione osservata prima del pilot.

## Risultato della singola esecuzione reale, osservato dall'utente

```text
STATUS: SONNET_V2_REAL_PILOT_RECORDED
STAGE_STATUS: RECORDED_COMPLETE
STAGE_ID: rq2_v2_sonnet_q050_d_sourcebound_pilot_v1:cloudbed-1_q050:sonnet:A1:D
CLAIM_SHA256: ec058cb6f061f9c342b4a54a7aa037b1d8de7242ba6b91c17cf22976a66dc29e
RECORD_SHA256: 521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009
EVIDENCE_BUNDLE_SHA256: f63f1f0fd744497acc92814d8aabf80fb30cb08d8e5244ec62501d29052154d6
SAME_NAME_PARALLEL_CALLS: False
MODEL_REQUESTS: 7
INPUT_TOKENS: 136306
OUTPUT_TOKENS: 2849
USAGE_COMPLETE: True
ESTIMATED_COST_USD: 0.301102
CLAIM_EXISTS: True
RECORD_EXISTS: True
OOD_TEST_LOCKED: True
C_K_EXECUTED: False
```

Budget operativo USD 5.00 (non hard cap). Nessun retry automatico. La call ha raggiunto esattamente il limite di 7 invocazioni massimo, per cui è particolarmente importante non ripetere né aumentare il budget sullo stesso claim. Il costo è stimato, non una fattura o un cap garantito. Token totali 139155.

## Interpretazione scientifica

1. **Successo tecnico reale** del percorso D con provider, esecutore V2, claim create-only, ledger source-bound, readback, bundle delle evidenze e telemetria usage.
2. `RECORDED_COMPLETE` = integrità/contratto D, **non** accuratezza RCA.
3. `SAME_NAME_PARALLEL_CALLS=False`: l'esatto scenario `AMBIGUOUS_TOOL_RESULT` V1 (chiamate parallele omonime) **non è stato riprodotto**; perciò non asserire che sia stato provato su provider reale in questo caso, pur essendo stato verificato da test fake.
4. Nessuna C/K eseguita; nessuna K scientificamente frozen; nessuna evidenza di trasferimento delle regole alle 11 query OOD test (sempre LOCKED).
5. Questa run appartiene a un nuovo protocollo V2. **Non** aggregare statisticamente i suoi risultati come retry/repair V1 e non alterare i 39 record V1.
6. Nessun altro stage autorizzato dalla release singola, pur in presenza di budget provider ampio.

## Prossimo gate

Audit separato read-only dell'artefatto su Drive:
- ricalcolare SHA256 dei file canonici claim e record; controllare source/release pin e `audit_restart()`;
- estrarre solo contatori (non raw output, diagnosi, credenziali o GT) dei tool_call_id effettivamente abbinati e della telemetria;
- verificare consistenza numero di request, token, `RECORDED_COMPLETE`, `evidence_bundle_sha256`, presenza reale del record e assenza di nuovi stage;
- STOP se i digest non coincidono; nessuna ripetizione della run.

Successivamente progettare e congelare un **nuovo protocollo distinto** per D/C/K discovery, eventualmente in blocchi da 5–10 stadi **sequenziali**, ma solo con stage e dipendenze preregistrate, errore fail-closed, namespace nuovo, release e gate appropriati. Scegliere con il relatore quanto ampliare RQ2, dato che la scadenza tesi è il 1 dicembre 2026.

## Precedenti gate

- PyCharm 15/15 test mirati, poi 867/867 suite globale, 77.935s, OK.
- Colab `SONNET_V2_FINAL_PREFLIGHT_OK`; source hash `05c1c...`.
- Release `SONNET_V2_RELEASE_FROZEN_NO_API`; hash `c07e0...`.
- Pilot completo come sopra.

**Non riavviare questo pilot, né cambiare record/claim.**
