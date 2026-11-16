# RQ2-V4 — Task-aware D validator, versione DRAFT (15 novembre 2026)

**Nessuna API, nessun nuovo claim/record, nessuna nuova release.** Il codice di V3 e gli esperimenti congelati restano intatti.

## 16 novembre 2026 — Primo esperimento REALE V4 Gemini A0 D: RECORDED_COMPLETE

**ESITO USER-REPORTED (Colab, 16/11/2026):** `SOURCE_COMMIT_PIN_CLEAN: OK`, `GEMINI_CREDENTIAL: PRESENT`, `PILOT_RETURN_CODE: 0` e `AUDIT_RETURN_CODE: 0`. Primo stage scientifico V4 **eseguito UNA sola volta**: `rq2_v4_task_aware_d_discovery_v0:cloudbed-1_q032:gemini:A0:D` / `gemini-3.5-flash-lite` / harness `A0`, source pin `78734fa130369d7c236ec53c0cc25d88c8860b27`, release V4 `52e5b25cd71f3621d69b1e979a4457cd741242bddff3f49eae936588196330be`.

- Dispatcher: `status=V4_ONE_STAGE_RECORDED`, `record_status=RECORDED_COMPLETE`, `record_sha256=345ebe4bd64ecbc1958988262d677aae76ec977e6001dec52a1cc7b02d921e4f`, `descendants_blocked=[]`, `claims_created=1`, `automatic_retry_allowed=false`.
- Audit indipendente READ-ONLY: `claims=1, records=1, orphans=0`, stage claim presente, stage record `RECORDED_COMPLETE` e SHA identico; `task_index=task_2`, `task_contract_valid=true`, `json_status=valid_json`.
- Consumo osservato D: `llm_calls=7`, `input_tokens=40570`, `output_tokens=394`, `token_usage_complete=true`. Non inferire fattura o cap USD: budget precedente USD 0.10 era operativo, NON hard cap.
- **Conclusione limitata ma importante:** V4 task-aware ha accettato correttamente l'output formale del task_2 nel primo esperimento live. Non dimostra ancora correttezza causale, efficacia K, trasferimento OOD o generalizzazione a 15 combinazioni. RQ1 e V3 restano congelati.
- **MAI RITENTARE D**: il claim e il record esistono già e sono intoccabili. Non pulire/rimuovere/riclassificare il record. Il protocollo source commit e release SHA restano congelati.

**PROSSIMO STEP:** preflight **solo lettura** dell'adiacente stage `rq2_v4_task_aware_d_discovery_v0:cloudbed-1_q032:gemini:A0:C` via `preview_one_v4_stage` con ledger/source/release verificati. Controllare che D parent sia `RECORDED_COMPLETE` con hash esatto, che C e K non abbiano claim/record, che audit iniziale e finale rimanga `claims=1, records=1, orphans=0`, pacchetto C con SHA/prompt verificati, zero API e zero scritture scientifiche. Non utilizzare OOD. Successivamente, se PASS, preparare singolo stage C real con autorizzazione limitata, senza rieffettuare D. Evitare ulteriori PyCharm test già passati. `OPENRCA_RQ2_V4_ENABLE_PAID_SINGLE_STAGE` deve restare unset nel preflight. Mai aggiornare checkout frozen.

## 16 novembre 2026 — Consenso utente al primo pilot V4, non ancora eseguito

L'utente ha risposto: «sì autorizzo sempre non c'è bisogno che me lo chiedi», in risposta alla proposta puntuale di **un solo** stage V4 `rq2_v4_task_aware_d_discovery_v0:cloudbed-1_q032:gemini:A0:D` su `gemini-3.5-flash-lite`, con budget operativo di riferimento **USD 0.10 non hard cap**, massimo 6 tool rounds, no automatic retry. Questa autorizzazione concreta è acquisita per il primo stage. Non chiedere nuovamente il consenso per esso; non trasformare la frase di disponibilità generale in un'autorizzazione di spesa illimitata o di pilot su altre combinazioni senza vincoli e identificativi espliciti.

