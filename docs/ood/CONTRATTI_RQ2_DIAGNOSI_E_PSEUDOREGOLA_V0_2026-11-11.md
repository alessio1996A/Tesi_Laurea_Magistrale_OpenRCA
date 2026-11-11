# RQ2 — Contratti di diagnosi e pseudoregola, proposta V0

**Stato:** progettazione, NON freeze e NON autorizzazione a inferenze.  
**Data:** 11 novembre 2026.  
**Relazione:** `PROTOCOLLO_RQ2_BOZZA_V0_2026-11-11.md`, anteprima V1 in `REPORT_ANTEPRIMA_PARTIZIONE_RQ2_V1_2026-11-11.md`.

## 1. Perché separare gli output

La risposta al **task OpenRCA originale** deve restare quella prodotta dallo stesso runner e con lo stesso contratto RQ1, conservata **grezza** e valutata solo dopo il freeze tramite lo scorer Microsoft. Sette dei 15 task OOD non chiedono esplicitamente `reason`; non si può quindi usare il risultato Microsoft come unica misura della capacità di diagnosticare la **classe**.

**D (diagnosi RCA originale):** run originale senza alcuna modifica al task per uniformare la classe. Output grezzo e traiettoria salvati in create-only.

**C (probe causa uniforme):** chiamata aggiuntiva **senza tool**, basata esclusivamente su istruzione originale e **bundle deterministico della telemetria effettivamente osservata in D**. Vietati `record.csv`, `query.scoring_points`, report di scoring, file d'inventario GT, split labels, motivazione della scelta del caso e liste delle quattro etichette OOD. Non suggerire che la risposta debba appartenere a una delle quattro classi. Stessa procedura per A1 e A1_8R e per i provider, a parità di evidenze disponibili per ciascuna run.

**K (pseudoregola):** solo sulle **quattro discovery**, dopo C, con ingresso derivato dalle sole evidenze/diagnosi C e senza score; mai sulle undici test. Può dichiarare `insufficient_evidence` anziché inventare soglie. Nessuna esecuzione di codice LLM.

Lo schema è volutamente una proposta **task-agnostic**, non un aggiornamento del contratto OpenRCA; il validatore verifica struttura e coerenza locale, **non** correttezza RCA né attendibilità delle evidenze.

## 2. Riferimenti alle evidenze

Il runner futuro deve costruire un *evidence bundle* deterministico, dai messaggi dei tool realmente eseguiti: identificatori `E001`, `E002`, ... associati in modo stabile al singolo run, con sorgente/tool, parametri, intervallo temporale, unità e contenuto osservato/troncamento dichiarato. Bundle ricostruibile da log salvati, **senza** GT.

La probe C e K possono solo citare ID presenti nel bundle. Un ID inventato è errore del contratto. **Il validatore offline usa una allowlist di ID** passata esplicitamente; non legge telemetria né GT e non decide se le evidenze sostengano davvero la causa. La valutazione del *grounding* va fatta separatamente.

Prima di congelare RQ2 vanno fissati algoritmo e limiti di dimensione del bundle, disponibilità delle osservazioni, temperatura, limiti output e formato di prompt per provider. Non si deve inventare un bundle da una risposta del modello quando i tool non hanno prodotto segnali.

## 3. Contratto C — `rq2_cause_probe_v0`

Top-level JSON (esattamente queste chiavi, nessun wrapper Markdown):

```json
{
  "schema_version": "rq2_cause_probe_v0",
  "decision": "diagnosis",
  "predicted_fault_type": "categoria tecnica in testo libero, non dalla lista OOD",
  "predicted_component": "componente ipotizzato o null",
  "confidence": "low",
  "evidence_ids": ["E001"],
  "alternatives": ["ipotesi alternativa e motivo della preferenza"],
  "limitations": ["limite delle osservazioni, non certezza causale"]
}
```

- `decision`: `diagnosis` oppure `abstain`.
- Se `diagnosis`: `predicted_fault_type` stringa non vuota; almeno un `evidence_ids` presente nel bundle. `predicted_component` è stringa o `null`.
- Se `abstain`: `predicted_fault_type=null`, `predicted_component=null`, `evidence_ids` può essere vuoto; almeno una `limitations` che motivi l'astensione.
- `confidence`: `low|medium|high|unassessed`; dichiarazione soggettiva del modello, **non** probabilità calibrata.
- `alternatives`, `limitations` sono liste di testo, possono essere vuote solo in diagnosi; non rappresentano verifiche già eseguite.

