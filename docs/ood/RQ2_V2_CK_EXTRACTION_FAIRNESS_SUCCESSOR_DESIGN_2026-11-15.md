# RQ2-V2 — revisione tecnica e criteri di equità del successore C/K (15 novembre 2026)

**Stato:** bozza di progettazione e audit, NON release scientifica, NON autorizzazione ad API. Branch `audit/rq2-v2-ck-multiblock-fairness-2026-11-15`. La sorgente V2 originale è congelata al commit `f0b64a36b08c2ae5db424b544965db5362190377` e alla release SHA256 `af1867e2539edbb42cf27ae92c602dfacca1c12968475235955fb1cf0ed2dac4`.

## Evidenza osservata e limiti di attribuzione

- Nel record reale `cloudbed-1_q032:gemini:A0:C`, `INVALID_OUTPUT`, SHA `51946d926aa2a5a0f9dd2ba997d8565116ef8158a2af44df5d0051d73ee3f4b1`, lo `schema_version` contiene una nuova riga NON escapata in `"rq2_cause\n_probe_v0"`. K è `BLOCKED_DEPENDENCY` e non ha richieste provider. D precedente resta immutabile.
- La funzione condivisa `agent.graph_engine.testo_messaggio` usa `"\n".join(parti)` per liste di blocchi. Il test offline ha riprodotto una corruzione equivalente con due frammenti testuali sintetici.
- Il record scientifico conserva il testo **dopo estrazione**, non l'`AIMessage.content` originale: attribuire il difetto reale a Gemini oppure all'adattatore è **non dimostrato**. Il record NON viene riparato.
- A parità di blocchi sintetici, 4/4 test sul comportamento originale, 9/9 test del candidato e 6/6 test di integrazione simulata sono **PASS riferiti dall'utente in PyCharm**. Tali test NON provano come i provider reali suddividano il contenuto.

## Decisione tecnica candidata

Una politica uniforme estrae solo frammenti testuali visibili con concatenazione esatta `"".join(fragments)`, mantenendo OGNI carattere fornito, senza inserire spazi o newline. Non esegue JSON repair, non rimuove caratteri, non forza diagnosi, non cambia schema C/K o prompt, non rivela ragionamento/firme/tool use.

Un blocco di tipo `text` o `text_delta` produce il proprio contenuto. Un blocco non testuale non deve essere incluso. Un elenco eccessivo deve produrre un errore di protocollo **registrabile**, non un'eccezione post-claim che lasci un orphan. Una stringa singola deve restare bit-per-bit identica.

**Limite metodologico:** la concatenazione esatta è appropriata per frammenti della *stessa risposta*, ma non autorizza a unire messaggi distinti o output eterogenei. I test mock non dimostrano la semantica dei content block reali per tutte le versioni SDK; verificare rappresentazioni runtime congelate prima del freeze.

## Implementazione sperimentale NON ATTIVA

- `src/evaluation/rq2_v2_ck_text_extraction_candidate.py`: estrattore neutrale isolato.
- `src/evaluation/rq2_v2_ck_provider_transport_candidate.py`: trasporto successore isolato, nessun import dal dispatcher esistente; usa factory RQ2-only e il metering consolidato. Una sola chiamata logica `model.invoke`; eventuale errore del provider mantiene costo incerto e non attiva retry.
- `src/tests/test_rq2_v2_ck_provider_transport_candidate_offline.py`: nuovi test per percorso candidato, C/K, metering, no retry, redazione eccezioni, errori tool e limiti content block; **in attesa del risultato PyCharm**, non considerarli già PASS.

I test su `src/tests/test_rq2_v2_ck_candidate_transport_integration_offline.py` esercitano il trasporto originale con un monkeypatch solo nei test, per dimostrare compatibilità e differenza. Il successore separato evita qualsiasi monkeypatch in runtime reale.

**Vincolo del freeze:** il vecchio `src/evaluation/rq2_v2_unified_release_preflight.py` include `evaluation/rq2_ck_provider_transport.py` e `evaluation/rq2_v2_unified_live_dispatcher.py` nell'inventario SHA. La release congelata non può autorizzare né certificare il nuovo trasporto solo perché esiste un file candidato; la verifica source-bound deve includere esplicitamente ogni componente del nuovo percorso di esecuzione. Non modificare la vecchia release G4E/G4L o la sua directory.

## Gap di provenienza identificato nell'interfaccia esistente

L'adattatore congelato `normalize_ck_call()` accetta la ricevuta del trasporto successore, ma costruisce un artifact C/K con i soli campi `raw_response` e `stage_meter`. Di conseguenza, i metadati aggiunti alla ricevuta (`content_extraction_policy`, `response_content_kind`, `text_blocks_observed`, `nontext_blocks_observed`) **non sopravvivono alla registrazione sul ledger V2**. Questo è un rischio di auditabilità; non è un errore di validazione JSON e non conferisce alcun permesso di cambiare il ledger congelato.

Nuovo test mirato: `src/tests/test_rq2_v2_ck_candidate_ledger_compatibility_offline.py`. Usa un ledger/release interamente sintetici in TemporaryDirectory, verifica D→C→K sui tre modelli, C invalida→K bloccata senza retry e documenta esplicitamente la perdita dei metadati. **Stato: in attesa dell'esito PyCharm**.

Per il successore scientifico occorre un contratto/ledger **versionato e separato** che conservi queste diagnostiche in una struttura validata, senza salvare thinking, firme o altri dati sensibili; tutti i record del successore devono avere una policy dichiarata e identica per modello. La compatibilità con lo schema V2 non equivale a disponibilità di provenienza sufficiente.

