# RQ2-V2 — G4L: preparazione release writer create-only (HARD-DISABLED)

**Data:** 15 novembre 2026. **Stato:** codice nuovo su branch di preparazione, **9/9 test PyCharm PASS (output utente: `Ran 9 tests in 10.624s — OK`)**; nessuna release scientifica, nessun consenso economico e nessuna chiamata API.

## Motivazione e perimetro

Il G4K `src/evaluation/rq2_v2_unified_live_dispatcher.py` aveva gia' superato 18/18 test mock e contiene `LIVE_API_ENABLED=False`. Non riscrivere il dispatcher gia' funzionante. Il gate ancora mancante era una procedura controllata per la futura materializzazione di `data/rq2_v2_unified_scientific_v1/release_v1.json` richiesta dal ledger G4F.

Su **nuovo branch** `feature/rq2-v2-scientific-release-writer-prep-2026-11-15`, nato dal commit documentale `f08737dcfce20ef84bebc70ea1c1446c09c28bd7`:
- Aggiunta nello stesso file source-bound esistente `src/evaluation/rq2_v2_unified_scientific_ledger.py` la funzione `create_authorized_scientific_release_once`, con `SCIENTIFIC_RELEASE_WRITE_ENABLED=False` per default. La funzione blocca ogni invocazione immediatamente, prima di leggere o scrivere il filesystem.
- Un eventuale futuro sblocco, NON autorizzato oggi, obbligherebbe G4D reale (HEAD clean, namespace assente), 6 SDK pinned/4 SHA runtime, G4A source-bound GT-free, G4B blueprint, contratto G4E e digest SHA esterno, budget/referenza reali, creazione O_EXCL + fsync + readback, lock e nessun retry su fallimento.
- Nuovo file `src/tests/test_rq2_v2_unified_scientific_release_writer_offline.py`, **9 test sintetici PASS su PyCharm**. Simulazioni con `TemporaryDirectory`, source/SDK fake, patch della flag solo durante il test; nessuna API o provider. Casi: hard-disable, ref sintetico, ref differente, versione SDK, SHA diverso, OOD unlocked, una scrittura fake canonica, duplicato no-overwrite, namespace occupato.

## Attenzione sugli hash

La funzione e' stata aggiunta ad uno dei **30 sorgenti gia' inventariati**; il numero di SOURCE_PATHS **rimane 30**, ma lo SHA del file `rq2_v2_unified_scientific_ledger.py` e di conseguenza gli SHA **aggregato sorgenti e blueprint** saranno diversi dopo il nuovo commit. Non usare i vecchi hash `8c2d.../220053...` per una release sul nuovo branch; essi restano evidenza valida del PASS prerelease del commit `4733eb90...`. La prossima verifica Colab dovra' fare source-bound/release prerelease GT-free sul nuovo commit clean, senza invocare provider.

**Per la nuova suite PyCharm mirata**:
```powershell
git status --short
git fetch origin
git switch feature/rq2-v2-scientific-release-writer-prep-2026-11-15
git pull --ff-only origin feature/rq2-v2-scientific-release-writer-prep-2026-11-15
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_scientific_release_writer_offline.py" -v
```
I 9 metodi sono PASS (10.624s), già acquisiti e NON da ripetere. Per il cambiamento al modulo ledger G4F, rimane da eseguire **soltanto la regressione strettamente dipendente** `test_rq2_v2_unified_scientific_ledger_offline.py` (22 metodi), poi l'audit Colab del nuovo sorgente, sempre senza API. Non ripetere 87 test prerelease, 145 test G4 storici o il vecchio preflight Colab.

## Gate di sicurezza aperti

- `SCIENTIFIC_RELEASE_WRITE_ENABLED=False` e `LIVE_API_ENABLED=False`.
- 0/180 stage reali, 11 OOD locked, RQ1 e precedenti RQ2 frozen; nessuna nuova release SHA o claim.
- Il codice futuro non puo' dimostrare da solo il consenso dell'utente: un digest non e' firma personale. Sono necessari un budget operativo positivo e una policy stop, la referenza di approvazione e il consenso **separato** per `cloudbed-1_q032:gemini:A0:D`. Un limite USD non e' hard cap provider.
- Dopo la futura variazione della flag di produzione serve **nuovo** clean HEAD e audit reale G4A/G4B sul codice finale. Non abilitare alcuna flag in questa fase e non fare un test reale senza ulteriore consenso dell'utente.
- Refactoring e documentazione italiana a fine progetto, dopo audit/freeze sperimentali; questa estensione circoscritta non e' refactoring.

**Non modificare alcun protocollo scientifico, prompt C/K o test OOD.** Il nuovo branch e' una proposta ingegneristica da validare, non una release.
