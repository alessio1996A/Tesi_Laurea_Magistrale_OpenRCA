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

## 30. Audit reale compatibilità V3: 40/40 bundle ricostruibili e 71/209 osservazioni troncate (11 novembre 2026)

**Output Colab riportato dall'utente**, eseguito sul commit `57002748bdb44ad04a3fe15d48a7f4687df796fe`: `rq2_historical_trajectory_feasibility_v0`, `status=HISTORICAL_COMPATIBILITY_ONLY`, `read_only=true`, `read_ground_truth=false`, `read_scoring=false`, `read_ood_cases=false`, `model_api_calls=0`, `files_written=false`.

Aggregati osservati realmente dalla cartella congelata `data/results/v2/openrca_harness_v2_five_agents_development_v3`:
- `json_files=80`: 40 JSON con `tool_trajectory` + 40 JSON non di risultato;
- `result_records_with_trajectory=40`;
- `bundle_structurally_usable=40` — **40/40**, nessuna incompatibilità strutturale nell'audit di questa coorte;
- `observations=209`; `truncated_observations=71`, cioè **33.97%** delle osservazioni;
- `incompatibility_reasons={}`.

**Interpretazione**: il bundler attuale supporta tutte le 40 traiettorie storiche V3 esaminate, dunque gli identificativi di tool-call mancanti nel runner legacy non impediscono la ricostruzione dei *dati osservati* su questa coorte; non è necessario alterare retroattivamente il grafo RQ1. L'assenza di ambiguità su V3 **non garantisce** che nuovi run RQ2 non generino chiamate parallele e non dimostra validità causale. L'alto troncamento di 71/209 è un rischio di **sufficienza semantica** delle evidenze C/K, pur non invalidando gli hash delle osservazioni; rilevare e riportare sempre `truncated` e trattare ogni possibile perdita come limitazione.

**Decisione scientifica da fissare prima del freeze**: RQ2-B (generazione della pseudoregola) e RQ2-C (sua applicazione deterministica offline cieca sul test con positivi/negativi e controllo multi-fault) sono risultati distinti. Generare 24 candidati K e poi eseguire solo D/C sui test non dimostra trasferimento della conoscenza; occorre predefinire criterio di scelta/formalizzabilità e la verifica della regola **senza guardare il test**, non implementare codice suggerito dal modello in automatico né introdurre nuovi detector nel freeze RQ1. Se nessun candidato è implementabile, dichiarare esito negativo/non valutabile per RQ2-C.

**Prossimo passo tecnico**: binding in memoria delle richieste C/K al piano GT-free, allo stage ID, al D originale e alla C precedente; nessuna API e nessuna persistenza. Poi progettare runner RQ2 con budget+autorizzazione, e protocollo scientifico congelato prima dei casi OOD. L'audit V3 non utilizza output storici per formulare o tarare regole RQ2.

## 31. Adapter GT-free con binding dei passaggi C/K al piano e alle run D (11 novembre 2026)

Dopo l'audit V3 reale registrato al §30 (**40/40 traiettorie compatibili, 209 osservazioni, 71 troncate, zero chiamate API**), è stato preparato un ulteriore strato esclusivamente **offline/in memoria**:
- `src/evaluation/rq2_stage_binding.py`: `prepare_bound_c` e `prepare_bound_k` controllano lo SHA del piano `rq2_dryrun_workflow_preview_v0`, lo schema chiuso GT-free, l'assegnazione caso/modello/harness/fase, le dipendenze D→C→K, i metadati `case_id`/`variant`/`variant_scheme=current`/`model_provider`/`max_tool_rounds` del risultato D e la parità deterministica fra la C precedente e l'input D+istruzione originale quando si propone K. K non viene costruita sul test. Non importa o esegue `run_experiment`, tool, provider, CSV, dataset, scoring e non scrive file. I pacchetti rimangono `can_execute_api=false`, `model_api_calls=0`, `scientific_rules_frozen=false`.
- `src/tests/test_rq2_stage_binding.py`: **20 test sintetici predisposti, NON ancora eseguiti dall'utente**; verificano contaminazioni di ID, altre varianti/modelli, GT extra, SHA, K solo discovery, riferimenti errati, errore provider D e non-esecuzione.
- `docs/ood/REPORT_AUDIT_V3_E_BINDING_RQ2_2026-11-11.md`: quadro di evidenze, rischi del troncamento, controllo di identità e **distinzione fondamentale fra proposta K (RQ2-B) e verifica offline cieca della regola (RQ2-C)**.

**Rimane aperto per la vera inferenza:** `source_verified_in_this_function=false`; i nomi dei provider sono solo associati alle famiglie logiche `gemini`/`sonnet`/`haiku`, non sono congelati gli ID esatti del modello o i parametri; il nuovo modulo non legge i byte del manifest per verificare `original_instruction`. Un futuro runner deve validare sorgenti, modello, prompt, temperature e budget, piano create-only, integrità/ripresa, e consenso API prima di qualsiasi chiamata reale. I 20 test di binding sono la prossima verifica locale; non avviare ancora Colab.

**Comando PyCharm:** `python -m unittest discover -s src/tests -p "test_rq2_stage_binding.py" -v` dopo pull, attesi 20 test. Nessun esperimento OOD già lanciato. Nessuna modifica RQ1.

## 32. Binding offline D→C/K: 20 test sintetici superati in PyCharm (11 novembre 2026)

**Output effettivo dell'utente:** `Ran 20 tests in 0.339s — OK`, per la suite `src/tests/test_rq2_stage_binding.py`. I **20 test sintetici** sono quindi superati; confermano controlli preliminari di associazione fra caso/modello/harness, provenienza D→C/K, blocco K sul test, schema GT-free chiuso e assenza di autorizzazione API. Non dimostrano integrità dei dati Market reali, precisione della diagnosi né efficacia di pseudoregole.

Il report della coorte storica V3 rimane: **40/40 bundle strutturalmente ricostruibili**, **209 osservazioni**, **71 troncate**, zero incompatibilità; per i casi RQ2 resta obbligatorio verificare provenance e troncamento run per run.

**Prossimo punto scientifico prioritario prima di chiamate provider:** definire e preregistrare la differenza tra RQ2-B (generazione della specifica K) e RQ2-C (implementazione offline controllata, senza eseguire pseudocode LLM, congelata prima del test, e valutazione su positivi/negativi con particolarità multi-fault). Questo richiede anche scelta ex ante della regola principale, criteri di implementabilità e astensione; le 24 K proposte non sono di per sé evidenza di trasferimento. La partizione V1 e il piano rimangono `DRAFT_NOT_EXECUTABLE`. Nessuna inferenza OOD o chiamata API ancora autorizzata.

## 33. Predisposto scorer offline RQ2-C per gruppi temporali multi-fault (11 novembre 2026)

**Base verificata:** suite PyCharm `test_rq2_stage_binding.py` completata dall'utente, `Ran 20 tests in 0.339s — OK` (§32). Nessuna API/LLM per RQ2.

**Nuovi artefatti predisposti, NON ancora eseguiti dall'utente:**
- `src/evaluation/rq2_rule_group_scorer.py`: valutatore *offline, in memoria* per gli esiti di una **regola già congelata e applicata altrove**. Non produce né interpreta pseudocodice di un LLM, non apre dataset e non chiama provider. Richiede che il **solo processo di valutazione isolato** fornisca i riferimenti completi per ogni gruppo di finestra. Un gruppo con due classi è positivo per **entrambe**; uno con reference incompleta non è mai negativo per default. Output solo aggregati TP/FP/TN/FN, astensioni, errori, gruppi unscorable, coverage e tassi condizionati. **Questo modulo riceve intenzionalmente etichette dal chiamante dello scorer: non importarlo nell'agente, nel runner GT-free o nei prompt!**
- `src/tests/test_rq2_rule_group_scorer.py`: **20 test sintetici preparati**, mai su vero Market; **ancora da verificare in PyCharm**. Controllano multi-fault, deduplicazione gruppo/caso, KPI di copertura, gestione delle astensioni/errori, tassi senza denominatore, dati sconosciuti, output privo di mapping di classi per caso.
- `docs/ood/RQ2_C_VALUTAZIONE_OFFLINE_REGOLE_PROPOSTA_V0_2026-11-11.md`: propone griglia di formalizzabilità prima del test, distinzione fra `RQ2-B` (generazione di K) e `RQ2-C` (applicazione cieca di regole fisse), metriche, negativi one-vs-rest, gestione finestra multi-fault e decisioni da preregistrare.

**Non congelare ancora:** manca catalogo KPI/unità realmente disponibili, criteri meccanici di formalizzabilità, criterio ex ante di selezione del braccio/regola principale e implementazione offline del detector, ID modello/budget API/persistenza reale. Lo scorer è un pezzo di valutazione, **non** dimostra conoscenza trasferita in questa fase. Non applicarlo alle 10 finestre reali di test prima che protocolli e regole siano congelati, e non inserire GT nel runner.

**Prossimo comando PyCharm** dopo `git pull --ff-only`: `python -m unittest discover -s src/tests -p "test_rq2_rule_group_scorer.py" -v`. Attesi 20 test sintetici.

## 34. Scorer RQ2-C: 20/20 test superati; audit semantica KPI e priorità pre-freeze (11 novembre 2026)

**Output effettivo dell'utente:** `Ran 20 tests in 0.006s — OK` della suite `src/tests/test_rq2_rule_group_scorer.py`. Tutti i **20 test sintetici** del valutatore offline group-level sono superati: multietichetta per la finestra condivisa, TP/FP/TN/FN, astensioni/errori, denominatori, reference incompleta. Non è stata effettuata **alcuna valutazione su telemetria OOD test o su pseudoregole reali**.

