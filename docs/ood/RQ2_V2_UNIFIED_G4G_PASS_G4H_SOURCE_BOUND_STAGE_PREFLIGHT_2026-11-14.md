# RQ2-V2 unificata — G4G PASS; G4H preflight source-bound del singolo stage

**Data:** 14 novembre 2026. **Branch:** `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.

## Esito G4G realmente riportato in PyCharm

```text
Ran 17 tests in 22.415s

OK
```

Questo chiude G4G fake-only: grafi ReAct/Planning/PAVE veri, fake LLM/ToolNode, i 15 abbinamenti harness×modello e il nuovo ledger scientifico G4F in TemporaryDirectory con release fittizia, 45 claim/record D/C/K nel test principale e controlli su errori, provenance, orphan, no-retry, OOD bloccati. Non sono esecuzioni API. La prima failure G4G era un typo della fixture corretto prima della nuova prova, senza allentare il ledger.

## Verifica trasporti precedenti già eseguita

I documenti `RQ2_COLAB_LANGCHAIN_PARAMETER_MOCK_2026-11-12.md` e `RQ2_COLAB_FAKE_HTTP_INVOKE_2026-11-12.md` confermano che erano già stati testati su Colab i due client sincroni LangChain→SDK con HTTP 503 finto e socket deny-all (Google attempts=1 e Anthropic retries=0, un invio mock per `invoke` in modalità con/senza tools). **Non ripetere questi audit per principio**; resta da verificare timeout effettivo, streaming/async se utilizzati, lock Drive/FUSE e accounting reale della campagna. La futura release deve vincolare versione e source SHA del runtime.

## G4H: nuova integrazione di sola lettura, NON ancora collaudata

Nuovi file:
- `src/evaluation/rq2_v2_unified_live_stage_preflight.py`
- `src/tests/test_rq2_v2_unified_live_stage_preflight_offline.py` (**19 test scritti, non ancora eseguiti**).

Questo modulo è **la preparazione riusabile dal futuro dispatcher unico**, non il dispatcher live: richiede il ledger G4F con release e commit approvati esternamente, validazione source-bound del piano da 180 stage; controlla che lo stage discovery sia ignoto a OOD e non sia già stato claimed/recorded, e che non esistano orphan claims globali. Legge direttamente **solo il CSV manifest GT-free** `data/processed/benchmark_inputs_market.csv`, con schema, unicità caso, limiti istruzione e validità finestra. Il gate G4F ha già controllato split+manifest SHA e RQ1 source. Non apre Market.zip, scorer o GT.

Per D crea esclusivamente la proposta `ExperimentConfig` che rispetta le cinque varianti, `v2_enforce`, 6 round e 2 verifiche per Planning/PAVE. Per C/K ricostruisce il package **dagli output D/C esistenti** con `prepare_cause_probe` e `prepare_candidate_rule`, e verifica lo SHA del system prompt con la release. Nessuna indicazione originaria può venire da un parametro libero del chiamante; il record C deve essere già valido prima di K. Tutto l'output conserva `can_create_scientific_claim=False`, `can_construct_provider_client=False`, `can_execute_api=False`, `can_run_ood_test=False`, `files_written=False`.

I 19 test G4H usano CSV manifest inventato, release fittizia, source SHA/mock nel TemporaryDirectory; **non** sono letture di Drive. Verificano D/C/K, prompt SHA, dipendenze, duplicate case, colonne GT proibite, finestra tempo invalida, orphan, stage già recordati, OOD e nessuna scrittura/API.

**Nota economica corretta nel ledger G4F:** token usage completo e prezzo certificato sono due dimensioni diverse. Il ledger ora consente `cost_estimate_usd_not_invoice="UNKNOWN"` anche se la usage metadata è completa: non va inventato `0 USD` se il listino/prezzo applicato non è noto. Questo è un aggiustamento semantico, non un nuovo hard cap e non usa provider.

## Cosa manca per il pilot realmente autorizzato

G4H verifica la preparazione source-bound del singolo stage ma NON chiama API o registra nuovi claim. Il successivo G4I dovrà aggiungere l'esecutore RQ2-V2 source-bound a livello singolo stage, con la stessa semantica del percorso G4G fake: D via `run_experiment` RQ1 e V2 ReAct/verify, C/K tool-free con trasporti `rq2_model_factory` già esistenti. Prima dell'esecuzione reale servono:
- invocazione SDK e receipt testate tramite fake factory **dello stesso dispatcher**, senza allentare i controlli;
- commit clean e SHA source inventory includendo tutti i nuovi moduli G4F/G4H/dispatcher/provider, non soltanto le 15 sorgenti della preview precedente G4C;
- reale release immutabile/approvata e audit GT-free sul nuovo commit; scelta dei limiti operativi e verifica lock Drive/FUSE;
- singolo stage pagato con autorizzazione esplicita dell'utente, non l'intera matrice;
- OOD test e Opzione B restano locked.

Il G4C reale precedente e' attestato sul checkout `33d5d8b28494d5bf41168d0a709854aa3134ea6a`. Hash plan/blueprint G4C sono una BASE storica, non l'hash del codice finale che includerà i moduli nuovi.

## Prossimo test PyCharm

Verificare `git status --short` pulito; poi:
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_live_stage_preflight_offline.py" -v
```

**Attesi 19 test e OK, ma NON attestati prima del risultato dell'utente.** Se fallisce, leggere la prima traceback completa, correggere soltanto il problema provato e ricontrollare G4F/G4G ove toccati. RQ1/benchmark congelati e test OOD non vanno modificati.
