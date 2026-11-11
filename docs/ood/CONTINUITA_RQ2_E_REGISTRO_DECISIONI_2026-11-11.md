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
