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
| V2.3 | Audit offline delle predizioni congelate senza ripararle, inclusa conformità canonica | Audit reale eseguito: 30/32 legacy; 28/32 canonico struttura/cardinalità; 20/32 anche entro finestra; controllo temporale separato confermato |
| V2.4 | Output conforme al task + integrazione nei cinque agenti e test fake-LLM | Audit Colab eseguito: 29/32 task-aware; controllo enforce cronologico e test locali ancora da confermare |
| V2.5 | Proposta development V2 bilanciata per task, cardinalità e cloudbed | Colab ha confermato 8 ID GT-free; selettore versionato aggiornato; test PyCharm e riesecuzione Colab da confermare; NON congelata |
| V2.6 | Preregistrazione e runner in sicurezza per cinque agenti (40 run); ablation 5+1 separata | Strumenti dry-run/freeze create-only/runner una run alla volta pubblicati; 68 test attesi, ancora da verificare, nessuna API o freeze eseguito |

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
- `src/tests/test_v2_frozen_prediction_audit.py`: sette test su 32 output artificiali, alterazioni di hash, provenienza e JSON.
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

## V2.4 — Contratto per task e runner comune

[Documentazione dell'integrazione V2.4](V2_4_TASK_AWARE_RUNNER_2026-11-03.md). Le sette task richiedono sottoinsiemi differenti delle tre chiavi RCA. La V2 distingue campi richiesti, ordine, cardinalità e warning sul timestamp fuori dalla finestra; le modalità v2_audit e v2_enforce sono opt-in e il default legacy rimane immutato. Prima di nuovi run: eseguire i test in PyCharm e confermare l'audit task-aware sui freeze V1.

## Evidenza audit reale e scomposizione multilivello

[Nota dei risultati V2.3 (32 run)](V2_3_REAL_FROZEN_AUDIT_2026-11-03.md). Il nuovo audit distingue conformità rigorosa di schema/cardinalità dal controllo temporale aggiuntivo, senza modificare i vecchi freeze. Il requisito di confinare il timestamp di diagnosi alla finestra va trattato come **policy interna di plausibilità** finché non sia verificato come obbligo del benchmark.

## Nuova evidenza task-aware e selettore V2.5 — 3 novembre

La conformità **task-aware** nei due esperimenti storici è **29/32**: due problemi di cardinalità e un campo obbligatorio mancante. Il codice distingue inoltre la conformità in modalità enforce (che controlla anche l'ordine cronologico dei task con data) nel campo `task_aware_enforce_valid_total`; questo valore richiede la nuova esecuzione Colab.

Il [piano V2.5](V2_5_COHORT_PROPOSAL_2026-11-03.md) introduce una proposta di **otto casi development**, quattro per cloudbed e cinque agenti (40 run ipotizzati). Prima di congelarla è necessario verificare gli hash, le quattro finestre dell'audit A/2, tutti i 25 casi storici censiti e gli eventuali altri casi osservati. Il codice non consulta score, etichette o telemetria; la proposta non significa che le API siano autorizzate.

## V2.6 — Nuovi strumenti preregistrazione e runner

Il [runbook operativo V2.6](V2_6_PREREGISTRATION_RUNBOOK_2026-11-03.md) contiene test, preview senza scritture, freeze create-only e preflight, con esecuzione API disattivata per default. Sono pubblicati `evaluation.v2_preregister` e `evaluation.v2_campaign_runner` con **13 test offline nuovi**, portando il totale atteso a **68**. Il protocollo resta non congelato finché non sono stati superati i test e verificata la preview; non sono stati eseguiti modelli o nuovi score.

Il runner V2.6 ora applica il vincolo sull'ordine dei cinque agenti per incidente: prima della chiamata API verifica i risultati e la provenienza dei predecessori. Una campagna vergine ha 8 run ready e 32 waiting_for_previous_variant. Non congelare anteprime prodotte da commit precedenti a questo aggiornamento: rieseguire test e preview sul commit Git finale.

## Correzione V2.6A del tentativo A0 pre-API

Il primo avvio A0 sul freeze `..._v1` ha trovato un bug nel controllo SHA del preprocessing: la baseline A0 ha `evidence_sha256=None` per definizione. La verifica e' fallita prima del claim e di Gemini. Vedi [rapporto di revisione](V2_6A_A0_SHA_REVISION_2026-11-03.md). Il piano originale resta intatto; nuovo protocollo `openrca_harness_v2_five_agents_development_v2`, nuovo file freeze, 70 test offline attesi. Nessuna delle 40 run v1 e' stata eseguita dal tentativo fallito.

## Ripresa da V2.6B — dipendenza modello

Nel primo run A0 del freeze `..._v2`, il runner ha creato un claim permanente ma ha fallito l'import `langchain_google_genai` prima del grafo e della richiesta Gemini. Il `requirements.txt` contiene gia' il pacchetto `langchain-google-genai`, da installare nel runtime Colab. Il piano v2 e il claim v2 vanno conservati come audit trail. Il nuovo protocollo `openrca_harness_v2_five_agents_development_v3` prepara un distinto freeze con stesse condizioni sperimentali e guardia delle dipendenze **prima** del claim. Serve una nuova conferma di **71 test**, preview e SHA prima del primo run. Vedi [resoconto V2.6B](V2_6B_DEPENDENCY_RECOVERY_2026-11-03.md).
