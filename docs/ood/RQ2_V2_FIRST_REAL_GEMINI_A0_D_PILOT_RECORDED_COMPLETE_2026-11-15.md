# RQ2-V2 — Primo pilot REALE Gemini A0 / D: RECORDED_COMPLETE

**Data:** 15 novembre 2026. **Fonte:** output JSON Colab e terminale effettivamente comunicati dall'utente; non è una validazione del ground truth né uno score ufficiale.

## Identità sperimentale congelata

- Git sorgenti: `f0b64a36b08c2ae5db424b544965db5362190377` (checkout clean PASS).
- Release G4E/G4L reale: `af1867e2539edbb42cf27ae92c602dfacca1c12968475235955fb1cf0ed2dac4` (read-only preflight iniziale PASS).
- Riferimento autorizzazione: `CHAT_2026-11-15_RQ2V2_OPTION_A_100USD_GEMINI_A0_D`.
- Protocollo: `rq2_v2_unified_five_harness_discovery_v0`.
- Stage ID esatto: `rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:D`.
- Modello/provider: `gemini-3.5-flash-lite` / Google; harness: `A0`; stage: diagnosi `D`.
- Budget campagna Opzione A: USD 100.00 **operativo**, NON hard cap di fatturazione; il pilot non approva altre chiamate in massa.

## Provenienza e risultato

**Console utente:**
```text
=== RQ2 V2 SINGLE REAL PILOT — GEMINI A0 D ===
SOURCE_COMMIT_PIN_CLEAN: OK
PINNED_RUNTIME: OK
status=PILOT_READONLY_PREFLIGHT_PASS
LIVE_SINGLE_STAGE: invoking exactly one claimed D (not one HTTP)
status=RQ2_V2_REAL_GEMINI_A0_D_PILOT_RECORDED
run_status=RECORDED_COMPLETE
PILOT: FIRST STAGE RECORDED — STOP FOR REVIEW
CHECKOUT TEMPORANEO: RIMOSSO
```

Il preflight leggeva una release esistente e attestava `ledger_claims=0`, `ledger_records=0`, `ledger_orphans=0`, `provider_requests_sent=0` prima del pilot; dopo il pilot il report indica **`ledger_claims=1`, `ledger_records=1`, `ledger_orphan_claims=0`**. Il claim è risolto da un record immutabile; non è opportuno ripetere lo stage e la procedura lo impedirebbe.

**Record immutabile SHA256:** `8628b902aaa4a5955d8527ba6151eb1dc4d004aa9722cc11302a0c20fca98fb1`.

**Usage OSSERVATO nel ledger** `rq2_v2_unified_stage_meter_v0`:
- `observed_model_requests=7` (conteggio logico osservato, NON numero HTTP garantito).
- `input_tokens_observed=30332`; `output_tokens_observed=409`; `usage_complete=true`.
- `cost_estimate_usd_not_invoice=UNKNOWN`. Non inferire costo fatturato dal campo UNKNOWN; eventualmente stima illustrativa distinta con tariffe verificate e caveat.
- `usd_hard_cap_guaranteed=false`, `automated_retry=false`.
- `downstream_blocked=[]`, `other_stages_executed=false`, `ood_test_executed=false`.

**Estratto della diagnosi osservata (NON GT validata):**
```json
{"1":{"root cause occurrence datetime":"2022-03-20 15:00:00","root cause component":"cartservice-2","root cause reason":"high latency in cartservice-grpc affecting downstream checkoutservice-grpc and frontend-http"}}
```
La risposta è stata accettata strutturalmente dal contratto D: `RECORDED_COMPLETE` NON significa root cause corretta. Nessun accesso a GT, nessuno scorer eseguito, nessuna valutazione indipendente della correttezza. Non trattare questa diagnosi come una nuova regola K, perché lo stage K non è ancora stato eseguito.

## Stato scientifico dopo il pilot

- Opzione A: **1 stage D realmente registrato su 180 pianificati**; 179 non ancora eseguiti. Due stage C/K dello stesso caso/modello/harness non sono ancora eseguiti; il D è prerequisito per C, e C per K.
- Tutti gli 11 incidenti OOD Opzione B **LOCKED**.
- RQ1 e RQ2 V1 precedenti invariati, nessun riavvio delle campagne frozen, nessuna fusione con storico V1.
- **Stop operativo** rispettato dopo il primo pilot; nessun batch e nessuna ripetizione automatica. Non ripetere cella pilot D: il record e il claim esistono.
- Verifica del ledger e uso token dopo la prima chiamata avvenuta nel processo; non confondere `usage_complete=true` (conteggi registrati) con prova di correttezza o costo effettivamente addebitato.
- Importanti 7 chiamate logiche nel D A0: compatibili con budget massimo 6 tool round + una finalizzazione, ma dai soli conteggi non dedurre traiettoria/tool rounds effettivi né numero HTTP fatturato.

## Prossimo passo di ricerca, dopo passaggio a nuova chat

Lo step scientificamente corretto è valutare la **fase C** del medesimo braccio `cloudbed-1_q032:gemini:A0`, riutilizzando come input **soltanto il record D immutabile** del ledger e i dati GT-free; se C valida, la futura fase K proporrà conoscenza candidata, non una regola già generalizzata. Non lanciare C o K in automatico come effetto collaterale del pilot D e non sbloccare OOD. Il consenso precedente era circoscritto al solo D. L'utente preferisce evitare richieste di approvazione ripetitive sul budget e sul lavoro tecnico; per eventuale nuova chiamata a pagamento di stage C/K occorre distinguere un nuovo perimetro rispetto a quello già eseguito, senza fargli ripetere decisioni economiche già prese.

Prima di procedere leggere il ledger esistente su MyDrive, verificare release e claim/record D, `audit_restart` senza orfani, e pin `f0b64...`. Il preflight dello stage C userà `preview_one_unified_stage(... stage_id=...:C)`. Non modificare i source per testare C; il dispatcher già supporta C/K tool-free. Non scrivere nell'handoff che C/K sono stati autorizzati o eseguiti.

**Continuity:** la chat corrente è lunga; avvisare l'utente di passare a nuova chat dopo aver aggiornato il documento handoff. Nessun paper o trascrizione del professore è necessario per questo prossimo passaggio.
