# RQ2-V2 unificata — G4C e G4D: risultati osservati in Colab e PyCharm

Data: 14 novembre 2026. Branch: `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.

## Output fornito dall'utente

**G4C Colab — riesecuzione della cella read-only:**
```text
CompletedProcess(args=['/usr/bin/python3', '-B', '-c', '... codice con assert source/blueprint e print(report) ...'], returncode=0)
```
Gli assert inclusi nel codice del subprocess comprendono:
- `source.status == OFFLINE_SOURCE_BOUND_NO_RELEASE_NO_API`;
- `source.gt_free_source_verified` e `source.frozen_rq1_source_identity_verified` veri;
- `source.logical_stages==180`;
- `plan.logical_stage_count==180`, tetto teorico di invocazioni graph `492`;
- blocchi `can_execute_api=False`, `can_run_ood_test=False`,
  `ground_truth_read=False`, `scientific_release_frozen=False`,
  `can_write_scientific_claims=False`.

L'utente in precedenza aveva riportato il commit effettivo del checkout
`33d5d8b28494d5bf41168d0a709854aa3134ea6a` e la conclusione
`G4 REAL GT-FREE SOURCE PREFLIGHT: TERMINATO (0 API)`.

Interpretazione rigorosa: **G4C esecuzione/asserzioni: PASS**, in quanto
`subprocess.run(... check=True)` non segnala errori e il processo ha
`returncode=0`. Tuttavia il JSON stampato dallo script non è stato
incollato dall'utente, quindi i **valori numerici concreti degli SHA**
(`source_plan_preview_sha256`, `blueprint_sha256`, prompt C/K) non
sono materialmente raccolti nella conversazione e **non devono essere
inventati**. Esiste già evidenza storica separata sullo split/manifest
del 12/11, ma è distinta dal JSON G4C.

Per acquisire un report leggibile usando le variabili `code`, `REPO`,
`env` già definite nella stessa sessione Colab:
```python
import json, subprocess, sys
result = subprocess.run(
    [sys.executable, "-B", "-c", code],
    cwd=REPO, env=env, text=True,
    capture_output=True, check=True,
)
report = json.loads(result.stdout)
print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
```
Questa cella ripete **solo la lettura GT-free**, nessuna API, nessuna
scrittura scientifica o Market.zip.

**G4D PyCharm:**
```text
Ran 19 tests in 0.485s
OK (skipped=2)
```
Interpretazione: 19 metodi unittest contati, **17 eseguiti e superati,
2 saltati** (test dei symlink `test_scientific_namespace_symlink_is_rejected`
e `test_historical_symlink_is_rejected` possono saltare quando Windows
non consente la creazione di symlink). Non affermare che tutte e 19
le prove negative siano state effettivamente eseguite su Windows.
Il G4D di correttezza sulle verifiche disponibili è PASS con
copertura di symlink ancora aperta per altro ambiente.

## Stato successivo

G1 25 PASS, G2 9 PASS, G3A 23 PASS, G3B 9 PASS, G4A 18 PASS,
G4B 18 PASS; G4C exec/asserzioni PASS ma valori SHA non catturati;
G4D 17 eseguiti PASS +2 skipped. 11 casi OOD sempre locked.
**Non** equivalgono a run reali. Non esiste ancora il dispatcher unico
scientifico né una release firmata/approvata, nessuna autorizzazione API.

La prossima attività è costruire la release scientifica in forma
create-only con claim/record e verifiche runtime, inizialmente
non abilitata a richieste live. Evitare di sovrascrivere i risultati
frozen RQ1/RQ2 V1 e il pilot Sonnet V2.
