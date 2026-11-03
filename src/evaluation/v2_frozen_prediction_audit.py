"""Audit V2 in sola lettura delle 32 risposte storiche congelate.

Richiede freeze originale, piani, split e manifest GT-free. Valida gli SHA
dei file di risultato prima di leggere raw_response. Usa SOLO l'istruzione
ufficiale (non etichette) per cardinalita', e la finestra ufficiale per
controllare il timestamp Asia/Shanghai. Non riscrive previsioni, non fa
scoring e non chiama il modello. In presenza di dati incoerenti: STOP.

Il validatore V2 e' intenzionalmente piu' severo di quello legacy; una
risposta storica valida per legacy puo' risultare non conforme V2.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from evaluation.v2_case_window_audit import (
    PROTOCOLS,
    SPLIT_SHA256, MANIFEST_SHA256, SPLIT_COLUMNS, MANIFEST_COLUMNS,
    _read_csv, _window,
)
from output.v2_contract import audit_openrca_v2


FREEZE_NAMES = (
    "a1_verify_paired_development_v1_results_freeze_v1.json",
    "a1_verify_st_paired_development_v1_predictions_frozen_v1.json",
)
FREEZE_SHAS = (
    "e8c350d3e3372d0e4afb6fd63d60f2f5632394bc7e2a4b996ca0ff864ae2ccf0",
    "43e646792685b1cde03052cadc2c8a82749d058a4e04ee0b01f607a7384fd104",
)
BASE_COMMITS = (
    "6927fcfa18fc29fce64ad65eac98231b2ba42184",
    "138fb523efec4a665a2424ab2faedb698f10562e",
)
RUN_ID = re.compile(r"^[a-z0-9_-]+$")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _file(root: Path, path: Path, expected: str) -> dict:
    """Verifica byte esatti prima di deserializzare JSON."""
    raw = path.read_bytes()
    if _sha(raw) != expected:
        raise ValueError(f"SHA-256 non corrispondente: {path.name}")
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON non e' oggetto: {path.name}")
    return obj


def audit_frozen_predictions(
    data_dir: Path, *, verify_original_hashes: bool = True,
) -> dict:
    root = Path(data_dir)
    processed = root / "data/processed"
    protocols = root / "data/protocols"
    split_path = processed / "split_market_v1.csv"
    manifest_path = processed / "benchmark_inputs_market.csv"

    split_bytes = split_path.read_bytes()
    manifest_bytes = manifest_path.read_bytes()
    split_hash, manifest_hash = _sha(split_bytes), _sha(manifest_bytes)
    if verify_original_hashes and (
        split_hash != SPLIT_SHA256 or manifest_hash != MANIFEST_SHA256
    ):
        raise ValueError("SHA-256 degli input GT-free alterato")
    split = _read_csv(split_path, SPLIT_COLUMNS)
    manifest = _read_csv(manifest_path, MANIFEST_COLUMNS)
    if set(split) != set(manifest):
        raise ValueError("split e manifest usano case_id diversi")
    for case_id, row in split.items():
        if any(
            row[x] != manifest[case_id][x]
            for x in ("cloudbed", "start_unix", "end_unix")
        ):
            raise ValueError(f"{case_id}: finestra split/manifest diversa")

    rows = []
    studies = []
    for study_index, protocol in enumerate(PROTOCOLS):
        plan_path = protocols / f"{protocol}_cohort_v1.json"
        plan_bytes = plan_path.read_bytes()
        plan = json.loads(plan_bytes.decode("utf-8"))
        plan_hash = _sha(plan_bytes)
        freeze_path = protocols / FREEZE_NAMES[study_index]
        freeze_bytes = freeze_path.read_bytes()
        if (verify_original_hashes and
                _sha(freeze_bytes) != FREEZE_SHAS[study_index]):
            raise ValueError(f"SHA-256 freeze diverso: {protocol}")
        freeze = json.loads(freeze_bytes.decode("utf-8"))
        if (
            plan.get("protocol") != protocol
            or freeze.get("protocol") != protocol
            or plan.get("split_file_sha256") != split_hash
            or plan.get("input_manifest_sha256") != manifest_hash
            or freeze.get("frozen_plan_sha256") != plan_hash
            or freeze.get("git_commit") != BASE_COMMITS[study_index]
            or plan.get("case_count") != 8 or plan.get("run_count") != 16
            or freeze.get("case_count") != 8 or freeze.get("run_count") != 16
            or freeze.get("scoring_performed") is not False
        ):
            raise ValueError(f"Manifest di freeze/piano incoerente: {protocol}")
        if study_index == 0 and freeze.get("ground_truth_accessed") is not False:
            raise ValueError("Freeze primo studio non GT-free")

        pairs = plan.get("pairs")
        if not isinstance(pairs, list) or len(pairs) != 8:
            raise ValueError(f"Coppie assenti: {protocol}")
        base = root / "data/results/paired" / protocol
        expected_paths = {}
        for pair in pairs:
            case_id = pair["case_id"]
            if (
                case_id not in split
                or split[case_id]["split"] != "development"
                or split[case_id]["cloudbed"] != pair["cloudbed"]
            ):
                raise ValueError(f"Caso non development o inconsistente: {case_id}")
            if len(pair["ordered_variants"]) != 2:
                raise ValueError("Attesi due bracci per coppia")
            for i, variant in enumerate(pair["ordered_variants"]):
                run_id = pair["run_ids"][i]
                if not RUN_ID.fullmatch(run_id) or run_id in expected_paths:
                    raise ValueError("Run ID non valido o duplicato")
                if not run_id.endswith("__" + variant.lower() + "__r01"):
                    raise ValueError("Run ID/variante incoerente")
                expected_paths[run_id] = (case_id, variant, i)

        if len(expected_paths) != 16:
            raise ValueError("Attese 16 esecuzioni uniche per studio")
        if study_index == 0:
            hashes = freeze.get("file_sha256")
            if not isinstance(hashes, dict) or len(hashes) != 24:
                raise ValueError("Freeze del primo studio incompleto")
            expected_files = {
                *(f"{name}.json" for name in expected_paths),
                *(f"{pair['case_id']}__r01.pair_started.json" for pair in pairs),
            }
            if set(hashes) != expected_files:
                raise ValueError("Freeze del primo studio con nomi inattesi")
            # Anche i file pair_started sono sotto hash, ma non sono predizioni.
            for name in sorted(expected_files):
                _file(root, base / name, hashes[name])
            manifest_rows = [
                {
                    "run_id": run_id,
                    "case_id": case_id,
                    "variant": variant,
                    "result_file_sha256": hashes[f"{run_id}.json"],
                }
                for run_id, (case_id, variant, _) in sorted(expected_paths.items())
            ]
        else:
            manifest_rows = freeze.get("results")
            if not isinstance(manifest_rows, list) or len(manifest_rows) != 16:
                raise ValueError("Freeze ST privo di 16 risultati")
            if set(item["run_id"] for item in manifest_rows) != set(expected_paths):
                raise ValueError("Freeze ST non copre esattamente i 16 run")
            if len({item["run_id"] for item in manifest_rows}) != 16:
                raise ValueError("Run duplicati nel freeze ST")

        each_pair = {}
        for item in manifest_rows:
            run_id = item["run_id"]
            case_id, variant, order_index = expected_paths[run_id]
            if item.get("case_id") != case_id or item.get("variant") != variant:
                raise ValueError("Caso/variante non coerente con il piano")
            expected_relative = (
                f"data/results/paired/{protocol}/{run_id}.json"
            )
            if (study_index == 1 and
                    item.get("result_relative_path") != expected_relative):
                raise ValueError("Path relativo ST non atteso")
            result = _file(
                root, root / expected_relative,
                item["result_file_sha256"],
            )
            provenance = result.get("paired_provenance") or {}
            if (
                result.get("case_id") != case_id
                or result.get("variant") != variant
                or provenance.get("protocol") != protocol
                or provenance.get("run_id") != run_id
                or provenance.get("frozen_plan_sha256") != plan_hash
                or provenance.get("git_commit") != BASE_COMMITS[study_index]
                or provenance.get("execution_order_index") != order_index
                or provenance.get("paired_evidence_sha256")
                    != result.get("evidence_sha256")
            ):
                raise ValueError(f"Metadati di esecuzione incoerenti: {run_id}")
            if study_index == 1:
                if item.get("evidence_sha256") != result.get("evidence_sha256"):
                    raise ValueError("Evidence SHA ST differente")
                if item.get("json_status") != result.get("json_status"):
                    raise ValueError("Stato JSON ST differente")
            each_pair.setdefault(case_id, []).append(result["evidence_sha256"])
            raw = result.get("raw_response")
            start, end = _window(manifest[case_id])
            audit = audit_openrca_v2(
                raw, instruction=manifest[case_id]["instruction"],
                start_unix=start, end_unix=end,
            )
            rows.append({
                "protocol": protocol,
                "case_id": case_id,
                "variant": variant,
                "run_id": run_id,
                "json_legacy_valid": result.get("json_status") == "valid_json",
                "v2_valid": audit["valid"],
                "v2_reason": audit["reason"],
                "schema_cardinality_valid": audit["schema_cardinality_valid"],
                "timestamp_in_window": audit["timestamp_in_window"],
                "temporal_outliers": audit["temporal_outliers"],
                "expected_faults": audit["expected_faults"],
                "diagnosed_faults": audit["diagnosed_faults"],
                "raw_response_present": isinstance(raw, str) and bool(raw.strip()),
            })
        if len(each_pair) != 8 or any(
            len(shas) != 2 or shas[0] != shas[1]
            for shas in each_pair.values()
        ):
            raise ValueError(f"Evidence differente tra i bracci: {protocol}")
        studies.append({
            "protocol": protocol,
            "freeze_sha256": _sha(freeze_bytes),
            "plan_sha256": plan_hash,
            "cases": len(each_pair),
            "runs": len(manifest_rows),
        })

    by_variant = {}
    for variant in sorted({row["variant"] for row in rows}):
        selected = [row for row in rows if row["variant"] == variant]
        by_variant[variant] = {
            "runs": len(selected),
            "legacy_json_valid": sum(x["json_legacy_valid"] for x in selected),
            "v2_contract_valid": sum(x["v2_valid"] for x in selected),
            "schema_cardinality_valid": sum(
                x["schema_cardinality_valid"] for x in selected
            ),
            "timestamp_in_window_among_schema_valid": sum(
                x["timestamp_in_window"] is True for x in selected
            ),
        }
    return {
        "audit": "v2_frozen_prediction_audit_v1",
        "studies": studies,
        "runs_checked": len(rows),
        "by_variant": by_variant,
        "v2_invalid_reasons": dict(Counter(
            x["v2_reason"] for x in rows if not x["v2_valid"]
        )),
        "error_breakdown": {
            "schema_or_cardinality_failures": sum(
                not x["schema_cardinality_valid"] for x in rows
            ),
            "temporal_only_failures": sum(
                x["schema_cardinality_valid"]
                and x["timestamp_in_window"] is False
                for x in rows
            ),
            "out_of_window_fault_timestamps": sum(
                len(x["temporal_outliers"]) for x in rows
            ),
            "outliers_within_60_seconds_of_boundary": sum(
                abs(item["signed_seconds_from_nearest_boundary"]) <= 60
                for x in rows for item in x["temporal_outliers"]
            ),
            "outliers_over_60_seconds_of_boundary": sum(
                abs(item["signed_seconds_from_nearest_boundary"]) > 60
                for x in rows for item in x["temporal_outliers"]
            ),
        },
        "runs": rows,
        "read_ground_truth": False,
        "read_market_zip": False,
        "read_scorer": False,
        "gemini_calls": 0,
        "files_written": False,
        "historical_predictions_modified": False,
        "limitations": [
            "Audit formale: non e' scoring e non determina cause corrette.",
            "Un timestamp fuori finestra puo' richiedere revisione della policy V2.",
            "Le coorti V1 sono piloti development e non valutazione blind.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    args = parser.parse_args()
    report = audit_frozen_predictions(args.data_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
