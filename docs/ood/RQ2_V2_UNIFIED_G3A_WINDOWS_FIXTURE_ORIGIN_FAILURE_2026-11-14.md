# RQ2-V2 unificata — G3A: fallimento 19-test e correzione fixture tool origin

Data: 14 novembre 2026. Stato: test corretti sul branch, **nuovo esito NON ancora verificato da PyCharm**. Non confondere con G1 (25/25 PASS) e G2 (9/9 PASS).

## Output autentico del primo gate G3A (Windows/PyCharm)

Comando:
```powershell
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_synthetic_journal.py" -v
```
Esito fornito dall'utente:
```text
Ran 19 tests in 121.164s
FAILED (failures=1, errors=6)
```
La suite di 19 metodi conteneva un test parametrico di 15 arm che ha prodotto **6 ERROR** per tutte le combinazioni (3 modelli × 2 harness) di `A1_8R_Planning` e `A1_PAVE`, oltre a **1 FAIL** `27 != 45` nel conteggio dei record. Gli altri 9 arm avevano 27 stage registrati; il conteggio fallito era effetto secondario dei sei errori.

Errore di riferimento:
```text
evaluation.rq2_v2_unified_synthetic_journal.UnifiedRQ2JournalError:
D status/provenance/output mismatch
```

## Diagnosi della causa (code review)

- `rq2_v2_unified_provenance_gate.audit_captured_v2_d` richiede per i due harness Planner/PAVE una origine nativa esplicita `"origine": "llm"|"planner"` su ogni tool call/result. È un vincolo corretto, **da non allentare**.
- `test_rq2_v2_unified_synthetic_journal.fake_run` aveva generato una traiettoria sintetica con tool ID, ma **senza origine** per tutti gli harness. Questo e' consentito dal modello ReAct V2 ma **non** dal grafo `verify_graph` con planner. Nessun provider reale o grafico `verify_graph` era in esecuzione in questo test: e' un difetto della fixture.
- La prova G2 che attraversava realmente Planning/PAVE via `run_experiment` e ToolNode aveva superato il proprio gate 9/9 in PyCharm. Il guasto G3A non ne invalida il risultato.

## Patch applicata (solo file di test)

`src/tests/test_rq2_v2_unified_synthetic_journal.py`:
- `fake_run()` continua a creare tool call/result con ID nativi, ma per `A1_8R_Planning` e `A1_PAVE` aggiunge a entrambi `"origine": "llm"`, rappresentando una esplorazione sintetica autentica del planner graph.
- Per A0/A1/A1_8R resta la versione ReAct senza origine esplicita; il bundle ammette l'origine `unknown` solo per i non-planner.
- Nuovo test negativo: rimuove intenzionalmente l'origine a entrambi i Planning/PAVE e verifica che `RECORDED_COMPLETE` continui a essere rifiutato, con i claim rimasti orfani e senza retry.
- **Nessuna modifica ai grafi**, al modulo production D, a `rq2_v2_unified_provenance_gate`, a `rq2_v2_unified_synthetic_journal`, ai source frozen RQ1/V1, alle regole, ai prompt, o alle evidenze Market.
- I metodi della suite passano da **19 a 20**, non ancora certificati.

## Prestazioni: blocco distinto dalla correttezza

La durata originale **121.164 s** per 19 metodi e 27 stage salvati (più tentativi di test) è troppo alta per un journal sintetico. Le `audit_restart` integrali e le verifiche SHA/provenance dei parent sono ripetute su ogni claim e record: causa plausibile di costo crescente (da profilare, **non ancora misurata come causa certa**). Dopo il nuovo gate, ottimizzare l'efficienza **senza togliere controlli o creare condizioni di race**; non adottare soglie arbitrarie o cronometrare i test con assert flaky. Non iniziare la campagna da 180 stage prima di risolvere il problema operativo.

## Prossimo step su PyCharm

```powershell
git status --short
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_synthetic_journal.py" -v
```
Output atteso: `Ran 20 tests`, `OK`. Richiedere l'output utente completo: il risultato non e' ancora attestato.

**G3 complessivo NON concluso**: manca ancora il percorso unico fake `run_experiment→claim→record D→C→K` e il source-bound release/dispatcher reale (G3B). OOD 11 locked; API 0; GT 0; real Drive writes 0.
