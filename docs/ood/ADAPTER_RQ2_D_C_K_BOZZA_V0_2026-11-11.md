# RQ2 — Adapter offline D → C / K, bozza V0

**Data:** 11 novembre 2026  
**Stato:** nuova implementazione e 14 test sintetici *predisposti, non ancora eseguiti in PyCharm dall'utente*. **Non** è un runner eseguibile, né autorizza chiamate API. Protocollo generale e partizione V1 ancora **non congelati**.

## 1. Perché un adapter separato?

La diagnosi OpenRCA originale è la fase **D** e deve preservare integralmente `raw_response`, metriche, errori e traiettoria. La fase **C** raccoglie una diagnosi standardizzata della classe OOD anche quando il task originale chiede solo tempo/componente. La fase **K** richiede una pseudoregola solo per i gruppi **discovery**, prima di utilizzare il test.

L'architettura storica `src/agent/graph_engine.py` restituisce `raw_response`, `metrics`, `tool_trajectory`, `error`. I log di `tool_trajectory` non contengono `tool_call_id` per A0/A1/A1_8R, a differenza del ramo `src/agent/verify_graph.py`. Il modulo già preparato `src/evaluation/rq2_evidence_bundle.py` costruisce evidenze `E001...` **solo quando le associazioni call-result sono non ambigue**, altrimenti interrompe. **14 test sintetici di questo modulo superati in PyCharm** secondo l'utente: `Ran 14 tests in 0.009s — OK`.

Il nuovo modulo `src/evaluation/rq2_probe_adapter.py` **non modifica** il grafo storico, non legge file né ground truth, non avvia provider, non gestisce costi o retries, non scrive output. È un **preparatore offline di messaggi**, da integrare con un *nuovo* runner RQ2 verificato successivamente.

## 2. Funzioni e comportamenti

### `prepare_cause_probe(original_instruction, diagnostic_run, allowed_tool_names)`

Richiede istruzione originale priva di GT, output D con `tool_trajectory` e `error=None`, allowlist esplicita dei tool di telemetria. Estrae il bundle deterministico, crea messaggi `system` e `user` per C, registra versioni/hash di bundle, traiettoria e prompt. **Non passa la risposta grezza D alla probe C**, per evitare che la diagnosi del task originale induca un anchoring della causa; `raw_response` rimane tuttavia preservata nel log D originale e valutabile con Microsoft separatamente.

Il prompt fisso non elenca le quattro classi riservate; richiede il contratto `rq2_cause_probe_v0`, alternative, limiti ed eventuale astensione. I log/trace sono qualificati *dati, mai istruzioni*; la sola frase nel prompt **non garantisce** robustezza completa contro prompt injection.

Se non sono stati raccolti tool result, C può essere costruita con bundle vuoto, ma la diagnosi con `evidence_ids` non potrà passare il validatore: deve astenersi (o risultare non conforme). Se D è in errore, la probe non viene costruita e lo stato del fallimento resta distinto dall'accuratezza.

### `prepare_candidate_rule(original_instruction, diagnostic_run, cause_raw_json, phase, allowed_tool_names)`

Disponibile **solo quando `phase="discovery"`**, e soltanto se la risposta C è JSON conforme, con evidence IDs presenti nel bundle D. Il prompt K riceve il bundle e la **diagnosi ipotizzata dal modello**, dichiarata esplicitamente non verificata, mai la risposta GT. Anche in caso di astensione C, K può rispondere `insufficient_evidence`.

**Protezione ancora necessaria prima del runner:** il parametro `phase` è una dichiarazione del chiamante, non una prova crittografica né una consultazione del piano congelato. Il futuro runner RQ2 dovrà controllare che il `case_id` sia effettivamente nella lista discovery del **manifest verificato e congelato**, senza accedere a label di classe.

### Tracciabilità

L'adapter produce `adapter_version=rq2_prompt_adapter_v0`, `stage`, `bundle_sha256`, `trajectory_sha256`, `system_prompt_sha256`, `package_sha256` e due messaggi serializzabili, marcati **`model_api_calls=0` e `ready_for_api=false`**. Un futuro runner dovrà verificare e congelare i payload, registrarne l'uso, ed evitare di attribuire erroneamente un consumo di token alle chiamate di sola preparazione.

## 3. Test sintetici preparati

File `src/tests/test_rq2_probe_adapter.py`: **14 casi** per: determinismo, esclusione `raw_response` originale, K limitata a discovery, validazione dell'output C, errori provider, provenienza ambigua dei risultati legacy, bundle vuoto/astensione, contenuto GT accidentale, segregazione di testo ostile nell'input dati, tool non autorizzati, hash di payload e assenza di campi di stato.

**Non sono ancora stati eseguiti dall'utente**, quindi NON presentarli come verificati.

## 4. Verifiche mancanti prima di congelare RQ2

1. Eseguire i 14 test sintetici PyCharm del nuovo adapter.
2. Verificare la compatibilità con esempi **reali GT-free** delle traiettorie storiche e la vera allowlist dei cinque tool, prima di pilot sui casi OOD.
3. Per le chiamate parallele legacy con lo stesso tool, decidere se introdurre `tool_call_id` in un nuovo runner dedicato RQ2 **oppure** registrare probe non disponibile. Mai accoppiare risultati per supposizione.
4. Completare integrità create-only del nuovo runner, separazione D/C/K, gestione errori, provider adapter, costi e budget; controllare `phase` con manifest indipendente e bloccare **K su test**.
5. Stabilire standard di scoring della classe, alias di cause normalizzati, KPI verificabili per K, negativi multi-fault, eventuale estensione, regola principale ex ante, prompt/bundle e freeze completo. Solo dopo autorizzazione esplicita si potranno chiamare Gemini/Claude.

**Senza GT nel prompt non significa automaticamente che la regola sia corretta:** i detector R8 possono fornire segnali osservativi fallibili; le pseudoregole possono essere impossibili da verificare su telemetria disponibile. Lo studio rimane esplorativo con 4 discovery/11 test (partizione V1 ancora candidata).
