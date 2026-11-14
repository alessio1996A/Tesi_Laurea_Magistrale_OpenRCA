# RQ2-V2 unificata — G4F: ledger scientifico create-only implementato, NO API

Data: 14 novembre 2026. Branch: `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.

## Risultati attestati dall'utente

**G4E PyCharm:** `Ran 18 tests in 0.651s; OK`. Sono 18 unit test sintetici sul contratto della futura release.

**G4C Colab reale, finalmente JSON completo:**
- `status=RQ2_V2_UNIFIED_REAL_GT_FREE_SOURCE_PREFLIGHT_OK_NO_API`
- `source_plan_preview_sha256=e6f797c4ca01ed422b80e928854469b9f8c7f7cc4215835bf91f9f7305425a00`
- `blueprint_sha256=a2874e9771eb50899afd15d55cecf239493f44077e16e937b5276f8a07e8fb61`
- `split_sha256=c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`
- `manifest_sha256=5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`
- `C_system_prompt_sha256=81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42`
- `K_system_prompt_sha256=0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71`
- 15 sorgenti, 5 harness, 3 modelli, 4 discovery, 11 OOD locked, D/C/K 60/60/60, 492 invocazioni grafo massime **candidate**, non cap HTTP; `model_requests_sent=0`, `scientific_artifacts_written=0`, `scientific_release_frozen=false`, `can_execute_api=false`.
- Commit Colab per questo preflight `33d5d8b28494d5bf41168d0a709854aa3134ea6a`; i nuovi commit G4F non erano presenti. Questi SHA non vanno scambiati per SHA del codice finale con ledger/dispatcher.

Full JSON riportato in
`docs/ood/RQ2_V2_UNIFIED_G4C_G4E_VERIFIED_SHA_REPORT_2026-11-14.md`.

## Nuovo codice G4F (da testare)

File:
- `src/evaluation/rq2_v2_unified_scientific_ledger.py`
- `src/tests/test_rq2_v2_unified_scientific_ledger_offline.py` (**22 metodi, non ancora eseguiti**).

Il primo è **il ledger scientifico vero**, distinto dagli store sintetici e V1/Sonnet pilot, ma **NON e' un dispatcher LLM**:
- obbligo di directory con `data/rq2_v2_unified_scientific_v1/release_v1.json` preesistente, hash release approvato esternamente, Git commit esatto e clean, sorgenti GT-free verificate e blueprint 180 stage identico;
- release passata al validatore rigoroso `validate_future_release`; il file di release **non viene creato** da questa classe;
- claim O_EXCL+fsync+readback prima dell'eventuale futura richiesta modello, su identità consentite solo discovery;
- record O_EXCL+fsync+readback dopo stage, parent SHA legati al claim e alla release, check full restart e nessun overwrite;
- stati `RECORDED_COMPLETE`, `INVALID_OUTPUT`, `PROVIDER_ERROR`, `BLOCKED_DEPENDENCY`; per errori prima di una richiesta HTTP è consentita ricevuta con zero attempt e costo `UNKNOWN`, senza inventare token fatturati;
- `stage_meter` obbligatorio su stage tentati, `usd_hard_cap_guaranteed=false`, no GT/scorer in alcun artefatto;
- D valida richiede output JSON task-aware e provenance dei `tool_call_id`; C/K validati sul bundle consentito, K insufficiente è valido come astensione e non regola funzionante;
- un solo writer OS per operazione, ma **FUSE/Drive lock non ancora provato**; test locale lock contestato non vale come test multiprocesso Drive;
- ogni claim irrisolto ferma **nuovi claim** fino a revisione manuale, senza retry automatici.
- metodi `claim_stage/record_stage` sono scritture concrete e **da NON puntare ai dati reali prima del freeze e della release approvata**; i test usano TemporaryDirectory + release/approval fixture **SYNTHETIC_APPROVAL_NOT_REAL**.

Questo modulo importa solo logica del progetto e standard library, **non** istanzia SDK, non spedisce richieste API, non legge Market.zip/GT, non esegue scorer, non apre la coorte test OOD.

## Finestra scientifica residua (importante)

Il ledger è una vera implementazione di salvataggio ma **non basta** per il pilot: manca ancora un solo dispatcher D/C/K reale con mock transport per l'intero percorso, accounting quota/spesa, provenienza delle richieste riuscite/fallite, trasporto retry/timeout verificato, prova di lock su filesystem Drive e policy di concorrenza/restart, blocco delle credenziali prima della release. Dopo aver aggiunto il dispatcher si dovrà congelare nuovamente la HEAD e rifare il source inventory includendo **il ledger e il dispatcher**. Nessun consenso a campagne pagate è stato ancora richiesto/fornito.

## Prossimo controllo PyCharm

Controllare che `git status --short` sia vuoto, quindi:

```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_scientific_ledger_offline.py" -v
```

**Attesi 22 metodi e `OK`, non ancora attestati.** Se fallisce, identificare il difetto e correggere sul branch tracciato senza aggirare il gate. Non usare API né iniziare l'Opzione B.
