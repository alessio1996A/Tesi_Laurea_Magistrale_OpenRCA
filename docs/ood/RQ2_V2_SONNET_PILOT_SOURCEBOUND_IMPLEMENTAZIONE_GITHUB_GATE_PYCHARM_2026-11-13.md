# RQ2-V2 — Implementazione pilot Sonnet D source-bound, gate PyCharm ancora da eseguire

**Data:** 13 novembre 2026  
**Stato:** `CODE_READY_FOR_OFFLINE_TEST` / `NO_LIVE_API_RELEASE` / `OOD_TEST_LOCKED`  
**Branch:** `feature/rq2-v2-sonnet-sourcebound-pilot-2026-11-13`  
**Branch sorgente:** `experiment/rq2-provenance-v2-offline-2026-11-13`  
**Base SHA:** `86b65699c59912a965b3451ad1ad120ca36e571c`  
**Base V1 congelata:** `c0eee134a1219bb1704efb73621cafe3d4f70a1a`

## Identità e scopo

Un solo stage tecnico nuovo: `cloudbed-1_q050 / sonnet / A1 / D`,
modello `claude-sonnet-5-5`, `v2_enforce`, massimo 6 tool round e
`recursion_limit=30`. Protocollo V2 distinto:
`rq2_v2_sonnet_q050_d_sourcebound_pilot_v1`.
Non è un retry V1 né una misura di generalizzazione. C e K non eseguite.
Le 11 query OOD test e tutta la GT restano fuori dal runtime.

## File aggiunti nel branch (nessuna modifica V1)

1. `src/evaluation/rq2_v2_sonnet_pilot_ledger.py`:
   source preflight GT-free con hash split/manifest, controllo codice RQ1,
   HEAD Git pulita e SHA esecutore V2; nuova root esclusiva
   `data/rq2_v2_provenance/sonnet_q050_d_pilot_v1`.
   Claim prima di ogni richiesta, file canonical JSON con `O_EXCL`,
   digest e readback. Errori, output invalidi e claim orfani non sono
   trasformati in successi né ritentati. Archivio V1 mai aperto/scritto.
2. `src/evaluation/rq2_v2_sonnet_pilot_driver.py`:
   entrypoint di una D con conferma esplicita, release SHA approvata,
   snapshot runtime, client Anthropic senza retry automatico,
   patch **temporanea** del solo esecutore V2 dentro il runner RQ1
   `run_experiment(..., salva=False)`. Massimo sette invocazioni LLM
   osservate, incluso l'eventuale passo finale, ed operational stop
   prima della richiesta successiva se supera la soglia USD.
   Il costo di una risposta già emessa può superare la soglia:
   **non esiste un hard cap USD garantito**.
   Il report distingue successo tecnico e reale presenza di tool call
   parallele omonime; se queste non compaiono, il vecchio scenario
   problematico non è riprodotto.
3. `src/tests/test_rq2_v2_sonnet_pilot_offline.py`:
   **13 nuovi metodi di test** progettati, da eseguire in PyCharm.
   Fake Anthropic/telemetria/dati/manifest e release; motore LangGraph
   e ledger veri. Coprono claim orfano/restart/no-retry, ID call/result
   originali e corrupt, JSON invalido, errore, metadati usage mancanti,
   manomissione record, deriva source hash, alterazione release SHA,
   sentinel byte-immutabile V1 e fake end-to-end con il driver.

**Verifica del diff GitHub sul commit sorgente:** tre nuovi file aggiunti,
zero file modificati del branch precedente (prima di questo documento).

## Release: NO-GO fino a preregistrazione e autorizzazione

L'entrypoint richiede due condizioni indipendenti:
- `confirm_paid_api=True` fornito esplicitamente per una sola D;
- `release_sha256=<64 hex>` di un file `release_v1.json`
  canonico, con identità/model/versioni, SHA input/codice e budget
  approvati. Il release SHA viene passato solo dopo il congelamento
  del commit: non si modifica il codice per fissare il pin.

Nessun file `release_v1.json` approvato viene creato qui; la costante
di default `EXPECTED_RELEASE_SHA256` resta `None`.
Il gate usa il vero `preview_discovery_d_config` per controllare
`split_market_v1.csv` SHA
`c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`
e `benchmark_inputs_market.csv` SHA
`5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`,
senza leggere dati di scoring. Controlla l'HEAD locale del repository
e l'assenza di modifiche. Nessuna chiamata provider è stata eseguita
durante l'implementazione.

## Prossimo gate: GitHub → PyCharm, offline

Su PowerShell, con working tree pulito:

```powershell
git status --short
git fetch origin
git switch --track origin/feature/rq2-v2-sonnet-sourcebound-pilot-2026-11-13
git status --short
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_sonnet_pilot_offline.py" -v
```

Se il branch locale esiste già, usare `git switch feature/rq2-v2-sonnet-sourcebound-pilot-2026-11-13`
e `git pull --ff-only` invece di `--track`.

**Atteso solo in caso di successo:** `Ran 13 tests / OK`.
Non affermare PASS prima dell'output dell'utente. Se fallisce, leggere
traceback e correggere solo nuovi file V2. In caso di successo:

```powershell
python -m unittest discover -s src/tests -p "test_*.py" -v
```

Baseline precedente **852/852 PASS**; se i 13 nuovi test sono
effettivamente raccolti senza duplicazioni, il totale atteso è **865**.
Il test PyCharm non è stato eseguito dall'assistente.

## Colab e fasi successive — non avviare ancora

Dopo gate offline PASS e controllo della coerenza della release:
1. preparare un preflight source-only in una directory separata su Colab;
2. verificare vero runtime/versioni SDK, disponibilità modello e
   prezzi del giorno; definire soglia e costo non garantito;
3. congelare HEAD, output preregistrato e release SHA, ottenere
   approvazione esplicita di un solo stage a pagamento;
4. solo a quel punto una sola D reale con `claim` create-only
   sulla radice V2 e audit post-run; nessun retry né C/K;
5. mantenere gli OOD test bloccati e decidere con il relatore
   se RQ2 resti uno studio esplorativo o abbia senso un
   protocollo successivo realmente indipendente.

## Stato finale di questo commit

**Codice implementato / test non ancora osservati / nessuna API / nessuna
diagnosi reale V2 / nessun criterio di generalizzazione soddisfatto.**

La priorità di progetto resta: chiudere esperimenti approvati
→ refactoring/commenti italiani/pulizia senza alterare freeze
→ stesura della tesi entro 1 dicembre 2026.
