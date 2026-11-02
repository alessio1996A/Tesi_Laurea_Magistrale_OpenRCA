# Protocollo A1_VERIFY vs A1_VERIFY_ST — sviluppo (v1)

**Stato al 2 novembre 2026:** variante implementata nel branch di sviluppo; nuovi run Gemini e scoring ufficiale **non ancora eseguiti**. Nessun risultato di accuratezza ST puo' essere dichiarato prima del freeze.

## Domanda di ricerca

L'inserimento di un contesto deterministico di coerenza strutturale/temporale nella finalizzazione, a parita' del resto dell'agente, migliora accuratezza, costo in token, latenza e conformita' JSON?

## Variabile indipendente unica

- **A1_VERIFY:** report con otto regole, max 4 round esplorativi, max 2 controlli mirati dal planner, una finalizzazione LLM.
- **A1_VERIFY_ST:** identica configurazione, **piu'** un report strutturale/temporale GT-free alla finalizzazione.

L'estensione ST NON modifica il planner, la sequenza di tool, le otto regole, le soglie, i prompt di base o l'output contract. Controlliamo il contributo della sola nuova informazione ST. Il numero di token nel prompt finale puo' differire, e deve essere conteggiato.

## Perche' proprio 4 + 2?

La quota 2/6 e' un compromesso definito in precedenza fra esplorazione autonoma e indagine coperta in modo deterministico. Serve a evitare che l'agente dedichi tutti i round a componenti gia' esaminati, ma **non e' una scelta ottimale dimostrata**. La manteniamo identica in entrambi i bracci per isolare l'effetto del contesto ST. Se il planner non trova candidati, i round riservati non tornano all'LLM. A1-R8 usa fino a 6 round liberi ed e' un confronto storico, non un controllo del solo planner.

## Copertura

R01, R02, R06, R07, R08, R09, R10, R11 sono attive in entrambi i bracci.
Il verificatore ST confronta soltanto:
- R01↔R07 (CPU container/nodo)
- R02↔R08 (memoria container/nodo)
- R06↔R09 (read I/O container/nodo)

R10 (write I/O nodo) e R11 (spazio disco nodo) restano nel report senza essere forzate in una coppia cross-layer. R03, R04, R05 non sono ancora implementate. Nessuna assenza di match e' prova che il componente sia sano.

## Limiti della verifica

- Le associazioni nodo/container provengono dagli identificativi di telemetria, non da un grafo applicativo verificato.
- L'ordine dei primi segnali non identifica l'istante di insorgenza della causa.
- Non abbiamo interventi fault-injection e percorsi causali di OpenRCA 2.0.
- I campi `causa_verificata` e `propagazione_verificata` rimangono falsi.
- Non si usa la ground truth per costruire il contesto, selezionare casi, orientare le verifiche o modificare le predizioni.

## Coorte indipendente di sviluppo

Generatore: `src/evaluation/paired_st_cohort.py` (nessun LLM).
Selezione SHA-256 su `a1-verify-st-2026-11-02-v1|case_id`, 4 development per cloudbed. Esclusi i quattro piloti storici e gli otto casi gia' valutati nel batch A1_VERIFY **sia per case_id che per sovrapposizione delle finestre nel medesimo cloudbed**. La selezione garantisce inoltre che i nuovi otto casi non si sovrappongano fra loro. Questo evita di scambiare due task sullo stesso incidente per casi indipendenti. Evaluation, mixed_quarantine e OOD_holdout non vengono ispezionati per la selezione.

Le 16 esecuzioni (8 coppie, 1 run per braccio/caso) devono usare:
- stessa versione SHA del codice, stesso modello/provider, stessi dati e stesse istruzioni;
- stesso `max_tool_rounds=6`, `max_verification_checks=2`, `output_contract_mode=legacy`;
- ordine AB/BA gia' indicato nel piano;
- salvataggi esclusivi con `open('x')` e run ID univoci: MAI sovrascrivere gli output precedenti;
- predizioni, raw response, errori, tool trajectory, hash del report, metriche di token/tempo/chiamate;
- scoring ufficiale eseguito **soltanto dopo il salvataggio e freeze completo** di tutti gli output.

## Esecuzione

Prima eseguire da PyCharm:
```bash
python -m unittest discover -s src/tests -p "test_*.py" -v
```

Colab, solo preflight GT-free (nessuna chiamata Gemini):
```bash
PYTHONPATH=src python src/evaluation/paired_st_cohort.py \
  --data-dir /content/drive/MyDrive/Tesi_OpenRCA
```

Solo dopo che la suite e' verde, aggiungere `--freeze` per registrare il piano in `data/protocols/a1_verify_st_paired_development_v1_cohort_v1.json`. Il generatore del piano NON avvia alcun modello.

Runner ST, prima sola ispezione GT-free e controllo degli output:
```bash
PYTHONPATH=src python src/evaluation/manual_paired_st_batch.py \\
  --data-dir /content/drive/MyDrive/Tesi_OpenRCA \\
  --repo-dir /content/Tesi_OpenRCA
```

Per eseguire **una sola coppia** (richiede chiave API, puo' comportare costi e deve seguire preflight e freeze):
```bash
PYTHONPATH=src python src/evaluation/manual_paired_st_batch.py \\
  --data-dir /content/drive/MyDrive/Tesi_OpenRCA \\
  --repo-dir /content/Tesi_OpenRCA \\
  --execute-pair cloudbed-2_q073 --confirm-api
```

Il runner registra un marcatore permanente prima delle API e salva ogni run con modalita' esclusiva: se una coppia si interrompe, **non avviare un retry automatico**. Continuare solo dopo controllo manuale di costi, output e provenienza. Ogni nuovo risultato deve riportare lo stesso commit Git dei precedenti.

## Misure e interpretazione

Registrare: score ufficiale medio, delta per coppia, diagnosi pienamente corrette, JSON validity, token completi, latenza end-to-end, chiamate LLM e tool, numero di relazioni ST, casi non valutabili, errori. Con sole otto coppie, dichiarare risultati preliminari e senza significativita' statistica garantita.

**Fase successiva distinta:** audit dei segnali R03/R04/R05, validazione dei detector su nuovi development e, se possibile, un altro confronto R8 vs R11 a ST invariato.
