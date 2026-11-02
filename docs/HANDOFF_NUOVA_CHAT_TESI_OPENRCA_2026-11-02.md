# Handoff per nuova chat — Tesi magistrale OpenRCA (stato al 2 novembre 2026)

> **Documento di continuità.** Usare questa pagina come punto di partenza in una nuova conversazione. NON è un nuovo protocollo sperimentale e non modifica risultati, etichette, modello o codice congelato. Se il contenuto differisce dai file immutabili o dai commit, questi ultimi sono la fonte di verità.

## 1. Obiettivo scientifico e modo di lavorare

La tesi magistrale in Ingegneria Informatica studia **Harness Engineering per la Root Cause Analysis (RCA) di microservizi con LLM**, basandosi su **Microsoft OpenRCA 1.0, dataset Market** e ispirandosi, quando giustificato dai dati, ai principi di PAVE / OpenRCA 2.0.

La domanda centrale è quali componenti deterministiche dell'harness migliorino (o peggiorino) correttezza diagnostica, costo, latenza e validità del formato, a parità delle altre condizioni. Non presupporre che una variante più complessa sia migliore: riportare anche risultati nulli o negativi.

- Lingua di collaborazione: **italiano**, spiegazioni tecniche progressive e comandi eseguibili.
- **PyCharm su Windows** per sviluppo, revisione e suite di test; **GitHub** per codice/versioni; **Google Colab** per esecuzioni con Gemini e ispezione dei file; **Google Drive** per benchmark, notebook, protocollo, output e scoring.
- Evitare modifiche distruttive, override di output, retry automatici e chiamate API senza autorizzazione esplicita dell'utente.
- I casi e le finestre dei vecchi piloti e delle coorti già valutate sono dati di sviluppo *visti*: non trattarli come nuovi incidenti indipendenti.
- Preservare evaluation, mixed_quarantine e OOD holdout da consultazione delle etichette o tuning fino a protocollo finale preregistrato.

## 2. Repository e versioni importanti

- Repo: https://github.com/alessio1996A/Tesi_Laurea_Magistrale_OpenRCA
- Branch per il professore/relatore: `presentation/relatore-2026-11-02`.
- Branch dello sviluppo ST sperimentale: `feature/a1-verify-st-v1`.
- **Commit del primo confronto storico** A1-R8 vs A1_VERIFY: `6927fcfa18fc29fce64ad65eac98231b2ba42184`.
- **Commit congelato del confronto A1_VERIFY vs A1_VERIFY_ST**: `138fb523efec4a665a2424ab2faedb698f10562e`.
- Il branch del relatore è stato aggiornato *fast-forward*, senza force, dal suo head storico `91f91ad1199f5e4bb7f80c15b97aa727bfbea5ed` al codice ST congelato, e poi aggiornato solo documentalmente. **Non sostituire mai il commit sperimentale esatto con l'HEAD più recente del branch**, perché ora la documentazione ha ulteriori commit.
- Controllo referenziale: `git status --short`, `git fetch origin`, `git switch presentation/relatore-2026-11-02`, `git pull --ff-only origin presentation/relatore-2026-11-02`. Se modifiche locali, non forzare.

## 3. Architetture realizzate

1. **A0**: baseline LLM con 5 tool per metriche service, container, node, log e trace; esplorazione autonoma, nessuna evidenza rule-based preparata.
2. **A1_V2**: A0 con evidence engineering/preprocessing, selezione, sintesi e report deterministico, ma **senza otto regole**.
3. **A1 / A1-R8**: A1_V2 **più 8 detector deterministici** R01, R02, R06, R07, R08, R09, R10, R11. Fino a 6 round esplorativi liberi.
4. **A1_VERIFY**: A1-R8 più planner deterministico di copertura dei candidati; al massimo **4 round esplorativi LLM + 2 verifiche mirate** e una finalizzazione LLM. Le verifiche sono letture di telemetria, **non prove causali**. I controlli 0/1/2 dipendono dalla copertura delle chiamate precedenti; i round inutilizzati NON tornano all'esplorazione.
5. **A1_VERIFY_ST**: stesse regole, modello, planner, budget 4+2, tool, output contract e prompt di base di A1_VERIFY; **solo nella finalizzazione** aggiunge il campo `STRUCTURAL_CONTEXT_JSON` derivato deterministicamente dai segnali strutturali/temporali.