**Ispezione ulteriore di codice RQ1 (sola lettura):** `src/agent/tool_factory.py` conferma cinque strumenti e filtro di finestra; `src/evaluation/experiment_runner.py` legge node/container usando colonne `timestamp,cmdb_id,kpi_name,value`, senza unità fisica esplicita. `src/harness/signal_catalog.py` usa `gauge_candidato`, `non_verificato`, `semantica_verificata=False` per varie famiglie. Le regole R01/R06 descrivono esplicitamente ambiguità della semantica di `container_cpu_usage_seconds` e `container_fs_reads_MB./dev/vda`; MB nel nome non prova throughput MB/s.

**Nuovo documento di decisione:** `docs/ood/RQ2_DECISIONI_PRE_FREEZE_E_CATALOGO_KPI_2026-11-11.md`, commit `26ca39a10e8a2520c98d4f96cfcd097c4704a69d`. PROPONE uno specifico percorso di freeze: catalogo KPI/versione con unità e semantica verificate prima di aprire il test, gate deterministico delle K, separazione RQ2-A/B/C, designazione ex ante di confronto primario, budget, piano create-only e autorizzazione API. La proposta **non** congela le scelte, né autorizza nuovi esperimenti.

**Decisione operativa attuale:** non accumulare nuove suite senza chiarire l'eseguibilità delle K. Priorità: catalogo KPI basato su codice/documentazione e sviluppo GT-free soltanto (mai OOD test), mock provider D/C/K con persistenza reale create-only, stima API e freeze del protocollo. Poi richiesta esplicita dell'utente per eventuali chiamate a pagamento. RQ1 invariata e RQ2 ancora `DRAFT_NOT_EXECUTABLE`.

## 35. Avvio effettivo dell'ultimo blocco pre-freeze: catalogo KPI source-only (12 novembre 2026)

Su richiesta dell'utente si riprende lo sviluppo RQ2 privilegiando qualità e metodologia, senza avviare API. **Nuovi artefatti GitHub** sul solo branch `feature/ood-knowledge-transfer-audit-2026-11-10`:
- `src/evaluation/rq2_kpi_formalizability_preflight.py`: catalogo preliminare di **29 nomi KPI già presenti nel codice RQ1** (21 node + 5 container da `harness.signal_catalog`, 3 riferimenti storici R01/R06). L'inventario è GT-free e non legge Market/telemetria; identifica origine e tool, ma **non certifica** disponibilità reale, unità fisica, semantica cumulativa/gauge o aggregazioni lecite. SHA del catalogo deterministico. La funzione `evaluate_k_formalizability` valida prima il contratto K e poi distingue `invalid_contract`, `insufficient_evidence`, `requires_verification`, riportando soltanto ragioni e conteggi, senza interpretare pseudocodice. Sempre `ready_for_test=false`, `model_api_calls=0`, `files_written=false`.
- `src/tests/test_rq2_kpi_formalizability_preflight.py`: **19 test sintetici preparati ma NON ancora eseguiti in PyCharm**, nessun dataset, codice generato o provider. **Non dichiarare suite verde senza il log dell'utente**.
- `docs/ood/RQ2_CATALOGO_KPI_E_PREFLIGHT_FORMALIZZABILITA_2026-11-12.md`: documenta evidenze nel codice e distingue **formalizzabilità operativa sul valore numerico grezzo** da **interpretazione fisica verificata**. Una regola su valori grezzi potrebbe essere riproducibile senza conoscere le unità fisiche; ciò non autorizza un'affermazione di causalità o una certificazione fisica. Il modulo attuale **non certifica ancora** nessuno dei due livelli.

**Prossimo comando PyCharm dopo pull:** `python -m unittest discover -s src/tests -p "test_rq2_kpi_formalizability_preflight.py" -v`, attesi 19 test. Successivamente censimento GT-free e congelamento delle trasformazioni ammesse, integrazione runner D/C/K con fake provider e create-only, budget e vero freeze. Non introdurre regole target OOD né test basati su risultati della coorte riservata. RQ1 invariata.

## 36. Test catalogo KPI e preflight K superati in PyCharm (12 novembre 2026)

L'utente ha eseguito `test_rq2_kpi_formalizability_preflight.py`: **`Ran 19 tests in 0.032s — OK`**. I 19 test sintetici del catalogo conservativo source-only, del controllo di JSON K e delle guardie di non-eseguibilità sono passati. Questa riuscita **non** certifica la presenza dei KPI nel dataset Market o le unità/semantiche fisiche; nessun modello o caso OOD è stato interrogato.

**Prossima priorità:** preflight di disponibilità e copertura di KPI in **sorgenti GT-free development** usando esclusivamente finestre development del manifest congelato. Evitare qualunque lettura di `record.csv`, `scoring_points`, casi `ood_holdout` o predizioni di test. Distinguere disponibilità nei dati, aggregazioni sui numeri grezzi e verifica delle unità fisiche; non creare detector target OOD. Dopo il controllo della copertura, completare il runner mock D/C/K con persistenza create-only e freeze/budget prima delle API. **Protocollo RQ2 e piano restano DRAFT_NOT_EXECUTABLE**; RQ1 invariata.

## 37. Predisposto audit reale KPI solo finestre development (12 novembre 2026)

A seguito di **19/19 test del preflight K source-only superati** in PyCharm (§36), è stata ispezionata l'infrastruttura `evaluation.v2_case_window_audit`/`agent.tools` e predisposto un nuovo audit **read-only e GT-free**:
- `src/evaluation/rq2_development_kpi_audit.py`: legge i due CSV GT-free congelati `split_market_v1.csv` e `benchmark_inputs_market.csv` e ne valida gli SHA originali e il schema chiuso, poi costruisce **soltanto finestre development** (92 casi) per la lettura aggregata di `metric_node.csv`/`metric_container.csv` dal Market.zip. **Rifiuta qualunque overlap temporale development–OOD** e membro ZIP ambiguo/mancante; ciascuna riga numerica nell'unione delle finestre development è contata una sola volta. Riporta in aggregato i KPI presenti nel codice RQ1 e nomi extra rilevati nello sviluppo, senza unità fisiche inventate, etichette, singoli casi o valori grezzi. Nessun provider, scorer, accesso a `record.csv`/`query.csv`, file write o detector.
- **Limitazione di I/O dichiarata apertamente:** si attraversano membri ZIP CSV giornalieri che possono contenere righe di altri split; queste righe sono *decodificate per poter filtrare* ma **mai usate per i conteggi**, né esposte a LLM o al report. Questo è diverso dall'affermare che non siano stati letti byte giornalieri esterni al development. `source_verified=true` si riferisce agli SHA dei **due CSV GT-free**, **NON** all'hash completo di `Market.zip`, che questo audit non calcola.
- `src/tests/test_rq2_development_kpi_audit.py`: **17 test sintetici predisposti, ancora da eseguire in PyCharm**; includono guardie GT, sovrapposizione OOD, ZIP allowlist, conteggi sulle unioni temporali, timestamp finali esclusi, valori non numerici, source hash, assenza di ID/valori per caso nel report.
- `notebooks/Colab_RQ2_Development_KPI_Presence_Audit_2026_11_12.ipynb`: notebook a singola cella predisposto per **dopo** i 17 test, con commit Git e output aggregato. **Non ancora eseguito**.
- `docs/ood/RQ2_AUDIT_DISPONIBILITA_KPI_DEVELOPMENT_2026-11-12.md`: documentazione tecnica e limiti.

**Prossimo comando PyCharm**, dopo `git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10`: `python -m unittest discover -s src/tests -p "test_rq2_development_kpi_audit.py" -v`, attesi **17 test**. Solo in caso di successo passare al notebook Colab. RQ2 ancora **DRAFT_NOT_EXECUTABLE**, RQ1 congelata invariata, zero API.

## 38. Audit KPI development: 16/16 test superati; correzione conteggio suite (12 novembre 2026)

**Output PyCharm dell'utente:** `Ran 16 tests in 0.503s — OK` per `src/tests/test_rq2_development_kpi_audit.py`. L'esito è **positivo e completo**: verifica del sorgente GitHub conferma esattamente **16 metodi `unittest.TestCase.test_*`**. La precedente previsione di **17 test** nel §37 e nel report era un errore di conteggio: era stata inclusa per errore la funzione ausiliaria di modulo `def test_rows()`, che costruisce i dati sintetici e non è un metodo `unittest` eseguibile. **Non risulta alcun test saltato**. Documentazione corrente corretta, nessuna modifica al codice o agli esperimenti RQ1.

**Prossimo passo ora autorizzato per sola lettura, senza API:** esecuzione di `notebooks/Colab_RQ2_Development_KPI_Presence_Audit_2026_11_12.ipynb` (una cella). Il notebook monta Drive, verifica i due CSV GT-free congelati, analizza i dati numerici nelle sole finestre `development`, stampa riepilogo aggregato e non scrive file né chiama modelli. **Precisazione I/O:** il parsing dei CSV giornalieri può decodificare righe di altri split, che però sono escluse dalle aggregazioni; non dichiarare una separazione fisica di lettura per byte. `source_verified=true` riguarda solo i due CSV GT-free, non l'hash completo del Market.zip.

In attesa dell'output reale Colab, **non dichiarare verifica della presenza dei KPI nel Market effettivamente completata**. Il piano RQ2 rimane `DRAFT_NOT_EXECUTABLE`; non avviare inferenze.

