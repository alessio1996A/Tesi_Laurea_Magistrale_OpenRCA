# RQ2 — Inventario KPI e preflight di formalizzabilità K

**12 novembre 2026** — **Modulo preparato; test PyCharm non ancora eseguiti**. Nessuna API, nessun Market.zip, nessun caso OOD aperto, nessuna modifica di codice o risultati congelati RQ1.

## Perché serve

La struttura JSON di una pseudoregola K può essere corretta anche se il modello ha inventato un KPI, una unità, una soglia o una semantica di contatore. Il validatore esistente `rq2_output_contracts.py` verifica il **contratto di formato**, non la realtà fisica della proposta.

Il nuovo modulo `src/evaluation/rq2_kpi_formalizability_preflight.py` fornisce un **primo controllo conservativo** usando soltanto informazioni già contenute nel codice sorgente RQ1. Non è un'interfaccia verso i modelli, non è un detector, non è uno scorer e non marca automaticamente alcuna regola come pronta per il test.

## Che cosa abbiamo censito

Il modulo utilizza i nomi già elencati da `GAUGE_NODI` (21 KPI) e `GAUGE_CONTAINER` (5 KPI) in `src/harness/signal_catalog.py`, più 3 nomi già presenti nei detector storici R01 e R06:

- `container_cpu_usage_seconds` in `rule_container_cpu.py`;
- `container_fs_reads_MB./dev/vda` e `container_fs_reads./dev/vda` in `rule_container_read_io.py`.

**Totale previsto: 29 nomi di KPI presenti nel codice, non 29 segnali verificati in Market.**

Per ogni nome di metrica l'inventario segnala il layer (`node` o `container`), il tool corrispondente, il file sorgente, e mantiene esplicitamente:

- `market_presence_verified=false`: l'esistenza nel codice non dimostra presenza nelle finestre del benchmark;
- `physical_unit=null`, `physical_unit_verified=false`: nessuna unità fisica è promossa sulla base del nome;
- `metric_semantics_verified=false`: nessuna serie è interpretata automaticamente come rate, gauge fisicamente verificato o contatore cumulativo;
- `rule_aggregation_verified=false`: `mean`, `max`, `delta` ecc. non sono tutte scientificamente equivalenti né automaticamente lecite.

Questa enumerazione **non copre ancora** in modo completo i segnali service/mesh/runtime, log o trace; e non è esaustiva per le metriche node/container presenti nel Market. La classificazione dei nomi è quindi **un'anteprima degli indizi già in codice**, non una lista bianca definitiva che prova assenza dei KPI sconosciuti.

## Comportamento del controllo K

`evaluate_k_formalizability(raw_json, allowed_evidence_ids=...)` utilizza il validatore RQ2-K già esistente, poi produce **solo metadati di fattibilità e motivi di insufficiente verifica**:

- `invalid_contract`: JSON non aderente al contratto oppure ID evidenza inventati;
- `insufficient_evidence`: il modello non è riuscito a formulare una regola;
- `requires_verification`: regola strutturalmente valida, ma le metriche/semantiche/unità sono ancora da accertare.

Possibili motivi, senza dati o diagnosi: `metric_not_in_source_catalog`, `market_presence_unverified`, `physical_unit_unverified`, `metric_semantics_unverified`, `aggregation_semantics_unverified`.

Il controllo restituisce **sempre** `ready_for_test=false`, `rule_executed=false`, `catalog_frozen_for_science=false`, `model_api_calls=0`, `files_written=false`. Non restituisce il pseudocodice né interpreta i threshold. Nomi e flag non possono essere trattati come prova di disponibilità nel dataset.

## Due significati distinti di formalizzabilità

Per evitare un ostacolo metodologico artificiale bisogna separare:

1. **Formalizzabilità operativa**: una regola eseguibile su numeri grezzi di una serie con nome esatto, finestra, aggregazione e calcolo replicabili, descritta **solo** come pattern numerico su osservazioni.
2. **Formalizzabilità con interpretazione fisica**: in aggiunta sono verificate l'unità, la natura della metrica (cumulativa/istantanea/ecc.) e l'interpretazione delle soglie come fenomeno reale.

Una regola può eventualmente essere utile **nel primo senso** anche se non possiamo certificarne la semantica fisica. Per adottare tale impostazione bisognerà definire **prima del test** il contratto di `raw_value`, la trasformazione ammessa e la policy di astensione, con un interprete controllato e un catalogo verificato su sorgenti **development GT-free** o documentazione ufficiale. **Questo modulo non certifica ancora neppure il livello operativo**: verifica solo il nome nel codice e segnala le evidenze mancanti. Non trasformare automaticamente un nome di KPI in un detector pronto.

## Test e prossimi passaggi

`src/tests/test_rq2_kpi_formalizability_preflight.py` contiene **19 test sintetici preparati, ancora da eseguire**: stabilità dei digest, source-only, nessuna unità certificata, KPI noti/sconosciuti, evidenze inesistenti, contratti non validi, astensione, pseudocodice inerziale e blocco di ogni esecuzione.

Da PyCharm (root repo):

```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_kpi_formalizability_preflight.py" -v
```

**Solo dopo la suite verde:** completare catalogo operativo *senza leggere OOD test*; definire regole di provenienza/aggregazione e una policy di freeze, quindi integrare runner RQ2 GT-free con modelli **mock** e create-only. Prima di API reali servono preregistrazione completa, costo massimo, ID modello congelati e autorizzazione esplicita.

Nessun progresso di questa fase altera RQ1; il catalogo è un artefatto di progettazione isolato.
