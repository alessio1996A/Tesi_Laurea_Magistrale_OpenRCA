"""Inventario sorgenti RQ2-V4 GT-free e immutabile, solo read-only.

Non legge release, claim o record V3; riutilizza soltanto il controllo
dei file sorgente e del manifest GT-free V2/V3 già verificato. Tutte
le nuove sorgenti V4 sono sottoposte a SHA256 dei byte reali. Nessuna API.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from evaluation.rq2_v2_unified_scientific_ledger import _sha
from evaluation.rq2_v3_scientific_source_inventory import (
    V3SourceInventoryBlocked, _root, _source_bytes,
    preview_v3_scientific_source_inventory,
)
from evaluation.rq2_v3_unified_gtfree_discovery_plan import (
    VERSION as V3_PROTOCOL, build_offline_v3_discovery_plan,
)
from evaluation.rq2_v4_d_task_aware_contract import VERSION as CONTRACT
from evaluation.rq2_v4_unified_gtfree_discovery_plan import (
    VERSION as PROTOCOL, NAMESPACE, RELEASE_FILE,
    build_offline_v4_discovery_plan,
)

VERSION = "rq2_v4_scientific_source_inventory_preview_v0"
STATUS = "V4_GT_FREE_SOURCE_INVENTORY_READONLY_NO_RELEASE"
V4_SOURCE_PATHS = (
    "evaluation/rq2_v4_d_task_aware_contract.py",
    "evaluation/rq2_v4_unified_gtfree_discovery_plan.py",
    "evaluation/rq2_v4_scientific_receipt_adapter_candidate.py",
    "evaluation/rq2_v4_scientific_ledger.py",
    "evaluation/rq2_v4_scientific_source_inventory.py",
    "evaluation/rq2_v4_scientific_source_release_gate.py",
)
# L'assenza del dispatcher V4 blocca il futuro freeze; non la si nasconde.
FUTURE_REQUIRED_PATHS = (
    "evaluation/rq2_v4_scientific_single_stage_dispatcher.py",
)


class V4SourceInventoryBlocked(ValueError):
    """Sorgenti GT-free o V4 non dimostrabili: nessuna release."""


def preview_v4_scientific_source_inventory(*, data_dir: Path,
                                           src_root: Path) -> dict:
    """Verifica digest reali di V2/V3/V4 e identità di 180 stage V4."""
    try:
        data = _root(data_dir, "V4 data root")
        src = _root(src_root, "V4 source root")
        base = preview_v3_scientific_source_inventory(
            data_dir=data, src_root=src,
        )
        v3 = build_offline_v3_discovery_plan()
        plan = build_offline_v4_discovery_plan()
        if (
            base.get("gt_free_source_verified") is not True
            or base.get("frozen_rq1_source_identity_verified") is not True
            or base.get("protocol") != V3_PROTOCOL
            or base.get("v3_plan_sha256") != v3["preview_sha256"]
            or base.get("candidate_inventory_sha256") != _sha({
                key: val for key, val in base.items()
                if key != "candidate_inventory_sha256"
            })
            or base.get("missing_future_paths") != []
            or base.get("can_execute_api") is not False
            or base.get("can_run_ood_test") is not False
            or plan["source_plan_sha256"] != v3["preview_sha256"]
            or plan["D_validation_contract"] != CONTRACT
            or plan["logical_stages"] != 180
            or len(plan["ood_test_cases_locked"]) != 11
            or plan["reuse_v3_d_outputs"] is not False
            or plan["reuse_v3_c_or_k_outputs"] is not False
            or plan["reuse_v2_d_or_ck_outputs"] is not False
            or plan["can_execute_api"] is not False
            or plan["can_run_ood_test"] is not False
            or set(V4_SOURCE_PATHS) & set(FUTURE_REQUIRED_PATHS)
            or len(set(V4_SOURCE_PATHS)) != len(V4_SOURCE_PATHS)
        ):
            raise V4SourceInventoryBlocked("V4/V3 GT-free plan or source drift")
        hashes = {
            name: hashlib.sha256(_source_bytes(src, name)).hexdigest()
            for name in V4_SOURCE_PATHS
        }
        pending = []
        for name in FUTURE_REQUIRED_PATHS:
            path = src / name
            if path.is_symlink():
                raise V4SourceInventoryBlocked("Future dispatcher symlink")
            if not path.is_file():
                pending.append(name)
        core = {
            "version": VERSION,
            "status": STATUS,
            "protocol": PROTOCOL,
            "plan_sha256": plan["preview_sha256"],
            "entries_sha256": plan["entries_sha256"],
            "scientific_namespace": NAMESPACE.as_posix(),
            "release_relative_path": RELEASE_FILE.as_posix(),
            "v2_source_files_sha256": base["v2_source_files_sha256"],
            "v3_source_files_sha256": base["v3_source_files_sha256"],
            "v3_future_source_files_sha256": {
                name: hashlib.sha256(_source_bytes(src, name)).hexdigest()
                for name in base["future_required_paths"]
            },
            "v4_source_files_sha256": hashes,
            "C_system_prompt_sha256": base["C_system_prompt_sha256"],
            "K_system_prompt_sha256": base["K_system_prompt_sha256"],
            "text_extraction_policy": base["text_extraction_policy"],
            "split_sha256": base["split_sha256"],
            "manifest_sha256": base["manifest_sha256"],
            "model_ids": dict(plan["model_ids"]),
            "harnesses": list(plan["harnesses"]),
            "discovery_cases": list(plan["discovery_cases"]),
            "ood_test_cases_locked": list(plan["ood_test_cases_locked"]),
            "stage_counts": dict(plan["stage_counts"]),
            "logical_stages": 180,
            "v4_task_aware_contract": CONTRACT,
            "future_required_paths": list(FUTURE_REQUIRED_PATHS),
            "missing_future_paths": pending,
            "gt_free_source_verified": True,
            "frozen_rq1_source_identity_verified": True,
            "ground_truth_read": False,
            "model_requests_sent": 0,
            "can_run_ood_test": False,
            "can_create_claim": False,
            "can_execute_api": False,
            "files_written": False,
        }
        return {**core, "candidate_inventory_sha256": _sha(core)}
    except (V3SourceInventoryBlocked, KeyError, TypeError, OSError) as exc:
        raise V4SourceInventoryBlocked("Untrusted or unsafe V3/V4 GT-free sources") from exc
