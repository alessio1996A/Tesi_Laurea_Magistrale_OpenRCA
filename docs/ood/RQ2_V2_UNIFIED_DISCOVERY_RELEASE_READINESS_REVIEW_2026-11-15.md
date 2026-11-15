# RQ2-V2 — Review finale prerelease Opzione A (NO API, NO RELEASE)

Data: 15 novembre 2026. Documento di review tecnico-scientifica; **non** e' un comando per creare il file release e non e' un consenso economico.

## Evidenza di codice realmente verificata

Commit PINNATO in Colab: `feb7b7c9684138f348d8a6e3e6e9d4eb61798ae7`. Source preflight GT-free 30/30 PASS su SDK isolato 6 versioni e 4 provider source SHA frozen; nessuna API. Contatore nuove verifiche locali: 18/18 K rubrica e 55/55 source/blueprint/release contract PASS.

Hash verificati:
- `source_inventory_sha256=8c2d022efed45214fec27b31ab4d7215f2912cd494aa6e16d3afaa55d8e891a1`.
- `k_rubric_sha256=d8b969d33e2e042ab44121a9b6e089fa96a4aa2b8be03cb31b3edeede6f83f52`.
- `blueprint_sha256=22005361b35c9873822fec37163cd55f00d4a2a1c697a5939ac0a5a4ec3b9270`.
- `source_plan_sha256=e6f797c4ca01ed422b80e928854469b9f8c7f7cc4215835bf91f9f7305425a00`.
- Split `c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724`; manifest `5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13`.
- Prompt C `81a5800500b3fafc23af4b7643e79a3d206c3ca6c80f6924514001ec85dc2a42`; K `0935e2b7232715b623bb174f0a059387659f8d9bc7939804c8a372d8aa27ba71`.

Modifiche su GitHub DOPO il commit Colab testé verificato sono state di sola documentazione; gli hash sorgente nel report rimangono validi **per il commit esattamente testato**. La release vera dovra' referenziare espressamente il commit finale clean eseguito, non attribuire retroattivamente un run a un altro HEAD.

## Politiche che NON cambiano

- Disegno: 4 discovery × 5 harness × 3 LLM × D→C→K = 180 stage logici (60 D, 60 C, 60 K). Dopo errore upstream, C/K blocked nel denominatore. Regole K candidate non sono diagnostiche validate; valutazione K preregistrata offline e senza GT.
- OOD: 11 test ancora LOCKED; nessun risultato Option B, nessuna contaminazione da etichette.
- Connessione: percorsi sync source-pinned; prove fake HTTP 503/429 e stall 0.3s PASS negli scenari osservati. Timeout della factory 300s per request, NO stage-wide guarantee, NO provider billing hard cap, `max_http_attempts_guaranteed=None`.
- Journal: namespace `data/rq2_v2_unified_scientific_v1` **assente** prima della release; create-only claim + `flock` single-writer verificato nella stessa sessione Drive; record dopo e no auto retry; orphan e ogni errore non si ritentano automaticamente.
- Stato attuale: `src/evaluation/rq2_v2_unified_live_dispatcher.py` ha `LIVE_API_ENABLED=False`. Release scientifica assente, 0/180 stage reali.
- Budget: il relatore preferisce integrita' scientifica alla micro-ottimizzazione dei costi; la release software **richiede comunque** importo positivo approvato in USD e riferimento reale. Non e' hard cap; non inferire consenso di spesa dalla dichiarazione generale del relatore.

## Sequenza esatta per rendere *possibile* un singolo D reale

1. **Decidere il perimetro scientifico definitivo**: nessuna modifica ai cinque harness, ai tre modelli, alle quattro discovery, a D/C/K, alla rubrica K o ai prompt. Mantenere 11 OOD isolati.
2. **Preparare su GitHub, in modo controllato e solo dopo verifica manuale, la versione live-capable**. Il dispatcher corrente e' disabilitato e non può eseguire alcuna chiamata; un'eventuale attivazione del dispatcher modifica un sorgente della lista `SOURCE_PATHS` e **richiede un nuovo clean HEAD e preflight completo su 30 sorgenti**. Non anticipare il flip per un test.
3. **Freeze definitivo**: audit reale Colab commit/source/runtime/CSV GT-free, numero 180, 11 OOD LOCKED; source SHA e blueprint SHA associati al nuovo HEAD. Nessuna API durante l'audit. Non copiare `source_inventory_sha256` del commit precedente dopo una modifica di sorgente.
4. **Release create-only**: costruire un manifesto canonico G4E con i campi e le flag validate, nessun campo sconosciuto, budget operativo positivo realmente autorizzato e riferimento umano reale. Approvare **esternamente** il suo SHA-256; scriverlo **una sola volta** nel namespace scientifico separato su Drive, con `O_EXCL`/fsync/readback. Il solo digest non e' una firma personale.
5. **Singolo pilot**: richiedere consenso esplicito per `rq2_v2_unified_five_harness_discovery_v0:cloudbed-1_q032:gemini:A0:D`, oltre a release e budget. Eseguire un solo writer/sessione e un solo `claim` prima del primo SDK invoke; conservare errori/token/tempo senza retry. Se crash, fermarsi per audit manuale. NON auto-eseguire C/K, tutti gli altri 179 stage o i test OOD.
6. **Audit dopo il pilot**: stato D, provenance tool_call_id, token usage completo/incompleto, provider failures, costi stimati vs reali se disponibili. Solo allora valutare se autorizzare la restante discovery.

**Nessuna voce sopra implica che i punti 2–6 siano gia' completati.** Soprattutto **non** settare flag G4E `true` senza che la specifica evidenza nel perimetro sync sia accettata esplicitamente: guardare i mock non equivale a una garanzia universale.

## Refactoring solo a fine dati

Come richiesto dall'utente: refactoring, commenti/docstring in italiano, rimozione ragionata dei file superflui e riordino repository su branch separato DOPO freeze dati/audit. Non alterare record scientifici grezzi o timeline Git.