## 39. Audit Colab reale KPI development: 29/29 KPI source-only presenti; 123 nomi in totale (12 novembre 2026)

**Output Colab completo fornito dall'utente**, notebook `notebooks/Colab_RQ2_Development_KPI_Presence_Audit_2026_11_12.ipynb` sul commit `773f86d21c2e1d44473e4d077746d2d36733e50d`. Stato osservato: `rq2_development_kpi_presence_audit_v0`, `DEVELOPMENT_ONLY_GT_FREE_NUMERIC_PRESENCE`, `source_verified=true`; hash split `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`, manifest `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`, catalogo `81958222ebe027c6f205e9b6d8fc6c562b386eba20a05436b35522dfd92cf2eb`.

**Risultati reali aggregati (non sintetici):**
- `development_cases=92`, `metrics_archive_members_read=8`;
- `rows_in_union_of_development_windows=6,722,921` e `valid_numeric_rows=6,722,921`, quindi **tutte le righe incluse nell'unione delle finestre development hanno valori numerici validi** in questi file node/container;
- `observed_distinct_metrics=numeric_distinct_metrics=123`; **29/29 KPI già censiti nel codice RQ1 presenti con valori numerici** (21 node e 8 container);
- **94 KPI aggiuntivi** non censiti nel catalogo source-only (38 node, 56 container); il report stampa i primi 60 nomi, **34 omessi**: il campione di nomi non è un catalogo completo dei 94;
- righe numeriche nelle finestre development: **785,445 node** + **5,937,476 container** = 6,722,921.
- I conteggi derivano dall'unione delle finestre: le righe in finestre development sovrapposte non sono duplicate.

**Protezioni dichiarate dall'output:** `statistics_only_development_windows=true`, `non_development_rows_filtered_before_aggregation=true`, `possible_non_development_rows_decoded_from_shared_csv=true`, `read_ground_truth=false`, `read_record_csv=false`, `read_scoring=false`, `read_ood_telemetry_for_analysis=false`, `read_model_predictions=false`, `model_api_calls=0`, `files_written=false`, `can_execute_rule=false`. I **membri CSV giornalieri condivisi sono fisicamente letti e possono contenere righe di altri split**, escluse dai conteggi. I due CSV GT-free hanno hash verificati, ma `market_archive_sha256_checked=false` (**non** è una verifica crittografica di tutta Market.zip).

**Interpretazione:** positiva la **fattibilità osservazionale** delle metriche nel development, ma **non** prova che ogni KPI compaia in ogni singolo caso, che sia presente nelle finestre OOD, che sia coerente fra cloudbed, né certifica unità fisica, tipo counter/rate, aggregazione idonea o effetto causale. Le 94 metriche extra sono osservate nel development e non sono prevalidati 94 nuovi detector; non progettare regole per le classi riservate basandosi su nomi di KPI senza discovery. Non leggere i casi OOD test per validare la disponibilità dei segnali prima del freeze.

**Conseguenza:** si può continuare con un catalogo operativo di **presenza numerica nello sviluppo**, ma separato dal livello di semantica fisica. Prossima integrazione: orchestrazione **mock-only** del percorso D→C→K sul piano non eseguibile con controlli di provenienza e create-only, nessuna API finché mancano protocollo e budget congelati. RQ1 invariata.

## 40. Integrazione mock D→C→K predisposta dopo audit KPI development (12 novembre 2026)

A seguito dell'audit reale documentato al §39 (92 development, **6.722.921 righe numeriche**, **29/29 KPI censiti presenti nell'unione delle finestre**, **123 nomi KPI**, 94 ulteriori nomi), è stata costruita la **prova d'integrazione sintetica** fra i componenti RQ2 già testati:

- `src/evaluation/rq2_mock_pipeline_integration.py`: helper **solo mock**. `validate_mock_dck_without_io` verifica C e, esclusivamente per discovery, K su un D sintetico con bundle tool, `E###`, identità piano/harness/modello, contratti JSON e preflight conservativo della K; non invoca API/telemetria o pseudocodice. `record_mock_stages` usa **l'esistente** `RQ2MockJournal` in directory temporanea per marcare ricevute D→C→K create-only dopo validazione. Rifiuta D di altro caso/modello, C/K incoerenti, duplicati, K nel test e test prima di freeze mock. Il freeze del journal è `MOCK_ONLY_NOT_RULE_FREEZE`: NON sblocca né sostituisce il freeze scientifico reale.
- `src/tests/test_rq2_mock_pipeline_integration.py`: **16 test sintetici predisposti, NON ancora eseguiti dall'utente**. Verificare prima di segnare un successo.
- `docs/ood/RQ2_KPI_AUDIT_COMPLETATO_E_INTEGRAZIONE_MOCK_2026-11-12.md`: quadro completo dei risultati Colab, limiti I/O e dell'audit, interfacce mock e gap prima di chiamare i provider.

**Prossimo passo PyCharm:** `python -m unittest discover -s src/tests -p "test_rq2_mock_pipeline_integration.py" -v` dopo `git pull --ff-only`, attesi **16 test**. Non avviare Colab/API per questa prova. Questo **non** è il vero runner RQ2; nessuna chiamata Gemini/Claude e nessuna modifica agli esperimenti RQ1.

## 41. Integrazione mock D→C→K superata in PyCharm; duplicazione involontaria della raccolta corretta (12 novembre 2026)

**Log effettivo dall'utente:**
```
Ran 32 tests in 1.150s

OK
```
L'analisi delle 32 voci nominali dell'output conferma **16 test propri** di `RQ2MockPipelineIntegrationTests` tutti `ok` **+ 16 test già esistenti** di `RQ2OutputContractsTests` tutti `ok`. La raccolta automatica `unittest discover -p "test_rq2_mock_pipeline_integration.py"` ha caricato indirettamente la classe `unittest.TestCase` dal test dei contratti, per via di `from test_rq2_output_contracts import RQ2OutputContractsTests` utilizzato soltanto per costruire la fixture K. **Non si tratta di 32 test nuovi di integrazione, né di 16 fallimenti/mancanze.**

**Correzione minimale al solo file di test (commit `0256dc7642f65b881dfe57034c4c3c2d4f3e94da`):** sostituito l'import diretto della classe con `import test_rq2_output_contracts as contract_fixtures`, usando `contract_fixtures.RQ2OutputContractsTests.rule()`. La correzione evita che il discovery raccolga direttamente anche la classe importata. **Attesi 16 test in una futura nuova esecuzione; la variante corretta non è ancora stata rieseguita dall'utente.** RQ1, runner, mock journal e contratti C/K invariati.

**Validato dal log:** il mock integra D→C→K sinteticamente, controlla input/provenienza E###, rifiuta K sui test e errori D/JSON non conformi, fa salvataggi mock create-only e non esegue pseudocodice. **Non è ancora una prova che il runner reale multi-provider o il freeze scientifico funzionino.**

**Passo successivo:** progettare un adapter **source-bound** che usa `rq2_dryrun_plan.preview_market(root)` sui manifest GT-free SHA-verificati e reimpiega `ExperimentConfig` + `run_experiment(..., salva=False)` senza modificarli, producendo artefatti RQ2 isolati e create-only. C e K useranno i prompt del `rq2_probe_adapter` soltanto dopo la D conforme; test bloccato fino al vero freeze delle regole, non il freeze mock. **Da congelare prima di attivare la rete:** ID e parametri modello, budget, policy errori/retry, catalogo operativo e condizione di freeze scientifico. Nessuna chiamata provider autorizzata ora.

## 42. Contratto di passaggio al runner reale (12 novembre 2026)

Creato `docs/ood/RQ2_PONTE_RUNNER_REALE_CONTRATTO_PROPOSTA_V0_2026-11-12.md` (commit `d51d3583980987d9e4f74e1840658014b322f685`), a seguito della verifica effettiva 16+16 test (§41). Il contratto constata le **interfacce reali** `preview_market(root)`, `ExperimentConfig` e `run_experiment(config, llm=None, verbose=True, salva=False)`, e propone il riuso della sola esecuzione D esistente con salvataggio RQ2 isolato, invece di modificare il runner di RQ1. C/K restano chiamate senza tool con prompt già preparati e output strettamente convalidato, K solo in discovery. Obblighi: verifica di source **reale** e metadati del caso, lista di modelli esatti, create-only e crash/restart, errori conservati, gate **scientifico** distinta dal mock freeze, budget autorizzato e scoring GT offline.

La correzione import `src/tests/test_rq2_mock_pipeline_integration.py` (commit `0256dc7642f65b881dfe57034c4c3c2d4f3e94da`) non modifica il runtime e non ha ancora un nuovo log di test; la suite precedente è interamente verde (16 integrazione + 16 contratti). Il documento è **DESIGN**, non codice eseguibile né protocollo frozen. **Prossima modifica tecnica prevista:** adapter sorgente D read-only e preflight delle vere configurazioni, senza API. RQ1 invariata, RQ2 ancora `DRAFT_NOT_EXECUTABLE`.

## 43. Suite integrazione corretta 16/16; primo ponte D source-bound non eseguibile (12 novembre 2026)

**Log reale comunicato dall'utente dopo commit `0256dc7642f65b881dfe57034c4c3c2d4f3e94da`:**
```
Ran 16 tests in 1.152s

OK
```
Confermata la correzione della raccolta `unittest`: **16/16 test dell'integrazione mock D/C/K superati**, non più 32 per via dell'import accidentale del TestCase dei contratti. Non esiste un secondo ciclo di run sperimentali.

