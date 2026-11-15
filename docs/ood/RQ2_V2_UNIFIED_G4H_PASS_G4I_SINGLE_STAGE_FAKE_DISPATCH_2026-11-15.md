# RQ2-V2 — G4H 20/20 PASS; G4I dispatcher source-bound per singolo stage (FAKE-ONLY)

Data: **15 novembre 2026**. Branch: `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.

## Ultima prova effettiva dell'utente

```text
Ran 20 tests in 7.090s

OK
```

**G4H ora PASS 20/20.** Questa è la seconda esecuzione dopo che il test negativo dei prompt è stato corretto: prima verifica SHA di C con D valido e C ancora non claimed, poi salva C e verifica SHA di K con K ancora libero. I due controlli SHA non sono stati disabilitati. G4F 22/22 e G4G 17/17 erano già PASS in esecuzione precedente; i loro moduli produttivi non sono stati modificati per risolvere la failure G4H.

## Nuovo G4I — codice in attesa di test PyCharm, NON LIVE

Nuovi file:
- `src/evaluation/rq2_v2_unified_single_stage_dispatcher.py`
- `src/tests/test_rq2_v2_unified_single_stage_dispatcher_offline.py` (**24 test scritti, non ancora eseguiti**).

**G4I non è un dispatcher API autorizzato**. È il primo coordinatore realmente *per singolo stage*, non tutta la tripla di G4G:

1. Dato uno stage_id della sola discovery, richiede una release fittizia `approval_reference=SYNTHETIC_APPROVAL_NOT_REAL` con SHA e commit mockati dai test, e il vero ledger create-only G4F.
2. Richiede una radice in `tempfile.gettempdir()` e un marker fisico `.rq2_v2_unified_single_stage_fake_only`; rifiuta `Market.zip`, altri risultati o input benchmark e una release con riferimento non sintetico.
3. Invoca `preview_one_unified_stage` G4H: legge SOLO il manifest GT-free, controlla piano/release/commit e accede ai parent D/C già persistiti, ricostruisce il package C o K e confronta il package SHA256 prima del claim.
4. Scrive un **solo claim** create-only, immediatamente prima del callback sul fake LLM. Esegue `gateway.run_d`, `run_c` o `run_k` sotto `network_forbidden()` (blocca socket). NON costruisce o importa modelli/provider live.
5. Registra nel ledger **esattamente un record tentato** per stage; se D o C fallisce, marca i discendenti come `BLOCKED_DEPENDENCY` senza claim/API. Errori simulati pre-request sono `PROVIDER_ERROR`, uso/costo `UNKNOWN` e richieste esterne zero; un crash inaspettato dopo claim mantiene un orphan da revisione, **senza retry**.
6. Ricicla i contratti D/C/K già validati nel precedente G4G, senza modificare RQ1 o lo scorer. Ogni risposta indica `real_provider_requests=0`, `can_execute_api=False` e OOD locked.
7. Stage D: il gateway fake usato dai test attraversa davvero `run_experiment` e i due grafi ReAct/Planning/PAVE; C/K usano prompt tool-free e risposte simulate, con token sintetici. Tutti i record sono in TemporaryDirectory.

La suite G4I comprende 24 metodi, inclusi tre bracci diversi D→C→K **in chiamate separate**, errori D/C/K, raw invalido, block children, retry disabilitato, claim orphan dopo interruzione, meter fallito, file extra/Market vietati, root non temporanea, origine OOD, prompt package SHA alterato, connessione socket negata e token completi con costo USD sconosciuto.

**ATTENZIONE: non trasferire la release fake dei test su Google Drive, non modificare marker per aggirare i blocchi.** Il marker serve solo a impedire usi accidentali su dati reali.

## Prossimo comando PyCharm (G4I)

Accertare `git status --short` vuoto sul branch RQ2-V2 unificato, poi:
```powershell
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_unified_single_stage_dispatcher_offline.py" -v
```
**Attesi 24 metodi e OK, NON ancora attestati**. Se fallisce, leggere il PRIMO errore, correggere solo ciò che è dimostrato e non toccare il ledger o il protocollo congelato senza una regressione mirata. Non è richiesto Colab o alcuna API.

## Stato e rischi residui

- **PASS già attestati**: G4F (22), G4G (17), G4H (20) e i precedenti gate offline.
- **PENDING**: G4I 24 test. È un'orchestrazione FAKE per singolo stage, non un driver live.
- **Nessuna API reale RQ2-V2 unificata eseguita**; la release scientifica nuova non è ancora stata firmata, gli undici OOD test sono locked.
- **Prima di un pilot pagato:** un adapter RQ2-only reale con stesso controllo di claim pre-API, no-retry, timeout e usage testati; real source inventory + SHA su nuova HEAD che includa G4F/G4H/G4I/adapter; controllo lock FUSE/concorrenza su Google Drive e limite operativo/costi, preregistrazione; approvazione esplicita dello stage. Non chiamare 492 invoke graph '492 HTTP garantite' né costo reale di token sintetici.

Decisione metodologica: riutilizzare l'esistente `rq2_model_factory.py` e i vecchi trasporti D/C/K **solo come implementazioni da adattare**, perché sono vincolati allo store RQ2 V1 e non al ledger G4F. Non fare un'unione di archivi. Dopo i fake G4I PASS, concentrare il lavoro sul pilot e sul freeze, senza moltiplicare esperimenti di facciata.
