# Registro di continuità — RQ2 OpenRCA / Harness Engineering
**Aggiornamento: 11 novembre 2026**  
**Stato: preparazione del protocollo, senza nuove inferenze LLM.**  
Branch di lavoro: `feature/ood-knowledge-transfer-audit-2026-11-10`. Il protocollo/risultati della prima fase restano congelati al riferimento `e4845e7fe9a399e10dd2db6f320dfeaeeddf3379`. Il registro serve alla futura metodologia della tesi, **non** sostituisce codice, output originali o verifiche sperimentali.

## 1. Domande di ricerca e confini

- **RQ1 (conclusa):** studiare come configurazioni di harness diverse influenzano la RCA. Cinque varianti `A0`, `A1`, `A1_8R`, `A1_8R_Planning`, `A1_PAVE`; confronto cross-model Gemini / Claude Sonnet / Claude Haiku su EVALUATION20. Risultati e run storici congelati, non rifare, sovrascrivere o adattare sui risultati già osservati.
- **RQ2 (in preparazione):** per guasti *non coperti dalle regole deterministiche*, verificare (i) diagnosi tramite evidenze, (ii) spiegazione tecnica, (iii) pseudoregola deterministica candidata. Verificare separatamente la regola su episodi indipendenti, ove possibile; possibile assenza di generalizzazione dimostrabile se i dati sono insufficienti. Non implementare human-in-the-loop o aggiunta autonoma di regole: sviluppi futuri.
- **OOD** nell'uso operativo significa `ood_holdout`: *classi deliberate fuori dallo sviluppo*, **non** garanzia che il modello non ne abbia mai appreso il concetto durante il pretraining.

## 2. Popolazione del benchmark, regole e classi

Il benchmark Market comprende **15 tipologie** di guasto, suddivise progettualmente in:
- **8 con regole implementate:** R01 container CPU load; R02 container memory load; R06 container read I/O load; R07 node CPU load; R08 node memory consumption; R09 node disk read I/O consumption; R10 node disk write I/O consumption; R11 node disk space consumption.
- **3 classi note ma senza regole affidabili:** R03 container network packet retransmission; R04 container network packet corruption; R05 container network latency. **Non riservate come OOD**: potevano in linea di principio apparire nei gruppi development/evaluation e l'LLM poteva diagnosticarle da metriche/log/trace. La presenza effettiva nelle specifiche coorti va ancora verificata con un audit delle etichette.
- **4 classi deliberatamente riservate per RQ2:** node CPU spike, container write I/O load, container process termination, container packet loss.

**Non equiparare** numero di regole, classi, query, finestre, episodi di fault injection, task e guasti indipendenti. Una query riguarda un task diagnostico; più query possono riferirsi alla medesima finestra/guasto.

## 3. Dati verificati e provenienza

Audit GT-free in Colab, **output originale riportato dall'utente** e commit `7ae250fc420048f36853ed56e18ea1ecbe15f5d3`:
- SHA split: `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`;
- SHA manifest: `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`;
- 148 query: development 92, evaluation 23, mixed_quarantine 18, ood_holdout 15;
- `ood_holdout`: **15 query**, 6 cloudbed-1 e 9 cloudbed-2; task_1..task_7 `1/4/1/1/5/1/2`;
- finestre di 1800 s, **14 gruppi temporali**; `cloudbed-1_q014` (task_5) e `cloudbed-1_q030` (task_3) condividono l'identico intervallo: non separarli in discovery e test;
- zero sovrapposizioni *di finestre* con altri split, **non** dimostrazione di completa indipendenza causale/assenza di leakage;
- `read_ground_truth=false`, `read_record_csv=false`, `read_query_csv=false`, `read_telemetry=false`, `model_api_calls=0`, `files_written=false`.
- **Non abbiamo ancora contato quante volte ciascuna delle quattro classi compare nei 15 casi**, né quante iniezioni di guasto fisicamente indipendenti rappresentano. NON indicare le 15 query come 15 guasti.

Relazione estesa: `docs/ood/REPORT_PREFLIGHT_GT_FREE_2026-11-10.md`.

## 4. Test e artefatti fase 2

1. `src/evaluation/ood_holdout_preflight.py`; `src/tests/test_ood_holdout_preflight.py`; `notebooks/Colab_OOD_GTFree_Preflight_2026_11_10.ipynb`. **4 test su dati sintetici superati dall'utente in PyCharm**. Audit Colab reale completato e JSON verificato. L'esecuzione iniziale del notebook stampava solo un messaggio finale, senza JSON: corretta la cattura/validazione/stampa del JSON su GitHub, poi rieseguito con successo. Documentare come correzione strumentale, non modifica ai dati.
2. `src/evaluation/ood_source_schema_audit.py`; `src/tests/test_ood_source_schema_audit.py`; `notebooks/Colab_OOD_Source_Schema_2026_11_10.ipynb`. **Altri 4 test sintetici superati dall'utente in PyCharm** (`Ran 4 tests in 0.155s — OK`). **Notebook Colab ora eseguito con successo dall'utente**; risultato e intestazioni confermati, senza etichette lette.
3. Il secondo notebook legge **solo le intestazioni** di `query.csv` e `record.csv` nella root Drive e in `Market.zip`, non le righe: identifica posizione/schema, ma non la presenza delle classi.
4. Nessuna nuova chiamata a Gemini, Sonnet o Haiku né scoring nella fase 2 a oggi; nessuna nuova regola implementata.

## 5. Decisioni non ancora prese (NON presentarle in tesi come definitive)

- **Quali harness usare per RQ2?** Ipotesi ragionata: `A1_8R` principale, `A0` controllo; considerare `A1`, `A1_PAVE`, `A1_8R_Planning` solo se una domanda sperimentale ne giustifica il costo. La prima fase ne usava cinque: **non affermare che RQ2 debba obbligatoriamente usarli tutti**.
- Modelli da confrontare a protocollo stabile: Gemini, Sonnet, Haiku. Pilot tecnico Gemini prima delle campagne; **non ottimizzare sui casi e chiamarli poi test indipendenti**.
- Numero di casi discovery/test per ogni classe; criteri di raggruppamento per fault injection, selezione, dimensione campione, classi con pochi episodi, controlli negativi, qualità e validazione della pseudoregola.
- Eventuale **ampliamento del dataset**: solo dopo inventario delle etichette e dell'indipendenza. Niente prelievo arbitrario dagli split development/evaluation/quarantine; evitare sovrapposizioni con esperimenti precedenti e privilegiare query ufficiali quando serve scorer Microsoft.

