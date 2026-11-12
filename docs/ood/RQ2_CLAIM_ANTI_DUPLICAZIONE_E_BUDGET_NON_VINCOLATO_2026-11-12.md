# RQ2 — Claim anti-duplicazione per Colab, senza limite economico

**12 novembre 2026** — Proposta tecnica **offline, non eseguibile**. Modulo nuovo predisposto, test locali non ancora eseguiti. Nessuna API Gemini/Claude chiamata.

## Decisione del relatore riferita dall'utente

L'utente ha riportato che il professore consente l'utilizzo del budget necessario per Gemini/Claude. **Non impostare un tetto USD o un cap economico come condizione per la campagna RQ2.** Le stime del preflight `rq2_budget_preflight.py` rimangono utili come *analisi descrittiva*, ma non devono ostacolare la campagna. Il log delle richieste e dei token fatturabili è importante per riproducibilità e confronto di efficienza, **non per autorizzare o bloccare sulla base di una soglia monetaria**.

**Test confermati:** `test_rq2_budget_preflight.py`: `Ran 16 tests in 0.005s — OK`. Il precedente criterio hard-cap USD nei documenti pre-freeze è **superato da questa decisione**. Continuano a essere obbligatori verifiche fonti, modelli/prompt, decisioni metodologiche, protezione test e gestionale delle doppie esecuzioni.

## Problema: API pagata, Colab disconnesso, risultato non salvato

Un esperimento potrebbe essere iniziato e fatturato prima di avere un file JSON finale. In questo caso un riavvio che controlla soltanto i risultati già salvati potrebbe **ripetere involontariamente la stessa richiesta**, alterando il protocollo e moltiplicando i costi, anche se il budget non è vincolato. Il problema fondamentale è di **identità sperimentale e integrità**, non di spesa.

## Nuovo modulo `rq2_discovery_claim_journal.py`

Il modulo `RQ2DiscoveryClaimJournal` riusa il preflight sorgenti dello store `RQ2StageArtifactStore` e salva solo una *prenotazione persistente e immutabile* per uno stage D, C o K **della sola discovery**.

- Radice fissa `<data_dir>/data/rq2/stage_claims_v0/`, diversa sia da RQ1 sia da `stage_artifacts_v0`; il costruttore e `audit_restart()` non scrivono.
- `claim_stage(stage_id,model_id_proposed)`: fa audit dell'archivio e dei claim precedenti, verifica l'identità del piano/manifest congelato e le dipendenze, impedisce stage test, risultati già esistenti, model ID incoerente e claim preesistenti; quindi crea **una sola volta** il file `RQ2_CLAIM_<sha256(stage_id)>.json` con `os.O_EXCL`, checksum, data UTC e provenienza.
- Il claim **non è un via libera alle API**: `authority=NO_API_AUTHORITY`, `can_execute_api=false`. Una futura modalità live deve controllare un **protocollo frozen separato**, e usare il claim come barriera immediatamente **prima** di ogni tentativo reale. Il claim stesso non chiama il provider.
- L'esito del controllo al riavvio distingue `finished_with_matching_result` da `unresolved_manual_review`. Uno stage claimato ma senza record finale rimane **incerto**, anche dopo ore o giorni. Non ci sono timeout auto-release o retry automatici. Per rilanciare uno stage incerto serve *un audit esplicito e un protocollo di eccezione versionato*; questa versione non fornisce una funzione per cancellare, modificare o duplicare la prenotazione.
- Le fasi C/K richiedono la presenza di un genitore persistito in stato `RECORDED_COMPLETE` con lo **stesso model ID**. Se il genitore è `PROVIDER_ERROR` o `INVALID_OUTPUT`, non si crea un claim nuovo: la fase dipendente va registrata offline come `BLOCKED_DEPENDENCY` tramite il recorder precedente.
- L'archivio di risultati e quello dei claim restano **due strutture distinte**; al riavvio si confrontano modello, stage, dipendenze e hash delle due sorgenti GT-free. Digest SHA-256 rilevano corruzione accidentale, non proteggono da un attore che abbia pieno controllo di tutti i file.
- Nessun modulo di claim importa SDK/provider, crea `ExperimentConfig` live, interroga tool OpenRCA, legge record/scorer/GT, o apre i casi test.

**Limite operativo esplicito:** il journal non risolve automaticamente la finestra tra `claim_stage` e una chiamata provider. Dopo un crash lì, potrebbe esistere un claim anche se nessuna richiesta è partita: è corretto segnalarlo come incerto senza inventare un retry. Per una campagna scientifica vera questa ambiguità deve essere gestita dal protocollo di revisione/riassegnazione, non con uno sblocco basato sul tempo.

## Verifica locale

`src/tests/test_rq2_discovery_claim_journal.py`: **20 test sintetici predisposti, ancora da eseguire**, con manifest e piano finti **solo all'interno dei test**. Coprono create-only, due claim sullo stesso stage, restart senza artifact, riconciliazione con artifact presente, claim di C/K condizionati, errori D, K/test bloccati, tampering, file parziale, fonte cambiata e assenza di budget economico.

Da PyCharm:

```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_discovery_claim_journal.py" -v
```

**Attesi 20 test. Non dichiarare successo finché non arriva il log PyCharm.**

## Passaggi successivi

Dopo test verdi: completare la specifica **scientifica di freeze** (coorte, output mode D, hash prompt C/K e regole di formalizzabilità), collegare preflight D, recorder e claim a un **runner simulato end-to-end** che usa soltanto provider fake. Solo dopo le verifiche preregistrare il protocollo e avviare i pilot reali, senza tetto economico artificiale e senza trattare la disponibilità finanziaria come un sostituto dell'integrità sperimentale.

**Nessun risultato RQ2 reale è stato ancora prodotto. RQ1 congelata invariata.**
