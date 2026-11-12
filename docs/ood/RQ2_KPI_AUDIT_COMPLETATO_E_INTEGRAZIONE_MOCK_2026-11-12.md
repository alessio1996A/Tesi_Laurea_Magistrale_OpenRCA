# RQ2 — Audit numerico development completato, integrazione D/C/K mock-only

**12 novembre 2026** · **Audit Colab REALE completato; integrazione mock predisposta, ancora da testare in PyCharm.**  
Branch: `feature/ood-knowledge-transfer-audit-2026-11-10`.

## 1. Risultati REALI dell'audit Colab

Il notebook `Colab_RQ2_Development_KPI_Presence_Audit_2026_11_12.ipynb` è stato eseguito dall'utente al commit `773f86d21c2e1d44473e4d077746d2d36733e50d`. Output ricevuto:

| Indicatore | Osservato |
|---|---:|
| Finestre/casi development | **92** |
| Membri node/container del Market.zip attraversati | **8** |
| Righe nelle unioni delle finestre development | **6.722.921** |
| Righe numeriche valide in tali finestre | **6.722.921** |
| KPI osservati con valori numerici, distinti per layer | **123** |
| KPI già elencati in codice e riscontrati con numeri | **29/29** |
| Nuovi nomi KPI rispetto al catalogo source-only | **94** |
| Ulteriori nomi elencati a output | **60** (34 omessi) |
| Righe numeriche node | **785.445** |
| Righe numeriche container | **5.937.476** |

Il controllo delle sorgenti ha confermato gli SHA dei **due CSV GT-free**, non dell'intero `Market.zip` (`market_archive_sha256_checked=false`).

**Isolamento:** le righe usate per aggregare appartengono soltanto alle finestre development. Per filtrare si è dovuto scorrere membri CSV giornalieri che possono fisicamente contenere righe di altri split: questa decodifica non è lettura esclusiva dei byte development, ma nessun altro split è usato per i conteggi né presentato a un modello. `read_ground_truth=false`, `read_record_csv=false`, `read_scoring=false`, `read_model_predictions=false`, `model_api_calls=0`, `files_written=false`.

**Non dedurre:** la presenza di 29/29 nomi nelle unioni delle finestre development non equivale alla disponibilità su ciascuno dei 92 casi o sulla coorte OOD; 123 nomi non equivalgono a 123 detector, 94 metriche extra non sono 94 unità fisiche verificate. Nessun KPI è stato attribuito a una fault class riservata. Lo split 4 discovery/11 test è invariato e ancora candidato.

## 2. Perché adesso verificare un flusso mock completo

Il codice già predisposto ha componenti isolati:
- `rq2_dryrun_plan.py` — 204 stage D/C/K non eseguibili;
- `rq2_stage_binding.py` — associa input C/K a D, caso, modello, harness e fase;
- `rq2_evidence_bundle.py` / `rq2_probe_adapter.py` — evidenze citabili e richieste C/K;
- `rq2_output_contracts.py` — validazione JSON dei risultati C/K;
- `rq2_kpi_formalizability_preflight.py` — certifica solo nomi presenti nel codice, MAI unità/soglie o regole pronte;
- `rq2_mock_journal.py` — ricevute **solo mock** create-only, gate test bloccato prima del freeze **mock**.

Serve la prova di **integrazione**: il medesimo D sintetico passa a C, produce una C strettamente valida che cita soltanto E### osservate, quindi K solo in discovery; gli stage vengono salvati tramite il journal mock solo dopo la validazione di tutti gli input. Non deve esserci alcun percorso per trasformare una conferma mock in autorizzazione a una API.

## 3. Modulo predisposto

`src/evaluation/rq2_mock_pipeline_integration.py`:
- `validate_mock_dck_without_io(...)`: verifica off-line un D sintetico, la sua C, e la sua K per discovery (oppure D/C su test). Rifiuta evidenze inesistenti, combinazioni case/model/harness non consentite, K sul test, JSON incompleto e piano non eseguibile alterato. Non salva file, non invoca modelli.
- `record_mock_stages(...)`: usa **esclusivamente** l'esistente `RQ2MockJournal` su directory temporanea dell'utente, per creare ricevute mock D/C/K con `O_EXCL` e digest, dopo aver validato gli input. Non registra le risposte sintetiche né esegue il vero agente. Il journal blocca i test senza freeze **MOCK_ONLY_NOT_RULE_FREEZE**.
- Il report d'integrazione mantiene `model_api_calls=0`, `can_execute_api=false`, `ready_for_test=false`, `rule_executed=false`; le ricevute create-only non sono risultati scientifici.
- **Limiti dichiarati:** nessuna verifica dell'istruzione originale contro i byte effettivi del manifest, nessun freeze degli ID dei modelli, nessuna chiamata ai provider, nessun catalogo KPI fisico verificato, nessun nuovo detector.

`src/tests/test_rq2_mock_pipeline_integration.py`: **16 test sintetici predisposti e NON ANCORA ESEGUITI** (solo `TestCase.test_*`); casi positivi D/C/K, scrittura create-only, rifiuto duplicati, blocco test senza freeze mock, rifiuto di evidence IDs fittizi, errori provider D simulati, K JSON non valido e pseudocodice mai eseguito.

## 4. Esecuzione successiva in PyCharm

```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_mock_pipeline_integration.py" -v
```

Attesi **16 test**; **non affermare che sono riusciti** prima dell'output dell'utente.

## 5. Che cosa manca ancora per la campagna reale

Il **runner API** non è stato implementato o autorizzato. Una prova mock di D/C/K non certifica né il funzionamento del provider né la formazione di pseudoregole K, ma riduce il rischio di confusione fra le fasi e di perdita di provenienza. Per i nuovi esperimenti reali restano obbligatori: ID modello e parametri fissati, budget, politica di gestione errori, persistenza create-only effettiva del contenuto, verifica hash sorgenti per run, isolamento del GT, gate di freeze scientifico sulle K prima dei test, catalogo KPI operativo con unità e trasformazioni esplicitamente trattate, e consenso esplicito a qualunque spesa/provider.

**RQ1 congelata non modificata.**
