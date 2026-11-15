# RQ2-V2 Opzione A — decisione budget operativo (NON consenso API)

**Data dichiarata:** 15 novembre 2026, conversazione di continuità della tesi OpenRCA.

## Decisione ricevuta

L'utente, dopo la proposta esplicita **"Confermi 100 USD come budget operativo della campagna RQ2-V2 Opzione A, oppure preferisci un altro importo? Questa decisione riguarderebbe soltanto il budget e la preparazione del manifesto. Non autorizzerebbe ancora nessuna chiamata API"**, ha risposto: **"si come ti dicevo il budget per il professore non è un problema"**.

Interpretazione operativa circoscritta: **budget di pianificazione e operatività approvato = USD 100.00 per tutta l'Opzione A** (60 D + 60 C + 60 K pianificati, fino a 180 stage logici). Nessuna riduzione arbitraria del protocollo per risparmiare. Questa decisione non approva spesa illimitata, non modifica il protocollo e non equivale a hard cap del fornitore. Qualsiasi eventuale aumento oltre USD 100.00 richiederà un consenso nuovo.

## Cosa questa decisione NON autorizza

- Nessuna chiamata Google/Anthropic, nessuna attivazione `LIVE_API_ENABLED` o `SCIENTIFIC_RELEASE_WRITE_ENABLED`.
- Nessun `release_v1.json`, `claim` o record in `data/rq2_v2_unified_scientific_v1`.
- Nessuna approvazione del **digest SHA-256 canonico** della release (non ancora costruita); il digest non è una firma personale.
- Nessun consenso per il primo stage `rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:D` (necessario successivamente, separatamente).
- Nessuna autorizzazione per i restanti 179 stage né per gli 11 test OOD dell'Opzione B.

La stringa del futuro `approval_reference` dovrà essere **reale, tracciabile e approvata** in relazione al manifesto finale; non va inventata né sostituita con un nome di fixture. La decisione attuale può essere citata come **evidenza di budget**, non come approvazione di release o API.

## Policy operativa suggerita, ancora da ratificare con la release

1. Eseguire **solo un pilot D** autorizzato indipendentemente, poi STOP obbligatorio per audit di token, costo osservabile e eventuali errori.
2. Conservare stato, token e usage completeness; nessun retry automatico e nessun recupero automatico dei claim orfani. Se costo non misurabile o provider in errore, stop per revisione.
3. Prima di ogni batch autorizzato, verificare costo cumulativo osservato/ricostruibile e tariffe correnti; sospendere le nuove chiamate quando il consumo cumulativo raggiunge **USD 100.00** o se la proiezione del prossimo batch potrebbe superare l'importo, salvo nuova approvazione. In mancanza di metering certo non proseguire alla cieca. Il limite **non** è un hard cap fisico della fatturazione e non può impedire un eccesso dovuto a una richiesta già in corso.
4. Nessun cambio della coorte, dei 5 harness, dei 3 modelli, di D/C/K, prompt o della rubrica K per il budget.

## Evidenza tecnica già congelata, da NON ripetere inutilmente

- Git sorgenti Colab preflight G4L clean: `5fa6a4af36821e5c038cf9b4f22237cb3326d9cc`.
- `source_inventory_sha256=205f6dd4c6fc89af4ec69bf64f4d4ad85d4416a67d6f28d5899212d1eb457c4d`.
- `blueprint_sha256=13cac143d4eea5aad297d0b642e358f55d5f50ae53a8622e44fa488d6de7f3e7`.
- G4L 9/9, G4F 22/22 test mirati PASS; runtime e 30 sorgenti reali GT-free PASS.
- `SCIENTIFIC_RELEASE_WRITE_ENABLED=False`, `LIVE_API_ENABLED=False`; release SHA null, 0/180 stage reali, 11 OOD locked.
- Prossima azione tecnica distinta: preparazione/riesame **versione finale attivabile** su commit dedicato, con test e source audit richiesti per i sorgenti effettivamente modificati; poi proposta di release G4E e consenso SHA separati prima di qualsiasi creazione o API.

**Nessuna API invocata, nessuna release creata e nessun file sperimentale modificato** con questa annotazione.
