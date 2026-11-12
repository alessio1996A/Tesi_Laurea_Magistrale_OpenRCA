# RQ2 — Identità dei modelli, tariffe e scenari di budget (pre-freeze)

**12 novembre 2026** — Documento di progettazione e stima **OFFLINE, NON eseguibile**. **Aggiornamento successivo del 12 novembre:** su indicazione dell'utente, il professore ha autorizzato un budget senza massimale prefissato; resta da finalizzare il protocollo tecnico/scientifico prima delle chiamate reali. RQ1 e i suoi risultati congelati rimangono invariati.

## 1. Base verificata

L'utente ha completato i test sintetici `src/tests/test_rq2_discovery_stage_recorder.py` con:

```
Ran 20 tests in 3.351s

OK
```

Sono **20/20** test del collegamento D→C→K e della persistenza isolata, non 20 inferenze LLM.

Il codice RQ1 attuale in `src/agent/model_factory.py` ammette `claude-sonnet-5-5` e `claude-haiku-5-5`. `ExperimentConfig` ha come default `gemini-3.5-flash-lite`. La selezione proposta è pertanto:

| Modello logico | Provider | ID API candidato | Fonte nel codice |
|---|---|---|---|
| Gemini | Google | `gemini-3.5-flash-lite` | `ExperimentConfig.model_name` |
| Sonnet | Anthropic | `claude-sonnet-5-5` | `ANTHROPIC_MODELS` |
| Haiku | Anthropic | `claude-haiku-5-5` | `ANTHROPIC_MODELS` |

Gli **ID sono compatibili con la factory**, ma questa verifica non prova che il servizio remoto sia disponibile al momento dell'esecuzione e non costituisce un freeze scientifico. Nel codice RQ1 Anthropic usa `max_retries=0` e `max_tokens=4096` per richiesta; non passa `temperature`, `top_p`, `top_k`. Gemini usa il default storico di `ChatGoogleGenerativeAI(model=model_name)`, senza fissare esplicitamente tali parametri. **Non introdurre silenziosamente nuove configurazioni**, che altererebbero il confronto con RQ1.

## 2. Tariffe ufficiali verificate il 12 novembre 2026

USD per **milione di token**, normale API paid tier, senza ipotizzare cache, batch o free tier:

| Modello | Input / MTok | Output / MTok | Precisazioni |
|---|---:|---:|---|
| Gemini 3.5 Flash-Lite | $0,30 | $2,50 | Output **include thinking tokens fatturabili** |
| Claude Sonnet 5.5 | $2,00 | $10,00 | Prezzo base |
| Claude Haiku 5.5 — prompt fino a 100.000 token | $0,10 | $0,50 | Soglia **per richiesta**, non per run D |
| Claude Haiku 5.5 — prompt oltre 100.000 token | $0,50 | $2,50 | Si applica alla richiesta superiore alla soglia |

**Fonti primarie:**
- Google: https://ai.google.dev/gemini-api/docs/pricing
- Anthropic: https://platform.claude.com/docs/en/about-claude/pricing
- Specifiche Haiku: https://platform.claude.com/docs/en/models/haiku-5-5/overview

Le tariffe sono **uno snapshot di progettazione** e devono essere verificate immediatamente prima delle API. Non assumere la tariffa ridotta di caching o Batch se non effettivamente usati e registrati.

## 3. Conti del piano: passaggi logici e invocazioni API

Il piano RQ2 candidato prevede **15 incidenti × 2 harness × 3 modelli**:
- D: **90 stage**, ciascuno con una run del vero agente e potenzialmente **diverse** chiamate modello;
- C: **90 stage**, idealmente **una chiamata tool-free ciascuno**;
- K: **24 stage**, una chiamata tool-free ciascuno, **solo 4 discovery × 2 harness × 3 modelli**;
- **204 stage logici totali**, ma **non 204 chiamate API totali**.

Per **singolo modello**, piano massimo: **30 D, 30 C e 8 K = 68 stage**. Alcune C/K possono essere bloccate dopo errori a monte e non consumare token. Non cambiare il denominatore scientifico per questa ragione.

## 4. Esempio di sensibilità, NON stima di spesa autorizzata

Lo script `src/evaluation/rq2_budget_preflight.py` accetta **assunzioni esplicite di token aggregati per singolo stage**, non legge telemetria o usage reale. Esempio puramente ipotetico (nessun numero qui rappresenta la media della coorte RQ2):