**Nuovo codice:** `src/evaluation/rq2_source_bound_d_preflight.py` (commit `5db57fa249722ec1f8aa3033a01da9da2ad8764e`) è un **preflight soltanto di discovery e in sola lettura**. Per una D richiesta: usa direttamente `preview_market(root)` per autenticare il piano candidato da CSV GT-free SHA verificati, valida stage D e proprietà del piano con `_validate_plan`, ri-verifica hash di entrambi i file prima/dopo il parsing, impone identità esatta fra manifest/split/stage per finestra/task/case/cloudbed, e costruisce temporaneamente un `ExperimentConfig` per controllare `A1/A1_8R`, provider/modello proposto e schema `current`. **Non restituisce l'oggetto config né invoca `run_experiment`**; stampa soltanto metadati e SHA256 dell'istruzione, senza contenuto task o telemetria. Tutte le richieste **test** vengono respinte, e anche la discovery resta `can_execute_D=false`, `can_execute_api=false`, `model_version_frozen=false`, `scientific_protocol_frozen=false`, `api_budget_approved=false`. La proposta di ID modello e di `output_contract_mode` è da congelare prima delle API.

**Test preparati ma ancora da eseguire:** `src/tests/test_rq2_source_bound_d_preflight.py`, **16 metodi unittest sintetici** che simulano in modo esplicito solo nei test la verifica delle fonti e usano CSV temporanei sintetici; controllano blocchi su manipolazione sorgenti, ID errati, colonne GT, istruzione e finestre non corrispondenti. Non dichiarare questi nuovi 16 test superati prima del log dell'utente.

**Documentazione:** `docs/ood/RQ2_PREFLIGHT_D_SOURCE_BOUND_2026-11-12.md`, commit `5fd04621e31e9a22cb1268835313b52fa7dc467a`.

**Prossimo comando PyCharm:** `python -m unittest discover -s src/tests -p "test_rq2_source_bound_d_preflight.py" -v` dopo pull, **attesi 16 test**. Nessuna esecuzione Colab o chiamata provider ancora autorizzata. Un futuro runner reale dovrà aggiungere budget, provider/temperature/parametri pin, error states e persistence create-only vera; il mock freeze non sblocca i test reali. RQ1 invariata.

## 44. Preflight source-bound D superato in PyCharm; autorizzata solo progettazione della persistenza (12 novembre 2026)

**Log dell'utente:** `Ran 16 tests in 0.524s — OK` per `src/tests/test_rq2_source_bound_d_preflight.py`. Sono **16/16 test sintetici** della verifica di identità fonte/piano/finestre/configurazione D, senza errori. Questo non costituisce un preflight Colab eseguito con la nuova funzione sul dataset vero, né prova che la D possa essere lanciata: `can_execute_api=false`, `DRAFT_NOT_EXECUTABLE`, ID modello e budget non congelati.

**Passaggio successivo:** storage persistente RQ2 isolato dal percorso `data/results` congelato RQ1, create-only, digest dei payload e delle dipendenze, guardie GT e audit crash/restart; prima soltanto con fixture sintetiche e nessuna invocazione modello. Distinguere ricevute `rq2_mock_journal` da archivi **di output** per future run, senza utilizzare il freeze mock come autorizzazione della fase test. Non dichiarare esito dei nuovi test prima del log PyCharm.

## 45. Persistenza RQ2 create-only degli artefatti discovery predisposta (12 novembre 2026)

A seguito della conferma utente `Ran 16 tests in 0.524s — OK` per il preflight D source-bound (§44), è stato aggiunto un **vero store di file JSON** per gli artefatti, distinto dal mock journal e **in stato non-eseguibile**:

- `src/evaluation/rq2_stage_artifact_store.py` (commit `de58c9404a502f290c3b9bafcc1b005970ce95b9`, fix status non-stringa `801e1bad3aa2e75fc99c8fd9da6573a40c6d7c17`): il costruttore ricontrolla il piano GT-free con `preview_market(root)`, `_validate_plan`, hash attesi dei due CSV originali e mantiene la destinazione RQ2 **fissa** `data/rq2/stage_artifacts_v0`. Il costruttore non scrive. `save_discovery_stage` salva JSON canonico create-only via `os.O_EXCL`, con status `RECORDED_COMPLETE`, `INVALID_OUTPUT`, `PROVIDER_ERROR`, `BLOCKED_DEPENDENCY`, identità stage/harness/modello proposta, hash piano, SHA delle sorgenti, hash dell'artefatto, hash delle dipendenze D→C→K e hash del record. `audit_restart` verifica tutti i record prima di una nuova scrittura, rifiuta file estranei/corrotti/partial write e conserva errori per audit. **Nessuna funzione invoca LLM, tool, scorer o pseudocodice.**
- **Sicurezza del perimetro:** il percorso `data/results` RQ1 resta intatto; ogni **stage test** è bloccato a prescindere dal mock freeze. Lo store non sblocca la fase reale e non autorizza API o retry. La differenza fra digest integrità e firma/autenticità scientifica e l'impossibilità di rilevare leakage semantico in stringhe arbitrarie sono documentate.
- `src/tests/test_rq2_stage_artifact_store.py`: **23 metodi unittest sintetici predisposti ma NON ancora eseguiti**. Prove di write-once, dipendenze, D/C/K, error states, crash/restart, iniezione GT, integrità sorgenti, identità modello, blocco test e limiti di dimensione. Nessun dato reale o API.
- `docs/ood/RQ2_PERSISTENZA_STAGE_CREATE_ONLY_V0_2026-11-12.md` (commit `87dcc4179f5d3a34e7bcb815efe50d858af8505b`): dettaglio tecnico, limiti e test.

**Comando PyCharm:** dopo `git pull --ff-only`, eseguire `python -m unittest discover -s src/tests -p "test_rq2_stage_artifact_store.py" -v`; **attesi 23 test, non ancora confermati**. È **persistenza vera su file** per contenuti caller-supplied, **non** un runner reale dei tre provider: mancano claim, retry, budget API, output mode/ID modello freeze e gate scientifico prima del test. RQ1 congelata invariata.

## 46. Store artefatti RQ2 create-only: 23/23 test superati (12 novembre 2026)

**Output effettivo comunicato dall'utente:** `Ran 23 tests in 1.617s — OK` per `src/tests/test_rq2_stage_artifact_store.py`. La suite sintetica del **nuovo archivio isolato RQ2** è tutta verde: creazione esclusiva di file, controllo digest, identità stage/plan, ripresa e blocco file corrotti/incompleti, propagazione errori D→C→K, blocco fase test, controllo GT solo a livello schema e sorgenti GT-free. Questi 23 test NON eseguono run dell'agente e NON validano API provider o freeze scientifico. Nessuna esecuzione sperimentale RQ2 reale è stata autorizzata.

**Prossimo obiettivo:** collegare questo archivio ai componenti di preparazione D/C/K e al runner storico **in una orchestrazione iniettabile con provider fittizi**, mantenendo un perimetro hard-blocked prima del freeze. Non creare un nuovo motore RCA e non modificare i dati RQ1 congelati. Prima di una campagna API restano da definire modello versione esatta, parametri, protocollo, budget, gestione riavvii e vero congelamento delle regole K.

## 47. Adapter D/C/K offline verso store RQ2 con provenienza ed error states (12 novembre 2026)

Dopo il log dell'utente **`Ran 23 tests in 1.617s — OK`** dello store create-only (§46), aggiunto:
- `src/evaluation/rq2_stage_artifact_store.py`: metodo additivo `load_discovery_stage` (commit `dc2a04e74ae41d18941d06de1255b0061bc5e7b3`), sola lettura e `audit_restart()` obbligatorio; continua a rifiutare test.
- `src/evaluation/rq2_discovery_stage_recorder.py` (commit `dbe229df0eee9e5fca9e0ffd6c3c26b97dffbd1a`): adapter **offline, non provider runner**. Usa il piano verificato, manifest GT-free, identità modello esatta, binding D→C→K e bundle E### per validare i risultati caller-supplied prima di salvarli tramite store. `record_d` persiste run e traiettoria, distinguendo `PROVIDER_ERROR`, `INVALID_OUTPUT` della traiettoria e `RECORDED_COMPLETE` della run. **Un D originale con `json_status=invalid_json` ma traiettoria utilizzabile mantiene `RECORDED_COMPLETE` per la fase di raccolta evidenze e la C può procedere; la validità dell'output task D resta registrata e distinta** (decisione metodologica proposta, da confermare al freeze). `record_c` e `record_k` rifiutano false evidence, mismatch del modello, JSON malformato e K fuori discovery; gli errori non sono riparati, e il fallimento di un genitore produce blocco della fase dipendente. `insufficient_evidence` K valido non è un fallimento API. Nessuna API invocata.
- `src/tests/test_rq2_discovery_stage_recorder.py`: **20 metodi unittest sintetici predisposti, NON ancora eseguiti**. Test di catena completa, errori e astensione, restart, isolamento GT, create-only e bloccaggio test.
- `docs/ood/RQ2_DISCOVERY_RECORDER_INTEGRAZIONE_V0_2026-11-12.md`: spiegazioni, confini epistemici e prossimi passi.

**Comando PyCharm:** `python -m unittest discover -s src/tests -p "test_rq2_discovery_stage_recorder.py" -v` dopo pull, **attesi 20 test**. Prima della campagna provider devono ancora essere fissati e verificati: politica D invalid_json, ID/parametri modello, contratto della D, cost ceiling, claim/retry, versionamento dei prompt ed effettivo freeze del protocollo/candidati K. Il mock freeze NON sblocca il test. RQ1 congelata invariata, RQ2 non eseguibile e non ancora lanciata.

