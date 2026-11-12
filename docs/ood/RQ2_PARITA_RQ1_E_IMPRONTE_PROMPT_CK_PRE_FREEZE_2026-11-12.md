# RQ2 — Parità sorgenti RQ1 e impronte prompt C/K: prefreeze read-only

**12 novembre 2026** — **13 sorgenti RQ1 verificate byte-for-byte come Git blob**, rispetto al commit RQ1 `e4845e7fe9a399e10dd2db6f320dfeaeeddf3379`. Nuovo preflight **source-only e non eseguibile**. Non legge Market, telemetry, GT, score né risposte LLM.

## Stato reale prima di questo passaggio

L'utente ha eseguito `test_rq2_fake_discovery_driver.py` e riportato `Ran 16 tests in 8.230s — OK`. La prova del coordinatore automatico con fake backend è quindi superata (**16/16**), ma **non** certifica il grafo reale o la disponibilità provider.

## 1. Verifica esatta della modalità D originale: risolta

Consultate sul branch attuale le due sorgenti RQ1 e confrontato ciascun Git blob con il **commit frozen RQ1** (blob identici):
- `src/evaluation/evaluation20_preregister.py`: in `build_plan`, il piano ufficiale include esattamente `"output_contract_mode": "v2_enforce"` insieme a `"variant_scheme": "current"`, `"max_tool_rounds": 6`, `"recursion_limit": 30`.
- `src/evaluation/evaluation20_campaign.py`: `run_one` passa `output_contract_mode=plan["output_contract_mode"]` a `ExperimentConfig` e controlla che il risultato contenga `v2_enforce`.

Quindi, **per il confronto D di RQ2 con RQ1, la modalità da preregistrare è `v2_enforce`**. Non usare per errore il default `legacy` di `ExperimentConfig`. Questa scelta è sostenuta da sorgente storico verificato, **non** da una congettura basata su un vecchio output. È ancora necessario congelare formalmente il protocollo nuovo e testarne la parità runtime prima delle API.

## 2. Sorgenti RQ1 identiche al commit frozen

Confrontati i Git blob dei seguenti **13** file fra commit `e4845e7` e branch RQ2 (tutti identici):

`evaluation20_preregister.py`, `evaluation20_campaign.py`, `experiment_runner.py`, `experiment_config.py`, `model_factory.py`, `agent/prompts.py`, `agent/graph_engine.py`, `agent/tool_factory.py`, `agent/tools.py`, `output/v2_task_contract.py`, `harness/evidence_builder.py`, `harness/signal_catalog.py`, `harness/rules/rule_container_cpu.py`.

Questo **non implica automaticamente** che l'intero albero del repository e tutte le dipendenze siano congelati. Il confronto copre questi file specifici. Non modifica codice/risultati RQ1.

## 3. Codice nuovo di cattura delle impronte

`src/evaluation/rq2_protocol_identity_preflight.py`:
- Ri-controlla localmente i **Git blob SHA-1 attesi** delle 13 sorgenti RQ1. Normalizza eventuali terminatori CRLF di un checkout Windows al solo scopo del confronto col Git blob, rifiutando qualunque altra alterazione.
- Registra `SHA-256` per i 13 file RQ1 e per sette file già sviluppati in RQ2 relativi a C/K, evidenze, binding e persistenza.
- Calcola SHA-256 del **testo esatto** di `CAUSE_SYSTEM` e `RULE_SYSTEM` dal sorgente `rq2_probe_adapter.py` importato, senza usare casi reali o modelli; include `probe_adapter_version`.
- Verifica gli ID candidati `gemini-3.5-flash-lite`, `claude-sonnet-5-5`, `claude-haiku-5-5` contro la factory RQ1, `4096` output token Claude e `max_tool_rounds=6`.
- Riporta `rq1_D_output_contract_mode_verified="v2_enforce"` e propone lo stesso valore per RQ2 D.
- Restituisce un JSON di sola provenienza, con `SOURCE_PROVENANCE_CAPTURE_NOT_SCIENTIFIC_FREEZE`, `rq2_scientific_protocol_frozen=false`, `rq2_discovery_api_enabled=false`, `rq2_test_unlocked=false`, `provider_issued_requests=0`, `files_written=false`.
- Non impone tetto USD: `cost_ceiling_required=false`, su decisione del professore riferita dall'utente. Token e costi rimangono report scientifici.

**Non è ancora il freeze scientifico dei prompt**: gli hash vengono acquisiti per esporre e rilevare successivi cambiamenti; per il freeze dovremo registrare gli SHA attesi in un artefatto versionato e bloccare esplicitamente differenze. L'hash di un prompt *di sistema* da solo non copre l'intero messaggio dinamico C/K, che comprende istruzione originale e bundle E###; il digest del codice `rq2_probe_adapter` e i `package_sha256` delle singole richieste servono proprio a completare questa provenienza.

## 4. Nuovi test da verificare

`src/tests/test_rq2_protocol_identity_preflight.py`: **14 metodi sintetici/read-only predisposti; ancora non eseguiti in PyCharm**. La suite rilegge anche gli effettivi file del repository per rilevare drift RQ1; per il resto usa soltanto mock e file temporanei. Sono incluse verifiche Git blob, output mode, parametri, prompt hash, cambio sorgente, cambio prompt, terminatori Windows, blocco API e isolamento dati.

```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_protocol_identity_preflight.py" -v
python -m evaluation.rq2_protocol_identity_preflight
```

**Attesi 14 test e JSON di cattura impronte.** Non dichiarare successo prima del log utente. Il JSON non include casi OOD né dati sensibili: serve soltanto a riportare hash e decisioni verificabili.

## 5. Rimangono da fare prima del pilot reale

- Runner real D: chiamare solo `run_experiment(config, salva=False)` con `output_contract_mode="v2_enforce"`, `variant_scheme="current"`, 6 round, 30 recursion; esperimento con fake LLM *nel motore vero* prima del primo provider remoto.
- C/K: un'invocazione per stage **senza tool**, contenuto esatto dei prompt preparato da `rq2_probe_adapter`; fissare temperature/default provider, limiti, versioni, estrazione dei text block, error states e usage per singola richiesta. Non sostituire il task originale D con l'output C.
- Freeze scientifico di coorte, statistiche e criteri K senza consultare test, mantenere test OOD chiuso e scorer GT isolato. Nessun human-in-the-loop diagnostico.
- Proteggere claim → chiamata → record, con audit manuale delle incertezze, nessun retry silenzioso. Nessun tetto economico per le API, come indicato dall'utente.

**Stato RQ2: `DRAFT_NOT_EXECUTABLE`**, nessuna API avviata.