**Distinguere i cinque tool dalle otto regole**. I tool recuperano telemetria, le regole cercano anomalie e candidati.

Regole implementate:
- R01 container CPU load; R02 container memory load; R06 container read I/O load;
- R07 node CPU load; R08 node memory consumption; R09 node disk read I/O consumption;
- R10 node disk write I/O consumption; R11 node disk space consumption.

**Regole assenti da verificare per un futuro R11:** R03 container network packet retransmission; R04 container network packet corruption; R05 container network latency.
Altre classi del benchmark (node CPU spike, container write I/O load, container process termination, container packet loss) sono considerate **OOD riservate** e non vanno inserite surrettiziamente nello sviluppo.

Le categorie di guasto del benchmark / `record.csv` hanno informato la scelta delle regole; ciò non equivale a etichette ground truth in input al singolo agente. Le regole correnti leggono la **telemetria**, non le risposte dei casi valutati. I test sintetici offline (238 test superati nell'ambiente PyCharm all'epoca) controllano proprietà software, **non** accuratezza indipendente delle 8 regole reali.

## 4. Cosa è e cosa NON è il contesto PAVE-inspired

Codice: `src/harness/structural_temporal_verifier.py`, inserito in `src/agent/verify_graph.py` come contesto aggiuntivo nella finalizzazione ST.

- Da identificativi `node-N.servizio-replica` ricava una associazione **lessicale** nodo ↔ container; non dimostra che questa sia una topologia applicativa certificata.
- Compara segnali di stessa famiglia: R01↔R07 CPU; R02↔R08 memoria; R06↔R09 read I/O.
- Descrive compatibilità temporale dei primi segnali e casi di relazione assente/ambigua/non valutabile.
- I campi `causa_verificata=False`, `propagazione_verificata=False` restano corretti.
- **NON** esiste ancora un grafo service→service da trace parent/child integrato con relazioni RPC; **NON** esiste una verifica passo per passo di percorso causa→sintomo; **NON** abbiamo dimostrazioni controfattuali tramite fault injection. Non chiamarlo "PAVE completo" o "causal verification confermata".
- La vecchia demo PAVE con **dati sintetici** `src/evaluation/demo_verifica_pave_offline.py` è stata volutamente **eliminata** dal branch del professore. Non ricrearla come artefatto di presentazione.

## 5. Primo confronto storico (coorte development separata)

**A1-R8 vs A1_VERIFY** su 8 casi appaiati già congelati e valutati in precedenza:
- Score medio ufficiale: A1-R8 **0,3850**, A1_VERIFY **0,3225**.
- Score 1: **2/8** vs **1/8**.
- Output JSON validi: **7/8** vs **8/8**.
- Token totali: **474.590** vs **258.649**.
- Durata totale: **709,365 s** vs **598,321 s**.
- A1_VERIFY riduce costi di inferenza ma **non** migliora la media di accuratezza in questa coorte.
- Documenti: `docs/a1_verify_paired_experiment_v1.md`, `docs/a1_verify_paired_runner_v1.md`.
- Freeze SHA-256: `e8c350d3e3372d0e4afb6fd63d60f2f5632394bc7e2a4b996ca0ff864ae2ccf0`; scoring SHA-256: `2504295d89f49c20c5e14da552ee176e54e52286cc2f86c417755367a814fb5f`.
- **Non confrontare direttamente** i punteggi medi storici con quelli ST sotto: si tratta di coorti differenti.

## 6. Secondo confronto completato (coorte development nuova)

