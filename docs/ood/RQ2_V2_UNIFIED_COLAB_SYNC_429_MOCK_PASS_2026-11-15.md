# RQ2-V2 — Colab SDK sync HTTP 429: PASS, nessuna API, nessuna release

**Data prova utente:** 15 novembre 2026.  
**Branch:** `feature/rq2-v2-unified-five-harness-three-models-2026-11-14`.  
**Commit provato in Colab:** `442bf7d61762cf5b11b58050d53aa8258ab74e0b` (HEAD pinned).  
**Prova:** `src/tests/rq2_v2_sync_429_retry_probe.py`.  
**Guard:** `src/tests/test_rq2_v2_sync_429_retry_guard_offline.py`.

## Catena delle evidenze

- PyCharm, output utente: `Ran 6 tests in 0.521s\nOK`.
- Colab, output utente: `GIT PIN: OK`, `SDK ISOLATI: PRESENTI`.
- `status: SYNC_HTTP_429_MOCK_ONE_SEND_EACH_NO_API_NOT_RELEASED`.
- Google `CK_tool_free`: `synthetic_429_http_sends=1`, `http_error_observed=true`.
- Google `D_bound_tools`: `synthetic_429_http_sends=1`, `http_error_observed=true`.
- Anthropic `CK_tool_free`: `synthetic_429_http_sends=1`, `http_error_observed=true`.
- Anthropic `D_bound_tools`: `synthetic_429_http_sends=1`, `http_error_observed=true`.
- Totale: `synthetic_429_http_sends_total=4`; `external_provider_requests=0`; `real_credentials_used=false`; checkout di test rimosso.
- `async_streaming_tested=false`; `max_http_attempts_guaranteed=null`; `usd_hard_cap_guaranteed=false`; `scientific_release_frozen=false`; `can_execute_api=false`; `can_run_ood_test=false`.

**Interpretazione:** lo snapshot SDK pinned sul percorso `.invoke` sincrono LangChain → SDK → HTTP in-memory ha trattato gli errori HTTP 429 fittizi senza invii ulteriori *negli esatti quattro casi provati*. Questa evidenza si aggiunge alla prova 503 fittizia (12/11) e alla prova timeout `0.3s` con server loopback (15/11), senza ripeterle.

## Limiti da preservare

- Il probe 429 usa `MockTransport` in-memory. Non verifica una risposta HTTP reale da un provider, la politica di quote dell'account, o l'effetto di header `Retry-After`/backoff non simulati.
- I due percorsi D-bound e CK tool-free provati non equivalgono alla garanzia matematica su ogni chiamata del grafo completo. `max_http_attempts_guaranteed=None` resta corretto.
- Nessuna evidenza di durata massima *dell'intero stage D*: timeout 300 secondi configurato per singola request; probe di stallo usa 0.3s.
- Nessuna garanzia di tetto USD fatturabile. Nessun importo reale autorizzato. Non trasformare il PASS in permesso API o release.
- Nessun GT o Market letto. I 11 casi OOD di Opzione B restano bloccati; nessuna regola di conoscenza validata o trasferita in questa prova.
- RQ1, RQ2 V1, vecchio pilot Sonnet e protocolli congelati non vanno modificati.
- `LIVE_API_ENABLED=False` permane nel dispatcher. Stato nuova V2 unificata: `0/180` stage API.

## Prossima azione

Concludere la valutazione *documentata e circoscritta* del gate sync 503+429+stallo senza avviare altri test indifferenziati. Predisporre **budget operativo ed esplicita approvazione** del primo stage D, previa revisione prezzi/quote provider. Non usare il vecchio contatore RQ2 V1 `D=30,C=30,K=8`: nella nuova matrice ogni modello ha `D=20,C=20,K=20`. Poi effettuare freeze sorgenti/runtimes e creare release G4E/G4F soltanto dopo verifica di ogni prerequisito; approvazione SHA release e conferma per singolo stage sono distinte. Nessun claim o API nel frattempo.
