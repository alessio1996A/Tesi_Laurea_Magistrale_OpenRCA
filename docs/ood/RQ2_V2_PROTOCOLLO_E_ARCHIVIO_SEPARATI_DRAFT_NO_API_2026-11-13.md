# RQ2-V2 — Proposta di protocollo e archivio indipendenti (DRAFT, NO API)

**Data di redazione:** 13 novembre 2026
**Stato:** `DRAFT_NOT_EXECUTABLE` — proposta tecnica, **NON preregistrazione definitiva**
**Branch di lavoro:** `experiment/rq2-provenance-v2-offline-2026-11-13`
**Versione candidata:** `rq2_knowledge_transfer_provenance_v2_draft`

## 1. Evidenze di partenza e motivazione

Output della suite PyCharm riportato dall'utente:

```text
Ran 817 tests in 69.351s

OK
```

I **817 test automatici** sul branch V2 sono stati superati, dopo:
- 7 test specifici `tool_call_id` e validatore fail-closed;
- 2 test runner→LangGraph→bundle→preparazione C con fake LLM/tool;
- 3 test D→C→K, journal/restart/no retry in directory temporanea;
- regressioni e suite globale aggiornate.

Questo è **evidence of software test coverage**, NON qualità diagnostica su OpenRCA, né riproducibilità di un provider reale o validazione delle regole K.

In V1 sono registrati **39/72 stage** di discovery: 24 Gemini, 15 Sonnet, zero Haiku. I claim provider osservati sono 32, gli stage blocked offline sono 7. Tre D Sonnet sono `INVALID_OUTPUT` per `AMBIGUOUS_TOOL_RESULT`, pur contenendo JSON D valido e senza errore provider; un C Gemini è INVALID, con K bloccato. Conservare V1 create-only.

**Decisione di ingegneria:** la fonte del limite è la mancata registrazione di `tool_call_id` nel ramo `graph_engine.py` di V1, mentre il bundler richiede provenance non ambigua. V2 conserva ID originali nel solo esecutore aggiuntivo; il bundler NON è stato allentato.

## 2. Principi inderogabili

1. V1 è congelata: mai riscrivere claim, record, risultati, score, split, manifest o source freeze. Un `INVALID_OUTPUT` V1 rimane invalido V1; nessun replay "riparativo" e nessun retry.
2. Gli **11 casi OOD test restano LOCKED**: niente file, etichette, score o esecuzione per selezionare, correggere o tarare il nuovo harness. Nessuna inferenza dalla GT.
3. Distinguiamo `RECORDED_COMPLETE` tecnico, validità JSON D, provenance verificata, valutazione qualitativa e accuratezza ufficiale. Non sono sinonimi.
4. V2 richiede uno **studio separato**: etichetta di protocollo, namespace, order of execution, budget, versione SDK/provider e logiche di fallimento propri.
5. Funzioni sorgente V1 invocate dal test non autorizzano l'impiego della loro directory reale: i test DCK hanno usato `TemporaryDirectory`, non il Drive.
6. Per ogni chiamata provider effettiva: create-only claim **prima** della chiamata, solo un tentativo, errore conservato, nessun rilancio automatico, `CLAIM_WITHOUT_ARTIFACT` → review manuale senza riavvio.
7. Un controllo formale su tool ID non dimostra la veridicità dell'osservazione: nessuna regola causalmente verificata senza analisi indipendente.
8. Protocolli e questioni metodologiche devono essere congelati **prima**, non dopo, di qualsiasi nuova API.

## 3. Namespace e forma del piano V2

Proposta di collocazione **distinta**, NON ancora usata per dati reali:

```text
<data_dir>/
  data/
    rq2/                          # V1, invariata
      stage_claims_v0/
      stage_artifacts_v0/
    rq2_v2_provenance/            # V2, nuova radice disgiunta
      releases/
      stage_claims_v1/
      stage_artifacts_v1/
      audit_manifests/
```

Il prefisso `data/rq2_v2_provenance` deve essere hard-coded da una nuova componente isolata, senza accettare `../` o un path arbitario. **Il codice non deve creare in anticipo directory reali** in fase di sola lettura.

Nuova grammatica degli identificativi di stage proposta:
```text
rq2_knowledge_transfer_provenance_v2:<case_id>:<model>:<harness>:D|C|K
```
La grammatica deve essere effettivamente implementata e confrontata con un **allowlist preregistrato**, non con un pattern permissivo. `test` NON è nel piano eseguibile; la sola modifica di `:test` in `:discovery` deve essere impossibile.

Documento di release create-only da definire prima della prima chiamata:
- `protocol_id` e `release_sha256`, schema version, data di freeze UTC;
- `git_commit_sha`, SHA-256 di file Python rilevanti e requirements / snapshot SDK;
- fingerprint dei CSV GT-free e SHA del piano completo, senza ground truth;
- coorte, ordine deterministico, modelli/provider/versioni, harness e D/C/K;
- input e output contract, hash dei prompt, max round, max token e policy timeout/retry;
- status reali, audit schema, token/costi, casi di stop e manual review;
- budget per singolo stage, budget aggregato e autorizzazione esplicita;
- stato `can_dispatch_api=false` sino a gate distinto firmato;
- fase OOD test `LOCKED`, nessuna scorciatoia per il freeze.

**Il prototipo non va avviato con release V1 né derivando autorizzazione dal successo di una suite mock.**

## 4. File create-only e confini di fiducia

Artefatto V2 (schema ancora da implementare) da vincolare a:
`protocol_id`, `release_sha256`, `stage_id`, `case_id`,
`logical_model`, `model_id`, `provider`, `harness`,
`stage`, `phase`, hash della dipendenza, `status`,
`raw_result` / `diagnostic_run`, hash SHA256 canonico,
`source_sha256`, token reali, `api_attempts`,
`technical_only=true`, `can_execute_test=false`.

