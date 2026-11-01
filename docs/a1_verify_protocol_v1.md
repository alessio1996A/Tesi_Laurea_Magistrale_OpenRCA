# Protocollo sperimentale A1_VERIFY v1 — prima integrazione LangGraph

**Stato:** implementazione con test sintetici *non ancora eseguiti in
PyCharm*. Nessuna chiamata Gemini e nessun esperimento OpenRCA lanciato
dalla creazione di questa variante.

## Motivazione e provenienza

La simulazione offline sul caso storico e gia' esplorato
`cloudbed-2_q006` ha restituito SHA-256 delle evidenze coerente,
4 candidati senza precedente controllo mirato, e 2 proposte con budget
ipotetico `max_checks=2`, `remaining_rounds=2`:
- R01, `node-5.adservice-2`, container metrics;
- R10, `node-5`, node metrics, KPI `system.io.w_s`.

La scelta di `adservice-2` e' conseguenza dell'ordinamento della
policy, non evidenza di causalita' superiore rispetto a `frontend-0`.
q006/q040 NON sono una validazione indipendente della policy.

## Isolamento delle varianti

Nuova variante `A1_VERIFY` in `ExperimentConfig`.

- `A0`: invariato.
- `A1_V2`: invariato.
- `A1`: invariato.
- `A1_VERIFY`: il report e le otto regole sono gli stessi di A1,
  e il prompt di sistema di base resta comune. Il nuovo grafo e'
  implementato in `src/agent/verify_graph.py`, distinto da
  `src/agent/graph_engine.py`.

`output_contract_mode` resta impostato per default su `legacy`;
`structured` e `audit` sono opzioni di output separate. La
finalizzazione strutturata, se abilitata, aggiunge una chiamata LLM
oltre a quelle gia' conteggiate.

## Sequenza del nuovo grafo

1. **Agente** esplora con LLM e i cinque tool consueti.
2. L'esplorazione termina quando il modello non richiede altri tool
   oppure raggiunge la quota riservata.
3. **Planner** legge il report A1 e la traiettoria di chiamate
   effettivamente emesse; propone controlli di metriche mirati.
4. **Verifica** emette una chiamata *deterministica* a ToolNode per
   ogni controllo proposto. NON e' una chiamata LLM.
5. **Finale** riceve report, istruzione originale e osservazioni dei
   tool, con il richiamo che una correlazione non dimostra causalita';
   il modello puo' produrre una sola risposta senza nuovi tool.
6. **Executor** registra chiamate LLM, chiamate tool, round esplorativi,
   round di verifica, token disponibili, errori e traiettoria.

## Budget e costi

`max_tool_rounds=6` e `max_verification_checks=2` per default:

- al massimo 4 round esplorativi dell'LLM;
- fino a 2 round di verifica *di un tool ciascuno*;
- totale massimo 6 round con tool, come nel budget storico;
- il modello puo' effettuare piu' chiamate tool nello stesso round
  esplorativo, come nella variante preesistente;
- un'ulteriore chiamata LLM finale e' sempre effettuata, anche se
  l'agente aveva prodotto una risposta provvisoria senza tool;
- non c'e' retry implicito o fallback ad output inventati.

Il budget dei round non impone identico numero di token o costo.
Occorre confrontare `llm_calls`, `tool_calls`,
`total_tokens`, `duration_seconds` e il flag
`token_usage_complete`. Un uso token incompleto va riportato, non
interpretato come costo nullo. La policy potrebbe ridurre lo spazio
di esplorazione libera senza alcun beneficio: e' un'ipotesi
sperimentale, non un miglioramento garantito.

Il risultato su file, quando `salva=True`, usa il prefisso
`a1_verify_unified_` e la modalita' esclusiva `open("x")`:
non sovrascrive A1/A0 o i risultati storici.

## Limiti metodologici

- Solo le classi delle otto regole vengono pianificate; l'assenza di
  un candidato NON significa che la causa sia assente.
- Il controllo mirato verifica la disponibilita' di osservazioni, non
  certifica meccanismi causali. `causa_verificata=False`.
- Un tool puo' restituire informazioni incomplete o errori; questi
  vengono inoltrati al modello senza essere trasformati in conferme.
- Il contesto finale puo' essere troncato se la traiettoria e' lunga;
  l'implementazione lo segnala.
- Il planner usa una politica di copertura equa per livello e
  componente, non una stima di probabilita' causale.
- Non e' implementata una verifica completa di propagazione service
  graph. Nessuna topologia e' inventata.
- Nessuna lettura delle etichette evaluation/OOD o apprendimento
  automatico delle nuove regole e' consentito.
- I test offline dimostrano proprieta' software: non un vantaggio
  sul benchmark.

## Test e introduzione progressiva

1. Eseguire l'intera suite con `unittest discover`.
2. Riprodurre il report deterministicamente e confermarne lo SHA
   invariato (test senza API) su casi gia' esplorati.
3. Scegliere un sottoinsieme development non usato durante la
   progettazione e definire la comparazione *prima* della prima
   chiamata LLM su quei casi.
4. Eseguire A1 e A1_VERIFY con stessi provider, modello e limiti
   di round, esplicitando la diversa allocazione del budget.
5. Solo dopo congelamento del protocollo valutare le predizioni
   con scorer ufficiale; conservare trace, costi, errori e run ID.
6. Trattare evaluation e OOD come holdout non osservati fino
   all'ultima fase sperimentale.