Verifica read-only del codice al source pin scientifico `78734fa130369d7c236ec53c0cc25d88c8860b27`:
- `src/evaluation/experiment_runner.py` usa `enforce_task_output(..., output_contract_mode="v2_enforce")` dopo il vecchio parser, e quindi aggiorna `prediction/json_status/output_contract_v2`; `src/evaluation/rq2_v4_d_task_aware_contract.py` valida il JSON e i soli campi del task, con identica funzione nel readback.
- La V4 si applica al piano 5 harness × 3 provider-modelli × 4 casi; i 55 test precedenti sono sintetici/offline, non certificano ancora 15 percorsi di provider reali.
- C/K riusa il validatore V3 per il *proprio* contratto C/K ed evidence bundle; la relativa branch `_validate_artifact` per C/K non pretende tutti i tre campi nel D parent, ma richiede `d_record.status="RECORDED_COMPLETE"` e provenance.
- Procedere con una cella Colab che imposti opt-in **solo nel subprocess del primo stage**, binding a source commit/release SHA congelati, consenso `ONE_V4_STAGE_CLAIM_ONLY`, per un unico tentativo `run_one_v4_stage`. Claim create-only precede chiamata SDK; se eccezione dopo claim, **non ripetere**: audit read-only e review manuale, non cancellare file/claim.
- Il costo di USD 0.10 è solo budget di riferimento senza cap; D può avere più chiamate modello (fino ai tool round del grafo). Non autorizzare automaticamente altri stage.
- Non è stata ancora effettuata alcuna chiamata a pagamento V4 in questa conversazione. Release V4 rimane il freeze SHA `52e5b25cd71f3621d69b1e979a4457cd741242bddff3f49eae936588196330be`.

## 16 novembre 2026 — Primo D V4: preflight read-only PASS, nessuna API

Risultato restituito dall'utente in Colab:
```json
{
  "status": "V4_GEMINI_A0_D_READONLY_PREFLIGHT_PASS",
  "stage_id": "rq2_v4_task_aware_d_discovery_v0:cloudbed-1_q032:gemini:A0:D",
  "model_id": "gemini-3.5-flash-lite",
  "source_commit": "78734fa130369d7c236ec53c0cc25d88c8860b27",
  "release_sha256": "52e5b25cd71f3621d69b1e979a4457cd741242bddff3f49eae936588196330be",
  "max_tool_rounds_D": 6,
  "claims_before": 0,
  "claims_after": 0,
  "records_before": 0,
  "records_after": 0,
  "orphans": 0,
  "ood_locked": 11,
  "real_llm_calls": 0,
  "can_execute_api": false
}
```

Processo `RETURN_CODE=0`, `V4 D PREFLIGHT PASS — NESSUNA API ESEGUITA`. Ha costruito ledger V4 con verifica della release e prova runtime, controllato stage e istruzione GT-free, nessun claim/record.

**PROSSIMO PASSO: richiedere approvazione *esplicita* dell'utente per ESATTAMENTE questo nuovo stage V4 Gemini A0 D, budget operativo suggerito USD 0.10 (non hard cap), una sola esecuzione senza retry.** Nessuna autorizzazione è stata ancora acquisita per V4; `can_execute_api=false` in preflight è intenzionale. Non fare partire il pilot, creare claim o invocare il modello prima dell'approvazione. Dopo approvazione eseguire il dispatcher congelato V4 senza aggiornare il checkout/commit scientifico.

## STATO ATTUALE CERTIFICATO — V4 SCIENTIFIC FREEZE PASS (16 novembre 2026)

**Questa sezione aggiorna/supera le istruzioni storiche “V4 draft/no release” presenti più sotto. Non eseguire le vecchie celle di creazione release, né ripetere freeze o test senza motivo.**

