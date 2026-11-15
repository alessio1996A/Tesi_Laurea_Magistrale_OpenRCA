# HANDOFF OPERATIVO — RQ2-V3 POST-FREEZE, 15 novembre 2026

> **Stato corrente: RELEASE SCIENTIFICA V3 CONGELATA E VERIFICATA SU COLAB; ZERO API LLM V3; NESSUN PILOT AUTORIZZATO.**
> Questo documento è il nuovo punto di continuità. Il precedente `HANDOFF_RQ2_V3_GT_FREE_EQUAL_COMPARISON_PRE_RELEASE_2026-11-15.md` rimane come registro storico *pre-freeze*. Non reinterpretarne lo stato «NO-GO» come stato corrente: le condizioni tecniche di release sono state verificate successivamente. I limiti di attestazione sincrona/multi-VM/USD permangono.

## 1. Contesto, urgenza e regole

- Tesi magistrale Ingegneria Informatica, Università di Catania: **Harness Engineering per LLM applicato alla Root Cause Analysis (Microsoft OpenRCA)**.
- **Consegna corretta dall'utente: 5 dicembre 2026.** Priorità esplicita: **terminare RQ2 e portare al professore metodo, risultati e limiti per confronto**, prima di iniziare la stesura dei capitoli. I capitoli saranno proposti e concordati con il relatore dopo la valutazione RQ2. Non insistere sulla scrittura anticipata e non ripetere test/gate già validati.
- Repository: `alessio1996A/Tesi_Laurea_Magistrale_OpenRCA`; branch di lavoro `feature/rq2-v3-gtfree-equal-comparison-design-2026-11-15`.
- **SOURCE CODE SCIENTIFICAMENTE CONGELATO**: commit `8f8b39e480db1296de155068c001d17ae05ac6ad`. Tutti i successivi commit *solo documentali* non sostituiscono il pin di codice, non possono essere trattati come release e non vanno usati per `expected_commit` nei gate.
- Colab codice: `/content/Tesi_OpenRCA`; SDK isolati: `/content/rq2_v2_pinned_sdk_py313`; dataset root montato: `/content/drive/MyDrive/Tesi_OpenRCA`.
- RQ1 ed RQ2-V2 **NON modificare**; non migrare output V2 a V3; niente retry, niente GT/scorer/Market come input in RQ2-V3. Claim-first, `O_EXCL`, readback, parent SHA, audit orphan, una sola sessione writer e **uno stage per volta**.
- Undici casi OOD/test sigillati; non utilizzarli per pilot/discovery. Human-in-the-loop non richiesto dal relatore, solo discussione finale.
- Solo dopo esplicito consenso separato per **singolo stage**, **modello**, **commit codice**, **release SHA**, **budget USD operativo** si possono valutare chiamate reali. Il freeze autorizzato **NON autorizza API**; NON impostare `OPENRCA_RQ2_V3_ENABLE_PAID_SINGLE_STAGE`.
- Avvisare l'utente quando cambiare chat; aggiornare prima un handoff GitHub e fornire il testo pronto da incollare. Richiedere paper o trascrizioni del relatore solo se indispensabili e spiegando perché; non servono per il prossimo passo tecnico.

## 2. Metodologia e risultati precedenti intatti

- RQ1 Evaluation20: 20 incidenti × 5 harness × 3 modelli = 300 tentativi, 295 complete e 5 errori provider Gemini. Score ufficiale Microsoft già congelato. Sonnet A0 mean=0.1165, strict 1/20; Sonnet A1_PAVE mean=0.5040, strict 8/20. Non confondere il vantaggio di accuracy/harness con una prova di trasferimento della conoscenza.
- RQ2-V2 precedente: commit `f0b64a36b08c2ae5db424b544965db5362190377`, release SHA `af1867e2539edbb42cf27ae92c602dfacca1c12968475235955fb1cf0ed2dac4`. Pilot `cloudbed-1_q032:gemini:A0`: D `RECORDED_COMPLETE`, C `INVALID_OUTPUT`, K `BLOCKED_DEPENDENCY`. Rimane storico: non ripetere o riclassificare.
- Motivazione V3: estrazione testo finale omogenea D/C/K senza separatori fra blocchi di testo, senza riparazioni JSON, escludendo thinking/tool-use e conservando provenance; stesso disegno sperimentale, modelli, budget di esecuzione e coorte.

## 3. Identità scientifica congelata (da trascrivere senza modifiche)