## 48. Recorder RQ2 D/C/K: 20/20 test superati (12 novembre 2026)

**Log effettivo inviato dall'utente:** `Ran 20 tests in 3.351s — OK` per `test_rq2_discovery_stage_recorder.py`. Tutti i **20 test sintetici** dell'adapter D→C→K su `RQ2StageArtifactStore` sono verdi; verificate in ambiente locale catena D/C/K, create-only, errori e blocchi, astensione, integrità del manifest sintetico e audit restart. Queste NON sono run RQ2 sui 15 incidenti OOD; il codice non effettua dispatch provider. RQ1 congelata invariata.

**Passo successivo:** specificare l'identità esatta dei modelli e realizzare stima ex ante dei costi usando tariffe ufficiali correnti, distinguendo una D multi-chiamata dai passaggi logici C/K. Prima di abilitare qualunque API servono ancora modello e parametri congelati, cost ceiling approvato, modalità D, claim/riavvio, protocollo freeze e gestione test indipendente.

## 49. Preflight offline ID modelli e costi per token, senza autorizzazione API (12 novembre 2026)

Dopo **20/20 test del recorder RQ2 superati** (§48), sono stati verificati i modelli ammessi nell'esistente factory RQ1 e i **prezzi ufficiali API del 12 novembre 2026**. Candidati, **NON ancora scientificamente congelati**: Gemini `gemini-3.5-flash-lite` (Google); Sonnet `claude-sonnet-5-5`, Haiku `claude-haiku-5-5` (Anthropic). La factory Anthropic ha `max_retries=0`, `max_tokens=4096` e non passa temperatura/top_p/top_k; Google mantiene le impostazioni predefinite storiche, **non una temperatura esplicitamente congelata**.

**Snapshot prezzi paid standard USD per milione token**, senza free tier/cache/batch: Gemini `$0.30 input/$2.50 output` (output include token di reasoning), Sonnet `$2/$10`, Haiku prompt **per richiesta fino a 100k token** `$0.10/$0.50`, oltre 100k `$0.50/$2.50`. Sorgenti ufficiali: `https://ai.google.dev/gemini-api/docs/pricing`, `https://platform.claude.com/docs/en/about-claude/pricing`, `https://platform.claude.com/docs/en/models/haiku-5-5/overview`.

**Nuovo codice** `src/evaluation/rq2_budget_preflight.py` (commit `fc234701fda28a0ad2c2cbce145cc516deffc2a8`, fix soglia Haiku C/K `cc90d2aa6f135637a2f959d164e873aac388cac1`, arrotondamento Decimal `29bdbe4298affaf7a6fdfa5a2c94a718a3a8a005`): verifica ID compatibili con factory esistente senza istanziare client; offre calcolo matematica di sensibilità token D/C/K. D è multi-chiamata: **150k input di uno stage D non implica una singola richiesta Haiku oltre 100k**; indica fascia tariffaria, non costo effettivo. C/K sono previste singole richieste. Piano 30 D +30 C+8K **per modello**, 204 stage totali. Tutti i report restano `can_execute_api=false`, `api_budget_approved=false`, `approved_spending_limit_usd=null`, `cost_hard_cap_enforced=false`, `real_usage_observed=false`.

**Esempio NON rappresentativo, solo sensitività:** ipotesi D 150k input/4k output per stage, C 8k/600, K 10k/900. Costo matematico ipotetico intera coorte $13.4556–$15.4956, che **NON è un tetto, né una previsione, né un budget approvato**. Actual usage, retry, token di thinking, prezzi, cache e imposte possono modificarlo; il pilot RQ1 Sonnet A0 con 141065 input su 7 chiamate **non definisce una media rappresentativa**.

**Nuovi test** `src/tests/test_rq2_budget_preflight.py`: **16 metodi sintetici preparati, NON ancora eseguiti in PyCharm**. `docs/ood/RQ2_MODELLI_E_BUDGET_PRE_FREEZE_2026-11-12.md` (commit `79be21363ef9d3e7d43bc612ac29be2bc42c3ee6`) documenta premesse, tariffe, limiti e decisioni richieste. **Prossimo test:** `python -m unittest discover -s src/tests -p "test_rq2_budget_preflight.py" -v` dopo pull. Solo dopo suite verde progettare claim/lease, cost ceiling reale e protocollo/esecuzione con autorizzazione esplicita.

## 50. Budget API RQ2 senza tetto economico su indicazione del relatore; suite budget verde (12 novembre 2026)

**Output PyCharm comunicato dall'utente:** `Ran 16 tests in 0.005s — OK` per `test_rq2_budget_preflight.py`: **16/16 test sintetici riusciti**. I calcoli tariffari restano utili come informazioni di reporting, non attestano utilizzo o costi reali.

**Decisione esplicita dell'utente dopo colloquio col professore:** il relatore ha consentito un **budget senza tetto economico predeterminato** per le API Gemini e Claude da utilizzare nella tesi. **Non bloccare né ridimensionare la campagna per un limite USD, né richiedere un massimale di spesa come prerequisito scientifico.** Restano obbligatori per tracciabilità: contatori di token, richieste, modelli, errori, stima/costo osservato e differenze eventuali tra provider. I dati economici sono **KPI secondari, non un gate di autorizzazione economica**.

**Distinguere chiaramente:** l'assenza di *limite di spesa* non costituisce di per sé una richiesta di effettuare SUBITO chiamate a pagamento né rende il piano `DRAFT_NOT_EXECUTABLE` scientificamente congelato. Le API si potranno invocare dopo il completamento del protocollo RQ2, controllo versioni/provider, isolamento discovery→test e implementazione dei claim anti-doppia-esecuzione, senza chiedere un ceiling USD. Priorità alla qualità, riproducibilità, stop in caso di anomalie tecniche, nessun retry automatico non tracciato e preservazione dei risultati RQ1. Le discussioni economiche sui cost ceiling nei paragrafi anteriori sono **superate da questa decisione**.

**Prossimo sviluppo:** claim persistenti create-only **anti-ripetizione involontaria** sullo stesso stage prima della chiamata al provider, senza time-based lease o re-run silenziosi al riavvio Colab. Connettore runner con provider MOCK e protocolli prima dell'inferenza reale.

## 51. Claim anti-ripetizione prima delle future API, senza cost ceiling (12 novembre 2026)

**Implementato**, ma **NON ancora testato su PyCharm**, il modulo `src/evaluation/rq2_discovery_claim_journal.py` (commit `6f4aae01c4427f6d0ac7362ae44e0f491e7bcd3b`, correzione costanti hash `ff84581cdaccce50d369e6bbe08299993b46e91d`). Riusa `RQ2StageArtifactStore` e i manifest GT-free originali con hash congelati. Directory claim separata `data/rq2/stage_claims_v0`; un claim per stage discovery D/C/K, con `os.O_EXCL`, SHA, identità modello e hash dipendenze. Prima di un claim C/K esige il precedente artefatto `RECORDED_COMPLETE` dello stesso modello; rifiuta stage test, duplicati, richieste dopo risultati già registrati, errori a monte e cambi sorgente. `audit_restart()` distingue **claim risolti da artefatti corrispondenti** e **claim senza artefatto**; questi ultimi sono `unresolved_manual_review`, **mai retry o lease temporizzato automatico**. Un claim non autorizza API; non esistono API dispatch in questo modulo.

**Test preparati:** `src/tests/test_rq2_discovery_claim_journal.py`, **20 test unittest sintetici**, non eseguiti. **Documentazione**: `docs/ood/RQ2_CLAIM_ANTI_DUPLICAZIONE_E_BUDGET_NON_VINCOLATO_2026-11-12.md`, commit `37ae08c61b341a107c270531e0688a1392a36561`.

Il professor-assenso riportato dall'utente (§50) elimina **qualsiasi tetto USD come vincolo di avvio**. Costi/token/attempt saranno comunque conservati nei log per rigore sperimentale; claim come prova anti-duplicazione, non controllo economico. Prima delle API resta la necessità di un **freeze scientifico e di un runner controllato**; non è necessaria una soglia monetaria predeterminata.

**Prossimo comando PyCharm:** `python -m unittest discover -s src/tests -p "test_rq2_discovery_claim_journal.py" -v` dopo `git pull --ff-only`, attesi **20 test**. Non considerare questa suite superata prima dell'esito. RQ1 invariata; RQ2 ancora `DRAFT_NOT_EXECUTABLE`.

## 52. Claim discovery create-only: suite 20/20 superata (12 novembre 2026)

**Log reale ricevuto dall'utente:** `Ran 20 tests in 2.310s — OK` per `test_rq2_discovery_claim_journal.py`. Confermata la riuscita dei **20 test sintetici** del registro claim (no API): prenotazione esclusiva, blocco duplicati, persistenza delle incertezze dopo crash, riconciliazione con record successivo, dipendenze D/C/K, mismatch modelli, corruzione, sorgenti GT-free e blocco test. **Non sono state effettuate chiamate Gemini/Claude né run sui 15 incidenti RQ2.**

La decisione del relatore riportata dall'utente in §50 rimane **budget economico non vincolante**, con rendicontazione token/costi solo per riproducibilità; i claim proteggono il protocollo, **non impongono un cap di spesa**. I claim non autorizzano il dispatch. **Prossima integrazione:** dry-run orchestrato che connetta claim, D/C/K e store con backend finto rigorosamente senza rete; parallela verifica dello stato di preregistrazione e del contratto D rispetto a RQ1. Un mock freeze NON è un freeze scientifico, e il test OOD resta chiuso.

