"""G4H — source-bound preview di UN SOLO stage scientifico Opzione A.

Questa e' la frontiera di PREPARAZIONE del futuro dispatcher LIVE:
legge il manifest GT-free gia' SHA-verificato, la release e i record
D/C/K create-only; costruisce il package C/K dai record immutabili.

NON crea un client, un claim, un modello, un output, un file o una
richiesta API. Anche un esito PASS NON autorizza il pilot pagato.
Per l'esecuzione sara' necessario un dispatcher successivo con
controlli di approvazione specifica, limiti operativi e trasporto.

Non usare il piano RQ2 V1 per interpretare questi stage:
questo modulo legge ESCLUSIVAMENTE i 180 ID della RQ2-V2 unificata.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from evaluation.experiment_config import ExperimentConfig
from evaluation.rq2_probe_adapter import (
    CAUSE_SYSTEM, RULE_SYSTEM,
    prepare_candidate_rule, prepare_cause_probe,
)
from evaluation.rq2_stage_binding import ALLOWED_TOOLS
from evaluation.rq2_v2_unified_discovery_plan import (
    MAX_TOOL_ROUNDS, MAX_VERIFICATION_CHECKS, RECURSION_LIMIT,
)
from evaluation.rq2_v2_unified_scientific_ledger import (
    UnifiedScientificLedger,
)
from evaluation.rq2_v2_unified_scientific_ledger_preflight import (
    RELEASE_FILE,
)
from evaluation.rq2_v2_unified_scientific_ledger import _read

VERSION = "rq2_v2_unified_one_stage_source_preflight_v0"
REQUIRED_COLUMNS = frozenset((
    "case_id", "instruction", "task_index", "cloudbed",
    "start_unix", "end_unix", "query_index",
))
FORBIDDEN_COLUMNS = frozenset((
    "reason", "scoring_points", "ground_truth", "fault_type",
    "fault_label", "reference_fault_types",
))


class UnifiedStagePreviewBlocked(RuntimeError):
    """Uno stage non e' pronto o la sua provenienza non e' dimostrabile."""


def _source_instruction(*, data_dir: Path, case_id: str) -> str:
    """Solo CSV manifest GT-free. Non apre Market.zip, GT o scorers."""
    path = data_dir / "data/processed/benchmark_inputs_market.csv"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 10_000_000:
        raise UnifiedStagePreviewBlocked("GT-free manifest absent/unsafe")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            columns = reader.fieldnames
            if (
                columns is None
                or not REQUIRED_COLUMNS.issubset(columns)
                or FORBIDDEN_COLUMNS & {c.lower() for c in columns}
            ):
                raise UnifiedStagePreviewBlocked("Manifest schema not GT-free")
            selected = [row for row in reader if row.get("case_id") == case_id]
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        raise UnifiedStagePreviewBlocked("Unreadable GT-free manifest") from exc
    if len(selected) != 1:
        raise UnifiedStagePreviewBlocked("Case missing/duplicated in manifest")
    row = selected[0]
    instruction = row.get("instruction")
    if (
        type(instruction) is not str or not instruction.strip()
        or len(instruction) > 6000
        or type(row.get("task_index")) is not str
        or not row["task_index"].strip()
        or row.get("cloudbed") not in ("cloudbed-1", "cloudbed-2")
    ):
        raise UnifiedStagePreviewBlocked("Invalid case/task instruction")
    try:
        start, end = int(row["start_unix"]), int(row["end_unix"])
    except (ValueError, KeyError) as exc:
        raise UnifiedStagePreviewBlocked("Invalid manifest time window") from exc
    if start >= end:
        raise UnifiedStagePreviewBlocked("Non-positive window")
    return instruction


def preview_one_unified_stage(
    *, data_dir: Path, repo_dir: Path,
    stage_id: str, expected_commit: str,
    approved_release_sha256: str,
) -> dict:
    """Verifica la preparabilita' di uno stage; output sempre NO_API."""
    # Init ledger ripete source-bound GT-free, commit clean e release SHA.
    scientific = UnifiedScientificLedger(
        data_dir=data_dir, repo_dir=repo_dir,
        expected_commit=expected_commit,
        approved_release_sha256=approved_release_sha256,
    )
    row = scientific.rows.get(stage_id) if type(stage_id) is str else None
    if row is None:
        raise UnifiedStagePreviewBlocked("OOD/unknown stage forbidden")
    if scientific.load_claim(stage_id=stage_id) is not None or (
        scientific.load_record(stage_id=stage_id) is not None
    ):
        raise UnifiedStagePreviewBlocked("Stage already claimed or recorded")
    audit = scientific.audit_restart()
    if audit["orphan_claims"]:
        raise UnifiedStagePreviewBlocked("Orphan claim blocks further work")

    # Il ledger ha gia' controllato i due hash del CSV contro il freeze.
    instruction = _source_instruction(
        data_dir=scientific.data, case_id=row["case_id"],
    )
    released = _read(scientific.data / RELEASE_FILE)
    if released is None:
        raise UnifiedStagePreviewBlocked("Missing pinned release")

    config = ExperimentConfig(
        variant=row["harness"], case_id=row["case_id"],
        model_name=row["model_id"],
        model_provider=row["model_provider"],
        repo_dir=scientific.repo,
        data_dir=scientific.data,
        max_tool_rounds=MAX_TOOL_ROUNDS,
        max_verification_checks=MAX_VERIFICATION_CHECKS,
        recursion_limit=RECURSION_LIMIT,
        output_contract_mode="v2_enforce",
        variant_scheme="current",
    )
    if (
        config.canonical_variant != row["harness"]
        or released["source_plan_sha256"] != scientific.plan["preview_sha256"]
    ):
        raise UnifiedStagePreviewBlocked("RQ1 D config or source plan drift")

    parents = {}
    for parent_id in row["depends_on"]:
        parent = scientific.load_record(stage_id=parent_id)
        if parent is None or parent["status"] != "RECORDED_COMPLETE":
            raise UnifiedStagePreviewBlocked("Required parent stage incomplete")
        parents[parent_id] = parent["record_sha256"]

    package_sha = None
    system_sha = None
    if row["stage"] in ("C", "K"):
        stem = stage_id.rsplit(":", 1)[0]
        d = scientific.load_record(stage_id=stem + ":D")
        if d is None or d["status"] != "RECORDED_COMPLETE":
            raise UnifiedStagePreviewBlocked("Valid immutable D required")
        drun = d["artifact"]["diagnostic_run"]
        if row["stage"] == "C":
            package = prepare_cause_probe(
                original_instruction=instruction,
                diagnostic_run=drun,
                allowed_tool_names=ALLOWED_TOOLS,
            )
            target_system = CAUSE_SYSTEM
        else:
            c = scientific.load_record(stage_id=stem + ":C")
            if c is None or c["status"] != "RECORDED_COMPLETE":
                raise UnifiedStagePreviewBlocked("Valid immutable C required")
            package = prepare_candidate_rule(
                original_instruction=instruction,
                diagnostic_run=drun,
                cause_raw_json=c["artifact"]["raw_response"],
                phase="discovery",
                allowed_tool_names=ALLOWED_TOOLS,
            )
            target_system = RULE_SYSTEM
        package_sha = package["package_sha256"]
        system_sha = hashlib.sha256(target_system.encode("utf-8")).hexdigest()
        expected_system = released[
            "C_system_prompt_sha256" if row["stage"] == "C"
            else "K_system_prompt_sha256"
        ]
        if package["system_prompt_sha256"] != expected_system or (
            system_sha != expected_system
        ):
            raise UnifiedStagePreviewBlocked("Frozen C/K prompt SHA drift")
    return {
        "version": VERSION,
        "status": "STAGE_SOURCE_PREVIEW_READY_BUT_NO_API",
        "stage_id": stage_id,
        "case_id": row["case_id"],
        "stage": row["stage"],
        "harness": row["harness"],
        "logical_model": row["logical_model"],
        "model_id": row["model_id"],
        "model_provider": row["model_provider"],
        "release_sha256": approved_release_sha256,
        "source_commit": expected_commit,
        "parent_record_sha256": parents,
        "source_instruction_read_from_gt_free_manifest": True,
        "instruction": instruction,
        "d_config": {
            "variant": config.canonical_variant,
            "model_name": config.model_name,
            "model_provider": config.model_provider,
            "max_tool_rounds": config.max_tool_rounds,
            "max_verification_checks": config.max_verification_checks,
            "recursion_limit": config.recursion_limit,
            "output_contract_mode": config.output_contract_mode,
            "variant_scheme": config.variant_scheme,
        },
        "prepared_package_sha256": package_sha,
        "C_K_system_prompt_sha256": system_sha,
        "can_create_scientific_claim": False,
        "can_construct_provider_client": False,
        "can_execute_api": False,
        "can_run_ood_test": False,
        "model_requests_sent": 0,
        "files_written": False,
    }