- Branch del codice: `feature/rq2-v4-task-aware-ledger-2026-11-15`. **Commit scientifico esatto, da NON cambiare:** `78734fa130369d7c236ec53c0cc25d88c8860b27`. Ulteriori commit docs-only non sostituiscono il pin.
- Protocollo: `rq2_v4_task_aware_d_discovery_v0`. **Plan SHA-256** `ddba5cd92795e92e196d69cd5cc13df85eec91e9c18913561356f268127deec7`.
- **Source inventory SHA-256** `a88ff23870c18836d375b3d6b222d00b91fa275a57eec3f19bae913ce0670633` (sei sorgenti V4 + futuro dispatcher separato, V2/V3 sorgenti e dati GT-free senza GT).
- **Runtime attestation SHA-256** `192133f40fdf247fa5cfd6c6b2cfd59b23d53fea73d9e64f3d8151ad2c90ff9c`: 4 invii HTTP 429 sintetici, 4 timeout loopback, lock/O_EXCL Drive nel *medesimo* Colab; SDK versioni e sorgenti esatte. Non dimostra altri Colab, timeout di intero stage o hard cap USD.
- **Release V4 SHA-256 confermata** `52e5b25cd71f3621d69b1e979a4457cd741242bddff3f49eae936588196330be`.
- Directory dati in Drive: `/content/drive/MyDrive/Tesi_OpenRCA/data/rq2_v4_task_aware_scientific_v1/`; release create-only `release_v1.json`. Directory V3 separata e intatta.
- Checkout Colab V4 isolato: `/content/Tesi_OpenRCA_V4` a commit scientifico detached e clean; SDK isolati `/content/rq2_v2_pinned_sdk_py313` ripristinati nel runtime Python 3.13.18. **Non fare git pull in questo checkout e non modificare i sorgenti congelati.**
- V4 55/55 test offline mirati PASS riportati da utente: 20 task/piano +12 adapter/ledger +10 release gate +13 dispatcher.
- La prima prova Colab `V4_READONLY_SOURCE_RUNTIME_PREFLIGHT_PASS` ha confermato 180 stage (4 discovery × 5 harness × 3 modelli × D/C/K), 11 casi OOD locked, 0 release/claim/run.
- La seconda prova Colab `V4_RUNTIME_PROOF_PASS_RELEASE_CANDIDATE_ONLY` ha calcolato candidate release SHA e runtime attestation senza creare release/claim/API.
- **La release è stata poi effettivamente creata una sola volta**: processo 1 `V4_RELEASE_CREATE_ONLY_READBACK_PASS`, `RETURN_CODE=0`; processo 2 distinto `V4_SCIENTIFIC_FREEZE_INDEPENDENT_AUDIT_PASS`, `RETURN_CODE=0`, proof `V4_SOURCE_BOUND_RELEASE_VERIFIED`, ledger `V4_SCIENTIFIC_LEDGER_READBACK_AUDITED`, **claims=0, records=0, orphans=0**. `real_llm_calls=0`. Il flag `can_execute_api=false` in release/proof è intenzionale e non è un'autorizzazione.

**Prossima e unica attività:** preflight **read-only** stage V4 `rq2_v4_task_aware_d_discovery_v0:cloudbed-1_q032:gemini:A0:D`, usando `preview_one_v4_stage` del dispatcher, dopo aver istanziato `V4ScientificLedger` e verificato claims/records/orphans=0. La preview può leggere istruzione GT-free ma non GT né telemetria; non deve creare claim/record o chiamare API. Eseguire in processo separato privo di credenziali e senza `OPENRCA_RQ2_V4_ENABLE_PAID_SINGLE_STAGE`. Se NO-GO fermarsi, non ripetere esecuzioni live. Il successivo vero pilot (a pagamento) necessita *nuovo consenso esplicito per stage, modello e budget operativo*, con `run_one_v4_stage` attualmente default disabled. Nessuna nuova API autorizzata ora.

**Pulizia finale:** dopo la campagna, separare artefatti/prototipi dal codice di consegna tramite archivio/branch/tag con SHA, non cancellare storia e prove congelate. Migliorare commenti in italiano e struttura su branch successivo, non sul commit scientifico.

## Evidenza e motivazione

Il primo e unico pilot reale V3 `rq2_v3_unified_equal_ck_extraction_discovery_v0:cloudbed-1_q032:gemini:A0:D` (release SHA256 `dae141c0dd7231cc172ef891299367df85adf2618be0b0c7882336ee585b1c04`; code commit `8f8b39e480db1296de155068c001d17ae05ac6ad`) ha prodotto:
- `D=INVALID_OUTPUT`, `C=K=BLOCKED_DEPENDENCY`, `claims=1, records=3, orphans=0`;
- `json_status=valid_json`, `output_contract_v2.valid=true`, `provenance_ok=true`, una sola componente testuale e nessun blocco non testuale;
- task `task_2`, campo richiesto soltanto `root cause reason`, presente; mancano `root cause occurrence datetime` e `root cause component` **non richiesti**.
- V2/V3 ledger `_validate_artifact` impone indiscriminatamente tutti e tre i campi in `RECORDED_COMPLETE`, causando falsi `INVALID_OUTPUT` formali. La diagnosi non è stata confrontata con la GT e non si conosce la correttezza causale.

**Il record V3 originale resta immutato; nessuna sua riclassificazione o replay.**

## Implementazione nuova, in nuovo branch