## 53. Rehearsal end-to-end claim→D/C/K→restart predisposto, senza creare nuovo RCA runner (12 novembre 2026)

Dopo il log utente `Ran 20 tests in 2.310s — OK` del claim journal (§52), aggiunto `src/tests/test_rq2_claim_recorder_end_to_end.py` (commit `639c6b9a544885ed76a6bb401b4f904b8a34854b`): **16 test sintetici preparati, NON ancora eseguiti**. Riusa il vero `RQ2DiscoveryClaimJournal`, `RQ2DiscoveryStageRecorder` e `RQ2StageArtifactStore`, ma usa fixture e SHA/verifica del piano finti **solo dentro i test**. Copre la sequenza di 3 claim e 3 risultati, audit restart, dipendenze, errore D/C e blocchi successivi, JSON invalido senza repair, D original invalid_json con evidenze utilizzabili, K `insufficient_evidence`, duplicati, claim orfani dopo disconnessione, tampering e blocco test, senza provider, telemetria reale o GT. Questa suite **non dimostra disponibilità API** e non autorizza pilot.
 
Documentazione: `docs/ood/RQ2_REHEARSAL_CLAIM_RECORDER_E_DECISIONI_PRE_FREEZE_2026-11-12.md` (commit `89b9415205ddefd67dcd3876bdbed1e4e71ed7d4`): matrice delle decisioni e dei gate prima del freeze. **Addendum** a `docs/ood/PROTOCOLLO_RQ2_BOZZA_V0_2026-11-11.md` (commit `4f3724f4ca21b2a296a904f4784c317caaf75cf2`) per aggiornare esplicitamente le richieste economiche storiche: budget **senza tetto USD** su indicazione del relatore riferita dall'utente; usage/costo sempre registrati come indicatori di reporting, non limiti di spesa. Nessuna modifica al motore RQ1.

**Prossima verifica PyCharm:** `python -m unittest discover -s src/tests -p "test_rq2_claim_recorder_end_to_end.py" -v` dopo pull, **attesi 16 test**. Dopo il verde, proseguire verso pre-freeze di output mode D e hash C/K e poi integrazione fake provider, evitando scaffolding non necessario. Il test RQ2 e le API restano chiusi finché protocollo e autorizzazione tecnica sono pronti.

## 54. Prova end-to-end 16/16 verde; coordinatore fake-only discovery predisposto (12 novembre 2026)

**Log PyCharm dell'utente:** `Ran 16 tests in 9.059s — OK` per `test_rq2_claim_recorder_end_to_end.py`. Verificato l'intero flusso sintetico claim→D/C/K→persistenza→riavvio con tutte le guardie anti-duplicazione. Non è stato ancora usato un vero provider né eseguita la coorte RQ2.

**Implementato passo successivo, ANCORA NON TESTATO:** `src/evaluation/rq2_fake_discovery_driver.py` (commit `0558d920e83f5e73ce71f64826d10b9f0c209b32`). Classe `RQ2FakeDiscoveryDriver` che gestisce autonomamente l'ordine D/C/K con le esistenti classi `RQ2DiscoveryClaimJournal` e `RQ2DiscoveryStageRecorder`, usando esclusivamente `DeterministicFakeBackend` con risposta pre-caricata in memoria. Il backend non può chiamare provider, strumenti né `run_experiment`; il runner richiede un file marcatore `.rq2_synthetic_fixture_only` e rifiuta una root contenente `Market.zip`. Le due sorgenti GT-free fittizie e il piano sono monkeypatchati **solo nei test**; fuori dai test `preview_market` continua a richiedere SHA originali. Output fake non scientifici e non utilizzabili per inference. Un claim senza artefatto resta manual review; D/C falliti bloccano la fase successiva senza provider claim.

**16 nuovi metodi sintetici (non ancora eseguiti)** in `src/tests/test_rq2_fake_discovery_driver.py` (commit `396317cf05a505993f22b3234cf46a917e5847bb`); documentati in `docs/ood/RQ2_FAKE_DISCOVERY_COORDINATOR_REHEARSAL_2026-11-12.md` (commit `c0df57f8b82089437b46a6287b144eb536a7ba20`). Controllano il primo **vero coordinamento fake** stage-per-stage, recupero e errori, oltre al blocco dei provider reali.

**Prossima verifica:** `python -m unittest discover -s src/tests -p "test_rq2_fake_discovery_driver.py" -v` dopo pull, attesi **16**, esito non ancora confermato.

**Decisioni prima di API:** mantieni i 204 stage logici (90 D + 90 C + 24 K) e 3 modelli/2 harness, budget senza tetto USD, costi/token annotati; congelare modalità D, ID/parametri C/K, hash prompt, protocollo e criterio freeze pseudoregole. Test e RQ1 rimangono sigillati. Il fake driver **non esercita ancora il grafo reale**, ma riduce il rischio nel codice di orchestrazione. Non confondere i suoi record con risultati scientifici.

## 55. Coordinatore fake-only discovery: 16/16 test superati (12 novembre 2026)

**Log effettivo comunicato dall'utente:** `Ran 16 tests in 8.230s — OK` per `src/tests/test_rq2_fake_discovery_driver.py`. Tutti e **16 i test sintetici** del coordinatore `RQ2FakeDiscoveryDriver` sono verdi. La prova include prenotazione prima della risposta finta, sequenza D→C→K, errori D/C e blocchi successivi, rifiuto di duplicati dopo riavvio, claim senza risposta dopo crash, astensione valida e isolamento da `Market.zip` / client provider. **Non sono run reali, nessuna API Gemini/Claude, nessuna lettura di telemetria OOD e nessuna modifica RQ1.**

**Passo successivo:** eseguire preflight **source-only** delle identità precise dei modelli, modalità e parità del contratto D rispetto alla campagna RQ1, hash dei prompt C/K, moduli di runtime e scorer. Prima di scegliere `legacy` o `v2_enforce` sulla sola memoria, rintracciare l'opzione effettivamente usata nelle run RQ1 cross-model congelate; se i manifest disponibili non lo attestano, segnare `RQ1_OUTPUT_CONTRACT_PARITY_UNVERIFIED`, senza inferire o sostituire con un valore ipotetico. Questa verifica non deve toccare le 11 query test né sbloccare provider.

**Budget:** l'indicazione del relatore riferita dall'utente (nessun cap USD) resta valida e non è un ostacolo alla preparazione di run, ma non sostituisce il freeze metodologico né autorizza retry involontari. Tracciare token e costi solo come evidenza.

## 56. Parità D con RQ1 risolta su 13 blob frozen; prompt C/K SHA pre-freeze (12 novembre 2026)

Dopo l'esito **16/16, 8.230s, OK** del coordinatore fake (§55), esaminate sul branch RQ2 le fonti storiche RQ1 al commit congelato `e4845e7fe9a399e10dd2db6f320dfeaeeddf3379`. **13 file** (preregister/campaign/runner/config/factory/agent prompts/graph/tool factory/tools/v2 task contract/evidence builder/signal catalog/rule container CPU) hanno **esattamente lo stesso Git blob SHA-1** nel commit RQ1 e nel branch corrente. Un confronto di questi 13 file non garantisce l'intera dipendenza e non equivale a test runtime.

**Decisione D basata su sorgente verificato:** `src/evaluation/evaluation20_preregister.py` costruisce il piano RQ1 Evaluation20 con `"output_contract_mode": "v2_enforce"`, `"variant_scheme": "current"`, `"max_tool_rounds": 6`, `"recursion_limit": 30`; `evaluation20_campaign.py` passa il mode dal piano a `ExperimentConfig` e ne verifica la parità nel record. **RQ2 D dovrà usare `v2_enforce` per comparabilità con RQ1**, non il default `legacy` dell'oggetto. Rimane da congelare formalmente nel nuovo protocollo; nessuna API autorizzata ora.

**Nuovo modulo di provenienza** `src/evaluation/rq2_protocol_identity_preflight.py` (commit iniziale `1130063f7edc53fdc6415f19aa5d5b7774e4dc79`, correzione compatibilità checkout Windows CRLF `4ccd4d1cb814572455da14dc63832dac4713b7c2`): ri-controlla i Git blob SHA1 di 13 sorgenti RQ1, registra hash SHA256 dei file RQ1 e di 7 file di input/validazione/store RQ2, calcola SHA256 di `CAUSE_SYSTEM` e `RULE_SYSTEM` importati da `rq2_probe_adapter`, verifica gli ID modelli e max_token Anthropic rispetto a factory e produce un **JSON senza case ID, GT, telemetry, LLM o scritture**, sempre `SOURCE_PROVENANCE_CAPTURE_NOT_SCIENTIFIC_FREEZE`, `rq2_discovery_api_enabled=false`, `rq2_test_unlocked=false`.

**Nuova suite** `src/tests/test_rq2_protocol_identity_preflight.py`, **14 test preparati e NON ancora eseguiti dall'utente**, commit `ff131aa4d32eba7007d5f24d15b50fdf31e62423`. Documento `docs/ood/RQ2_PARITA_RQ1_E_IMPRONTE_PROMPT_CK_PRE_FREEZE_2026-11-12.md` commit `37a299c32c54499c4d7c77e5d8ca02593111ea0f`. **Prossima verifica in PyCharm:**
```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_protocol_identity_preflight.py" -v
python -m evaluation.rq2_protocol_identity_preflight
```
**Attesi 14 test, poi JSON con hash C/K da acquisire.** Lo snapshot non è ancora un freeze scientifico, e non attesta runtime delle vere API. Prima dei provider: pin esplicito mode D/config, hash prompt C/K, versione/parametri provider, verfica fake `run_experiment` storico e protocollo 4+11.