## Contratto di provenienza scientifica C/K successore — candidato, non attivo

Dopo l'esito PyCharm **3/3 PASS** per `test_rq2_v2_ck_candidate_ledger_compatibility_offline.py`, è stato preparato `src/evaluation/rq2_v3_ck_provenance_receipt_candidate.py` (nessuna API, nessun writer) con un envelope versionato `text_extraction` per C/K.

Il contratto candidato conserva esattamente: `schema`, `policy`, `content_kind`, `text_blocks`, `nontext_blocks`. Verifica schema/policy esatti, conteggi interi non negativi e limitati, coerenza tra errori e presenza di testo, e classificazione C/K con gli stessi validatori rigorosi del percorso congelato. Nessun contenuto di thinking, firma o tool-use nei nuovi metadati. La ricevuta mantiene `raw_response` e `stage_meter`.

La separazione è deliberata: l'artifact successore **non è compatibile** con la lista di campi ammissibili del ledger V2. In seguito servirà un **contratto ledger V3 dedicato**, con namespace distinto, versione e inventario source-bound, create-only, SHA e controlli pre/post-record. Non è consentito forzare l'accettazione dell'artifact successore modificando il vecchio ledger.

Nuovi test preparati, **non ancora eseguiti in PyCharm**: `src/tests/test_rq2_v3_ck_provenance_receipt_candidate_offline.py` (7 test per C/K su 3 modelli, errore provider, JSON invalido, metadati tamper, readback serializzato, fail closed su metadata assente e isolamento V2). Nessuna release o autorizzazione live è stata emessa.

## Prototipo di persistenza V3 SOLO OFFLINE, successivo ai 38 test PASS

Il test del contratto di provenienza successore `test_rq2_v3_ck_provenance_receipt_candidate_offline.py` ha avuto **7/7 PASS** nell'ambiente PyCharm dell'utente. Totale test mirati di questa indagine: **38/38 PASS** (4 + 9 + 6 + 9 + 3 + 7). Non sono esecuzioni LLM reali.

È ora disponibile `src/evaluation/rq2_v3_offline_provenance_journal_prototype.py`: prova di persistenza create-only **non produttiva**, che genera da sola una `TemporaryDirectory` e non accetta un percorso dati utente, non apre Google Drive, non legge GT, non costruisce SDK, non crea release e non può eseguire API. Verifica rilettura e hash canonici, dipendenze D→C→K, propagazione `BLOCKED_DEPENDENCY`, nessun retry, blocco di claim orfani e conservazione/validazione di `text_extraction` nei record C/K. È presente il test `src/tests/test_rq2_v3_offline_provenance_journal_prototype.py` con 7 prove **in attesa di esecuzione PyCharm**.

**Limite essenziale:** il prototipo usa gli stage ID del piano V2 unicamente come *fixture sintetiche*, non può scrivere dati scientifici permanenti e non è una release V3. Prima del futuro protocollo reale servono: nuovi identificatori protocollo/piano e namespace, release autorizzata, hash source-bound per **tutti** i componenti, commit clean, gestione di lock e crash su Drive, test e policy uniformi su D e C/K, budget e autorizzazioni di singolo stage. Vietato usare il prototipo per scrivere nella directory scientifica V2.

## Requisiti GO/NO-GO prima della futura campagna reale

1. **GO tecnico:** nuovi test passati e controlli anti-regressione selettivi su trasporto, parser, output-contract, contatori, gestione errori e no-auto-retry.
2. **GO scientifico:** protocollo successore con identificatore, inventario SHA, source commit pulito, release, namespace create-only, matrici e criteri di scoring separati. No record V2 sovrascritti; nel report distinguere versioni, modalità di estrazione, validità JSON, astensione e K bloccati.
3. **GO comparabilità:** stessi prompt C/K e stessa policy di estrazione per Gemini/Sonnet/Haiku; stessi casi e harness. Non mescolare risultati da trasporti diversi nell'analisi primaria. Valutare su set accoppiati, conteggiando i fallimenti senza cherry picking.
4. **GO sicurezza:** nessun accesso GT/Market.zip/scorer nella discovery e nessuno degli 11 OOD sbloccato; un solo writer, claim prima della chiamata, zero retry automatici, budget USD 100 operativo NON hard cap, approvazione separata per esatta singola stage.
5. **NO-GO attuale:** i 19 test su mock non rendono ancora il nuovo trasporto live-capable; una nuova release e una nuova persistenza devono essere deliberatamente progettate. Non avviare D/C/K pagati durante l'audit.

## Questioni da decidere prima del nuovo freeze

- Coorte V2 precedente: il pilot D valido e C invalido con K bloccata devono restare un **pilot storico separato**. Qualunque confronto primario del successore deve usare la sua stessa versione metodologica per ogni braccio; eventuale riuso di D vecchi richiede una regola preregistrata esplicita e audit di equivalenza, oppure si riparte con un nuovo D nel protocollo successore. Non decidere implicitamente.
- Provenienza dei content block: nel successore conservare solo diagnostiche non sensibili (`content_kind`, `text_blocks`, `nontext_blocks`, `content_extraction_policy`), con verifica source-bound. Non salvare thinking/signature.
- Le valutazioni di validità strutturale, spiegazione causale, astensione, qualità regola K e consumo token vanno riportate separatamente. Discovery è GT-free e non prova correttezza causale.

**Nessuna modifica ai risultati o a release/protocollo RQ1/RQ2-V2 originale.**
