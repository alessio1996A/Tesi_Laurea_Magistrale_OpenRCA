"""Audit A/3: statistiche descrittive su KPI di rete, SOLO finestre development gia' viste.

Non classifica guasti, non costruisce regole e non accede a ground truth.
Richiede il JSON originale prodotto da network_kpi_inventory.py e
ricontrolla selezione, hash dei manifest e finestre protette.
La colonna value e' convertita a numero SOLO dopo il filtro temporale.
Il report contiene profili per componente, KPI e finestra, senza soglie.
Nessun file viene scritto; stdout contiene JSON. Nessuna API LLM.

Esempio:
 python src/evaluation/network_signal_profile.py \
  --data-dir /content/drive/MyDrive/Tesi_OpenRCA \
  --inventory /content/network_kpi_inventory_v1.json \
  > /content/network_signal_profile_v1.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import zipfile
from collections import defaultdict
from pathlib import Path

import pandas as pd

from evaluation.network_kpi_inventory import (
    CLOUDBEDS, EXPECTED_MANIFEST_SHA256, METRIC_SOURCES, SEEN_CASE_IDS,
    SPLIT_HEADERS, _days_for_window, _sha256, select_audit_windows,
)

# La whitelist usa nomi osservati nell'inventario, non categorie etichettate.
EXACT = {
    "metric_container.csv": frozenset({
        "container_network_receive_errors.eth0",
        "container_network_transmit_errors.eth0",
        "container_network_receive_packets.eth0",
        "container_network_transmit_packets.eth0",
        "container_network_receive_packets_dropped.eth0",
        "container_network_transmit_packets_dropped.eth0",
    }),
    "metric_node.csv": frozenset({
        "system.net.tcp.retrans_segs",
        "system.tcp.retrans_pct",
        "system.net.tcp.out_segs",
        "system.net.tcp.in_segs",
        "system.net.packets_in.error",
        "system.net.packets_out.error",
    }),
}
MESH_PREFIXES = (
    "istio_request_duration_milliseconds.",
    "istio_requests.",
)
METRIC_WHITELIST = frozenset(METRIC_SOURCES)


def _selected_kpi(source: str, kpi: str) -> bool:
    if source == "metric_mesh.csv":
        return kpi.startswith(MESH_PREFIXES)
    return kpi in EXACT.get(source, frozenset())


def _read_inventory(
    inventory_path: Path,
    split_path: Path,
    manifest_path: Path,
    *,
    per_cloudbed: int,
    verify_hashes: bool,
    seen_case_ids: frozenset[str],
) -> tuple[dict, list[dict]]:
    inventory_bytes = inventory_path.read_bytes()
    plan = json.loads(inventory_bytes.decode("utf-8"))
    if plan.get("audit") != "network_kpi_inventory_v1":
        raise ValueError("Versione inventario KPI inattesa")
    if plan.get("read_ground_truth") is not False:
        raise ValueError("L'inventario non dichiara una lettura GT-free")
    if plan.get("read_metric_values") is not False or plan.get("gemini_calls") != 0:
        raise ValueError("Inventario incompatibile con la fase A/2")
    if plan.get("split_sha256") != _sha256(split_path):
        raise ValueError("Hash split non coerente con l'inventario")
    if plan.get("manifest_sha256") != _sha256(manifest_path):
        raise ValueError("Hash manifest non coerente con l'inventario")
    if verify_hashes and _sha256(manifest_path) != EXPECTED_MANIFEST_SHA256:
        raise ValueError("Manifest GT-free non originale: audit bloccato")

    selected, consumed = select_audit_windows(
        split_path,
        per_cloudbed=per_cloudbed,
        verify_hash=verify_hashes,
        seen_case_ids=seen_case_ids,
    )
    expected = [{k: row[k] for k in SPLIT_HEADERS} for row in selected]
    if plan.get("selected_windows") != expected:
        raise ValueError("Finestre nell'inventario diverse dalla selezione verificata")
    if plan.get("development_case_ids_now_seen") != consumed:
        raise ValueError("Provenienza dei casi development consumati incoerente")
    return {
        "inventory_sha256": hashlib.sha256(inventory_bytes).hexdigest(),
        "selected_windows": selected,
        "development_case_ids_now_seen": consumed,
    }, selected


def _describe(series: list[tuple[int, float | None]]) -> dict:
    ordered = sorted(series, key=lambda pair: pair[0])
    valid = [(stamp, value) for stamp, value in ordered if value is not None]
    values = pd.Series([value for _, value in valid], dtype="float64")
    gaps = [
        valid[i][0] - valid[i - 1][0]
        for i in range(1, len(valid))
        if valid[i][0] > valid[i - 1][0]
    ]
    steps = [
        valid[i][1] - valid[i - 1][1]
        for i in range(1, len(valid))
        if valid[i][0] > valid[i - 1][0]
    ]
    n = len(valid)
    return {
        "rows": len(ordered),
        "numeric_samples": n,
        "non_numeric_or_non_finite": len(ordered) - n,
        "distinct_values": int(values.nunique()) if n else 0,
        "minimum": float(values.min()) if n else None,
        "median": float(values.median()) if n else None,
        "p95": float(values.quantile(0.95)) if n else None,
        "maximum": float(values.max()) if n else None,
        "zeros": int((values == 0).sum()) if n else 0,
        "negative_values": int((values < 0).sum()) if n else 0,
        "first_timestamp": int(valid[0][0]) if n else None,
        "last_timestamp": int(valid[-1][0]) if n else None,
        "median_sampling_gap_seconds": float(pd.Series(gaps).median()) if gaps else None,
        "decreasing_steps": sum(delta < 0 for delta in steps),
        "increasing_steps": sum(delta > 0 for delta in steps),
        "flat_steps": sum(delta == 0 for delta in steps),
        "max_positive_step": max((d for d in steps if d > 0), default=None),
    }


def profile_signals(
    *,
    market_zip: Path,
    split_path: Path,
    manifest_path: Path,
    inventory_path: Path,
    per_cloudbed: int = 2,
    verify_hashes: bool = True,
    seen_case_ids: frozenset[str] = SEEN_CASE_IDS,
) -> dict:
    """Statistiche solo per i KPI della whitelist e le stesse finestre A/2."""
    proof, windows = _read_inventory(
        Path(inventory_path), Path(split_path), Path(manifest_path),
        per_cloudbed=per_cloudbed,
        verify_hashes=verify_hashes,
        seen_case_ids=seen_case_ids,
    )
    market_zip = Path(market_zip)
    if not market_zip.is_file():
        raise FileNotFoundError(market_zip)
    by_cloud: dict[str, list[dict]] = defaultdict(list)
    for window in windows:
        by_cloud[window["cloudbed"]].append(window)

    data: dict[tuple[str, str, str, str, str], list[tuple[int, float | None]]] = defaultdict(list)
    paths = []
    with zipfile.ZipFile(market_zip, "r") as archive:
        members = set(archive.namelist())
        for cb in CLOUDBEDS:
            days = sorted({
                day for w in by_cloud[cb]
                for day in _days_for_window(w["start_unix"], w["end_unix"])
            })
            for source in sorted(METRIC_WHITELIST):
                for day in days:
                    path = f"Market/{cb}/telemetry/{day}/metric/{source}"
                    if path not in members:
                        raise FileNotFoundError(f"CSV di telemetria assente: {path}")
                    paths.append(path)
                    with archive.open(path) as raw:
                        reader = pd.read_csv(
                            raw,
                            usecols=["timestamp", "cmdb_id", "kpi_name", "value"],
                            dtype={"cmdb_id": "string", "kpi_name": "string", "value": "string"},
                            chunksize=100_000,
                        )
                        for chunk in reader:
                            stamp = pd.to_numeric(chunk["timestamp"], errors="coerce")
                            for window in by_cloud[cb]:
                                mask = (
                                    stamp.ge(window["start_unix"])
                                    & stamp.lt(window["end_unix"])
                                )
                                subset = chunk.loc[mask, ["cmdb_id", "kpi_name", "value"]]
                                if subset.empty:
                                    continue
                                names = subset["kpi_name"].fillna("")
                                subset = subset.loc[
                                    names.map(lambda x: _selected_kpi(source, str(x)))
                                ]
                                if subset.empty:
                                    continue
                                for index, row in subset.iterrows():
                                    if pd.isna(row["cmdb_id"]):
                                        continue
                                    raw_value = row["value"]
                                    try:
                                        number = float(raw_value)
                                        value = number if math.isfinite(number) else None
                                    except (ValueError, TypeError):
                                        value = None
                                    key = (
                                        cb, source, window["case_id"],
                                        str(row["cmdb_id"]), str(row["kpi_name"])
                                    )
                                    data[key].append((int(stamp.loc[index]), value))

    profiles = []
    for (cb, source, case_id, cmdb_id, kpi), entries in sorted(data.items()):
        profiles.append({
            "cloudbed": cb,
            "source": source,
            "case_id": case_id,
            "cmdb_id": cmdb_id,
            "kpi_name": kpi,
            "statistics": _describe(entries),
            "unit": "non_verificata",
            "signal_semantics": "non_verificata",
            "root_cause_verified": False,
        })
    return {
        "audit": "network_signal_profile_v1",
        "source_inventory_sha256": proof["inventory_sha256"],
        "selected_windows": [
            {k: w[k] for k in SPLIT_HEADERS} for w in windows
        ],
        "development_case_ids_now_seen": proof["development_case_ids_now_seen"],
        "profile_count": len(profiles),
        "files_read": paths,
        "profiles": profiles,
        "ground_truth_read": False,
        "gemini_calls": 0,
        "classification_performed": False,
        "limitations": [
            "Descrizione statistica, non prova di guasto o attribuzione causale.",
            "TCP retrans_segs e retrans_pct sono metriche di NODE, non di container.",
            "Gli errori RX/TX non identificano univocamente packet corruption.",
            "Le durate Istio includono potenzialmente elaborazione applicativa.",
            "Le unita', la natura dei contatori e gli eventuali reset non sono verificati.",
            "Le finestre development osservate sono gia' viste e non sono nuove valutazioni blind.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args()
    data_dir = args.data_dir
    print(json.dumps(
        profile_signals(
            market_zip=data_dir / "Market.zip",
            split_path=data_dir / "data/processed/split_market_v1.csv",
            manifest_path=data_dir / "data/processed/benchmark_inputs_market.csv",
            inventory_path=args.inventory,
        ),
        indent=2, ensure_ascii=False, allow_nan=False,
    ))


if __name__ == "__main__":
    main()