| Stage | Input token / stage ipotizzati | Output token / stage ipotizzati |
|---|---:|---:|
| D (somma di tutte le richieste di una run RCA) | 150.000 | 4.000 |
| C (una richiesta) | 8.000 | 600 |
| K (una richiesta) | 10.000 | 900 |

Sulle tariffe snapshot, per **tutte le 204 opportunità**, si ottiene in tale *scenario illustrativo*:

| Modello | Scenario con fascia bassa Haiku | Scenario conservativo Haiku |
|---|---:|---:|
| Gemini | $1,8090 | $1,8090 |
| Sonnet | $11,0920 | $11,0920 |
| Haiku | $0,5546 | $2,5946 |
| **Totale** | **$13,4556** | **$15,4956** |

Perché la fascia Haiku è un intervallo? I 150.000 input token nella D sono una **somma di più richieste**: nessuna singola richiesta potrebbe superare i 100.000, oppure una o più potrebbero superarli. Senza i valori per richiesta, il calcolatore presenta una fascia di tariffa e **non inventa la ripartizione**. Quando C/K consistono in una sola richiesta, una loro dimensione oltre 100.000 applica invece l'aliquota alta senza incertezza di ripartizione.

**Questi numeri non sono un tetto garantito e non sono una previsione robusta.** Le run reali possono consumare molti più o meno token, contenere token di thinking fatturabili, fallire dopo spesa, o incontrare cambi tariffari. Sono esclusi sconti cache e costi addizionali/FX/IVA. Un singolo pilot Sonnet storico ha riportato 141.065 token di input aggregati su 7 chiamate, ma **un pilot non dimostra la media della coorte**; la scelta di D=150k nello scenario non deve essere presentata come una media storica certificata.

## 5. Nuovo codice e controlli

`src/evaluation/rq2_budget_preflight.py`:
- `validate_existing_model_factory()` controlla la compatibilità degli ID con la factory storica, senza creare un oggetto LLM;
- `estimate_stage_token_cost()` calcola costo per modello e stage, con particolare attenzione alla soglia **per-request** di Haiku;
- `estimate_campaign_cost()` riceve esattamente 3 ipotesi di token D/C/K, conta i 30/30/8 stage per modello e calcola scenari low/conservative con `Decimal`, senza usare un provider o leggere file;
- Sempre `can_execute_api=false`, `api_budget_approved=false`, `scientific_protocol_frozen=false`, `cost_hard_cap_enforced=false`, `approved_spending_limit_usd=null`. **Nessun limite numerico è stato autorizzato dall'utente** e il codice non può far partire inference.

`src/tests/test_rq2_budget_preflight.py`: **16 test sintetici completati in PyCharm: `Ran 16 tests in 0.005s — OK`**. Coprono ID esatti, factory drift, tariffe e input non validi, soglia Haiku a 100k e per-request C/K, coorte 204, scenario riproducibile, nessun provider creato e nessun blocco sciolto.

### Prossimo comando PyCharm

```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_budget_preflight.py" -v
```

**Esito confermato dall'utente: 16/16 — OK.**

## 6. Decisioni da congelare PRIMA di spendere

1. **Versioni/ID e parametri**: tre nomi sopra, compatibili con RQ1; `temperature`, output token limit, eventuali effort defaults e tentativi di retry. Una modifica rispetto alla RQ1 va motivata.
2. **Output mode di D**: la scelta `legacy` vs `v2_enforce` è ancora aperta nel preflight; stabilirla prima della prima run. Per C/K i prompt/validator devono avere hash congelati.
3. **Budget senza limite USD prestabilito (decisione del relatore riferita dall'utente):** nessun hard cap finanziario da approvare o imporre; conservare token, numero di chiamate, utilizzo/costi a fini di reporting. Il **claim create-only** resta necessario per evitare duplicazioni involontarie e perdita di provenienza: non è una quota economica. Il calcolatore offline non autorizza l'esecuzione, che rimane subordinata al protocollo tecnico e scientifico.
4. **Pilot senza contaminazione dei test**: provare un caso sintetico o development e una sola configurazione, con massimo e log di token/costo. L'output del pilot non deve essere usato per ottimizzare le regole sui test.
5. **Scientific freeze**: protocolli, candidato 4+11, metriche e criterio di selezione K devono essere congelati *prima* dei risultati di test; l'archivio mock e il preflight budget non possono aprire il test.

**Stato:** RQ2 ancora `DRAFT_NOT_EXECUTABLE` per motivi tecnico-scientifici, **non per mancanza di budget economico**. Non sono state lanciate nuove API e non esistono risultati reali della discovery.
