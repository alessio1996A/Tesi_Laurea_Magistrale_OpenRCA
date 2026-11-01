# Pre-registrazione del primo confronto accoppiato A1 vs A1_VERIFY

Protocollo: `a1_verify_paired_development_v1`

## Ipotesi e fattori sperimentali

**Domanda:** a parita' di budget massimo di round con tool,
una quota di verifiche mirate pre-finalizzazione aumenta lo score
ufficiale OpenRCA e/o la robustezza del processo RCA rispetto ad A1?

- **Baseline A1-R8:** fino a 6 round di esplorazione LLM.
- **A1_VERIFY:** fino a 4 round di esplorazione LLM + fino a 2
  verifiche deterministiche via ToolNode. Non assume che anomalie
  identifichino causalmente la root cause.
- **Costanti:** stesso caso, finestra, versione del dataset, modello
  `gemini-3.5-flash-lite`, provider Google, stesso prompt A1 di
  base, stessa evidence SHA (da verificare per ogni coppia), stessa
  suite di tool, output mode `legacy`, budget massimo 6 round,
  `recursion_limit=30`.
- **Differenze dichiarate:** distribuzione dei round, eventuali
  chiamate addizionali ai tool e un'eventuale chiamata aggiuntiva LLM
  per il finale A1_VERIFY. Uguale budget in round non significa
  necessariamente uguale budget in token o costo.

## Pre-registrazione GT-free

**Selezione predefinita:** 4 `development` per cloudbed (8 casi)
come studio di fattibilita'. Una esecuzione per braccio e caso,
quindi 16 esecuzioni LLM totali *solo quando verra' autorizzato il
batch*: il preflight descritto sotto non fa nessuna chiamata API.

I quattro piloti gia' ispezionati
`cloudbed-1_q052`, `cloudbed-1_q040`,
`cloudbed-2_q006`, `cloudbed-2_q012` sono esclusi anche se
classificati development.

Selection seed immutabile: `a1verify-2026-11-01-v1`.
Ordinamento e scelta SHA-256 su `seed|case_id`; la scelta non dipende
da metriche, punteggi, categorie di guasti o predizioni. All'interno
di ogni coppia, ordine AB/BA deterministico registrato a priori.

Selezione effettuata solo da:
- `data/processed/split_market_v1.csv` (colonne `case_id,split`);
- `data/processed/benchmark_inputs_market.csv` (crosscheck che
  i case ID esistano nel manifest GT-free; nessun uso di altri campi).

Il preflight **rifiuta** CSV con colonne GT note o partizioni non
riconosciute, case ID duplicati, differenze rispetto ai conteggi
dello split precedentemente congelato:
`development=92, evaluation=23, mixed_quarantine=18,
ood_holdout=15`. Non seleziona mai altri split. Nessuna lettura
di Market.zip, risultati, scorer o chiavi API.

Il piano descrive un **feasibility study**: 8 casi e una replica
per variante non consentono conclusioni definitive o affermazioni
statisticamente robuste.

## Esecuzione offline e congelamento

Con PyCharm (test):
```shell
git pull --ff-only origin refactor/model-agnostic-harness-v1
python -m unittest discover -s src/tests -p "test_*.py" -v
```

In Colab, dopo il mount di Drive e il pull:
```shell
PYTHONPATH=src python src/evaluation/manual_preregister_dev.py \
    --data-dir /content/drive/MyDrive/Tesi_OpenRCA
```

**Senza `--freeze`: anteprima soltanto, non scrive file.**
Verificare prima i conteggi e gli otto case ID restituiti.

Solo dopo revisione del piano, eseguire lo stesso comando con
`--freeze`; questo crea un file con modalita' esclusiva `x`
in `data/protocols/a1_verify_paired_development_v1_cohort_v1.json`.
Non sovrascrivere piani precedenti. Il piano registra SHA-256 dei
due input, IDs, split counts, ordine dei bracci e run IDs previsti.

## Prescrizioni del batch successivo (non ancora eseguito)

- Escludere ogni caso usato in prototipazione dagli eventuali
  ulteriori studi di validazione.
- Salvare gli output in un **nuovo namespace** con ID univoci per
  trial, e usando `open("x")` senza sovrascrittura.
- Una volta creato il piano congelato, non sostituire casi con
  esiti sfavorevoli e non riordinare la coorte in funzione degli
  score. Per errori infrastrutturali, registrare l'errore e
  applicare eventuali retry predefiniti, mai selettivi in base
  alla correttezza della risposta.
- Salvare gli hash di codice/prompt/evidenze, il `raw_response`,
  predizione, esito JSON, metriche e traiettoria.
- Valutare **solo dopo che le predizioni dei due bracci
  sono state salvate e congelate** con il software di scoring
  ufficiale, rigorosamente offline rispetto all'agente.
- Report: score ufficiale per caso/braccio, differenza accoppiata,
  successi completi, JSON validity, chiamate LLM, tool calls e
  round effettivi, total tokens con stato di completezza,
  latenza e fallimenti. Dichiarare eventuali valori mancanti.
- Per evitare affermazioni causali improprie, separare:
  verifiche osservazionali, copertura investigativa e score RCA.
- Trattare i risultati della coorte come *preliminari*.
  Un eventuale test piu' ampio / replicato richiede ulteriori
  casi development mai usati nella scelta della policy.
- Mantenere evaluation/OOD sigillati fino al freeze della
  versione finale e al confronto scientifico predefinito.

**Non avviare il batch API automaticamente** dalla funzione
di selezione o dal comando di anteprima.
