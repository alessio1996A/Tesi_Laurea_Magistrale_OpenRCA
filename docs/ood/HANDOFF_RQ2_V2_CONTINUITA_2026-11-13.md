# Handoff di continuità — OpenRCA RQ2-V2, 13 novembre 2026

**Scopo:** riprendere la tesi in una nuova chat senza perdere
commit, esiti, errori o vincoli sperimentali.

**Repository:** `alessio1996A/Tesi_Laurea_Magistrale_OpenRCA`
**Branch:** `experiment/rq2-provenance-v2-offline-2026-11-13`
**Base congelata V1:** `c0eee134a1219bb1704efb73621cafe3d4f70a1a`
**Consegna tesi:** 1 dicembre 2026.
**Metodo:** lavoro su branch separato tramite connettore GitHub,
utente testa in PyCharm/PowerShell e poi (solo con autorizzazione)
in Colab. Nessuna API di provider senza approvazione preventiva.
Dopo il freeze: refactoring del codice, commenti in italiano e
pulizia file superflui, senza alterare sorgenti/risultati congelati.

## Tesi, benchmark e risultati congelati

Università di Catania, LM Ingegneria Informatica.
Harness Engineering per LLM su RCA con Microsoft OpenRCA.

RQ1 Evaluation20: 20 incidenti × 5 harness × 3 LLM =
300 tentativi, 295 complete e 5 errori provider Gemini.
Scoring Microsoft ufficiale e confronti statistici già
congelati; non cambiare il protocollo RQ1.

RQ2: knowledge transfer, stadi D→C→K, due harness A1/A1_8R,
modelli Gemini/Sonnet/Haiku. Quattro casi discovery già visti:
`cloudbed-1_q032`, `cloudbed-1_q050`,
`cloudbed-2_q026`, `cloudbed-2_q045`.
Undici casi OOD test LOCKED. V1 rimane a 39/72 stage:
28 RECORDED_COMPLETE, 4 INVALID_OUTPUT,
7 BLOCKED_DEPENDENCY; 32 tentativi API reali.
24 record Gemini, 15 Sonnet, 0 Haiku.
Tre D Sonnet invalid per ambiguità fra tool call parallele
omonime, perché il grafo V1 non serializza gli originali
`tool_call_id` nei risultati. Il bundle RQ2 fail-closed
è corretto: **non allentarlo**, non riparare V1 retroattivamente,
non fare retry sui claim V1.

## Codice V2 sul branch

Nuovi file, senza cambiare sorgenti originali:
- `src/agent/rq2_v2_graph_engine.py`: replica minima
  esecutore V1 che aggiunge i `tool_call_id`
  originali alle tool call e tool result; nessun ID inventato.
- `src/evaluation/rq2_v2_isolation_policy.py`:
  validazione allowlist di stage discovery e namespace
  V2, esclusione test OOD.
- `src/evaluation/rq2_v2_artifact_store.py`:
  artifact store **solo sintetico**,
  JSON canonico, hash, create-only O_EXCL, status
  coerenti e parent hash.
- `src/evaluation/rq2_v2_claim_journal.py`:
  claim journal indipendente **solo sintetico**,
  no retry, restart audit e claim senza output preservati.
- `src/evaluation/rq2_evidence_bundle.py`,
  `src/evaluation/rq2_probe_adapter.py`,
  `src/evaluation/experiment_runner.py` rimangono invariati.

La nuova radice `data/rq2_v2_provenance` è disgiunta
da `data/rq2` V1. I moduli attuali richiedono un
marker sintetico e rifiutano Market.zip e directory
del benchmark reale. Sono ancora in stato
`DRAFT_NOT_EXECUTABLE`, NON una release di produzione.

## Test effettivamente eseguiti dall'utente in PyCharm

