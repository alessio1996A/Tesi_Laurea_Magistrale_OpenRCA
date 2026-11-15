# RQ2-V2 — G4E canonical release draft PASS, SHA awaiting external approval

**Data:** 15 novembre 2026. **Status registrato dall'utente:** `G4E_CANDIDATE_STRUCTURALLY_VALID_NOT_APPROVED`; terminale Colab `G4E DRAFT: VALIDATED IN MEMORY — 0 API` e `CHECKOUT TEMPORANEO: RIMOSSO`.

## Provenienza

- Git source SHA pinnato e verificato: `f0b64a36b08c2ae5db424b544965db5362190377` (checkout detached temporaneo pulito). Branch: `feature/rq2-v2-runtime-optin-final-source-2026-11-15`.
- Runtime pinned e fonte GT-free reali, non fixture; G4A/G4B/G4D/G4E autovalidati, senza autorizzazione esterna del digest.
- `source_file_count=30`, inventory SHA256 `709afa6158a6244a7dccda2f72c928dd7a12855211083001f7949474e3bea103`.
- Blueprint SHA256 `54a9df1b243a1ccc3a522958379bbbd1b26738c8276a31baea054946976f9bea`.
- `canonical_release_bytes=5133`.

## Manifesto scientifico G4E proposto, NON ancora approvato

- **Release candidate SHA-256 canonico completo:** `af1867e2539edbb42cf27ae92c602dfacca1c12968475235955fb1cf0ed2dac4`.
- **Approval reference PROPOSTO, NON ancora approvato:** `CHAT_2026-11-15_RQ2V2_OPTION_A_100USD_GEMINI_A0_D`.
- Budget operativo per l'intera Opzione A: **USD 100.00**, già approvato separatamente (non hard cap provider).
- 4 discovery incidents: `cloudbed-1_q032`, `cloudbed-1_q050`, `cloudbed-2_q026`, `cloudbed-2_q045`.
- 5 harness: `A0`, `A1`, `A1_8R`, `A1_8R_Planning`, `A1_PAVE`.
- 3 modelli: `gemini`, `sonnet`, `haiku`; 180 stage D/C/K totali.
- 11 incidenti di TEST OOD **LOCKED**; non eseguiti.
- Primo pilot già autorizzato proceduralmente dall'utente, **solo dopo la release approvata:** `rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:D`. Nessuna autorizzazione per gli altri 179 stage o per il test OOD.

## Condizioni e significato dello SHA

- `external_release_digest_approved=false`, `release_file_written=false`, `scientific_claims_written=0`, `model_requests_sent=0`, `can_execute_api=false`, `can_run_ood_test=false`.
- Lo SHA è l'hash canonico di un oggetto proposta costruito in memoria nel checkout Colab: **non è una firma crittografica del relatore o dell'utente**. Il validatore G4E è stato chiamato col digest calcolato localmente, perciò il suo esito PASS comprova coerenza strutturale, non autorizzazione esterna.
- Il JSON riportato non contiene i 30 SHA sorgenti *individuali* né i 5133 byte canonici, ma questi sono stati ricostruiti in memoria dal preflight sorgenti reali. Per la futura creazione create-only è obbligatorio **ricostruire esattamente lo stesso oggetto, con gli stessi 30 hash e approval reference, verificare il digest esternamente approvato, e fermarsi su ogni mismatch**. Non derivare il manifesto da un riassunto o ricostruirlo per approssimazione.
- Nessun file `release_v1.json` creato, nessun claim, nessuna API; le due attivazioni runtime restano assenti. Il writer e dispatcher non si accendono in un processo di preflight.

## Unica decisione necessaria successiva

Mostrare all'utente l'esatto SHA candidate, source commit, reference proposto, budget e scope e chiedere **approvazione esplicita del manifesto specifico e del riferimento proposto**. Non chiedere nuovamente budget né generico consenso al pilot, già ricevuti; non procedere automaticamente a creare la release prima dell'approvazione del SHA canonico.

Dopo approvazione: predisporre una **sola cella G4L create-only** nel runtime Colab isolato, checkout clean del medesimo source commit, digest approved pin esterno; nessun provider; fermarsi per audit dopo la scrittura. Poi, in ulteriore passo separato, pilot Gemini A0 D con gate per-stage, senza auto retry e dopo esame del consumo. RQ1 e RQ2 storici congelati; 11 OOD locked; niente riscrittura protocollo o ulteriori test preparatori non necessari.
