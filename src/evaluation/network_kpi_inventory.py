"""Fase A/2: inventario GT-free dei NOMI dei KPI di rete su finestre development.

Questo script e' separato dai detector R01-R11 e da tutti i runner LLM.
- Legge solo split_market_v1.csv + SHA-256 del manifest GT-free.
- Sceglie finestre development con seed fisso e senza overlap con
  evaluation, mixed_quarantine, OOD o finestre storiche gia' viste.
- Dal Market.zip legge SOLO timestamp, cmdb_id e kpi_name dei CSV metrici
  container/node/mesh: NON legge la colonna 'value', log o trace.
- Non legge query.csv, record.csv, scoring o predizioni.
- Output JSON su stdout, nessun file creato e zero chiamate Gemini.
- I casi selezionati diventano dati di SVILUPPO VISTI: non riutilizzarli
  come nuovi incidenti indipendenti in future ablation o blind test.

Esempio Colab (salvare stdout solamente in /content, non nei freeze):
 python src/evaluation/network_kpi_inventory.py \
   --data-dir /content/drive/MyDrive/Tesi_OpenRCA \
   > /content/network_kpi_inventory_v1.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


EXPECTED_SPLIT_SHA256 = "c3e99db3facbca592b13009829280b7402ed3a0b38e5bc687f2d1f8f73f2c724"
EXPECTED_MANIFEST_SHA256 = "5fabd40123aaa8bb614bb812f2994c776967b9b04ec3bfe477f89c1dde614d13"
SEED = "network-kpi-inventory-2026-11-03-v1"
SPLITS = {"development", "evaluation", "mixed_quarantine", "ood_holdout"}
CLOUDBEDS = ("cloudbed-1", "cloudbed-2")

# 12 casi storici di src/evaluation/paired_st_cohort.py (inclusi piloti),
# 8 del piano ST congelato + q009 e 4 casi della vecchia coorte 93ddc0c 
# visibili nei nomi degli artefatti development di Google Drive.
# Qualsiasi finestra sovrapposta a uno di essi viene esclusa.
SEEN_CASE_IDS = frozenset({
    "cloudbed-1_q002", "cloudbed-1_q009", "cloudbed-1_q016",
    "cloudbed-1_q034", "cloudbed-1_q035", "cloudbed-1_q036",
    "cloudbed-1_q038", "cloudbed-1_q040", "cloudbed-1_q043",
    "cloudbed-1_q052", "cloudbed-1_q063", "cloudbed-1_q065",
    "cloudbed-1_q067",
    "cloudbed-2_q006", "cloudbed-2_q007", "cloudbed-2_q012",
    "cloudbed-2_q015", "cloudbed-2_q033", "cloudbed-2_q046",
    "cloudbed-2_q053", "cloudbed-2_q055", "cloudbed-2_q066",
    "cloudbed-2_q067", "cloudbed-2_q068", "cloudbed-2_q073",
})
METRIC_SOURCES = (
    "metric_container.csv",
    "metric_node.csv",
    "metric_mesh.csv",
)
SPLIT_HEADERS = ["case_id", "cloudbed", "start_unix", "end_unix", "split"]
TIMEZONE = ZoneInfo("Asia/Shanghai")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _overlaps(a: dict, b: dict) -> bool:
    return (
        a["cloudbed"] == b["cloudbed"]
        and a["start_unix"] < b["end_unix"]
        and b["start_unix"] < a["end_unix"]
    )


def _rank(row: dict) -> str:
    return hashlib.sha256(f"{SEED}|{row['case_id']}".encode("utf-8")).hexdigest()


def select_audit_windows(
    split_path: Path,
    *,
    per_cloudbed: int = 2,
    verify_hash: bool = True,
    seen_case_ids: frozenset[str] = SEEN_CASE_IDS,
) -> tuple[list[dict], list[str]]:
    """Sceglie finestre senza toccare telemetria; mai casi holdout."""
    if type(per_cloudbed) is not int or per_cloudbed < 1:
        raise ValueError("per_cloudbed deve essere un intero positivo")

    if verify_hash and _sha256(split_path) != EXPECTED_SPLIT_SHA256:
        raise ValueError("SHA-256 split diverso dal file congelato; audit bloccato")

    with split_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != SPLIT_HEADERS:
            raise ValueError("Lo split deve avere ESATTAMENTE i 5 campi GT-free")
        rows = []
        ids = set()
        for original in reader:
            row = dict(original)
            case_id = row["case_id"]
            cb = row["cloudbed"]
            if cb not in CLOUDBEDS or not case_id.startswith(cb + "_q"):
                raise ValueError("ID o cloudbed non valido")
            if row["split"] not in SPLITS or case_id in ids:
                raise ValueError("Split non ammesso o case_id duplicato")
            ids.add(case_id)
            row["start_unix"] = int(row["start_unix"])
            row["end_unix"] = int(row["end_unix"])
            if row["start_unix"] >= row["end_unix"]:
                raise ValueError("Intervallo non valido")
            rows.append(row)

    if not rows:
        raise ValueError("Split vuoto")
    if not seen_case_ids.issubset(ids):
        raise ValueError("Casi storici assenti dallo split: controllo non sicuro")
    if verify_hash and Counter(row["split"] for row in rows) != {
        "development": 92, "evaluation": 23,
        "mixed_quarantine": 18, "ood_holdout": 15,
    }:
        raise ValueError("Conteggi split inattesi")

    # Le finestre holdout e quelle gia' esaminate sono tutte PROTETTE.
    protected = [
        row for row in rows
        if row["split"] != "development" or row["case_id"] in seen_case_ids
    ]
    eligible = [
        row for row in rows
        if row["split"] == "development"
        and row["case_id"] not in seen_case_ids
        and not any(_overlaps(row, other) for other in protected)
    ]

    selected = []
    for cb in CLOUDBEDS:
        candidates = sorted(
            (r for r in eligible if r["cloudbed"] == cb),
            key=lambda r: (_rank(r), r["case_id"]),
        )
        chosen = []
        for row in candidates:
            if not any(_overlaps(row, prior) for prior in chosen):
                chosen.append(row)
            if len(chosen) == per_cloudbed:
                break
        if len(chosen) != per_cloudbed:
            raise ValueError(f"Finestre development indipendenti insufficienti: {cb}")
        selected.extend(chosen)

    # Tutti gli ID development che condividono intervalli di telemetria
    # con questa ispezione saranno considerati 'visti' per lavori futuri.
    consumed_ids = sorted({
        row["case_id"] for row in rows
        if row["split"] == "development"
        and any(_overlaps(row, chosen) for chosen in selected)
    })
    return selected, consumed_ids


def _days_for_window(start: int, end: int) -> list[str]:
    current = datetime.fromtimestamp(start, timezone.utc).astimezone(TIMEZONE).date()
    last = datetime.fromtimestamp(end - 1, timezone.utc).astimezone(TIMEZONE).date()
    days = []
    while current <= last:
        days.append(current.strftime("%Y_%m_%d"))
        current += timedelta(days=1)
    return days


def inventory_kpis(
    market_zip: Path,
    split_path: Path,
    manifest_path: Path,
    *,
    per_cloudbed: int = 2,
    verify_hashes: bool = True,
    seen_case_ids: frozenset[str] = SEEN_CASE_IDS,
) -> dict:
    """Conta i nomi KPI osservati SOLO negli intervalli scelti."""
    if verify_hashes and _sha256(manifest_path) != EXPECTED_MANIFEST_SHA256:
        raise ValueError("SHA-256 manifest GT-free inatteso; audit bloccato")
    selected, consumed = select_audit_windows(
        split_path, per_cloudbed=per_cloudbed,
        verify_hash=verify_hashes, seen_case_ids=seen_case_ids,
    )
    if not market_zip.is_file():
        raise FileNotFoundError(market_zip)

    by_cloud = defaultdict(list)
    for window in selected:
        by_cloud[window["cloudbed"]].append(window)

    counts = Counter()
    samples_per_window = Counter()
    component_sets = defaultdict(set)
    present_windows = defaultdict(set)
    inspected_paths = []
    with zipfile.ZipFile(market_zip, "r") as archive:
        members = set(archive.namelist())
        for cb in CLOUDBEDS:
            days = sorted({
                day
                for window in by_cloud[cb]
                for day in _days_for_window(window["start_unix"], window["end_unix"])
            })
            for source in METRIC_SOURCES:
                for day in days:
                    member = f"Market/{cb}/telemetry/{day}/metric/{source}"
                    if member not in members:
                        raise FileNotFoundError(f"CSV di telemetria mancante: {member}")
                    inspected_paths.append(member)
                    with archive.open(member) as raw:
                        reader = pd.read_csv(
                            raw,
                            usecols=["timestamp", "cmdb_id", "kpi_name"],
                            chunksize=100_000,
                        )
                        for chunk in reader:
                            stamp = pd.to_numeric(chunk["timestamp"], errors="coerce")
                            # I dati fuori dalle finestre ammesse non entrano in statistiche.
                            for window in by_cloud[cb]:
                                mask = stamp.ge(window["start_unix"]) & stamp.lt(
                                    window["end_unix"]
                                )
                                relevant = chunk.loc[mask, ["cmdb_id", "kpi_name"]]
                                relevant = relevant.dropna(subset=["kpi_name"])
                                if relevant.empty:
                                    continue
                                case_id = window["case_id"]
                                samples_per_window[(cb, source, case_id)] += len(relevant)
                                for kpi, part in relevant.groupby("kpi_name", sort=False):
                                    key = (cb, source, str(kpi))
                                    counts[key] += len(part)
                                    present_windows[key].add(case_id)
                                    component_sets[key].update(
                                        str(item) for item in part["cmdb_id"].dropna().unique()
                                    )

    sources = []
    for cb in CLOUDBEDS:
        for source in METRIC_SOURCES:
            kpis = []
            for (key_cb, key_source, kpi), n in sorted(counts.items()):
                if (key_cb, key_source) != (cb, source):
                    continue
                key = (cb, source, kpi)
                kpis.append({
                    "kpi_name": kpi,
                    "observed_rows": n,
                    "distinct_components": len(component_sets[key]),
                    "windows_with_kpi": len(present_windows[key]),
                })
            sources.append({
                "cloudbed": cb,
                "source": source,
                "selected_windows": len(by_cloud[cb]),
                "matched_rows": sum(
                    n for (kcb, src, _), n in samples_per_window.items()
                    if kcb == cb and src == source
                ),
                "distinct_kpis": len(kpis),
                "kpis": kpis,
            })

    return {
        "audit": "network_kpi_inventory_v1",
        "scope": "GT-free, development-only, previously unseen nonoverlapping windows",
        "split_sha256": _sha256(split_path),
        "manifest_sha256": _sha256(manifest_path),
        "selection_seed": SEED,
        "selected_windows": [
            {k: w[k] for k in SPLIT_HEADERS} for w in selected
        ],
        "development_case_ids_now_seen": consumed,
        "sources": sources,
        "files_read": inspected_paths,
        "read_ground_truth": False,
        "read_metric_values": False,
        "read_logs": False,
        "read_traces": False,
        "gemini_calls": 0,
        "limitations": [
            "L'assenza di un KPI in questo campione non dimostra assenza nell'intero Market.",
            "Il nome KPI non prova che il segnale sia una misura discriminante.",
            "Un conteggio non rivela unità, precisione, causalità o semantica del KPI.",
            "Le finestre ispezionate sono ora development VISTO, non future valutazioni indipendenti.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--per-cloudbed", type=int, default=2)
    args = parser.parse_args()
    root = args.data_dir
    print(json.dumps(
        inventory_kpis(
            market_zip=root / "Market.zip",
            split_path=root / "data/processed/split_market_v1.csv",
            manifest_path=root / "data/processed/benchmark_inputs_market.csv",
            per_cloudbed=args.per_cloudbed,
        ),
        ensure_ascii=False, indent=2,
    ))


if __name__ == "__main__":
    main()
