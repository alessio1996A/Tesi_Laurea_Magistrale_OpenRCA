"""Pre-register an A1 vs A1_VERIFY development cohort without accessing GT.

Only reads the already frozen GT-free split and the GT-free input manifest.
It does NOT inspect telemetry, predictions, scorer files or API keys.
Deterministic SHA-256 ordering, balanced by cloudbed, excluding explored
pilot cases. No file writes except explicit save_plan_exclusive().
"""
from __future__ import annotations

import csv
from hashlib import sha256
import json
from pathlib import Path
import re

HISTORICAL_CASE_IDS = frozenset({
    "cloudbed-1_q052",
    "cloudbed-1_q040",
    "cloudbed-2_q006",
    "cloudbed-2_q012",
})
ALLOWED_SPLITS = frozenset({
    "development", "evaluation", "mixed_quarantine", "ood_holdout",
})
PROTOCOL = "a1_verify_paired_development_v1"
SEED = "a1verify-2026-11-01-v1"
_CLOUD = re.compile(r"^cloudbed-([12])_q[0-9]+$")


def _csv_rows(path: Path, required: set[str]) -> list[dict[str, str]]:
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            raise ValueError("Intestazioni CSV duplicate")
        if not required.issubset(headers):
            raise ValueError(
                f"{path.name}: colonne mancanti {sorted(required-set(headers))}; "
                f"presenti {headers}"
            )
        # Reject label-bearing inputs BEFORE reading any row values.
        dangerous = {
            "reason", "scoring_points", "root_cause_reason",
            "root cause reason", "root_cause_component",
            "ground_truth", "label", "labels", "answer",
            "fault_type", "fault_category", "failure_type",
        }
        found = {h.strip().casefold() for h in headers} & dangerous
        if found:
            raise ValueError(f"{path.name}: colonne GT non consentite: {sorted(found)}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path.name}: CSV vuoto")
    return rows


def _cloud(case_id: str) -> str:
    match = _CLOUD.fullmatch(case_id)
    if match is None:
        raise ValueError(f"Case ID non valido: {case_id!r}")
    return f"cloudbed-{match.group(1)}"


def costruisci_piano_abbinato(
    split_path: Path,
    manifest_path: Path,
    *,
    per_cloudbed: int = 4,
) -> dict:
    """Freeze eight GT-free dev cases by default; no labels or real LLM calls.

    The protocol is a *feasibility pilot*, not an independent accuracy
    estimate or proof of improvement. One paired run per incident.
    """
    if type(per_cloudbed) is not int or per_cloudbed < 1:
        raise ValueError("per_cloudbed deve essere intero positivo")

    split_path = Path(split_path)
    manifest_path = Path(manifest_path)
    split_rows = _csv_rows(split_path, {"case_id", "split"})
    manifest_rows = _csv_rows(manifest_path, {"case_id"})

    all_ids = set()
    grouped = {"cloudbed-1": [], "cloudbed-2": []}
    split_counts = {name: 0 for name in sorted(ALLOWED_SPLITS)}
    for row in split_rows:
        case_id = row["case_id"].strip()
        partition = row["split"].strip().lower()
        cloudbed = _cloud(case_id)
        if case_id in all_ids:
            raise ValueError(f"Case ID duplicato nello split: {case_id}")
        all_ids.add(case_id)
        if partition not in ALLOWED_SPLITS:
            raise ValueError(f"Partizione non riconosciuta: {partition!r}")
        split_counts[partition] += 1
        if partition == "development" and case_id not in HISTORICAL_CASE_IDS:
            grouped[cloudbed].append(case_id)

    available = {row["case_id"].strip() for row in manifest_rows}
    if len(available) != len(manifest_rows):
        raise ValueError("Case ID duplicati nel manifest")
    if not all_ids.issubset(available):
        missing = sorted(all_ids - available)
        raise ValueError(f"Case ID dello split assenti dal manifest: {missing[:5]}")

    if any(len(items) < per_cloudbed for items in grouped.values()):
        raise ValueError(
            f"Non abbastanza development nuovi per cloudbed: "
            f"{ {k: len(v) for k, v in grouped.items()} }"
        )

    def rank(case_id: str) -> str:
        return sha256(f"{SEED}|{case_id}".encode("utf-8")).hexdigest()

    selected = []
    for cloudbed in sorted(grouped):
        selected.extend(
            sorted(grouped[cloudbed], key=lambda case_id: (rank(case_id), case_id))[
                :per_cloudbed
            ]
        )
    selected = sorted(selected, key=lambda case_id: (rank(case_id), case_id))

    # Randomized but reproducible variant execution order within each pair.
    # Order selection does not inspect incident features or performance.
    pairs = []
    for case_id in selected:
        reverse = int(rank(case_id)[-2:], 16) % 2 == 1
        order = (["A1_VERIFY", "A1"] if reverse else ["A1", "A1_VERIFY"])
        pairs.append({
            "case_id": case_id,
            "cloudbed": _cloud(case_id),
            "trial": 1,
            "ordered_variants": order,
            "max_tool_rounds": 6,
            "max_verification_checks": 2,
            "output_contract_mode": "legacy",
            "run_ids": [
                f"{PROTOCOL}__{case_id}__{variant.lower()}__r01"
                for variant in order
            ],
        })

    return {
        "protocol": PROTOCOL,
        "selection_seed": SEED,
        "split_file_sha256": sha256(split_path.read_bytes()).hexdigest(),
        "input_manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
        "split_counts": split_counts,
        "historical_exclusions": sorted(HISTORICAL_CASE_IDS),
        "per_cloudbed": per_cloudbed,
        "case_count": len(pairs),
        "run_count": 2 * len(pairs),
        "model_provider": "google",
        "model_name": "gemini-3.5-flash-lite",
        "replicates_per_arm": 1,
        "cohort_role": "development_feasibility_not_blind_evaluation",
        "scoring": "only_after_both_variants_predicted_and_frozen",
        "read_ground_truth": False,
        "read_telemetry": False,
        "llm_calls": 0,
        "pairs": pairs,
    }


def save_plan_exclusive(plan: dict, destination: Path) -> Path:
    """Explicit write only; no overwrite, including existing pilot plans."""
    if not isinstance(plan, dict) or plan.get("protocol") != PROTOCOL:
        raise ValueError("Piano non valido")
    destination = Path(destination)
    # Avoid writing to results history or a caller-provided directory alone.
    if destination.suffix != ".json":
        raise ValueError("Destinazione deve essere un file .json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as target:
        json.dump(plan, target, indent=2, ensure_ascii=False, sort_keys=True)
        target.write("\n")
    return destination
