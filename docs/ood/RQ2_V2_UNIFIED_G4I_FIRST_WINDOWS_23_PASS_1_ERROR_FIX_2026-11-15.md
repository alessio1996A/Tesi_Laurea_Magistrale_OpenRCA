# RQ2-V2 unificata — G4I prima esecuzione 23 PASS + 1 ERROR; fix fixture release manomessa

Data: 15 novembre 2026. Branch: `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.

## Esito PyCharm reale dell'utente

```text
Ran 24 tests in 13.179s

FAILED (errors=1)
```

Le 23 prove diverse da `test_fake_release_required_even_if_marker_exists` sono PASS, inclusi grafi D/C/K fake, tre percorsi provider/harness, stage singolo, parent/record SHA, no-retry/orphan, OOD bloccati, socket deny-all e prezzo sconosciuto. L'unica failure è un errore all'ULTIMA assert del test di release manomessa:

```text
File "src/tests/test_rq2_v2_unified_single_stage_dispatcher_offline.py", line 372
    self.assertEqual(self.ledger.audit_restart()["claims"], 0)
...
UnifiedScientificLedgerBlocked: Missing/different scientific release
```

**Diagnosi:** il test cambia intenzionalmente `release_v1.json`, sostituendo il riferimento `SYNTHETIC_APPROVAL_NOT_REAL` con `APPROVAL_FROM_REAL_PERSON`. Il primo `self.run_stage()` viene correttamente rifiutato dall'identity gate. Poi il test vuole contare i claim con `audit_restart()` sulla stessa release manomessa. L'audit non può e non deve aprire un archivio con SHA release errato, quindi solleva `UnifiedScientificLedgerBlocked` anziché restituire un conteggio. **Non è evidenza di errore di API, protocollo, ledger o dispatcher.** La protezione contro manomissioni è corretta.

## Correzione minima su GitHub

Commit: `e57f4955ea1f343339deb4ed02285116df118335`.

Unico file modificato: `src/tests/test_rq2_v2_unified_single_stage_dispatcher_offline.py`.

Il test ora:
1. verifica precisamente che `self.run_stage()` rifiuti la release alterata con `Missing/different scientific release`;
2. verifica che **anche** `self.ledger.audit_restart()` rifiuti la stessa release con identica eccezione;
3. conferma sul filesystem temporaneo che **non** siano state create le directory `CLAIMS` o `RECORDS`, senza eseguire audit su una release per definizione invalida.

**Nessuna variazione** a codice G4I produttivo, ledger G4F, G4H, G4G, RQ1, prompt C/K, split/manifest GT-free, OOD, oppure i 180 stage. Nessuna API reale effettuata.

## Prossimo test PyCharm

Controllare che `git status --short` sia vuoto, poi:
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_single_stage_dispatcher_offline.py" -v
```

Attesi 24 test e `OK`, **non ancora attestati**. G4F 22/22, G4G 17/17, G4H 20/20 erano PASS con file di produzione invariati da questa correzione. Non occorre ripeterli per la sola modifica di questo test.

Dopo G4I PASS, prossima priorità: vero adapter RQ2-only per Gemini/Claude con test del *medesimo* percorso sotto factory mock, real source inventory che includa G4F/G4H/G4I/adapter e verifica lock su Google Drive prima di freeze e singolo pilot pagato **con consenso esplicito**. Opzione B e 11 OOD restano bloccati.
