# RQ2-V2 — First real Gemini A0 C: INVALID_OUTPUT, K BLOCKED_DEPENDENCY (15 novembre 2026)

Documento **solo evidenza**, aggiunto con commit esclusivamente documentale. Non modifica release, sorgenti, prompt, protocollo, dataset, ledger o risultati RQ1.

## Fonte e identità congelate

- Repo: `alessio1996A/Tesi_Laurea_Magistrale_OpenRCA`
- Source commit pinned/clean: `f0b64a36b08c2ae5db424b544965db5362190377`
- Scientific release SHA-256: `af1867e2539edbb42cf27ae92c602dfacca1c12968475235955fb1cf0ed2dac4`
- Stage D immutabile: `rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:D`
- D record SHA: `8628b902aaa4a5955d8527ba6151eb1dc4d004aa9722cc11302a0c20fca98fb1`
- Stage C: `rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:C`
- C package SHA preflight: `7a4889585306d24e44d70219065f2ce0af3fc47c199d733ba8bc906570fa8088`
- C prompt SHA preflight: `81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42`
- Evidenze C: 6 osservazioni, D usato read-only e non rieseguito.

## Preflight, singola chiamata reale, post-audit

Il primo tentativo di esecuzione della cella non ha consumato API: `SecretNotFoundError` poiché il Secret Colab era denominato `GEMINI_API_KEY` anziché `GOOGLE_API_KEY`. Errore prima del claim C. Dopo correzione del nome del Secret, è stata eseguita **una sola** chiamata logica pagata per C, senza retry.

Output comunicato dall'utente:
- `PRE_C_LIVE_GATE: PASS`: prima di C `claims=1, records=1, orphans=0`, package invariato, zero API.
- `status=RQ2_V2_REAL_GEMINI_A0_C_RESULT`, `run_status=INVALID_OUTPUT`.
- C record SHA: `51946d926aa2a5a0f9dd2ba997d8565116ef8158a2af44df5d0051d73ee3f4b1`.
- C meter: `observed_model_requests=1`, `input_tokens_observed=3151`, `output_tokens_observed=257`, `usage_complete=true`, `cost_estimate_usd_not_invoice=UNKNOWN`, `usd_hard_cap_guaranteed=false`.
- K è stato creato **come record bloccato**, `BLOCKED_DEPENDENCY`, senza alcun claim o richiesta API K.
- `POST_C_READONLY_AUDIT`: `claims=2, records=3, orphans=0`; D SHA invariato; C INVALID_OUTPUT; K BLOCKED_DEPENDENCY; `OOD_locked=11`.
- Le 180 posizioni logiche non sono tutte run pagate: dopo questo passo 3 record registrati (D, C e K bloccato), 2 stage effettivamente invocati, 177 senza record.
- D meter storico: input 30332, output 409, 7 invocazioni logiche. D+C combinati osservati: input 33483, output 666, totale 34149; **non** equivale a costo di fattura certo.

## Diagnosi tecnica dell'INVALID_OUTPUT: raw originale preservato

Il contenuto JSON del record C originale su Google Drive (percorso scientifico, solo lettura) è stato recuperato e verificato: `artifact.raw_response` ha lunghezza 883 caratteri; il campo `schema_version` contiene una nuova riga **non escapata** nel mezzo della stringa:

```text
"schema_version": "rq2_cause
_probe_v0"
```

Un tentativo di `json.loads` sul raw **originale** produce:

```text
JSONDecodeError: Invalid control character at: line 2 column 31 (char 32)
```

Il record stesso mantiene SHA `51946d926aa2a5a0f9dd2ba997d8565116ef8158a2af44df5d0051d73ee3f4b1`, coerente con il calcolo SHA256 del suo core JSON canonico. **Non riparare, alterare, sovrascrivere o rivalutare retroattivamente il record scientifico**.

Solo per diagnosi offline controfattuale, sostituire quella nuova riga in una COPIA in memoria produce JSON parsabile con gli otto campi previsti, `decision="abstain"`, `confidence="low"`, `predicted_fault_type=null`, `predicted_component=null`, `evidence_ids=["E001"]`, due alternative e due limitazioni. Questo **non** rende valido il risultato osservato; il motivo formale di invalidazione è sintattico prima del controllo della qualità dell'astensione.

## Interpretazione scientifica, limiti e decisione

Il contenuto testuale indica incertezza diagnostica, non nuova etichetta GT verificata: cita MRT max per checkoutservice-grpc 2713.75 ms e cartservice-grpc 747.46 ms, assenza di errori espliciti nelle query E003/E004 e fallimento di query metriche granulari E005/E006; la risposta avrebbe preferito astenersi. Queste sono **affermazioni del modello/estratto di evidenze**, non conferma di correttezza contro ground truth. L'astensione è prevista dal contratto C; l'output originale resta INVALID_OUTPUT per malformed JSON.

**Decisioni vincolanti:**
1. Non rilanciare C e non correggere la sua risposta.
2. Non eseguire K di questa stessa catena: il record K è irrevocabilmente `BLOCKED_DEPENDENCY` nel protocollo create-only.
3. Non riavviare D, non ricreare G4E/G4L, non cambiare sorgenti/protocollo frozen, né risultati RQ1.
4. Nessun accesso a ground truth o agli 11 OOD bloccati.
5. Se si prosegue con una nuova catena sperimentale, preparare un altro stage del piano attraverso preflight GT-free distinto; nessuna esecuzione API in questo documento.
6. Nessun paper o trascrizione del relatore necessario a questo gate; preparare successivamente valutazione scientifica e scrittura con scadenza tesi 1 dicembre 2026.
