# RQ2-V2 unificata — G4H: due errori SHA in fixture, fix mirato
**Data:** 15 novembre 2026. **Branch:** `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.

## Output effettivo dell'utente (PyCharm)
```text
G4H: Ran 19 tests in 4.967s
FAILED (errors=2)
G4F: Ran 22 tests in 20.972s
OK
G4G: Ran 17 tests in 19.580s
OK
```

G4H: i 17 test diversi dalla preparazione positiva di C e K passano. Gli unici due errori sono `test_c_preview_uses_saved_d_evidence_and_frozen_prompt` e `test_k_preview_requires_valid_saved_d_and_c`, entrambi `UnifiedStagePreviewBlocked("Frozen C/K prompt SHA drift")` nel modulo `rq2_v2_unified_live_stage_preflight.py`. **NON è un crash del ledger o dei grafi**: G4F/G4G rimangono PASS anche dopo il cambio di semantica token vs prezzo sconosciuto.

## Diagnosi verificata a sorgente
La fixture `source_fixture()`, condivisa coi test G4E, imposta gli hash `C_system_prompt_sha256` e `K_system_prompt_sha256` entrambi a `FAKE_SHA`, SHA generico di `b"synthetic fixture, never API"`. Il G4H costruisce una release fake partendo da quella fixture, quindi registra come 'frozen' due impronte che **non** corrispondono ai prompt veri in `evaluation.rq2_probe_adapter.CAUSE_SYSTEM` / `RULE_SYSTEM`. La funzione `preview_one_unified_stage` confronta correttamente il prompt realmente costruito contro il pin della release e rifiuta C/K. Il gate di sicurezza ha funzionato. Non alterare quel gate né i prompt congelati.

## Correzione su GitHub, **solo fixture G4H**
Commit: `bbdfcff3d1628db409072835cc13440f195d2d1f`.

File modificato: `src/tests/test_rq2_v2_unified_live_stage_preflight_offline.py`.
Nella `setUp()`, subito dopo `source = source_fixture()`, prima di calcolare il blueprint e creare la release fake:
```python
source["C_system_prompt_sha256"] = hashlib.sha256(
    CAUSE_SYSTEM.encode("utf-8")
).hexdigest()
source["K_system_prompt_sha256"] = hashlib.sha256(
    RULE_SYSTEM.encode("utf-8")
).hexdigest()
```

Questa modifica è **limitata alla fixture G4H**: non cambia `source_fixture()` condivisa dagli altri test, non cambia i contratti/validatore, non modifica il codice G4H produttivo, non cambia SHA reali da Colab, ledger G4F, orchestratore G4G o RQ1. Aggiunto un **ventesimo test negativo**, `test_actual_prompt_drift_still_fails_closed_for_both_stages`, che altera intenzionalmente il prompt visto dal gate C o K e verifica che l'eccezione di SHA continui a bloccare lo stage senza creare claim.

## Prossimo controllo in PyCharm
```powershell
git status --short
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_live_stage_preflight_offline.py" -v
```
**Attesi 20 test e OK, NON ancora verificati dall'utente.** Non è indispensabile ricorrere a Colab o provider per questo fix: G4F 22/22 e G4G 17/17 erano già stati eseguiti dall'utente su sorgenti invariati nei rispettivi moduli. Se fallisce, leggere il nuovo traceback prima di qualunque modifica.

## Stato
Nessuna API reale, nessuna nuova campagna scientifica Opzione A, nessuna firma di release nuova; 11 casi OOD e Opzione B bloccati. G4I resta il passo successivo dopo PASS G4H.