Claim da vincolare allo stesso release, con:
`attempt_number=1`, data UTC, digest del parent,
stato `NO_API_AUTHORITY` come *semantica della claim*,
non come permesso della release. Un permesso API
deve arrivare solo da un gate diverso, indipendente
e valido per quel protocollo.

Se D fallisce: registrare C/K `BLOCKED_DEPENDENCY`
**senza claim di provider**. Se C fallisce: K blocked.
Se D è `RECORDED_COMPLETE` ma il JSON finale non è
valido, preservare entrambi gli stati: questa politica
deve essere esplicitata prima del freeze, perché
C dipende dalle evidenze tool, non dalla diagnosi D.
Un'astensione valida in C/K non equivale a errore.

I controlli di integrità devono:
- rifiutare file esistenti anche se apparentemente validi (NO RETRY);
- usare `O_EXCL` o equivalente atomico per il create-only;
- rifiutare symlink nei percorsi e identificativi fuori allowlist;
- evitare la scrittura in `data/rq2` oppure `data/results` di RQ1;
- verificare contenuto JSON canonico, status, versione e tutti gli hash;
- rifiutare campi GT noti e qualunque import del percorso scorer in pipeline attiva;
- verificare tutti i parent hash e l'identità del modello al restart;
- trattare record mancanti dopo claim come problema manuale, mai cancellare;
- distinguere durata, input/output token e costo **osservato**
  da un preventivo, senza affermare limiti finanziari che SDK non impongono.

I digest rilevano corruzioni/modifiche accidentali, non garantiscono autenticità contro chi può riscrivere sia file sia hash.

## 5. Piano sperimentale: cosa NON decidiamo retroattivamente

I 4 casi discovery della V1 sono già stati osservati. Se vengono riusati nella V2, l'esperimento misurerebbe la **robustezza tecnica della correzione su una coorte già vista**, NON una replica indipendente di generalizzazione. La correzione è stata motivata da errori osservati proprio su questa coorte; tale circostanza va dichiarata.

Per valutare il trasferimento di conoscenza in modo credibile:
- specificare *prima* la definizione di successo D→C→K e l'eventuale assenza di regole K formalizzabili;
- se non sono disponibili altri casi discovery mai visti, non inventare una coorte indipendente;
- non usare gli 11 casi OOD test per sviluppare V2;
- valutare se l'analisi di generalizzazione sia effettivamente fattibile nei giorni restanti, oppure presentare RQ2 come **studio esplorativo** con limiti;
- preregistrare campagna, comparatori, denominatori e attrition: tentativi per modello/harness, stage completati, invalid, blocked, astensioni, token, durata, errori provider, plausibilità delle regole, score ufficiale *solo quando legittimamente ammesso*;
- non promettere automaticamente 72 nuove esecuzioni: preventivare costi e limiti prima del piccolo pilot; ogni piano ampliato richiede nuova approvazione.

Non modificare il confronto RQ1 Evaluation20 preesistente né le statistiche già congelate.

## 6. Gate sequenziali GO / NO-GO

### Gate A — già superato per gli scenari testati
- **817/817 test Python PASS** sul branch sperimentale.
- Matching reale ToolNode/AIMessage ↔ ToolMessage con ID.
- Equivalenza V1/V2 della diagnostica *sintetica* senza gli ID.
- DCK fake con record, claim, dipendenze e restart.

### Gate B — DA IMPLEMENTARE E TESTARE, SOLO OFFLINE
- Nuovo piano/protocol ID e schema senza dispatcher API.
- Nuovi store/journal V2 in namespace fisicamente disgiunto.
- Test di create-only, symlink/path traversal, duplicati, crash e restart.
- Rifiuto assoluto delle directory V1 come destinazione.
- Verifica fingerprint GT-free senza leggere score/label.
- Simulazione completa del percorso runner-V2→D→C→K→archivio V2,
  con fake provider, e test fail-closed.
- Suite completa di regressione dopo tali modifiche.

### Gate C — PREREGISTRAZIONE SCIENTIFICA (prima di API)
- Stabilire coorte, comparatori e ipotesi falsificabili;
- quantificare budget e limite di stop, verificare SDK/versioni/policy;
- fissare source/release SHA, manifest e split; definire owner autorizzativo;
- scegliere un *solo* pilot su caso discovery, modello e harness registrati;
- autorizzare esplicitamente una chiamata a pagamento, senza retry.

### Gate D — dopo il pilot, senza conclusioni anticipate
- Audit token/tool/provenance/schema/claim/record e costo;
- esito `RECORDED_COMPLETE` è tecnico, non score;
- se il rischio residuo è eccessivo: **STOP**, conservare come evidence
  e descrivere gli esiti senza forzare una campagna V2;
- OOD test rimane LOCKED finché un freeze scientifico specifico,
  indipendente e giustificato non viene approvato.

## 7. Decisione di priorità per la tesi

Con consegna il **1 dicembre 2026**, evitare un'altra espansione
sperimentale incontrollata. In parallelo alla costruzione del gate B
preparare tabelle e figure RQ1/RQ2, metodologia, threat to validity,
e una decisione chiara su **che cosa dimostra** RQ2. Il refactoring
finale, commenti italiani e rimozione file superflui vanno dopo
il freeze sperimentale e non devono alterare risultati/source pin.

**Stato operativo alla redazione:**
- nessun nuovo codice di store/journal V2 implementato;
- nessuna chiamata API V2 e nessun test OOD;
- documento di design, non release firmata;
- V1 immutata.
