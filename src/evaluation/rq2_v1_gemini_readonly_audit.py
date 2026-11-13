"""Audit di SOLA LETTURA degli stage Gemini discovery RQ2-V1.

Legge esclusivamente il journal create-only V1 e gli input GT-free gia'
verificati dal repository. NON usa Market.zip, ground truth, scorer,
classi target, chiavi provider, API o i casi OOD test.
Non scrive in Drive ne' nel repository. Non seleziona regole per il test.

Uso in Colab dopo clone dello stesso branch:
    python -m evaluation.rq2_v1_gemini_readonly_audit --data-dir /content/drive/MyDrive/Tesi_OpenRCA
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from evaluation.rq2_discovery_claim_journal import RQ2DiscoveryClaimJournal
from evaluation.rq2_dryrun_plan import DISCOVERY, HARNESSES, VERSION

GEMINI_MODEL = "gemini"
STAGES = ("D", "C", "K")
EXPECTED_V1_STATUS_COUNTS = {
    "RECORDED_COMPLETE": 22,
    "INVALID_OUTPUT": 1,
    "BLOCKED_DEPENDENCY": 1,
}


class GeminiReadOnlyAuditError(ValueError):
    """Non leggere/parzializzare archivi incongruenti o incompleti."""


def expected_gemini_ids() -> tuple[str, ...]:
    return tuple(
        f"{VERSION}:{cid}:{GEMINI_MODEL}:{harness}:{stage}"
        for cid in DISCOVERY for harness in HARNESSES for stage in STAGES
    )


def summarize_verified_gemini(records: list[dict]) -> dict:
    """Riepilogo di dati GIA' verificati: nessuna label, no model output raw.

    Questa funzione NON legittima una K per OOD: anche una candidata
    ben formata resta non verificata finche' un freeze indipendente
    di segnali, unita', aggregazioni e soglie non e' eseguito.
    """
    expected = set(expected_gemini_ids())
    if type(records) is not list or len(records) != 24:
        raise GeminiReadOnlyAuditError("Expected precisely 24 existing Gemini records")

    by_id = {}
    for record in records:
        if type(record) is not dict:
            raise GeminiReadOnlyAuditError("Malformed record")
        sid = record.get("stage_id")
        if type(sid) is not str or sid not in expected or sid in by_id:
            raise GeminiReadOnlyAuditError("Unplanned, duplicate or non-Gemini stage")
        if (
            record.get("logical_model") != GEMINI_MODEL
            or record.get("phase") != "discovery"
            or record.get("status") not in (
                "RECORDED_COMPLETE", "INVALID_OUTPUT", "BLOCKED_DEPENDENCY"
            )
        ):
            raise GeminiReadOnlyAuditError("Record provenance/status invalid")
        if type(record.get("artifact")) is not dict:
            raise GeminiReadOnlyAuditError("Missing artifact dictionary")
        by_id[sid] = record
    if set(by_id) != expected:
        raise GeminiReadOnlyAuditError("Missing/extra Gemini discovery stage")

    status_counts = Counter(record["status"] for record in records)
    if dict(status_counts) != EXPECTED_V1_STATUS_COUNTS:
        raise GeminiReadOnlyAuditError("V1 Gemini status counts drifted from frozen audit")

    cases = []
    c_decisions = Counter()
    k_decisions = Counter()
    k_preflights = Counter()
    for case_id in DISCOVERY:
        for harness in HARNESSES:
            prefix = f"{VERSION}:{case_id}:{GEMINI_MODEL}:{harness}"
            d, c, k = (by_id[prefix + ":" + stage] for stage in STAGES)
            k_info, k_preflight, c_decision = None, None, None
            if c["status"] == "RECORDED_COMPLETE":
                parsed_c = c["artifact"].get("validated_c")
                if type(parsed_c) is not dict or parsed_c.get("decision") not in (
                    "diagnosis", "abstain"
                ):
                    raise GeminiReadOnlyAuditError("Complete C missing strict contract")
                c_decision = parsed_c["decision"]
                c_decisions[c_decision] += 1
            elif c["status"] == "INVALID_OUTPUT":
                c_decisions["invalid_output"] += 1
            else:
                c_decisions["blocked_or_other"] += 1

            if k["status"] == "BLOCKED_DEPENDENCY":
                if k["artifact"]:
                    raise GeminiReadOnlyAuditError("Blocked K has an artifact")
                k_decisions["blocked_dependency"] += 1
            elif k["status"] == "RECORDED_COMPLETE":
                parsed_k = k["artifact"].get("validated_k")
                k_preflight = k["artifact"].get("preflight_status")
                if (
                    type(parsed_k) is not dict
                    or parsed_k.get("status") not in (
                        "candidate", "insufficient_evidence"
                    )
                    or k_preflight not in (
                        "requires_verification", "insufficient_evidence",
                        "not_formalizable"
                    )
                    or k["artifact"].get("scientific_freeze") is not False
                ):
                    raise GeminiReadOnlyAuditError("K contract/freeze status inconsistent")
                k_info = parsed_k["status"]
                k_decisions[k_info] += 1
                k_preflights[k_preflight] += 1
            else:
                k_decisions["invalid_or_error"] += 1

            cases.append({
                "case_id": case_id,
                "harness": harness,
                "D_record_status": d["status"],
                "C_record_status": c["status"],
                "C_decision": c_decision,
                "K_record_status": k["status"],
                "K_contract_status": k_info,
                "K_preflight_status": k_preflight,
            })
    return {
        "audit_id": "rq2_v1_gemini_readonly_audit_v0",
        "provider": GEMINI_MODEL,
        "phase": "discovery",
        "observed_stages": len(records),
        "planned_stages": len(expected),
        "by_record_status": dict(sorted(status_counts.items())),
        "C_decisions": dict(sorted(c_decisions.items())),
        "K_contract_statuses": dict(sorted(k_decisions.items())),
        "K_preflight_statuses": dict(sorted(k_preflights.items())),
        "cases": cases,
        "scientific_k_rules_frozen": 0,
        "can_run_ood_test": False,
        "read_ground_truth": False,
        "model_api_calls": 0,
        "files_written": 0,
        "changed_v1_records": False,
        "technical_validity_is_not_accuracy": True,
    }


def audit_real_gemini_discovery(*, data_dir: Path) -> dict:
    """Carica solo V1 da path sorgente verificato, mai crea claim."""
    root = Path(data_dir)
    if root.is_symlink() or not root.is_dir():
        raise GeminiReadOnlyAuditError("Existing non-symlinked data_dir required")
    journal = RQ2DiscoveryClaimJournal(data_dir=root)
    audit = journal.audit_restart()
    if (
        audit["unresolved_manual_review"] != 0
        or audit["automatic_retry_allowed"] is not False
        or audit["can_execute_api"] is not False
        or audit["can_execute_test"] is not False
    ):
        raise GeminiReadOnlyAuditError("V1 journal integrity gate not satisfied")

    records = []
    for sid in expected_gemini_ids():
        record = journal.store.load_discovery_stage(stage_id=sid)
        if record is None:
            raise GeminiReadOnlyAuditError("Gemini discovery stage missing")
        claim = journal._read_claim(sid)  # verified internal read only
        if record["status"] == "BLOCKED_DEPENDENCY":
            if claim is not None:
                raise GeminiReadOnlyAuditError("Blocked stage must not be claimed")
        elif (
            claim is None
            or claim["model_id_proposed"] != record["model_id_proposed"]
            or claim["dependency_record_hashes"] != record["dependency_record_hashes"]
        ):
            raise GeminiReadOnlyAuditError("Attempted stage claim mismatch")
        records.append(record)
    summary = summarize_verified_gemini(records)
    return {
        **summary,
        "v1_total_claims_all_providers": audit["claims"],
        "v1_total_recorded_all_providers": audit["result_archive_discovery_count"],
        "unresolved_claims": audit["unresolved_manual_review"],
        "source_verified_by_v1_store": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    report = audit_real_gemini_discovery(data_dir=args.data_dir)
    # stdout only: nessun write, raw output modello o ground truth.
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
