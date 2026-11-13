# RQ2 — Gemini V1 q026 candidate, node metrics aggregation semantics and next quick audit

Date: 2026-11-13. No API calls, GT, write to frozen Drive, K retry or OOD data.

## User read-only audit from Colab
```text
STATUS: GEMINI_Q026_EVIDENCE_INSPECTION_OK
RULE: node_disk_iowait_latency_spike
ALL_METRIC_NAMES_KNOWN_IN_CODE: True
EVIDENCES_IN_BUNDLE: 6
TRUNCATED_IN_BUNDLE: 0

EVIDENCE: E001
TOOL: tool_get_node_metrics
TRUNCATED: False
OBSERVATION_CHARS: 362
VISIBLE_NAME_PRESENT: system.cpu.iowait True
VISIBLE_NAME_PRESENT: system.io.await False
VISIBLE_TIMESTAMP_FIELD_HINT: True

EVIDENCE: E005
TOOL: tool_get_node_metrics
TRUNCATED: False
OBSERVATION_CHARS: 361
VISIBLE_NAME_PRESENT: system.cpu.iowait False
VISIBLE_NAME_PRESENT: system.io.await True
VISIBLE_TIMESTAMP_FIELD_HINT: True

EVIDENCE: E006
TOOL: tool_get_node_metrics
TRUNCATED: False
OBSERVATION_CHARS: 365
VISIBLE_NAME_PRESENT: system.cpu.iowait True
VISIBLE_NAME_PRESENT: system.io.await False
VISIBLE_TIMESTAMP_FIELD_HINT: True

TIME_SERIES_60S_VERIFIED: FALSE
UNITS_VERIFIED: FALSE
THRESHOLDS_VALIDATED: FALSE
RULE_EXECUTED: FALSE
SCIENTIFIC_FREEZE: FALSE
API_CALLS: 0
DRIVE_WRITES: 0
GROUND_TRUTH_READ: FALSE
OOD_TEST: LOCKED
```

Candidate K frozen record SHA `9d969ca0cce8974c3cd70a67043c2c0039aa53ae7f6dcbafd76e427d9f0d6009`, hypothesis not GT disk I/O, scope node-6, KPI `system.cpu.iowait` mean 60 s >=5 percent AND `system.io.await` mean 60 s >=15 ms. Candidate is `requires_verification`, scientific_freeze=false.

## Source inspection (GitHub code ref `e3b4ce869e2e005ea3b2c0f7b1b287e819e96a6f`)
`src/agent/tools.py::tool_get_node_metrics`:
- For each requested `[start_unix,end_unix)`, filters `metric_node.csv` (numeric timestamp/value), component and regex KPI.
- Aggregates **all numeric rows in the entire requested interval** by `(cmdb_id,kpi_name)`, computes `campioni`, `media` (sum/count), `minimo`, `massimo`, `primo_timestamp` and `ultimo_timestamp`.
- It **does not return individual time-series samples** or compute sliding 60-second means. First/last timestamps only mark extrema of observed coverage, not complete sampling series.
- Even if observations E001/E005 cite two KPI names, this is insufficient to prove both conditions are computed over the *same* 60-second interval on node-6. Their underlying `arguments.start_unix,end_unix,cmdb_id` must be inspected, and returned data lines must show correct node and KPI. E006 may be a second iowait window.
- If each tool query happens to span exactly 60 s and aligns, the tool's mean can be a 60s interval mean (subject to coverage and sampling), but this does not prove correct percent/ms units, numeric thresholds, baselines, causality, or an implementable portable detector.
- Do not invent metric values or infer that the two conditions passed; thresholds are proposed by the LLM, not validated.
- Safer next quick gate: read-only inspection of E001/E005/E006 tool arguments and max 600-char observed summary. Print window durations and alignment, without reading Market.zip, GT, or OOD. Decide feasibility after results. Do not create a rule or alter existing K JSON.

## Context
The second Gemini K candidate q045 DNS uses `service_log_warnings`, outside node/container KPI catalog. This does not prove unavailability in log telemetry; requires separately specified, GT-free log extractor and no test-label feedback.
The Sonnet q050 K produced `insufficient_evidence` (not candidate), is frozen and cannot be retried. The 11 OOD test cases remain sealed. Thesis deadline: 2026-12-01.
