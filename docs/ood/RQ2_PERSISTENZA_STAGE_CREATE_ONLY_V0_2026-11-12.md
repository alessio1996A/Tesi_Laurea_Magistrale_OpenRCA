# RQ2 — Persistenza di artefatti per stage (create-only, V0)

**12 novembre 2026** — Codice implementato sul branch `feature/ood-knowledge-transfer-audit-2026-11-10`. **I nuovi 23 test sintetici sono predisposti ma non ancora eseguiti dall'utente.** Nessuna API, nessuna analisi dei casi OOD test e nessun mutamento dei risultati RQ1.

## 1. Verifica precedente realmente riuscita

L'utente ha eseguito il preflight sorgente D in PyCharm e riportato:

```
Ran 16 tests in 0.524s

OK
```

Questo conferma il comportamento sintetico di `rq2_source_bound_d_preflight.py` per identità, finestre e configurazione non eseguibile. Il preflight D **non** è ancora stato eseguito direttamente sul manifest reale tramite la sua CLI; il test usa fixture sintetiche e verifica le guardie, non una chiamata ai provider.

## 2. Perché non basta il mock journal

`rq2_mock_journal.py` salva soltanto ricevute `MOCK_COMPLETE`, senza dati D/C/K, errori grezzi o artefatti di modello. Per riprodurre una futura campagna RQ2 serve un **archivio separato di contenuti reali**, immodificabili e riconducibili a caso, modello, harness, stage, fonti e dipendenze. Non deve poter autorizzare automaticamente un'esecuzione a pagamento né aprire il test.

Nuovo modulo: `src/evaluation/rq2_stage_artifact_store.py`.

- Il costruttore ricalcola `preview_market(data_dir)` usando i CSV GT-free originali con SHA-256 previsto, verifica con `_validate_plan` la coerenza del piano, poi definisce una directory esclusiva. **Il costruttore non scrive alcun file**.
- Directory di destinazione **fissa**: `<data_dir>/data/rq2/stage_artifacts_v0/` (fuori da `data/results/` di RQ1). Non può essere ridirezionata dal chiamante su un'altra cartella.
- `save_discovery_stage(...)` riceve esclusivamente un risultato **già fornito dal chiamante**. Non esegue agente, LLM, strumenti, scorer o pseudocodice. Nome file `RQ2_STAGE_<sha256(stage_id)>.json`, scrittura con `os.O_CREAT|os.O_EXCL`, fsync, contenuto JSON canonico con `record_sha256` e `artifact_sha256`.
- Metadati: stage, fase, caso, harness, modello logico, nome proposto (ancora **non congelato**), hash piano e dei due manifest GT-free, status, mappa degli hash delle dipendenze, payload originale JSON-seralizzabile, `authorization=NO_API_AUTHORITY`.
- Stati finali separati: `RECORDED_COMPLETE`, `INVALID_OUTPUT`, `PROVIDER_ERROR`, `BLOCKED_DEPENDENCY`. Un provider error **non va trasformato** in un output valido. Dopo D in errore, C deve diventare `BLOCKED_DEPENDENCY`; dopo C bloccata, K viene anch'essa bloccata. L'archivio non autorizza retry o sovrascrittura di uno stage già registrato: policy di retry con claim sarà una decisione separata del protocollo.
- `audit_restart()` verifica digest, JSON canonico, provenienza, dipendenze, stati, integrità della directory e presenza di file estranei, anche dopo riavvio. Una scrittura parziale resta sul disco ed è **rifiutata** (non cancellata/sistemata automaticamente).
- **La fase test è sempre bloccata** in questa versione: il mock freeze non può mai essere scambiato per un freeze scientifico. Non contiene funzioni per dispatch del modello o per sbloccare il test.
- Limitazione dimensione per singolo artefatto: circa **32 MB** di JSON canonico; una risposta troppo grande non viene troncata silenziosamente, ma rifiutata.

### Integrità versus autenticità scientifica

L'hash di un record è utile per accertare alterazioni accidentali; **non costituisce una firma crittografica contro un soggetto che può riscrivere record e hash**, né sostituisce inventario commit, manifest scientifico e freeze del protocollo. Un input `RECORDED_COMPLETE` indica che il contenuto è stato salvato, **non** che la diagnosi sia corretta, che il JSON sia semanticamente valido o che l'esecuzione del modello sia autorizzata.

Le chiavi tipiche della parte di ground truth (`scoring_points`, `ground_truth`, `reference_fault_types`, etc.) sono respinte ricorsivamente. Questo è un blocco del **schema**, non un filtro semantico dei valori stringa: la separazione scientifica dal GT deve essere garantita a monte dal processo runner, dalle fonti consentite e dagli input/output contrattualizzati.

L'archivio è **create-only a livello di singolo stage finale**, non è un meccanismo di prenotazione atomica delle chiamate LLM. Non sono ancora definiti: gestione di claim `in_progress`, retries dopo timeout senza doppia spesa, limiti di costo, modelli esatti, output C/K, freeze scientifico delle K e valutazione offline. Non usarlo per lanciare realmente la campagna.

## 3. Nuovi test sintetici

`src/tests/test_rq2_stage_artifact_store.py`: **23 metodi di test**, privi di provider, telemetria e dati Market. Testano: costruttore solo lettura, isolamento da RQ1, D/C/K e hash delle dipendenze, blocchi su stage test, provider error, invalid JSON, blocchi a cascata, duplicati create-only, manomissione JSON, crash con file parziale, file estranei, cambio degli SHA manifest, cambio del piano, contenuti non finiti, campi GT iniettati, identità modello e limiti di dimensione.

**Passo richiesto in PyCharm:**

```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_stage_artifact_store.py" -v
```

**Attesi 23 test. Esito NON ancora verificato.** Se falliscono, correggere il nuovo modulo/fixture e rieseguire prima di procedere.

## 4. Successivo sviluppo, dopo verifica verde

Collegare la persistenza al future orchestration path **senza modificare** `run_experiment(config, salva=False)`, verificando innanzitutto che gli input siano *realmente source-bound*, che la D sia registrata in modalità create-only e che C/K siano dipendenti da un output D valido o dichiarati bloccati. Prima delle vere API: modello/provider ID esatti, modalità output D fissata, parametri, policy errori/retry, budget hard cap e autorizzazione, data isolation e freeze scientifico delle pseudoregole. Solo dopo si procede alla discovery reale.