La normalizzazione delle classi per l'accuratezza va definita **nel solo scorer offline** e congelata prima delle inferenze; il validatore strutturale NON contiene le quattro etichette ufficiali.

## 4. Contratto K — `rq2_candidate_rule_v0`

Top-level JSON (nessun codice eseguibile):

```json
{
  "schema_version": "rq2_candidate_rule_v0",
  "status": "candidate",
  "hypothesized_fault_type": "categoria ipotizzata",
  "rule_name": "nome tecnico candidato",
  "scope": "node oppure container e precondizioni",
  "evidence_ids": ["E001"],
  "required_signals": [
    {"metric": "nome esatto disponibile", "unit": "unita", "aggregation": "max", "window_seconds": 300}
  ],
  "conditions": [
    {"metric": "nome esatto disponibile", "operator": ">", "threshold": 1.0, "unit": "unita", "aggregation": "max", "window_seconds": 300}
  ],
  "combination": "all",
  "abstain_when": ["assenza della metrica o finestra incompleta"],
  "counterexamples": ["un evento confondente da distinguere"],
  "limitations": ["non validata su incidenti indipendenti"],
  "pseudocode": "SE metrica_max_5min > 1.0 ALLORA segnale_candidato"
}
```

- `status`: `candidate` oppure `insufficient_evidence`.
- Per `candidate`: tipo e nome regola non vuoti, almeno un riferimento evidenza, almeno una metrica e condizione misurabile, unità/aggregazione/finestra coerenti fra `required_signals` e `conditions`; almeno un caso di astensione, controesempio e limitazione. `combination` solo `all|any`. Operatori solo `>,>=,<,<=,==`; `threshold` numerico finito, **non** `bool`. Finestre intere positive. Le metriche devono appartenere a un catalogo osservabile con la telemetria effettiva, da fissare prima del freeze.
- Per `insufficient_evidence`: `hypothesized_fault_type` e `rule_name` possono essere `null`, `required_signals=[]`, `conditions=[]`, `pseudocode=null`, e una limitazione/astensione che giustifichi l'insufficienza. Non ripetere la chiamata suggerendo l'etichetta GT.
- Tutte le stringhe sono **solo dati**, non comandi. Non usare `eval`, `exec` o AST dinamico sul pseudocode. Traduzione in detector deterministicamente controllato solo dopo audit e freeze della proposta, senza consultare il test.
- Un candidato valido strutturalmente non è automaticamente corretto, causalmente verificato, implementabile né generalizzabile.

## 5. Metodi e metriche proposte

**RQ2-A:** esattezza di `predicted_fault_type` a livello query, per test e per fase; astensioni, output invalidi, errori provider a parte. I modelli non ricevono target labels. Scoring ufficiale Microsoft solo sul D grezzo e separato. A1 vs A1_8R appaiati per caso/modello; l'unità di incertezza per la coppia multi-fault è il gruppo temporale.

**RQ2-B:** validità del contratto K, supporto delle affermazioni tramite evidence IDs e metriche reali, falsificabilità, indipendenza dalla GT, implementabilità, astensioni e controesempi. Non assegnare un voto unico prima di approvare griglia e procedura di valutazione; eventuali valutatori indipendenti devono usare rubriche fisse.

**RQ2-C:** dopo congelamento di candidati e implementazioni offline, test su gruppi mai visti, con negativi a livello di finestra **considerando tutte le classi presenti**; evitare che una finestra con un guasto target sia usata come negativo per quello stesso target. Indicare TP/FP/TN/FN e non valutabili con denominatori; `container write I/O load` non ha al momento una coorte cross-cloudbed.

## 6. Cosa il codice può verificare ora e cosa resta da definire

Implementazione senza provider `src/evaluation/rq2_output_contracts.py`: parser JSON stretto e validazione strutturale per C/K senza imporre etichette. Test sintetici in `src/tests/test_rq2_output_contracts.py`. **Questi artefatti non importano runner LLM o GT**.

Ancora **aperti**: costruzione bundle evidenze, prompt C/K specifici, set dei nomi delle metriche realmente disponibili, adattatori provider e token budget, selezione ex ante della regola principale tra 24 candidati teorici, scoring classi con alias preregistrati e valutazione dei negativi multi-fault. Non è stato definito un protocollo operativo congelato. Zero API.
