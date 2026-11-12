# RQ2 — Politica provider proposta, ancora NON congelata (12 novembre 2026)

**Stato:** CANDIDATE_ONLY; non è una release, non abilita discovery/test,
non modifica i 13 blob RQ1 e non autorizza chiamate a pagamento.

## Provenienza: verifiche realmente eseguite dall'utente

**SDK e LangChain in Colab Python 3.13.18**: 
`langchain-core==1.7.1`, `langgraph==1.2.18`,
`langchain-google-genai==4.4.2`, `google-genai==2.34.0`,
`langchain-anthropic==1.7.7`, `anthropic==2.6.0`.
Fingerprint sorgenti registrati in
`RQ2_PROVIDER_POLICY_SOURCE_AUDIT_2026-11-12.md`.
Factory RQ1 invariata, Git blob `05308d5740763db0444556dcb7330d8fb4c308ec`.

1. **Colab source audit:** `7/7 OK`, versioni combacianti.
2. **Colab SDK retry mock:** `8/8 OK`, `google-genai.retry_args`
   con `None/attempts=1/attempts=2` → `1/1/2` callback
   artificiali; `anthropic max_retries=0` → un solo send a
   `httpx2.MockTransport` che risponde 503.
3. **Colab LangChain bridge source:** `RQ2 SOURCE TRACE: CONTROLLI
   SUPERATI` sulle SHA pinnate; Google traduce
   `max_retries` in `HttpRetryOptions(attempts=...)` e inoltra
   timeout in millisecondi; Anthropic inoltra entrambi.
4. **Colab LangChain parameter mock:** commit
   `5c6c56c246abbf7a187b173ac0375f88f9d2b440`;
   `8/8 OK` in 0.002s; con chiavi sintetiche e socket
   bloccati, Google `max_retries=1` e `timeout=300s`
   produce `attempts=1`, `timeout=300000ms`; Claude
   `max_retries=0` e `timeout=300s` producono
   client SDK `max_retries=0` e `timeout=300s`.
   `external_provider_requests=0`, `sdk_http_transport_exercised=false`.
   Questi sono **risultati di forwarding locale, non test di comportamento
   HTTP end-to-end o timeout sotto stallo**.

## Proposta di scelta per il freeze (non ancora approvata)

| Vincolo | Gemini | Claude Sonnet/Haiku |
|---|---|---|
| Max tentativi per singola chiamata LLM | 1 `HttpRetryOptions.attempts` | 1 invio = `max_retries=0` |
| Configurazione LangChain proposta | `max_retries=1` | `max_retries=0` |
| Timeout esplicito candidato per richiesta | `timeout=300s` | `timeout=300s` |
| Retry a livello runner / stage | vietato | vietato |
| Max output | storico Gemini, senza nuovi parametri sampling | `max_tokens=4096` storico |
| Modelle & prompt | ID e prompt della RQ1/bozza RQ2 immutati | idem |

**300 secondi non è ancora un valore congelato.** È il valore verificato
nel test di inoltro, proposto per rendere esplicito e simmetrico il timeout
di una *singola richiesta*, ma una D ha diverse richieste per round. Non
confonderlo con un limite globale di durata dello stage o della campagna.
Timeout e provider error = record di fallimento; **non** chiamata ripetuta,
**non** costo/tokens inferiti come zero, **non** correzione del JSON.

**Semantica importante:** `max_retries=1` su
`ChatGoogleGenerativeAI` diventa **1 tentativo complessivo**
(`HttpRetryOptions.attempts=1`) nella versione SHA pinnata,
non `1 retry dopo il primo tentativo`. Su Anthropic,
`max_retries=0` significa 0 retry dopo la prima richiesta.
Non scambiare questi parametri tra SDK.

## Integrazione successiva obbligatoriamente RQ2-only

**NON cambiare `src/agent/model_factory.py`, né sorgenti RQ1 frozen.**
Implementare una factory `crea_modello_rq2` con kwargs espliciti
(e versione/identità SRC/hash inclusi nella futura release) e usarla
esclusivamente **dopo** l'autorizzazione tramite release firmato:

- D: `run_experiment(config, llm=modello_rq2, verbose=False, salva=False)`;
  `run_experiment` originale supporta già `llm` opzionale: stessa
  configurazione task, graph, tool e harness, solo trasporto esplicitato.
- C/K: chiamare la stessa factory RQ2-only nello stage tool-free,
  dopo il claim immutabile e la verifica di release.
- Tutte le chiamate sono **sincrone `invoke`** negli stage previsti.
  Vietare `ainvoke`, `stream` e `astream` senza audit separato,
  soprattutto per possibili retry impliciti nel backend Google async.
- Non usare `with_retry` LangChain, callback di retry o
  task automatici Colab che possano avviare chiamate duplicate.