## 57. Preflight sorgenti RQ1 e SHA dei prompt C/K: 14/14 test ed esecuzione CLI confermati (12 novembre 2026)

**Output dell'utente su PyCharm:**
```
Ran 14 tests in 0.348s

OK
```
Eseguito inoltre `python -m evaluation.rq2_protocol_identity_preflight`, JSON `version=rq2_protocol_identity_preflight_v0`, `status=SOURCE_PROVENANCE_CAPTURE_NOT_SCIENTIFIC_FREEZE`, `rq1_reference_commit=e4845e7fe9a399e10dd2db6f320dfeaeeddf3379`, `rq1_source_blob_sha1_match=true`. **13/13 sorgenti RQ1** in elenco corrispondono ai Git blob congelati. `rq1_D_output_contract_mode_verified=v2_enforce`; proposta identica RQ2 D, `D_variant_scheme=current`, `D_max_tool_rounds=6`, `D_recursion_limit=30`, harness `A1,A1_8R`.

**Cattura SHA-256 reale dall'output CLI (pre-freeze, non nuovo protocollo immutabile):**
- Prompt C `CAUSE_SYSTEM`: `81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42`.
- Prompt K `RULE_SYSTEM`: `0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71`.
- `evaluation/rq2_probe_adapter.py` SHA256 `60de1f73af15609a4328532dacd54b20b42701836bd6d6c4b60128ef9e6a4e53`.
- `evaluation/rq2_output_contracts.py` `6c4d838bc86daf118b896462a3ee9a88f2952100126d58a0173a816b02fd4c0b`.
- `evaluation/rq2_evidence_bundle.py` `c51fc5cb4455e46037352b52fb3fa0ec83ea275a91219269b683755ffa360e79`.
- `evaluation/rq2_stage_binding.py` `8a353d8ffb30eafe8a3db3334a361224a2e38dd405750cfe30cc42357cdee97c`.
- `evaluation/rq2_discovery_stage_recorder.py` `39986f1e74442f65046f1812abdc8a5fd16dd2cfb57326dfca80ccc6203b2873`.
- `evaluation/rq2_discovery_claim_journal.py` `378c5f871dc1395f706c650be4227a795bc7f9548e6ed91e6c85e64a938b7ec1`.
- `evaluation/rq2_stage_artifact_store.py` `1badfae0038622e186a6e8a5dd739f9c67af841cc2e6309dc18af45cb671f7cd`.
- La suite controlla **sorgenti RQ1 nel clone reale locale**, non il dataset; `read_market=false`, `read_ground_truth=false`, `read_model_predictions=false`, `provider_issued_requests=0`, `files_written=false`.
- Modelli proposti `gemini-3.5-flash-lite`, `claude-sonnet-5-5`, `claude-haiku-5-5`; max output Anthropic 4096, sampler non esplicitamente pinned nella factory storica.

**Caveat vincolanti:** il report conferma `rq2_scientific_protocol_frozen=false`, `rq2_discovery_api_enabled=false`, `rq2_test_unlocked=false`. Si sono **acquisite** le impronte dei prompt ma non si è ancora verificata/fissata la configurazione runtime tool-free per C/K né l'identità di tutte le dipendenze; gli SHA delle sole stringhe di sistema non coprono i prompt dinamici per caso. Il protocollo deve definire e immutabilmente vincolare i parametri prima delle API, senza accesso ai casi test.

**Prossimo passo:** esercitare `run_experiment(config,llm=fake,salva=False)` nel vero LangGraph con caso e tool **sintetici e confinati**, e poi provare la chiamata tool-free C/K con provider fake. Non modificare runner RQ1, non chiamare API/Market, non introdurre cost ceiling.

## 58. Regressione del vero runner LangGraph con LLM e tool sintetici predisposta (12 novembre 2026)

Dopo la verifica reale del preflight sorgenti RQ1 (§57), aggiunto `src/tests/test_rq2_real_langgraph_fake_llm.py` (commit `34ac28786026a754f7b8cae72bb5b2ce46c1d1fd`) con **13 test sintetici ancora NON eseguiti dall'utente**.

**Novità rispetto ai test precedenti:** la suite chiama effettivamente `evaluation.experiment_runner.run_experiment(config, llm=FakeLangGraphLLM, verbose=False, salva=False)`, che a sua volta usa l'originale `agent.graph_engine.crea_grafo_rca`, `ToolNode` LangGraph, `esegui_grafo_rca` e `output.v2_task_contract` di RQ1. Sono *reali* le funzioni del grafo, il routing dei tool, l'audit V2 e il conteggio token; sono **finti** tutti gli output, l'LLM, il tool `synthetic_probe`, il caso `cloudbed-1_q999` (non nel benchmark) e il report evidence. Solo `prepara_esperimento` è patchato per disabilitare QUALSIASI lettura di manifest/Market. Factory provider patchata per fallire se chiamata. `salva=False` e data_dir temporanea.

**13 verifiche proposte:** A1/A1_8R con `ToolNode`, prompt con task-aware V2, predizione JSON, tool-call/result, uso token osservato, 6 round→1 finalizzazione, rifiuto chiamata tool oltre limite, risposta finale vuota, JSON non valido, missing usage, modalità provider Google senza client e assenza di scritture. La suite **non prova** la preparazione reale delle metriche o la correttezza delle future API su caso discovery.

Documentazione `docs/ood/RQ2_LANGGRAPH_ORIGINALE_FAKE_LLM_V0_2026-11-12.md` (commit `f2758af5bb3d8b98d70d33cc358c11b5485514b2`). **Prossimo comando PyCharm:** `python -m unittest discover -s src/tests -p "test_rq2_real_langgraph_fake_llm.py" -v` dopo pull, **attesi 13**. Dopo il verde, implementare e testare adapter tool-free per C/K, pin del protocollo/parametri e freeze scientifico, poi primo pilot reale discovery autorizzato. `D.output_contract_mode=v2_enforce` deriva dal freeze originale RQ1. Budget illimitato per decisione relatore riferita dall'utente, ma nessun dispatch/API prima dei gate. RQ1 invariata, test RQ2 chiusi.

## 59. Vero motore RQ1 `run_experiment` + LangGraph + ToolNode fake: 13/13 test superati (12 novembre 2026)

**Log reale inviato dall'utente:** `Ran 13 tests in 0.940s — OK` per `src/tests/test_rq2_real_langgraph_fake_llm.py`. **13/13** test della regressione contro il **vero** runner/graph engine RQ1 con `llm=FakeLangGraphLLM` e `synthetic_probe` in memoria sono riusciti. Passano A1/A1_8R, output `v2_enforce`, prompt task-aware, chiamate al `ToolNode` reale, limite 6 round e finalizzazione, token usage e output/errori; l'originale `prepara_esperimento` è patchato apposta per impedire l'accesso a Market/manifest. **Nessuna API, nessuna run reale e nessuna lettura dei casi RQ2**. Questo test non certifica il preprocessing reale A1/A1_8R e non è un pilot scientifico.

**Prossimo lavoro:** verificare l'ultimo tratto C/K tool-free usando `rq2_stage_binding` e `rq2_probe_adapter`, record e claim già testati, con trasporto LLM **finto/iniettato e senza rete**. Controllare i formati LangChain di output (contenuto text block Anthropic/Gemini, usage e errori) senza alterare RQ1 o introdurre API implicite. D RQ2 eredita `output_contract_mode=v2_enforce` da RQ1. Prompt C/K SHA acquisiti (§57) ma non ancora scientificamente congelati. Budget non vincolante, test OOD ancora bloccati.

## 60. Tool-free C/K con messaggi LangChain e fake controllato, 17 test ancora da eseguire (12 novembre 2026)

Dopo la conferma **`Ran 13 tests in 0.940s — OK`** del test del vero runner RQ1/ToolNode su fake (§59), aggiunto il modulo `src/evaluation/rq2_toolfree_fake_transport.py` (commit `7d8df8e5268081828efb5c89823782622e4f5146`, hardening piano/harness `710264b4c88739da8702c324d242e5fa9c5e40a8`). **NON è un runner reale, NON istanzia provider**. Riceve esclusivamente una `StrictToolFreeFake` (una sola `AIMessage` o `SimulatedProviderFailure` in memoria), materializza la coppia originale `SystemMessage/HumanMessage` da `prepare_bound_c/k` e verifica digest canonici di `binding_sha256/package_sha256`, stage discovery, ID logico/harness e snapshot SHA-256 già acquisiti dei prompt `CAUSE_SYSTEM=81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42` e `RULE_SYSTEM=0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71`. Un solo fake `invoke` per C o K, **nessun bind_tools**; rifiuta richieste di tool, conserva testo grezzo solo dai blocchi `type=text`, distingue risposta vuota, eccezione fake e JSON non conforme (JSON validato successivamente dal recorder). Contatori `usage_metadata` riportati solo come **synthetic_not_billed**, missing usage = null senza zeri inventati. `model_api_calls=0`, `can_execute_api=false`, `can_execute_test=false` sempre.

**Nuova suite predisposta:** `src/tests/test_rq2_toolfree_fake_transport.py`, **17 metodi unittest NON ANCORA ESEGUITI** (commit `3f889f82b192ba3f2987217571624ee5ae114fe6`). Copre messaggi LangChain, estrazione blocchi Anthropic escludendo thinking, error/timeout fake, output invalido/empty, divieto tool, SHA, token fake, blocco test, strict backend, duplicati, e prova D persistita→claim C→C fake→claim K→K fake→audit dello store RQ2. L'ultima prova riutilizza fixture sintetiche e sorgenti patchate unicamente dentro il test. Documentazione `docs/ood/RQ2_CK_TOOLFREE_FAKE_TRANSPORT_2026-11-12.md` commit `ef857bf2937e5af583edee944f51e9ba845f7c71`.