**A1_VERIFY vs A1_VERIFY_ST** su 8 casi diversi dai precedenti, selezionati per SHA-256 e senza sovrapposizioni di finestre con casi storici né fra i nuovi. 16 esecuzioni su `gemini-3.5-flash-lite` con budget **4+2**, output contract `legacy`. Predizioni salvate **prima** dello scoring ufficiale.

**Versione sperimentale esatta:** `138fb523efec4a665a2424ab2faedb698f10562e`.

Risultati:

| Indicatore | A1_VERIFY | A1_VERIFY_ST |
|---|---:|---:|
| Score medio ufficiale | 0,2288 | 0,2913 |
| Score esattamente 1 | 0/8 | 1/8 |
| JSON conformi (parser legacy) | 7/8 | 8/8 |
| Token complessivi | 318.154 | 349.266 |
| Secondi totali end-to-end | 536,519 | 520,649 |

Analisi appaiata:

| Caso | VERIFY | ST | Delta ST − VERIFY |
|---|---:|---:|---:|
| cloudbed-1_q016 | 0,00 | 0,00 | 0,00 |
| cloudbed-1_q036 | 0,50 | 0,00 | −0,50 |
| cloudbed-1_q043 | 0,50 | 0,50 | 0,00 |
| cloudbed-1_q065 | 0,50 | 0,50 | 0,00 |
| cloudbed-2_q053 | 0,00 | 1,00 | +1,00 |
| cloudbed-2_q055 | 0,00 | 0,00 | 0,00 |
| cloudbed-2_q066 | 0,33 | 0,33 | 0,00 |
| cloudbed-2_q073 | 0,00 | 0,00 | 0,00 |

**1 caso migliore, 1 peggiore, 6 invariati; delta medio +0,0625**. Il vantaggio medio è sensibile al singolo caso q053 e non dimostra una superiorità robusta. A1_VERIFY su q053 ha omesso il campo `root cause reason`: output JSON sintatticamente leggibile ma non conforme a OpenRCA; conservato senza riparazione o retry. Validità formato e correttezza diagnostica sono metriche distinte.

Provenienza Google Drive (sotto `/content/drive/MyDrive/Tesi_OpenRCA`):
- Piano: `data/protocols/a1_verify_st_paired_development_v1_cohort_v1.json`, SHA-256 `b93d38ce4dcda942ce6b3c01cd5af80ae7f957857025fc73afca745ba11e6166`.
- Output: `data/results/paired/a1_verify_st_paired_development_v1/` (16 JSON e 8 marcatori).
- Freeze predizioni: `data/protocols/a1_verify_st_paired_development_v1_predictions_frozen_v1.json`, SHA-256 `43e646792685b1cde03052cadc2c8a82749d058a4e04ee0b01f607a7384fd104`.
- Report scoring: `data/results/a1_verify_st_paired_development_v1_official_scoring_v1.json`, SHA-256 `26f10169e379f9a8ceabcd83923ae7daa72ca90f705e021d77e6eb5772027f45`.
- Manifest GT-free `benchmark_inputs_market.csv` SHA-256 `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`; split `split_market_v1.csv` SHA-256 `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`.
- Analisi documentata: `docs/a1_verify_st_paired_results_2026-11-02.md`.

**Non fare ulteriori chiamate Gemini per queste 16 run.** Il runner blocca deliberatamente il retry, e i file restano immutabili. Se si fa uno studio nuovo, usare altro protocollo, run ID e coorte.

## 7. Branch del professore e notebook

Sul branch `presentation/relatore-2026-11-02` sono stati inseriti:
- `docs/a1_verify_st_paired_results_2026-11-02.md` — resoconto ST con punteggi, delta, hash, limiti.
- `docs/PRESENTAZIONE_RELATORE.md` — guida aggiornata con entrambi gli studi.
- `notebooks/Colab_Demo_Relatore_A1_VERIFY_ST.ipynb` — **notebook Colab di sola lettura**: mount Drive, controllo hash, tabella, grafici; nessuna API Gemini.
- `docs/r11_feasibility_plan_v1.md` — roadmap per R03/R04/R05 e futura ablation.
- `docs/a1_verify_st_protocol_v1.md` — disegno scientifico della variante ST.