| Identità | Valore |
|---|---|
| Code commit | `8f8b39e480db1296de155068c001d17ae05ac6ad` |
| Protocollo | `rq2_v3_unified_equal_ck_extraction_discovery_v0` |
| Namespace | `data/rq2_v3_unified_scientific_v1` |
| Release file su Drive | `data/rq2_v3_unified_scientific_v1/release_v1.json` rispetto alla root |
| Release SHA256 | `dae141c0dd7231cc172ef891299367df85adf2618be0b0c7882336ee585b1c04` |
| Inventory GT-free SHA256 | `e13bc96871a39ccaae4f25fd3f4ba99b263a40ced08a48d29d4c52a0d9c1be06` |
| Runtime attestation SHA256 | `61909d3fea3010968e9bf2485008e3b8477af960ff18e5e88f216f2b579db204` |
| Release schema | `rq2_v3_scientific_release_v1`, 30 campi |
| Canonical JSON | 6647 byte |
| Cohort discovery | 4 incidenti, 5 harness, 3 modelli |
| Stage logici | 180 = 60 D + 60 C + 60 K |
| OOD/test locked | 11 |

Harness `A0`, `A1`, `A1_8R`, `A1_8R_Planning`, `A1_PAVE`; provider `gemini`, `sonnet`, `haiku`. **180 stage logici NON equivalgono a 180 invii HTTP**: D può avere più chiamate; K può essere bloccato da D/C.

## 4. Evidenze effettive (15/11/2026)

1. Il codice candidato è stato modificato SOLO nei quattro file V3: `src/evaluation/rq2_v3_scientific_live_stage_preflight.py`, `rq2_v3_scientific_source_release_gate.py`, `src/tests/test_rq2_v3_scientific_live_stage_preflight_offline.py`, `src/tests/test_rq2_v3_scientific_source_release_gate_offline.py`. Test PyCharm mirati sui due gate modificati: **13/13 + 13/13 PASS**. Restano validi i 147 test V3 mirati *pre-fix* segnalati nel precedente handoff; non sommarli come suite globale unica e non affermare che la suite globale sia verde.
2. In Colab al code commit sopra, runtime snapshot separato: 6/6 versioni richieste e 4/4 SHA di file sorgente SDK PASS, factory RQ2 PASS. Trasporto sincrono mock HTTP 429: un invio per provider × stile CK-tool-free/D-bound-tools; timeout read su loopback a ~0,3s, analoghi quattro percorsi; tutti con credenziali fittizie e nessuna API esterna. Lock e O_EXCL testati su scratch nella stessa sessione/runtime (8 processi, 1 creatore esclusivo), NON cross-VM.
3. L'utente ha riportato con `RETURN_CODE: 0` il preflight V3 `V3_RUNTIME_ATTESTATION_PASS_NO_RELEASE`, inventory e attestation SHA sopra; `can_execute_api=false`, 0 API reali.
4. L'utente ha riportato con `RETURN_CODE: 0` `V3_RELEASE_CANDIDATE_READONLY_PASS`: 30 campi, 6647 byte, release SHA approvato sopra, file ancora assente. Ha poi **autorizzato esplicitamente SOLO il freeze create-only**, nessuna API/pilot.
5. Esecuzione freeze Colab **riportata dall'utente, con output completo**:
   - SOURCE PIN PASS; INVENTORY GT-FREE PASS; RUNTIME PASS; RELEASE CANONICAL SHA PASS;
   - `RELEASE WRITE: O_EXCL COMPLETED`; `READBACK: PASS`;
   - `SOURCE RELEASE GATE: PASS` (`V3_SOURCE_BOUND_RELEASE_VERIFIED`);
   - `LEDGER AUDIT: PASS` (`V3_SCIENTIFIC_LEDGER_READBACK_AUDITED`);
   - stato `V3_SCIENTIFIC_RELEASE_FROZEN_VERIFIED_NO_API`, `RETURN_CODE: 0`;
   - `claims=0`, `records=0`, `orphans=0`, `automatic_retry_allowed=false`, `release_frozen=true`, `can_execute_api=false`, `api_budget_approved=false`, `real_llm_calls_this_cell=0`.
6. **Non rieseguire la cella di freeze** (create-only); non cancellare né sovrascrivere il file esistente. Il registro Drive non è riprodotto in GitHub, perciò non inventare evidenze indipendenti oltre agli output Colab comunicati.

## 5. Limiti delle evidenze: conservarli esplicitamente

- `sdk_retries_disabled_verified=true` nel receipt riguarda soltanto i percorsi **sincroni osservati** sotto HTTP 429 fake; NON prova tutte le condizioni d'errore, i percorsi asincroni/streaming o un hard cap globale di richieste.
- `per_request_timeout_verified=true` riguarda timeout HTTP di lettura su loopback. **Nessuna garanzia sul timeout dell'intero stage D**.
- `single_writer_drive_verified=true` riguarda competizione nello **stesso runtime Colab**; sessioni differenti/VM diverse NON sono coperte. Mantenere una sola sessione writer e stage seriale.
- `usage_meter_fail_closed=true` significa che usage/costo incompleto resta `UNKNOWN`, non zero USD certificato. `usd_hard_cap_guaranteed=false`.
- Freeze + source SHA sono **prove di integrità, non firme di approvazione economica**.