## 6. Passi operativi successivi

1. Eseguire **l'unica cella** di `notebooks/Colab_OOD_Source_Schema_2026_11_10.ipynb` e conservare output, commit e percorso; zero API.
2. Sulla base degli schemi, progettare **audit controllato delle etichette/episodi** in un percorso dedicato: ground truth consultato solo da componente di partizionamento/valutazione, mai da agent/prompt/strumenti inferenziali, e dichiarato esplicitamente (non più GT-free).
3. Contare distribuzione delle quattro classi, cluster di fault injection e task, senza fissare split discovery/test a posteriori dopo aver visto performance LLM.
4. Congelare protocollo, metriche (diagnosi Microsoft; qualità spiegazioni; verificabilità della pseudo-regola; veri/falsi positivi/astensione) e budget; solo poi pilot/API autorizzati.
5. Conservare per ogni esperimento: commit sorgente, hash input/piano, ambiente/versioni, dataset/split, modello/provider/config, prompt/harness, numero di tool/costi, stato run/errori, output/log, scoring, analisi statistica, limiti, decisione e motivazione.

## 7. Istruzioni di continuità tra chat

Questo file e le fonti/commit collegati sono la **traccia persistente** da leggere per primo in una nuova conversazione. Il contesto conversazionale è utile, ma non sostituisce la verifica dello stato del repository, dei risultati e degli output. Non iniziare una nuova campagna da zero, non reinventare il codice, non toccare il freeze storico. Ogni nuova evidenza o decisione importante richiede aggiornamento del registro e riferimento a commit/artefatto.

## 8. Aggiornamento 11 novembre 2026 — secondo Colab completato e audit GT controllato predisposto

**Output confermato dall'utente**, commit in Colab `6b06fd9b2125fe086a422d6e03249bdbfa76e15a`:
- `ood_source_schema_only_v1`, `archive_bytes=2865427796`; quattro CSV trovati in `Market.zip`: `Market/cloudbed-1/query.csv` (33649 byte), `Market/cloudbed-1/record.csv` (5356), `Market/cloudbed-2/query.csv` (36012), `Market/cloudbed-2/record.csv` (6027).
- `query.csv`: `task_index,instruction,scoring_points`; `record.csv`: `timestamp,level,component,reason,datetime`. I due CSV alla root Drive hanno dimensioni uguali a quelli di cloudbed-1, **ma la provenienza non è stata verificata**: non usarli al posto delle sorgenti ZIP dei due cloudbed.
- `read_records=false`, `read_ground_truth_values=false`, `read_telemetry=false`, `model_api_calls=0`, `files_written=false`.

**Verifica di metodo sui sorgenti pubblici Microsoft**:
- Nel generatore ufficiale OpenRCA (`main/generate.py`), le query sono prodotte iterando `record.csv` in ordine di riga; più guasti nella stessa mezz'ora possono dar luogo a scoring multi-failure. Il codice della tesi NON presume quell'allineamento senza verificarlo su archivio/split/manifest originali. Fonti:
  - https://github.com/microsoft/OpenRCA/blob/main/main/generate.py
  - https://github.com/microsoft/OpenRCA/blob/main/main/task_specification.json
- In particolare i task `task_1`, `task_3`, `task_5` non richiedono *root cause reason* nel loro score; questa proprietà influenza la definizione della metrica per RQ2. Evitare di chiamare successo della diagnosi di classe un successo su tempo/componente soltanto.
- Fusi orari: l'autore usa UTC+8 per le date locali nei CSV; l'audit confronta le epoche Unix di `record.timestamp` con le epoche Unix del manifest, senza conversioni del fuso del laptop o del runtime Colab.

**Codice preparato, NON ancora testato sul computer dell'utente né sul dataset reale**:
- `src/evaluation/ood_class_inventory.py`: componente **isolato di audit che legge esplicitamente etichette GT** dei due `record.csv` e `scoring_points` nel ZIP, con controllo riga-per-riga della concordanza fra ID, indice, task, istruzione, tempo e campi scoring. Restituisce *solo distribuzioni aggregate per classe*, senza associazioni fra `case_id` e etichetta. I match delle classi sono esatti dopo normalizzazione della punteggiatura, senza inferire sinonimi a posteriori; eventuali etichette non riconosciute sono riportate come aggregati con stato `requires_nomenclature_review`, non occultate.
- `src/tests/test_ood_class_inventory.py`: 5 test su archivi e manifest sintetici per conteggi, finestre condivise, etichette sconosciute, mismatch di task e timestamp, archivio assente.
- `notebooks/Colab_OOD_Controlled_Class_Inventory_2026_11_11.ipynb`: unica cella; estrazione degli aggregati di classe in JSON; non esporta GT per caso, non apre telemetria, non chiama provider, non scrive file.
- **ATTENZIONE**: l'audit successivo **non è GT-free**. L'accesso alle etichette è voluto ed esclusivamente nel ramo di partizionamento/valutazione. È vietato inserirlo nei tool/prompts dell'agente. Non abbiamo ancora selezionato discovery/test o dato API access agli agenti.

**Prossimi passi:** l'utente esegue i 5 test PyCharm; poi, se OK, la sola cella Colab controllata. Si analizzeranno conteggi per classe, gruppi di finestre e limiti reali del campione, *prima* del protocollo e dei costi LLM.

## 9. Aggiornamento — inventario GT controllato riuscito (11 novembre 2026)

**Output completo ricevuto dall'utente:** `audit=ood_class_inventory_controlled_gt_v1`, Colab al commit `751cbd5b1b7a76c477f73ae7e56ba9e758de301f`; `source_verified=true`, `classification_status=complete`, **148** allineamenti query–record verificati, **15** query OOD tutte mappate alle quattro classi, **0** nomi di classe sconosciuti. Nessuna API LLM e nessun output case–etichetta. In questo audit il GT è stato **letto deliberatamente solo per l'inventario aggregato**, quindi non è GT-free.

| Classe | Query OOD | Gruppi temporali entro classe | Task che chiedono reason | cloudbed-1 | cloudbed-2 |
|---|---:|---:|---:|---:|---:|
| node CPU spike | 3 | 3 | 1 | 2 | 1 |
| container write I/O load | 3 | 3 | 2 | 0 | 3 |
| container process termination | 4 | 4 | 2 | 2 | 2 |
| container packet loss | 5 | 5 | 3 | 2 | 3 |
| **Totale** | **15** | **15 appartenenze classe-gruppo, 14 gruppi globali** | **8** | **6** | **9** |

