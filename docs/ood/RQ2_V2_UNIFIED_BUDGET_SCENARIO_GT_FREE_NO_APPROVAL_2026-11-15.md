# RQ2-V2 Opzione A — Scenario budget GT-free (non e' autorizzazione)

**Data ricontrollo listini pubblici:** 15 novembre 2026.  
**Scopo:** prima ricognizione quantitativa per release scientifica RQ2-V2.  
**Stato:** WHAT-IF, `api_budget_approved=false`, `can_execute_api=false`.  
**Nota:** i token ipotizzati NON sono un'osservazione sulle 180 run, non sono upper bound e non rappresentano un preventivo del fornitore.

## Matrice corretta RQ2-V2

- 4 casi discovery (GT-free), 5 harness, 3 LLM.
- Per **ciascun modello**: 20 D, 20 C, 20 K, in totale 60 stage; 180 stage logici complessivi.
- 492 `max_graph_invocations_candidate` secondo G4B, **non** 492 HTTP garantiti, **non** 492 richieste da pagare.
- Un errore D/C puo' impedire i successivi stage, quindi il numero di stage effettivamente completabili non e' garantito.
- Il vecchio helper `estimate_campaign_cost()` in `rq2_budget_preflight.py` conta **30 D,30 C,8 K per modello per RQ2 V1**: NON utilizzarlo come proiezione complessiva di questa V2. Riutilizzabile per la formula unitaria `estimate_stage_token_cost()` (pure, no API).

## Listini Standard PAID senza cache/batch, USD per milione token

| Modello | Input | Output | Condizioni |
| --- | ---: | ---: | --- |
| `gemini-3.5-flash-lite` | 0.30 | 2.50 | Include thinking nell'output fatturabile |
| `claude-sonnet-5-5` | 2.00 | 10.00 | Tariffa Standard |
| `claude-haiku-5-5` | 0.10 | 0.50 | Ogni *request* con prompt <=100k token |
| `claude-haiku-5-5` alta | 0.50 | 2.50 | Ogni *request* con prompt >100k token |

Fonti ufficiali consultate:
- https://ai.google.dev/gemini-api/docs/pricing
- https://platform.claude.com/docs/en/about-claude/pricing

Sono tariffe **consultate** il 15/11/2026, non bloccate per gli addebiti futuri. Ricontrollare poco prima di ogni autorizzazione live. Non si assumono cache, free-tier, Batch, tasse, maggiorazioni, strumenti esterni, commissioni o overage.

## Ipotesi ILLUSTRATIVE omogenee (non osservazioni)

- Ogni **D**, sommando *tutte* le richieste LangChain del singolo stage: 150.000 token input + 5.000 output.
- Ogni **C**: 10.000 input + 2.000 output.
- Ogni **K**: 10.000 input + 2.000 output.
- Assunzioni scelte soltanto per mostrare sensibilita' dei costi con lo stesso carico su tutti i modelli: tokenizer e output effettivi differiranno. Non dedurre la realisticita' dell'assunzione C/K da alcun risultato precedente.
- Per Haiku D, la soglia 100k dipende dai token di **ogni singola richiesta**, non dai 150k aggregati dello stage. L'intervallo usa tutte richieste sotto soglia vs tariffa alta su ogni token come estremo prudenziale *a token fissati*; **non e' un limite massimo della spesa**.

### Formula esatta per le ipotesi

`stage_cost = input_tokens * input_rate / 1_000_000 + output_tokens * output_rate / 1_000_000`.

`scenario_per_model = 20 * cost(D) + 20 * cost(C) + 20 * cost(K)`.

| Modello | D singolo (USD) | C singolo (USD) | K singolo (USD) | 60 stage del modello (USD) |
| --- | ---: | ---: | ---: | ---: |
| Gemini | 0.0575 | 0.0080 | 0.0080 | 1.47 |
| Sonnet | 0.3500 | 0.0400 | 0.0400 | 8.60 |
| Haiku | 0.0175–0.0875 | 0.0020 | 0.0020 | 0.43–1.83 |
| **Totale illustrativo 180 stage** | | | | **10.50–11.90** |

**Interpretazione corretta:** USD 10.50–11.90 e' il costo matematico condizionato a *questi token esatti*, alle tariffe descritte e al completamento di tutti gli stage. NON e' una previsione attendibile dell'intera campagna e **NON** e' un limite tecnico di fatturazione. Un singolo D puo' superare largamente le assunzioni. Il timeout di 300 secondi e' configurato *per request*, non per stage.

## Scelta del pilot D

Ordine di piano: primo candidato **non autorizzato**
`rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:D`.

Alla sensibilita' puramente teorica di 150k input + 5k output, costo Gemini stimato `USD 0.0575`, non una garanzia che il pilot costi meno di USD 0.10. Prima di richiedere la prima esecuzione:
1. definire un **budget operativo esplicito e non sintetico**, separato dal costo previsto, e la policy manuale di stop; senza hard cap provider non si promette che il costo non eccedera' la cifra;
2. verificare la quota/provider, l'accesso al modello e i listini al momento della richiesta;
3. verificare final HEAD clean, 29 source SHA, SDK pinned, gate di usage/ledger/single writer;
4. costruire release create-only con SHA canonico approvato dall'utente separatamente dal commit;
5. richiedere **ulteriore consenso esplicito per l'esatto singolo D**, senza autorizzazione per C, K o altri 179 stage.

`LIVE_API_ENABLED=False`, RQ2-V2 `0/180` API stage, 11 OOD LOCKED, RQ1 frozen. Nessuna chiamata provider o file scientifico creato con questo memo.
