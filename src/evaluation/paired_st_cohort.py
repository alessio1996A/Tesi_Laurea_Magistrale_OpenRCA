"""Pre-registra casi development nuovi per A1_VERIFY vs A1_VERIFY_ST.

Usa solo split/manifest GT-free, non legge telemetria, risultati o etichette.
Esclude tutti i dodici casi gia' esaminati nei batch precedenti.
La selezione SHA-256 e' indipendente dai punteggi. Nessuna chiamata LLM.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

PROTOCOL = "a1_verify_st_paired_development_v1"
SEED = "a1-verify-st-2026-11-02-v1"
PREVIOUS = frozenset({
    "cloudbed-1_q052", "cloudbed-1_q040",
    "cloudbed-2_q006", "cloudbed-2_q012",
    "cloudbed-1_q063", "cloudbed-2_q007",
    "cloudbed-2_q046", "cloudbed-1_q035",
    "cloudbed-1_q002", "cloudbed-2_q033",
    "cloudbed-1_q038", "cloudbed-2_q067",
})
COUNTS = {
    "development": 92, "evaluation": 23,
    "mixed_quarantine": 18, "ood_holdout": 15,
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path, expected):
    with Path(path).open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fields = reader.fieldnames or []
        if set(fields) != expected or len(set(fields)) != len(fields):
            raise ValueError(f"Colonne non ammesse in {path}: {fields}")
        return list(reader)


def costruisci_piano(split_path: Path, manifest_path: Path, per_cloudbed: int = 4):
    """Crea un piano di 8 incidenti (4 per cloudbed) non ancora analizzati."""
    if type(per_cloudbed) is not int or per_cloudbed < 1:
        raise ValueError("per_cloudbed non valido")
    # Il file split originale contiene informazioni GT-free aggiuntive note.
    split_rows = load(split_path, {"case_id", "cloudbed", "start_unix", "end_unix", "split"})
    manifest_rows = load(manifest_path, {
        "case_id", "cloudbed", "query_index", "task_index",
        "instruction", "start_unix", "end_unix",
    })
    ids = [row["case_id"] for row in split_rows]
    if len(ids) != len(set(ids)):
        raise ValueError("ID duplicati nello split")
    all_manifest = {row["case_id"]: row for row in manifest_rows}
    if len(all_manifest) != len(manifest_rows) or not set(ids).issubset(all_manifest):
        raise ValueError("Manifest incoerente con split")
    counts = Counter(row["split"] for row in split_rows)
    if dict(counts) != COUNTS:
        raise ValueError(f"Split modificato: {dict(counts)}")
    for row in split_rows:
        if row["cloudbed"] not in ("cloudbed-1", "cloudbed-2"):
            raise ValueError("Cloudbed non valido")
        if not row["case_id"].startswith(row["cloudbed"] + "_q"):
            raise ValueError("ID e cloudbed non coincidono")
        original = all_manifest[row["case_id"]]
        if any(original[key] != row[key] for key in ("cloudbed", "start_unix", "end_unix")):
            raise ValueError("Finestra GT-free non coerente")

    def rank(case_id):
        return hashlib.sha256(f"{SEED}|{case_id}".encode()).hexdigest()

    # Gli ID del benchmark non sono necessariamente incidenti indipendenti:
    # due task possono riferirsi alla stessa finestra di telemetria.
    # Escludiamo anche le finestre sovrapposte ai 12 task gia' ispezionati.
    by_id = {row["case_id"]: row for row in split_rows}
    if not PREVIOUS.issubset(by_id):
        raise ValueError("Alcuni casi storici sono assenti dallo split")

    def window(row):
        start, end = int(row["start_unix"]), int(row["end_unix"])
        if start >= end:
            raise ValueError("Finestra temporale GT-free non valida")
        return start, end

    def overlaps(a, b):
        if a["cloudbed"] != b["cloudbed"]:
            return False
        sa, ea = window(a)
        sb, eb = window(b)
        return sa < eb and sb < ea

    previous_rows = [by_id[case_id] for case_id in sorted(PREVIOUS)]
    eligible = [
        row for row in split_rows
        if row["split"] == "development"
        and row["case_id"] not in PREVIOUS
        and not any(overlaps(row, old) for old in previous_rows)
    ]
    selected_rows = []
    for cloudbed in ("cloudbed-1", "cloudbed-2"):
        items = sorted(
            (row for row in eligible if row["cloudbed"] == cloudbed),
            key=lambda row: (rank(row["case_id"]), row["case_id"]),
        )
        winners = []
        for row in items:
            # Una sola richiesta per intervallo di telemetria, anche fra
            # nuovi task diversi: evita dipendenza fra gli 8 casi del batch.
            if any(overlaps(row, chosen) for chosen in winners):
                continue
            winners.append(row)
            if len(winners) == per_cloudbed:
                break
        if len(winners) != per_cloudbed:
            raise ValueError("Finestra indipendenti development insufficienti")
        selected_rows.extend(winners)
    selected = sorted(
        (row["case_id"] for row in selected_rows), key=lambda case_id: (rank(case_id), case_id)
    )
    pairs = []
    for case_id in selected:
        reversed_order = int(rank(case_id)[-2:], 16) % 2 == 1
        variants = (["A1_VERIFY_ST", "A1_VERIFY"] if reversed_order
                    else ["A1_VERIFY", "A1_VERIFY_ST"])
        pairs.append({
            "case_id": case_id, "cloudbed": case_id.split("_")[0],
            "ordered_variants": variants,
            "run_ids": [f"{PROTOCOL}__{case_id}__{v.lower()}__r01" for v in variants],
            "max_tool_rounds": 6,
            "max_verification_checks": 2,
            "exploration_round_limit": 4,
            "output_contract_mode": "legacy",
        })
    return {
        "protocol": PROTOCOL, "selection_seed": SEED,
        "split_file_sha256": sha(split_path),
        "input_manifest_sha256": sha(manifest_path),
        "split_counts": COUNTS,
        "historical_exclusions": sorted(PREVIOUS),
        "selection_excludes_overlapping_historical_windows": True,
        "selection_enforces_nonoverlapping_new_windows": True,
        "per_cloudbed": per_cloudbed,
        "case_count": len(pairs), "run_count": len(pairs) * 2,
        "model_provider": "google", "model_name": "gemini-3.5-flash-lite",
        "cohort_role": "development_feasibility_not_blind_evaluation",
        "read_ground_truth": False, "llm_calls": 0,
        "scoring": "freeze_predictions_before_official_scoring",
        "pairs": pairs,
    }


def main():
    parser = argparse.ArgumentParser(description="Preregistrazione ST senza Gemini")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--per-cloudbed", type=int, default=4)
    parser.add_argument("--freeze", action="store_true",
                        help="Salva esclusivamente un piano nuovo, senza sovrascrivere")
    args = parser.parse_args()
    root = args.data_dir
    plan = costruisci_piano(
        root / "data/processed/split_market_v1.csv",
        root / "data/processed/benchmark_inputs_market.csv",
        per_cloudbed=args.per_cloudbed,
    )
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    if args.freeze:
        out = root / "data/protocols" / (PROTOCOL + "_cohort_v1.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("x", encoding="utf-8") as stream:
            json.dump(plan, stream, indent=2, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
        print("Piano congelato:", out)


if __name__ == "__main__":
    main()
