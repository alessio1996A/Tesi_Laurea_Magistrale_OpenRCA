# RQ2 — Pacchetto di revisione scientifica prima del release discovery

**Data 12/11/2026 · STATO: CANDIDATE_FOR_REVIEW, NON APPROVATO, NON ESEGUIBILE**

**Scopo:** chiudere le decisioni scientifiche già discusse, senza aprire nuovi
casi OOD, alterare RQ1 o autorizzare chiamate ai provider. Questo file **non**
è `RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json`, non produce né contiene la firma
SHA-256 di tale release, non modifica i gate software e non è una richiesta
di autorizzazione alle API.

## Evidenze già acquisite realmente

| Gate tecnico | Evidenza reale |
|---|---|
| RQ1 frozen | 13 blob originari verificati; factory RQ1 Git blob `05308d5740763db0444556dcb7330d8fb4c308ec` |
| Split/coorte OOD | 4 discovery, 11 test (4/10 gruppi temporali), fonte e SHA in `RQ2_PREFLIGHT_GT_FREE_REALE_VERIFICATO_2026-11-12.md` |
| Piano sorgenti GT-free | `plan_preview_sha256=ecd6d926933a5ad056ad1a581fa7e490c0a13eee18070c7dac8627c1b19c062e` dal precedente preflight Colab |
| SDK LangChain sync | mock HTTP503 completo in Colab: 8/8 test, un send finto per ognuna delle quattro `invoke`, nessuna API remota |
| RQ2-only factory / D / C/K | 10 + 12 + 15 = **37/37 test PyCharm** (`0.055s`, `0.963s`, `8.137s`) |
| Scorer fault type offline | **16/16 test PyCharm** (`Ran 16 tests in 0.004s — OK`), mock e dati sintetici |
| Esecuzioni RQ2 | **Nessuna** discovery D/C/K e nessun test OOD reali finora |

**53 test delle ultime quattro suite PyCharm** sono stati superati.
Le cifre riguardano unit test offline e mock, **non** diagnosi corrette
su OOD. Il test HTTP Colab prova unicamente i percorsi sincroni sotto
HTTP503 mock, non timeout sotto stallo reale.

## Decisioni da congelare ex ante (proposta specifica e verificabile)

### A. Domande di ricerca e inferenza

- **RQ2-A (primaria):** valutare se i due harness A1 e A1_8R
  riconoscono la classe di guasto su **11 query OOD non viste**,
  a parità di caso e provider, tramite probe C separata dalla
  risposta diagnostica D del task Microsoft. Questa misura
  documenta **generalizzazione OOD della diagnosi**:
  non chiamarla da sola *knowledge transfer riuscito*.
- **RQ2-B (secondaria):** osservare se la discovery sui 4 casi
  produce 24 proposte K strutturalmente valide, attribuite a
  evidenze E###, falsificabili e formalizzabili. Senza prova
  delle unità/operazioni non chiamarle detector pronti.
- **RQ2-C (esplorativa condizionata):** testare l'applicazione
  di regole K soltanto dopo implementazione deterministica,
  validazione su sorgenti consentite e **freeze scientifico
  indipendente prima di consultare gli 11 casi test**.
  Se 0 K superano il criterio, non creare un detector fittizio:
  riportare un esito negativo o inconcludente sull'effettivo
  trasferimento implementabile.

### B. Partizione, arm, denominatori

- 4 discovery: `cloudbed-1_q032`, `cloudbed-1_q050`,
  `cloudbed-2_q026`, `cloudbed-2_q045`.
- 11 test OOD già definiti in `rq2_dryrun_plan.py`;
  10 gruppi temporali distinti; la finestra multi-guasto
  `cloudbed-1_q014`/`cloudbed-1_q030` non conta
  come due episodi indipendenti.
- Audit GT *isolato* aggregato esistente
  `REPORT_ANTEPRIMA_PARTIZIONE_RQ2_V1_2026-11-11.md`
  indica una discovery per classe e gap cross-phase
  di almeno 90 minuti nei casi comparabili.
  Il mapping query→classe rimane **non esportato**.
- 3 modelli `gemini-3.5-flash-lite`, `claude-sonnet-5-5`,
  `claude-haiku-5-5` × 2 harness `A1`, `A1_8R`.
- 72 stage discovery (24 D, 24 C, 24 K);
  132 stage test (66 D, 66 C) dopo freeze K;
  204 stage pianificati in tutto, **non** 204 richieste HTTP.
- Arm dimostrativo principale da approvare *prima delle K*:
  **A1_8R + Claude Sonnet 5.5**. Tutte le 24 K di altri arm
  rimangono nel riepilogo descrittivo, evitando selection bias.

### C. Scoring offline RQ2-A

- `src/evaluation/rq2_fault_type_eval_policy.py` con
  16/16 test sintetici superati e Git blob osservato
  `535ea298a7458790ca16d9cb40fa93c8b369e3a0`.
