# V2.6B — Recupero controllato dopo import Gemini mancante

**3 novembre 2026. Stato: patch e test pubblicati, NON ancora eseguiti su Colab.**

## Evidenza del secondo tentativo, pre-API

Nella prima run di A0 `cloudbed-1_q005`, dopo il freeze
`openrca_harness_v2_five_agents_development_v2`, il runner si e'
fermato durante `from langchain_google_genai import ChatGoogleGenerativeAI`:

`ModuleNotFoundError: No module named 'langchain_google_genai'`.

Il file `requirements.txt` del repository elenca gia' il pacchetto
`langchain-google-genai`, ma la sessione Colab non lo aveva installato.
Il traceback mostra il guasto nella creazione del client locale, **prima
dell'invocazione del grafo e di Gemini**. A differenza del primo errore SHA
A0, qui il runner aveva **gia' scritto il claim** permanente.
Verificare su Drive che il claim esista e che l'output JSON non esista.
Non cancellare il claim, non modificare il file di freeze e non rieseguire
automaticamente la run con lo stesso run ID.

## Recupero metodologicamente corretto

1. Conservare il piano v1 originale con SHA
   `b5444e85335e273e71cb08326c5988469af992cfe7d1d5f2d79562abeb806d01`.
2. Conservare il piano v2 e il claim v2 che documenta il tentativo
   pre-API fallito. Nessuna risposta LLM deve essere inventata per quel
   tentativo. Non cancellare i file.
3. Installare i pacchetti elencati in `requirements.txt` nello stesso
   interpreter Python usato dal runner, prima di nuovi esperimenti.
   Verificare import `langchain_google_genai`, `langgraph` e
   `ChatGoogleGenerativeAI` senza chiamare l'API.
4. La revisione `v3` conserva invariati 8 incidenti, sette task,
   split development, modello, prompt, budget, agenti e selezione,
   ma controlla gli import runtime `langchain_google_genai`,
   `agent.graph_engine`, e per i verificatori `agent.verify_graph`,
   **prima** di scrivere il claim. Un modulo mancante ferma la run
   senza creare claim e senza chiamare API.
5. Codice di selezione: stesso seed e stessi 8 ID, ma protocollo
   `openrca_harness_v2_five_agents_development_v3`: produce file
   `data/protocols/v2/openrca_harness_v2_five_agents_development_v3_plan_v1.json`
   e `data/results/v2/openrca_harness_v2_five_agents_development_v3/`.
   In nessun caso riutilizzare i vecchi run ID, eliminare i vecchi claim,
   o ricalcolare retroattivamente vecchi scoring.
6. Prima di congelare: superare **71 test offline** (`test_v2*.py`),
   ripetere la preview, verificare che il registro A/2 sia lo stesso.
   Freeze con apertura create-only e registrazione SHA e commit; verificare
   8 ready + 32 waiting in preflight. L'utente ha autorizzato la **sola prima
   esecuzione A0**; le successive richiedono un nuovo controllo.

## Limiti

La validazione offline delle dipendenze riduce i fallimenti prevedibili
ma non garantisce il successo dell'API, dei tool o della generazione.
Anche dopo l'installazione e il preflight, un errore di runtime potrebbe
avvenire dopo il claim: fermarsi e ispezionare prima di qualsiasi altra
esecuzione, senza retry.

**Nessuna chiamata Gemini viene effettuata durante installazione, import,
test sintetici, preview, freeze o preflight.**
