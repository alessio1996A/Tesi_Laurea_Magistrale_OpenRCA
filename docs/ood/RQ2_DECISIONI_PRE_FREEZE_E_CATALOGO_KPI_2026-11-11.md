# RQ2 — Decisioni pre-freeze e confine di formalizzabilità delle regole

**Data:** 11 novembre 2026  
**Stato:** proposta operativa, **NON congelata**; nessuna chiamata API autorizzata.  
**Base:** tutte le suite RQ2 eseguite finora dall'utente superate, compresa `test_rq2_rule_group_scorer.py` (**20/20, 0,006 s**). Audit V3 reale **40/40 bundle**, 209 osservazioni, 71 troncate. Piano preliminare reale GT-free: 4 discovery + 11 test, 90 D + 90 C + 24 K = 204 stage logici, non chiamate API.

## 1. Risultato dell'ispezione del codice corrente

Sono stati consultati **soltanto file sorgente GitHub**, non i dati OOD test né output LLM, per la progettazione del catalogo KPI.

| Sorgente | Osservazione confermata dal sorgente | Implicazione |
|---|---|---|
| `src/agent/tool_factory.py` | Cinque tool con allowlist: `tool_get_service_metrics`, `tool_get_container_metrics`, `tool_get_node_metrics`, `tool_get_logs`, `tool_get_traces`. Tutti vincolati a cloudbed/finestra. | Solo questi tool sono ammessi nella traiettoria D RQ2. |
| `src/evaluation/experiment_runner.py` | Il preprocessore delle metriche node/container seleziona `timestamp`, `cmdb_id`, `kpi_name`, `value`. | **Non esiste in questa interfaccia una colonna dedicata a unità fisica, tipo di metrica o semantica cumulativa**. |
| `src/harness/signal_catalog.py` | Elenca KPI node e container come whitelist osservativa; per KPI noti restituisce `gauge_candidato`, per sconosciuti `non_verificato`. Per Mesh/Runtime ci sono note di `semantica_verificata=False`. | Il catalogo attuale non certifica automaticamente che unità/tipo/trasformazione siano corretti per una soglia. |
| `src/harness/rules/rule_container_cpu.py` | `container_cpu_usage_seconds` non monotono nei dati osservati; il file dice espressamente che la semantica fisica resta da verificare. | **Vietato** interpretarlo automaticamente come contatore cumulativo o derivarne un rate. |
| `src/harness/rules/rule_container_read_io.py` | `container_fs_reads_MB./dev/vda` è trattato come livello per campione, non throughput; il suffisso MB è dichiarato non definitivamente verificato. | **Vietato** inferire MB/s o unità fisiche certificate dalla sola stringa. |
| `src/harness/mesh_runtime_detector.py` | Prefissi Istio e nomi Java Runtime sono elencati; alcuni sono trattati come valori osservati anziché statistiche fisiche già validate. | Non associare in modo opportunistico semantiche di rate, counter o latenza. |

**Decisione di sicurezza:** nei contratti K le stringhe `metric`, `unit`, `aggregation`, `window_seconds` e `threshold` sono **affermazioni del modello**, non fatti verificati. `validate_candidate_rule` controlla la forma JSON, **non** certifica l'esistenza del KPI, le unità, il tempo di campionamento, la compatibilità dell'aggregazione o la validità della soglia. Non si può considerare una regola `formalizable` semplicemente perché ha JSON valido.

## 2. Procedura proposta, deterministica e senza human-in-the-loop

