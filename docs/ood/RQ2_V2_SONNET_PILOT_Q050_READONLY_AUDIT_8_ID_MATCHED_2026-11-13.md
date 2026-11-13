# RQ2 V2 — Audit read-only dopo il primo pilot Sonnet, provenance 8/8

**Data:** 2026-11-13. **Stato:** `PILOT_TECHNICAL_AUDIT_CLOSED` / `NO_NEW_STAGE_AUTHORIZED` / `OOD_TEST_LOCKED`. Evidenze riportate dall'utente da Google Colab. Report su branch **documentale** separato dal commit scientifico.

## Provenance e integrità osservate

```text
STATUS: SONNET_V2_REAL_PILOT_READONLY_AUDIT_OK
STAGE_STATUS: RECORDED_COMPLETE
TOOL_CALLS: 8
TOOL_RESULTS: 8
UNIQUE_TOOL_CALL_IDS: 8
TOOL_IDS_PAIRED: True
SAME_NAME_PARALLEL: False
MODEL_REQUESTS: 7
INPUT_TOKENS: 136306
OUTPUT_TOKENS: 2849
ESTIMATED_COST_USD: 0.301102
RECORD_SHA256: 521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009
API_CALLS_DURING_AUDIT: 0
FILES_WRITTEN_DURING_AUDIT: FALSE
OOD_TEST: LOCKED
```

- Case: `cloudbed-1_q050`; arm: Sonnet 5.5 / A1 / D; 1 nuova D scientifica V2, **non** un retry V1.
- HEAD: `bf2b0a0a67977a65c79d47ada4b07e825eaf8dff`; source binding SHA256 `05c1c12072432e6ee7332802142dd709a6a9adfbf71845615274bbd927240f0b`.
- Release SHA256 `c07e0aaa19b6cc1826e532c7da89e856c68e73975be84f572a727c09c7580813`.
- Claim SHA256 `ec058cb6f061f9c342b4a54a7aa037b1d8de7242ba6b91c17cf22976a66dc29e`.
- Record SHA256 `521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009`.
- Bundle SHA256 `f63f1f0fd744497acc92814d8aabf80fb30cb08d8e5244ec62501d29052154d6`.
- 8 tool call e 8 tool result, 8 ID nativi distinti, matching 1:1, con `audit_restart` e `_verify_record` che hanno superato il controllo.
- 7 richieste LLM osservate, input 136306, output 2849, 139155 totali; usage completo, costo stimato USD 0.301102, non fattura. Nessuna chiamata durante l'audit.
- `SAME_NAME_PARALLEL=False`: **NON** è stata riprodotta l'esatta ambiguità V1 delle chiamate omonime parallele; non presentare l'audit come prova live di quel sotto-caso.
- `RECORDED_COMPLETE` misura consistenza del contratto e artefatti: NON certifica la correttezza RCA.
- C/K non sono state eseguite, nessuna K frozen, nessuna dimostrazione di generalizzazione alle 11 OOD test.
- Claim e record di questa D sono conservati create-only. **Non ritentare o sovrascrivere** il pilot, né modificare i 39 record V1.

## Decisione proposta per il prossimo gate, non ancora autorizzata

Prima di lanciare altri modelli fare un audit **offline GT-free** della *preparabilità* del pacchetto C dal record D reale appena congelato: leggere unicamente la instruction originale del manifest GT-free e confrontarne SHA256, rifare bundle delle 8 tool evidenze e verificarne SHA, applicare `prepare_cause_probe` in modo read-only e verificare dimensione/campi e pacchetto hash, **senza stampare prompt o dati grezzi**. Se l'adapter supera il proprio limite (45k caratteri), fermarsi e registrare il limite; non troncare a posteriori le evidenze.

Solo dopo verificare fattibilità di una futura campagna su *nuovo protocollo* C→K e altri discovery arm (possibili blocchi sequenziali da 5, ma non autorizzati dalla release D). Nuovi stage/claims dipendono dal record D originale; C e K devono avere release, hash/source pin e store indipendenti, parse fail-closed; K parte solo dopo C valida. Gli 11 OOD test restano `LOCKED` fino a separato freeze e review scientifica.

L'ampia disponibilità economica comunicata dall'utente non sostituisce i gate metodologici; la data di consegna è 1 dicembre 2026 e RQ1 è già congelata.
