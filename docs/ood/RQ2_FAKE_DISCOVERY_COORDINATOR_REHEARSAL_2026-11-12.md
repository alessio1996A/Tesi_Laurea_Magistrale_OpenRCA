# RQ2 — Coordinatore discovery con backend finto, senza accesso ai dati reali

**12 novembre 2026** · Branch `feature/ood-knowledge-transfer-audit-2026-11-10`. **Nuovi 16 test sintetici predisposti, non ancora verificati in PyCharm.**

## Evidenza precedente

Il log consegnato dall'utente per `test_rq2_claim_recorder_end_to_end.py` è:

```
Ran 16 tests in 9.059s

OK
```

La suite precedente è **16/16 verde**, ma verifica passaggi manuali D→C→K su fixture, non il dispatch di un vero LLM. La nuova implementazione serve a verificare che **un unico coordinatore** possa governare lo stage e il checkpoint, sempre con output sintetici.

## 1. Nuovo `rq2_fake_discovery_driver.py`

Il modulo aggiunge **soltanto**:

- `DeterministicFakeBackend`: restituisce una sola volta, da memoria, un dizionario di risposte per `stage_id`. **Nessuna funzione di SDK, rete, modello, tool, scorer o `run_experiment` è importata o chiamata.**
- `RQ2FakeDiscoveryDriver`: usa le vere interfacce `RQ2DiscoveryClaimJournal` (create-only) e `RQ2DiscoveryStageRecorder` (registrazione delle D/C/K) e l'audit dello store già implementato. Non modifica alcuna regola RQ1.
- `run_one(stage_id=...)`: controlla stage discovery pianificato e modello esatto, verifica la fase precedente. Se il genitore è fallito, registra `BLOCKED_DEPENDENCY` senza creare claim provider. Altrimenti crea **prima** il claim e poi prende una risposta dal fake backend. Eventuali errori fra queste due operazioni lasciano una prenotazione senza artefatto, da revisionare, **mai ritentata automaticamente**.
- `run_discovery_triplet(...)`: orchestra sequenzialmente D, C, K sullo stesso caso/harness/modello e restituisce audit finale, senza run reali, con `model_api_calls=0`, `can_execute_test=false` e `scientific_results_produced=false`.

### Isolamento dalla campagna scientifica

Il costruttore richiede l'esatto file marcatore `.rq2_synthetic_fixture_only` contenente `RQ2_SYNTHETIC_FIXTURE_ONLY_V0\n` e **rifiuta qualunque root che abbia `Market.zip`**. Accetta solo un oggetto di tipo esatto `DeterministicFakeBackend`, non un provider o callback esterno che possa effettuare chiamate. L'autenticazione originale di `preview_market` sui manifest GT-free resta obbligatoria nella produzione; la *sostituzione temporanea* degli hash originali avviene **esclusivamente nei test**, su due CSV sintetici. Lo script in assenza di quel monkeypatch non può fingere che gli hash dei dati sintetici siano gli originali.

Queste sono guardie contro l'uso accidentale, **non una sandbox di sicurezza contro qualcuno che modifichi il codice intenzionalmente**. Gli output del fake backend non devono essere pubblicati, aggregati o valutati come run della RQ2 reale. Nessun claim creato in questo percorso autorizza automaticamente future API.

## 2. Test preparati

File: `src/tests/test_rq2_fake_discovery_driver.py`, **16 veri metodi `TestCase.test_*`**. Riutilizzano il setup già verificato della suite precedente come *modulo*, per evitare un secondo discovery accidentale dei suoi `TestCase`.

Copertura: sequenza con 3 claim e 3 artefatti; dipendenze; blocco duplicati al riavvio; errori D/C con blocco in cascata; JSON C invalido conservato; K `insufficient_evidence` valido; interruzione tra claim e risposta; claim orfano al riavvio; rifiuto di directory non marcate o con `Market.zip`; rifiuto di oggetti con interfaccia provider; blocco stage test e K prematura; rifiuto di schema fake incoerente; D original invalid_json con tool-evidence valida; nessun cost ceiling.

**Comando PyCharm (PowerShell):**

```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_fake_discovery_driver.py" -v
```

**Attesi 16 test, ancora da eseguire.**

## 3. Stato delle decisioni da congelare

L'esito positivo del fake driver non prova l'esecuzione del grafo `run_experiment` né la compatibilità del tool-free `invoke` C/K con i provider Google/Anthropic. Questi verranno verificati nei prossimi passaggi.

La bozza scientifica rimane 4 discovery/11 test (10 finestre), 90 D + 90 C + 24 K, tre modelli precisi candidati e due harness. **Budget economico senza limite**, come riferito dall'utente dal professore; per ogni run reale registreremo comunque usage/costi/errori. Da fissare prima della prima API: modalità originale D `legacy/v2_enforce` e suo status di parità RQ1, prompt C/K e digest dei file sorgente, parametri di C/K e policy degli errori/provider, pre-registrazione formale e gate del freeze scientifico K prima di usare le finestre test. Nessun `human in the loop` diagnostico.

Non introduciamo refactoring cosmetico o nuove classi di fault nella RQ1.
