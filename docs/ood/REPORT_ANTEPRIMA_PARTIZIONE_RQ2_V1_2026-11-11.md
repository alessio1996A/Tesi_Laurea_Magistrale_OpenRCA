# RQ2 — Rapporto dell'anteprima V1 bilanciata (non congelata)

**Data dell'evidenza:** 11 novembre 2026  
**Provenienza:** output Colab fornito dall'utente, branch `feature/ood-knowledge-transfer-audit-2026-11-10` al commit di esecuzione `f3382d43d80bd82d400749fbf5315ccc8b63ea89`; `audit=rq2_partition_preview_balanced_v1`; `status=DRAFT_NOT_EXECUTABLE`; `source_verified=true`.

## 1. Invarianti e sorgenti

- Split Market SHA256: `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`.
- Manifest GT-free SHA256: `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`.
- Criterio deterministico: `openrca-rq2-ood-balanced-group-safe-v1-2026-11-11`; `eligible_candidate_count_aggregate=11`; `valid_candidate_partitions_count=24`.
- Selezione candidata: **4 query discovery / 11 query test**, in rispettivamente **4 / 10 gruppi temporali**. Ogni discovery è un singleton di finestra.
- Discovery su cloudbed-1 **2**, cloudbed-2 **2**; test su cloudbed-1 **4**, cloudbed-2 **7**.
- Nessuna coppia discovery/test distante al massimo un'ora nello stesso cloudbed: `cross_phase_near_pairs_3600s=0`.
- Gap minimo fra finestre discovery e test nello stesso cloudbed `5400` secondi (**90 minuti**).
- La coppia con finestra identica `cloudbed-1_q014`/`cloudbed-1_q030` resta unita nel **test**.
- Questo algoritmo usa GT **solo** nella fase di partizionamento offline per verificare una query discovery per classe; **non** emette una mappatura per-caso, e non dà etichette ad agenti o prompt.
- Indicatori di esecuzione: `read_ground_truth=true`, `read_telemetry=false`, `read_predictions=false`, `model_api_calls=0`, `files_written=false`, `emits_case_label_mapping=false`.

## 2. ID della partizione V1 proposta

**Discovery (4):**
```text
cloudbed-1_q032
cloudbed-1_q050
cloudbed-2_q026
cloudbed-2_q045
```

**Test (11):**
```text
cloudbed-1_q014
cloudbed-1_q021
cloudbed-1_q030
cloudbed-1_q059
cloudbed-2_q014
cloudbed-2_q021
cloudbed-2_q040
cloudbed-2_q041
cloudbed-2_q058
cloudbed-2_q076
cloudbed-2_q077
```

Classi **solo in forma aggregata**:

| Classe | Discovery | Test | Cloudbed rappresentati nel test |
|---|---:|---:|---:|
| node CPU spike | 1 | 2 | 2 |
| container write I/O load | 1 | 2 | 1 |
| container process termination | 1 | 3 | 2 |
| container packet loss | 1 | 4 | 2 |

`container write I/O load` resta confinato a cloudbed-2 nella popolazione disponibile: la V1 **non** risolve l'assenza di un test cross-cloudbed per questa classe.

## 3. Confronto con V0 e interpretazione

- La V0 era una preview valida rispetto agli invarianti minimi (una discovery per classe, finestre condivise unite), ma aveva **4/4 discovery in cloudbed-2**, incluse finestre OOD direttamente contigue `cloudbed-2_q040` e `cloudbed-2_q041`. V0 archiviata in `docs/ood/REPORT_ANTEPRIMA_PARTIZIONE_RQ2_V0_2026-11-11.md`.
- La V1 migliora **bilanciamento ambientale** e riduce possibili interferenze di vicinanza temporale fra discovery/test, senza usare esiti LLM, scoring o telemetria.
- Il criterio è stato modificato **prima di qualunque inferenza su OOD**: non si tratta di adattamento al risultato dei modelli.
- **Non** concludere che 14 gruppi siano 14 iniezioni fisicamente indipendenti. Evitare test di significatività eccessivamente ambiziosi; con 2/2/3/4 query positive di test per classe la pseudoregola resta una *proof-of-feasibility*.
- La finestra con due classi diverse richiede valutazione di negativi a livello di *intera finestra e componente*: una query non può essere automaticamente un negativo della classe presente nell'altra.

## 4. Decisione e controlli ancora aperti

**Decisione metodologica provvisoria:** mantenere la **V1 come candidata alla partizione finale**, senza continuare a riottimizzare la selezione. **Non congelata** finché non saranno fissati: schema diagnostico omogeneo, schema della pseudoregola, prompt, separazione D/C/K, controlli negativi e policy per errori/astensioni, budget, versioni provider, hash/manifest immutabili e test software/Colab.

**Prossimo passo:** costruire contratti JSON e validatori senza GT per le risposte degli agenti e le proposte di pseudoregole; test sintetici PyCharm. **Nessuna chiamata LLM autorizzata o eseguita da questo audit.**
