"""Inventario OOD preliminare, GT-free, in sola lettura.

Legge SOLO split_market_v1.csv e benchmark_inputs_market.csv congelati.
Non accede a record.csv, query.csv, Market.zip, scorer, output di agenti.
Non sceglie casi discovery/test; NON identifica le 4 classi senza GT.
Non effettua chiamate ai modelli e non scrive alcun file.

PYTHONPATH=src python -m evaluation.ood_holdout_preflight \
    --data-dir /content/drive/MyDrive/Tesi_OpenRCA
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from evaluation.v2_case_window_audit import (
    MANIFEST_COLUMNS, MANIFEST_SHA256, SPLIT_COLUMNS, SPLIT_SHA256,
    _overlap, _read_csv, _sha, _window,
)

EXPECTED_COUNTS = {
    "development": 92,
    "evaluation": 23,
    "mixed_quarantine": 18,
    "ood_holdout": 15,
}


def inventory_ood(data_dir: Path, *, verify_original_hashes: bool = True) -> dict:
    """Audita metadati, finestre e collisioni senza leggere etichette."""
    root = Path(data_dir)
    split_file = root / "data/processed/split_market_v1.csv"
    manifest_file = root / "data/processed/benchmark_inputs_market.csv"
    split_sha = _sha(split_file)
    manifest_sha = _sha(manifest_file)

    if verify_original_hashes and (
        split_sha != SPLIT_SHA256 or manifest_sha != MANIFEST_SHA256
    ):
        raise ValueError("Split o manifest diversi dalle sorgenti GT-free congelate")

    split = _read_csv(split_file, SPLIT_COLUMNS)
    manifest = _read_csv(manifest_file, MANIFEST_COLUMNS)
    if set(split) != set(manifest):
        raise ValueError("Split/manifest: case_id differenti")

    counts = dict(Counter(row["split"] for row in split.values()))
    if set(counts) - set(EXPECTED_COUNTS):
        raise ValueError("Nome di split sconosciuto")
    if verify_original_hashes and counts != EXPECTED_COUNTS:
        raise ValueError("Conteggi degli split originali inattesi")

    for case_id, row in split.items():
        other = manifest[case_id]
        if (
            row["case_id"] != case_id
            or row["cloudbed"] not in ("cloudbed-1", "cloudbed-2")
            or not case_id.startswith(row["cloudbed"] + "_q")
            or any(row[k] != other[k] for k in (
                "cloudbed", "start_unix", "end_unix"
            ))
        ):
            raise ValueError("Incoerenza di ID, cloudbed o finestra: " + case_id)
        _window(row)

    ood = sorted(
        (row for row in split.values() if row["split"] == "ood_holdout"),
        key=lambda row: row["case_id"],
    )
    other = [row for row in split.values() if row["split"] != "ood_holdout"]
    n = len(ood)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        a, b = find(i), find(j)
        if a != b:
            parent[b] = a

    pairs = []
    for i, a in enumerate(ood):
        for j in range(i + 1, n):
            b = ood[j]
            if _overlap(a, b):
                union(i, j)
                pairs.append([a["case_id"], b["case_id"]])

    groups = {}
    for i, row in enumerate(ood):
        groups.setdefault(find(i), []).append(row["case_id"])
    groups_list = sorted(
        (sorted(ids) for ids in groups.values()),
        key=lambda ids: ids[0],
    )
    cross_split_overlaps = sorted(
        (
            {
                "ood_case_id": a["case_id"],
                "other_case_id": b["case_id"],
                "other_split": b["split"],
            }
            for a in ood for b in other if _overlap(a, b)
        ),
        key=lambda x: (x["ood_case_id"], x["other_case_id"]),
    )

    return {
        "audit": "ood_holdout_gtfree_preflight_v1",
        "source_verified": verify_original_hashes,
        "split_sha256": split_sha,
        "manifest_sha256": manifest_sha,
        "split_counts": dict(sorted(counts.items())),
        "ood_query_count": n,
        "ood_by_cloudbed": dict(sorted(Counter(
            row["cloudbed"] for row in ood
        ).items())),
        "ood_by_task": dict(sorted(Counter(
            manifest[row["case_id"]]["task_index"] for row in ood
        ).items())),
        "ood_window_durations_seconds": sorted({
            _window(row)[1] - _window(row)[0] for row in ood
        }),
        "ood_overlap_pairs": pairs,
        "ood_window_groups_count": len(groups_list),
        "ood_window_groups": groups_list,
        "ood_cross_split_overlaps": cross_split_overlaps,
        "ood_cases_metadata_only": [
            {
                "case_id": row["case_id"],
                "cloudbed": row["cloudbed"],
                "task_index": manifest[row["case_id"]]["task_index"],
                "start_unix": int(row["start_unix"]),
                "end_unix": int(row["end_unix"]),
            }
            for row in ood
        ],
        "read_ground_truth": False,
        "read_record_csv": False,
        "read_query_csv": False,
        "read_telemetry": False,
        "read_predictions": False,
        "model_api_calls": 0,
        "files_written": False,
        "limitations": [
            "Non identifica le 4 classi né conta guasti fisici indipendenti.",
            "Gruppi senza overlap non garantiscono indipendenza causale.",
            "Overlap fra split è un segnale di rischio da verificare, non leakage automaticamente accertato.",
            "Nessun caso discovery o test è stato selezionato o sbloccato.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inventory_ood(args.data_dir), indent=2,
                     ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
