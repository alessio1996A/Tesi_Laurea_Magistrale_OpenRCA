# Claude 5.5: correzione del contenuto strutturato e protocollo V3 (2026-11-05)

## Risultati immutabili delle campagne precedenti

V1:
- Piano SHA-256: fb828dfcd7f2ac9e07b6d916ffd51e61b6a23052c1edbf7a06e965acb5a26158
- Commit Git: 63a046723165976558840a30efb1b5097ad3fdf7
- Primo tentativo Sonnet A0 cloudbed-1_q005: CLAIM_PENDING_NO_AUTO_RETRY;
  claim presente, output e sidecar assenti. Interruzione KeyboardInterrupt
  in ToolNode. NON ripetere né cancellare il run_id V1.

V2:
- Piano SHA-256: 33c6f4f20f6d0462d215c83e6ae81c8344ba4332937801fae4ce98d5ba10cd7b
- Commit Git: e2229ce3a33c37f2066c842332c34b8ff7624e28
- Audit parità tool vecchio/nuovo: d24a8e6fd3d6e48e052f17f70bbb8948b0922c0cdb3d877053a98d9d2a6a64cd
- Prima run Sonnet A0 cloudbed-1_q005: completata infrastrutturalmente,
  JSON invalid_v2_task_output, "JSON non analizzabile"; nessuna predizione
  registrata nel campo prediction. Output SHA-256:
  fe639ca801d82111e23b0928b4dd48828f4533311a9439475e7e54b44eef6a1f.
  7 llm_calls, 6 round, 13 tool calls, input_tokens 141065,
  output_tokens 2784, durata 226.846 s. Queste sono metriche di esecuzione,
  NON di accuratezza e NON garantiscono completezza del costo API.
- 39 Sonnet ancora ready, 40 Haiku ready, zero scoring.

## Root cause tecnico identificato

In src/agent/graph_engine.py al commit V2, la funzione testo_messaggio()
gestiva AIMessage.content come lista di blocchi. Per i blocchi
dizionario senza campo "text" eseguiva str(elemento), concatenandoli
alla risposta. Anthropic puo' restituire un blocco thinking con
signature (metadati del protocollo di ragionamento) seguito da un
blocco text con il JSON diagnostico.

La risposta V2 originale inizia con la rappresentazione Python
"{'signature': ..." e prosegue con contenuto che assomiglia al JSON
finale. json.loads() non puo' analizzare l'intera stringa.
Non e' quindi scientificamente corretto attribuire automaticamente
l'invalidita' sintattica alla sola generazione del modello: il parser
del nostro harness ha contaminato il contenuto finale.

L'archivio originale V2 NON deve essere modificato. Un'eventuale
ricostruzione offline del campo text dal raw_response e' esclusivamente
un *audit secondario*, NON la predizione V2 registrata. Non si applicano
riparazioni ad hoc a mano o tentativi nascosti.

## Correzione del protocollo V3

Nuovo branch feature/claude-content-block-v3-2026-11-05, derivato dal
commit V2 e2229ce3a33c37f2066c842332c34b8ff7624e28.

- src/agent/graph_engine.py: testo_messaggio(contenuto, solo_testo=True)
  prende solo blocchi di contenuto testuale dalle risposte AI;
  i blocchi thinking/signature, tool_use, redacted_thinking e blocchi
  opachi non diventano testo diagnostico.
- src/agent/verify_graph.py: stessa estrazione per la finalizzazione
  con planner e PAVE, e controllo di risposta vuota.
- Default storico di testo_messaggio(contenuto) preservato per
  tool observations. Non cambiano originali AIMessage passati al
  modello, tool, politiche del planner, prompt RCA, contratto OpenRCA,
  max_tokens, impostazioni del provider e limiti dei round.
- src/tests/test_anthropic_content_block_extraction.py:
  regressioni offline sui blocchi, firme sintetiche, controllo
  finale JSON e integrazione con grafo fittizio senza API.
- src/tests/test_claude_development_campaign.py:
  regressioni sulla non alterazione dei file V1 e V2.

## Campagna nuova (nessun riutilizzo dati precedenti)

Protocollo: openrca_claude_five_agents_development_v3.
Piano create-only distinto su Drive:
data/protocols/v2/openrca_claude_five_agents_development_v3_plan_v1.json
Risultati create-only distinti:
data/results/v2/openrca_claude_five_agents_development_v3/

8 incidenti GT-free congelati, 5 varianti, 2 modelli;
40 run Sonnet, 40 Haiku, ordine preregistrato come V3 Gemini.
Budget A0/A1/R8=6 tool round; Planning/PAVE=4 esplorazione+2 verifica.
Questi nuovi 80 run_id non collidono con V1 o V2.
Le diagnosi V1/V2 non sono integrate come risultati V3.

## Condizioni prima di autorizzare la prossima API

1. Clonare checkout V3 separato su Colab. Mai fare git pull nelle
   directory congelate V1 o V2.
2. Verificare i piani e il risultato V2 via SHA, solo lettura.
3. Eseguire tutti gli unittest V3 offline, compreso fake Claude,
   per verificare che il JSON finale escluda thinking/signature.
4. Facoltativo: ispezione della stringa raw_response V2 per distinguere
   contenuto del modello da metadati; il risultato originale resta
   invariato e l'audit non viene trasformato in predizione.
5. Creare il piano V3 *solo* dopo esito positivo delle verifiche.
6. Nuova autorizzazione per una singola chiamata pilota Sonnet A0 V3.
   Retry automatici disattivati; claim create-only scritto prima API.
7. Dopo la run, verificare integrita', output_contract_v2.valid,
   metriche e SHA prima di considerare altri run.
8. Solo dopo 40 run e freeze, usare lo scorer ufficiale, senza
   passare la ground truth alle chiamate LLM.

Il primo output V2 invalid JSON e' un esito infrastrutturale;
NON equivale a errore RCA del modello e NON deve essere inserito
come zero d'accuratezza V3.

## Rischi residui e limiti

La fix migliora l'estrazione dei blocchi in modo deterministico.
Non garantisce che Claude generi sempre JSON valido o che la
diagnosi sia corretta. Il caso V2 mostrava un segmento finale
simile a JSON, ma solo un parser offline puo' stabilirne la
conformita' del task; nessuna interpretazione di questa stringa
cambia gli artefatti storici.