La demo notebook si trova **nel repository GitHub**, non è stato asserito che sia già stata importata/valutata dentro il Drive dell'utente. Non sovrascrivere `Tesi_OpenRCA.ipynb` e `Colab_Demo_Relatore_OpenRCA.ipynb` preesistenti. Nessun test E2E Colab è stato eseguito dal solo salvataggio del nuovo notebook.

Link branch: https://github.com/alessio1996A/Tesi_Laurea_Magistrale_OpenRCA/tree/presentation/relatore-2026-11-02

## 8. Prossima attività concordata (NON ancora eseguita)

**Prima di implementare 11 regole**, fare un **audit GT-free della telemetria di rete del Market.zip** su finestre development non già valutate, controllando:
- R03: `container network packet retransmission`, presenza o assenza di misure dirette di ritrasmissioni, unità e controesempi;
- R04: `container network packet corruption`, presenza o assenza di segnali discriminanti per distinguere corruption, loss, timeout e latency;
- R05: `container network latency`, metriche/trace/log/mesh per latenza di rete e limiti nel separarla dalla durata dell'applicazione;
- colonne effettive, KPI, distribuzioni, timestamp e contesto; nessun uso delle etichette `record.csv` o `scoring_points`.

Usare `docs/r11_feasibility_plan_v1.md`. **Se mancano segnali specifici non inventarli:** una o più regole possono restare assenti. Non leggere etichette evaluation/OOD.

**Solo dopo** inventario, specifiche e test indipendenti, implementare eventuali regole in un nuovo branch, mantenendo intatti gli esperimenti precedenti. Preregistrare un confronto R8 vs R8+regole supportate con stesso planner e ST. Confronti su casi diversi non consentono differenze causali tra architetture.

**PAVE in parallelo, ma in un esperimento distinto:** studiare la possibilità di ricostruire un grafo osservativo RPC da trace parent/child e join con componenti service/container/node, catene candidate da causa a sintomo, validazione per arco con stato supportato/contraddetto/non verificabile e provenance. Senza interventi, chiamare sempre "supporto osservativo", non "verifica causale dimostrata". Non cambiare R8→R11 e PAVE nello stesso confronto se vogliamo attribuire gli effetti.

### Prossimo passo pratico nella nuova chat

1. Leggere questo handoff e `docs/r11_feasibility_plan_v1.md` tramite GitHub connesso.
2. Controllare su Google Drive, in **sola lettura** e con fonte verificata, la struttura di `Market.zip` e delle finestre development ancora libere. Se l'accesso non è disponibile, preparare celle Colab GT-free di inventario; non chiedere la chiave Gemini.
3. Registrare quali segnali di rete esistono davvero e quali sono insufficienti; classificare fattibilità delle tre regole.
4. Nessuna chiamata API Gemini o modifica ai file congelati.

## 9. Riferimenti scientifici e avvertenze

- Microsoft OpenRCA: https://github.com/microsoft/OpenRCA
- PAVE/OpenRCA 2.0: https://arxiv.org/abs/2606.27154
- Lo scorer ufficiale può assegnare punteggi a campi parziali: **non** attribuire automaticamente score zero a output legacy non conformi senza guardare lo scoring già registrato.
- `record.csv` e `query.csv` possono contenere etichette: non aprirli nel percorso dell'agente o nell'audit GT-free delle nuove regole.
- Se cambia una soglia dopo aver visto i risultati development, documentare l'iterazione e utilizzare casi indipendenti per la successiva valutazione.
- Non promettere "full PAVE" o "11 regole validate" prima di dati e test.

## 10. Avvertenza su continuità della chat

