"""A/6 — Verifica temporale esatta dei KPI R03/R05, SENZA ground truth.

Legge soltanto metric_node.csv e metric_mesh.csv del Market.zip e soltanto
le QUATTRO finestre development gia' consumate dall'inventario A/2.
Richiede e verifica i JSON originali A/2, A/3 e A/5, lo split e il manifest.
Non apre record.csv, query.csv, log, trace o output degli agenti.
Nessuna soglia, classificazione, inferenza causale o chiamata Gemini.
Il matching e' ESATTO al timestamp in secondi: nessuna interpolazione.
Campioni invalidi o duplicati non contano come coppie numeriche valide.

Esecuzione dalla radice del repository con PYTHONPATH=src:
 python -m evaluation.network_temporal_alignment \
  --data-dir /content/drive/MyDrive/Tesi_OpenRCA \
  --inventory /content/network_kpi_inventory_v1.json \
  --profile /content/network_signal_profile_v1.json \
  --pairing /content/network_signal_pairing_v1.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from evaluation.network_signal_profile import _read_inventory
from evaluation.network_feasibility_summary import summarize
from evaluation.network_kpi_inventory import (
    CLOUDBEDS, EXPECTED_MANIFEST_SHA256, SEEN_CASE_IDS,
    _days_for_window,
)

NODE_NAMES = frozenset({
    "system.net.tcp.retrans_segs", "system.tcp.retrans_pct",
    "system.net.tcp.in_segs", "system.net.tcp.out_segs",
})
DURATION = "istio_request_duration_milliseconds."
REQUESTS = "istio_requests."
SOURCES = ("metric_node.csv", "metric_mesh.csv")


def _numeric(raw: object) -> float | None:
    try:
        n = float(raw)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def _kind(source: str, name: str) -> tuple[str, str] | None:
    if source == "metric_node.csv":
        return ("node", name) if name in NODE_NAMES else None
    if name.startswith(DURATION) and name[len(DURATION):]:
        return ("mesh", "duration|" + name[len(DURATION):])
    if name.startswith(REQUESTS) and name[len(REQUESTS):]:
        return ("mesh", "requests|" + name[len(REQUESTS):])
    return None


def _validate_lineage(
    *, root: Path, inventory: Path, profile: Path, pairing: Path,
    verify_hashes: bool, seen_case_ids: frozenset[str],
) -> tuple[list[dict], dict]:
    split = root / "data/processed/split_market_v1.csv"
    manifest = root / "data/processed/benchmark_inputs_market.csv"
    proof, windows = _read_inventory(
        inventory, split, manifest, per_cloudbed=2,
        verify_hashes=verify_hashes, seen_case_ids=seen_case_ids,
    )
    if verify_hashes and hashlib.sha256(manifest.read_bytes()).hexdigest() != EXPECTED_MANIFEST_SHA256:
        raise ValueError("Manifest GT-free non originale")
    prior = summarize(inventory, profile)
    if prior["source_inventory_sha256"] != proof["inventory_sha256"]:
        raise ValueError("Provenienza A/2 incoerente")
    if prior["source_windows"] != [
        {k: w[k] for k in ("case_id", "cloudbed", "start_unix", "end_unix", "split")}
        for w in windows
    ]:
        raise ValueError("Finestre A/3 incoerenti")
    pairing_bytes = pairing.read_bytes()
    previous_pairing = json.loads(pairing_bytes.decode("utf-8"))
    if (
        previous_pairing.get("audit") != "network_signal_pairing_v1"
        or previous_pairing.get("input_inventory_sha256") != prior["source_inventory_sha256"]
        or previous_pairing.get("input_profile_sha256") != prior["source_profile_sha256"]
        or previous_pairing.get("source_windows") != prior["source_windows"]
        or previous_pairing.get("read_ground_truth") is not False
        or previous_pairing.get("read_market_zip") is not False
        or previous_pairing.get("classification_performed") is not False
        or previous_pairing.get("gemini_calls") != 0
    ):
        raise ValueError("Provenienza A/5 o dichiarazioni GT-free incoerenti")
    return windows, {
        "input_inventory_sha256": prior["source_inventory_sha256"],
        "input_profile_sha256": prior["source_profile_sha256"],
        "input_pairing_sha256": hashlib.sha256(pairing_bytes).hexdigest(),
    }


def _add_signal(
    groups: dict, duplicates: set, key: tuple, signal: str, value: float | None,
) -> None:
    slot = groups.setdefault(key, {})
    duplicate_key = (*key, signal)
    if signal in slot:
        # Due campioni con stessa chiave: nessuna scelta arbitraria.
        duplicates.add(duplicate_key)
        slot[signal] = None
    elif duplicate_key not in duplicates:
        slot[signal] = value


def _totals(groups: dict, *, source: str, duplicates: set) -> dict:
    per_cloud = defaultdict(Counter)
    for key, signals in groups.items():
        cb = key[0]
        counter = per_cloud[cb]
        counter["timestamp_keys_with_any_signal"] += 1
        if source == "node":
            names = ("system.net.tcp.retrans_segs", "system.tcp.retrans_pct")
            context = ("system.net.tcp.in_segs", "system.net.tcp.out_segs")
        else:
            names = ("duration", "requests")
            context = ()
        if not all(name in signals for name in names):
            counter["incomplete_timestamp_pairs"] += 1
            continue
        counter["exact_timestamp_pairs"] += 1
        if source == "node" and all(name in signals for name in context):
            counter["timestamp_pairs_with_both_context_kpis"] += 1
        if any((*key, name) in duplicates for name in names):
            counter["ambiguous_duplicate_pairs"] += 1
            continue
        a, b = (signals[name] for name in names)
        if a is None or b is None:
            counter["non_numeric_pairs"] += 1
            continue
        counter["both_numeric_pairs"] += 1
        if a > 0 and b > 0:
            counter["both_positive_same_timestamp"] += 1
        elif a > 0:
            counter["first_positive_second_nonpositive"] += 1
        elif b > 0:
            counter["second_positive_first_nonpositive"] += 1
        else:
            counter["neither_positive"] += 1
    # Duplicati su una sola metrica, anche senza una coppia, sono visibili.
    for key in duplicates:
        cb = key[0]
        per_cloud[cb]["ambiguous_signal_timestamp_keys"] += 1
    merged = Counter()
    rows = []
    for cb in CLOUDBEDS:
        merged.update(per_cloud[cb])
        rows.append({"cloudbed": cb, **dict(sorted(per_cloud[cb].items()))})
    return {"by_cloudbed": rows, "total": dict(sorted(merged.items()))}


def analyze_temporal_alignment(
    *, data_dir: Path, inventory_path: Path, profile_path: Path, pairing_path: Path,
    verify_hashes: bool = True, seen_case_ids: frozenset[str] = SEEN_CASE_IDS,
) -> dict:
    """Legge soli nomi e valori KPI permessi, produce solo conteggi aggregati."""
    root = Path(data_dir)
    windows, provenance = _validate_lineage(
        root=root, inventory=Path(inventory_path), profile=Path(profile_path),
        pairing=Path(pairing_path),
        verify_hashes=verify_hashes, seen_case_ids=seen_case_ids,
    )
    zip_path = root / "Market.zip"
    if not zip_path.is_file():
        raise FileNotFoundError(zip_path)
    by_cb = defaultdict(list)
    for window in windows:
        by_cb[window["cloudbed"]].append(window)

    node, mesh = {}, {}
    node_duplicates, mesh_duplicates = set(), set()
    paths = []
    skipped_bad_timestamps = 0

    with zipfile.ZipFile(zip_path) as archive:
        members = set(archive.namelist())
        for cb in CLOUDBEDS:
            days = sorted({
                day for w in by_cb[cb]
                for day in _days_for_window(w["start_unix"], w["end_unix"])
            })
            for source in SOURCES:
                for day in days:
                    path = f"Market/{cb}/telemetry/{day}/metric/{source}"
                    if path not in members:
                        raise FileNotFoundError(f"Telemetria attesa mancante: {path}")
                    paths.append(path)
                    with archive.open(path) as raw:
                        for chunk in pd.read_csv(
                            raw, usecols=["timestamp", "cmdb_id", "kpi_name", "value"],
                            dtype={
                                "cmdb_id": "string", "kpi_name": "string",
                                "value": "string",
                            },
                            chunksize=100_000,
                        ):
                            stamps = pd.to_numeric(chunk["timestamp"], errors="coerce")
                            for window in by_cb[cb]:
                                filtered = chunk.loc[
                                    stamps.ge(window["start_unix"])
                                    & stamps.lt(window["end_unix"]),
                                    ["cmdb_id", "kpi_name", "value"],
                                ]
                                # I valori fuori dalle finestre NON vengono
                                # interpretati, aggregati o riportati.
                                for index, item in filtered.iterrows():
                                    timestamp = stamps.loc[index]
                                    if not math.isfinite(timestamp) or not float(timestamp).is_integer():
                                        skipped_bad_timestamps += 1
                                        continue
                                    if pd.isna(item["cmdb_id"]) or pd.isna(item["kpi_name"]):
                                        continue
                                    kind = _kind(source, str(item["kpi_name"]))
                                    if kind is None:
                                        continue
                                    ts = int(timestamp)
                                    component = str(item["cmdb_id"])
                                    number = _numeric(item["value"])
                                    if kind[0] == "node":
                                        key = (cb, window["case_id"], component, ts)
                                        _add_signal(node, node_duplicates, key, kind[1], number)
                                    else:
                                        role, suffix = kind[1].split("|", 1)
                                        key = (cb, window["case_id"], component, suffix, ts)
                                        _add_signal(mesh, mesh_duplicates, key, role, number)

    return {
        "audit": "network_temporal_alignment_v1",
        **provenance,
        "selected_windows": [
            {k: w[k] for k in ("case_id", "cloudbed", "start_unix", "end_unix", "split")}
            for w in windows
        ],
        "reused_existing_development_windows": True,
        "new_case_count": 0,
        "read_market_zip": True,
        "read_ground_truth": False,
        "read_logs": False,
        "read_traces": False,
        "gemini_calls": 0,
        "classification_performed": False,
        "temporal_matching": "same cloudbed + case + component + suffix(if mesh) + exact unix-second timestamp",
        "r03": _totals(node, source="node", duplicates=node_duplicates),
        "r05": _totals(mesh, source="mesh", duplicates=mesh_duplicates),
        "skipped_bad_timestamps": skipped_bad_timestamps,
        "metric_files_read": paths,
        "limitations": [
            "Co-occorrenza allo stesso timestamp, non causalita' o root cause.",
            "Le unita' e la semantica di TCP e Istio sono ancora da verificare.",
            "Non prova che packet retransmission del nodo identifichi il container.",
            "Durata di richiesta Istio non equivale a sola latenza di rete.",
            "Nessuna nuova regola deterministica o soglia e' stata creata.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--pairing", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze_temporal_alignment(
        data_dir=args.data_dir, inventory_path=args.inventory,
        profile_path=args.profile, pairing_path=args.pairing,
    ), indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
