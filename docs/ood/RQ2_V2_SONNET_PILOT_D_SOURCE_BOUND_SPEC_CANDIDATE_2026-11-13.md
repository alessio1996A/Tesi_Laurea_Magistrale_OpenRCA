# RQ2-V2 — Specifica candidata pilot Sonnet D autentico, NO API

**Data:** 13 novembre 2026
**Repo:** `alessio1996A/Tesi_Laurea_Magistrale_OpenRCA`
**Branch engineering:** `experiment/rq2-provenance-v2-offline-2026-11-13`
**Stato:** `SCIENTIFIC_PILOT_CANDIDATE_NOT_RELEASED`.
**Questo file NON autorizza alcuna chiamata provider né alcuna scrittura nei risultati V1.**

## Perché fare questo pilot

Nella V1, tre D reali Sonnet sono `INVALID_OUTPUT` per
`AMBIGUOUS_TOOL_RESULT`, pur avendo JSON D valido;
la `tool_trajectory` del runner V1 non conservava
`tool_call_id` e non poteva associare senza ambiguità
call/result paralleli allo stesso tool.

Il ramo V2 preserva l'ID autentico dei messaggi
`AIMessage.tool_calls[].id` e `ToolMessage.tool_call_id`
e ha superato test sintetici/di regressione
(ultima suite globale osservata: **852/852**).
Questo dimostra compatibilità software, non il
comportamento di un provider remoto reale.

Il pilot deve rispondere **solo** alla domanda tecnica:
«Su una D reale, i tool-call ID sono conservati e il bundle
osservativo resta verificabile senza rilassare il validatore?»

## Identità candidata, UNA sola D

| Campo | Valore candidato |
|---|---|
| Provider | Anthropic |
| Modello logical | `sonnet` |
| Modello esatto candidato | `claude-sonnet-5-5` |
| Caso | `cloudbed-1_q050` — **discovery**, non OOD test |
| Harness | `A1` |
| Stage | `D` soltanto |
| Protocollo | Nuovo V2 scientifico (ID **da congelare**, distinto dalla bozza e da V1) |
| Archivio | `data/rq2_v2_provenance/` sul Drive, namespace V2 create-only |
| Esecutore | `src/agent/rq2_v2_graph_engine.py`, non il solo runner legacy |
| Task JSON D | `v2_enforce` |
| Budget harness | `max_tool_rounds=6`, `recursion_limit=30`, nessuna estensione implicita |
| Fase C/K | **NON autorizzate da questo pilot** |
| OOD test / GT | **LOCKED**, niente scorer o labels nel runtime |
| Retry stage | **Nessuno**; errore/crash = claim persistente e audit manuale |

### Perché proprio q050/A1

Il precedente tentativo V1 su questo stesso arm
ha incontrato tool call parallele omonime e
`AMBIGUOUS_TOOL_RESULT`. Il caso è adatto come
**pilot tecnico mirato a un limite già noto**,
non come replica indipendente, non come misura
unbiased della percentuale di errori reali.
Non è lecito correggere retroattivamente il
record V1 né riusare il suo claim per il V2.

## Invarianti che il nuovo codice reale deve soddisfare

1. **Repository/runner invariati per V1/RQ1.**
   Branch V2 additive: introdurre un entrypoint separato
   e documentare il richiamo all'esecutore V2, non
   modificare `src/agent/graph_engine.py`,
   `src/evaluation/experiment_runner.py` o
   i file sperimentali congelati.
2. **Source binding reale:** prima del claim
   leggere e verificare in modalità GT-free
   `data/processed/split_market_v1.csv` e
   `data/processed/benchmark_inputs_market.csv`
   contro gli hash congelati:
   - split `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`;
   - manifest `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`;
   - `preview_market` e `RQ2StageArtifactStore` V1
     forniscono riferimenti di schema e controlli, ma
     **non devono essere usati per scrivere V2**.
3. **Release V2 specifica e create-only:** ID protocollo,
   model/provider/runtime exact pin, tool/prompt output,
   code SHA, source hashes, schema claim/record,
   ordine e singolo `stage_id`, denominatore 1/1
   e policy errore. La bozza
   `rq2_knowledge_transfer_provenance_v2_draft`
   **non** basta a liberare provider.
