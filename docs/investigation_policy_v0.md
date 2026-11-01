# Policy proposta di verifica mirata v0 — prototipo offline

## Problema che motiva il lavoro

L'audit retrospettivo sui casi *gia' esplorati* q040/q006 ha
riprodotto esattamente lo SHA-256 delle evidenze storiche.

Per q006:
- 4 candidati osservativi A1-R8 disponibili;
- 0 ipotesi riprese con nome componente **e** reason canonica;
- 0 chiamate ai tool di metriche **mirate al cmdb_id** documentate;
- il componente node-5 e' comparso nella diagnosi finale, ma con una
  reason composta che non coincide con la classe canonica R10.

Questi risultati **non provano** che l'LLM non abbia visto le evidenze:
esse erano contenute nel prompt. Non dimostrano neppure che una delle
4 ipotesi fosse una root cause. Il caso e' contaminato da analisi
esplorative e NON va usato per stimare un miglioramento.

## Contratto del planner

File `src/harness/investigation_planner.py`.
Funzione `pianifica_verifiche_mirate(evidence_report, tool_trajectory,
start_unix=..., end_unix=..., max_checks=..., remaining_rounds=...)`.

Questo e' un **piano**, non un nodo del grafo e NON esegue gli strumenti.

1. Riceve solo report di telemetria deterministico A1-R8 e tool
   trajectory dell'esplorazione in corso, piu' budget e finestra del caso.
2. Esamina i candidati `candidati_riportati`; segnala i candidati omessi
   dal budget del report, che non possono essere recuperati dal planner.
3. Considera gia' interrogato un candidato solo se la traiettoria
   contiene una chiamata metriche mirata allo stesso `cmdb_id`, nel
   livello corretto (node/container), con finestra che include
   l'intero episodio e un KPI compatibile (se presente).
   Una chiamata senza `kpi_name` e' una query piu' ampia e puo'
   coprire quel KPI; questa e' una **assunzione di copertura della query**,
   NON una garanzia che il risultato sia stato restituito o compreso.
4. Propone al massimo `min(max_checks, remaining_rounds)` chiamate
   distinte alle metriche, ciascuna con `start_unix`, `end_unix`,
   `cmdb_id` ed eventualmente `kpi_name` originale se disponibile.
5. Deduplica richieste identiche e distribuisce le proposte fra
   livello container/nodo e fra identita' dei componenti, senza
   attribuire punteggi causali o inventare priorita' di guasto.
6. Se non rimane budget, propone zero controlli.
7. Non cambia l'istruzione, non muta la diagnosi, non interroga
   tool, LLM o etichette.

La policy NON e' per ora collegata a `graph_engine.py` o
`experiment_runner.py`. I risultati A0/A1/A1_V2 restano invariati.

## Ipotesi ancora da verificare prima dell'integrazione

- Tutti i tool reali supportano `cmdb_id` e finestra; lo schema dei
  KPI e i limiti `max_rows` possono far perdere segnali.
- Un batch di piu' chiamate puo' essere eseguito in un singolo round LLM,
  ma il planner usa conservativamente una proposta per round:
  la futura variante dovra' documentare e vincolare il budget complessivo.
- I risultati dei tool potrebbero essere insufficienti anche per
  una query precisa. In quel caso serve uno stato **non conclusivo**.
- Il criterio di copertura investigativa e' diverso dalla validazione
  dell'evidenza e dalla verifica causale.
- `remaining_rounds` deve essere letto dallo stato effettivo del
  grafo quando e se il planner verra' collegato, non dedotto da un
  caso storico o dalla ground truth.
- La policy e' stata concepita dopo l'ispezione di q006:
  non valutarne l'efficacia sugli stessi casi come validazione nuova.

## Passo successivo

1. Test offline del solo planner.
2. Una simulazione puramente descrittiva su q006 con un **budget
   ipotetico**, marcato come tale e non confuso con i round storici.
3. Disegnare un braccio `A1_VERIFY` nuovo e versionato:
   proposta -> esecuzione limitata di tool -> osservazione ->
   risposta finale, con fallimento esplicito e tracciamento token,
   chiamate, round e costo.
4. Congelare protocollo e prompt *prima* di eseguire gli esperimenti
   su casi di sviluppo non utilizzati nella progettazione.
