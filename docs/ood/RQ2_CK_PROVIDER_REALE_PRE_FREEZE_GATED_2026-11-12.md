# RQ2 — Adattatore C/K per provider reali, con gate scientifico NON ancora rilasciato

**12 novembre 2026** — Nuovo codice disponibile su `feature/ood-knowledge-transfer-audit-2026-11-10`. **15 test di integrazione preparati, non ancora eseguiti dall'utente.** RQ1 resta congelata e intatta.

## 1. Punto di partenza, verificato dall'utente

La suite `src/tests/test_rq2_toolfree_fake_transport.py` è verde:

```
Ran 17 tests in 1.691s

OK
```

Questo dimostra che C/K dispongono di messaggi LangChain, hashing, tool-free, gestione eccezioni, blocchi contenuto e integrazione col journal con un *fake* LLM; non sono chiamate a Gemini o Claude. Il successivo adapter **introduce il collegamento concreto al factory RQ1** ma rimane intenzionalmente bloccato fino alla preregistrazione.

## 2. Nuovo codice e prova senza credenziali

### `src/evaluation/rq2_ck_provider_transport.py`

- `run_one_claimed_ck(data_dir,stage_id,confirm_paid_api=False)` è il futuro ingresso **C/K LIVE** e non invia nulla all'import. Richiede conferma esplicita per la chiamata, un file release originale `data/rq2/RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json` e il suo **SHA-256 immutabilmente PINNATO nel codice**. **Al momento `RELEASE_SHA256 = None`, quindi tutte le chiamate reali sono bloccate per definizione**. Un numero arbitrario o un finto file non possono aprire le API nella versione distribuita. Non è un'autorizzazione tramite budget economico.
- Il futuro release deve riportare `SCIENTIFIC_DISCOVERY_RELEASE`, la partizione esatta 4 discovery/11 test, harness `A1/A1_8R`, 3 ID modelli, `D_output_contract_mode=v2_enforce`, 6 round, recursion limit 30, `C_K_tool_calls_allowed=false`, hash dei due prompt system verificati e politica `NO_AUTOMATIC_RETRY`. Il **test resta comunque bloccato**.
- Lo stage source-bound deve avere `phase=discovery`, un output D immutabile `RECORDED_COMPLETE` con `output_contract_mode=v2_enforce`, modello corretto, stessa istruzione GT-free con SHA verificato; K richiede anche una C `RECORDED_COMPLETE` con identità binding D/C invariata. I prompt sono ricostruiti *soltanto* dai record D e C, mai accettati dal chiamante in input libero.
- Dopo controlli e identità, la funzione esegue **prima `journal.claim_stage(...)`** e **poi** crea il modello mediante `agent.model_factory.crea_modello(provider, model_id)` di RQ1, senza modificare i modelli o i parametri storici. Per C o K passa **una sola coppia `SystemMessage/HumanMessage`** a `invoke`, senza `bind_tools`, quindi al massimo una richiesta per stage (non sono previsti retry automatici).
- L'output modello `AIMessage` viene trattato come testo di risposta (escludendo blocchi thinking e firme tramite `testo_messaggio(...,solo_testo=True)`). Qualunque `tool_calls` diventa `PROTOCOL_ERROR` senza esecuzione. `usage_metadata` viene letto solo quando contiene contatori validi; `output_token_details.reasoning` o gli altri dettagli numerici sono mantenuti quando presenti, senza attribuzioni arbitrarie; valori mancanti restano null. Il codice salva la categoria dell'errore provider e l'eventuale codice HTTP numerico, **senza il messaggio dell'eccezione**, che potrebbe includere segreti o prompt.
- Un nuovo campo opzionale `transport_receipt` viene salvato nel **medesimo JSON create-only** della C o K da `RQ2DiscoveryStageRecorder.record_c/record_k`: ID esatto, provider, hash del prompt binding, hash della risposta, errore, tentativi, token osservati, durata, motivi di arresto e disabilitazione dei tool. Il recorder valida la corrispondenza contro lo stage e la risposta prima del salvataggio. Gli output già registrati con la vecchia interfaccia restano leggibili; il campo è additivo e obbligatorio nel percorso live.
- **Disconnessione:** claim persistente senza output = stato `unresolved_manual_review`. La funzione non esegue retry, non rimuove claim, non apre i test, non corregge JSON e non converte `PROVIDER_ERROR` in predizione valida. La creazione del client fallita prima di `invoke` viene registrata come errore tecnico; una chiamata inviata che fallisce può avere consumato token anche se i contatori mancano.
- **Budget:** nessun tetto USD preimpostato per decisione del professore riferita dall'utente; token e costi si rendicontano come KPI secondari. Il trasporto conserva token e dettagli ma **non calcola ancora un costo esatto provider-side**. La successiva rendicontazione dovrà includere costo tariffario e l'eventuale fatturazione reale, senza usarla come gate.

### `src/tests/test_rq2_ck_provider_transport.py`

**15 test nuovi, ancora da eseguire.** Per testare il percorso che in produzione è bloccato, i test creano **solo nella cartella temporanea** un release *falso* e applicano un **monkeypatch del suo hash esclusivamente nel processo unittest**. Inoltre sostituiscono `crea_modello` con un fake deterministico in memoria: **nessun SDK viene istanziato e nessuna chiamata API parte**.

I test provano: conferma e freeze assente bloccati, modifica release bloccata, D mancante, stage test rifiutato, drift del contratto D, chiamata unica C/K con `SystemMessage/HumanMessage` reali, token e risposta persistenti, eccezione 503/timeout senza leak di segreti, JSON invalido non riparato, richiesta tool respinta, missing usage nullo, duplicato prima della factory, ordine claim prima della factory, incoerenze token non dichiarate complete.

### PyCharm

```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_ck_provider_transport.py" -v
```

Attesi **15 test; non ancora verificati in PyCharm**. Se falliscono, diagnosticare il nuovo codice e correggerlo; **non modificare RQ1** e **non sbloccare il release** per farli passare.

## 3. Da completare prima del pilot Colab reale

Questa modifica è **necessaria ma non sufficiente** a eseguire la discovery:

1. Pre-registrare scientificamente protocollo, split, prompt/metriche KPI e policy di fallimenti/retries e salvare un release reale immutabile; cambiare `RELEASE_SHA256` solo dopo audit del release, con commit Git e hash verificati.
2. Preparare **il vero driver D**, che riusi `run_experiment(config,llm=None,salva=False)` in Colab con `output_contract_mode=v2_enforce`, e registri l'output nell'archivio RQ2; claim D sempre prima delle API.
3. Rendere coerenti i parametri provider, i prompt C/K e le versioni delle dipendenze; al primo avvio controllare credenziali/ambiente offline, SHA sorgenti ed error policy.
4. Una volta verificato il pilot reale, pianificare le 4 discovery, e soltanto **dopo freeze scientifico delle K**, usare gli 11 casi test; non modificare il denominatore 204 stage logici.
5. Separare scoring GT rigorosamente offline dai prompt, tool e processo di generazione delle regole. Non implementare human-in-the-loop diagnostico.

**Stato: RQ2 ancora non eseguibile via API.** Le prove con SDK fake non sono benchmark scores.
