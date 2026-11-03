# Guida alla presentazione del progetto (2 novembre 2026)

## Aggiornamento integrato — 3 novembre 2026

**Percorso per il colloquio:** [Presentazione integrata e interpretazioni](RELATORE_PRESENTAZIONE_INTEGRATA_2026-11-03.md). Il [nuovo notebook Colab](../notebooks/Colab_Relatore_Risultati_e_Regole_2026_11_03.ipynb) genera **9 grafici** dai due scoring congelati e dai conteggi degli audit di rete, senza nuove chiamate Gemini. Le demo storiche restano intatte.

- **Primo confronto:** A1-R8 vs A1_VERIFY, score medio 0,3850→0,3225, token −45,50%, tempo −15,65%.
- **Secondo confronto (altra coorte):** A1_VERIFY vs A1_VERIFY_ST, score medio 0,2288→0,2913; 1 miglioramento, 1 peggioramento, 6 pareggi.
- **R03:** 720/720 coppie TCP allo stesso timestamp, ma solo a livello nodo.
- **R04:** 720/720 profili di errori e drop tutti zero nel campione GT-free osservato.
- **R05:** 33.960/33.960 coppie Istio allo stesso timestamp, ma durata RPC ≠ sola latenza di rete.

[Nota di fattibilità R03/R04/R05, audit A/1–A/6](network_r03_r05_feasibility_relatore_2026-11-03.md). Gli script rimangono nel branch di analisi `feature/r03-r05-feasibility-schema-v1` e il codice sperimentale congelato non è stato modificato. A0 e A1_V2 sono rappresentati come architetture, senza punteggi non documentati.

## Aggiornamento: secondo esperimento A1_VERIFY_ST completato (2 novembre 2026)

**Codice storico primo esperimento:** `6927fcfa18fc29fce64ad65eac98231b2ba42184`.
**Codice congelato secondo esperimento:** `138fb523efec4a665a2424ab2faedb698f10562e`.
Il branch del relatore include ora entrambi gli esperimenti e puo' ricevere commit documentali successivi: per verificare le run usare i rispettivi commit, non il branch HEAD.

**Risultato A1_VERIFY vs A1_VERIFY_ST (altra coorte development, 8 coppie):** score medio 0,2288 vs 0,2913; vittorie ST 1, sconfitte ST 1, pareggi 6; output JSON validi 7/8 vs 8/8; token 318.154 vs 349.266; durata 536,519 s vs 520,649 s. Miglioramento medio non robusto, concentrato in `cloudbed-2_q053`. A1_VERIFY_ST usa un contesto osservativo cross-layer alla finalizzazione, **non** una verifica causale PAVE.

[Report sperimentale ST e hash dei file su Drive](a1_verify_st_paired_results_2026-11-02.md).



## Obiettivo della dimostrazione

Presentare il software Python progettato in PyCharm e gli esperimenti condotti in Google Colab. Lo sviluppo non deve compromettere gli 8 casi accoppiati già conclusi, congelati e valutati.

**Commit sperimentale del primo confronto**: `6927fcfa18fc29fce64ad65eac98231b2ba42184`.
**Commit sperimentale del confronto ST**: `138fb523efec4a665a2424ab2faedb698f10562e`.
**Branch di presentazione**: `presentation/relatore-2026-11-02`.
Questo branch contiene anche il codice A1_VERIFY_ST e documentazione aggiornata. I due commit sperimentali fissati restano i riferimenti per verificare le run.

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
│   │   └── structural_temporal_verifier.py  # contesto ST integrato e osservativo
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

## Secondo esperimento: mostrare i risultati reali, non il vecchio prototipo sintetico

Il file dimostrativo sintetico `src/evaluation/demo_verifica_pave_offline.py` **e' stato eliminato** e non va richiamato.

Per la demo aggiornata aprire [Colab_Demo_Relatore_A1_VERIFY_ST.ipynb](../notebooks/Colab_Demo_Relatore_A1_VERIFY_ST.ipynb): notebook indipendente **di sola lettura** che verifica i manifest e visualizza la tabella appaiata, senza chiamate API. Per il piano di verifica delle 3 nuove regole consultare [r11_feasibility_plan_v1.md](r11_feasibility_plan_v1.md). Al suo posto utilizzare `src/harness/structural_temporal_verifier.py`, `src/agent/verify_graph.py` e il report ST congelato. Il nuovo confronto non modifica il primo.

**Frozen ST**: `data/protocols/a1_verify_st_paired_development_v1_predictions_frozen_v1.json`, SHA-256 `43e646792685b1cde03052cadc2c8a82749d058a4e04ee0b01f607a7384fd104`.

**Scoring ST**: `data/results/a1_verify_st_paired_development_v1_official_scoring_v1.json`, SHA-256 `26f10169e379f9a8ceabcd83923ae7daa72ca90f705e021d77e6eb5772027f45`.

Usare un notebook Colab **di sola lettura**, separato dal notebook storico e senza chiamate Gemini; non eseguire i comandi `--execute-pair` o `--confirm-api`. Per riproducibilita' usare il commit sperimentale ST esatto.

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

**Regola generale:** non scambiare il primo prototipo offline per il contesto ST integrato e testato; la relazione osservativa non dimostra causalita'.
