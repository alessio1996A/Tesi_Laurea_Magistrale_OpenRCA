"""Diagnostica prestazionale riproducibile del journal RQ2-V2 (NO API).

Esecuzione: python -B src/tests/profile_rq2_v2_unified_journal_offline.py
Sfrutta SOLO le fixture sintetiche dei test G3A, in TemporaryDirectory.
Non legge Market.zip/GT/Drive, non crea client provider, non cambia i gate.

Scopo: individuare costo cumulativo di audit_restart/letture/hash senza
ottimizzazioni premature o perdita di controlli di integrita'.
"""
from __future__ import annotations

import cProfile
import io
import pstats
import tempfile
import time
from pathlib import Path

from evaluation.rq2_v2_artifact_store import MARKER, MARKER_BYTES
from evaluation.rq2_v2_unified_synthetic_journal import (
    UnifiedRQ2SyntheticJournal,
)
from test_rq2_v2_unified_synthetic_journal import (
    cause, fake_run, model_id, rule, sid,
)

# Un modello soltanto: riproduce i 5 percorsi harness e accumula 15 record.
# La diagnostica non dichiara che Gemini reale sia stato eseguito.
MODEL = "gemini"
HARNESSES = (
    "A0", "A1", "A1_8R", "A1_8R_Planning", "A1_PAVE",
)


def main() -> None:
    print("STATUS: RQ2_V2_UNIFIED_JOURNAL_PROFILE_SYNTHETIC_ONLY", flush=True)
    print("MODEL_LABEL:", MODEL, flush=True)
    print("HARNESSES:", ", ".join(HARNESSES), flush=True)
    print("API_CALLS: 0 | GT_READ: FALSE | MARKET_READ: FALSE", flush=True)

    profile = cProfile.Profile()
    timings = []
    with tempfile.TemporaryDirectory(prefix="rq2_v2_journal_profile_") as tmp:
        root = Path(tmp)
        (root / MARKER).write_bytes(MARKER_BYTES)
        journal = UnifiedRQ2SyntheticJournal(data_dir=root)
        profile.enable()
        start = time.perf_counter()
        for harness in HARNESSES:
            for stage in ("D", "C", "K"):
                stage_id = sid(MODEL, harness, stage)
                stage_start = time.perf_counter()
                journal.claim_stage(
                    stage_id=stage_id,
                    model_id=model_id(MODEL),
                )
                if stage == "D":
                    artifact = {
                        "diagnostic_run": fake_run(MODEL, harness),
                    }
                elif stage == "C":
                    artifact = {"raw_response": cause()}
                else:
                    artifact = {"raw_response": rule()}
                journal.record_stage(
                    stage_id=stage_id, model_id=model_id(MODEL),
                    status="RECORDED_COMPLETE", artifact=artifact,
                )
                duration = time.perf_counter() - stage_start
                timings.append((harness, stage, duration))
                print(
                    "STAGE_TIME_SEC:", harness, stage,
                    f"{duration:.3f}", flush=True,
                )

        audit_start = time.perf_counter()
        audit = journal.audit_restart()
        final_audit_duration = time.perf_counter() - audit_start
        elapsed = time.perf_counter() - start
        profile.disable()
        assert audit["claims"] == 15, audit
        assert audit["stored_stage_records"] == 15, audit
        assert audit["matched_claim_records"] == 15, audit
        assert audit["unresolved_claims_for_manual_review"] == 0, audit
        assert audit["can_execute_api"] is False
        assert audit["can_run_ood_test"] is False
        assert not (root / "Market.zip").exists()
        assert not (root / "data/rq2").exists()

    print("STATUS: OFFLINE_PROFILE_INTEGRITY_OK", flush=True)
    print("ALL_STAGES_SEC:", f"{sum(t[2] for t in timings):.3f}")
    print("FINAL_AUDIT_SEC:", f"{final_audit_duration:.3f}")
    print("PROFILE_TOTAL_SEC:", f"{elapsed:.3f}")
    print("CLAIMS_AND_RECORDS: 15 / 15")
    print("UNRESOLVED_CLAIMS: 0")
    print("TOP_CUMULATIVE_FUNCTIONS:")
    output = io.StringIO()
    pstats.Stats(profile, stream=output).strip_dirs().sort_stats(
        "cumulative"
    ).print_stats(22)
    print(output.getvalue())
    print("FILES_LEFT_ON_DRIVE: 0")
    print("MODEL_API_CALLS: 0")


if __name__ == "__main__":
    main()
