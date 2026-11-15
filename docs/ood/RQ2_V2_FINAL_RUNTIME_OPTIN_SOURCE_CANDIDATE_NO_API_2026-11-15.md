# RQ2-V2 — candidato source finale con opt-in runtime esatto, default OFF

**Data:** 15 novembre 2026. **Stato:** nuova modifica ingegneristica **non ancora testata da PyCharm o Colab**. Nessuna API, release, claim, record o approvazione di manifesto creata da questo commit.

## Motivazione

I due sorgenti gia' verificati G4K e G4L avevano costanti `LIVE_API_ENABLED=False` e `SCIENTIFIC_RELEASE_WRITE_ENABLED=False`. Un eventuale futuro flip esplicito nel sorgente dopo il freeze avrebbe invalidato la fingerprint e obbligato un'altra campagna di verifica. Per preparare **un singolo commit definitivo verificabile prima del pilot**, i gate ora leggono un opt-in esatto dell'ambiente **all'import del modulo**, default `False`, e rimangono separati dal consenso scientifico/finanziario.

Base di branch: `178ba0d9b289d2a1fc5a95006311443bd4b30007` (decisione budget Opzione A registrata). Nuovo branch: `feature/rq2-v2-runtime-optin-final-source-2026-11-15`.

## Diff circoscritto

1. `src/evaluation/rq2_v2_unified_live_dispatcher.py` G4K: `LIVE_API_ENABLED = runtime_live_optin()`, helper che accetta solo valore esatto della variabile `OPENRCA_RQ2_V2_ENABLE_PAID_SINGLE_STAGE`. **Default False**. La sola variabile non basta: `confirm_paid_api=True`, stage_id autorizzato identico a quello passato, SHA esatto di release, Git HEAD clean, release reale con budget + approval reference, G4H/ledger preclaim e lock restano obbligatori. Non imposta né usa tali valori da solo.
2. `src/evaluation/rq2_v2_unified_scientific_ledger.py` G4L: `SCIENTIFIC_RELEASE_WRITE_ENABLED = runtime_release_write_optin()`, helper che accetta solo valore esatto della variabile `OPENRCA_RQ2_V2_ENABLE_RELEASE_CREATE`. **Default False**. Futura release create-only richiede G4D/G4A/G4B, SDK pinned, G4E, SHA canonico approvato, riferimento esterno reale e budget; no API, no claim. La sola variabile non e' autorizzazione.
3. `src/tests/test_rq2_v2_runtime_optin_guards_offline.py`: nuova suite **6 test da eseguire**, con patch delle sole variabili in memoria, isolamento dei gate e consenso per-stage obbligatorio. Nessun provider o file di dati.

**Importante:** le due variabili sono selettori tecnici, NON autenticazione né consenso dell'utente; il fatto che siano pubblicate nel codice non conferisce alcun diritto all'esecuzione. Non impostarle nel preflight Colab. Per il pilot verranno usate soltanto in un processo separato e soltanto dopo approvazione della release SHA e consenso esplicito per lo stage pagato.

## Piano minimo di verifica

- Su checkout locale branch clean al nuovo HEAD: nuovo test opt-in **6**; regressione G4L **9**; regressione G4K **18**. Questi ultimi due gruppi sono giustificati perche' abbiamo cambiato esattamente i loro gate runtime. La regressione G4F **22** era PASS sul codice G4L e le funzioni di ledger/record non sono state modificate; non ripeterla in blocco senza un motivo.
- Se tutti PASS: un **solo** Colab GT-free su checkout temporaneo pinned al commit finale, 30 SOURCE_PATHS, G4A/G4B/G4D/dossier, SDK pinned, flags effettivamente `False` in processo con env disattivato, release assente, ledger vuoto, 11 OOD locked. Gli SHA `source_inventory_sha256=205f6dd4...` e `blueprint_sha256=13cac143...` del commit G4L precedente sono solo evidenza storica: **due sorgenti della lista sono cambiati, ricalcolare entrambi**.
- Non fare test API o aggiungere altri esperimenti preparatori se i gate sopra passano; preparare manifesto G4E canonical a budget `100.00` e reference di approvazione esterna **solo dopo** review scientifica di fingerprint e sorgenti. Manifesto candidate non equivale ad approvazione.
- Prima della creazione release: il suo digest SHA-256 deve essere approvato separatamente. Prima del pilot: consenso addizionale esclusivo per `rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:D`, un solo writer/claim, zero retry, STOP obbligatorio per audit.

## Invarianti

- RQ1 e vecchie V1 congelate; RQ2 Opzione A 4 discovery x 5 harness x 3 LLM x D/C/K = **180 stage logici** pianificati; Opzione B 11 OOD ancora LOCKED.
- Budget operativo approvato `USD 100.00` per Opzione A (non hard cap, non consenso API); policy stop/batch successivi ancora da ratificare nella release. Niente ottimizzazione arbitraria per i costi.
- Nessuna modifica ai prompt D/C/K, rubrica K, benchmark, risultato precedente, versioni SDK, scoring o 30-list SOURCE_PATHS.
- No attivazione delle env, no creazione release, no API su questo branch. Il pin SHA e la fonte dei 30 source saranno aggiornati solo **dopo** veri test PyCharm e Colab.

**Non confondere** una sorgente "attivabile" con una release approvata o con l'esecuzione live: sono tre condizioni diverse. Non sono richiesti adesso paper/trascrizioni del relatore.

## Esito PyCharm e autorizzazione utente (15 novembre 2026, dopo la preparazione)

L'utente ha comunicato esplicitamente **«si i test sono passati tutti e autorizzo»** in risposta alla richiesta di eseguire le tre suite (6 opt-in + 9 release writer + 18 dispatcher) e alla specificazione che il pilot reale avrebbe richiesto un'autorizzazione esplicita. Pertanto **33/33 test risultano PASS secondo il resoconto dell'utente**; l'output dettagliato non e' stato incollato, quindi non attribuire tempi o altri dettagli non forniti. La frase e' registrata come consenso a procedere al **solo** pilot `rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:D`, subordinatamente ai gate di release ancora mancanti. Non e' approvazione del manifesto canonico, il cui SHA non e' ancora disponibile; non autorizza gli altri 179 stage ne' gli 11 OOD.

Verifica GitHub del branch prima del prossimo preflight: `3b9a82896d027bfe0920a7e4e9128412b9ba2b74` ancora identico alla HEAD del branch prima della documentazione. **Prossimo ed unico controllo tecnico:** Google Colab READ-ONLY su checkout clean PINNED della nuova HEAD (dopo i soli commit documentali), verificando entrambi i selettori runtime OFF nel processo Python isolato, le 30 sorgenti source-bound, runtime, G4A/G4B/G4D e dossier GT-free in memoria; stampare nuovi SHA inventario/blueprint, con confronto positivo solo per le identita' scientifiche stabili. Non attivare env, non costruire client LLM, non creare release, claim o record. Fino a quel PASS `release_sha256=null`, nessuna API RQ2 V2.

Successivamente si prepara la release G4E **in forma di proposta senza scrittura**, budget `100.00` USD gia' confermato; occorre mostrare il digest SHA del manifesto all'utente e ottenerne l'approvazione esplicita prima della creazione create-only G4L. Non chiedere di nuovo consenso generico al pilot gia' espresso; prima di eseguire verificare che l'autorizzazione continui a riferirsi esattamente al singolo stage e che release/commit approvati coincidano.
