# V2.6 — Preregistrazione e runner dei 40 esperimenti

Data: 3 novembre 2026. **Stato: strumenti implementati, non ancora testati in PyCharm né eseguiti su Colab.**

## Coorte verificata dal notebook (non ancora congelata)

| Caso | Task | Guasti richiesti |
|---|---|---:|
| cloudbed-1_q005 | task_2 | 1 |
| cloudbed-1_q066 | task_6 | 1 |
| cloudbed-1_q027 | task_7 | 2 |
| cloudbed-1_q013 | task_5 | 1 |
| cloudbed-2_q071 | task_4 | 2 |
| cloudbed-2_q020 | task_6 | 1 |
| cloudbed-2_q034 | task_1 | 1 |
| cloudbed-2_q024 | task_3 | 1 |

Criteri: 4+4 cloudbed, 7 task coperte, un multi-guasto per cloudbed, zero overlap con le finestre note di esperimenti precedenti e audit A/2. Solo development; la selezione non usa punteggi o etichette.

## I nuovi moduli

- `src/evaluation/v2_preregister.py`: costruisce il piano con 40 ID univoci; default **dry-run**, `--write` crea una sola volta un piano sotto `data/protocols/v2`, con hash e commit Git.
- `src/evaluation/v2_campaign_runner.py`: default **preflight** delle 40 run senza inferenza. L'esecuzione richiede **`--execute --run-id ... --confirm-api`** e permette una sola run per invocazione, senza batch/retry automatici.
- `src/tests/test_v2_preregister.py`: 6 test offline.
- `src/tests/test_v2_campaign_runner.py`: 7 test offline con runner finto, inclusi ordine preregistrato e provenance dei predecessori.

Il piano registra modello `gemini-3.5-flash-lite`, 6 round, 4+2 per A1_VERIFY e A1_VERIFY_ST, output `v2_enforce`, nome di ogni caso e suo timestamp ufficiale. Le cinque varianti sono A0, A1_V2, A1-R8 (internamente A1), A1_VERIFY, A1_VERIFY_ST. L'ordine viene ruotato per incidente, senza pretendere una randomizzazione perfetta. **Una replica per agente/caso non permette stime attendibili di variabilità tra run.**

Il runner controlla PRIMA della chiamata API il freeze, il commit Git, il manifest, il caso e il preprocessing GT-free. Crea un `claim` permanente immediatamente prima della chiamata API. Un crash lascia il claim per bloccare retry automatici potenzialmente fatturati. I risultati finiscono solo sotto `data/results/v2/openrca_harness_v2_five_agents_development_v1/`, un file JSON per run in creazione esclusiva, completo di `raw_response`, metriche e provenienza.

## Step A — Test obbligatori PyCharm (zero API)

```powershell
git fetch origin
git switch feature/harness-v2-clean-2026-11-03
git pull --ff-only origin feature/harness-v2-clean-2026-11-03
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_v2*.py" -v
```

Attesi **70 test**: 55 dei blocchi precedenti + 6 di preregistrazione + 9 del runner campagna. Tutti devono essere `OK`. Eseguire anche `python -m unittest discover -s src/tests -v` se il progetto ha dipendenze installate, ma NON avviare altri script con chiamate modello.

## Step B — Colab: preview del piano, senza scrivere nulla

Dopo l'esito positivo dei test:

```python
import os, sys, subprocess, json
from pathlib import Path

repo = Path("/content/Tesi_OpenRCA_V2")
data_dir = Path("/content/drive/MyDrive/Tesi_OpenRCA")
inventory = Path("/content/network_kpi_inventory_v1.json")

subprocess.run([
    "git", "-C", str(repo), "pull", "--ff-only",
    "origin", "feature/harness-v2-clean-2026-11-03"
], check=True)
assert inventory.is_file()

env = os.environ.copy()
env["PYTHONPATH"] = str(repo / "src")
p = subprocess.run([
    sys.executable, "-m", "evaluation.v2_preregister",
    "--data-dir", str(data_dir),
    "--inventory", str(inventory),
    "--repo-dir", str(repo),
], cwd=repo, env=env, capture_output=True, text=True, check=True)

plan = json.loads(p.stdout)
print("stato:", plan["status"])
print("run:", plan["run_count"])
print("git commit:", plan["git_commit"])
print("primo ordine:", plan["cases"][0]["ordered_variants"])
assert plan["run_count"] == 40
assert plan["status"] == "PREREGISTERED_NOT_EXECUTED"
```

Questa preview è in sola lettura, non è un freeze.

## Step C — Freeze del piano SOLO DOPO controllo della preview

Una volta confermati test, 40 run, registro storico e commit, eseguire una sola volta:

