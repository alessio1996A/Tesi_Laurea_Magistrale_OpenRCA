# RQ2 — Esito audit V3 e piano-bound adapter offline D→C→K

**Data:** 11 novembre 2026 · **Stato:** audit V3 effettivamente eseguito; nuovo binding preparato ma test PyCharm **non ancora eseguiti**. Il protocollo RQ2 è ancora **DRAFT_NOT_EXECUTABLE**.

## 1. Evidenza reale ricevuta

Notebook `Colab_RQ2_Historical_Trajectory_Feasibility_2026_11_11.ipynb`, branch `feature/ood-knowledge-transfer-audit-2026-11-10`, commit `57002748bdb44ad04a3fe15d48a7f4687df796fe`.

| Indicatore | Esito |
|---|---:|
| JSON nella directory dei risultati V3 congelati | 80 |
| File JSON contenenti `tool_trajectory` | 40 |
| JSON di altri tipi | 40 |
| Bundle strutturalmente ricostruibili | **40/40 (100%)** |
| Osservazioni risultanti dai tool | 209 |
| Osservazioni troncate dal bundle | **71/209 (33,97%)** |
| Incompatibilità rilevate | **0** |
| Letture di GT, scoring, casi OOD | **0** |
| Chiamate API, file nuovi | **0** |

L'assenza di ambiguità nelle 40 traiettorie storiche **non garantisce** che tutti gli esperimenti RQ2 futuri siano compatibili. Il bundler deve continuare a rifiutare chiamate concorrenti allo stesso tool senza `tool_call_id`, risposte incomplete, tool fuori allowlist e contenuti sospetti. Le 71 osservazioni troncate documentano un limite di **copertura semantica** dell'evidenza: gli hash consentono di rilevare differenze, ma la parte non presente nel prompt non può essere ricostruita dal modello, e la diagnosi può risultare incerta o insufficiente. Nessuna evidenza storica è stata usata come materiale per creare regole nuove.

## 2. Decisione di architettura

Il runner RQ1 congelato non va modificato. Per i nuovi casi RQ2, l'adapter già predisposto `src/evaluation/rq2_probe_adapter.py` può utilizzare `tool_trajectory` restituita dal runner D. Esso costruisce un bundle con `E001`, `E002`, ecc., cita SHA della risposta integrale e annota `truncated`. Per realizzare un **runner effettivo**, manca tuttavia un legame verificabile fra fase, case_id, modello, harness e risposta D. La costruzione diretta di pacchetti K senza controllo sul piano potrebbe consentire assegnazioni erronee o riuso di output C di un altro caso.

Il nuovo modulo **di sola preparazione in memoria** `src/evaluation/rq2_stage_binding.py` mira a coprire quel controllo prima di un'implementazione API:
- accetta esclusivamente un piano `rq2_dryrun_workflow_preview_v0` **non eseguibile** con flags di autorizzazione disattivate, 204 stage e SHA coerente;
- verifica schema GT-free chiuso delle entry, 4 discovery + 11 test e assegnazioni per 2 harness ×3 modelli, dipendenze D→C→K, nessuno K su test;
- richiede nel dizionario D stesso `case_id`, `variant`, `variant_scheme=current`, `model_provider`, modello *logico* compatibile e budget 6 round;
- prepara la probe C **senza inoltrare la `raw_response` D** come suggerimento di causa;
- prepara K soltanto se la precedente C proviene dagli stessi input, modello e bundle, e la sua risposta rispetta il contratto C con IDs di evidenza disponibili;
- produce esclusivamente pacchetti serializzabili marcati `can_execute_api=false`, `model_api_calls=0`, `provider_model_versions_frozen=false`, `scientific_rules_frozen=false`. Non importa provider, filesystem, strumenti, scorers o dataset.

**Limite cruciale:** gli ID modello sono ancora versioni *logiche*. Un controllo su `sonnet`/ `haiku` / `gemini` come sottostringa del nome **non è un freeze delle versioni**, né garantisce temperature e parametri. Il vero runner dovrà usare una mappa chiusa di ID/versioni/parametri verificati e un piano congelato create-only. Inoltre questo binding non confronta l'istruzione originale con i byte reali del manifest verificato; il futuro runner dovrà farlo.

## 3. Verifica tecnica da eseguire

Aggiunto `src/tests/test_rq2_stage_binding.py`, **20 test sintetici predisposti**. Controllano ID caso, harness, modello, provider, schema `current`, errore D, tool vietato, piano corrotto, flag API, campi GT extra, differenza di risposta/instruction fra D e C, evidence IDs non autorizzati e stato K solo discovery. I test non accedono a Market, Drive o provider.

**Comando PyCharm dopo pull del branch:**

```powershell
git status
git pull --ff-only origin feature/ood-knowledge-transfer-audit-2026-11-10
$env:PYTHONPATH="src"
python -m unittest discover -s src/tests -p "test_rq2_stage_binding.py" -v
```

**Attesi 20 test; non dichiararli superati finché non arriva il log dell'utente.** Non occorre Colab in questa fase.

## 4. Gap scientifici da chiudere prima delle API

1. **RUOLO DELLA K:** le 24 proposte di pseudoregola (4 discovery ×2 harness ×3 modelli) appartengono alla **RQ2-B**. Sono ipotesi generate, non rule knowledge validata. La correttezza strutturale JSON non garantisce implementabilità fisica.
2. **TRASFERIMENTO RQ2-C:** per affermare trasferimento di conoscenza occorre una **verifica offline e cieca** di una o più specifiche deterministiche formalizzabili, congelate sulle discovery, poi applicate ai gruppi di test e a negativi opportunamente definiti. Con il piano attuale D/C su test **non si crea automaticamente un nuovo harness con regole apprese**. Non confondere le due misure. Se nessuna K è implementabile, riportare risultato negativo/non valutabile per RQ2-C.
3. **TRONCAMENTO:** la prova storica indica 71/209 osservazioni troncate; analizzare quale effetto abbia sulle C e K, senza sfruttare informazioni dei casi test per cambiare il prompt. Dedicare metrica `truncated_count` ed eventuale astensione.
4. **ASSEGNAZIONE:** 4 discovery, 11 test e 4 classi riservate restano una partizione candidata. Prima di chiamare le API servono preregistrazione e freeze dei prompt, modello esatto, costi massimi, policy degli errori, formato/piano create-only e separazione GT.
5. **NO HUMAN-IN-THE-LOOP**: menzionabile nei limiti/prospettive, non implementato nell'esperimento.

Il risultato V3 rende promettente la compatibilità dell'infrastruttura, **non** rappresenta una prova di diagnosi o generalizzazione OOD.