Branch: `feature/rq2-v4-task-aware-ledger-2026-11-15`.

Aggiunti (senza modificare file RQ1/V2/V3):

1. `src/evaluation/rq2_v4_d_task_aware_contract.py`: validazione D condivisa per futuro classificatore e futuro readback. Richiede output originale e prediction canonica coerenti, audit `v2_enforce`, task `task_1..task_7`, campi realmente richiesti, cardinalità, ID sequenziali, assenza duplicati JSON, date richieste valide e ordine cronologico. Mantiene validi campi extra secondo V2.4. `classify_v4_d` preserva audit provenance D prima di `RECORDED_COMPLETE`; `require_v4_d_status` usa la stessa implementazione per readback. Errori runner/provider sono segregati e NON diventano `INVALID_OUTPUT`.
2. `src/tests/test_rq2_v4_d_task_aware_contract_offline.py`: **17 test aggiunti, da eseguire** (non chiamarli PASS prima del risultato): tutti e sette i task, regressione task_2, campi extra, failure JSON, indici, cardinalità, timestamp, cronologia, prediction, audit e provenance, classificazione vs readback.
3. `src/evaluation/rq2_v4_unified_gtfree_discovery_plan.py`: nuovo protocollo `rq2_v4_task_aware_d_discovery_v0`; namespace `data/rq2_v4_task_aware_scientific_v1`; **180 stage** su quattro discovery × cinque harness × tre modelli × D/C/K; 11 OOD esclusi; senza lettura dei risultati V3; release inesistente e API non autorizzata.
4. `src/tests/test_rq2_v4_unified_gtfree_discovery_plan_offline.py`: **3 test aggiunti, da eseguire**: coorte, namespace, identity di harness/modelli e OOD.

## Aggiornamento 16 novembre 2026 — Adapter e ledger V4

L'utente ha eseguito e riportato **`Ran 20 tests in 0.301s — OK`** per i 17 test del contratto D + 3 test di piano V4. Non chiedere di ripeterli senza motivo.

Sono stati poi aggiunti soltanto NUOVI file, da testare:
- `src/evaluation/rq2_v4_scientific_receipt_adapter_candidate.py`: D `normalize_v4_d_capture` usa `classify_v4_d`; la convalida `validate_v4_scientific_artifact` sullo stesso documento usa `require_v4_d_status`. I metadati di estrazione V3 sono immutati. C/K riusa solo il codice puro V3 tramite mappatura degli stage ID, **mai risultati V3**, mantenendo provenance/contratto C/K.
- `src/evaluation/rq2_v4_scientific_ledger.py`: indipendente, derivato dalla logica ledger V3 congelata ma con namespace, protocolli, receipt, percorsi, claim/record create-only, lock, hash, readback e status tutti **V4**. Include `data/rq2_v3_unified_scientific_v1` fra le sorgenti storiche da non toccare (controllo symlink only). Il ledger è **hard NO-GO** senza una futura release V4 verificata, perché il gate V4 attuale è esplicitamente bloccante.
- `src/evaluation/rq2_v4_scientific_source_release_gate.py`: placeholder esplicito, ogni verifica solleva `V4SourceReleaseBlocked` (nessun claim, nessuna API). Il prossimo intervento dovrà implementare il vero gate indipendente con pin di source/release/runtime/Drive.
- `src/tests/test_rq2_v4_adapter_ledger_offline.py`: **12 nuovi test, NON ancora eseguiti**; usano solo dati sintetici e TemporaryDirectory con mock dichiarato del gate V4 per testare adapter, ledger, immutabilità, no-retry e status tamper. Il gate reale resta NO-GO.

**Prossimo comando PyCharm** sul branch V4 aggiornato, con `git status --short` pulito:
```powershell
git pull --ff-only origin feature/rq2-v4-task-aware-ledger-2026-11-15
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v4_adapter_ledger_offline.py" -v
```
Non ripetere ora i 20 test già PASS. L'utente riporterà `Ran 12 tests...` o traceback; se errore, correggere *solo* il nuovo codice V4 con commit tracciabile. Nessun Colab o API.

## Aggiornamento 16 novembre 2026 — 32/32 offline PASS, nuovo gate source/release

L'utente ha riportato `Ran 12 tests in 1.068s — OK` per `test_rq2_v4_adapter_ledger_offline.py`; sommati ai 20 precedenti **32 test V4 mirati PASS**. Non chiedere di ripeterli senza necessità. Tutti sintetici/offline, non certificano i limiti della rete reale.

