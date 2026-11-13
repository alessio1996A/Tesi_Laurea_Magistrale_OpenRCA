# RQ2 — Gemini q045: evidence audit for proposed log-warning detector (read-only)

**Data:** 2026-11-13. User-provided output `GEMINI_Q045_LOG_EVIDENCE_AUDIT_OK`; no provider, no Drive writes, no GT, no OOD test.

## Record K and contract
- Gemini V1 `cloudbed-2_q045/A1/K`, frozen record SHA `32ddf6815e4216f0a46070950252852cec984f4456a0bb3758c86b16d1296add`.
- Proposed `productcatalogservice_dns_timeout_detector`, scope `productcatalogservice-*`, candidate KPI `service_log_warnings`, `count` and `sum` in 60s with `>0`; status `candidate`, preflight `requires_verification`; `scientific_freeze=false`. This is model-generated text, not verified semantics or DNS cause.
- Proposed evidence references E002,E003,E005, all `tool_get_logs` with `log_type=service`, selected cmdb_id instances -0, -1, -2, `[1647820800,1647822600)` (1800s); max_rows=20. E002 returned 2 rows, E003 6 rows, E005 4 rows; NONE of these 3 selected observations truncated (global evidence bundle truncated_count=1 in some other E).
- E002 `CONTAINS_WARN=True`, `CONTAINS_DNS=False`, `CONTAINS_TIMEOUT=True`. Observed log preview includes `severity: warning` and `dial tcp: lookup basic-tidb-external...`; event 1647821920.
- E003 `CONTAINS_WARN=True`, `CONTAINS_DNS=False`, `CONTAINS_TIMEOUT=False`; preview shows `unexpected EOF` log rows, event 1647821906. `warn` substring does NOT guarantee that each row has explicit severity or represents DNS.
- E005 `CONTAINS_WARN=True`, `CONTAINS_DNS=False`, `CONTAINS_TIMEOUT=True`; preview includes `severity: warning` and dial tcp lookup, event 1647821918.
- None of E002/E003/E005 contains the declared metric string `service_log_warnings`. The underlying tool `src/agent/tools.py::tool_get_logs` returns selected log rows with timestamps and text; it DOES NOT define a 60s warning counter, severity parser or deterministic DNS detector.

## Interpretation, next data gate
- The observations support a **possible** reproducible 60s log-event count, unlike solely whole-window KPI means. They do **NOT** independently prove a correct DNS diagnosis or a validated detector; `warn` substring and log text `lookup` do not establish unit semantics or false-positive rate.
- To understand feasibility, a single read-only *discovery-only* telemetry audit can stream only `Market/cloudbed-2/telemetry/<date>/log/log_service.csv`, with source-verified GT-free split/manifest, only q045 discovery time and `productcatalogservice-` scope, and count exact literal `severity: warning` per explicitly anchored 60s bucket. Keep output aggregate-only, no raw logs/GT/case-level heldout rows. Daily file may physically contain other cohorts: filter by discovery interval **before aggregation**; do not inspect test intervals or test predictions. This would be *post-hoc candidate operationalization*, not a preregistered/verified rule.
- Need independent catalog/extractor definition and checks on healthy/development-only data plus the exact policy for warning severity, 60s rolling/tumbling/aggregation, missing data and broader false positives BEFORE any rule freeze. No future threshold/window alteration to force q045 to succeed.
- q026 other candidate `node_disk_iowait_latency_spike` has two aligned 400s whole-window means for iowait and await, NOT the declared 60s means; not frozen. Sonnet q050 K is valid `insufficient_evidence`, not a rule. 11 OOD test queries remain locked.
