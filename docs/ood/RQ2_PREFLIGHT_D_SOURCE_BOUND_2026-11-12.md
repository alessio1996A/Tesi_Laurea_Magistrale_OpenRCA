# RQ2 — Preflight discovery D legato alle sorgenti GT-free

**12 novembre 2026** — Nuovo codice **NON ESEGUIBILE**. Nessuna API, nessun accesso a telemetria Market o ground truth, nessuna modifica a RQ1. **16 test sintetici predisposti, NON ancora eseguiti dall'utente.**

## 1. Evidenze precedenti

Il log PyCharm di `test_rq2_mock_pipeline_integration.py`, dopo la correzione dell'import accidentale della classe `TestCase`, è:

```
Ran 16 tests in 1.152s

OK
```

Sono **16/16 test propri dell'integrazione D→C→K**, tutti superati. È distinta la precedente prova da 32 test (16 integrazione + 16 contratti importati erroneamente); nessun errore di esecuzione in entrambe.

L'audit numerico Colab sui 92 development è già concluso: **29/29 KPI source-only riscontrati**, 123 nomi osservati, 6.722.921 righe numeriche dell'unione delle finestre. Non sono state verificate unità fisiche o metriche sui test OOD.

## 2. Nuovo modulo

`src/evaluation/rq2_source_bound_d_preflight.py` contiene `preview_discovery_d_config(...)`.

**Input:** radice Drive con i due CSV GT-free congelati, un `case_id` nella lista statica delle **quattro discovery**, modello logico `gemini/sonnet/haiku`, harness `A1/A1_8R`, ID modello **proposto ma non ancora approvato** e modalità output `legacy/v2_enforce` **esplicita e non congelata**.

Il codice:
1. Chiama **`evaluation.rq2_dryrun_plan.preview_market(root)`** per verificare SHA-256 originali, partizione 4+11 e finestre senza overlap; il piano deve essere ancora `DRAFT_NOT_EXECUTABLE`.
2. Controlla che esista precisamente lo stage `D` della discovery richiesta, con `stage_id`, fase, dipendenze e identità corretti; tutte le D dei test sono respinte in questa interfaccia.
3. Rilegge i byte dei **due CSV GT-free** e verifica hash prima e dopo il parsing: il file non può cambiare nell'intervallo di preflight senza arrestare il controllo. Il manifest ha **schema chiuso senza GT**, e i record devono corrispondere fra split, manifest e stage per caso, cloudbed, task, `start_unix`, `end_unix`.
4. Costruisce un oggetto temporaneo `ExperimentConfig` originale con `variant_scheme="current"`, tool round = 6 e provider coerente col modello logico. **Non restituisce l'oggetto** né invoca `run_experiment`.
5. Restituisce esclusivamente un **report JSON serializzabile** con hash dell'istruzione, identità tecnica e metadati, senza includere il testo della richiesta, token, telemetria o output del modello.

Flag intenzionalmente sempre negativi: `model_version_frozen=false`, `output_contract_mode_frozen=false`, `scientific_protocol_frozen=false`, `api_budget_approved=false`, `can_execute_api=false`, `can_execute_D=false`, `can_execute_test=false`, `can_execute_K=false`, `model_api_calls=0`, `files_written=false`.

**Non è un'autorizzazione**: il controllo di coerenza parziale del nome modello (`sonnet`, `haiku`, `gemini`) non sostituisce l'ID provider/versione esatta e i parametri congelati. La modalità D `legacy` oppure `v2_enforce` rimane da selezionare in protocollo sulla base della parità con RQ1. Nessun pilot può partire con questo solo report.

## 3. Test

`src/tests/test_rq2_source_bound_d_preflight.py` contiene **16 metodi `TestCase.test_*`** con **CSV totalmente sintetici e preflight sorgenti simulato solo all'interno del test**. Provano: sorgenti coerenti, cambio A1/A1_8R, mancata diffusione del testo dell'istruzione, blocco D test e harness non ammessi, ID modello incoerente, modalità output esplicita, piano non verificato, digest alterato, byte split modificati, finestra/task manifest incoerenti, istruzione vuota e iniezione di colonne di scoring. I test non dimostrano ancora il funzionamento sul manifest Market vero.

### Comando PyCharm (PowerShell)

```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_source_bound_d_preflight.py" -v
```

**Attesi 16 test; non sono ancora stati eseguiti in PyCharm.** Nessuna run Colab è necessaria per questa suite.

## 4. Passi mancanti

Il runner **live** deve essere realizzato solo dopo il preflight, con esecuzione D che **riusa `run_experiment(config, salva=False)`**, e chiamate C e K separate, senza tool. Sono ancora indispensabili: identità modello/parametri/contratto fissati, manifest e piano *realmente* congelati, output persistenti RQ2 create-only (non ricevute mock), policy provider-error e retry, tetto di spesa e autorizzazione esplicita, freeze scientifico K prima di accedere ai dati di test, scoring offline separato.

**RQ1 congelata invariata. RQ2 resta `DRAFT_NOT_EXECUTABLE`.**
