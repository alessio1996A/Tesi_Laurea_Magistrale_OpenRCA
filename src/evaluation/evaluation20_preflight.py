"""OpenRCA Market: audit GT-free per 20 nuovi incidenti EVALUATION.

Solo lettura di split_market_v1.csv, benchmark_inputs_market.csv e
piano Gemini V3 (solo metadati della coorte). NON legge Market.zip,
query.csv, record.csv, predizioni, score o telemetria. NON chiama API.
NON crea o modifica file. Se 20 casi non sono eleggibili, non inventa
un'alternativa e non modifica i criteri.

Esempio Colab (repository alla branch che contiene questo file):
 PYTHONPATH=src python -m evaluation.evaluation20_preflight \
    --data-dir /content/drive/MyDrive/Tesi_OpenRCA
"""
from __future__ import annotations

import argparse
from collections import Counter
from itertools import combinations
import hashlib
import json
from pathlib import Path

from evaluation.v2_case_window_audit import (
    MANIFEST_COLUMNS, MANIFEST_SHA256, SPLIT_COLUMNS, SPLIT_SHA256,
    _overlap, _read_csv, _sha, _window,
)
from evaluation.v2_preregister import EXPECTED_CASES
from output.v2_contract import infer_requested_faults

SPLIT_COUNTS = {
    "development": 92,
    "evaluation": 23,
    "mixed_quarantine": 18,
    "ood_holdout": 15,
}
V3_PROTOCOL = "openrca_harness_v2_five_agents_development_v3"
V3_PLAN_SHA = "002aadbee9cf5339ffb2ed36d90eaa492ca3c0900cbf32b3682629beb5610d68"
SEED = "openrca-market-evaluation20-blind-selection-2026-11-06-v1"
VARIANTS = ("A0", "A1", "A1_8R", "A1_8R_Planning", "A1_PAVE")
MODELS = ("gemini", "sonnet", "haiku")
TASKS = frozenset(f"task_{i}" for i in range(1, 8))


def _ordered(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (
        hashlib.sha256((SEED + "|" + r["case_id"]).encode()).hexdigest(),
        r["case_id"],
    ))