- 7/7 test tool provenance V2.
- 41/41 regressioni mirate.
- 812/812 suite globale.
- 2/2 runner-LangGraph fake end-to-end.
- 814/814 suite globale.
- 3/3 DCK fake con store V1 *solo in TemporaryDirectory*.
- 817/817 suite globale.
- 8/8 policy isolamento.
- 16/16 nuovo store/journal sintetico V2.
- **841/841 suite globale — 72.153 secondi — OK**.

Sono test software, non 841 diagnosi sul benchmark.
GO solo offline, NO-GO API reali, NO-GO test OOD.
Report principale:
`docs/ood/RQ2_V2_GATE_841_PASS_GO_OFFLINE_NO_LIVE_2026-11-13.md`.
Confronto GitHub sulla base V1: 23 file aggiunti,
0 file preesistenti modificati, prima del gate successivo.

## Lavoro appena preparato: gate pending

**Nuovo test non ancora eseguito:**
`src/tests/test_rq2_v2_runner_to_ledger_fake_e2e.py`.

Unisce `run_experiment` V1, grafo LangGraph,
fake LLM/tool, esecutore V2 temporaneamente
patchato nel solo test, bundle tool_call_id,
preparazione offline pacchetti C/K e **nuovo**
journal/store V2 in `TemporaryDirectory`.

Identificativo consentito `cloudbed-1_q032` usato
SOLO come chiave fixture; dati, istruzione, C/K,
telemetria e tool sono inventati e nessun benchmark
reale viene aperto. Tre nuovi metodi:
1. triplet D/C/K per A1 e A1_8R; sei record/claim,
   provenienza delle due tool call omonime, parent SHA,
   restart e no retry;
2. ID tool result corrotto ⇒ D INVALID_OUTPUT,
   C/K BLOCKED_DEPENDENCY, nessun claim C/K;
3. C con ID E999 inesistente ⇒ INVALID_OUTPUT,
   K BLOCKED_DEPENDENCY.

**Stato:** codice GitHub preparato, test non ancora
eseguito in PyCharm; non dichiarare pass.

### Comandi PyCharm

Solo se branch giusto e working tree pulito:

```powershell
git branch --show-current
git status --short
git fetch origin
git pull --ff-only origin experiment/rq2-provenance-v2-offline-2026-11-13
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_runner_to_ledger_fake_e2e.py" -v
```

Attesi **3** test. In caso di errori leggere il
traceback e correggere SOLO nuovi file V2.
Se OK, ripetere
`python -m unittest discover -s src/tests -p "test_*.py" -v`.
Previsti circa **844** test (841+3), da verificare.

## Decisioni ancora aperte

Senza nuovi esperimenti reali NON è dimostrata
la generalizzazione a nuove classi. Prima di
un pilot V2, il nuovo store reale richiederà:
source pin, release SHA, coorte/comparatori,
JSON/prompt e policy errori, journal/claim
create-only, budget stop e autorizzazione.
Una replica sui 4 discovery già analizzati
proverebbe robustezza tecnica, non generalizzazione
indipendente. Undici test OOD restano LOCKED.
Non implementare human-in-the-loop, per decisione
del relatore. Non accumulare nuove campagne se
compromettono la scrittura RQ1 e la scadenza tesi.

## Prompt di ripresa in una nuova chat

> Riprendiamo la tesi OpenRCA. Con connettore GitHub
> leggi per intero
> `docs/ood/HANDOFF_RQ2_V2_CONTINUITA_2026-11-13.md`
> sul branch
> `experiment/rq2-provenance-v2-offline-2026-11-13`,
> verifica HEAD/ultimo commit e report.
> Non modificare V1 né inventare risultati.
> L'ultima suite globale confermata era 841/841.
> È pendente il test fake runner-to-new-ledger V2:
> 3 nuovi test in
> `test_rq2_v2_runner_to_ledger_fake_e2e.py`.
> Procedi metodicamente con commit su GitHub,
> test PowerShell/PyCharm e nessuna API senza
> autorizzazione.

In una chat successiva verificare HEAD perché
nuovi commit/test potrebbero aver aggiornato lo stato.
