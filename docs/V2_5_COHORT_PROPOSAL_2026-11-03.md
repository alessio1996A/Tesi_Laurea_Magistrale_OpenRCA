# V2.5 — Coorte dei cinque agenti: proposta GT-free e controlli

**Data:** 3 novembre 2026  
**Stato:** CODICE DI SELEZIONE PRONTO PER TEST, COORTE **NON ANCORA CONGELATA**.  
**Branch:** \`feature/harness-v2-clean-2026-11-03\`.  
**Artefatti V1:** sempre immutati.

## 1. Esito V2.4 sui 32 run storici

L'audit Colab del 3 novembre ha riportato:

| Variante | Run | Legacy | Canonico 3 campi + cardinalita' + finestra | Task-aware richiesto dal benchmark |
|---|---:|---:|---:|---:|
| A1-R8 | 8 | 7 | 5 | **7** |
| A1_VERIFY (due coorti) | 16 | 15 | 10 | **15** |
| A1_VERIFY_ST | 8 | 8 | 5 | **7** |
| **Totale** | **32** | **30** | **20** | **29** |

Le tre non conformita' task-aware sono **due cardinalita' errate** (1 invece di 2 e 2 invece di 1) e **un campo richiesto mancante** (\`root cause reason\`). Gli **otto timestamp fuori dall'intervallo** sono una diagnostica temporale separata e non vengono contati come invalidita' di formato benchmark.

Il conteggio di 29/32 viene dalla modalità *audit*. Il nuovo report distingue anche \`task_aware_enforce_valid_total\`, che comprende un controllo sull'ordine cronologico per le task con data richiesta. **Finche' il nuovo report non e' eseguito, questo secondo numero e' ignoto.**

## 2. Protocollo proposto

- *Obiettivo:* confronto appaiato di **A0, A1_V2, A1-R8 (codice \`A1\`), A1_VERIFY e A1_VERIFY_ST** su una coorte development comune.
- *Campione proposto:* **8 casi**, 4 per cloudbed, selezione deterministica SHA-256 con seed fisso \`openrca-harness-v2-five-agents-2026-11-03-v1\`.
- *Output:* contratto uniforme \`v2_enforce\` e prompt task-aware GT-free per i cinque agenti.
- *Budget:* 6 round di tool massimi; A1_VERIFY/A1_VERIFY_ST con configurazione iniziale 4+2. **Non** cambiare contemporaneamente in 5+1: e' una ablation distinta.
- *Ripetizioni iniziali:* 1 per variante/caso, quindi **40 run previsti**. Una replica non consente di stimare la variabilita' stocastica. Eventuali repliche successive vanno preregistrate e svolte per tutte le varianti, non solo per quelle favorite.
- *Metriche di report:* score ufficiale solo dopo freeze, conformita' task-aware, warnings temporali, token, round di tool, verifiche svolte, tempo end-to-end, errori/provider.
- *Nessuna API nuova* e nessuna coorte definitivamente selezionata prima dei gate software.

## 3. Provenienza ed esclusioni

\`src/evaluation/v2_cohort_selector.py\` richiede:

1. **Split e manifest GT-free originali con SHA-256**.
2. Due file coorte V1: i loro 16 casi devono essere nel registro storico.
3. Registro storico dei **25 casi noti** del modulo A/2 \`network_kpi_inventory.py\` nel branch di analisi.
4. L'**inventario A/2 originale** \`network_kpi_inventory_v1.json\`, che deve contenere quattro finestre development e il seed noto. Il selettore ricostruisce le stesse quattro finestre con l'algoritmo deterministico originale e verifica anche gli ID development consumati.
5. Esclusione di tutti i casi gia' osservati e di **qualsiasi altra finestra che si sovrapponga sullo stesso cloudbed** a una finestra vista, anche se ha un ID diverso.
6. Esclusione delle finestre in sovrapposizione con gli altri split usando **soltanto i metadati del file split**, senza leggere esempi, etichette o telemetria evaluation/OOD.

**Importante:** il registro storico deve essere confermato per eventuali ulteriori esplorazioni precedenti non ancora annotate: se ne esistono, vanno aggiunte PRIMA del freeze. La separazione temporale rende meno probabile il riuso della stessa telemetria, ma non dimostra indipendenza causale/statistica tra incidenti.

Il risultato dello script è \`PROPOSED_NOT_FROZEN_NOT_EXECUTED\`: **una proposta da controllare**, non una lista definitiva di nuovi run.

## 4. Test offline PyCharm

\`\`\`powershell
git pull --ff-only origin feature/harness-v2-clean-2026-11-03
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_v2*.py" -v
\`\`\`

Attesi **55 test**: 14 contratto originario, 6 finestre V1, 7 audit freeze, 15 task-aware, 6 runner fake-LLM, 7 selezione coorte.

## 5. Colab: prima diagnostica dell'ordine cronologico

Rieseguire \`evaluation.v2_frozen_prediction_audit\` senza scoring e leggere:

\`\`\`python
print("Task-aware audit:", report["task_aware_valid_total"])
print("Task-aware enforce:", report["task_aware_enforce_valid_total"])
print("Errori enforce:", report["task_aware_enforce_invalid_reasons"])
\`\`\`

## 6. Colab: selezione GT-free V2 in sola lettura

\`\`\`python
import os, sys, json, subprocess
from pathlib import Path

repo = Path("/content/Tesi_OpenRCA_V2")
env = os.environ.copy()
env["PYTHONPATH"] = str(repo / "src")
inventory = Path("/content/network_kpi_inventory_v1.json")
assert inventory.is_file(), "Inventario A/2 assente: recuperarlo, NON inventarlo"
result = subprocess.run(
    [sys.executable, "-m", "evaluation.v2_cohort_selector",
     "--data-dir", "/content/drive/MyDrive/Tesi_OpenRCA",
     "--inventory", str(inventory), "--per-cloudbed", "4"],
    cwd=repo, env=env, text=True, capture_output=True, check=True,
)
proposal = json.loads(result.stdout)
print("Proposta:", proposal["status"])
print("Casi:", proposal["selected_cases"])
print("Run previsti:", proposal["planned_runs"])
print("Stato GT:", proposal["read_ground_truth"])
\`\`\`

Non esegue alcuna chiamata modello e non scrive file. Per congelare la coorte sarà necessario valutare il registro e il protocollo, creare un file in una cartella V2 distinta usando apertura *create-only*, stabilire hash e ordine dei run, e prevedere consenso alle API e budget di spesa.

## 7. Prima di giovedi' 5 novembre

Ordine vincolante: test offline → audit sui freeze + confronto enforce → ispezione proposta e copertura task → eventuale protocollo coorte → runner preregistrato e test fake LLM → autorizzazione esplicita ai modelli → run reali → freeze → scorer → interpretazione. Nessun passaggio successivo può essere dichiarato concluso in assenza dell'output reale e dei gate superati.
