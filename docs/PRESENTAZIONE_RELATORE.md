# Guida alla presentazione del progetto (2 novembre 2026)

## Obiettivo della dimostrazione

Presentare il software Python progettato in PyCharm e gli esperimenti condotti in Google Colab. Lo sviluppo non deve compromettere gli 8 casi accoppiati già conclusi, congelati e valutati.

**Commit sperimentale immutabile**: `6927fcfa18fc29fce64ad65eac98231b2ba42184`.
**Branch di presentazione**: `presentation/relatore-2026-11-02`.
Questo branch contiene solo pulizia documentale, commenti e rimozione di file locali dell'IDE.

## Struttura del repository

```text
Tesi_Laurea_Magistrale_OpenRCA/
├── README.md
├── requirements.txt
├── src/
│   ├── agent/
│   │   ├── tools.py               # lettura e sintesi telemetria
│   │   ├── tool_factory.py        # 5 tool vincolati al caso e alla finestra
│   │   ├── model_factory.py       # provider Google, interfaccia espandibile
│   │   ├── prompts.py             # prompt RCA condiviso
│   │   ├── graph_engine.py        # A0/A1
│   │   └── verify_graph.py        # A1_VERIFY con planner e finale
│   ├── harness/
│   │   ├── evidence_builder.py    # estrazione anomalie ed evidenze
│   │   ├── evidence_selector.py   # qualità/candidati
│   │   ├── evidence_summarizer.py # sintesi e budget
│   │   ├── unified_report.py      # report fornito all'LLM
│   │   ├── rule_batch.py          # 8 regole implementate
│   │   ├── rules/                 # detector per node e container
│   │   ├── investigation_planner.py
│   │   └── structural_temporal_verifier.py  # prototipo OFFLINE
│   ├── output/                    # contratto JSON canonico
│   ├── evaluation/                # runner, coorte, audit, scoring separato
│   └── tests/                     # regressione software
├── docs/                          # protocolli e analisi
└── tools/                         # utilità storiche di manutenzione
```

Queste directory hanno già una divisione per responsabilità; NON spostarle in massa, perché ciò comporterebbe modifiche agli import e rischio di regressioni.

## Cosa mostrare in PyCharm (5–10 file)

1. `src/agent/tool_factory.py` — i cinque tool, filtro cloudbed e guardia temporale.
2. `src/agent/tools.py` — un esempio di lettura CSV a chunk e sintesi KPI.
3. `src/harness/unified_report.py` e `evidence_summarizer.py` — report compatto.
4. `src/harness/rule_batch.py` e una delle otto regole in `rules/`.
5. `src/agent/graph_engine.py` — ciclo A1 con tool; `verify_graph.py` — esplorazione, planner, verifica, finale.
6. `src/evaluation/paired_cohort.py` e `paired_runner.py` — preregistrazione, protezioni anti-rerun, provenienza.
7. `src/output/openrca_contract.py` — schema JSON e validazione.
8. `src/tests/` — test offline e isolamento dell'LLM.

I commenti in italiano sono introdotti nelle fasi chiave di `verify_graph.py` senza alterarne la logica.

## Cosa mostrare in Colab

Il notebook **Colab_Demo_Relatore_OpenRCA.ipynb** è stato creato come file separato dal notebook storico `Tesi_OpenRCA.ipynb` (122 celle). Il notebook e' stato [caricato nella cartella demo_relatore su Drive](https://drive.google.com/file/d/1JIdqEdpvHuUIgDQ96_QCFabBBCf2IGyP/view?usp=drivesdk). Aprirlo da Colab tramite Google Drive e percorrerne le sezioni in ordine:

1. Mount Drive e checkout **del commit sperimentale fissato**, senza `git pull`.
2. Mappa del progetto e creazione dei cinque tool (non invoca Gemini).
3. Catalogo delle otto regole deterministiche e limiti.
4. Verifica SHA-256 dei 16 output e 8 marcatori.
5. **Replay storico** di `cloudbed-2_q033`, evidenziando le due verifiche pianificate.
6. Tabella degli 8 casi e grafici, letti dal file di scoring congelato.
7. Suite test (facoltativa e offline).

**Non rilanciare le otto coppie**: il runner impedisce volontariamente replay delle chiamate API potenzialmente fatturate. Per una dimostrazione live di Gemini serve una nuova esecuzione separata, pre-approvata, su un caso nuovo e con risultato distinto.

## Dati su Drive: conservare

```text
Tesi_OpenRCA/
├── Market.zip                   # benchmark voluminoso
├── Tesi_OpenRCA.ipynb           # notebook storico; NON cancellare
├── Tesi_OpenRCA_backup.ipynb    # backup storico; NON cancellare
└── data/
    ├── processed/               # split e manifest GT-free
    ├── protocols/
    │   ├── a1_verify_paired_development_v1_cohort_v1.json
    │   └── a1_verify_paired_development_v1_results_freeze_v1.json
    └── results/
        ├── paired/a1_verify_paired_development_v1/
        └── scoring/a1_verify_paired_development_v1_official_scoring_v1.json
```

I file `record.csv`, `query.csv` e le predizioni storiche NON vanno eliminati senza una verifica della provenienza. I primi possono contenere etichette/risposte e non devono essere esposti ai runner investigativi.

## Cleanup sicuro

- Su questo branch rimuovere dal controllo di versione **solo** i file `.idea/` locali di PyCharm e aggiungerli a `.gitignore`.
- **Conservare** `src/evaluation/A0_OpenRCA.py`, `A1_OpenRCA.py`, `manual_*.py`, gli script `tools/`, e i documenti storici: alcuni possono servire per riprodurre prove passate.
- Non cambiare nomi, percorsi o import dei moduli centrali in prossimità della discussione.
- Eseguire `python -m unittest discover -s src/tests -p 'test_*.py' -v` in PyCharm prima di integrare il branch.

## Risultati da riportare senza esagerazioni

| Misura, 8 casi development | A1-R8 | A1_VERIFY |
| --- | ---: | ---: |
| Score medio ufficiale | 0,3850 | 0,3225 |
| Exact score = 1 | 2/8 | 1/8 |
| Output JSON validi | 7/8 | 8/8 |
| Token | 474.590 | 258.649 |
| Secondi end-to-end | 709,365 | 598,321 |

Interpretazione: significativa riduzione osservata del costo in token (−45,50%), ma nessun miglioramento osservato di accuratezza. Otto casi non dimostrano la generalizzabilità. Le verifiche del planner NON certificano causalità; il verificatore strutturale/temporale ispirato a PAVE non è stato integrato nella sperimentazione; il knowledge transfer e la valutazione OOD sono futuri.

## Riferimenti integri

- Freeze file SHA256: `e8c350d3e3372d0e4afb6fd63d60f2f5632394bc7e2a4b996ca0ff864ae2ccf0`.
- Scoring file SHA256: `2504295d89f49c20c5e14da552ee176e54e52286cc2f86c417755367a814fb5f`.
- Scorer ufficiale Microsoft: commit `2a481ae63cb045c3eadbeca9eddaa10ec1151979`.

**Regola generale:** presentare la ricerca conclusa senza scambiare i prototipi offline per componenti già valutati.
