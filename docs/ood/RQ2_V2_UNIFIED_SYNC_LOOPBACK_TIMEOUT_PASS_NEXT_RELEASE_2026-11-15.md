# RQ2-V2 — Sync HTTP timeout loopback PASS, release non autorizzata

**Data:** 15 novembre 2026 (output Colab fornito dall'utente).  
**Protocollo:** RQ2-V2 unificata, Opzione A, 5 harness × 3 modelli × 4 discovery × D/C/K = 180 stage pianificati.  
**Commit sottoposto a prova:** `d67141ad0ef1e0b4f258c2667372e9aca8ff6292`.  
**Probe:** `src/tests/rq2_v2_sync_timeout_loopback_probe.py`; suite guard `src/tests/test_rq2_v2_sync_timeout_loopback_guard_offline.py`.

## Evidenza ricevuta e catena GitHub → PyCharm → Colab

- PyCharm: `Ran 8 tests in 0.009s — OK` (nuova suite stdlib guard). Non sono run di modello.
- Colab: checkout separato su commit esatto `d67141a...`, dipendenze SDK isolate disponibili, nessuna installazione, nessun accesso Drive/Market/GT.
- Report Colab: `status=SYNC_LOCAL_STALL_TIMEOUT_CHECKED_NO_API_NO_RELEASE`, `loopback_sends_total=4`, `actual_model_calls=0`, `external_api_requests=0`, `real_credentials_used=false`, `scientific_release_frozen=false`, `can_execute_api=false`, `can_run_ood_test=false`.
- Google, `CK_tool_free`: 1 POST locale, eccezione timeout osservata, `elapsed_seconds=0.3071`.
- Google, `D_bound_tools`: 1 POST locale, timeout, `elapsed_seconds=0.3057`.
- Anthropic, `CK_tool_free`: 1 POST locale, timeout, `elapsed_seconds=0.3041`.
- Anthropic, `D_bound_tools`: 1 POST locale, timeout, `elapsed_seconds=0.3037`.
- Probe eseguito su endpoint locale `127.0.0.1` con risposta volutamente ritardata, timeout test **0.3 s**, nessuna richiesta API. Checkout temporaneo rimosso.

**Lettura:** il percorso sincrono LangChain → SDK → HTTP locale per le quattro modalità ha terminato per timeout di lettura e ha emesso esattamente una richiesta per prova, senza retry osservati **su questo scenario di stallo**. È un risultato ulteriore, distinto dal vecchio test HTTP finto 503 già passato il 12/11 e dallo SDK-only mock passato il 15/11. Non ripetere nessuna delle tre prove senza una precisa causa tecnica.

## Limiti e punti da NON certificare impropriamente

1. Il timeout RQ2-only production è configurato a `TIMEOUT_SECONDS=300.0` per *singola request*. In questa prova è stato deliberatamente usato `0.3 s`; nessuna prova ha atteso 300 s, e nessun hard timeout *dello stage D* è garantito.
2. Non sono stati provati tutti gli HTTP status/guasti (per esempio 429, connect failures e DNS), tutte le possibili ripetizioni interne dei provider, i percorsi streaming/async, l'idempotenza remota o una garanzia di numero massimo di HTTP.
3. La prova verifica *sync*. `async_streaming_tested=false`, `full_stage_timeout_guaranteed=false`, `usd_hard_cap_guaranteed=false`. Non dichiarare garanzie superiori in tesi o nella release.
4. La factory RQ2-only rimane distinta dalla factory RQ1 frozen. Il dispatcher G4K ha `LIVE_API_ENABLED=False`. La nuova release scientifica non esiste, nessun consenso API è stato dato, nessun claim scientifico reale è stato creato.
5. I flag vincolanti G4E `transport_retries_proven_no_implicit_http_retry` e `per_request_timeout_verified` richiedono un giudizio tracciabile **limitato all'esatto percorso autorizzato**. Non dedurre una garanzia universale da una prova 503 + stallo. Se la valutazione non è sufficiente, mantenere il gate chiuso oppure aggiungere solo il caso negativo mirato mancante, senza tornare a una nuova infrastruttura.
6. La prova di `flock` e `O_EXCL` su Drive ha verificato una sola sessione/VM, non sessioni concorrenti né durability remota. Single-writer, orphan → manual audit, no auto-retry.
7. I 29 sorgenti del preflight reale commit `601dc7c2f971b919962ff190e6feb192c4dd237a` non sono stati modificati dall'aggiunta del probe nei test e dalle note, ma la futura release deve usare un **nuovo HEAD finale clean** e registrare la propria identità di codice.
8. Sono ancora **0/180 stage RQ2-V2 API reali**. Gli 11 OOD sono LOCKED; Opzione B non autorizzata. RQ1 e RQ2 V1 immutati.

## Prossimi gate, senza ripetere test superati

- **Prima del freeze:** definire perimetro e policy sincrona (Google `max_retries=1`, Anthropic `max_retries=0`, timeout per request 300s); documentare esattamente le prove sufficienti/insufficienti. Non impostare flag `True` senza evidenza.
- **Budget operativo:** progettare stima token USD usando la matrice *nuova* 20 D/20 C/20 K per modello, non il totale legacy RQ2 V1 presente in `rq2_budget_preflight.estimate_campaign_cost`. Per un singolo pilot D distinguere costo *stimato*, budget *approvato* e hard cap *non disponibile*.
- **Selezione stage:** candidato predefinito non autorizzato: il primo stage D nell'ordine del piano `rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:D`, da accettare formalmente prima di qualunque API.
- **Freeze:** commit finale che includa eventuali cambiamenti di policy/dispatcher, nuova lettura source-bound GT-free, SHA runtime e prompt, release canonica G4E create-only con digest esternamente approvato e readback G4F. Il semplice Git SHA non è consenso o firma umana.
- **API:** previo consenso esplicito, una singola D, un solo writer Colab, claim prima della prima chiamata, nessuna ripetizione automatica anche dopo timeout/orphan. Un errore è un risultato.
- Non aprire i test OOD, non cambiare i prompt, non modificare RQ1.

**Nota:** `max_http_attempts_guaranteed=None`, `usd_hard_cap_guaranteed=False` rimangono veri e vanno mantenuti in tutti i report.
