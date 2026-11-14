# RQ2 q045 — extractor/prototype synthetic-only, not scientific freeze

Date 2026-11-14. New branch `feature/rq2-q045-warning-detector-synthetic-2026-11-14` based on frozen K live source commit `e3b4ce869e2e005ea3b2c0f7b1b287e819e96a6f`.

## Files added
- `src/evaluation/rq2_q045_warning_detector_synthetic.py`: pure function `inspect_synthetic_warning_windows`, **only accepts `phase="synthetic"`**, no files, no Market/GT/test case, no API, no generated pseudocode. Explicit 60-s UTC epoch-aligned nonoverlapping buckets; scope `productcatalogservice-*`; pooled count across service instances; regex `severity\s*:\s*warning` case-insensitive; `sum > 0`; duplicate exact log_id+timestamp+component+message deduplicated; conflicting same log_id rejected; malformed/unknown events rejected; explicit per-bucket completeness required: incomplete -> abstain even when positive, complete with no warning -> negative (ONLY as synthetic assumption); never marks candidate scientifically frozen.
- `src/tests/test_rq2_q045_warning_detector_synthetic.py`: 31 targeted synthetic tests including time boundaries, all values, invalid coverage, no accidental test/development phase, out-of-scope rows, duplicates, untrusted text inert and no API/writes.
- This file documents the gate; no existing code or frozen artifact modified.

## Source candidate
Gemini V1 `cloudbed-2_q045/A1/K` source record SHA `32ddf6815e4216f0a46070950252852cec984f4456a0bb3758c86b16d1296add`. The K JSON says `service_log_warnings` count/sum in 60 s >0, productcatalogservice-* scope; it does **not** specify regex, handling missing coverage, pooling of instances, dedup or window anchoring. All of those were specified **post-hoc** and therefore should NOT be represented as original Gemini rule or independently validated transfer. Discovery-only exploratory audit counted 6 explicit warnings among 12 events; 5 (instance,bucket) cells, two global 60s buckets, 77s first-to-last event span.

## Scientific boundary
- Synthetic tests establish **software behavior**, not presence/precision of detector in OpenRCA.
- **No rule OOD test or scientific freeze** is authorized by this branch, even if all tests pass.
- Only after code gate passes, consider a distinct GT-free development-only source adapter to verify log completeness/availability on independent non-holdout windows; source guard must derive permitted windows from original hash-checked split and exclude all OOD holdout and test times. Do not retrofit design after viewing OOD.
- Before any RQ2-C outcome study, independently preregister exact semantics and criteria, include broad warning specificity vs DNS causality caveat, freeze code and criteria, score on 10 OOD temporal groups only after authorization via isolated post-freeze evaluation.
- Existing RQ1 results and Gemini V1/Sonnet V2 D/C/K records remain unchanged. No human-in-loop implementation.

## User PyCharm single targeted check
```powershell
git status --short
git fetch origin feature/rq2-q045-warning-detector-synthetic-2026-11-14
git switch feature/rq2-q045-warning-detector-synthetic-2026-11-14
git pull --ff-only
$env:PYTHONPATH = "src"
python -m unittest discover -s src/tests -p "test_rq2_q045_warning_detector_synthetic.py" -v
```
Expect 31 tests, but **DO NOT claim PASS until user reports output**. Do not rerun unrelated full test suite now; user prefers full cleanup/regression at end.
