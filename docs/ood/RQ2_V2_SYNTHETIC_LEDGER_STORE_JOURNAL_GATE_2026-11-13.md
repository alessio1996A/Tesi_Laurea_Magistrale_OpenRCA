# RQ2-V2 — Store e journal indipendenti, esclusivamente sintetici (gate offline)

**Data:** 13 novembre 2026.
**Branch:** `experiment/rq2-provenance-v2-offline-2026-11-13`.
**Stato:** codice preparato e verificato staticamente; **16 test nuovi NON ancora eseguiti localmente**.
**Base del gate:** 8/8 test policy V2 PASS comunicati dall'utente.
**Esecuzione provider:** non autorizzata.

## Cosa è stato aggiunto

Tre nuovi file sul branch, senza modifiche a file preesistenti:

1. `src/evaluation/rq2_v2_artifact_store.py`
   - classe `RQ2V2SyntheticArtifactStore`;
   - radice V2 `data/rq2_v2_provenance/stage_artifacts_v1`;
   - JSON canonico, digest record e dipendenze SHA256;
   - salvataggi esclusivi create-only con `os.O_EXCL`;
   - controllo status D secondo tool provenance fail-closed;
   - controllo status C/K secondo JSON contract;
   - C/K `BLOCKED_DEPENDENCY` solo quando il parent non è completo;
   - rifiuto di file estranei, symlink e oggetti non canonici all'audit.

2. `src/evaluation/rq2_v2_claim_journal.py`
   - classe `RQ2V2SyntheticClaimJournal`;
   - radice V2 `data/rq2_v2_provenance/stage_claims_v1`;
   - claim create-only con modello, protocollo, parent hash e tentativo unico;
   - verifica che ogni record tentato corrisponda a un claim;
   - `CLAIM_WITHOUT_ARTIFACT` resta manual review, MAI retry automatico;
   - nessun claim provider per gli stage `BLOCKED_DEPENDENCY`;
   - audit di ripartenza e controlli di coerenza claim ↔ result.

3. `src/tests/test_rq2_v2_synthetic_ledger.py`
   - **16 test nuovi** di successo, errore e isolamento;
   - solo `TemporaryDirectory`, marker sintetico, finti dati di tool;
   - nessuna chiamata ad API, Market, scoreboard o dataset GT.

## Vincoli di sicurezza

Per costruire store o journal è necessario il marker
`<data_dir>/.rq2_v2_synthetic_only` con byte esatti
`RQ2_V2_SYNTHETIC_ONLY_NO_API_V0\n`.

Un path reale di OpenRCA è rifiutato quando contiene
`Market.zip`, `data/processed`, `data/rq2`
oppure `data/results`.
La destinazione deve essere un `Path` assoluto,
senza `..`, symlink o file nei componenti di directory.
Le sole chiamate di costruzione e audit non scrivono file.

**Questi moduli rimangono sintetici, NON il nuovo store scientifico reale.**
Non hanno release firmata, manifest GT-free sorgente verificato,
provider autorizzato, policy di budget o conoscenza del benchmark reale.
Non sono un dispatcher e non possono autorizzare chiamate API.
L'eventuale archivio V2 di produzione richiederà un gate ulteriore
che mantenga invariata la semantica create-only senza riutilizzare V1.

## Regressione e criteri GO/NO-GO

Nuovi test:
- D→C→K completo in radice V2, parent hash e restart verificabili;
- D con chiamate parallele omonime senza ID → INVALID + figli blocked;
- claim orfano senza record → unresolved, non ritentabile;
- claim/record duplicati rifiutati;
- C invalid → K blocked;
- D con provenance ambigua non può essere `RECORDED_COMPLETE`;
- GT key proibito rifiutato;
- file corrotto non cancellato e audit bloccato;
- root senza marker o con vecchia directory V1 rifiutata;
- ID OOD test rifiutato;
- symlink di namespace rifiutato;
- modello incongruente rifiutato;
- status `INVALID_OUTPUT` falsamente dichiarato su D con traccia valida rifiutato;
- C dichiarato completo con JSON invalido rifiutato;
- D provider error preserved con C/K blocked;
- C provider error richiede testo d'errore e blocca K.

### Prima esecuzione locale

Dal branch `experiment/rq2-provenance-v2-offline-2026-11-13`,
dopo verifica di `git status --short` vuoto:

```powershell
git fetch origin
git pull --ff-only origin experiment/rq2-provenance-v2-offline-2026-11-13
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_synthetic_ledger.py" -v
```

**Esito atteso da verificare:** 16 test. Qualsiasi errore:
STOP, conservare traceback, non cambiare altri file e NON lanciare API.

Se **16/16 PASS**, ripetere l'intera suite:

```powershell
python -m unittest discover -s src/tests -p "test_*.py" -v
```

La precedente suite globale ha restituito **817/817 PASS**;
il nuovo totale previsto è **833**, ma solo il log di
`unittest` confermerà numero ed esito.

## Metodologia

- V1 (39 record discovery) immutata;
- OOD test (11 casi) LOCKED;
- provider API requests: **zero** nel codice aggiunto;
- nessun risultato diagnostico nuovo o claim reale creato;
- non spacciare test software per accuratezza RCA;
- release V2 reale e denominatori sperimentali ancora da preregistrare.

**Successo del gate offline significa solo correttezza negli scenari testati,
non approvazione di un'altra campagna a pagamento.**
