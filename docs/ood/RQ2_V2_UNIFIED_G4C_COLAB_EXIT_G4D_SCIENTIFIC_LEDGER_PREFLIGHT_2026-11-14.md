# RQ2-V2 unificata — G4C Colab eseguito senza traceback, JSON mancante; G4D gate di ledger scientifico

**Data:** 14 novembre 2026. **Opzione A prioritaria, B successiva**. Branch di sviluppo `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`. 11 casi OOD restano locked.

## 1. Output Colab G4C riportato realmente dall'utente

```text
Drive already mounted at /content/drive; to attempt to forcibly remount, call drive.mount("/content/drive", force_remount=True).
=== 1/3: CSV ORIGINALI GT-FREE ===
FOUND: data/processed/split_market_v1.csv
FOUND: data/processed/benchmark_inputs_market.csv
=== 2/3: CODICE UNIFICATO SEPARATO ===
CODE_COMMIT: 33d5d8b28494d5bf41168d0a709854aa3134ea6a
=== 3/3: RQ2 V2 UNIFIED SOURCE GATE — NO API ===
G4 REAL GT-FREE SOURCE PREFLIGHT: TERMINATO (0 API)
```

La cella Colab originale, riportata in `docs/ood/RQ2_V2_UNIFIED_G4B_PASS_COLAB_GT_FREE_SOURCE_READONLY_2026-11-14.md`, contiene un subprocess `check=True`, con assert sui flag di sicurezza e un `print(json.dumps(report))` **prima** della riga finale. Il testo fornito non include quel JSON, quindi:
- **confermato dal testo:** Drive montato, CSV GT-free trovati, checkout esatto `33d5d8...`, cella giunta alla fine con dicitura 0 API e nessun traceback;
- **forte indicazione, subordinata all'esecuzione integrale della cella originale:** subprocess uscito 0 dopo gli assert;
- **non ancora documentato dagli output visibili:** `source_plan_preview_sha256`, `blueprint_sha256`, impronte prompt C/K, `split_sha256`, `manifest_sha256`, tutti i flag del JSON. Non inventare/riciclare hash di vecchie coorti, non dichiarare che il JSON sia stato ricevuto.

Per completare l'audit G4C senza ambiguità chiedere il report JSON effettivo o rieseguire esclusivamente il blocco READ-ONLY della cella. **Non serve rimontare Drive**, non cambiare i CSV, non aprire Market.zip, non avviare modelli. La verifica GT-free RQ2 V1 era già stata osservata il 12/11, ma non sostituisce la ricevuta completa G4C unificata.

## 2. G4D — Guardia READ-ONLY del futuro ledger scientifico comune

Nuovi file:
- `src/evaluation/rq2_v2_unified_scientific_ledger_preflight.py`
- `src/tests/test_rq2_v2_unified_scientific_ledger_preflight_offline.py` (**19 metodi non ancora eseguiti**).

Il modulo G4D:
- richiede `expected_commit` SHA-1 Git esadecimale fisso, **fornito dall'esterno**, non derivato automaticamente da HEAD;
- verifica `git rev-parse HEAD` e `git status --porcelain` pulito;
- verifica roots assolute/sicure, symlink e assenza del futuro namespace `data/rq2_v2_unified_scientific_v1`;
- chiama `preview_unified_source_bound` per certificare realmente dati GT-free e sorgenti, quindi `build_unified_release_blueprint` con 180 stage;
- restituisce un report di provenance con SHA di sorgenti/plan/blueprint, e permessi sempre spenti;
- **NON crea release, claim, ledger operativo, client LLM, filesystem output, o API.**
- **NON riusa** il journal sintetico o gli archivi V1/Sonnet pilot. L'identità codice di questo guard *non è ancora nell'inventario scientifico frozen*: dovrà esserlo nel momento della release.

I 19 unittest usano repo con `.git` e snapshot Git sintetici, mock source-bound/blueprint per coprire: head mismatch, tree dirty, symlink, namespace occupato, GT leakage flag, OOD unlocked, API flag true, blueprint source SHA drift, nessuna creazione file. Non sono sostituti della verifica reale Colab.

## 3. Prossimo comando PyCharm — G4D

Eseguire dal branch unificato solo con modifiche locali assenti:
```powershell
git status --short
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_scientific_ledger_preflight_offline.py" -v
```

Attesi **19 test** e `OK`, **non ancora attestati**. Se compaiono errori, diagnosticarli senza allentare il guard.

## 4. Stato generale

G1 25/25, G2 9/9, G3A 23/23, G3B 9/9, G4A 18/18, G4B 18/18: **102 metodi unittest già PASS**. G4C output terminale disponibile ma JSON completo mancante. G4D test scritti ma non eseguiti. **Non esiste ancora il ledger scientifico con claim/record né il dispatcher provider comune**, non è firmata alcuna release, nessuna nuova chiamata LLM unificata, Opzione B sempre bloccata.
