# RQ2 — Decisione metodologica q045 dopo audit del contratto K originale (14 novembre 2026)

**Origine:** output reale fornito dall'utente da audit Colab in sola lettura.
`STATUS: Q045_ORIGINAL_K_CONTRACT_READONLY_OK`, zero API, zero scritture Drive, zero GT, zero esecuzioni della regola, OOD test ancora bloccati.

## Identità e provenienza

- Gemini V1 discovery `cloudbed-2_q045`, harness `A1`, K `productcatalogservice_dns_timeout_detector`.
- SHA-256 record K congelato: `32ddf6815e4216f0a46070950252852cec984f4456a0bb3758c86b16d1296add`.
- `scientific_freeze=false`. Candidate K non valida come regola pronta per il test OOD.

## Contratto originale, inalterato

```json
{
  "required_signals": [
    {"aggregation":"sum","metric":"service_log_warnings","unit":"count","window_seconds":60}
  ],
  "conditions": [
    {"aggregation":"sum","metric":"service_log_warnings",
     "operator":">","threshold":0.0,"unit":"count","window_seconds":60}
  ],
  "combination":"all",
  "abstain_when": [
    "When DNS infrastructure is under scheduled maintenance",
    "When log collection agents are experiencing transport delays"
  ],
  "counterexamples": [
    "Transient network glitches that do not result in service log warning patterns for DNS timeouts",
    "Database connection resets unrelated to DNS resolution failures"
  ],
  "limitations": [
    "Relying on service logs rather than direct metric counters may introduce a short detection delay",
    "Trace logs were truncated during discovery, limiting end-to-end latency correlation"
  ]
}
```

## Real observations without extrapolation

- Discovery q045 read-only log audit (window 1800 s): 12 scoped service log rows, 6 explicit `severity: warning` rows, 5 (service instance, 60-s bucket) cells, not necessarily 5 distinct time intervals; no GT, not a DNS cause proof.
- Independent development-only read-only audit: 92 development cases included in input partition; 4 log files read; 116 scoped rows, 100 explicit warnings, 7 (cloudbed, 60-s bucket) cells; all scoped rows and warnings in cloudbed-2. These are raw rows, **not** independent faults; no event-ID dedup or log collection completeness certified. HEAD `c2bed47a9f61ac6ac67223c47a9b55e680d6f0ee`.
- Synthetic prototype tests 31/31 PASS and development log audit fixture tests 20/20 PASS in PyCharm. These are **software unit tests**, not experiment diagnoses.

## Why this cannot be frozen scientifically as a DNS detector

1. `service_log_warnings` was not a source-defined metric; the regex `severity\\s*:\\s*warning`, UTC 60-s tumbling buckets and service-instance pooling were operational choices made *after* observing discovery. They are not specified by the original K output.
2. The sole condition `sum(warnings)>0` is generic: **no DNS lookup/timeout predicate** appears in its actual machine-evaluable condition. Counterexample explicitly identifies non-DNS database resets; a warning can accompany unrelated faults. Thus a positive warning decision cannot be interpreted as a verified DNS diagnosis.
3. Two explicit abstention conditions require external evidence: scheduled DNS maintenance status and log-agent transport delays. No verified telemetry/metadata contract for either exists in the current proof. Defaulting such unknowns to false would override the model's K contract.
4. Log stream completeness is unproven. The synthetic `complete_windows` flag is deliberately caller-supplied and synthetic-only; it cannot justify real-data negatives when no warnings are observed.
5. Development telemetry presence shows observability; no class-level specificity, false-positive rate, causal relation, independent negative controls or generalization have been measured. The 11 test OOD cases have remained sealed.

## Decision

- **Do NOT promote q045 to scientific freeze**, do NOT run q045 on the 11 OOD test cases, do NOT report positive generalization or a negative test result, do NOT silently rewrite the K conditions to include DNS text.
- Label the RQ2 knowledge-transfer outcome **'estrazione di candidate strutturalmente valide e segnali osservabili; trasferimento/generalizzazione non verificati'**, not 'trasferimento fallito': the OOD test was *not performed*, so no empirical failure of generalization was observed.
- Keep q026 separate: KPI names validated in source and 400-second aligned summary means, not the original requested 60s means; no valid scientific freeze. Sonnet V2 q050 K legitimately abstained (`insufficient_evidence`).
- **Stop adding paid runs, detector variants or extra exploratory branches for the present thesis submission**. Preserve current original data, hashes, existing test artifacts and all frozen RQ1 evidence.
- Enter final **refactoring/organization** phase in a separate consolidation branch after inventory. Comment/document in Italian, remove redundant temporary files only after proving they are unreferenced, maintain Git tags/commits for auditability; test targeted areas, then full regression. Write thesis with claims carefully separated (RQ1 measured results vs RQ2 feasibility/limitations). No human-in-loop implementation.

**Deadline:** tesi da consegnare entro 2026-12-01.