- Preservare sempre original source provenance, prestazioni e punteggi
  RQ1; **documentare che l'esperimento RQ2 esplicita la policy di
  trasporto a differenza della storica RQ1**. Non sostenere parità
  completa della configurazione provider.
- Rispettare l'ordine: preflight release SHA → verifica sorgenti/split
  → claim create-only → istanziazione provider → singolo stage; i test
  OOD devono restare separatamente preclusi fino al freeze K.

## Cosa resta da chiudere prima di una vera API

1. Un **solo** controllo finale con trasporto HTTP finto per verificare
   almeno il percorso `invoke` sync di Gemini e Claude e la propagazione
   di un errore sintetico senza retry. Non affermare certificazione di
   timeout di rete in assenza di prova della condizione di stallo;
   nominare i limiti esplicitamente. Se questa prova fallisce, fermare
   la release e correggere il trasporto RQ2-only, non modificare RQ1.
2. Formalizzare e versionare la policy di normalizzazione alias offline
   sul `predicted_fault_type` **prima di vedere predizioni OOD**;
   denominatori, astensioni e provider error già nella bozza.
3. Certificare (oppure dichiarare non formalizzabili) KPI/unità/operazioni
   per le candidate K; mai eseguire pseudocodice generato dal modello.
4. Preregistrare definitivamente `A1_8R + Sonnet` come arm dimostrativo
   primario e il carattere esplorativo per N piccolo; conservare
   il rapporto di audit GT isolato una-discovery-per-classe.
5. Firma create-only del release scientifico con hash pinnato,
   readback integrità e test che dimostrino D/C/K sbloccabili solo su
   discovery; **test OOD restano bloccati** fino al freeze delle regole.
6. Solo allora chiedere autorizzazione specifica alla **prima**
   chiamata a pagamento per una discovery pianificata.

**Progresso di tesi:** questa decisione di trasporto è documentazione
metodologica della RQ2; non è un risultato diagnostico. Con la consegna
del 1 dicembre, iniziare parallelamente la scrittura dei capitoli
RQ1/architettura senza aspettare l'esito delle discovery.


## 12/11: chiuso il gate del fake HTTP sync; integrazione RQ2-only candidata

**Output Colab realmente attestato:** sul commit
`7019020364dfae6ae649d9620ffb4948e70a2f71`,
`Ran 8 tests in 0.004s — OK`,
`SYNC_FAKE_HTTP_503_INVOKE_VERIFIED_AS_TESTED_NOT_RELEASED`.
Google `httpx.MockTransport` e Claude `httpx2.MockTransport`:
**1 solo send HTTP finto per ciascuna delle 4 invocazioni**,
`CK_tool_free` e `D_bound_tools` su entrambi i provider.
Zero richieste reali, zero tool eseguiti. È ora lecito considerare
**verificato solo** il no-retry per `invoke` sincrono con HTTP 503
mockato sulle versioni/sorgenti Colab pin, non per async,
streaming o timeout fisico.

**Codice candidato aggiunto dopo questo risultato** (da sottoporre
ancora a unit test aggiornati e freeze):
- `src/evaluation/rq2_model_factory.py`: consentiti esattamente
  Google Gemini 3.5 Flash Lite, Claude Sonnet 5.5 e Claude Haiku 5.5;
  verifica 6 versioni e 4 SHA file SDK prima di istanziare modelli;
  Google `max_retries=1`, Claude `max_retries=0`,
  entrambi `timeout=300s`, Claude `max_tokens=4096`.
  Nessuna nuova temperature/sampling option.
- `src/evaluation/rq2_discovery_d_provider_transport.py`:
  riutilizza `run_experiment(config, llm=..., salva=False)`
  senza cambiare il runner RQ1; istanzia la factory RQ2-only
  **dopo** la validazione del release e del claim create-only.
- `src/evaluation/rq2_ck_provider_transport.py`: importa
  `crea_modello_rq2` come factory locale, lasciando invariata
  la guardia del release, claim e l'unica `invoke` sync tool-free.
- Test `src/tests/test_rq2_model_factory.py` (10 test stdlib
  preparati, non ancora attestati) + adattamento al modello iniettato
  degli esistenti test D. Tutti i mock C/K già presenti patchano
  il simbolo locale `crea_modello` e non usano API vere.

**Distinzione da RQ1:** i kwargs della factory sono deliberatamente
più espliciti dei default Gemini storici e del timeout Claude storico.
Resta valida la comparazione di *harness* all'interno della RQ2, con
un trasporto replicabile; NON asserire che la configurazione provider
RQ2 sia identica a quella storica RQ1. La fonte dell'agente RQ1
`src/agent/model_factory.py` mantiene SHA Git blob
`05308d5740763db0444556dcb7330d8fb4c308ec`.
**Nessun release scientifico firmato e nessuna API live**.
Il valore timeout 300s è un candidato operativo verificato solo
come parametro, non come limite eseguito su stallo HTTP.
