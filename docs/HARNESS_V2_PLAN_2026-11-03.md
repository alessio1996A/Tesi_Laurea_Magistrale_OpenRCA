# Harness V2 — Piano di ricostruzione controllata (3–5 novembre 2026)

**Scopo:** uniformare contratto d'uscita, integrità temporale, test e confronti fra gli agenti OpenRCA preservando i risultati V1.

**Base immutabile:** commit `138fb523efec4a665a2424ab2faedb698f10562e`.  
**Branch V2:** `feature/harness-v2-clean-2026-11-03`.  
**Freeze V1 non sovrascrivibili:** primo studio A1-R8/A1_VERIFY (commit `6927fcfa18fc29fce64ad65eac98231b2ba42184`), secondo A1_VERIFY/A1_VERIFY_ST (commit `138fb523efec4a665a2424ab2faedb698f10562e`).

## Obiettivi di consegna desiderati per giovedì 5 novembre

| Gate | Obiettivo | Stato |
|---|---|---|
| V2.1 | Contratto JSON uniforme: chiavi, campi, timestamp Asia/Shanghai, cardinalità dalla sola istruzione GT-free | 12 test sintetici eseguiti in PyCharm: OK |
| V2.2 | Audit integrità delle due coorti V1: split, manifest, durata, overlap tra casi e piloti | 6 test sintetici eseguiti in PyCharm: OK; audit Colab reale ancora da eseguire |
| V2.3 | Audit offline delle predizioni congelate senza ripararle, inclusa conformità canonica | Codice audit 32 freeze + 6 test sintetici pubblicati; attendono verifica PyCharm e Colab |
| V2.4 | Nuova configurazione di esecuzione dei cinque agenti con medesimo contratto e metadata V2, test fake-LLM | Da completare dopo gate V2.3 |
| V2.5 | Coorte development V2 preregistrata, selezione senza finestre coincidenti con tutte le attività già viste | Da concordare e congelare dopo audit |
| V2.6 | Nuovi esperimenti reali A0/A1_V2/A1-R8/A1_VERIFY/A1_VERIFY_ST e confronto eventuale 4+2 vs 5+1 | Richiede consenso all'uso delle API, esecuzioni Colab, freeze e solo successivamente scoring |

**Il codice testato e il protocollo sono un obiettivo realistico a breve termine. Una campagna completa con API, scoring e repliche non deve essere dichiarata conclusa finché non è stata realmente eseguita e verificata.** Non ci sono operazioni in background.

## Regole metodologiche non negoziabili

1. **Non sovrascrivere** risultati, manifest di freeze, scoring, predizioni, commit sperimentali o protocolli V1: il loro contenuto deve rimanere auditabile.
2. **Niente accesso alla ground truth durante sviluppo e preregistrazione:** `record.csv`, `query.csv` e label fuori dall'harness, dalla scelta dei casi e dal planner. Scoring soltanto dopo freeze.
3. **Finestre [start_unix, end_unix)** in secondi, coerenti fra manifest, split e tool. Le date del JSON finale sono in ora locale `Asia/Shanghai`.
4. **Un caso V2 non deve sovrapporsi temporalmente ad altri casi scelti né alle finestre di pilot, batch o audit già consumati.** Il caso `cloudbed-2_q007` nel confronto V1 condivide esattamente la finestra del pilot `cloudbed-2_q006`. Non rimuoverlo dal risultato V1: documentare la limitazione.
5. **Il contratto JSON** verifica conformità di struttura, cardinalità richiesta e finestra; NON dimostra accuratezza causale. Su errore, mantenere `raw_response`, segnalare invalidità, non inventare diagnosi.
6. **Esperimenti appaiati:** stessi casi, stessa evidenza e modello, ordine dei bracci controllato, numero di repliche predefinito, output distinti, completezza token e tempo, scorer ufficiale dopo freeze.
7. **Un solo cambiamento alla volta:** uniformità del contratto per tutti gli agenti; planning 4+2 vs 5+1 come ablation separata; R03/R04/R05 non promosse senza validazione indipendente.
8. **Nessuna nuova chiamata Gemini automatica:** autorizzazione esplicita prima dell'esecuzione; interrompere su interruzioni e non ritentare automaticamente.

## File introdotti nella V2.1–V2.2

- `src/output/v2_contract.py`: `infer_requested_faults`, `validate_openrca_v2`, `audit_openrca_v2` (tutte funzioni offline).
- `src/tests/test_v2_contract.py`: test con JSON sintetici validi/invalidi e confini temporali.
- `src/evaluation/v2_case_window_audit.py`: audit in sola lettura dei due piani di studio originali.
- `src/tests/test_v2_case_window_audit.py`: test con split, manifest e piani artificiali, incluse finestre sovrapposte.

## Nuovo modulo offline di auditing delle 32 risposte storiche

- `src/evaluation/v2_frozen_prediction_audit.py`: verifica split, manifest, due piani congelati, due freeze SHA-256, tutti i risultati e le evidenze appaiate. Calcola per ciascuna risposta lo stato legacy e la conformità V2 **senza** correggere i JSON e **senza** leggere scoring/GT.
- `src/tests/test_v2_frozen_prediction_audit.py`: sei test su 32 output artificiali, alterazioni di hash, provenienza e JSON.
- Risultato sui 32 output **reali ancora da ottenere in Colab**; non attribuire esiti V2 prima di quella esecuzione.

## Test PyCharm

Da root del repository, sul branch V2:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_v2_contract.py" -v
python -m unittest discover -s src/tests -p "test_v2_case_window_audit.py" -v
python -m unittest discover -s src/tests -p "test_v2_frozen_prediction_audit.py" -v
```

## Colab: audit finestre senza Gemini

Dopo test PyCharm superati, sul repository V2 aggiornato:

```python
import os, sys, subprocess
from pathlib import Path
repo = Path("/content/Tesi_OpenRCA_V2")
env = os.environ.copy()
env["PYTHONPATH"] = str(repo / "src")
res = subprocess.run([
    sys.executable, "-m", "evaluation.v2_case_window_audit",
    "--data-dir", "/content/drive/MyDrive/Tesi_OpenRCA",
], cwd=repo, env=env, text=True, capture_output=True, check=True)
print(res.stdout)
```

Questo audit legge soltanto `split_market_v1.csv`, `benchmark_inputs_market.csv` e i due piani delle coorti già congelati. Aspettarsi la segnalazione della coincidenza fra `cloudbed-2_q006` e `cloudbed-2_q007`. Non modifica output.

## Criterio di fine progetto V2

Una nuova serie di risultati potrà sostituire **nelle conclusioni** la V1, **non sovrascriverla negli archivi**, soltanto dopo test, freeze, audit e scoring su una coorte documentatamente idonea. Anche uno score più basso rimarrà un risultato valido da riportare.
