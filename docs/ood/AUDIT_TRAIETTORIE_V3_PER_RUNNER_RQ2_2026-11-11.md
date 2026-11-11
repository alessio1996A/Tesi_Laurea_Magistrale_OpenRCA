# RQ2 — Verifica di compatibilità sulle traiettorie V3 congelate (preflight di sola lettura)

**Data:** 11 novembre 2026  
**Stato:** strumenti preparati; **12 test sintetici non ancora eseguiti dall'utente; audit Colab non ancora eseguito**. Non si è chiamato alcun LLM né modificata RQ1.

## Motivazione scientifica/ingegneristica

Prima di collegare il nuovo `rq2_probe_adapter.py` a un runner RQ2, va verificato il **formato effettivo delle traiettorie**. Il codice RQ1 `src/evaluation/experiment_runner.py` restituisce un dizionario contenente `raw_response`, `prediction`, `metrics`, `tool_trajectory`, `error`. Quando `llm=None`, `run_experiment` istanzia un modello reale; **perciò non deve essere eseguito in questa fase**. L'opzione `salva=False` evita il salvataggio opzionale del risultato, ma **non** impedisce una chiamata API se si usa `llm=None`.

Il vecchio `src/agent/graph_engine.py` non registra ID di chiamata nei risultati della traiettoria per A0/A1/A1_8R. Se due chiamate allo stesso tool risultano pendenti contemporaneamente, abbinare i parametri a una risposta senza ID sarebbe arbitrario. Il nuovo bundle RQ2 rifiuta tale situazione in modo fail-closed. Prima di cambiare codice, occorre misurare il fenomeno in modo aggregato.

## Artefatti

- `src/evaluation/rq2_historical_trajectory_audit.py`: audit **sola lettura**, **solo** sotto il protocollo RQ1 V3 `data/results/v2/openrca_harness_v2_five_agents_development_v3` indicato nel README. Non apre Market.zip, CSV originali, `data/results/scoring`, data OOD né chiavi API. Legge JSON dei risultati già esistenti, usa solo `tool_trajectory` e `error` per contare bundle compatibili, risultati ambigui, fallimenti di struttura, numero di osservazioni, troncamenti e bundle vuoti. Non stampa nomi di casi, risultati di tool o predizioni. Non usa output storici per produrre pseudoregole RQ2.
- `src/tests/test_rq2_historical_trajectory_audit.py`: **12 test sintetici**, coprendo directory mancante, risultato legacy, wrapper, assenza di traiettorie, ambiguità, JSON non conforme, rifiuto top-level GT, risultati errore, esclusione scoring e immutabilità del file. **Non dichiarare passati prima dell'esecuzione PyCharm.**
- `notebooks/Colab_RQ2_Historical_Trajectory_Feasibility_2026_11_11.ipynb`: una cella che monta Drive, verifica la directory dei soli risultati V3, scarica/aggiorna il branch senza scartare modifiche locali ed esegue l'audit in sola lettura. Nessuna inferenza e nessun output di caso.

## Sequenza

1. PyCharm:
   ```powershell
   git status
   git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
   $env:PYTHONPATH="src"
   python -m unittest discover -s src/tests -p "test_rq2_historical_trajectory_audit.py" -v
   ```
   Attesi 12 test. Se non passano, correggere prima il codice, senza modificare RQ1.
2. Colab: aprire `notebooks/Colab_RQ2_Historical_Trajectory_Feasibility_2026_11_11.ipynb`. L'output contiene **solo aggregati** di compatibilità. La directory può avere file claim/log oltre ai result; quelli senza traiettoria sono conteggiati separatamente. Se non è accessibile, evitare percorsi alternativi non verificati e rivalutare il layout del protocollo.
3. In base al rapporto reale, decidere se per la fase RQ2 occorre un nuovo wrapper che conservi `tool_call_id` (senza alterare il motore RQ1) oppure se un'astensione tecnica sulle traiettorie ambigue è sufficiente.
4. Solo in seguito verificare in un nuovo runner RQ2 i tool GT-free effettivi, costruzione D/C/K, create-only persistente e ripresa, bundle informativo dei report deterministici A1/A1_8R, modello/costi, limiti e freeze scientifico.

## Cautela metodologica

Questa verifica **non** legge il GT e **non** costituisce ulteriore ricerca di nuove regole: i risultati V3 servono soltanto a misurare **compatibilità del formato**, non qualità di diagnosi né frequenza delle classi. Le pseudoregole RQ2 rimangono vincolate alle quattro discovery della V1 non ancora congelata e non possono essere suggerite o aggiustate usando risultati del test.

**Risultato precedente confermato:** l'utente ha eseguito `Ran 18 tests in 8.944s — OK` per `test_rq2_mock_journal.py`. Journal mock verificato su dati sintetici, ma nessuna run OOD reale ancora eseguita.