- Quattro stringhe canoniche, normalizzazione strettamente
  lessicale, nessun sinonimo/fuzzy scelto dopo le predizioni.
  `unmatched_diagnosis` viene contato come errato nella
  metrica primaria, **non** come astensione.
- Accuratezza primaria per arm: **corretti / 11 pianificati**;
  provider error, invalid JSON, abstain, blocked e missing
  restano nel denominatore.
- Metriche secondarie: coverage, accuratezza sui soli
  contratti validi, accuratezza sulle diagnosi; confronto
  A1_8R−A1 win/tie/loss sui casi appaiati.
  Evitare significatività statistica forte su N piccolo.
- Le reference GT sono lette solo nel **processo separato
  di valutazione** dopo gli output OOD congelati: mai nel
  modello, tool, C/K, prompt o pseudoregole.

### D. Regole K: non eseguire conoscenza non verificata

- Catalogo di **29 nomi KPI noti nel codice** (non un inventario
  certificato delle metriche nelle finestre OOD) con
  `kpi_source_catalog_sha256=`
  `81958222ebe027c6f205e9b6d8fc6c562b386eba20a05436b35522dfd92cf2eb`
  da precedente preflight Colab.
- Una K è `candidate` se il JSON e riferimenti E### sono
  validi. Diventa operativamente formalizzabile solo dopo
  verifica indipendente di nome preciso della metrica,
  presenza in sorgenti **development GT-free** autorizzate,
  tipo/semantica, unità, finestra, aggregazione, missing,
  threshold e astensione; nessuna valutazione sugli 11 test.
- Finché tali precondizioni non sono dimostrate,
  classificare `requires_verification`/`not_formalizable`.
  Non creare automaticamente threshold né eseguire
  `pseudocode` LLM. Eventuali 0 regole formalizzabili
  vanno riportate come risultato negativo.
- In RQ2-C lo scorer `rq2_rule_group_scorer.py` è offline,
  gruppi completi con presenza multi-fault per classe,
  nessun controllo healthy inventato.

### E. Policy provider e integrità delle esecuzioni

- **Factory solo RQ2:** Google `max_retries=1` (1 tentativo
  SDK complessivo nelle versioni pin), Anthropic
  `max_retries=0` (0 ritentativi dopo il primo invio),
  `timeout=300.0s` **per singola richiesta**;
  Claude `max_tokens=4096`. Non è un limite globale D;
  timeout fisici sotto stallo non certificati. Niente
  `ainvoke`/`stream`/`astream` senza nuova preregistrazione.
- Iniettare `llm` nel runner RQ1 invariato; D con
  5 tool originali e al massimo 6 round; C/K una
  `invoke` sincrona senza tool.
- Dopo release verificato, ogni singolo stage ha un
  claim **create-only** prima delle API, output/raw/usage
  archiviati create-only, nessun retry automatico o
  correzione arbitraria del JSON; crash = audit manuale.
- Zero limite USD preventivo su indicazione del relatore
  riferita dall'utente; registrare obbligatoriamente
  token, costi, durata, errori ed eventuali dati usage
  mancanti (non sostituire con zero).
- Anche dopo release discovery, gli 11 test rimangono
  **bloccati** fino al freeze separato delle conoscenze.

## Blocchi realmente residui PRIMA della prima API (da non aggirare)

1. **Approvazione scientifica esplicita** di questi criteri e della
   partizione/arm scelti senza aver visto nuove K o test OOD.
   La presente scheda è solo la proposta verificabile.
2. **Impronte finali e identità di versione:** rileggere il
   Git commit conclusivo, SHA-256 runtime degli script
   scoring/factory/catalogo e di tutti gli altri sorgenti
   che saranno pin nel release. I vecchi hash non
   devono essere riciclati a fronte di drift di codice.
3. **Controllo prerelease offline, senza API** in Colab sul
   *medesimo* checkout della futura campagna: 4 discovery,
   11 test, 204 stage, 4/10 gruppi, factory runtime
   source-hash, alias scorer e criteri K.
4. **Release create-only `RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json`**
   con campo `test_unlocked=false`, hash SHA-256
   realmente verificato tramite readback e controlli
   che vincolino source/protocollo/policy del provider,
   oltre ai guard esistenti di `_read_release`.
   NON creare tale release da questo semplice documento;
   `RELEASE_SHA256=None` e
   `PLAN_STATUS=DRAFT_NOT_EXECUTABLE` devono restare tali
   finché tutti i gate siano completati.
5. **Autorizzazione esplicita a uno specifico primo stage D**
   a pagamento (modello/caso/harness), seguita da esecuzione
   singola con audit; nessuna campagna automatica anticipata.

**Nota scientifica per la tesi:** 11 query test su 10 finestre
sono una coorte piccola, la classe container write I/O load
risulta solo in cloudbed-2 e la separazione per finestre
non prova indipendenza fisica delle iniezioni. Formulare
le conclusioni in termini di evidenza osservata e
limiti di generalizzazione, non di universalità.
