"""RQ2-K: catalogo dei KPI misurato sui SOLI incidenti discovery (sola lettura).

Scopo
-----
Fornire, prima del congelamento del protocollo K, i numeri che servono a fissare
due parametri senza indovinarli:
  * il passo di campionamento dei KPI (da cui l'orizzonte globale H);
  * la quota di campioni mancanti (da cui la soglia di "valutabilita'").
Dice anche quali KPI esistono davvero per nodi e container, in cloudbed-1 e in
cloudbed-2, cosi' si puo' controllare se i nomi scritti dai modelli esistono.

Garanzie
--------
  * GT-free: legge solo il manifest (finestre dei casi, senza etichette) e le
    metriche di nodo e container dentro la finestra ufficiale del caso.
    Rifiuta un manifest con colonne di ground truth.
  * Solo discovery: qualunque case_id fuori da DISCOVERY_CASES e' rifiutato,
    quindi i casi sigillati non si possono aprire da qui per errore.
  * Nessuna chiamata a modelli, nessuna scrittura tranne il file di uscita,
    che e' create-only (se esiste non viene sovrascritto).
  * Non copre service, mesh, runtime, log e trace: il formato e' diverso e il
    protocollo K usa solo i livelli node e container.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import zipfile
from pathlib import Path

import pandas as pd

from agent.tools import _get_telemetry_csv_paths

VERSION = "rq2_k_catalog_v1"

# I soli quattro incidenti di discovery. Nessun altro caso e' ammesso.
DISCOVERY_CASES = (
    "cloudbed-1_q032",
    "cloudbed-1_q050",
    "cloudbed-2_q026",
    "cloudbed-2_q045",
)

LEVELS = {"node_metrics": "node", "container_metrics": "container"}
COLUMNS = ["timestamp", "cmdb_id", "kpi_name", "value"]
GT_COLUMNS = {"reason", "scoring_points"}
MANIFEST_RELATIVE = "data/processed/benchmark_inputs_market.csv"
CHUNK_ROWS = 100_000


class CatalogScopeError(ValueError):
    """Richiesto un caso che non e' un incidente di discovery, o manifest con GT."""


def load_case(manifest_path: Path, case_id: str) -> dict:
    """Finestra del caso dal manifest (senza etichette), solo se e' discovery."""
    if case_id not in DISCOVERY_CASES:
        raise CatalogScopeError(f"Caso non ammesso (non e' discovery): {case_id}")
    manifest = pd.read_csv(manifest_path)
    if GT_COLUMNS & set(manifest.columns):
        raise CatalogScopeError("Il manifest contiene colonne di ground truth.")
    rows = manifest.loc[manifest["case_id"] == case_id]
    if len(rows) != 1:
        raise CatalogScopeError(f"Case ID assente o duplicato: {case_id}")
    row = rows.iloc[0]
    case = {
        "case_id": case_id,
        "cloudbed": str(row["cloudbed"]),
        "start_unix": int(row["start_unix"]),
        "end_unix": int(row["end_unix"]),
    }
    if case["cloudbed"] not in ("cloudbed-1", "cloudbed-2"):
        raise CatalogScopeError("Cloudbed non valido nel manifest.")
    if case["start_unix"] >= case["end_unix"]:
        raise CatalogScopeError("Intervallo non valido nel manifest.")
    return case


def read_window(zip_path: Path, case: dict, kind: str) -> pd.DataFrame:
    """Metriche di un livello dentro la finestra [start, end) del caso."""
    paths = _get_telemetry_csv_paths(
        start_unix=case["start_unix"], end_unix=case["end_unix"],
        market_system=case["cloudbed"], data_kind=kind,
    )
    blocks = []
    with zipfile.ZipFile(zip_path, "r") as archive:
        for path in paths:
            with archive.open(path) as handle:
                for chunk in pd.read_csv(handle, usecols=COLUMNS,
                                         chunksize=CHUNK_ROWS):
                    stamps = pd.to_numeric(chunk["timestamp"], errors="coerce")
                    mask = stamps.ge(case["start_unix"]) & stamps.lt(case["end_unix"])
                    if mask.any():
                        blocks.append(chunk.loc[mask, COLUMNS].copy())
    if not blocks:
        return pd.DataFrame(columns=COLUMNS)
    return pd.concat(blocks, ignore_index=True)


def _median(values: list[float]) -> float | None:
    clean = sorted(v for v in values if v is not None and not math.isnan(v))
    if not clean:
        return None
    mid = len(clean) // 2
    return float(clean[mid] if len(clean) % 2 else (clean[mid - 1] + clean[mid]) / 2)


def kpi_stats(frame: pd.DataFrame, window_seconds: int) -> dict:
    """Statistiche per KPI: componenti, passo di campionamento, copertura.

    Passo = mediana delle differenze tra istanti consecutivi, mediana sulle
    serie del KPI. Copertura di una serie = istanti distinti osservati / istanti
    attesi (finestra / passo del KPI), limitata a 1. Una copertura bassa indica
    campioni mancanti, quindi condizioni "sconosciute" nella logica a tre valori.
    """
    result: dict[str, dict] = {}
    if frame.empty:
        return result
    frame = frame.assign(timestamp=pd.to_numeric(frame["timestamp"], errors="coerce"))
    frame = frame.dropna(subset=["timestamp"])
    for kpi, group in frame.groupby("kpi_name", sort=True):
        steps, stamps_per_series = [], {}
        for cmdb_id, series in group.groupby("cmdb_id", sort=True):
            stamps = sorted(set(series["timestamp"].astype("int64")))
            stamps_per_series[cmdb_id] = len(stamps)
            if len(stamps) >= 2:
                diffs = [b - a for a, b in zip(stamps, stamps[1:])]
                steps.append(_median([float(d) for d in diffs]))
        step = _median(steps)
        coverages = []
        if step:
            expected = max(1.0, window_seconds / step)
            coverages = [min(1.0, n / expected) for n in stamps_per_series.values()]
        result[str(kpi)] = {
            "components": len(stamps_per_series),
            "step_seconds": step,
            "coverage_min": min(coverages) if coverages else None,
            "coverage_median": _median(coverages),
        }
    return result


