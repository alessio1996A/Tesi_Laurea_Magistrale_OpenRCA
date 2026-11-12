# RQ2 — C/K senza tool: trasporto LangChain con LLM finto (V0)

**12 novembre 2026** · Branch `feature/ood-knowledge-transfer-audit-2026-11-10`. **Nuovi 17 test predisposti, non ancora eseguiti in PyCharm.** Nessun provider reale né API, nessuna lettura di Market, ground truth o scoring. Nessun codice di RQ1 modificato.

## 1. Baseline confermata

Il log reale dell'utente conferma `Ran 13 tests in 0.940s — OK` per `test_rq2_real_langgraph_fake_llm.py`. Quindi il vero `run_experiment(config,llm=fake,salva=False)` e il vero grafo LangGraph RQ1 attraversano i test con tool e caso sintetici, includendo `v2_enforce`, sei round, una finalizzazione, token osservati ed errori. **Questo non include dati Market o API reali.**

La lettura CLI precedente ha catturato (non congelato scientificamente) gli hash dei prompt di sistema:
- `CAUSE_SYSTEM`: `81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42`
- `RULE_SYSTEM`: `0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71`

## 2. Nuovo trasporto STRICTLY FAKE

`src/evaluation/rq2_toolfree_fake_transport.py` introduce:

- `StrictToolFreeFake`, un oggetto sintetico che può emettere **una sola** `AIMessage` LangChain o una `SimulatedProviderFailure`. Non è un wrapper generico in cui iniettare un reale provider: il trasporto richiede `type(fake_model) is StrictToolFreeFake` e rifiuta client/oggetti estranei.
- `invoke_bound_probe_fake(binding=...,fake_model=...)`, che accetta un *binding* da `prepare_bound_c` oppure `prepare_bound_k` già esistenti, verifica l'integrità SHA256 canonica del binding e del `package_sha256`, identità stage/logical model, **fase discovery soltanto** e hash dei prompt verificati sopra.
- Materializza esattamente una coppia `SystemMessage` + `HumanMessage` da `underlying_package.messages`, preservando il contenuto dei prompt. Non esegue `bind_tools`, non registra tools, non invia i prompt a un provider remoto.
- Invoca una volta il solo fake, raccoglie il testo dai blocchi `type=text` o da contenuto stringa usando l'estrattore **storico RQ1** `agent.graph_engine.testo_messaggio(...,solo_testo=True)`. I blocchi di *thinking* non diventano parte della risposta JSON. `AIMessage.tool_calls` o `invalid_tool_calls` generano una **violazione di protocollo**, senza ulteriore richiesta o tool execution.
- Distingue `FAKE_RESPONSE_OBSERVED`, `FAKE_EMPTY_RESPONSE`, `FAKE_PROTOCOL_ERROR`, `FAKE_PROVIDER_ERROR`, conservando `raw_response` e `provider_error` senza riparare JSON. La validazione vera C/K resta nei contratti e in `RQ2DiscoveryStageRecorder`.
- Legge `usage_metadata` dal fake in modo conservativo: se mancano campi o valori validi, indica `complete=false` con token `null`, **non inventa zeri**. `source=SYNTHETIC_AI_MESSAGE_NOT_BILLED` e `actual_usage_billed=false`. Questi contatori sintetici **non sono ancora persistiti dall'archivio D/C/K**.
- Il risultato riporta sempre `model_api_calls=0`, `can_execute_api=false`, `can_execute_test=false`, `scientific_protocol_frozen=false`, `is_scientific_result=false`.

**Controllo di provenienza:** l'hash di un pacchetto ricalcolato dimostra *coerenza interna*, **non** che le fonti GT-free siano state autenticamente lette o che un modello remoto abbia emesso la risposta. È responsabilità dello store source-bound e del successivo runner preregistrato dimostrarlo. I prompt SHA sono snapshot del prefreeze e **non sostituiscono un protocollo scientifico immutabile**.

## 3. Nuovi test

`src/tests/test_rq2_toolfree_fake_transport.py` contiene **17 nuovi metodi unittest**, con fixture sintetiche importate come *moduli*, non classi `TestCase`. Coprono:

- C e K attraverso reali oggetti `SystemMessage`/`HumanMessage` e una sola `invoke`;
- verifica esatta hash C/K e nome modello `claude-sonnet-5-5`;
- esito JSON grezzo, errore provider simulato, risposta vuota, rifiuto di qualsiasi `tool_calls`;
- estrazione corretta dei soli text block, senza thinking Anthropic;
- usage presente, assente, invalidità schema/programma e respinta di finti client provider esterni;
- rifiuto della fase test anche quando un binding C dalla bozza la include;
- prova **D persistita → claim C → C tool-free fake → claim K → K tool-free fake → archivio RQ2** con audit finale `claims=3`, `finished_with_matching_result=3`.

Le chiamate sono solo al fake; non viene letto un benchmark reale. Il test integrato usa la fixture di manifest temporaneo e plan mockato già verificata, confinata al test.

### Comando PyCharm

```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_toolfree_fake_transport.py" -v
```

**Attesi 17 test: non considerarli superati finché non arriva l'output dell'utente.**

## 4. Parti ancora necessarie per il primo pilot API

1. **Provider C/K reale**: tool-free, una chiamata per stage, parametri per i modelli esatti, errori, timeout e prompt package hash; non riutilizzare automaticamente un modello del grafo con `bind_tools`.
2. **Usage persistente**: token originali billable (incluso thinking ove previsto), costo e identificazione provider per ogni chiamata, senza tetto USD imposto.
3. **Freeze dei parametri e protocollo RQ2**: modalità D `v2_enforce` derivata RQ1, ID modello, versions dei package, prompt system/package hashes, split discovery/test, KPI/criteri K, politica di retry e blocco test.
4. **Orchestrazione realmente source-bound**: per D usare il runner storico; claim prima della chiamata, risultato create-only dopo e audit dei claim incerti. Non aprire test finché le K discovery non siano congelate scientificamente.

**Budget economico senza limite prestabilito**, come indicato dal professore all'utente. Il coordinatore fake e il nuovo trasporto non costituiscono autorizzazione a effettuare inferenze.