La memoria trasversale di ChatGPT può aiutare ma **non conserva necessariamente ogni dettaglio, file, hash e comando**. Il presente file è il punto di riferimento duraturo. Nella nuova chat chiedere esplicitamente di leggerlo e riprendere dall'audit GT-free R03–R05. Se una fonte non è accessibile, non inventare lo stato corrente: recuperarla tramite il connettore GitHub o il repository locale.


---

## 11. Fonti scientifiche recuperate e studiate

**Questo paragrafo è un indice ragionato, NON sostituisce le pubblicazioni originali.** I testi originali sono stati precedentemente caricati nella Library ChatGPT; una nuova chat con accesso alla Library può cercarli per nome. Per una verifica di citazioni e dettagli tecnici leggere le fonti originali; non attribuire loro risultati solo sulla base di questa sintesi.

1. **OpenRCA 1.0** — Junjielong Xu, Qinan Zhang, Zhiqing Zhong, Shilin He e altri, *OpenRCA: Can Large Language Models Locate the Root Cause of Software Failures?*, ICLR 2025; PDF già studiato con nome `13411_OpenRCA_Can_Large_Langua.pdf`. Benchmark generale: **335 failure cases** da 3 sistemi, >68 GB di telemetria (metriche, log e trace); **Market** usato nella tesi è un sottoinsieme distinto con **148 casi**, 44 componenti e 15 categorie. Il paper propone un RCA-agent che riceve una query, interroga tool e ricerca cause (elementi richiesti: tempo, componente, reason). L'esito storico riportato nel paper per Claude 3.5 è 11,34% di casi risolti nel setting studiato: **non è direttamente confrontabile** con gli score dei nostri otto casi Market.
   - Codice/benchmark: https://github.com/microsoft/OpenRCA
2. **OpenRCA 2.0 / PAVE** — Aoyang Fang, Yifan Yang, Jin'ao Shang e altri, *OpenRCA 2.0: From Outcome Labels to Causal Process Supervision*, arXiv:2606.27154v2, 30 giugno 2026; PDF in Library `2606.27154v2.pdf` (sono presenti anche copie numerate). PAVE significa **Path Annotation via Verified Effects**: annota e verifica step-wise percorsi di propagazione in **record di fault injection con interventi noti** (causa→effetto, forward verification), con controllo di topologia, anomalie di telemetria e compatibilità temporale. OpenRCA 2.0 propone 500 istanze cross-system con annotazioni causali. Distinguere metriche di risultato (root-cause accuracy) da metriche di **percorso** (path reachability, node/edge matching). **La nostra implementazione sul Market 1.0 non possiede gli interventi/annotazioni di quel setting e NON riproduce il protocollo PAVE.**
   - Paper: https://arxiv.org/abs/2606.27154
3. **White paper di lavoro sulle tecniche** — *Agent Harness, Agent Harnessing e Harness Engineering — Definizioni, perimetro architetturale, tassonomia delle tecniche e analisi critica della letteratura*, **versione 1.0, 13 ottobre 2026, 14 pagine**. Documenti della Library ChatGPT: `Agent_Harnessing_2026.docx`, `Agent_Harnessing_2026(1).docx`. Fonte di **definizioni operative e tassonomia proposta**, non un nuovo benchmark empirico né una legge che molte più tecniche migliorino sempre l'agente.

### Definizioni e concetti chiave del white paper

- **Agent Harness** = runtime che media e governa ciclo modello–ambiente, azioni, contesto, stato e verifiche.
- **Agent Harnessing** = strategie runtime che regolano osservazioni, azioni, controllo, feedback senza cambiare i pesi dell'LLM.
- **Harness Engineering** = progettare, implementare, versionare, valutare e migliorare l'harness con costi, rischi e qualità misurabili.
- Distinguere **prompt engineering** (istruzioni), **context engineering** (selezione/struttura informazioni), **harnessing** (governo operativo) ed **engineering** (processo scientifico e software).
- Principio guida: partire da baseline minima, identificare failure mode, cambiare **una tecnica alla volta**, usare ablation e regression, considerare token/tempo/accuratezza/validità. Più componenti non implicano migliore qualità.

