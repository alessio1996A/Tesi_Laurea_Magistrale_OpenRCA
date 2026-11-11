# RQ2 — Preflight GT-free di un piano D/C/K NON eseguibile

**11 novembre 2026**  
**Stato: BOZZA, non approvata né congelata. Zero chiamate Gemini/Claude, zero file risultati o piani persistiti.** Il presente documento NON autorizza un pilot, un test della generalizzazione o la modifica della fase RQ1.

## 1. Evidenze già verificate

- Partizione V1 valutata realmente in Colab al commit `f3382d43d80bd82d400749fbf5315ccc8b63ea89`: 4 discovery e 11 test, suddivisi in 4/10 gruppi di finestra; distribuzione 2+2 discovery fra cloudbed, gap minimo 5400 s nello stesso cloudbed, nessuna coppia cross-phase entro un'ora.
- **Discovery candidata:** `cloudbed-1_q032`, `cloudbed-1_q050`, `cloudbed-2_q026`, `cloudbed-2_q045`.
- **Test candidato:** `cloudbed-1_q014`, `cloudbed-1_q021`, `cloudbed-1_q030`, `cloudbed-1_q059`, `cloudbed-2_q014`, `cloudbed-2_q021`, `cloudbed-2_q040`, `cloudbed-2_q041`, `cloudbed-2_q058`, `cloudbed-2_q076`, `cloudbed-2_q077`.
- La coppia `cloudbed-1_q014` e `cloudbed-1_q030` ha finestra sovrapposta e resta interamente in test.
- Le sorgenti congelate sono `split_market_v1.csv` SHA256 `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724` e `benchmark_inputs_market.csv` SHA256 `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`.
- Contratti C e K: **16 test sintetici** superati in PyCharm. Bundle delle evidenze: **14 test sintetici** superati. Adapter offline D→C/K: **14 test sintetici** superati secondo il più recente output dell'utente `Ran 14 tests in 0.009s — OK`. Nessuna verifica su output LLM reale ancora eseguita.

## 2. Nuovo piano dry-run e dimensioni logiche

`src/evaluation/rq2_dryrun_plan.py` usa SOLO `inventory_ood` e i metadati del manifest GT-free. Non importa né apre `Market.zip`, `record.csv`, `query.csv`, `scoring_points` o output di scoring. Convalida SHA degli input nel percorso CLI reale e controlla che:
- 15 query della sola coorte `ood_holdout` siano allocate una volta in discovery/test;
- nessun gruppo di finestre sovrapposte venga diviso;
- nessun gap discovery–test nello stesso cloudbed sia minore o uguale a un'ora;
- numero di casi e gruppi corrisponda alla V1 e gli ID rimangano quelli già documentati.

Dimensioni **proposte, non approvate**: 15 query × 2 harness (`A1`, `A1_8R`) × 3 modelli logici (`gemini`, `sonnet`, `haiku`):
- **90 stage D** (RCA originale; fino a sei round di tool; uno stage D può comprendere numerose chiamate LLM);
- **90 stage C** (probe causa senza tool e con bundle evidenze);
- **24 stage K** (proposta regola sui soli 4 discovery ×2 harness ×3 modelli);
- **204 stage logici totali**. **NON sono 204 chiamate API**, né una stima in USD.
- Stage D→C→K dipendenti: K presente *solo* sulle discovery. In test sono previsti soltanto D→C.
- Non sono stati fissati provider model IDs, temperature/output limits, disponibilità tool reali, costo, max spesa o condizioni di retry. `can_execute_api=false`, `api_budget_approved=false`, `preview_only=true`, `status=DRAFT_NOT_EXECUTABLE`, tutti gli stage `BLOCKED_DRAFT`.
- Un **ulteriore blocco inter-fase**, da implementare nel futuro runner effettivo, impedirà l'accesso a D/C del test finché regole e criteri ricavati dalle discovery non saranno congelati. L'anteprima NON è un sistema di autorizzazione.

## 3. Validazione e source assurance

La funzione pura `make_workflow_preview` accetta metadati da un chiamante e verifica coerenza e i digest *dichiarati*, perciò marca `source_verified=false`: i valori SHA passati dai test sintetici non dimostrano l'autenticità dei byte originali.

Il wrapper reale `preview_market` richiama `inventory_ood(..., verify_original_hashes=True)`, che calcola SHA256 dei due CSV, verifica schemi senza etichette e confronta gli hash congelati. **Solo qui** il sommario marca `source_verified=true`.

Nessun piano è scritto su Drive. Il futuro piano **create-only** avrà un protocol ID nuovo, versione, SHA del codice e dei prompt, schema di run, stima costi, verifica del freeze e autorizzazione separata: prima di ciò non eseguire i passaggi.

## 4. Artefatti e ordine

- `src/evaluation/rq2_dryrun_plan.py`: preflight e enumerazione **in memoria**.
- `src/tests/test_rq2_dryrun_plan.py`: **15 test sintetici** predisposti per GT exclusion, hash, stage K solo discovery, dipendenze, gruppo multi-fault, spaziatura temporale, completezza, blocco API e determinismo. **Non ancora eseguiti dall'utente.**
- `notebooks/Colab_RQ2_DryRun_Workflow_Preflight_2026_11_11.ipynb`: unica cella di lettura dei due CSV GT-free, controllo degli SHA e stampa **solo il sommario**, senza scrivere file. Da eseguire **dopo** i 15 test PyCharm.

**Prossimo comando in PyCharm:**
```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_dryrun_plan.py" -v
```

## 5. Limiti e decisioni aperte

La partizione V1 rimane una candidata, non una validazione causale dell'indipendenza fisica delle iniezioni. L'esperimento è esplorativo con 2/2/3/4 positivi di test per le quattro classi. Non implementiamo human-in-the-loop, installazione automatica delle regole, o generazione/esecuzione di codice da pseudocode. **Prima di qualsiasi API a pagamento** saranno necessari runner isolato, salvataggio create-only, controllo delle evidenze reali, budget, congelamento regole, test mock e consenso esplicito dell'utente.
