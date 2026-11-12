# RQ2 — Rehearsal end-to-end claim/recorder e registro delle decisioni prima del freeze

**12 novembre 2026** · Branch `feature/ood-knowledge-transfer-audit-2026-11-10`. **Non è un protocollo congelato; nessuna API chiamata.** I nuovi test di questa sezione NON sono ancora stati eseguiti dall'utente.

## 1. Verificato in PyCharm

L'utente ha riportato:

```
Ran 20 tests in 2.310s

OK
```

Si tratta della suite `test_rq2_discovery_claim_journal.py`: conferma **20/20 test sintetici**, inclusi claim senza risultato, crash, blocco duplicati, dipendenze e isolamento fase test. Non è una prova reale con Gemini/Claude né un'autorizzazione a chiamarli.

## 2. Nuova prova di integrazione senza creare un altro runner

File aggiunto: `src/tests/test_rq2_claim_recorder_end_to_end.py`.

**16 nuovi metodi unittest** (contati come `TestCase.test_*`), che riutilizzano *direttamente*, senza copiare la logica di produzione:
- `RQ2DiscoveryClaimJournal.claim_stage` per i claim create-only, uno per stage;
- `RQ2DiscoveryStageRecorder.record_d/record_c/record_k` per gli esiti e le dipendenze;
- `RQ2StageArtifactStore.audit_restart/load_discovery_stage` per il controllo hash alla ripresa.

Usano **solo un piano e due CSV sintetici in una directory temporanea**; le costanti SHA e la verifica `preview_market` sono monkeypatchate **esclusivamente nel file di test**. Non vengono aperti `Market.zip`, `query.csv`, `record.csv`, scorer, GT o API, e non vengono mai usati i 15 dati incidenti OOD reali.

**Scenari di controllo:** D→C→K complete con 3 claim e 3 artefatti; associazione dei digest delle dipendenze; nessuna ripetizione dopo il completamento; claim D senza risultato dopo disconnessione; claim C senza risultato e conseguente blocco K; errori provider D/C con `BLOCKED_DEPENDENCY` senza nuovi claim; JSON C invalido conservato; D finale in JSON invalido con osservazioni comunque valide per C; `insufficient_evidence` K non trattato come errore provider; tentativi C/K fuori ordine; modello errato; blocco test; claim corrotto; cambio dei manifest dopo l'inizializzazione.

Il mock non simula la complessità interna di `run_experiment`, l'autenticazione provider, le limitazioni rate limit o il contenuto fisico della telemetria. Non è il driver live e non costituisce prova di disponibilità modelli.

## 3. Decisioni scientifiche — stato e confini

| Oggetto | Proposta coerente con le evidenze già disponibili | Stato |
|---|---|---|
| Materiale RQ1 | Lasciare immutati protocollo, esiti e scorer RQ1 (Evaluation20 295 validi + 5 errori provider) | **Vincolo invariabile** |
| Partizione | 4 discovery singleton, 11 test raggruppati in 10 finestre; test multi-fault `cloudbed-1_q014`/`q030` nella stessa unità | **Validata GT-free, da pre-registrare** |
| Design RQ2-A | 2 harness `A1`/`A1_8R`, 3 modelli (Gemini/Sonnet/Haiku), 90 D e 90 C; valutazione appaiata e GT isolato | **Da congelare** |
| RQ2-B | 24 K solo discovery, inclusi errori e astensioni nel denominatore | **Da congelare** |
| RQ2-C | Valutazione deterministica **offline** delle sole regole K tecnicamente formalizzabili e congelate *prima* del test, su 10 gruppi di finestre; nessuna selezione a posteriori | **Protocollo da definire** |
| Modelli | `gemini-3.5-flash-lite`, `claude-sonnet-5-5`, `claude-haiku-5-5`; factory RQ1 attuale e parametri esatti per chiamate C/K da registrare | **ID candidati, non frozen** |
| D | Riutilizzare il codice RQ1 `run_experiment(config, salva=False)`; `max_tool_rounds=6`, `variant_scheme=current` | **Interfaccia verificata; output_contract_mode da fissare** |
| D JSON non valido | Conservare comunque la D con traiettoria osservativa valida; C usa solo evidenze tool e istruzione originale, senza final answer D | **Decisione implementativa, da preregistrare prima delle API** |
| C e K | Prompt già codificati in `rq2_probe_adapter.py`, niente tool, esiti JSON stretti o astensione; hash prompt da congelare | **Funzioni offline pronte; chiamata provider non implementata** |
| Metriche K | 29/29 KPI già elencati riscontrati come dati numerici nel *development*, 94 nomi extra; unità e semantiche fisiche non certificate | **Catalogo operativo/freeze ancora aperto** |
| Budget | **Nessun tetto economico richiesto**, secondo indicazione del relatore riferita dall'utente. Registrare sempre usage/costo, errori e numero chiamate | **Decisione dell'utente registrata** |
| Claim/retry | Create-only prima di ogni futura richiesta; claim senza risultato è **manual review**, non retry automatico; nessun rilancio arbitrario | **Guardie testate offline** |
| Human in the loop diagnostico | Non implementare, su indicazione del professore; eventuale riflessione nei limiti della tesi | **Vincolo invariabile** |

La `manual review` di un **crash/infrastruttura**, per determinare se una chiamata è stata inviata, non va confusa con un sistema *human-in-the-loop* per risolvere incidenti OpenRCA o correggere diagnosi; il secondo rimane **fuori scope**.

## 4. Quali problemi rimangono per il pilot reale

Non serve più definire un tetto monetario, ma devono essere verificati prima di usare la rete:
1. **Parità D con RQ1:** selezionare e registrare il valore esatto di `output_contract_mode` e la modalità dei prompt, senza modificarli in base agli esiti OOD.
2. **Versionamento statico:** commit del ramo, pacchetti, ID modelli reali, parametri Anthropic/Gemini, SHA dei prompt C/K, schema output e policy di gestione errori; nessun retry silenzioso.
3. **Orchestratore scientifico effettivo:** sostituire le *fixture* con un vero `run_experiment(..., salva=False)` per D e chiamate C/K **senza tool**, con contatori token/usage e output grezzi create-only. Una prova con fake backend/LLM è necessaria prima della prima chiamata reale.
4. **Isolamento test:** proibire ogni stage test fino al freeze discovery e catalogo KPI; differenziare il freeze scientifico dai mock.
5. **Crash recovery:** decidere ex ante come trattare claim incompleti; la barriera anti-duplicato non deve diventare perdita silenziosa di denominatori.
6. **Confronto scientifico:** risultato RQ2-A su C, non equiparare a D; per RQ2-C dichiarare interpretazione operativa/raw vs fisica e valutazione multi-label per gruppi.

**Nessun task di refactoring cosmetico** finché non sono conclusi esperimenti e tesi. Le modifiche ai documenti precedenti sul budget sono superate dal §50 del registro di continuità.

## 5. Test successivo

PyCharm PowerShell, dalla root repository:

```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_claim_recorder_end_to_end.py" -v
```

**Attesi 16 test. Esito ancora non confermato.** Dopo i test, chiudere le decisioni del protocollo tecnico e implementare soltanto le parti mancanti del vero runner, senza cambiare il motore RCA.