def choose_balanced(rows: list[dict], target: int = 20) -> list[dict] | None:
    """Selezione deterministica GT-free: 50/50 cloudbed, sette task,
    almeno un multi-guasto per cloudbed e nessun overlap interno.
    Nessuna selezione da output/score. Se impossibile, restituisce None.
    """
    if type(target) is not int or not 8 <= target <= 23 or target % 2:
        raise ValueError("Target richiesto: numero pari fra 8 e 23")
    if len({r["case_id"] for r in rows}) != len(rows):
        raise ValueError("Case ID duplicati")
    if len(rows) < target:
        return None
    ranked = _ordered(rows)
    for option in combinations(ranked, target):
        counts = Counter(r["cloudbed"] for r in option)
        if counts != {"cloudbed-1": target // 2, "cloudbed-2": target // 2}:
            continue
        if {r["task_index"] for r in option} != TASKS:
            continue
        if any(
            not any(r["cloudbed"] == cb and r["requested_fault_count"] >= 2
                    for r in option)
            for cb in ("cloudbed-1", "cloudbed-2")
        ):
            continue
        if any(
            _overlap(a, b)
            for i, a in enumerate(option) for b in option[i + 1:]
        ):
            continue
        return sorted(option, key=lambda r: (r["cloudbed"], r["case_id"]))
    return None


def evaluation20_preflight(data_dir: Path, target: int = 20) -> dict:
    """Controlla l'eleggibilita' senza consultare etichette o scoring."""
    root = Path(data_dir)
    split_path = root / "data/processed/split_market_v1.csv"
    manifest_path = root / "data/processed/benchmark_inputs_market.csv"
    plan_path = root / "data/protocols/v2" / f"{V3_PROTOCOL}_plan_v1.json"
    split_sha, manifest_sha = _sha(split_path), _sha(manifest_path)
    if (split_sha, manifest_sha) != (SPLIT_SHA256, MANIFEST_SHA256):
        raise ValueError("STOP: fingerprint originali split/manifest non validi")
    if _sha(plan_path) != V3_PLAN_SHA:
        raise ValueError("STOP: piano V3 congelato non coincide")
    split = _read_csv(split_path, SPLIT_COLUMNS)
    manifest = _read_csv(manifest_path, MANIFEST_COLUMNS)
    if set(split) != set(manifest):
        raise ValueError("STOP: manifest/split hanno ID differenti")
    counts = dict(Counter(row["split"] for row in split.values()))
    if counts != SPLIT_COUNTS:
        raise ValueError(f"STOP: split alterato {counts}")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    dev8 = plan.get("cases")
    if (plan.get("protocol") != V3_PROTOCOL
            or plan.get("case_count") != 8
            or plan.get("run_count") != 40
            or plan.get("ground_truth_accessed") is not False
            or not isinstance(dev8, list)
            or {r.get("case_id") for r in dev8} != EXPECTED_CASES):
        raise ValueError("STOP: la coorte V3 non e' verificabile")

    for case_id, row in split.items():
        m = manifest[case_id]
        if any(row[k] != m[k] for k in (
            "cloudbed", "start_unix", "end_unix"
        )):
            raise ValueError(f"STOP: mismatch split/manifest {case_id}")
        if row["cloudbed"] not in ("cloudbed-1", "cloudbed-2"):
            raise ValueError(f"STOP: cloudbed {case_id}")
        if not case_id.startswith(row["cloudbed"] + "_q"):
            raise ValueError(f"STOP: ID del caso {case_id}")
        _window(row)

    development = [r for r in split.values()
                   if r["split"] == "development"]
    protected = [r for r in split.values()
                 if r["split"] in ("mixed_quarantine", "ood_holdout")]
    seen = [split[c] for c in sorted(EXPECTED_CASES)]
    evaluations = [r for r in split.values()
                   if r["split"] == "evaluation"]
    evaluations.sort(key=lambda r: r["case_id"])

    entries = []
    for row in evaluations:
        case_id = row["case_id"]
        m = manifest[case_id]
        task = m["task_index"]
        faults = infer_requested_faults(m["instruction"])
        overlap_dev8 = sorted(x["case_id"] for x in seen
                              if _overlap(row, x))
        overlap_dev = sorted(x["case_id"] for x in development
                             if _overlap(row, x))
        overlap_hold = sorted(x["case_id"] for x in protected
                              if _overlap(row, x))
        overlap_eval = sorted(x["case_id"] for x in evaluations
                              if x["case_id"] != case_id
                              and _overlap(row, x))
        reasons = []
        if overlap_dev:
            reasons.append("overlap_with_development")
        if overlap_hold:
            reasons.append("overlap_with_quarantine_or_ood")
        if task not in TASKS or faults is None:
            reasons.append("unknown_task_or_cardinality")
        entry = {
            "case_id": case_id,
            "cloudbed": row["cloudbed"],
            "start_unix": int(row["start_unix"]),
            "end_unix": int(row["end_unix"]),
            "task_index": task,
            "requested_fault_count": faults,
            "overlaps_with_8_development": overlap_dev8,
            "overlaps_with_any_development": overlap_dev,
            "overlaps_with_quarantine_or_ood": overlap_hold,
            "overlaps_with_other_evaluation": overlap_eval,
            "strict_eligible": not reasons,
            "exclusion_reasons": reasons,
        }
        entries.append(entry)

    strict = [
        {k: e[k] for k in (
            "case_id", "cloudbed", "start_unix", "end_unix",
            "task_index", "requested_fault_count"
        )}
        for e in entries if e["strict_eligible"]
    ]
    # _overlap/_window lavorano con rappresentazione canonica Unix.
    # I dati da scegliere sono riportati come stringhe nell'algoritmo.
    for row in strict:
        row["start_unix"] = str(row["start_unix"])
        row["end_unix"] = str(row["end_unix"])

    proposed = choose_balanced(strict, target=target)
    if proposed is not None:
        for row in proposed:
            row["start_unix"] = int(row["start_unix"])
            row["end_unix"] = int(row["end_unix"])
    return {
        "audit": "openrca_evaluation20_preflight_v1",
        "status": ("PROPOSED_GT_FREE_NOT_FROZEN_NOT_EXECUTED"
                   if proposed is not None else
                   "BLOCKED_NO_STRICT_BALANCED_SELECTION"),
        "target_new_cases": target,
        "models": list(MODELS),
        "variants": list(VARIANTS),
        "planned_new_runs_if_feasible": target * len(MODELS) * len(VARIANTS),
        "development_cases_retained_for_exploratory_analysis": sorted(EXPECTED_CASES),
        "split_counts": counts,
        "split_sha256": split_sha,
        "manifest_sha256": manifest_sha,
        "development_v3_plan_sha256": V3_PLAN_SHA,
        "selection_seed": SEED,
        "strict_policy": (
            "Evaluation split, no temporal overlap with ANY development "
            "or quarantine/OOD case, no overlap within new cohort, "
            "10+10 cloudbed for 20, all 7 tasks, >=1 multifault per cloudbed"
        ),
        "evaluation_rows_checked": len(entries),
        "strict_candidate_count": len(strict),
        "strict_candidates_by_cloudbed": dict(
            sorted(Counter(x["cloudbed"] for x in strict).items())
        ),
        "strict_candidates_by_task": dict(
            sorted(Counter(x["task_index"] for x in strict).items())
        ),
        "candidate_audit": entries,
        "proposed_cases": proposed,
        "selected_case_count": len(proposed) if proposed else 0,
        "read_ground_truth": False,
        "read_query_csv": False,
        "read_record_csv": False,
        "read_telemetry": False,
        "read_predictions": False,
        "scoring_performed": False,
        "model_api_calls": 0,
        "files_written": False,
        "limitations": [
            "Una disgiunzione temporale non garantisce indipendenza statistica.",
            "Cohort selection e' una PROPOSTA GT-free, non un protocollo firmato.",
            "Nessuna run parte senza test, budget approvato e nuovo runner.",
            "Se non sono eleggibili 20, non rilassare automaticamente i criteri.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--target", type=int, default=20)
    args = parser.parse_args()
    result = evaluation20_preflight(args.data_dir, args.target)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
