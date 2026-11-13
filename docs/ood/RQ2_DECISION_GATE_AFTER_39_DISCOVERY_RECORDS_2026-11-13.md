# RQ2 — Decision gate dopo 39 stage discovery registrati

**Data:** 13 novembre 2026.
**Scopo:** definire una decisione scientifica/operativa,
NON autorizzare API o alterare il protocollo congelato.

## Stato confermato

La cella offline q026/A1/C,K ha concluso:
- claim: 32, tutti con risultato e senza unresolved;
- artefatti discovery: 39/72, 24 Gemini, 15 Sonnet, 0 Haiku;
- 28 `RECORDED_COMPLETE`, 4 `INVALID_OUTPUT`,
  7 `BLOCKED_DEPENDENCY`;
- 32 tentativi provider, 7 blocchi logici senza API;
- token osservati RQ2 823.656 (Gemini 363.753,
  Sonnet 459.903), senza equipararli a costi fatturati;
- OOD test = LOCKED.

## Root cause: limite della traiettoria legacy

La `tool_trajectory` in
`src/agent/graph_engine.py` contiene `tool_call`
(`tipo`, `nome`, `parametri`) e `tool_result`
(`tipo`, `nome`, `risposta`), ma non conserva
il `tool_call_id` delle chiamate e delle risposte
nella struttura destinata a RQ2.

Il bundle di evidenze di RQ2
`src/evaluation/rq2_evidence_bundle.py`
è volutamente fail-closed: in assenza di ID
ammette l'associazione per nome soltanto
se c'è esattamente una chiamata pendente
per quel tool. Se vi sono più chiamate pendenti
dello stesso tool, l'associazione per nome
è ambigua e la D viene registrata come
`INVALID_OUTPUT`, anche se ha JSON finale
valido. Non è lecito indovinare l'abbinamento
delle risposte in base all'ordine o al contenuto.

Tre D reali Sonnet:
- `cloudbed-1_q050/A1/D` (24 eventi, 12 call, 12 result);
- `cloudbed-1_q050/A1_8R/D` (12 eventi, 6 call, 6 result);
- `cloudbed-2_q026/A1/D` (20 eventi, 10 call, 10 result);
hanno tutte `AMBIGUOUS_TOOL_RESULT`,
`original_d_json_status=valid_json` e
nessun `provider_error`. Questa è una
limitazione di associazione della provenance,
NON una prova che il modello ha diagnosticato male.

## Rischio per le future campagne

Sono ancora da tentare **9 stage Sonnet** e
**24 stage Haiku**. L'associazione ambigua può
ripetersi se i rispettivi modelli emettono
più chiamate allo stesso tool nello stesso
gruppo di osservazioni. È possibile che alcune
D completino correttamente, come avvenuto
su `q032`, ma la percentuale di successi
non può essere assunta a priori.

**Raccomandazione metodologica:** evitare
ulteriori batch multipli Anthropic alla cieca;
prima verificare offline la causa strutturale
e progettare su un **nuovo branch separato**
un candidato di correzione della provenance.
Nessun test OOD deve essere esplorato per
orientare tale correzione.

## Proposta di versione alternativa RQ2 V2

Senza toccare i dati e i pin del V1:
1. In una campagna V2 separata, acquisire
   `tool_call_id` dalla chiamata modello
   e `ToolMessage.tool_call_id` dal risultato.
   Propagarli *solo per future esecuzioni*
   nella `tool_trajectory`, preservando
   anche nome, argomenti e testo.
2. Conservare inalterato il validatore
   fail-closed: verificare l'associazione
   univoca per ID e compatibilità per nome;
   nessun fallback a ordinamenti euristici.
3. Test offline, deterministici, prima di
   qualunque API:
   - due chiamate parallele dello stesso tool
     con ID diversi e risultati in ordine inverso:
     mapping esatto, senza scambio argomenti;
   - un tool unico legacy senza ID: la
     compatibilità precedente resta valida;
   - due chiamate same-name legacy senza ID:
     `AMBIGUOUS_TOOL_RESULT`;
   - risultato con ID errato, mancante,
     duplicato o nome incoerente: fail-closed;
   - preservazione hash dei file V1 e nessun
     accesso a GT o split di test;
   - test su replay sintetici/sanitizzati
     che non ricostruiscono retroattivamente
     il successo delle D invalidate V1.
4. Aprire un nuovo protocollo/preregistrazione
   con commit, SHA di sorgenti, coorte, ordine,
   stage e budget distinti. Solo dopo preflight
   e consenso alla spesa, fare un piccolo pilot
   autentico, quindi eventuale campagna.
5. Nel confronto scientifico separare sempre
   V1 e V2: attrition tecnica, validità JSON,
   provenance, astensioni, token e accuratezza
   sono KPI distinti; non mescolare denominatori
   o promuovere a validi tentativi V1 invalidi.
6. La verifica delle regole candidate e lo
   sblocco degli OOD test richiedono ancora
   criteri indipendenti di freeze/validazione.
   Nessuna correzione deve essere scelta in base
   alle label OOD riservate.

La V2 qui è una **proposta**, non è implementata,
non è autorizzata a effettuare nuove API
e non cambia lo status V1.

## Opzioni senza manipolare il protocollo V1

- **Prosecuzione V1 con singoli stage**:
  scientificamente possibile solo su stage
  mai tentati, con rischio noto di ulteriore
  spesa e possibili `INVALID_OUTPUT`.
  In caso di non-complete, arresto immediato;
  C/K bloccate offline, nessun retry.
- **Mantenimento V1 come campagna osservata
  parziale + avvio V2 distinta**:
  riduce il rischio di spendere token
  replicando una limitazione strutturale,
  ma comporta una seconda campagna e
  richiede preregistrazione esplicita.
- **Haiku V1 prima di V2**:
  consentito solo su stage mai tentati e
  previo budget/preflight, ma non risolve
  la mancanza di `tool_call_id` del runner.

Considerare la scadenza di consegna
della tesi del 1 dicembre 2026 nel
prioritizzare sperimentazione, analisi
e scrittura. Il refactoring finale
e i commenti in italiano devono
rimanere separati dalla campagna
scientifica congelata.

**Nessuna modifica ai sorgenti o ai dati;
nessuna chiamata API prodotta da questo documento.**
