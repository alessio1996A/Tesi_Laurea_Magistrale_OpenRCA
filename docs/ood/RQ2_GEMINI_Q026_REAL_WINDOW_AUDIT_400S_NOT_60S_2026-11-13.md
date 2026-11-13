# RQ2 Gemini q026/A1/K — audit reale delle finestre delle evidenze (sola lettura)

**Data:** 2026-11-13. Fonte: output fornito dall'utente dall'audit Colab `Q026_WINDOW_SOURCE_AUDIT_OK`. Nessuna API, scrittura Drive, GT, regola eseguita, sblocco OOD.

## Risultati
- Candidata Gemini V1 `node_disk_iowait_latency_spike`, K frozen record `9d969ca0cce8974c3cd70a67043c2c0039aa53ae7f6dcbafd76e427d9f0d6009`; status `candidate` e `requires_verification`, **NON scientificamente congelata**.
- E001: `tool_get_node_metrics`, node-6, `system.cpu.iowait`, `[1647784800,1647786600)` = **1800 s**, campioni 30, media 6.298, min 5.45, max 10.95, `primo_timestamp=1647784800`, `ultimo_timestamp=1647786540`, no truncation.
- E005: `tool_get_node_metrics`, node-6, `system.io.await`, `[1647784800,1647785200)` = **400 s**, campioni 7, media 18.011429, min 0.67, max 35.76, primo=1647784800, ultimo=1647785160, no truncation.
- E006: `tool_get_node_metrics`, node-6, `system.cpu.iowait`, stesso intervallo **400 s** di E005, campioni 7, media 7.381429, min 5.51, max 10.95, primo=1647784800, ultimo=1647785160, no truncation.
- `IOWAIT_ALIGNED_WITH_AWAIT=['E006']`, `SAME_NODE_AND_EXACT_60S_WINDOW=False`.
- Le medie sull'intervallo 400s superano numericamente le soglie generate `iowait>=5` e `io.await>=15`, ma NON verificano condizioni `mean` su finestre di **60s**. La lettura di timestamp estremi NON dimostra disponibilità di una serie time-resolved campionata per calcolare sliding windows. Soglie, unità e causalità NON verificate. **Non** sostituire post hoc la regola con soglia/finestra 400s.
- `TIME_SERIES_60S_VERIFIED=FALSE`, `UNITS_VERIFIED=FALSE`, `THRESHOLDS_VALIDATED=FALSE`, `SCIENTIFIC_FREEZE=FALSE`, `RULE_EXECUTED=FALSE`, `API_CALLS=0`, `DRIVE_WRITES=0`, `GROUND_TRUTH_READ=FALSE`, `OOD_TEST=LOCKED`.

## Verifica codice
`src/agent/tools.py::tool_get_node_metrics` calcola statistiche aggregate sull'intera finestra richiesta e restituisce `campioni,media,minimo,massimo,primo_timestamp,ultimo_timestamp`, NON time-series completa o medie di 60s automatiche. Candidata potenzialmente formalizzabile solo con un **nuovo gate indipendente** su sorgenti di telemetria GT-free development, semantica/unità, allineamento e criterio di finestra 60s PRIMA dell'eventuale OOD; non promuovere la sola media 400s.

## Next pragmatic gate
Audit della seconda candidata Gemini V1 `cloudbed-2_q045/A1/K` `productcatalogservice_dns_timeout_detector`, frozen SHA `32ddf6815e4216f0a46070950252852cec984f4456a0bb3758c86b16d1296add`. Essa utilizza `service_log_warnings` count/sum 60s >0, nome non presente nel catalogo node/container non esaustivo per log. Prima verificarne fonte e argomenti E002,E003,E005 in sola lettura, senza inventare extractor né cercare risultati OOD. Se nessuna proposta supera il gate, RQ2-C non verificata; concentrare conclusione su astensioni e limiti.