## 6. Prossimo passo autorizzabile, NON ancora autorizzato

- **Nessuna nuova verifica generica e nessun retry/freeze**. Conservare il checkout Colab **detached al code commit**; non effettuare pull sul branch documentale per il pilot: l'HEAD diventerebbe diverso dal commit congelato e il gate bloccherebbe.
- Preparare (SOLO read-only) il piano per **un unico stage V3 D di discovery**, con esatto `stage_id` verificato sul piano corrente, modello/provider/variante, prompt invariati, stima del budget operativo da listini correnti e rischio delle chiamate multiple D. Non assumere che `0.10 USD` sia un hard cap.
- Presentare all'utente stage, model ID, source code commit, release SHA, budget USD e conseguenze di orphan/error. **Richiedere una nuova, separata autorizzazione esplicita** prima di costruire SDK/claim/performare richieste a pagamento.
- Solo dopo consenso: una sessione writer, un singolo stage, claim-before-request, no retry, record/create-only e audit di integrità; se provider error, output invalido, orphan o ambiguità: STOP/review.
- Valutare campagna ulteriormente SOLO dopo il pilot e un'eventuale approvazione separata. Niente 11 OOD/test prima della decisione metodologica dedicata.
- **Priorità concordata dall'utente: completare RQ2 prima della stesura.** Completare pilot controllato, poi coorte discovery ed analisi delle proposte K con relativi fallimenti, costi e provenienze; separare qualità del candidato dal dimostrato trasferimento della conoscenza e tenere gli 11 OOD protetti fino a protocollo dedicato. Preparare materiale di risultati per il colloquio con il professore e concordare con lui i capitoli. **Deadline confermata dall'utente: 5 dicembre 2026**.
- Alla fine, su branch separato e senza alterare artifact/release: refactoring mirato, commenti italiani, prudente rimozione file superflui, grafici accuratezza/token, stesura finale.

## 6bis. Pilot V3 D preflight read-only: PASS, 0 API

- Dopo il freeze, l'utente ha eseguito in Colab e riportato `RETURN_CODE: 0`, `status: V3_D_PILOT_READONLY_PREFLIGHT_PASS`.
- Stage esatto: `rq2_v3_unified_equal_ck_extraction_discovery_v0:cloudbed-1_q032:gemini:A0:D`; modello `gemini-3.5-flash-lite`; harness `A0`; `max_tool_rounds_D=6`; source `8f8b39e480db1296de155068c001d17ae05ac6ad`; release `dae141c0dd7231cc172ef891299367df85adf2618be0b0c7882336ee585b1c04`.
- Ledger ancora `claims=records=orphans=0`, `can_execute_api=false`, `real_llm_calls=0`. **NON è ancora un pilot eseguito**.
- Verificati sul sito ufficiale Google AI i prezzi Standard Gemini 3.5 Flash-Lite `$0.30/M input` e `$2.50/M output` (15/11/2026; https://ai.google.dev/gemini-api/docs/pricing/). Budget operativo **proposto** per uno stage D: **USD 0.10, NON approvato e NON hard cap**. Serve esatta autorizzazione dell'utente prima di creare claim o chiamare SDK.
- Obiettivo confermato: terminare RQ2, analizzare i cinque harness e tre modelli nella discovery, verificare eventualmente trasferimento sul set OOD sigillato secondo protocollo separato e presentare i risultati al relatore prima dei capitoli. Consegna tesi **5 dicembre 2026**.

## 7. Messaggio consigliato per eventuale nuova chat

> Riprendi la mia tesi OpenRCA. Leggi integralmente su GitHub `docs/ood/HANDOFF_RQ2_V3_POST_FREEZE_2026-11-15.md` nel repository `alessio1996A/Tesi_Laurea_Magistrale_OpenRCA`. V3 ha completato il freeze scientifico *create-only* in Colab: code commit **8f8b39e480db1296de155068c001d17ae05ac6ad**, release SHA **dae141c0dd7231cc172ef891299367df85adf2618be0b0c7882336ee585b1c04**, inventory SHA **e13bc96871a39ccaae4f25fd3f4ba99b263a40ced08a48d29d4c52a0d9c1be06**, runtime attestation SHA **61909d3fea3010968e9bf2485008e3b8477af960ff18e5e88f216f2b579db204**. Gli 11 OOD rimangono locked, 180 stage logici, claims=records=orphans=0, 0 API V3. NON ripetere freeze o test già PASS; non modificare RQ1/RQ2-V2 o il code pin. Prepara soltanto il piano per **un singolo pilot V3 D** con stage/model/commit/release/budget da farmi approvare separatamente. Consegna tesi **5/12/2026**: prima terminare RQ2 e presentarla al professore, poi concordare i capitoli. Non forzare la scrittura adesso; chiedere paper/trascrizioni solo se davvero necessari.