```python
p = subprocess.run([
    sys.executable, "-m", "evaluation.v2_preregister",
    "--data-dir", str(data_dir),
    "--inventory", str(inventory),
    "--repo-dir", str(repo),
    "--write",
], cwd=repo, env=env, capture_output=True, text=True, check=True)
print(p.stdout)
```

**Non avvia Gemini.** Il file piano è create-only in
`data/protocols/v2/openrca_harness_v2_five_agents_development_v1_plan_v1.json`.
Se già esiste, si ferma; non cancellare o sovrascrivere per forzare un nuovo freeze.

## Step D — Preflight di tutti i run, senza API

Dopo il freeze:

```python
p = subprocess.run([
    sys.executable, "-m", "evaluation.v2_campaign_runner",
    "--data-dir", str(data_dir), "--repo-dir", str(repo),
], cwd=repo, env=env, capture_output=True, text=True, check=True)
report = json.loads(p.stdout)
print(report["status_counts"])
# Prima di qualsiasi run:
# {"ready": 8, "waiting_for_previous_variant": 32}
print(report["plan_sha256"])
```

## Step E — Esecuzioni REALI (NON ANCORA AUTORIZZATE)

Richiedono autorizzazione esplicita all'uso delle API e verifica del budget. Ogni run richiede un run ID esatto e flag `--execute --confirm-api`. Non includiamo qui alcuna cella che avvii chiamate per errore. Prima di eseguire la campagna completa, verificare le dipendenze e il preflight in sola lettura, quindi registrare l'approvazione dell'utente al costo.

## Gate scientifici prima dello scoring

- Il contratto `v2_enforce` non fa retry LLM; i fallimenti JSON devono restare contabilizzati.
- Nessun test di scorers o ground truth durante sviluppo/preregistrazione. `evaluation` e `ood_holdout` non vengono usati.
- Ogni run ha output e claim separati; i run non ripresi automaticamente.
- Non si dichiara la campagna conclusa senza 40 output ispezionati, hash congelati e scoring ufficiale successivo al freeze.
- Il confronto 4+2 contro 5+1 è un esperimento successivo e separato; non fa parte dei 40 run.

## Verifica aggiuntiva dell'ordine di esecuzione

Il runner ora blocca un agente quando il precedente dello stesso incidente non e' completo. Prima della chiamata API verifica claim, file JSON e provenienza del precedente, hash del piano e `integrity_issues=[]`. Una nuova campagna completamente vergine mostra **8 run `ready`** (il primo agente di ogni incidente) e **32 `waiting_for_previous_variant`**. Le run vanno lanciate una alla volta nell'ordine preregistrato per ogni incidente. Non vengono mai effettuati retry automatici.

Se la preview precedente mostrava il commit `adfc005c738077e0bc2c2b6d928eadbd751c31b8`, quello era valido prima di questi controlli aggiuntivi: **ripetere il pull e la preview**; il freeze deve identificare il nuovo commit HEAD.

## Correzione successiva V2.6A — NON usare il freeze originario

Il primo tentativo A0 sul protocollo ..._v1 si e' arrestato **prima del claim e prima di Gemini**, per un controllo SHA errato: A0 non ha report deterministico e quindi ha `evidence_sha256=None`. Il codice e' stato corretto e il protocollo e' stato versionato **`openrca_harness_v2_five_agents_development_v2`**: un **nuovo** piano create-only, con commit Git e SHA differenti, va generato prima del primo run. **Non sostituire, eliminare o modificare il piano congelato ..._v1**. La correzione e i controlli sono documentati nel [rapporto V2.6A](V2_6A_A0_SHA_REVISION_2026-11-03.md). I test attesi sono ora **70** e il file piano corretto e' `data/protocols/v2/openrca_harness_v2_five_agents_development_v2_plan_v1.json`.

## Revisione V2.6B — Non usare i run ID del freeze v2

Il tentativo A0 sul protocollo `..._v2` si e' arrestato **dopo aver creato il claim, ma prima della chiamata Gemini** per `ModuleNotFoundError: langchain_google_genai`. Il pacchetto e' già presente in `requirements.txt`, ma non installato su Colab. **Non cancellare il claim e non ripetere il run ID v2.** La revisione `..._v3` controlla gli import del provider prima del claim e dispone di una nuova cartella run/freeze: [rapporto e procedura V2.6B](V2_6B_DEPENDENCY_RECOVERY_2026-11-03.md). Prima del nuovo freeze installare i requirements nel runtime Colab e verificare **71 test**. I vecchi esempi di questo runbook sono storici e non vanno eseguiti sul protocollo v2 già occupato.