### Le sedici voci della tassonomia del white paper (stessi titoli/numeri del testo)

1. Agent execution loop e ReAct.
2. Tool calling, action interface e tool design.
3. Context construction e retrieval policy.
4. Context compaction.
5. Tool-output offloading.
6. Progressive disclosure di skills e tools.
7. Persistent memory e task state management.
8. Planning e task decomposition.
9. Multi-agent orchestration e delegation.
10. Hooks, middleware e guardrail deterministici.
11. Sandboxing e constrained execution.
12. Feedback loop, self-verification e external verification.
13. Human-in-the-loop e handoff.
14. Observability, tracing ed evaluation.
15. Instruction, prompt e policy management.
16. Long-running execution, checkpoint e session handoff.

Il white paper distingue **6 responsabilità funzionali** dell'harness (Guo et al.: observation, context, control, action, state, verification/governance) e **7 sottosistemi** ricorrenti nei coding agent (Barbaste et al.: agent loop, LLM integration, tools/actions, memory/context, safety/permissions, orchestration, extensibility). Queste due mappe sono classificazioni con granularità diverse, **non** 6 o 7 ulteriori tecniche da sommare alle 16.

**Tecniche effettivamente pertinenti/realizzate nella nostra tesi:** 1 loop agentico LangGraph; 2 tool calling sui 5 tool e guardie di finestra; 3 costruzione/sintesi del contesto per RCA; 8 planning (4 round LLM + max 2 controlli); 10 validazione degli input/output e vincoli; 12 feedback osservativo e verifica di copertura, non di causalità; 14 tracing, audit, token/tempo, scorer e test; 15 prompt/output contract versionati; 16 freeze, provenance, manifest e isolamento dei run. **Non dichiarare che tutte le 16 siano state implementate.**

White paper: il primo harness può perfino peggiorare l'esito (es. Dhage), e il valore delle tecniche è **model/task-dependent**. Per questo abbiamo interpretato rigorosamente 1 vittoria ST, 1 sconfitta e 6 pareggi.

### Altri paper di Harness Engineering citati dal white paper (riferimenti da verificare per uso in bibliografia finale)

- Guo et al. (2026), *From Question Answering to Task Completion: A Survey on Agent System and Harness Design* (arXiv:2606.20683).
- Barbaste et al. (2026), *Harness Engineering: Anatomy, Architecture, and Evolution of Coding Agents—A Source-Code Study of Eleven Systems* (arXiv:2609.00006).
- Lin et al. (2026), *Agentic Harness Engineering: Observability-Driven Automatic Evolution of Coding-Agent Harnesses* (arXiv:2604.25850).
- Lee et al. (2026), *Meta-Harness: End-to-End Optimization of Model Harnesses* (arXiv:2603.28052).
- Zhang et al. (2026), *Self-Harness: Harnesses That Improve Themselves* (arXiv:2606.09498).
- Dhage (2026), *Harness Engineering for Predictable Agentic Systems: An Empirical Study of Deterministic Execution Constraints* (arXiv:2608.26197).
- Yao et al., *ReAct* (arXiv:2210.03629); Yang et al., *SWE-agent* (arXiv:2405.15793); Shinn et al., *Reflexion* (arXiv:2303.11366); Gou et al., *CRITIC* (arXiv:2305.11738).
- Practitioner: Addy Osmani, *Agent Harness Engineering* (2026); Hamel Bowne-Anderson, *Stop Overengineering Your Agent Harness* (2026).
- **Questi sono riferimenti contenuti nel white paper**; distinguere la loro bibliografia dall'effettiva lettura/validazione integrale di ogni singolo paper. Consultare le fonti originali prima di riportare cifre o citazioni nella tesi.

## 12. Indicazioni del professore/relatore — ricostruzione prudente da conversazioni precedenti

