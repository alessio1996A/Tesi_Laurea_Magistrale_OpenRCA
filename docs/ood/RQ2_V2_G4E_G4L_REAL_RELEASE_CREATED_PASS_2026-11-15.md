# RQ2-V2: G4E/G4L release scientifica reale CREATED + READBACK PASS

**Data:** 15 novembre 2026. **Fonte:** output JSON/terminale Colab fornito dall'utente in chat. **Nessuna chiamata ai modelli** durante questa release.

## Risultato Colab dopo riavvio celle/runtime

```text
=== RQ2 V2 COLAB RECOVERY + G4E/G4L RELEASE ===
GIT SOURCE PIN E CLEAN: OK
RUNTIME SDK PINNED: OK
status=G4E_G4L_REAL_RELEASE_CREATED_READBACK_PASS_NO_API
RELEASE G4E/G4L: PASS — ZERO API LLM
CHECKOUT TEMPORANEO: RIMOSSO
```

**Dati restituiti dal processo reale:**

| Campo | Valore |
| --- | --- |
| source_commit | `f0b64a36b08c2ae5db424b544965db5362190377` |
| release_sha256 | `af1867e2539edbb42cf27ae92c602dfacca1c12968475235955fb1cf0ed2dac4` |
| approval_reference | `CHAT_2026-11-15_RQ2V2_OPTION_A_100USD_GEMINI_A0_D` |
| budget_usd | `100.00` |
| source_inventory_sha256 | `709afa6158a6244a7dccda2f72c928dd7a12855211083001f7949474e3bea103` |
| blueprint_sha256 | `54a9df1b243a1ccc3a522958379bbbd1b26738c8276a31baea054946976f9bea` |
| created_release_bytes | `5133` |
| release_relative_path | `data/rq2_v2_unified_scientific_v1/release_v1.json` |
| claims | `0` |
| records | `0` |
| orphan_claims | `0` |
| live_api_enabled | `false` |
| provider_requests_sent | `0` |
| ood_test_locked | `11` |

La release e' **stata materializzata realmente** su MyDrive ed e' stata controllata con readback `UnifiedScientificLedger.audit_restart`. Non ripetere la cella create-only: il namespace di release esiste e un secondo tentativo sarebbe correttamente bloccato; non cancellare la release.

**Evidenza distinta:** il pin sorgenti e il manifest SHA erano gia' stati creati e controllati dal reale checkout GT-free G4A/G4B/G4D; il messaggio dell'utente sui 33/33 test PyCharm opt-in/G4K/G4L passati resta un resoconto senza log dettagliato.

## Unico passo successivo: primo pilot reale

La precedente autorizzazione dell'utente a procedere e la successiva richiesta di **non ripetere approvazioni a ogni passaggio** si riferiscono alla preparazione e al primo pilot circoscritto. Non avviare batch ne' test OOD; budget operativo approvato USD 100.00 non e' hard cap provider.

**Stage unico:**
`rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:D` (prima run reale RQ2-V2, `gemini-3.5-flash-lite` dal piano, harness baseline A0). Restano 179 stage **non autorizzati automaticamente**.

**Protocollo operativo per prossima singola cella Colab:**
1. Nessuna creazione di release: readback SHA G4E gia' persistente e `audit_restart` con **0 claim, 0 record, 0 orfani**, altrimenti STOP.
2. Clone temporaneo clean al **commit auditato f0b64** (non HEAD documentale), runtime Python 3.13 e 6 SDK pinned in `/content/rq2_v2_pinned_sdk_py313`; dopo restart ripristinarli solo se assenti/drift, verificando versione + SHA noto con `assert_exact_runtime_snapshot()`.
3. Input split/manifest GT-free e `Market.zip` presenti, credenziale Google ottenuta tramite Secrets Colab senza stampa. PrefLIGHT G4H `preview_one_unified_stage` sul singolo ID, nessun OOD/GT, G4K e G4L disattivati durante il preflight.
4. Solo dopo il PASS di tutti i controlli, avviare **un processo Python separato** con `OPENRCA_RQ2_V2_ENABLE_PAID_SINGLE_STAGE=EXPLICIT_ONE_STAGE_ONLY_V1`, **NON** `OPENRCA_RQ2_V2_ENABLE_RELEASE_CREATE`, e chiamare **una sola volta** `run_one_claimed_unified_stage(..., confirm_paid_api=True, approved_stage_id=stage_id, approved_release_sha256=release_sha, external_approval_reference=approval_reference, expected_commit=f0b64)`.
5. Non ritentare il comando/cella se incontra errore: potrebbero essere avvenuti claim o richieste addebitate anche senza record. Stampare `run_status`, `record_sha256`, input/output token osservati, `usage_complete`, audit di claims/records/orphans. **Fermarsi dopo il singolo D** per analisi scientifica ed economica prima di ulteriori stage, con errori provider e risultati invalidi preservati.
6. Budget USD 100 per **l'intera campagna** e' soltanto una stop-policy operativa, NON un massimo di fatturazione garantito; 300s e' timeout *per request*, non un hard timeout per l'intero stage. Google API puo' avere un numero di richieste effettive diverso dagli invoke logici.

**Divieti:** non modificare release, sorgenti, prompt, piano D/C/K, rubrica K, dati storici, RQ1; non eseguire C/K automaticamente; nessun test degli 11 casi OOD. Nessun nuovo paper o trascrizione richiesti per il pilot.

## Continuita' conversazione

L'utente chiede che si segnali spontaneamente quando la chat diventa molto lunga e si fornisca un handoff sufficiente. I passaggi qui registrati preservano la distinzione tra **release effettivamente creata** e **pilot ancora 0/180**.