1. Prima di aprire il test, creare **un catalogo tecnico statico versione V1** costruito da sorgenti/documentazione di schema e, solo se indispensabile, dalla coorte **development GT-free già autorizzata**, mai dalle telemetrie dei gruppi OOD test. Registrare per ogni KPI: origine (node/container/service/mesh/runtime), nome esatto, disponibilità, campionamento, tipo `level/counter/unknown`, unità `verified/unknown`, operazioni consentite e documento a supporto. Unità sconosciuta non va riempita con un'ipotesi.
2. Tutte le proposte K vengono validate rispetto al **catalogo congelato** e all'allowlist delle evidenze della loro discovery. Per diventare formalizzabili devono usare solo segnali accertati con trasformazioni ammesse e soglie espresse in unità coerenti; altrimenti riportare `unavailable_signal`, `unit_unverified` o `not_formalizable`. Non cambiare soglie, KPI, aggregazioni o finestre dopo aver letto la telemetria/risposta del test.
3. Non eseguire mai `pseudocode` fornito dall'LLM; un interprete deterministico con operazioni predefinite dovrà consumare **solo il contratto strutturato congelato**, dopo verifica di equivalenza e specifiche tecniche.
4. Conservare **tutte e 24 le opportunità K** (incluse `insufficient_evidence`, errori provider e non-formalizzabili). Vietato sopprimere denominatori, selezionare la migliore sulla base del test o correggere un candidato usando il ground truth.
5. La futura valutazione RQ2-C usa **10 gruppi di finestre**, non 11 query indipendenti; il gruppo multi-fault ha un insieme di classi e vale come positivo per tutte le classi presenti. Le altre classi possono servire da negativi one-vs-rest solo con reference completa; eventuali controlli healthy devono essere autentici e preregistrati.
6. Lo scorer offline `rq2_rule_group_scorer.py` riceve etichette solo da un processo **separato dal runtime**; restituisce TP/FP/TN/FN, coverage, astensioni/errori e denominatori. Non dimostra di per sé causalità né implementabilità.

## 3. Proposte di congelamento per ridurre i rischi entro la consegna

| Decisione | Opzione proposta prima delle API | Stato |
|---|---|---|
| Coorte | Strategia **E1**: 15 query OOD già inventariate; 4 discovery, 11 test in 10 gruppi. No espansione fittizia. | **Da approvare/congelare** |
| Contrasto RQ2-A | `A1` vs `A1_8R` appaiati per query e modello; metrica primaria: correttezza `predicted_fault_type` C sulle test con scoring GT isolato. | **Da congelare** |
| Modelli | Tre famiglie logiche Gemini/Sonnet/Haiku, **versioni esatte e parametri ancora da fissare**. | **Aperto** |
| Fasi | 90 D, 90 C, 24 K; C e K senza tool; K **solo** nelle discovery, test chiuso fino a freeze K e del detector. | **Bozza verificata tecnicamente** |
| RQ2-B | Struttura, citazioni, unità, falsificabilità e astensioni di **tutti** i 24 K, nessuna selezione basata su score. | **Da congelare** |
| RQ2-C | Valutare offline **tutti** i K ritenuti formalizzabili da gate statico pre-test; scegliere l'arm di riferimento ex ante e riportare molteplicità, missing e non-implementabilità. | **Da congelare** |
| Primario illustrativo RQ2-C | `A1_8R` + Sonnet, quattro discovery e relativi K, prescelto **prima** delle risposte OOD sulla base della domanda scientifica e della RQ1. Non selezionare il migliore a posteriori. | **Proposta, non decisione** |
| Unità/KPI | Fase di censimento **solo development/documentazione**, catalogo con unità/type `unknown` se non supportati. | **Aperto; blocca interprete** |
| Budget | Stima USD ex ante basata su run RQ1, plafond, errori, retry e autorizzazione esplicita per provider. 204 stage ≠ 204 chiamate. | **Aperto; blocca API** |
| Persistenza | Run plan create-only con hash delle sorgenti e del codice; separate D/C/K, integrità restart, nessuna sovrascrittura RQ1. | **Aperto; blocca API** |
| Freeze | Un freeze tecnico **prima delle discovery**; successivo freeze scientifico delle regole **prima del test**, entrambi auditabili. | **Aperto; blocca API** |

**Non confondere:** l'aver congelato un prompt prima delle discovery non autorizza automaticamente il test; prima del test vanno congelati candidati K, criterio di formalizzabilità e implementazione deterministica. L'analisi esplorativa di RQ2 non dimostra classi assenti dal pretraining del modello.

## 4. Prossimo risultato utile

La priorità non è moltiplicare suite sintetiche, ma **completare il catalogo KPI e la catena runner D/C/K con mock provider e persistenza create-only**, poi verificare in preflight una singola run di sviluppo non OOD. Successivamente preparare stima dei costi e freeze del protocollo, chiedendo autorizzazione esplicita **prima** di chiamare Gemini/Claude.

Non avviare Colab o effettuare chiamate modello sulla base di questo solo documento. Nessuna modifica ai file della campagna RQ1 congelata.