Nuovi file V4 e codice aggiornato da testare:
- `src/evaluation/rq2_v4_scientific_source_inventory.py`: nuovo inventario immutabile che ricontrolla solo sorgenti/manifest GT-free attraverso V3/V2 (NON record o release V3), poi SHA dei sei file V4 esistenti. `FUTURE_REQUIRED_PATHS` include il dispatcher V4 ancora assente; `missing_future_paths` è esplicito.
- `src/evaluation/rq2_v4_scientific_source_release_gate.py`: gate implementato (sostituisce placeholder) richiede release V4 GIÀ creata create-only, commit Git pulito esterno, SHA release esterno, 180 stage/11 OOD, hash di sorgenti V2/V3/V4 e futuro dispatcher, identità di prompt/modelli/policy, attestazione SDK/Drive del medesimo runtime. **Riutilizza il verificatore di trasporto/runtime V3 congelato come codice**, con nuovo commit/inventory V4; NON riutilizza file dati/risultati V3. `can_execute_api=false` sempre. Finché il dispatcher e release non esistono, il gate reale è **NO-GO**.
- `src/tests/test_rq2_v4_scientific_source_release_gate_offline.py`: **10 nuovi test da eseguire** con fixture sintetiche e mock espliciti; per errori di SHA, commit, history, OOD, dispatcher mancante, runtime attestation. Il PASS di questi test NON equivale a freeze reale o proof live.

**Prossimo comando PyCharm**, se working tree pulito, sul branch V4:
```powershell
git pull --ff-only origin feature/rq2-v4-task-aware-ledger-2026-11-15
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v4_scientific_source_release_gate_offline.py" -v
```
Non ripetere i 32 precedenti; attendere output 10 test. Non eseguire Colab o API.

**Pulizia finale richiesta esplicitamente dall'utente:** dopo il completamento sperimentale, creare un layout finale pulito e refactoring/commenti italiani, ridurre prototipi e file inutili nel codice attivo **senza distruggere evidenze, release, risultati congelati e sorgenti/commit necessari a riprodurre RQ1/RQ2**. Valutare archiviazione tag/branch/manifest prima di ogni eliminazione. Non anticipare il cleanup ora perché cambia gli SHA scientifici.

## Aggiornamento 16 novembre 2026 — Dispatcher V4 creato, 13 nuovi test non eseguiti

Dopo il precedente batch PyCharm, l'utente ha riportato `Ran 10 tests in 0.343s — OK` per `test_rq2_v4_scientific_source_release_gate_offline.py`. Totale **42/42 test V4 mirati PASS**, sino a questo punto. Non rieseguirli se non richiesto da una modifica che li coinvolga.

Aggiunte nuove, ancora da testare:
- `src/evaluation/rq2_v4_scientific_single_stage_dispatcher.py`: dispatcher a **singolo stage V4** (D/C/K distinti), derivato solo come codice dal dispatcher V3 (non riusa suoi claim/record). `LIVE_OPT_IN_ENV=OPENRCA_RQ2_V4_ENABLE_PAID_SINGLE_STAGE` catturata all'import; valore esatto `EXPLICIT_V4_ONE_STAGE_ONLY_V1`. `run_one_v4_stage` richiede Stage ID, approval reference, model ID, commit/release SHA, budget operativo non hard cap, `confirm_paid_api=True`. Registra claim create-only prima di ogni singolo stage; D usa `normalize_v4_d_capture` task-aware, C/K mantengono la grammatica e provenance già prevista; nessun retry, nessun OOD. Su D/C non valido discendenti bloccati senza nuove API; se errore ambiguo dopo claim, lascia orphan per revisione manuale.
- `src/tests/test_rq2_v4_single_stage_dispatcher_offline.py`: **13 nuovi test NON ANCORA ESEGUITI**; mock sintetici per opt-in, approvazione, budget, ID OOD/V3, provider fake, ordine claim→provider→record, blocco C/K, orphan, nessun retry.

**Il gate reale non può ancora aprirsi**: non esiste una release scientifica V4 create-only e manca la source/runtime attestation in Colab V4. Scrivere il modulo dispatcher NON concede autorizzazione a pagamento. Il precedente consenso V3 è esaurito.

