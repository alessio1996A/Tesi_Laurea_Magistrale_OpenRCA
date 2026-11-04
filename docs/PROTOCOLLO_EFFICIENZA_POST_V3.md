# Prototipo di ottimizzazione post-V3 — 4 novembre 2026

Questo lavoro è stato isolato nel branch
`feature/efficiency-prototype-2026-11-04` e NON modifica il codice
e le 40 run del commit V3 congelato
`6747eecc77c1b2fff7d581c7284578b5c574b4f7`.

## Ipotesi specifica

Ridurre round di esplorazione LLM non informativi può diminuire token
e latenza senza peggiorare troppo la diagnosi. L'ipotesi è da **testare**,
non è un risultato già dimostrato.

### Primo segnale osservativo: cloudbed-1_q013

- Storico A1 (nuovo **A1_8R**): 572,822 secondi, 45.321 token,
  7 chiamate LLM, 6 chiamate ai tool, preprocessing 13,043 secondi.
  Le sei chiamate sono 2 node metrics, 1 service metrics e 3 trace.
- Storico A1_VERIFY (nuovo **A1_8R_Planning**): 36,536 secondi,
  26.921 token, 4 chiamate LLM, 3 chiamate ai tool,
  preprocessing 13,685 secondi.
- Entrambe le run hanno score OpenRCA 0 per questo incidente.
- Non è possibile concludere che le tre trace dell'A1_8R fossero
  inutili: le richieste differivano nei parametri e nei periodi.
- Non si deve attribuire tutta la differenza di tempo al planner:
  latenza modello, rete e strumenti variano fra esecuzioni.

La maggior parte del tempo della run A1_8R di questo caso non è
preprocessing: circa 560 secondi si concentrano nelle restanti fasi.
Questo suggerisce di profilare prima esplorazione/tool/LLM.

## Audit offline, senza costo API

Lo script `src/evaluation/offline_efficiency_audit.py` legge SOLO i
metadati di performance e `tool_trajectory` dei JSON già salvati.

```bash
# Da Colab, dopo aver montato Drive e inserito src nel PYTHONPATH:
PYTHONPATH=src python -m evaluation.offline_efficiency_audit \
  /content/drive/MyDrive/Tesi_OpenRCA/data/results/v2/openrca_harness_v2_five_agents_development_v3 \
  --top 10
```

Lo script riporta per variante numero di run, LLM/tool medi,
token/tempo/preprocessing medi e conteggi di:
- **ripetizioni di famiglia**: chiamate allo stesso tipo di tool;
  NON implicano lavoro duplicato;
- **duplicati esatti**: stesso nome tool e identici parametri JSON;
  segnali candidati per eventuale caching.

Nessuna lettura di `query.csv`, `scoring_points` o `record.csv`.
Nessun nuovo esperimento e nessun file creato/sovrascritto dalla CLI.

## Primo esperimento candidato, dopo il colloquio

Non servono nuove regole o nuove famiglie di agenti per una prima ablation.
La configurazione `ExperimentConfig` già permette di variare
`max_tool_rounds` per il nuovo **A1_8R**.

- **Controllo:** A1_8R, massimo 6 round di tool.
- **Trattamento:** A1_8R, massimo 4 round di tool.
- Modello, prompt di sistema, output contract, cinque tool, report,
  otto regole, manifest GT-free e finalizzazione invariati.
- Scegliere *prima di leggere la ground truth* una coorte nuova,
  disgiunta dai 8 incidenti V3 già analizzati.
- Congelare manifest, selezione, algoritmo, numero di repliche,
  modelli, limiti e piano sperimentale prima delle nuove run.
- Due o più repliche per caso e per variante, ordine bilanciato,
  salvo vincoli tecnici e costi concordati.
- Registrare score ufficiale e output validi (primari);
  token, costo stimato e durata (secondari), oltre alla differenza
  paired di score per caso.
- Dopo aver congelato i JSON, calcolare lo score su GT offline;
  non modificare parametri retroattivamente sugli stessi casi.

**Regola di decisione:** non presentare una riduzione di token come
miglioramento complessivo finché non è verificato il costo in accuratezza
sui nuovi casi. Una eventuale variazione di accuratezza sul campione
ristretto non dimostra da sola generalizzazione.

## Alternative da considerare dopo l'audit

1. Evitare query *esattamente identiche* soltanto se l'interfaccia del
   tool è deterministica per quei parametri e non cambia output;
   un cache miss/hit non deve occultare errori di tool.
2. Ridurre il rumore del report deterministico sulla base di misure
   del numero di token **senza eliminare segnali rilevanti non testati**.
3. Migliorare i criteri di scelta dei candidati e la priorità delle
   verifiche in funzione della *copertura*, ma non specializzarli sulle
   etichette dei 8 incidenti V3.
4. Miglioramenti di accuratezza su rete/corruzione pacchetti richiedono
   una nuova ipotesi, telemetria misurabile e una coorte blind:
   non aggiungere regole R12/R13 per poi valutarle sugli stessi q005/q027.

## Controlli prima della prossima run

```bash
python -m compileall -q src
PYTHONPATH=src python -m unittest discover -s src/tests -p "test_*.py" -v
```

La variante di questo branch è **esplorativa**, e la suite va
rieseguita nel proprio ambiente Python. Non si devono modificare
la demo del relatore o i risultati V3 già congelati.