**Provenienza e limite:** il 21 ottobre 2026 l'utente ha condiviso la trascrizione di un colloquio con il relatore su Agent AI, LangGraph, Harness Engineering e OpenRCA Market. Non disponiamo qui della trascrizione integrale verificabile parola per parola. I punti sotto sono una **ricostruzione di note e risposte successive**, non citazioni letterali e non necessariamente tutti ordini esplicitamente pronunciati dal professore. Per contestazioni e formulazioni precise recuperare la trascrizione originale.

- **Obiettivo discusso:** studiare come il codice esterno di harnessing che recupera e prepara il contesto cambi il comportamento di un agente RCA a pesi fissi, rispetto a un agente senza harness. Far emergere qualità/efficienza, non solo una demo che funziona.
- **Prova iniziale suggerita:** un pilot limitato (nelle note ricorre una prova di circa **tre giorni**, eventualmente partendo dal sistema più piccolo) per confermare fattibilità prima di investire in una pipeline più grande. Questo si riferiva alla fase iniziale, già superata.
- **Confrontabilità:** stessi casi, task, modello, formato e condizioni quando si confrontano varianti; misurare accuratezza, falsi positivi/coverage, tempi e token. Distinguere i risultati storici da ablation appaiate sullo stesso insieme di casi.
- **Progressione architetturale discussa:** A0 agente autonomo vs A1 con preparazione deterministica del contesto; possibili livelli successivi di compatibilità temporale, dipendenze e verifiche, ed eventualmente integrazione ibrida. Nei primi riassunti di conversazione compariva una terminologia *concettuale* `B0` baseline rule-based, `A0`, `A1`, `A2`, `A3`, `A4`: **non confonderla** con le varianti realmente implementate e attualmente denominate `A1_V2`, `A1-R8`, `A1_VERIFY`, `A1_VERIFY_ST`.
- **Possibile obiettivo avanzato:** valutare se diagnosi validate possano diventare nuove regole deterministiche (*knowledge transfer*), tenendo categorie di guasto OOD non viste durante il training/sviluppo. Questo resta **futuro**: nessun loop automatico di apprendimento o nuova regola validata è stato implementato finora.
- **PAVE/OpenRCA 2.0:** fonte di idee per aggiungere dipendenze e verifiche osservabili, senza affermare che un grafo dedotto da soli `cmdb_id` equivalga a causalità accertata. Non confondere l'eventuale roadmap concettuale discussa con una richiesta formalmente conclusa o con un esperimento già eseguito.

### Cose NON disponibili in modo completo con l'attuale recupero

- **Parole testuali e ordine completo della trascrizione con il professore**, eventuali ulteriori richieste, scadenze, nomi o decisioni successive non registrate negli estratti.
- **Testo completo dei tre documenti scientifici nel repository**: il GitHub contiene i riferimenti/riassunti ma non i PDF/DOCX originali; i file sono stati individuati nella Library di ChatGPT. Per discussioni puntuali su formule, figure e limiti dei paper, consultarli direttamente.
- **Trascrizione completa di tutte le vecchie chat**: la memoria può riassumere ma non essere un registro perfetto.

Se nella nuova conversazione emerge un punto attribuito al professore ma non documentato, **non inventare né attribuire frasi letterali**. Recuperare gli appunti o chiedere all'utente il testo originale solo se davvero indispensabile.

## 13. Ripresa consigliata nella nuova chat

L'utente deve incollare: «Leggi integralmente `docs/HANDOFF_NUOVA_CHAT_TESI_OPENRCA_2026-11-02.md` sul branch `presentation/relatore-2026-11-02`; recupera quando necessario il white paper `Agent_Harnessing_2026.docx`, OpenRCA 1.0 e OpenRCA 2.0 dalla Library. Considera le note sul relatore una ricostruzione da verificare, non citazioni verbatim. Riprendiamo dall'audit GT-free R03/R04/R05, senza nuove chiamate Gemini e senza modificare i freeze.»