def build_catalog(zip_path: Path, manifest_path: Path,
                  cases: tuple[str, ...] = DISCOVERY_CASES) -> dict:
    """Catalogo per caso e aggregato per cloudbed e livello."""
    per_case = {}
    for case_id in cases:
        case = load_case(manifest_path, case_id)
        window = case["end_unix"] - case["start_unix"]
        levels = {}
        for kind, level in LEVELS.items():
            levels[level] = kpi_stats(read_window(zip_path, case, kind), window)
        per_case[case_id] = {"cloudbed": case["cloudbed"],
                             "window_seconds": window, "levels": levels}

    # Aggregato: per (livello, KPI) in quali cloudbed compare e con quale passo.
    merged: dict[str, dict[str, dict]] = {}
    for case_id, entry in per_case.items():
        for level, kpis in entry["levels"].items():
            for kpi, stats in kpis.items():
                slot = merged.setdefault(level, {}).setdefault(kpi, {
                    "cloudbeds": [], "cases": [], "steps": [], "coverage_min": [],
                })
                if entry["cloudbed"] not in slot["cloudbeds"]:
                    slot["cloudbeds"].append(entry["cloudbed"])
                slot["cases"].append(case_id)
                slot["steps"].append(stats["step_seconds"])
                slot["coverage_min"].append(stats["coverage_min"])
    aggregate = {}
    for level, kpis in merged.items():
        aggregate[level] = {}
        for kpi, slot in sorted(kpis.items()):
            covs = [c for c in slot["coverage_min"] if c is not None]
            aggregate[level][kpi] = {
                "cloudbeds": sorted(slot["cloudbeds"]),
                "cases": sorted(slot["cases"]),
                "step_seconds": _median(slot["steps"]),
                "coverage_min": min(covs) if covs else None,
            }
    steps_by_level = {
        level: _median([v["step_seconds"] for v in kpis.values()])
        for level, kpis in aggregate.items()
    }
    return {
        "version": VERSION, "cases": list(cases),
        "per_case": per_case, "aggregate": aggregate,
        "median_step_seconds_by_level": steps_by_level,
    }


def format_catalog(catalog: dict, horizon_steps: int = 5) -> str:
    """Riepilogo leggibile. L'orizzonte H e' un CALCOLO, non una decisione."""
    lines = [f"Catalogo KPI {catalog['version']} - casi: {', '.join(catalog['cases'])}", ""]
    for level, kpis in catalog["aggregate"].items():
        both = [k for k, v in kpis.items() if len(v["cloudbeds"]) == 2]
        lines.append(f"Livello {level}: {len(kpis)} KPI, {len(both)} presenti in entrambi i cloudbed")
        for kpi, info in kpis.items():
            cov = info["coverage_min"]
            step = info["step_seconds"]
            lines.append(
                f"  {kpi:<55} cloudbed={'+'.join(c[-1] for c in info['cloudbeds'])} "
                f"passo={step if step is None else int(step)}s "
                f"copertura_min={'n/d' if cov is None else format(cov, '.2f')}"
            )
        lines.append("")
    lines.append("Passo mediano per livello e orizzonte globale H proposto:")
    for level, step in catalog["median_step_seconds_by_level"].items():
        horizon = None if step is None else int(step * horizon_steps)
        lines.append(f"  {level}: passo={step}s  ->  H = {horizon_steps} x passo = {horizon}s "
                     "(calcolo, da approvare)")
    return "\n".join(lines)


def write_catalog(out_dir: Path, catalog: dict, code_commit: str | None) -> Path:
    """Scrive il catalogo in modo create-only, con SHA-256 del contenuto."""
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = dict(catalog)
    payload["code_commit"] = code_commit
    body = json.dumps(payload, sort_keys=True, indent=1, ensure_ascii=False)
    payload["sha256_of_body_without_this_field"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    target = out_dir / "catalog_discovery.json"
    with open(target, "x", encoding="utf-8") as handle:  # "x": fallisce se esiste
        json.dump(payload, handle, sort_keys=True, indent=1, ensure_ascii=False)
    return target


def _git_head(repo: Path) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--drive-root", required=True, type=Path)
    parser.add_argument("--out-dir", default="data/rq2_k_catalog_v1")
    parser.add_argument("--repo-dir", type=Path, default=None)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    catalog = build_catalog(args.drive_root / "Market.zip",
                            args.drive_root / MANIFEST_RELATIVE)
    print(format_catalog(catalog))
    if not args.no_write:
        commit = _git_head(args.repo_dir) if args.repo_dir else None
        target = write_catalog(args.drive_root / args.out_dir, catalog, commit)
        print(f"\nScritto (create-only): {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