**Conclusioni e cautele:** tutte e quattro le classi sono presenti, ma la dimensione campionaria è molto limitata; i 14 gruppi di finestre non provano indipendenza causale. La coppia di query nella stessa finestra corrisponde a **due classi differenti** (dedotto dall'uguaglianza per classe fra query e gruppi temporali); resta nello stesso braccio per ogni confronto discovery/test. Sette task su quindici non chiedono il motivo del guasto nello scoring ufficiale: per RQ2 servono valutazioni esplicite e omogenee della classe e della regola, preregistrate prima delle inferenze. Write I/O appare esclusivamente in cloudbed-2, quindi manca la possibilità di verifica cross-cloudbed per tale classe.

**Documento dei risultati:** `docs/ood/REPORT_INVENTARIO_CLASSI_GT_CONTROLLATO_2026-11-11.md` (creato e verificabile in questo branch).  
**Prossimo passo proposto, NON ancora eseguito:** audit di dipendenza fra iniezioni di guasto e progetto discovery/test (senza esposizione di GT al modello). **Non** avviare direttamente Gemini né modificare la fase 1; la selezione degli harness e il protocollo non sono congelati.

## 10. Preparazione controllo successivo (11 novembre 2026, ancora NON eseguito)

Creati sul branch corrente:
- `src/evaluation/ood_dependency_sensitivity.py`: audit di **sensibilità**, che riusa le validazioni di provenienza/GT di `ood_class_inventory.py` e confronta solo metriche aggregate: finestre OOD sovrapposte, vicinanza dei timestamp di record **nello stesso cloudbed, stessa classe, stesso componente** per soglie 0, 30, 60, 120, 240 minuti; stima quanti cluster si formano per ciascuna soglia.
- `src/tests/test_ood_dependency_sensitivity.py`: cinque test sintetici, **da eseguire e verificare in PyCharm**.
- `notebooks/Colab_OOD_Dependency_Sensitivity_2026_11_11.ipynb`: una cella, da eseguire **solo dopo test PyCharm OK**.

Questo modulo consulta GT nel ramo di **audit**, non esporta mapping etichette/case_id, non vede telemetria, non chiama modelli e non scrive. **ATTENZIONE: cluster per vicinanza+component+classe sono solo proxy di rischio, NON prova di dipendenza/indipendenza causale.** Nessun campione discovery/test né nuovo protocollo è stato selezionato.

## 11. Verifica PyCharm del controllo dipendenze (11 novembre 2026)

**Output test trascritto dall'utente; nessun test aggiuntivo eseguito dall'assistente:**
- `python -m unittest discover -s src/tests -p "test_ood_class_inventory.py" -v`: cinque test nominativi `test_aggregate_only_and_shared_window`, `test_missing_original_archive_is_error`, `test_record_timestamp_mismatch_rejected`, `test_task_mismatch_rejected`, `test_unknown_reason_requires_review`; **Ran 5 tests in 0.337s — OK**.
- `python -m unittest discover -s src/tests -p "test_ood_dependency_sensitivity.py" -v`: `test_base_four_ood_queries_three_disjoint_windows`, `test_missing_archive_fails`, `test_nearby_same_cause_component_disjoint_window`, `test_transitive_cluster`, `test_unknown_reason_blocks_sensitivity_audit`; **Ran 5 tests in 0.125s — OK**.

**Totale 10/10 su dati sintetici**. Non equivalgono a validazione scientifica del proxy di dipendenza su fault injection reali. **Prossima azione autorizzata:** esecuzione dell'unica cella `notebooks/Colab_OOD_Dependency_Sensitivity_2026_11_11.ipynb` sul dataset Market per ottenere aggregati di sensibilità, senza inferenze LLM, senza modifica al freeze e senza assegnare casi a discovery/test. Attendere output reale.

## 12. Esito reale dell'audit dipendenze (11 novembre 2026)

**Risultato Colab ricevuto dall'utente:** `ood_dependency_sensitivity_controlled_gt_v1` con `source_verified=true`, esecuzione al commit `a732773dcee3bfd2152c3d79432c5a56fb9e982d`. 15 query OOD, una coppia di finestre sovrapposte, 14 gruppi. **Nessuna ulteriore coppia con stesso cloudbed+classe+componente e timestamp vicino** alle soglie di 0, 1800, 3600, 7200 e 14400 s. A ogni soglia, 14 gruppi, istogramma `{1:13,2:1}`, coppie aggiuntive `0`. Gruppi contenenti ciascuna classe: node CPU spike 3; container write I/O load 3; container process termination 4; container packet loss 5.

**Attenzione:** questo **NON prova** 14 injection causalmente indipendenti. Nessun `case_id → classe` stampato, ground truth consultato soltanto dal modulo offline di audit; nessuna telemetria, API o scrittura. **Non è stata selezionata alcuna coorte discovery/test.**

**Report completo:** `docs/ood/REPORT_SENSIBILITA_DIPENDENZE_OOD_2026-11-11.md` (commit di creazione `42673476c8b44bbf69c5f3d52bfa8930e96f7068`).

**Prossima decisione:** progettare il protocollo separando diagnosi OOD e validazione di pseudoregole, mantenendo sempre unite le query con finestra in comune; scegliere harness e split con criteri preregistrati, riconoscendo i piccoli numeri per classe. Solo dopo autorizzazione API.

## 13. 11 novembre 2026 — bozza protocollo RQ2 e prototipo selettore (NON frozen)

**Progettazione predisposta, non approvazione del protocollo sperimentale:**
- Documento `docs/ood/PROTOCOLLO_RQ2_BOZZA_V0_2026-11-11.md`: confronto A1 vs A1_8R, A0 solo controllo opzionale; Gemini/Claude Sonnet/Claude Haiku; separazione fra diagnosi task originale D, probe uniforme di `predicted_fault_type` C, e proposta pseudoregola K **solo su discovery**. Documento contiene controllo negativo multi-fault a livello di finestra, criteri di qualità/verificabilità, astensioni, errori, costi da autorizzare, invarianti e piano di espansione E1/E2. **Non approvato né congelato**: niente API o modifiche all'agente.
- Proposta di coorte: 1 singleton discovery per classe, selezionato con hash fisso/GT isolato; resto test; **4 query discovery + 11 test**, con la coppia `cloudbed-1_q014` / `cloudbed-1_q030` **insieme nel test**. In base ai conteggi aggregati già verificati, il target sarebbe 2/2/3/4 query positive di test per classe, a condizione che l'anteprima venga confermata. Non è prova di indipendenza di fault injection; campione troppo piccolo per generalizzazione robusta.
- **Nuovo codice** `src/evaluation/rq2_partition_preview.py`: prototipo eval-only, legge il GT per stratificare in memoria, ma non emette il mapping case ID→classe; output include solo ID, gruppi, phase e **conteggi aggregati per classe**. Risposta marcata `DRAFT_NOT_EXECUTABLE`, nessun file scritto, nessuna API, nessuna inferenza.
- **Nuovi test** `src/tests/test_rq2_partition_preview.py`: sei test sintetici per determinismo, coerenza gruppi, nessuna fuga di mapping, assenza di singleton, etichette sconosciute e archivio mancante. **NON ancora eseguiti dall'utente**.
- **Nuovo notebook** `notebooks/Colab_RQ2_Partition_Preview_2026_11_11.ipynb`: una sola cella, da eseguire sul Market reale solo dopo PyCharm OK; stampa bozza del piano e ne controlla i vincoli. Non salva un piano runnable.

**Stime non autorizzate:** con due harness × tre modelli × 15 query, 90 run diagnostici D + 90 probe C e, per quattro discovery × due harness × tre modelli, 24 chiamate K di proposta. Queste cifre **non** sono stime USD o massimo di chiamate LLM: ogni run D include ulteriori chiamate LLM/tool.

**Scelta ampliamento:** E1 (15 query, studio esplorativo) consigliato **se non esistono altre coorti indipendenti documentate**; E2 prevede ricerca e validazione di nuovi episodi esterni ai due cloudbed già completamente ripartiti, senza rifare retroattivamente la RQ1. È una decisione ancora aperta e da documentare prima del freeze.

**Prossimo passo operativo:** test PyCharm del selettore su dati sintetici; poi Colab anteprima e discussione/freeze del protocollo. **Nessuna nuova run LLM deve partire da questa bozza.**

## 14. 11 novembre 2026 — Test PyCharm del selettore RQ2 superati

Output dell'utente: `Ran 6 tests in 1.059s — OK`, comando `python -m unittest discover -s src/tests -p "test_rq2_partition_preview.py" -v` (sei test sintetici). I sei test sono passati in PyCharm nell'ambiente dell'utente. **Non costituiscono ancora conferma della partizione sui dati Market reali.**

Prossimo passo: eseguire in Colab `notebooks/Colab_RQ2_Partition_Preview_2026_11_11.ipynb` su `Market.zip` originale, osservare il JSON con status `DRAFT_NOT_EXECUTABLE` e verificare quantità 4 discovery / 11 test, 4 / 10 gruppi, coppia di finestra condivisa non separata, nessun `case_id→reason` nel report. Non effettuare chiamate ai modelli; non scrivere un piano runnable; non modificare freeze EVALUATION20.

## 15. Preview V0 reale e revisione metodologica V1 (11 novembre 2026)

**Output Colab V0 ricevuto dall'utente** al commit `ce7463fcbe19046399f6a6186a73aa40885a6f6c`: `rq2_stratified_partition_preview_v0`, `DRAFT_NOT_EXECUTABLE`, sorgenti verificate, **4 discovery / 11 test** su **4 / 10 gruppi**, distribuzione aggregata delle quattro classi **discovery 1/1/1/1; test 2/2/3/4**. La coppia multi-fault `cloudbed-1_q014`/`cloudbed-1_q030` resta tutta nel test. Nessuna API o scrittura; etichette lette soltanto per partizionamento offline, mai esposte come mapping per caso.

**ID discovery V0**: `cloudbed-2_q021`, `cloudbed-2_q040`, `cloudbed-2_q041`, `cloudbed-2_q076`. **Tutte quattro discovery su cloudbed-2**. Inoltre le finestre di `cloudbed-2_q040` e `cloudbed-2_q041` sono contigue, anche se non sovrapposte. Nessun dato del modello è stato ancora osservato. **Decisione: NON congelare la V0**; archiviare integralmente stdout e motivazione in `docs/ood/REPORT_ANTEPRIMA_PARTIZIONE_RQ2_V0_2026-11-11.md`.

**Perché V1:** prima delle inferenze, correggere sbilanciamento ambientale e potenziali dipendenze di finestre contigue. **Preparati e caricati su GitHub, non ancora testati in PyCharm né Colab**:
- `src/evaluation/rq2_partition_preview_v1.py`: selezione deterministica per classe su finestre singleton non contigue ad altre, preservando esempi test di ogni classe per cloudbed, preferenza 2+2 discovery fra i due cloudbed e minimizzazione dei vicini discovery/test, tie-break SHA fissato.
- `src/tests/test_rq2_partition_preview_v1.py`: **7 test sintetici** previsti per bilanciamento, coerenza del gruppo condiviso, determinismo, protezione GT, adiacenze, cause sconosciute/archivio mancante, metrica gap.
- `notebooks/Colab_RQ2_Balanced_Partition_Preview_2026_11_11.ipynb`: unica cella che recupera il branch, verifica gli input, esegue il selettore **senza chiamate ai modelli e senza scritture**. Status `DRAFT_NOT_EXECUTABLE`.
- `docs/ood/PROTOCOLLO_RQ2_BOZZA_V0_2026-11-11.md` aggiornato con emendamento di metodo. La proposta non è un protocollo congelato.

**Passo immediato:** PyCharm `python -m unittest discover -s src/tests -p "test_rq2_partition_preview_v1.py" -v`; se i test passano, anteprima reale Colab V1. Non avviare Gemini/Claude né alterare V0/RQ1 prima di rivedere la selezione risultante.

## 16. Test PyCharm V1 superati (11 novembre 2026)

L'utente ha riportato `Ran 13 tests in 0.491s — OK` eseguendo la discovery `test_rq2_partition_preview_v1.py`. Le 13 esecuzioni includono **7 test nuovi della V1** e **6 test della V0 reimportati** a causa dell'importazione a livello di modulo della classe `unittest.TestCase` V0. Non significa che siano stati aggiunti sei nuovi test V1.

Correzione di sola organizzazione della suite al commit `7584086dfee55619d67a96ac7f257a2df92ef8cc`: la classe di fixture V0 ora viene raggiunta attraverso un import di modulo, così la discovery di `unittest` non dovrebbe più includere i sei test V0 quando si cerca il file V1. **Non modifica il selettore V1 né la partizione, né le sorgenti Market.** La conferma dei 7 test dopo la correzione resta da eseguire se si desidera il conteggio pulito.

**Prossimo passo:** anteprima reale `notebooks/Colab_RQ2_Balanced_Partition_Preview_2026_11_11.ipynb`; verificare che i vincoli V1 siano fattibili su Market, senza creare file o eseguire chiamate LLM. **Nessuna selezione congelata.**

## 17. Anteprima V1 reale e prima bozza dei contratti diagnostici (11 novembre 2026)

**Colab V1 eseguita dall'utente** al commit `f3382d43d80bd82d400749fbf5315ccc8b63ea89`: `rq2_partition_preview_balanced_v1`, `status=DRAFT_NOT_EXECUTABLE`, `source_verified=true`; 11 singleton eleggibili, 24 partizioni candidate valide, **4 discovery/11 test**, **4/10 gruppi temporali**, discovery distribuite **2 cloudbed-1 / 2 cloudbed-2**. Test distribuiti 4/7. `cross_phase_near_pairs_3600s=0`, distanza minima fra finestre di fasi diverse nello stesso cloudbed `5400` secondi. Distribuzione target per classe: discovery `1/1/1/1`; test `2/2/3/4`. `container write I/O load` solo cloudbed-2. Coppia multi-fault sempre insieme nel test. Nessuna API, file scritto o esposizione mapping case→classe.

**Discovery candidate V1:** `cloudbed-1_q032`, `cloudbed-1_q050`, `cloudbed-2_q026`, `cloudbed-2_q045`. **Test V1:** `cloudbed-1_q014`, `cloudbed-1_q021`, `cloudbed-1_q030`, `cloudbed-1_q059`, `cloudbed-2_q014`, `cloudbed-2_q021`, `cloudbed-2_q040`, `cloudbed-2_q041`, `cloudbed-2_q058`, `cloudbed-2_q076`, `cloudbed-2_q077`. Questi elenchi **NON sono un piano eseguibile congelato**; V0 archiviata separatamente.

**Nuovo report:** `docs/ood/REPORT_ANTEPRIMA_PARTIZIONE_RQ2_V1_2026-11-11.md`, con tutti i dati aggregati e le limitazioni.

**Implementazione preliminare dei contratti senza GT**:
- Documento `docs/ood/CONTRATTI_RQ2_DIAGNOSI_E_PSEUDOREGOLA_V0_2026-11-11.md`: D = RCA originale; C = schema JSON per causa/astensione uniforme senza elenco delle quattro classi; K = schema JSON per proposta pseudoregola solo su discovery, con evidenze verificate, condizioni finite, controlli negativi/astensione. Non equivale allo scorer Microsoft.
- Modulo `src/evaluation/rq2_output_contracts.py`: parsing JSON stretto, chiavi chiuse, ID evidenza allowlisted, `candidate/insufficient_evidence`; pseudocode trattato solo come testo. **Nessuna importazione del GT o API**.
- Test `src/tests/test_rq2_output_contracts.py`: 16 casi sintetici predisposti, **NON ancora eseguiti dall'utente**.
- Protocollo `docs/ood/PROTOCOLLO_RQ2_BOZZA_V0_2026-11-11.md` aggiornato con report V1 e contratti.

**Prossimo passo:** PyCharm `python -m unittest discover -s src/tests -p "test_rq2_output_contracts.py" -v`; poi progettare il bundle di evidenze C/K e relativi test, valutare la fattibilità degli input che userà davvero l'agente, fissare prompt e metriche prima del freeze. Il gap temporale e il bilanciamento non provano indipendenza fisica; con 2 positivi di test per due classi non vantare generalizzazione robusta. **Nessuna chiamata Gemini/Claude autorizzata.**

## 18. Test contratti C/K completati e bundle di evidenze predisposto (11 novembre 2026)

**Verifica PyCharm riferita dall'utente:** `Ran 16 tests in 0.034s — OK` per `test_rq2_output_contracts.py`. Sono **16 test sintetici superati**, non una valutazione su risposte LLM reali. Validano le strutture C (`rq2_cause_probe_v0`) e K (`rq2_candidate_rule_v0`), astensioni, evidenze allowlisted, soglie numeriche finite, JSON rigoroso, ma non accertano validità scientifica delle diagnosi.

**Nuovo lavoro preparato (NON ancora testato dall'utente):**
- `src/evaluation/rq2_evidence_bundle.py`: costruzione **deterministica senza GT** di evidenze numerate da `tool_trajectory` realmente registrato, con argomenti/provenienza, SHA256, troncamento dichiarato, blocco di nomi tool non autorizzati e marcatori GT.
- `src/tests/test_rq2_evidence_bundle.py`: **14 test sintetici** da eseguire in PyCharm.
- `docs/ood/BUNDLE_EVIDENZE_RQ2_PROGETTAZIONE_V0_2026-11-11.md`: motivazioni tecniche, formato, limiti, compatibilità con runner RQ1 ed evidenze.
- Rilevazione importante dal codice GitHub: in `src/agent/graph_engine.py` (A0, A1, A1_8R) le traiettorie storiche **non** conservano `tool_call_id`, mentre in `src/agent/verify_graph.py` esistono `tool_call_id` e `origine`. Perciò il nuovo bundle associa i risultati legacy ai parametri soltanto se c'è **una sola chiamata pendente dello stesso tool**; in presenza di ambiguità rifiuta anziché inventare provenienza. Per l'integrazione operativa RQ2 potrà essere necessario aggiornare un **nuovo runner dedicato** per preservare gli ID, lasciando RQ1 intatta.
- Il bundler non legge Market.zip o altri file, non modifica tool, non accede a scoring, non chiama LLM e non scrive. Le osservazioni dei tool restano dati potenzialmente non attendibili e il riferimento a un evidence ID **non** certifica supporto causale.

**Prossimo passo:** PyCharm `python -m unittest discover -s src/tests -p "test_rq2_evidence_bundle.py" -v`. Solo dopo esito verificato si procederà alla creazione di adapter e test mock, alla definizione dei prompt e poi al protocollo congelato. V1 split resta candidata, non è stato autorizzato alcun pilot API.

## 19. 11 novembre 2026 — Bundle evidenze: test PyCharm superati

Output riportato dall'utente dopo aggiornamento branch e riesecuzione del comando corretto: `Ran 14 tests in 0.009s — OK` per `python -m unittest discover -s src/tests -p "test_rq2_evidence_bundle.py" -v`. Il precedente `Ran 0 tests` era dovuto a mancata individuazione del file nella copia locale, non a un fallimento del modulo. **Quattordici test sintetici superati** sul bundle; non significa che la telemetria reale o il percorso LLM end-to-end siano già stati verificati. Nessuna chiamata API e nessun nuovo esperimento OOD eseguito.

## 20. Test bundle riusciti e primo adapter D→C/K offline (11 novembre 2026)

**Output PyCharm dell'utente:** `Ran 14 tests in 0.009s — OK` con `test_rq2_evidence_bundle.py`; le 14 verifiche sintetiche **sono passate**, non costituiscono prove su telemetria Market o run end-to-end. Registrazione del risultato al commit `c95242a6782fb94e11049de23c3a1fae70a9b657`.

**Nuovo adapter preparato, non ancora testato dall'utente:**
- `src/evaluation/rq2_probe_adapter.py`: funzioni pure per assemblare input uniformi C e K da output D esistente (istruzione originale + bundle evidence), senza inoltrare `raw_response` D, senza lettura di GT, database o dataset, senza provider né file write. Contratti C/K già predisposti. `phase=discovery` obbligatorio per K, ma **il futuro runner deve confrontare la fase con un piano congelato**: questo adapter da solo non autentica l'allocazione.
- `src/tests/test_rq2_probe_adapter.py`: **14 test sintetici preparati**, NON ancora eseguiti. Verifiche su provenienza, errore D, K solo in discovery, C valida, astensione, content segregation (non garanzia totale anti-injection), assenza di label GT, determinismo hash.
- `docs/ood/ADAPTER_RQ2_D_C_K_BOZZA_V0_2026-11-11.md`: design, proprietà e limitazioni.
- I pacchetti generati sono **offline** con `model_api_calls=0`, `ready_for_api=false`; nessun LLM è stato chiamato. I runner di RQ1 restano invariati.

**Prossimo passo:** `python -m unittest discover -s src/tests -p "test_rq2_probe_adapter.py" -v` in PyCharm dopo pull del branch; attesi **14 test**. Successivamente integrare soltanto in un nuovo runner RQ2 con piano create-only/frozen, policy anti-GT, pilot mock, budget e consenso API.

## 21. Adapter verificato e dry-run GT-free del piano D/C/K (11 novembre 2026)

**Output PyCharm dell'utente:** `Ran 14 tests in 0.009s — OK` con `test_rq2_probe_adapter.py`. **Quattordici test sintetici dell'adapter D→C/K superati.** Non costituiscono inferenze OOD o validazione di pseudoregole su dati reali.

**Nuovo passo preparatorio, non ancora testato dall'utente:**
- `src/evaluation/rq2_dryrun_plan.py`: solo `inventory_ood`/CSV GT-free con hash congelati e selezione V1 candidata già verificata in Colab; genera in memoria **90 stage D + 90 C + 24 K = 204 passaggi logici** per 15 query × 2 harness × 3 modelli logici. Queste **NON sono 204 chiamate API**. K solo discovery. Blocca test prima di freeze dei candidati come requisito da imporre nel futuro runner; qui non esiste dispatch. `status=DRAFT_NOT_EXECUTABLE`, `can_execute_api=false`, `api_budget_approved=false`, nessuna API e nessun file scritto.
- `src/tests/test_rq2_dryrun_plan.py`: **15 test sintetici** predisposti, non ancora eseguiti dall'utente. Validano vincoli sulla fase, dipendenze e separazione gruppi, SHA, mancato accesso al GT, dati fuori schema, ID duplicati, blocco API.
- `notebooks/Colab_RQ2_DryRun_Workflow_Preflight_2026_11_11.ipynb`: una cella, *solo dopo test PyCharm*; controlla realmente SHA dei due CSV e stampa soltanto riepilogo GT-free.
- `docs/ood/DRYRUN_PIANO_ESECUZIONI_RQ2_V0_2026-11-11.md`: dettagli e distinzione tra conteggi logici e costo inferenziale.
- Attenzione: versione/modello provider, budget API, runner autonomo create-only, policy test post-freeze e metrica qualità delle regole restano **non fissati**. Non avviare API o scoring e non modificare RQ1.

**Passo immediato:** PyCharm `python -m unittest discover -s src/tests -p "test_rq2_dryrun_plan.py" -v`; attesi 15 test. Solo dopo preflight Colab GT-free del piano dry-run e revisione del protocollo prima di qualunque run.

## 22. Test dry-run PyCharm: 14/15 superati, corretto falso positivo del controllo anti-GT (11 novembre 2026)

L'utente ha fornito il log completo della suite `test_rq2_dryrun_plan.py`: `Ran 15 tests in 0.025s — FAILED (failures=1)`. Il **solo** test fallito era `test_no_label_mapping_or_scoring_leak_in_plan` (`term='ground_truth'`): il test cercava `ground_truth` nell'intera rappresentazione testuale del dizionario `plan()` e trovava la **chiave di audit lecita** `reads_ground_truth: False`. L'indicatore dichiara esplicitamente che il generatore non ha letto GT; **il log non evidenzia un mapping caso→etichetta né una perdita di ground truth**. Gli altri 14 test della suite erano superati.

**Correzione mirata** al commit `9997d0adf38bc42260ca5db3f440126e42ebc1a4`, esclusivamente `src/tests/test_rq2_dryrun_plan.py`: sostituito il controllo testuale indiscriminato con verifica della flag `reads_ground_truth=False` e delle allowlist strutturali chiuse delle chiavi di `entries` e `partition`, con controllo dei marcatori GT nei valori testuali degli stage. Non cambia `src/evaluation/rq2_dryrun_plan.py`, non cambia la partizione V1, né uno scorer, un prompt, una run o il freeze RQ1.

**Da rifare in PyCharm:** `git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10`; poi `PYTHONPATH=src python -m unittest discover -s src/tests -p "test_rq2_dryrun_plan.py" -v`. Attesi 15 test, da considerare PASS solo dopo nuovo output dell'utente. Il notebook Colab preflight resta bloccato fino alla verifica. Nessuna API autorizzata.

## 23. Test dry-run RQ2 superati in PyCharm dopo correzione del falso positivo (11 novembre 2026)

Output effettivamente inviato dall'utente: `Ran 15 tests in 0.067s — OK` dopo pull della correzione mirata al test `test_no_label_mapping_or_scoring_leak_in_plan` e nuovo avvio della suite `test_rq2_dryrun_plan.py`. Tutti i **15 test sintetici** risultano quindi superati. Il precedente failure su `reads_ground_truth=False` era un falso positivo della ricerca di sottostringa; l'assert ora controlla strutture/chiavi permesse e il valore booleano senza confondere una proprietà di audit con un'etichetta.

**Stato:** il generatore `src/evaluation/rq2_dryrun_plan.py` e il protocollo RQ2 restano `DRAFT_NOT_EXECUTABLE`; nessuna chiamata modello, piano create-only, risultato D/C/K reale o modifica RQ1.

**Prossimo passo autorizzato come controllo offline:** notebook `notebooks/Colab_RQ2_DryRun_Workflow_Preflight_2026_11_11.ipynb`, una cella, verifica SHA reali e metadati della coorte GT-free, attesi 4 discovery + 11 test in 4+10 gruppi, 90 D + 90 C + 24 K = **204 stage logici**, `can_execute_api=false` e `model_api_calls=0`. Non sono 204 chiamate API. L'esito su Market reale non è ancora stato ottenuto; richiedere l'output Colab per audit. Nessuna chiamata Gemini o Claude autorizzata.

## 24. Preflight dry-run sul Market reale superato (11 novembre 2026)

**Output completo Colab fornito dall'utente**, branch `feature/ood-knowledge-transfer-audit-2026-11-10`, commit eseguito `5a254dc6f5cbf6a03f89aa2ce12df251553e388a`. Preflight `rq2_dryrun_workflow_preview_v0`, `status=DRAFT_NOT_EXECUTABLE`, `preview_only=true`, `source_verified=true`.
- Hash originali verificati: split `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`; manifest `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`.
- Partizione candidata V1 confermata esattamente: discovery `cloudbed-1_q032`, `cloudbed-1_q050`, `cloudbed-2_q026`, `cloudbed-2_q045`; test `cloudbed-1_q014`, `cloudbed-1_q021`, `cloudbed-1_q030`, `cloudbed-1_q059`, `cloudbed-2_q014`, `cloudbed-2_q021`, `cloudbed-2_q040`, `cloudbed-2_q041`, `cloudbed-2_q058`, `cloudbed-2_q076`, `cloudbed-2_q077`.
- 4 discovery e 11 test su 4+10 gruppi temporali; discovery 2+2 per cloudbed, test 4+7; gap cross-phase minimo nello stesso cloudbed 5400 s.
- 3 modelli **logici**: gemini, sonnet, haiku; 2 harness: `A1`, `A1_8R`. **90 stage D + 90 C + 24 K = 204 stage logici**, *non* 204 invocazioni API, poiché D può richiedere più chiamate LLM.
- Blocco: `provider_model_versions_frozen=false`, `api_budget_approved=false`, `can_execute_api=false`, `cross_phase_gate=TEST_BLOCKED_UNTIL_DISCOVERY_RULES_FREEZE`. `model_api_calls=0`, `files_written=false`, `reads_ground_truth=false`, `reads_predictions=false`, `reads_telemetry=false`. `preview_sha256=ecd6d926933a5ad056ad1a581fa7e490c0a13eee18070c7dac8627c1b19c062e`.
- La suite PyCharm di 15 test del generatore era già stata superata dopo il fix del falso positivo. Il notebook non ha scritto piani o risultati né modificato RQ1.

**Decisione:** accettare questo output come **preflight GT-free riuscito**, conservando `DRAFT_NOT_EXECUTABLE`. Non autorizza run, salvataggi sperimentali, scoring o congelamento del protocollo. Step seguente: verifica isolata create-only/restart/mock (senza provider) e controlli del freeze discovery→test; solo poi implementazione di runner RQ2 separato con autorizzazione API esplicita.

## 25. Preparato test isolato di journal create-only e blocco discovery→test (11 novembre 2026)

In seguito all'output Colab GT-free riuscito (vedere §24), è stato predisposto un **mock journal** in `src/evaluation/rq2_mock_journal.py`, completamente distinto dal futuro runner API. **Non importa provider né tool, non accede a dataset/scoring, non esegue diagnosi, prompt, classificazioni o pseudoregole**. Accetta esclusivamente il piano `DRAFT_NOT_EXECUTABLE` con `can_execute_api=false`, 204 stage e hash coerenti. Produce **solo ricevute sintetiche in cartelle temporanee**, con scrittura create-only `O_EXCL`, gestione fail-closed di file parziali, hash, restart/resume e dipendenze.

La transizione test richiede che tutti i **24 K discovery mock** siano completati e un file `MOCK_DISCOVERY_FREEZE.json` sia creato una sola volta. **Questo non è un freeze scientifico di regole** e non può autorizzare le chiamate reali. Eventuali modifiche alle ricevute dopo freeze falliscono in audit. Anche senza freeze mock, lo stage di test non può essere simulato.

**Nuovi file preparati (NON ancora testati dall'utente):**
- `src/evaluation/rq2_mock_journal.py`: transizioni e persistenza simulata, non esecuzione.
- `src/tests/test_rq2_mock_journal.py`: **18 test sintetici** su `tempfile.TemporaryDirectory()` per create-only, doppio invio, corrupt restart, 204 stage mock, blocco test, tampering, no API.
- `docs/ood/RQ2_MOCK_JOURNAL_PREPARAZIONE_2026-11-11.md`: design e limitazioni.

**Passo successivo:** PyCharm `python -m unittest discover -s src/tests -p "test_rq2_mock_journal.py" -v`, attesi 18 test. Non avviare Colab o modelli per questi test. Protocollo V1 e run plan restano non congelati; dopo verifica bisognerà aggiungere un runner RQ2 reale separato, con guardie GT e budget autorizzato, non promuovere il journal mock a runner.

## 26. Journal mock: 18 test completati correttamente (11 novembre 2026)

L'utente ha eseguito in PyCharm il file `test_rq2_mock_journal.py`, riportando **`Ran 18 tests in 8.944s — OK`**. Risultato: tutte le 18 verifiche sintetiche superate, comprese le transizioni D/C/K simulate, il create-only, i riavvii, gli hash, il blocco del test prima del freeze **mock** e l'assenza di invocazioni provider. L'esito non equivale a un vero freeze delle regole né a un test sul Market con modelli reali.

Controllo successivo sul codice già esistente del repository: `src/evaluation/experiment_runner.py` espone `prepara_esperimento(config)` (preprocessing GT-free), `run_experiment(config, llm=None, verbose=True, salva=False)` con creazione eventuale di un modello **se llm è None** e ritorna `raw_response`, `prediction`, `metrics`, `tool_trajectory`, `error`. La configurazione `src/evaluation/experiment_config.py` distingue `variant_scheme="current"` da `historic_v3`. La factory `src/agent/tool_factory.py` offre cinque tool: `tool_get_service_metrics`, `tool_get_container_metrics`, `tool_get_node_metrics`, `tool_get_logs`, `tool_get_traces`.

**Vincolo per la futura integrazione:** la sola creazione di `ExperimentConfig` e la preparazione dei messaggi C/K devono restare offline; **non chiamare `run_experiment` né `crea_modello` finché non esistono protocollo/piano/richiesta di spesa congelati e consenso esplicito**. Se un test richiede la risposta D, iniettarla come dizionario sintetico, non eseguire il runner storico. Il journal mock è una verifica di persistenza, non una funzione di provider dispatch.

## 27. Preflight di compatibilità su traiettorie RQ1 V3 reali — predisposto, non ancora eseguito (11 novembre 2026)

Per evitare un'integrazione RQ2 che fallisca su traiettorie reali, dopo **18 test mock journal superati** si è esaminato il codice storico:
- `src/evaluation/experiment_runner.py`: `run_experiment(config,llm=None,verbose=True,salva=False)` può chiamare API **se `llm=None`**; non invocare per audit. Ritorna `tool_trajectory`, `raw_response`, `error` e metriche. Il preprocessing `prepara_esperimento` legge solo telemetria GT-free. Non va modificato il codice RQ1 congelato.
- `src/agent/tool_factory.py`: esattamente cinque strumenti: `tool_get_service_metrics`, `tool_get_container_metrics`, `tool_get_node_metrics`, `tool_get_logs`, `tool_get_traces`.
- La cartella dati congelati V3 è `data/results/v2/openrca_harness_v2_five_agents_development_v3`, come da README. I risultati di scoring sono in directory separata e non vanno letti.

**Nuovi artefatti preparati:**
- `src/evaluation/rq2_historical_trajectory_audit.py`: ispezione **solo aggregata e di sola lettura** delle traiettorie JSON storiche V3 per misurare percentuale di bundle ricostruibili e ambiguità dell'associazione call-result, senza stampare ID casi, telemetria, predizioni, score o classi. Non apre Market.zip, CSV né casi OOD, non scrive o chiama provider.
- `src/tests/test_rq2_historical_trajectory_audit.py`: **12 test sintetici** preparati, non ancora eseguiti. **Non riportarli come riusciti finché non arriva l'output PyCharm**.
- `notebooks/Colab_RQ2_Historical_Trajectory_Feasibility_2026_11_11.ipynb`: preflight Colab a una cella (da eseguire soltanto dopo i 12 test).
- `docs/ood/AUDIT_TRAIETTORIE_V3_PER_RUNNER_RQ2_2026-11-11.md`: motivazioni e limiti.

**Razionale:** usare risultati V3 soltanto per audit di formato, **non** per progettare o adattare pseudoregole OOD o conoscere le risposte della coorte di test. Prima di implementare il runner provider occorre risolvere o registrare come non disponibile la provenienza di tool-result associati ambiguamente. L'uso di `run_experiment` con `salva=False` **non** elimina le chiamate API: serve ancora autorizzazione esplicita, budget e freeze. La partizione V1 resta candidata, non si è avviato alcun esperimento OOD.

**Prossimo comando in PyCharm:** `python -m unittest discover -s src/tests -p "test_rq2_historical_trajectory_audit.py" -v` dopo pull; attesi **12 test**. Poi Colab di lettura della sola cartella V3 se la directory è presente.

## 28. Test audit traiettorie V3: errore in una sola asserzione di conteggio (11 novembre 2026)

L'utente ha eseguito `python -m unittest discover -s src/tests -p "test_rq2_historical_trajectory_audit.py" -v`; output: **12 test, 11 OK, 1 ERROR**, nel test `test_unrelated_json_in_known_result_dir_skipped`. Il report usa `Counter` ma restituisce una normale `dict` con sole categorie osservate: quando il file sintetico `claim.json` non contiene `tool_trajectory`, il contatore `result_records_with_trajectory` non è presente e l'asserzione diretta causa `KeyError`. Questo **non** implica un difetto di lettura GT, di protezione di scorer o del bundler.

**Correzione limitata alla suite** al commit `be63e41403521b6469432743494810999368842c`: sostituita in `src/tests/test_rq2_historical_trajectory_audit.py` la singola lettura del contatore con `report["counts"].get("result_records_with_trajectory", 0)`. Nessuna modifica al modulo audit, runner, dati o codice congelato RQ1.

**Da verificare in PyCharm:** `git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10` e rieseguire i 12 test. Il Colab `Colab_RQ2_Historical_Trajectory_Feasibility_2026_11_11.ipynb` resta da eseguire solo dopo successo completo; nessuna inferenza API consentita.

## 29. Audit traiettorie V3: 12/12 test sintetici superati (11 novembre 2026)

**Verifica PyCharm comunicata dall'utente:** `Ran 12 tests in 0.236s — OK`, dopo la correzione mirata del test `test_unrelated_json_in_known_result_dir_skipped` al commit `be63e41403521b6469432743494810999368842c`. Tutti i 12 test sintetici dell'audit `src/evaluation/rq2_historical_trajectory_audit.py` sono ora superati: si controllano assenza della directory, parser di risultati, associazione ambigua tool-call↔tool-result, esclusione della directory scoring, assenza di modifica dei file originali, ecc. **Non** è ancora una verifica delle traiettorie V3 reali.

**Prossimo passaggio previsto:** eseguire la **sola cella** del notebook `notebooks/Colab_RQ2_Historical_Trajectory_Feasibility_2026_11_11.ipynb`, che ispeziona in sola lettura i JSON dei risultati V3 già congelati nella directory `data/results/v2/openrca_harness_v2_five_agents_development_v3`. Controllare nel riepilogo aggregato `counts` e `incompatibility_reasons` per decidere se occorre una raccolta RQ2 che mantenga `tool_call_id` o una gestione di indisponibilità del bundle. **Non** aprire score, GT, Market.zip o le 15 query OOD; nessuna API o file di risultati nuovi. La partizione RQ2 V1 resta `DRAFT_NOT_EXECUTABLE`, non congelata.
