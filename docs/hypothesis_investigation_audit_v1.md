# Audit delle ipotesi alternative e della copertura dell'indagine — v1

## Provenienza

Questo controllo nasce dal confronto ESPLORATIVO e gia' ispezionato dei
casi `cloudbed-1_q040` e `cloudbed-2_q006`. Non si possono utilizzare
come conferma indipendente di efficacia o per imparare nuove regole.
I report deterministici originali sono stati ricostruiti senza differenze
SHA-256. Nessun nuovo punteggio di OpenRCA e' attribuito a questo audit.

- q040: un candidato, diagnosi osservativamente coerente; nessuna coppia
  nodo/container da confrontare.
- q006: quattro candidati; due diagnosi finali senza corrispondenza
  lessicale esatta componente+classe; output con reason composte.
  Questo NON significa automaticamente assenza di evidenza: la diagnosi
  su node-5 e il candidato R10 condividono il componente, ma non la classe
  espressa con l'etichetta canonica.

## Modulo indipendente

`src/harness/hypothesis_coverage_audit.py` espone
`verifica_copertura_ipotesi(diagnosis, evidence_report, tool_trajectory)`.

Input esclusivamente:
1. `Diagnosis` ottenuta dalla predizione originale;
2. il report A1-R8 gia' creato deterministicamente dall'harness;
3. la traiettoria di chiamate ai tool salvata nel medesimo esperimento.

Il modulo distingue per ogni candidato riportato:
- **componente e classe canonica ripresi** nella diagnosi;
- **componente ripreso con reason non canonica**; una descrizione composta
  non viene convertita arbitrariamente in una delle otto classi;
- **candidato non ripreso** nella diagnosi finale.

Se `frontend-0` compare in candidati di host distinti, il confronto
per suffisso e' ambiguo e non viene promosso a corrispondenza.

Per indagine mirata, il modulo cerca chiamate effettivamente **registrate**
al tool di metriche per il livello del candidato e con `cmdb_id`
**esattamente** uguale all'identificativo in telemetria:
- R01, R02 e R06 -> `tool_get_container_metrics`;
- R07, R08, R09, R10, R11 -> `tool_get_node_metrics`.

Chiamate generiche allo stesso tool (senza `cmdb_id`) sono descritte
separatamente; log, tracce e metriche di servizio non costituiscono
una prova di controllo mirato del KPI nodo/container. Anche una chiamata
con `cmdb_id` corretto NON dimostra che il KPI sia stato restituito,
interpretato o che l'ipotesi sia causale.

Non vengono consultati gli output dei tool per inferire se un dato sia
stato effettivamente analizzato dall'LLM. E' quindi un audit di
**azioni documentate e diagnosi finale**, NON una misura della
completezza cognitiva dell'indagine.

## Output e limiti

- `candidati_ripresi_stessa_classe` e
  `candidati_con_metriche_mirate` sono **conteggi descrittivi**,
  non precision, recall, accuracy o verification score.
- `candidati_omessi_per_budget` limita la copertura osservabile.
- Il report delle regole era gia' nel prompt A1: non effettuare una
  chiamata mirata non significa che l'agente non abbia mai visto il
  candidato o la telemetria.
- La componente e la classe possono coincidere casualmente; anche in
  presenza di strumenti mirati, `causa_verificata=False`.
- L'audit non rilegge la ground truth, non aggiorna regole, non
  modifica risposte e non chiama Gemini.

## Roadmap di integrazione LangGraph

Non modificare il runner e le varianti A0/A1/A1_V2 storiche sulla base
di due casi esplorati. Prima creare una nuova variante **predefinita** di
protocollo di verifica, con:
1. rilevazione delle ipotesi alternative dai candidati osservativi;
2. policy esplicita e limitata che richieda controllo mirato delle
   ipotesi plausibili ancora non esaminate, se il budget lo consente;
3. output strutturato e registro motivato delle ipotesi confermate
   osservativamente, contraddette o non determinabili;
4. budget totale delle chiamate e dei token equivalente o almeno
   dichiarato rispetto alla baseline;
5. test su development NON usato per progettare la policy;
6. confronto ufficiale dopo congelamento del protocollo.

Da NON implementare prima che la policy sia chiaramente specificata:
correzione automatica della diagnosi in base alla prima anomalia,
promozione di regole per risposte corrette ai casi ispezionati, accesso
alle etichette OOD/evaluation, dichiarazioni di causalita' dimostrata.
