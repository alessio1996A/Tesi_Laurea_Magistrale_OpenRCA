# RQ2-V2 — Priorita' scientifiche e refactoring differito (15 novembre 2026)

**Stato:** decisioni operative non autorizzative, prima della release RQ2-V2 unificata.  
**Fonte della decisione:** indicazione riferita dall'utente a seguito di confronto con il relatore.  
**Branch:** `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.

## 1. Priorita' e politica economica

La priorita' indicata dal relatore e' completare la ricerca correttamente e con precisione; il costo delle chiamate non deve determinare scorciatoie, riduzioni arbitrarie della matrice o selezioni favorevoli degli agenti. Per questo non sospendere il lavoro metodologico per chiedere ripetutamente micro-budget.

**Questa indicazione NON costituisce** consenso a spendere una cifra indefinita, autorizzazione a eseguire API o accettazione di una release. Il contratto `rq2_v2_unified_scientific_release_contract.py` richiede comunque `approved_total_usd_limit` positivo (operativo, non hard-cap) e `approval_reference` reale; il dispatcher richiede conferma distinta per l'esatto stage prima di ogni chiamata. Ogni errore e ogni consumo incompleto vanno registrati. Non assegnare importi o approvazioni all'insaputa dell'utente.

## 2. Da completare prima dei primi stage RQ2-V2

1. Trattare le prove del percorso sincrono 503, HTTP 429 e timeout locale (tutte PASS) per quello che dimostrano, senza dedurne hard cap HTTP/USD o limite di durata dell'intero stage D.
2. **Preregistrare prima degli output reali** una rubrica deterministica e conservativa per K (riferimenti E### validi e presenti, segnali/metriche e unita' riscontrabili nella traiettoria, condizioni coerenti e non contraddittorie, presenza di controesempi/limiti/astensione, `requires_verification` distinto da `not_formalizable`). Evitare di confondere JSON valido, regola `candidate` e correttezza diagnostica. I giudizi semantici non automatizzabili devono essere esplicitamente dichiarati `unverified` e non trasformati in scoring certo.
3. Fissare il report primario sul denominatore **pianificato**: 5 harness × 3 modelli × 4 discovery, 60 D e fino a 60 C/60 K (180 stage logici). D/C fallite e K bloccate restano nel denominatore. Confronti appaiati a parita' di incidente e modello/harness; n=4 esplorativo.
4. Source/runtime GT-free e clean HEAD, ledger create-only/readback, single writer con claim prima delle API, nessun retry automatico, dipendenze D→C→K, permission della release SHA approvata esternamente.
5. Richiedere esplicita autorizzazione di budget tecnico e di un solo **stage D** prima delle chiamate reali; poi valutare l'eventuale espansione a campagna solo in accordo con l'utente. Nessuna autorizzazione anticipata a test OOD.
6. Dopo raccolta e audit dei 180 stage pianificati, analisi per tutti i 15 arm con token/tempo/errori/astensioni e dimensione esplorativa del confronto. Solo se esistono K verificabili, nuovo protocollo congelato Opzione B per gli 11 OOD, evitando leakage.
7. Non implementare human-in-the-loop: escluso su indicazione del relatore, menzionabile come lavoro futuro o limite, non come componente sperimentale.

## 3. Refactoring e pulizia SOLO dopo l'ultima raccolta dati

L'utente richiede esplicitamente, prima della stesura finale, una passata strutturata di manutenzione:
- nuova branch dedicata al refactoring a partire da commit sperimentale congelato;
- commenti/docstring esplicativi **in italiano** per il codice destinato alla consegna, con distinzione chiara tra codice di ricerca, strumenti di riproduzione e test;
- eliminazione o archiviazione dei file realmente inutili, duplicati o temporanei, solo dopo audit di riferimenti/import/dipendenze e una lista motivata da far verificare all'utente;
- organizzazione dei percorsi, script, notebook, documenti e repository, con README e istruzioni di riproducibilita';
- mantenere commit/tag e dati grezzi/manifest/scorer scientifici originali per la tracciabilita'. Non cancellare mai a posteriori l'evidenza della ricerca, non alterare protocolli e risultati gia' congelati;
- eseguire nuovamente i test rilevanti sulla branch di refactoring; separare tale attivita' dalla raccolta dati, per non cambiarne il significato scientifico.

**Questo e' un piano di lavoro, non un refactoring gia' eseguito.** Per ora nessun file eliminato.

## 4. Stato reale al momento della nota

- Preflight 29 sorgenti, SDK pinned, Drive single-writer locale, fake HTTP 503, loopback timeout e HTTP 429: PASS nei rispettivi scenari.
- Nessuna modifica ai 29 sorgenti di produzione da `601dc7c2f971b919962ff190e6feb192c4dd237a` (controllato con compare GitHub fino al commit `c09d6bfa3c45e518a208d5d9e9029ec6512216c0`).
- `LIVE_API_ENABLED=False`; release scientifica RQ2-V2 ancora assente; nessuna approvazione API per stage; `0/180` stage RQ2-V2 eseguiti reali.
- RQ1 congelato, RQ2 V1 e precedente pilot Sonnet V2 separati, 11 casi OOD LOCKED.
- Prossimo lavoro tecnico: definire/fissare rubrica K conservativa e controllare che la sua misurazione possa essere applicata **senza leggere GT** e **senza cambiare output C/K**; poi congelare la release, non ripetere suite precedenti senza causa.