4. **New source-bound journal/store:** V2 produce claim
   `O_EXCL` *prima* della prima richiesta al provider
   e risultato create-only dopo; conserva input
   identificativi, output/raw/usage/tool trajectory,
   hashes di provenance e status onesto.
   Mai leggere/scrivere/reinterpretare i 39
   artefatti V1 durante la run V2, salvo un
   audit V1 separato e read-only.
5. **Fail-closed:** se ID mancante/incoerente, JSON
   invalido, crash, timeout o provider error,
   non indovinare il match, non riparare output,
   non fare retry automatico, non sostituire
   con successo un risultato tecnico ambiguo.
6. **Nessun claim "complete" se lo storage è invalido.**
   Dopo la prova, readback hash di claim/record,
   verifica `tool_call_id`, evidenze, json_status
   e metadati token/costi/latency. `RECORDED_COMPLETE`
   significa **integrità tecnica**, NON correttezza RCA.
7. **Budget e runtime:** in `rq2_model_factory.py`
   Anthropic proposto `max_retries=0`,
   `max_tokens=4096`, `timeout=300s`
   **per chiamata singola**. Una D può generare
   varie richieste HTTP. Prima del pilot verificare
   ancora la versione del client, le API compatibili,
   limiti reali, pricing e un criterio di arresto
   finanziario/operativo esplicito.
8. **No parallelismo** con altri notebook; Colab
   in nuova directory `/content`, nessuna
   sovrascrittura della V1 su Drive.
9. **Test OOD chiusi.** Non aprire la coorte test
   per testare la correzione engineering o scegliere
   la "migliore" K.

## Esito tecnico e interpretazione

| Risultato possibile | Interpretazione |
|---|---|
| D registra call/result con ID validi e bundle non ambiguo | Successo della provenance **su questo pilot** |
| Provider non genera tool call omonime parallele | Flow autentico ok, ma **il caso ambiguo non è stato riprodotto** |
| ID assenti o mismatch / invalid bundle | Fallimento tecnico V2 reale da conservare |
| JSON D invalido ma bundle valido | Distinguere disponibilità evidenze da validità diagnosi JSON; seguire status preregistrato |
| Errore provider / crash / claim orfano | Fallimento/claim unresolved, STOP e audit manuale |

**Non si imputa a V2 un miglioramento accuracy perché
la D V1 era stata invalidata per provenance.**
Una D reale non dimostra che K si trasferisca a
nuove classi di guasto.

## Gate prima di passare da bozza a codice live

- [x] Gemini V1 audit reale GT-free: 24/24, 22 complete,
  1 invalid e 1 blocked; **2 K candidate da verificare,
  5 insufficient e 1 K blocked**, zero K frozen.
- [x] Suite V2 corrente: 852/852 test automatici
  superati in PyCharm, di cui pilot fake end-to-end.
- [ ] Implementare store/journal **V2 source-bound reale**,
  distinti dal synthetic-only e dai path V1.
- [ ] Coprire con test offline endpoint V2 di D con
  vero runner+fake LLM, source pin, claim/restart,
  no retry, invalid bundle, no write ai dati V1.
- [ ] Pin/release V2 sullo stesso commit e runtime
  Colab verificato, status `approved_for_one_pilot`
  con un solo stage consentito.
- [ ] Verifica costo/stima e autorizzazione
  esplicita di spesa/one shot (utente).
- [ ] **Solo allora** eseguire una singola D live.

## Dopo il pilot

Se positiva la provenance reale, decidere
quanto della discovery Sonnet/Haiku svolgere
in V2, senza aggregare come un unico esperimento
comparabile Gemini V1 e Anthropic V2.
Le 2 K Gemini richiedono prima una verifica
di formalizzabilità GT-free, e il test OOD
rimane bloccato fino al freeze indipendente.

**Obiettivo di progetto:** completare esperimenti
scientifici → refactoring/italianizzazione/pulizia
→ scrittura tesi entro il 1 dicembre 2026.
