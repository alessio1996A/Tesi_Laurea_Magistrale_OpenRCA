# RQ2 — Audit della presenza KPI nelle finestre development

**12 novembre 2026** — **Codice e notebook predisposti, test PyCharm ancora da eseguire, Colab non ancora eseguito**. Nessuna API o scrittura sperimentale.

## 1. Motivazione

I **19 test sintetici del catalogo source-only** `test_rq2_kpi_formalizability_preflight.py` sono stati eseguiti dall'utente con `Ran 19 tests in 0.032s — OK`. Questo conferma la funzione di inventario dei **29 nomi di KPI già presenti nel codice**, non l'effettiva presenza dei segnali nelle finestre Market.

Il preflight aggiuntivo `src/evaluation/rq2_development_kpi_audit.py` verifica **solo i campioni numerici dei KPI delle metriche node/container all'interno delle finestre development**, senza modificare le otto regole RQ1 né aprire i file `record.csv` e `query.csv`. Non confronta con etichette, diagnosi, predizioni o score.

## 2. Sorgenti e isolamento

- Verifica SHA-256 **esatti** dei due CSV già congelati (questo NON include il controllo dell'hash completo di `Market.zip`): `split_market_v1.csv` e `benchmark_inputs_market.csv`. Rifiuta schema modificato con colonna GT, ID disallineati, split non previsti e numero di 92 casi development diverso dall'inventario originale.
- Rifiuta qualsiasi **overlap temporale** fra una finestra development e una `ood_holdout` nello stesso cloudbed.
- Genera esclusivamente percorsi ZIP `Market/{cloudbed}/telemetry/{YYYY_MM_DD}/metric/metric_node.csv` e `metric_container.csv`; rifiuta file mancanti e ZIP con duplicati dei membri interessati.
- Usa le finestre ufficiali `[start_unix,end_unix)` con timezone `Asia/Shanghai`, come nel codice RQ1; per ogni membro ZIP considera l'**unione** degli intervalli development, così una riga numerica appartenente a più finestre development non viene contata due volte.
- Non restituisce righe, valori campionati, singoli ID di caso, diagnosi, score, cause o mapping KPI→guasto. Restituisce solo conteggi aggregati e un campione limitato di nomi di KPI non presenti nel catalogo source-only.

### Precisazione importante sui CSV giornalieri condivisi

**Un membro ZIP giornaliero può contenere anche righe temporali di split diversi**. L'audit deve materialmente leggere il flusso di queste righe per applicare il filtro: non sarebbe corretto dichiarare «zero byte OOD letti» sul piano I/O. Il codice invece garantisce che **soltanto le righe con timestamp appartenenti all'unione delle finestre development vengano impiegate per i conteggi**; il resto non entra nel report e non viene mostrato a modelli o runner. Un guardiano ulteriore rifiuta sovrapposizione development/OOD. Questo distinguo è registrato con i flag `full_daily_metric_csv_members_streamed=true`, `possible_non_development_rows_decoded_from_shared_csv=true`, `statistics_only_development_windows=true`, `read_ood_telemetry_for_analysis=false`.

Se la metodologia definitiva richiedesse invece isolamento **fisico a livello di file** senza nemmeno decodificare righe extra development, il preflight dovrebbe essere eseguito in un processo fidato che materializzi preventivamente una vista redatta e verificata o usare membri archive con intera giornata non OOD; non falsificare la dichiarazione di accesso.

## 3. Che cosa misuriamo e cosa NON misuriamo

Report aggregato per KPI source-only: disponibilità di almeno una riga numerica nei development; numero di righe numeriche osservate, differenziato per node/container; numero di nomi KPI ulteriori osservati solo nello sviluppo, senza sostenere che siano assenti altrove.

Tutti gli indicatori di `market_unit_verified`, `counter_or_rate_semantics_verified` e `catalog_physically_verified` rimangono **false**. La presenza di `system.cpu.pct_usage`, per esempio, non basta a certificare l'unità **%**, né permette di affermare una causa. Una nuova regola resta solo una candidata; l'eventuale specifica su `raw_value` e aggregazioni consentite va ancora congelata e convalidata prima del test.

L'analisi **non** verifica disponibilità sulle 15 query OOD; non deve usarle per adattare KPI, soglie, prompt o detector.

## 4. Nuovi file e ordine di esecuzione

- `src/evaluation/rq2_development_kpi_audit.py` — modulo read-only e API-free, con CLI `--data-dir`. In esecuzione reale la verifica degli hash è obbligatoria; lo switch `_synthetic_test_fixture` è solo interno ai test e imposta `source_verified=false`.
- `src/tests/test_rq2_development_kpi_audit.py` — **17 test sintetici predisposti, non ancora eseguiti**, incluso filtro delle righe OOD dallo scoring, unione finestre, conteggi non numerici, membri ZIP consentiti, file assenti/duplicati, tampering di split/manifest e filtro dei dati in output.
- `notebooks/Colab_RQ2_Development_KPI_Presence_Audit_2026_11_12.ipynb` — notebook a **una sola cella Python** che monta Drive, ripristina branch e invoca l'audit. **Eseguire solo dopo suite PyCharm verde.** Non scrive alcun output file né chiama modelli.

Comando PyCharm (PowerShell, root repository):

```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_development_kpi_audit.py" -v
```

**Attesi 17 test, non ancora confermati**. Dopo l'esito si potrà eseguire il notebook in Colab e discutere disponibilità numerica e segnali non presenti nel source-only catalog. Il runner D/C/K mock e la persistenza create-only rimangono i blocchi implementativi successivi; nessuna API senza freeze e autorizzazione.
