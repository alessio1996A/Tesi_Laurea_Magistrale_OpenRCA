# RQ2 — Prova del vero runner RQ1 e grafo LangGraph con LLM finto

**12 novembre 2026 — Nuova suite predisposta, NON ancora eseguita dall'utente.** Nessuna API, dataset OpenRCA, GT, scoring o output RQ1.

## Risultati già osservati

Il log PyCharm dell'utente conferma `Ran 14 tests in 0.348s — OK` per `test_rq2_protocol_identity_preflight.py`, seguito da esecuzione CLI `python -m evaluation.rq2_protocol_identity_preflight` con `rq1_source_blob_sha1_match=true`. Il confronto delle sorgenti RQ1 congelate ha verificato che la campagna Evaluation20 usava `v2_enforce`, `max_tool_rounds=6`, `variant_scheme=current`, `recursion_limit=30`. SHA-256 dei prompt C/K forniti dalla CLI e registrati nel documento di continuità:

- `CAUSE_SYSTEM`: `81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42`;
- `RULE_SYSTEM`: `0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71`.

Queste sono impronte **acquisite, non freeze scientifico**.

## 1. Cosa cambia rispetto al coordinatore fake già testato

Il coordinatore `rq2_fake_discovery_driver.py` prova claim e recorder con risposte pre-caricate. **Non invoca il grafo LangGraph originale**. La nuova prova chiama realmente:

```python
from evaluation.experiment_runner import run_experiment
run_experiment(config, llm=fake_model, verbose=False, salva=False)
```

con lo stesso `ExperimentConfig` del progetto. **Non cambia nessun sorgente RQ1.**

Il fake implementa `bind_tools(tools)` e `invoke(messages)`, producendo `AIMessage` e una richiesta tool sintetica. Il vero `agent.graph_engine.crea_grafo_rca` costruisce il grafo LangGraph, il vero `ToolNode` esegue il tool finto e il vero `esegui_grafo_rca` conta chiamate, token, round e trajectory. Il vero `run_experiment` applica `v2_enforce` all'output finto, senza leggere label, scorers o CSV.

### Confine di isolamento deliberato

**Soltanto `prepara_esperimento` viene sostituito dal test**, per impedire accessi a manifest e Market.zip: restituisce un caso **inventato** (`cloudbed-1_q999`, non nella coorte RQ2), un tool `synthetic_probe` completamente in memoria, un report evidence sintetico e una richiesta finta con una singola failure esplicita. `run_experiment`, `ExperimentConfig`, `agent.graph_engine`, `ToolNode`, `get_system_prompt` e `v2_task_contract` **sono invece quelli autentici di RQ1**.

Non è quindi una prova della **preparazione reale di A1/A1_8R**, della validità delle metriche OpenRCA nei 4 casi discovery, della disponibilità API Gemini/Claude o della qualità scientifica delle diagnosi. Il preflight source-bound su manifest reali e il futuro pilot indipendente saranno necessari. Il test non genera predizioni su casi realmente presenti in split. LLM fake e tool sintetico non chiedono credenziali.

## 2. Copertura tecnica nuova

File: `src/tests/test_rq2_real_langgraph_fake_llm.py`, **13 metodi unittest sintetici preparati**:

- A1 e A1_8R attraverso il vero `ToolNode` usando `bind_tools`;
- rispetto di `v2_enforce` e aggiunta delle istruzioni task-aware al system prompt;
- tool-call e tool-result registrati in `tool_trajectory`;
- aggregazione token osservati delle AIMessage (e `token_usage_complete=false` quando mancano);
- simulazione dei **6 round** con un'unica finalizzazione e 7 chiamate fake;
- rifiuto di una tool-call oltre il budget e errore di finalizzazione vuota;
- JSON originale invalido non trasformato in predizione valida;
- provider configurato come Google ma nessuna creazione del client Google;
- nessuna scrittura in `data/results` o lettura di `Market.zip`/manifest.

### Prossima verifica in PyCharm

```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_real_langgraph_fake_llm.py" -v
```

**Attesi 13 test, NON ancora eseguiti.** Se emergono errori, verificare il mock finto/test prima di considerare modifiche a `agent.graph_engine` o `experiment_runner`: RQ1 è congelata e l'interfaccia non va modificata per far passare un nuovo test.

## 3. Dopo la prova, per arrivare al pilot

1. Fissare `D.output_contract_mode=v2_enforce` nel protocollo RQ2 mantenendo la parità source-checked.
2. Preparare un singolo adapter per **C e K senza tool** con API provider reali (nessuna `bind_tools`), tracciamento usage/errori e modalità parametri pin coerenti per ogni modello; provarlo prima con fake model in memoria e blocco di chiamate ulteriori.
3. Freeze create-only del protocollo: coorte 4 discovery e 11 test, hash sorgenti/prompt/catalogo, classi e criteri di validazione, policy provider/retry, gate scientifico K. **Test OOD chiusi fino al freeze**.
4. Eseguire una singola run pilot reale autorizzata della discovery soltanto dopo preflight Colab, con claim persistente creato prima di chiamare il provider. Il professore non impone un limite finanziario; costi/token vanno comunque registrati per replicabilità.

**Non sono stati avviati nuovi esperimenti con modelli reali.**
