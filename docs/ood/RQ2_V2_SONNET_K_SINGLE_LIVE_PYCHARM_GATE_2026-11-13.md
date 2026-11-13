# RQ2 V2 Sonnet K — single-live runner pronto per TEST MIRATI (NO_API)

Data: 2026-11-13. Branch `feature/rq2-v2-sonnet-k-single-live-2026-11-13` dal K preview commit `55d146e7bc859ec3f332f97e65471b8dd41805f3`.

## Dato reale precedente
- K read-only Colab preview `SONNET_V2_K_SOURCEBOUND_PREFLIGHT_OK`, commit preview `55d146...`, K binding SHA `236700ed2ae85fc2fa9d8094215d3a624869d0c374ad1392b29d3cbb85cfaca0`, K package SHA `d8a2c7193a60f7e577fb3243ff27276428e164ea0a42eb124443396e6c8d875a`, system SHA `0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71`, prompt 19971 chars, zero API/writes.
- Il **binding SHA vecchio NON si riutilizza su questa nuova HEAD**. Ricalcolare binding K dalla nuova HEAD del driver in Colab. Il K package e system SHA dovrebbero rimanere uguali se dati invariati.
- D parent frozen record `521ed45b3dfefe6fd6c21427ca1c4ac0d03edbb1608bf80cbc424109c9f1a009`. C ContentBlocks V2 frozen `RECORDED_COMPLETE/diagnosis`, record `8e853074e69f1718ae1a8ebda3f67954bc495fa0d14651e0dfa8a3f03744a49b`. C V1 precedente `INVALID_OUTPUT`, record `39364800134f3713302a6f314822930b501a4300af6d62a12f7ce376a93f0579`, non va rieseguita né reinterpretata.
- Ipotesi C low confidence: node CPU spike, node-6, E001/E008, 3 alternative, 6 limitazioni. Non e' ground truth.

## Modifiche tecniche (solo file nuovi)
- `src/evaluation/rq2_v2_sonnet_k_single_live.py`: protocollo K con release SHA canonico, binding HEAD+parent D/C, wrapper unico `run_one_k`, input system+human da `prepare_candidate_rule`, output Anthropic text blocks da estrattore già testato, parser `validate_candidate_rule`, status `RECORDED_COMPLETE` oppure `INVALID_OUTPUT` o `EXECUTION_ERROR_REVIEW`, decisione `candidate`/ `insufficient_evidence`. Ledger K `data/rq2_v2_provenance/sonnet_q050_k_contentblocks_v2_v1` con nuova release, claim, record create-only. Zero retry, no provider se manca release/pin/consenso.
- `src/tests/test_rq2_v2_sonnet_k_single_live_offline.py`: 17 nuovi test mock per contratto, conteggi, parser, source drift, costo, claim/record, no retry, failure preservation.
- Nessuna modifica alle librerie, al contratto `rq2_candidate_rule_v0` o agli artefatti scientifici congelati. K pseudocodice è testo, **non viene eseguito**.
- La soglia USD 5.0 della futura release è metadato di autorizzazione, **non un hard cap**.
- Una K validata formalmente non equivale a regola causalmente corretta né verificata OOD. `insufficient_evidence` è un risultato valido e da non forzare in `candidate`.

## Gate locale rapido, ancora da eseguire

```powershell
git status --short
git fetch origin
git switch --track origin/feature/rq2-v2-sonnet-k-single-live-2026-11-13
git log -1 --format="%h %s"
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_v2_sonnet_k_single_live_offline.py" -v
```

Aspettativa 17/17, ma non dichiarare PASS finché l'utente non conferma. Per velocizzare si rinvia la regressione completa al freeze finale, come richiesto dall'utente (ultimo insieme completo confermato: 904 test, poi 18 test K preview).

## Dopo i test
Unico preflight read-only sul **nuovo commit K runner**: nuovo checkout Colab, niente API, validazione D/C e K package invariato, namespace K ancora assente; stampare nuovo `K_BINDING_SHA256`. Solo dopo release K create-only e singola API K autorizzata, in celle separate; zero retry. 11 casi OOD test ancora locked, nessuno score/GT.
