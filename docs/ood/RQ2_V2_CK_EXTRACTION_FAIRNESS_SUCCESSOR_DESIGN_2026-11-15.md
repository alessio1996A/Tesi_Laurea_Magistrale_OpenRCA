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
