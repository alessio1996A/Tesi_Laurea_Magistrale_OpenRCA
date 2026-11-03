"""Audit in sola lettura delle finestre degli esperimenti V1.

Controlla split e manifest GT-free con SHA-256, le 2 coorti congelate,
le 16 finestre development e le sovrapposizioni tra intervalli
[inizio, fine). Distingue le sovrapposizioni con piloti pregressi
senza alterare retroattivamente il protocollo storico.

NON legge Market.zip, record.csv, query.csv, predizioni o scorer.
NON chiama API e non scrive alcun file.

Colab con PYTHONPATH=src:
  python -m evaluation.v2_case_window_audit \
    --data-dir /content/drive/MyDrive/Tesi_OpenRCA
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


SPLIT_SHA256 = "c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724"
MANIFEST_SHA256 = "5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13"

PROTOCOLS = (
    "a1_verify_paired_development_v1",
    "a1_verify_st_paired_development_v1",
)
SPLIT_COLUMNS = {"case_id", "cloudbed", "start_unix", "end_unix", "split"}
MANIFEST_COLUMNS = {
    "case_id", "cloudbed", "query_index", "task_index",
    "instruction", "start_unix", "end_unix",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_csv(path: Path, fields: set[str]) -> dict[str, dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headings = reader.fieldnames or []
        # Lista CHIUSA: un manifest arricchito con GT viene rifiutato.
        if len(headings) != len(set(headings)) or set(headings) != fields:
            raise ValueError(f"Schema GT-free non conforme: {path.name}")
        index = {}
        for row in reader:
            case_id = row["case_id"]
            if case_id in index:
                raise ValueError(f"Case ID duplicato: {case_id}")
            index[case_id] = row
        if not index:
            raise ValueError(f"CSV vuoto: {path.name}")
        return index


def _window(row: dict) -> tuple[int, int]:
    try:
        start, end = int(row["start_unix"]), int(row["end_unix"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Finestra Unix non numerica") from exc
    if start >= end or str(start) != row["start_unix"] or str(end) != row["end_unix"]:
        raise ValueError("Finestra Unix mancante, non canonica o invertita")
    return start, end


def _overlap(a: dict, b: dict) -> bool:
    if a["cloudbed"] != b["cloudbed"]:
        return False
    a0, a1 = _window(a)
    b0, b1 = _window(b)
    return a0 < b1 and b0 < a1


def audit_case_windows(
    data_dir: Path, *, verify_original_hashes: bool = True,
) -> dict:
    root = Path(data_dir)
    split_path = root / "data/processed/split_market_v1.csv"
    manifest_path = root / "data/processed/benchmark_inputs_market.csv"
    split_sha, manifest_sha = _sha(split_path), _sha(manifest_path)
    if verify_original_hashes and (
        split_sha != SPLIT_SHA256 or manifest_sha != MANIFEST_SHA256
    ):
        raise ValueError("SHA-256 split o manifest GT-free diverso dal freeze")
    split = _read_csv(split_path, SPLIT_COLUMNS)
    manifest = _read_csv(manifest_path, MANIFEST_COLUMNS)
    if set(split) != set(manifest):
        raise ValueError("Insieme case_id diverso tra split e manifest")

    expected_counts = {
        "development": 92, "evaluation": 23,
        "mixed_quarantine": 18, "ood_holdout": 15,
    }
    counts = dict(Counter(x["split"] for x in split.values()))
    if verify_original_hashes and counts != expected_counts:
        raise ValueError("Conteggi split incoerenti")
    for id_, row in split.items():
        other = manifest[id_]
        for name in ("cloudbed", "start_unix", "end_unix"):
            if row[name] != other[name]:
                raise ValueError(f"{id_}: {name} differisce nel manifest")
        _window(row)

    selections = []
    old_overlap = []
    details = []
    for protocol in PROTOCOLS:
        plan_file = root / "data/protocols" / (protocol + "_cohort_v1.json")
        plan = json.loads(plan_file.read_text(encoding="utf-8"))
        if (
            plan.get("protocol") != protocol
            or plan.get("split_file_sha256") != split_sha
            or plan.get("input_manifest_sha256") != manifest_sha
        ):
            raise ValueError(f"Piano non coerente o modificato: {protocol}")
        pairs = plan.get("pairs")
        if not isinstance(pairs, list) or len(pairs) != 8:
            raise ValueError(f"{protocol}: attese esattamente 8 coppie")
        if plan.get("run_count") != 16 or plan.get("case_count") != 8:
            raise ValueError(f"{protocol}: numero run incoerente")

        ids = []
        historical = plan.get("historical_exclusions")
        if not isinstance(historical, list) or any(
            id_ not in split for id_ in historical
        ):
            raise ValueError(f"{protocol}: casi storici non validi")
        for pair in pairs:
            case_id = pair["case_id"]
            if case_id in ids:
                raise ValueError(f"{protocol}: caso duplicato")
            if case_id not in split:
                raise ValueError(f"{protocol}: caso assente dallo split")
            row = split[case_id]
            if row["split"] != "development":
                raise ValueError(f"{case_id}: caso non development")
            if pair["cloudbed"] != row["cloudbed"]:
                raise ValueError(f"{case_id}: cloudbed incoerente")
            if case_id in historical:
                raise ValueError(f"{case_id}: caso gia' esplicitamente escluso")
            if pair["max_tool_rounds"] != 6 or pair["max_verification_checks"] != 2:
                raise ValueError(f"{case_id}: budget storico inatteso")
            ids.append(case_id)
            selections.append({"protocol": protocol, "case_id": case_id, **row})
            for old_id in historical:
                if _overlap(row, split[old_id]):
                    old_overlap.append({
                        "protocol": protocol,
                        "case_id": case_id,
                        "historical_case_id": old_id,
                        "same_window": _window(row) == _window(split[old_id]),
                    })
        details.append({
            "protocol": protocol,
            "pairs": len(ids),
            "cloudbed_counts": dict(sorted(Counter(
                split[id_]["cloudbed"] for id_ in ids
            ).items())),
            "plan_sha256": _sha(plan_file),
        })

    overlaps_between_selected = []
    for i, first in enumerate(selections):
        for second in selections[i + 1:]:
            if _overlap(first, second):
                overlaps_between_selected.append({
                    "case_a": first["case_id"],
                    "case_b": second["case_id"],
                    "protocol_a": first["protocol"],
                    "protocol_b": second["protocol"],
                })

    if overlaps_between_selected:
        raise ValueError("Selezioni storiche sovrapposte: controllare i protocolli")

    return {
        "audit": "v2_case_window_audit_v1",
        "split_sha256": split_sha,
        "manifest_sha256": manifest_sha,
        "split_counts": counts,
        "cohorts": details,
        "checked_selected_development_cases": len(selections),
        "selected_window_durations_seconds": sorted({
            _window(s)[1] - _window(s)[0] for s in selections
        }),
        "selected_window_overlaps": overlaps_between_selected,
        "overlaps_with_historical_pilots": old_overlap,
        "read_ground_truth": False,
        "read_market_zip": False,
        "read_predictions": False,
        "scorer_called": False,
        "gemini_calls": 0,
        "files_written": False,
        "limitations": [
            "Confronto di intervalli e metadati, non validazione delle cause.",
            "Una sovrapposizione con un pilota resta segnalata, non corretta retroattivamente.",
            "Non prova la qualita' o completezza delle risposte degli agenti.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(
        audit_case_windows(args.data_dir),
        indent=2, ensure_ascii=False, allow_nan=False,
    ))


if __name__ == "__main__":
    main()
