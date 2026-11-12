# RQ2 — Adapter offline D/C/K → archivio create-only discovery

**12 novembre 2026** | **Nuovi 20 test sintetici preparati, NON ancora eseguiti dall'utente**.  
Nessuna chiamata LLM, nessun tool su OOD, nessuna scrittura o modifica RQ1, nessuna apertura del test.

## 1. Esito precedente confermato

L'utente ha eseguito `test_rq2_stage_artifact_store.py`:

```
Ran 23 tests in 1.617s

OK
```

Quindi lo store degli artefatti ha superato tutti i **23 test sintetici** per integrità, create-only, restart, segregazione RQ1 e blocco test. **Non** significa che una run RQ2 sia stata effettuata.

## 2. Nuovo collegamento, senza duplicare il motore RCA

`src/evaluation/rq2_discovery_stage_recorder.py` introduce `RQ2DiscoveryStageRecorder`, un adapter **offline e write-once** fra:
- `preview_market(data_dir)` e manifest GT-free con hash verificati;
- `rq2_stage_binding` per identità stage, piano, modello/harness e vincoli D→C→K;
- `rq2_evidence_bundle` per le sole osservazioni tool con E001, E002…;
- `rq2_output_contracts` per C e K JSON;
- `rq2_kpi_formalizability_preflight` per distinguere regole K strutturalmente valide da regole scientificamente pronte;
- `RQ2StageArtifactStore` per salvataggi veri su file RQ2 con `O_EXCL`, SHA e restart audit.

L'adapter **NON implementa D**, non invoca `run_experiment`, non ha un provider client, non esegue K, non richiama lo scorer e non autorizza il test. Riceve in input **esclusivamente contenuti forniti dal chiamante**, consentendo per ora prove con risultati totalmente sintetici; in futuro un orchestratore autorizzato potrà passargli le risposte dei provider.

### Funzioni esposte

- `record_d(stage_id,model_id_proposed,diagnostic_run)`: controlla identità D secondo il piano e ID modello esatto, lega il caso alla vera istruzione GT-free presente nel manifest e registra il record RQ1-style, incluse `tool_trajectory`, `raw_response`, eventuale `error` e `json_status`. Se l'errore del modello è presente, lo stato è `PROVIDER_ERROR`; se la traiettoria non è ricostruibile, è `INVALID_OUTPUT`; se la traiettoria è utilizzabile e non c'è errore, lo stato è `RECORDED_COMPLETE`.
- **Distinzione critica:** `RECORDED_COMPLETE` qui significa **run D osservativamente utilizzabile**, non una diagnosi originale D in JSON valido o corretta. Il campo originale `json_status` viene conservato separatamente. Una D il cui task JSON sia invalido può comunque fornire tool evidence per C, dato che il prompt C non incorpora la risposta finale D. **Questa convenzione va espressamente congelata prima delle API**, senza cambiare scelte dopo risultati OOD.
- `record_c(stage_id,model_id_proposed,raw_response,provider_error)`: legge la D persistita mediante `load_discovery_stage` (che riaudita tutti i record), ricostruisce C da `prepare_bound_c` con la stessa istruzione e traiettoria, verifica il JSON e le evidence IDs, conserva la risposta grezza, hash binding, JSON validato o errore. Se D ha fallito, C può essere salvata solo come `BLOCKED_DEPENDENCY` e non riceve testo/errore di chiamata.
- `record_k(stage_id,model_id_proposed,raw_response,provider_error)`: usa la D e la C **precedenti, effettivamente persistite**, verifica identità, binding C invariato e provenienza E###, esamina la proposta K e conserva il preflight conservativo di formalizzabilità. Un K `insufficient_evidence` valido è un risultato completo, non un provider error; un JSON invalido resta `INVALID_OUTPUT`. Se C ha fallito, K è `BLOCKED_DEPENDENCY`. Solo discovery, nessuna apertura test.

**Store aggiornato in modo conservativo:** `RQ2StageArtifactStore.load_discovery_stage(...)` ha una nuova interfaccia **read-only**, con `audit_restart()` prima di restituire un record verificato. Niente modifiche al writer create-only già testato e niente nuova autorizzazione.

## 3. Stati, errori e sicurezza

Gli stati persistiti non sono le classi del fault: sono esiti tecnici `RECORDED_COMPLETE`, `INVALID_OUTPUT`, `PROVIDER_ERROR`, `BLOCKED_DEPENDENCY`. Nessuna conversione degli errori in predizioni. Le risposte vengono salvate grezze (se fornite) senza riparazione JSON. I duplicati vengono rifiutati: per i timeout dopo una chiamata spesa ma prima del salvataggio finale servirà una politica di claim ed eventuale manual audit, prima di costruire un runner live.

Le guardie sulle chiavi conosciute di GT non costituiscono filtro semantico delle stringhe: la vera separazione dall'answer key dipende dalla procedura sorgente. Tutti i report/test attuali hanno `can_execute_api=false`, modello proposto e non congelato, nessun freeze scientifico né autorizzazione alla spesa. **Non interpretare gli output sintetici come risultati su OpenRCA.**

## 4. Test predisposti

`src/tests/test_rq2_discovery_stage_recorder.py` contiene **20 veri metodi unittest**, indipendenti dagli altri `TestCase` (le fixture sono importate come moduli, non come classi).

Vengono verificati: D→C→K e audit restart, nessuna funzione di dispatch, vincoli GT-free e identità, K non test-ready, D originale invalid_json con evidenze valide ancora utilizzabili, errore provider D con blocco a cascata, traiettoria malformata, C JSON invalido, timeout C, K JSON invalido, assenza di D o C, blocco fasi test, mismatch modello, iniezione schema scoring, create-only, modifica manifest dopo D, conflitto provider error+risposta C, `insufficient_evidence` K, restart dopo D.

Da PyCharm:

```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_discovery_stage_recorder.py" -v
```

**Attesi 20 test, non ancora confermati**. A seguito di esito verde, completare controllo dei veri parametri/model ID e claim/budget/freeze prima di introdurre qualunque modalità live. RQ1 e test OOD rimangono intatti.
