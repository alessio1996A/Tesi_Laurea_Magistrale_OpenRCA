"""RQ2 D->C->K offline MOCK integration using existing validated components.

This is an integration-test helper, NOT a real runner. No models, providers,
telemetry, dataset or scoring are imported or invoked. A caller must supply
synthetic D, C and optionally K outputs and a disposable RQ2MockJournal.

The only I/O performed is via the existing MOCK create-only receipt journal.
It does not save the synthetic D/C/K content, alter RQ1, or unlock real test
inference. Any mock discovery freeze remains MOCK_ONLY_NOT_RULE_FREEZE.
"""
from __future__ import annotations

from evaluation.rq2_dryrun_plan import PLAN_STATUS
from evaluation.rq2_evidence_bundle import (
    EvidenceBundleError, build_evidence_bundle, evidence_ids,
)
from evaluation.rq2_kpi_formalizability_preflight import evaluate_k_formalizability
from evaluation.rq2_mock_journal import RQ2MockJournal, MockJournalError
from evaluation.rq2_output_contracts import (
    ContractError, validate_candidate_rule, validate_cause_probe,
)
from evaluation.rq2_stage_binding import (
    ALLOWED_TOOLS, StageBindingError, _validate_plan,
    prepare_bound_c, prepare_bound_k,
)

VERSION = "rq2_mock_pipeline_integration_v0"


class MockPipelineError(ValueError):
    """Mock-only inputs or dependency/provenance checks failed."""


def validate_mock_dck_without_io(
    *,
    plan: dict,
    c_stage_id: str,
    original_instruction: str,
    synthetic_d: dict,
    synthetic_c_json: str,
    synthetic_k_json: str | None = None,
) -> dict:
    """Validate an entire synthetic stage package BEFORE writing receipts.

    Does not call an LLM, use telemetry, or emit D/C/K content. C is mandatory.
    K is mandatory for discovery and forbidden for test.
    """
    try:
        entries = _validate_plan(plan)
        c = entries.get(c_stage_id)
        if c is None or c["stage"] != "C":
            raise MockPipelineError("Not a planned C stage")
        discovery = c["phase"] == "discovery"
        if discovery != (synthetic_k_json is not None):
            raise MockPipelineError("K is required for discovery, forbidden in test")

        c_package = prepare_bound_c(
            plan=plan, c_stage_id=c_stage_id,
            original_instruction=original_instruction,
            diagnostic_run=synthetic_d,
        )
        bundle = build_evidence_bundle(
            synthetic_d["tool_trajectory"], allowed_tool_names=ALLOWED_TOOLS,
        )
        allowed = evidence_ids(bundle)
        validate_cause_probe(
            synthetic_c_json, allowed_evidence_ids=allowed,
        )

        k_package = None
        k_status = None
        formalizability = None
        if discovery:
            k_stage_id = c_stage_id.rsplit(":", 1)[0] + ":K"
            if k_stage_id not in entries:
                raise MockPipelineError("No planned discovery K")
            k_package = prepare_bound_k(
                plan=plan, k_stage_id=k_stage_id,
                original_instruction=original_instruction,
                diagnostic_run=synthetic_d,
                prior_c_binding=c_package,
                cause_raw_json=synthetic_c_json,
            )
            rule = validate_candidate_rule(
                synthetic_k_json, allowed_evidence_ids=allowed,
            )
            k_status = rule["status"]
            formalizability = evaluate_k_formalizability(
                synthetic_k_json, allowed_evidence_ids=tuple(sorted(allowed)),
            )
            if formalizability["ready_for_test"]:
                raise MockPipelineError("Mock rule cannot become test ready")

        d_stage_id = c["dependencies"][0]
        return {
            "integration_version": VERSION,
            "status": "MOCK_VALIDATED_NOT_EXECUTABLE",
            "phase": c["phase"],
            "stage_ids": (
                [d_stage_id, c_stage_id, k_package["stage_id"]]
                if discovery else [d_stage_id, c_stage_id]
            ),
            "plan_preview_sha256": plan["preview_sha256"],
            "c_binding_sha256": c_package["binding_sha256"],
            "k_binding_sha256": (
                k_package["binding_sha256"] if k_package else None
            ),
            "observation_count": bundle["observations_count"],
            "truncated_count": bundle["truncated_count"],
            "c_output_contract_valid": True,
            "k_output_contract_status": k_status,
            "k_formalizability_status": (
                formalizability["status"] if formalizability else None
            ),
            "rule_executed": False,
            "read_ground_truth": False,
            "read_market": False,
            "model_api_calls": 0,
            "can_execute_api": False,
            "ready_for_test": False,
            "files_written": False,
        }
    except (StageBindingError, EvidenceBundleError, ContractError) as exc:
        raise MockPipelineError("Mock D/C/K validation failed: " + str(exc)) from exc


def record_mock_stages(
    *,
    journal: RQ2MockJournal,
    plan: dict,
    c_stage_id: str,
    original_instruction: str,
    synthetic_d: dict,
    synthetic_c_json: str,
    synthetic_k_json: str | None = None,
) -> dict:
    """Persist *mock receipts* only; the real API execution remains forbidden.

    Every synthetic C/K input is validated first. No receipt is emitted on
    invalid input. The journal enforces create-only and test-phase mock gate.
    """
    if not isinstance(journal, RQ2MockJournal):
        raise MockPipelineError("Requires the existing mock-only journal")
    report = validate_mock_dck_without_io(
        plan=plan,
        c_stage_id=c_stage_id,
        original_instruction=original_instruction,
        synthetic_d=synthetic_d,
        synthetic_c_json=synthetic_c_json,
        synthetic_k_json=synthetic_k_json,
    )
    if (
        journal.plan_sha != report["plan_preview_sha256"]
        or journal.entries.get(c_stage_id) != _validate_plan(plan)[c_stage_id]
    ):
        raise MockPipelineError("Journal and plan identity differ")
    try:
        audit = journal.resume_audit()
        if report["phase"] == "test" and not audit["discovery_mock_frozen"]:
            raise MockPipelineError("Test blocked until MOCK discovery freeze")
        # Fail BEFORE partial receipts on an existing, completed stage.
        for sid in report["stage_ids"]:
            if journal._completed(sid) is not None:
                raise MockPipelineError("Mock stage already completed")
        for sid in report["stage_ids"]:
            journal.mark_mock_complete(sid)
    except MockJournalError as exc:
        raise MockPipelineError("Mock journal refused stage: " + str(exc)) from exc
    return {
        **report,
        "status": "MOCK_RECEIPTS_CREATED_NOT_REAL_RUNS",
        "mock_receipts_created": len(report["stage_ids"]),
        "files_written": True,
        "written_artifact_type": "disposable_mock_receipt_only",
    }
