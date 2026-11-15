# RQ2-V2 — G4I 24/24 PASS; G4J ricevute provider verso ledger G4F

**Data**: 15 novembre 2026. **Branch**: `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.

## Evidenza PyCharm ricevuta

```text
Ran 24 tests in 11.480s

OK
```

**G4I PASS 24/24** dopo il fix nel SOLO test di release manomessa. La fixture verifica correttamente che `run_stage` e `audit_restart` rifiutino un file release con SHA invalido e che non vengano scritti claim o record. Il gate reale SHA non è stato allentato.

Riepilogo gate recenti attestati: G4F 22/22, G4G 17/17, G4H 20/20, G4I 24/24 PASS; sono test offline con mock/fixture, non una nuova campagna API.

## Nuovo G4J: normalizzazione UNICA delle ricevute, sempre 0 API

File aggiunti al branch:
- `src/evaluation/rq2_v2_unified_provider_result_adapter.py`
- `src/tests/test_rq2_v2_unified_provider_result_adapter_offline.py` (**25 metodi UNITTEST DA ESEGUIRE, ancora PENDING**).

Il modulo NON invoca provider, non costruisce client, non legge Market/GT né scrive file. Usa il piano RQ2-V2 unificato **4 discovery × 5 harness × 3 modelli × D/C/K**, non V1.

Le due entrate sono:
- `normalize_d_run(stage_id,logical_model,run)` accetta il dizionario già restituito dal runner RQ1 **unchanged** (`run_experiment(...,llm=...,salva=False)`); controlla case, modello, provider, harness, schema `v2_enforce`, token completi/parziali, `llm_calls`, tool provenance e output; restituisce `RECORDED_COMPLETE`, `INVALID_OUTPUT` o `PROVIDER_ERROR` + artifact ledger. Un errore D usa un digest del testo dell'errore, NON il raw SDK error che potrebbe contenere segreti.
- `normalize_ck_call(stage_id,logical_model,call,diagnostic_run)` accetta il dict già restituito da `rq2_ck_provider_transport._one_call` con `api_attempts`, usage, raw text o errore sanitizzato. Preserva i risultati `candidate` e `insufficient_evidence`, non ripara evidenze inventate o JSON invalido, rifiuta D di modello/caso diversi, zero/doppie invocazioni non giustificate, totali token inconsistenti, errori provider non sanitizzati.

Le classificazioni sono sottoposte al medesimo `_validate_artifact` del ledger G4F, prima che il futuro dispatcher appenda un record. Questo evita la divergenza in cui il trasporto dichiara `RECORDED_COMPLETE` ma il readback scientifico lo respinge. Non nasconde un crash: malformazioni non classificabili fanno fail-closed, lasciando un eventuale claim irrisolto da revisione.

`observed_model_requests` significa **invocazioni logiche osservate**, non hard cap HTTP. `input_tokens_observed` / `output_tokens_observed` sono quantità riportate disponibili; `usage_complete=false` indica che non si può dedurre fatturazione totale. `cost_estimate_usd_not_invoice="UNKNOWN"` anche con token completi; **non si inventa un costo di zero dollari** e non si promette hard cap. `provider_requests_sent_here=0` significa esclusivamente che QUESTO ADATTATORE non chiama provider: non che la risposta già ricevuta non abbia richiesto API.

I 25 test G4J usano solo fixture in memoria e un `TemporaryDirectory` per un percorso completo di claim→record D/C/K→SHA→readback sul vero ledger G4F, con release e commit FAKE. Altri test riguardano modelli Gemini/Sonnet/Haiku, Planning, JSON invalidi, E### inventate, errori D/C/K, pre-request e post-invoke, uso incompleto e assenza di costo certificato. **Non sono 25 richieste API**.

## Prossima azione PyCharm

Sul branch pulito:
```powershell
git status --short
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_provider_result_adapter_offline.py" -v
```

**Attesi 25 e OK, NON ancora attestati.** In caso di fail, seguire il primo traceback, non dichiarare PASS né modificare RQ1/GT/rule prompts.

## Rischi reali ancora da chiudere prima del pilot pagato

1. Esiste già `rq2_model_factory.py` e i trasporti live RQ2-V1 `rq2_discovery_d_provider_transport.py`, `rq2_ck_provider_transport.py`. **NON riusare direttamente i vecchi entrypoint su G4F**: hanno release, recorder, namespace e piano V1 differenti. G4J normalizza le ricevute ma non è ancora una nuova entrypoint live.
2. Occorre collegare davvero un SOLO nuovo dispatcher RQ2-V2 a `crea_modello_rq2`, `run_experiment` RQ1 D e tool-free C/K, con claim sempre PRIMA del client, approvazione esplicita del singolo stage e prevenzione invocazioni accidentalmente multiple.
3. Il vecchio `SOURCE_PATHS` G4A include 15 sorgenti ma non include ancora ledger G4F, G4H/G4I/G4J, factory e nuovo dispatcher. **Non produrre una release live con un source inventory incompleto**; estenderlo e rigenerare gli hash dopo aver terminato il codice e testato i client.
4. Verificare lock/single-writer sul filesystem Google Drive/FUSE **senza dati RQ1 né query API** e tenere conto di crash/orphan. Limitare a 1 stage per primo pilot, monitorare uso/costi e verificare tariffe aggiornate; 492 e' tetto teorico graph invocation, non tetto HTTP/fattura.
5. Solo dopo nuovo freeze scientifico e consenso utente a costi/identità stage, iniziare un pilot API reale. **11 test OOD/Opzione B LOCKED**, nessuna nuova run RQ2-V2 ancora avviata.

## Interpretazione scientifica

G4I prova il percorso strutturale con fake provider. G4J prova la compatibilità dei risultati dei provider con il ledger e la contabilizzazione osservata. Nessuno dei due dimostra accuratezza RCA, disponibilità remota, bontà della regola K o generalizzazione: quelle ipotesi richiederanno la campagna Option A reale e il successivo test holdout autorizzato.