Prossimo comando unico PyCharm (branch V4, working tree pulito):
```powershell
git pull --ff-only origin feature/rq2-v4-task-aware-ledger-2026-11-15
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v4_single_stage_dispatcher_offline.py" -v
```
Riportare `Ran 13 tests...` ed eventuali errori. Non chiedere di ripetere 42 test già PASS.

## Aggiornamento 16 novembre 2026 — Dispatcher 13/13 PASS, totale V4 55/55

L'utente ha eseguito su PyCharm i 13 test nuovi `test_rq2_v4_single_stage_dispatcher_offline.py`: `Ran 13 tests in 0.254s — OK`. **Risultati cumulativi V4: 20+12+10+13 = 55 test offline PASS**. Non rieseguire questi test senza motivazione specifica.

Sorgenti V4 del branch `feature/rq2-v4-task-aware-ledger-2026-11-15` pronti per la **prima verifica read-only in Colab**. La release V4 non è stata creata, nessuna credenziale/provider API autorizzata; il precedente consenso V3 era per un singolo tentativo già consumato.

Procedura:
- NON modificare il checkout Colab V3 `/content/Tesi_OpenRCA` congelato. Usare un clone distinto `/content/Tesi_OpenRCA_V4` a commit V4 esatto e pulito, con dataset GT-free in `/content/drive/MyDrive/Tesi_OpenRCA`, SDK isolati già disponibili in `/content/rq2_v2_pinned_sdk_py313`.
- Verificare sola lettura `build_offline_v4_discovery_plan` (180 stage, 11 OOD, nessun riuso output V2/V3) e `preview_v4_scientific_source_inventory` (sorgenti V2/V3/V4, prompt, manifest/split, dispatcher presente, digest canonico), ed eventualmente `preview_v3_live_runtime` sul **nuovo commit V4**, soltanto come codice di verifica SDK, non come prova della nuova release.
- Solo dopo `PASS` fare proof runtime SDK/Drive (scratch) e creare release V4 **create-only** in namespace separato, con readback, hash esterno e zero API, preservando V3.
- Prima di lanciare ogni pilot a pagamento V4 serve consenso nuovo per singolo stage, modello e budget operativo; nessuna approvazione implicita.
- **Pulizia codice dopo la campagna**, previa archiviazione/version tagging di release e risultati; evitare refactoring del frozen source commit.

## Stato e NO-GO

- La V4 è ancora **offline e non rilasciata**. Adapter V4 e ledger V4 sono stati implementati; il source/release gate è un NO-GO intenzionale; dispatcher V4 implementato ma in attesa dei suoi 13 test mirati; manca la release create-only e il freeze source/runtime. Nessuna nuova API o campagna autorizzata.
- Il controllo V4 di `expected_faults` usa l'audit già registrato nel runner. In fase di integration/readback source-bound, bisognerà confrontarlo anche con l'istruzione GT-free originale e il manifest/split congelato, senza leggere GT.
- Il nuovo validatore NON deve essere sostituito con il validatore generale V2/V3 per D; invece i contratti C/K delle evidenze rimangono invariati.
- Nessun `git pull` nel Colab congelato V3 per provare questa bozza. Nessuna API, nessuna nuova release, nessun retry, nessun OOD.

## Prossima azione dell'utente: un solo batch mirato in PyCharm

Dopo aver verificato `git status --short` pulito, aprire il branch V4 e lanciare:

```powershell
git fetch origin
git switch -c feature/rq2-v4-task-aware-ledger-2026-11-15 --track origin/feature/rq2-v4-task-aware-ledger-2026-11-15
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v4_*_offline.py" -v
```

Se il branch è già disponibile localmente, usare `git switch feature/rq2-v4-task-aware-ledger-2026-11-15` anziché `-c`. Riportare il `Ran ... tests` e eventuali errori. Nessun test precedente da ripetere.

Dopo PASS: integrare il nuovo contratto nel futuro **V4 adapter + ledger** in un unico protocollo, con classificazione e verifica readback identiche, poi nuovi source inventory/release gate/runtime, test offline mirati e nuova release create-only. Prima di **ogni nuovo stage reale** servono nuovo consenso distinto, stage ID V4, commit codice V4 e release SHA nuova. Il precedente consenso V3 è esaurito.

## Priorità utente

Concludere RQ2 con ciclo D/C/K e verifica finale scientificamente difendibile prima di discutere con il relatore i capitoli; consegna corretta della tesi **5 dicembre 2026**. Chiedere appunti/paper solo se indispensabili. Preparare handoff GitHub quando la chat si prolunga.
