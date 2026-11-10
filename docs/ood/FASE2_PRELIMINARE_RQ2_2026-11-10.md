# Fase 2 — preflight del knowledge transfer (10 novembre 2026)

> Documento **preliminare**, non preregistrazione della campagna e non autorizzazione a chiamate API. La prima domanda sperimentale è stata dichiarata conclusa dal relatore. Il commit sorgente EVALUATION20 è `e4845e7fe9a399e10dd2db6f320dfeaeeddf3379` e rimane congelato.

## Scopo scientifico

Verificare se su guasti non codificati nel rule engine l'agente con harness (1) identifica una diagnosi, (2) la spiega tramite evidenze verificabili e (3) può proporre una **pseudoregola deterministica candidata**. La successiva verifica della regola su casi indipendenti è una domanda distinta. Non si modifica il modello né si sostiene che un tipo di guasto non sia mai stato nel pretraining.

## Decisione operativa preliminare

- **Prima** inventario senza GT, nessuna LLM: split Market 148 query già congelato; valori attesi: development 92, evaluation 23, mixed_quarantine 18, ood_holdout 15.
- **15 query OOD non significa 15 incidenti fisici indipendenti.** Controllare la sovrapposizione di finestre e provenienza. Il numero di classi OOD riservate è quattro; l'inventario GT-free NON attribuisce classi.
- **Poi** progettare la separazione discovery/test usando protezioni contro il leakage. Il conteggio per classe potrebbe richiedere un audit delle etichette *separato e non accessibile al ramo di inferenza*; non scegliere gli incidenti in base a quanto siano facili per l'agente.
- **Modelli:** iniziare operativamente da Gemini per il pilot tecnico, poi Sonnet e Haiku; per il confronto finale stesso piano congelato, stesse query e stesse metriche nei limiti degli errori provider. Se Gemini serve per modificare l'harness, quei casi diventano development e non devono essere venduti come test indipendente.
- **Metriche distinte:** score ufficiale Microsoft per la diagnosi; valutazione indipendente della spiegazione, dei KPI citati e della pseudo-regola; falsi positivi/negativi e possibilità di astensione del rule engine. Non fare valutare una pseudo-regola unicamente all'LLM che l'ha proposta.
- **Limite di ambito:** human-in-the-loop, email al supervisore e integrazione/auto-installazione delle regole sono future work secondo le trascrizioni del relatore. Nessun router automatico in produzione è imposto da questa fase.

## Prima attività: audit offline

Il codice `src/evaluation/ood_holdout_preflight.py` legge soltanto:

- `MyDrive/Tesi_OpenRCA/data/processed/split_market_v1.csv`
- `MyDrive/Tesi_OpenRCA/data/processed/benchmark_inputs_market.csv`

Verifica SHA dei due file contro i digest preregistrati e schemi chiusi, segnala conteggi, cloudbed, task, gruppi di finestre sovrapposte e overlap fra OOD e altri split. **Non** legge `Market.zip`, `query.csv`, `record.csv`, risultati precedenti, scoring o inferenze. Il report esce su stdout senza essere scritto in Drive.

### PyCharm (prima Colab)

```powershell
git status
git fetch origin
git switch --track origin/feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_ood_holdout_preflight.py" -v
```

Se il branch esiste già localmente, usare `git switch feature/ood-knowledge-transfer-audit-2026-11-10` e `git pull --ff-only`; non forzare switch o reset quando ci sono modifiche locali.

### Colab (solo dopo test PyCharm)

Notebook: `notebooks/Colab_OOD_GTFree_Preflight_2026_11_10.ipynb`. Unica cella di esecuzione, monta Drive in lettura logica (il mount non esegue modifiche ai dati della tesi), clona il branch in **cartella locale separata** `/content/Tesi_OpenRCA_OOD_Audit`, esegue lo script e stampa JSON. Non richiede chiavi e non chiama Gemini/Claude.

**Attenzione:** l'audit non risponde ancora a quante istanze di ogni classe siano disponibili: quel passo richiede un controllo separato della tassonomia e dei vincoli, prima del protocollo di inferenza.

## Provenienza e integrità

- Base del branch: commit sperimentale congelato `e4845e7fe9a399e10dd2db6f320dfeaeeddf3379`.
- Documenti delle trascrizioni e approvazione relatore: branch `docs/evaluation20-relatore-2026-11-09`, cartella `docs/relatore_2026-11-10/`.
- Regole implementate: otto. I quattro tipi riservati nelle note sono `node CPU spike`, `container write I/O load`, `container process termination`, `container packet loss`; verificarli su fonti di tassonomia senza introdurre etichette nei prompt o nell'audit GT-free.
- Nessun nuovo risultato OOD rivendicato, nessun esperimento avviato, nessuna chiamata a pagamento autorizzata.
