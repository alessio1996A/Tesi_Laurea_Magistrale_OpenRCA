# RQ2-V2 — Gate offline D→C→K con provenance e journal temporaneo

**Data:** 13 novembre 2026.
**Stato:** test sintetici preparati su branch sperimentale,
NON ANCORA ESEGUITI localmente. Nessuna nuova API.

## Esito della suite globale precedente

L'utente ha eseguito nella propria installazione PyCharm:

```text
Ran 814 tests in 64.991s

OK
```

Esito osservato: **814/814 PASS**, incluso il
test di runner real fake precedentemente aggiunto.
Questo non include i tre nuovi test qui descritti.

## Perché il gate è necessario

La nuova V2 recupera `tool_call_id` delle
chiamate LLM e dei risultati ToolMessage
senz'altro cambiamento al codice del grafo V1.
Abbiamo verificato la provenienza e l'input C
a livello di runner con due test sintetici.

Resta da verificare il comportamento dei
claim e del recorder D/C/K sui nuovi eventi
con ID, senza cambiare lo store originale.

**CRITICO:** lo store e il claim journal correnti
sono specifici del piano RQ2-V1 e delle directory
`data/rq2/stage_claims_v0` e
`data/rq2/stage_artifacts_v0`.
Non devono diventare lo store reale della V2.
Qui li usiamo solo nella fixture esistente
in una `TemporaryDirectory` con
plan/split/manifest interamente mock,
marker `.rq2_synthetic_fixture_only`,
senza accesso a Google Drive o Market.zip.

## Nuovi test

File `src/tests/test_rq2_v2_fake_dck_journal.py`:

1. `test_v2_ids_complete_fake_dck_and_survive_restart`:
   il vero LangGraph con LLM/tool finti genera due
   chiamate parallele omonime con ID distinti.
   L'esecutore V2 salva i metadata originali.
   Il bundle associa ogni osservazione agli
   argomenti corretti. Il fake driver V1,
   **solo in directory temporanea**, archivia
   il D sintetico e le risposte fake C/K,
   mantenendo SHA, dipendenze e matching
   claim/result dopo un restart.
   Convalida anche `model_api_calls=0`,
   `can_execute_api=false`,
   `scientific_results_produced=false`.

2. `test_wrong_v2_result_id_invalid_d_blocks_c_and_k_offline`:
   altera un ID nel SOLO fixture, prima
   del recorder. Il D risulta
   `INVALID_OUTPUT` e i figli C/K
   `BLOCKED_DEPENDENCY` senza claim provider.
   Il fake backend deve consumare un solo
   tentativo D e il journal deve indicare
   un claim e tre record con zero unresolved.

3. `test_completed_v2_fake_dck_cannot_be_claimed_again`:
   dopo il triplet completo, un nuovo claim
   D/C/K deve essere rifiutato, senza
   riesecuzione o aggiornamento dei dati.

Tutti questi test sono **sintetici**, non eseguono
provider, non hanno accesso ai reali incidenti
OpenRCA, non fanno scoring e non provano
accuratezza né generalizzazione.

## Procedura locale PyCharm

Controllare prima:

```powershell
git branch --show-current
git status --short
```

Se branch corretto e working tree pulito:

```powershell
git fetch origin
git pull --ff-only origin experiment/rq2-provenance-v2-offline-2026-11-13
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_fake_dck_journal.py" -v
```

**Previsti tre metodi di test**, esito da
verificare solo dal log reale. In caso di
fallimento, STOP, conservare il traceback,
non cambiare sorgenti congelati.

Solo se tutti i test passano:

```powershell
python -m unittest discover -s src/tests -p "test_*.py" -v
```

Se i test previsti vengono scoperti tutti e
non cambia altro, ci aspettiamo circa
**817 test** nella suite globale; il numero
esatto viene stabilito da unittest.

## Decisione post-gate

PASS significa soltanto compatibilità V2
con il recorder esistente in test isolati;
**non** è autorizzazione a salvare nuovi
record V2 nello store V1 reale.

Prima di qualsiasi nuova API progettare e
testare:
- namespace, protocol ID e journal V2 indipendenti;
- semantica dei claim create-only, no retry,
  crash recovery e dipendenze D→C→K;
- reale source pin + release v2 + budget;
- split/coorte preregistrati e separate
  metriche operative e scientifiche;
- confronto corretto con campagna V1,
  senza rivalutazione dei risultati V1.

OOD_TEST resta LOCKED.
