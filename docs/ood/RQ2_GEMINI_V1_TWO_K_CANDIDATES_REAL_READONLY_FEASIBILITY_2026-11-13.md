# RQ2 — due candidate K Gemini V1: audit reale read-only e valutazione iniziale di formalizzabilità

**Data:** 2026-11-13. **Origine:** output Colab fornito dall'utente dopo ripristino runtime, con `STATUS: GEMINI_TWO_CANDIDATES_READONLY_AUDIT_OK`. Zero API, zero scritture su Drive, nessuna GT, nessun test OOD aperto.

## Provenienza
- Python runtime restaurato in Colab; repository branch `feature/rq2-v2-sonnet-k-single-live-2026-11-13`, commit `e3b4ce869e2e005ea3b2c0f7b1b287e819e96a6f`; dipendenze pinned installate e `RUNTIME_SNAPSHOT: OK`.
- Gemini V1 discovery: `V1_GEMINI_STAGES: 24` e `CANDIDATES: 2`. I record, `validated_k` e `evaluate_k_formalizability` sono stati riletti dal journal. Il record Sonnet q050/K `insufficient_evidence` resta immutabile.
- La V1 Gemini e la V2 Sonnet sono **protocolli diversi**, non comparabili direttamente come confronto di accuracy.

## Candidate 1 — q026/A1/Gemini
- Record K SHA256: `9d969ca0cce8974c3cd70a67043c2c0039aa53ae7f6dcbafd76e427d9f0d6009`.
- Hypothesis not GT: `high disk iowait and I/O latency`. Rule `node_disk_iowait_latency_spike`; scope `node-6`.
- Evidenze `E001, E005, E006`.
- Segnale A `system.cpu.iowait`, unit `percent`, mean 60 s, threshold >=5.0.
- Segnale B `system.io.await`, unit `ms`, mean 60 s, threshold >=15.0.
- Combination `all`; abstain_when 2, counterexamples 2, limitations 2.
- Preflight `requires_verification`: `aggregation_semantics_unverified`, `market_presence_unverified`, `metric_semantics_unverified`, `physical_unit_unverified`.
- Entrambi nomi KPI sono presenti nel `src/harness/signal_catalog.py`, ma il catalogo li qualifica come `gauge_candidato` non verificato. Questo **non certifica** unità, disponibilità di serie 60s né soglie.

## Candidate 2 — q045/A1/Gemini
- Record K SHA256: `32ddf6815e4216f0a46070950252852cec984f4456a0bb3758c86b16d1296add`.
- Hypothesis not GT: `DNS resolution timeout / DNS lookup failure`. Rule `productcatalogservice_dns_timeout_detector`; scope `productcatalogservice-*`.
- Evidenze `E002, E003, E005`.
- Segnale `service_log_warnings` unit `count`, sum 60 s, threshold >0.0, combination `all`; abstain_when 2, counterexamples 2, limitations 2.
- Preflight `requires_verification`: `metric_not_in_source_catalog`. Il catalogo è specifico per nomi node/container e **non esaustivo per log/service**. Non concludere che il KPI sia inesistente nel benchmark, né costruirlo artificialmente. Per formalizzare occorre definire una estrazione dai log replicabile, non dipendente da GT o da test OOD.

## Decisione successiva
1. Audit in sola lettura dei riferimenti E della candidata q026: nomi esatti, tipo di tool, dimensione, troncamento, se è documentata una serie temporale e campioni per aggregazione 60s. Non trarre prove dalle stringhe modello; controllare codici/schema GT-free e sorgenti development senza accedere a classi/etichette/test OOD.
2. Se q026 manca di dati/semantica o soglie difendibili, non aggiustare le soglie sulla base dei casi OOD. Eventualmente verificare q045 con extractor di log rigorosamente preregistrato e non costruito su GT; se entrambe non formalizzabili, registrare questo risultato senza promuovere nulla.
3. `scientific_freeze=false`, `ready_for_test=false`, `OOD_TEST=LOCKED` per entrambe. Nessun nuovo provider/API, nessuna regola eseguita, nessuna riscrittura di record.

Scadenza tesi 2026-12-01: dare priorità alla verifica rapida, al refactoring e alla scrittura, senza moltiplicare nuove campagne pagate.