**Comando PyCharm dopo pull:** `python -m unittest discover -s src/tests -p "test_rq2_toolfree_fake_transport.py" -v`; attesi **17 test**, nessun esito ancora confermato. **Caveat importante:** la registrazione dei conteggi di token C/K effettivi in un artefatto persistente, la gestione delle vere API tool-free e il congelamento scientifico 4+11/KPI/parametri **NON** sono ancora implementati. Il fake transport non abilita la rete e l'integrità interna di un binding non è prova che il GT-free manifest sia stato verificato. RQ1 invariata, RQ2 resta `DRAFT_NOT_EXECUTABLE`, budget senza tetto economico per decisione riferita del professore, test OOD chiusi.

## 61. Trasporto C/K tool-free fake: suite 17/17 superata; chiarimento fase sperimentale (12 novembre 2026)

**Log effettivo comunicato dall'utente:** `Ran 17 tests in 1.691s — OK` per `src/tests/test_rq2_toolfree_fake_transport.py`. I **17/17 test** sono verdi: binding C/K, vere classi di messaggio LangChain ma **LLM esclusivamente fake**, estrazione testo e usage sintetico, errori, divieto tool, stage test bloccati e integrazione col vero journal/store su fixture temporanee. **Nessuna chiamata API Gemini/Claude è stata eseguita in RQ2, nessuna inferenza su casi reali OOD**.

L'utente ha chiesto conferma che le verifiche fossero fake: **sì**. Distinguere sempre: le funzioni originali `run_experiment`/LangGraph e gli adapter RQ2 sono codice realmente implementato e testato, mentre LLM/risposte/tool/telemetria dei test sono sintetici, e le sorgenti del benchmark non vengono aperte da queste suite. La verifica degli SHA e della parità del codice RQ1 è invece una verifica reale del repository, non del benchmark. I risultati delle suite non costituiscono punteggi di RCA né test di generalizzazione.

**Passo successivo:** costruire adapter C/K per provider reali con parametri versionati, usage e provider errors persistenti, e congelare il protocollo in modo scientifico prima di qualsiasi API RQ2. Poi pilot su una delle sole quattro discovery; 11 casi test restano isolati fino al freeze delle regole. Budget senza tetto USD secondo indicazione del relatore riferita dall'utente. Non modificare RQ1 congelata.

## 62. Adapter C/K provider effettivi implementato ma API bloccate, usage persistente (12 novembre 2026)

Dopo i **17/17 test C/K fake superati** (§61), implementato un ingresso reale per C/K che riusa la factory RQ1 senza cambiare RQ1. Nuovo modulo `src/evaluation/rq2_ck_provider_transport.py` (commit iniziale `bf7c73fc418657f4af15313c041d013fd623eef1`, rafforzamento gate `7ea59853f66c928559ed7499309b545573650934`). `run_one_claimed_ck` impone `confirm_paid_api=True` **e** un release scientifico immutabile con hash pin (nel modulo corrente **`RELEASE_SHA256=None`**, perciò l'invocazione LIVE è impossibile). Il release dovrà verificare schema, 4 discovery/11 test, tre ID modelli, 2 harness, mode D `v2_enforce`, 6 round/recursion 30, SHA verificati dei prompt C/K, tool C/K vietati, no retry e zero tetto economico. Il test OOD resta bloccato. L'import del modulo non istanzia client e non consuma API.

Quando sarà scientificamente autorizzato, il futuro percorso `run_one_claimed_ck` userà `RQ2DiscoveryStageRecorder` e `RQ2DiscoveryClaimJournal` per rileggere fonti GT-free e record D/C source-bound, verificare la modalità D e i bundle delle evidenze, **creare il claim create-only prima** di istanziare il client con `agent.model_factory.crea_modello`, chiamare `invoke([SystemMessage,HumanMessage])` una sola volta senza tool/retry, e salvare nello store RQ2 output, errori e token (`usage_metadata`, incluso dettaglio numerico thinking se presente). Le eccezioni sono ridotte a classe/codice HTTP per evitare la conservazione di credenziali nel testo. Claim senza file finale dopo un crash resta manual review e non si ritenta autonomamente.

Modifica **additiva** a `src/evaluation/rq2_discovery_stage_recorder.py` (commit `3d73acc7d1e2e6685d5e2d47c2ab93a5ad1670ba`): parametri facoltativi `transport_receipt` su `record_c/record_k`; validazione di stage ID, modello, provider, binding SHA, hash testo risposta, error, numero tentativi e contatori token coerenti; il campo viene persistito nello **stesso file create-only** della risposta. Vecchie prove con `transport_receipt=None` conservano il formato precedente. Questa è persistenza di osservazioni tecniche, non prova della qualità RCA, né una misura di costo esatto provider.

**15 NUOVI test, NON ancora eseguiti in PyCharm:** `src/tests/test_rq2_ck_provider_transport.py` (commit `7e09ec3754d5ac07b9a6cd35f990122044e22043`, adattato gate `2ee3459ebadb105fdfc481792441ffaece08d818`). I test **simulano soltanto** un release con hash monkeypatchato e sostituiscono `crea_modello` con un modello in memoria; non hanno accesso alla rete e non chiamano provider. Testano source-bound claim→C→K con usage persistito, rifiuto di duplicati/stage test, gate freeze, v2 mode, errore provider senza testo sensibile, output non valido e divieto tool. Documento `docs/ood/RQ2_CK_PROVIDER_REALE_PRE_FREEZE_GATED_2026-11-12.md` (commit `46ac1cc053a55a5139c9aace67cc90d1a03cfd47`).

**Prossimo test:** `python -m unittest discover -s src/tests -p "test_rq2_ck_provider_transport.py" -v`, **attesi 15**. Solo dopo suite verde: congelare scientificamente il protocollo, predisporre il driver D sul runner storico con claim, quindi una prima API pilot esplicitamente autorizzata su una delle 4 discovery. Budget economico non vincolante per decisione del relatore riferita dall'utente, ma ogni spesa/token va documentata; 11 test isolati fino a freeze K. RQ1 invariata.

## 63. Correzione unittest nel test di trasporto C/K; 20/20 recorder ancora verdi (12 novembre 2026)

**Log reale dell'utente:**
- `python -m unittest discover -s src/tests -p "test_rq2_ck_provider_transport.py" -v` si è interrotto **prima di eseguire test**, con `TypeError: RQ2ActualCKProviderAdapterOfflineTests.run() missing 1 required positional argument: 'model'`.
- `python -m unittest discover -s src/tests -p "test_rq2_discovery_stage_recorder.py" -v` → **`Ran 20 tests in 2.793s — OK`**. La retrocompatibilità della modifica additiva al recorder è confermata sui test sintetici esistenti.

**Causa esatta:** il nuovo `src/tests/test_rq2_ck_provider_transport.py` aveva una funzione di supporto chiamata `def run(self, stage, model)`, che sovrascrive involontariamente il metodo standard `unittest.TestCase.run(result)`. Il runner di test la chiamava senza gli argomenti richiesti; questo NON è un errore dell'adapter provider, né una prova che la suite provider abbia fallito nei singoli casi. **Nessuna chiamata API reale**.

**Correzione soltanto nel test:** rinominato `run` → `invoke_mocked_ck_stage` e aggiornate **9 chiamate `self.run(...)`**. Commit `c919464941ab3eaa830cb46f128a0819a0bb314c`. Il numero di metodi `test_*` resta **15**; i sorgenti di produzione RQ1 e RQ2 NON sono stati toccati per correggere questo errore.

**Prossimo comando PyCharm:**
```powershell
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_ck_provider_transport.py" -v
```
**Attesi 15 test, esito NON ancora confermato.** Se la suite manifesta errori ulteriori, analizzarli dai singoli traceback prima di qualunque altro refactoring. `RELEASE_SHA256=None` resta il blocco di produzione delle API; nel test si usa solo release temporanea con hash patchato e SDK fake. Budget senza massimale USD, test OOD bloccati fino a freeze scientifico.

## 64. Adapter reale C/K con SDK mock: 15/15 test verdi (12 novembre 2026)

**Log PyCharm dell'utente:** `Ran 15 tests in 5.476s — OK` per `src/tests/test_rq2_ck_provider_transport.py`, dopo la correzione del nome `TestCase.run()` registrata nel §63. Sono quindi **15/15 test della nuova interfaccia C/K superati**: release mock temporaneo e hash monkeypatchati SOLO nei test, factory `crea_modello` sostituita con SDK in memoria, un'unica chiamata, claim prima del modello, registra usage e stato error/JSON nei record create-only, blocca doppie chiamate e test. Nessuna inferenza RQ2 reale, nessun provider remoto coinvolto; nella produzione `RELEASE_SHA256=None` mantiene le API bloccate.

**Prossima attività prioritaria:** completare il punto D con il vero `run_experiment(config,salva=False)` sullo schema RQ2 discovery, claim prima della chiamata, identità source-bound, parità `v2_enforce` RQ1, file di risultato create-only e un pilot senza tetto finanziario (dopo freeze scientifico). Non modificare `experiment_runner.py` o `model_factory.py` RQ1. Evitare proliferazione di mock e refactoring; l'obiettivo è chiudere le barriere tecniche necessarie al primo pilot reale, con gli 11 test ancora isolati.
