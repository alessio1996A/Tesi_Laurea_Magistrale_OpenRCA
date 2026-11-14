# RQ2-V2 unificata — G4A 18/18 PASS e G4B blueprint non eseguibile

**Data:** 14 novembre 2026. **Branch:** `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`. Obiettivo scientifico Opzione A; Opzione B successiva, **11 test OOD rimangono bloccati**.

## 1. Risultato utente verificato

```text
Ran 18 tests in 0.353s
OK
```

L'utente ha eseguito `src/tests/test_rq2_v2_unified_release_preflight_offline.py`. **G4A test unitari PASS**. G1 25/25, G2 9/9, G3A 23/23, G3B 9/9 erano già PASS. Totale fino a G4A: **84 metodi unitari superati nelle cinque suite**, con fake / mock e senza nuova campagna provider. Nessuna prova ancora su GT-free CSV reali *nel contesto del nuovo G4A*; i test G4A sostituiscono la sorgente originale con fixture.

## 2. G4B aggiunto al branch — non ancora testato

Nuovi file:
- `src/evaluation/rq2_v2_unified_release_blueprint.py`
- `src/tests/test_rq2_v2_unified_release_blueprint_offline.py` (18 test method **NON ESEGUITI**).

Il blueprint prende una preview G4A come input, controlla SHA del piano a 180 stage, identità source-bound, 15 path sorgente, split/manifest e stato fail-closed; genera una rappresentazione deterministica (SHA) di tutti i 180 stage:
- **4 discovery × 5 harness × 3 modelli = 60 arm-case**; D/C/K 60 ciascuna; per ogni provider **20 D + 20 C + 20 K**.
- ReAct `A0/A1/A1_8R`: ipotesi di tetto al numero di `invoke` del grafo D **7** (6 round tool + finale).
- Planning/PAVE: ipotesi tetto D **5** `invoke` (4 esplorazione + finale, planner deterministico).
- C e K: ciascuna una richiesta logica tool-free se lo stadio precedente è valido.
- Somma teorica massima **492 invocazioni LLM a livello di grafo**, NON 492 richieste HTTP certificate, NON un preventivo di spesa, NON un hard-cap. Se una stage fallisce, i dipendenti non vengono inviati; il totale effettivo può essere inferiore. Ritenti impliciti SDK/LangChain e error receipts sono ancora da verificare.
- È espressamente vietato riusare `rq2_v2_unified_synthetic_journal` come store scientifico: namespace proposto separato `data/rq2_v2_unified_scientific_v1`, ancora **non creato** e **non implementato**.
- L'identità fonte G4A è soltanto input controllato; il blueprint non legge i CSV per conto proprio. Anche una preview apparentemente valida non può autorizzare API.

Il blueprint elenca i gate futuri: verifica GT-free reale; ledger scientifico create-only con readback; dispatcher unico D/C/K; meter sincrono e contabilità errore; trasporto per-request SDK realmente certificato; rate-limit/costi aggiornati; single-writer/concurrency; Git clean/pin scientifico; consenso API pagate.

**Attenzione:** gli attuali strumenti RQ2 V1 `rq2_budget_preflight.estimate_campaign_cost` e `STAGES_PER_MODEL={"D":30,"C":30,"K":8}` sono calcolati per V1 e NON descrivono la matrice 5×3×4 della Opzione A. Per Opzione A i corretti conteggi a modello sono **20/20/20**. Non importare i vecchi denominatori nei conti scientifici.

**Transport note:** il factory RQ2 candidato passa `max_retries=1` a Google e `max_retries=0` ad Anthropic; il modulo `rq2_sdk_retry_mock_probe` documenta che l'effettivo comportamento LangChain→SDK Google non è ancora certificato. Evitare qualunque affermazione di HTTP hard cap o 'nessun retry' fino a probe offline di trasporto effettivo.

## 3. Verifica in PyCharm

Controllare che `git status --short` sia vuoto, poi:
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_release_blueprint_offline.py" -v
```

**Attesi 18 test e OK; NON ANCORA CERTIFICATI.**

Non avviare API o accessi OOD. Dopo PASS, decidere come creare il journal scientifico *non sintetico* e il dispatcher unico con source-binding + release immutabile prima di fare alcun pilot, e verificare il G4A sui file originali GT-free. Gli output V1 e Sonnet V2 pilot sono frozen/storici, separati dalla nuova matrice.
