"""Audit GT-free, fase A/1: inventario degli SCHEMI di Market.zip.

- Sola lettura: nessuna scrittura sul dataset.
- Non apre record.csv, query.csv, scoring o file fuori whitelist.
- Legge la sola prima riga (header) dei CSV di telemetria consentiti.
- Non legge valori, KPI, incidenti o etichette; non produce diagnosi.
- Non effettua chiamate API o richieste a LLM.

Esecuzione dalla radice del repository:
    python src/evaluation/network_schema_audit.py "/path/Market.zip"

ATTENZIONE: questa e' una ricognizione di schema, NON un'analisi dei dati
di casi development. La successiva analisi di KPI/valori richiedera' la
selezione di finestre development libere e la protezione dei holdout.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path


# Whitelist di percorsi completi. I file di ground truth non sono ammessi.
ALLOWED = re.compile(
    r"^(?:[^/]+/)*Market/(?P<cloudbed>cloudbed-[12])/telemetry/"
    r"(?P<day>\d{4}_\d{2}_\d{2})/"
    r"(?P<source>"
    r"metric/metric_(?:container|node|service|mesh|runtime)\.csv"
    r"|trace/trace_span\.csv"
    r"|log/log_(?:service|proxy)\.csv"
    r")$"
)
SOURCES = (
    "metric/metric_container.csv",
    "metric/metric_node.csv",
    "metric/metric_service.csv",
    "metric/metric_mesh.csv",
    "metric/metric_runtime.csv",
    "trace/trace_span.csv",
    "log/log_service.csv",
    "log/log_proxy.csv",
)


def inspect_schema(zip_path: str | Path) -> dict:
    """Restituisce schemi e conteggi, senza leggere le righe dei CSV."""
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise FileNotFoundError(f"ZIP non trovato: {zip_path}")

    schemas: dict[tuple[str, str], dict[tuple[str, ...], list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    days: dict[tuple[str, str], set[str]] = defaultdict(set)
    member_count = 0
    telemetry_count = 0

    with zipfile.ZipFile(zip_path, "r") as archive:
        for info in archive.infolist():
            member_count += 1
            if info.is_dir():
                continue
            match = ALLOWED.fullmatch(info.filename)
            if match is None:
                continue  # Nessuna apertura di file fuori whitelist.

            # Limite esplicito di lettura: solo 64 KiB della prima riga.
            with archive.open(info, "r") as raw:
                header_line = raw.readline(65537)
            if len(header_line) > 65536 or b"\n" not in header_line:
                raise ValueError(f"Header non valido o >64 KiB: {info.filename}")
            try:
                decoded = header_line.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Header non UTF-8: {info.filename}") from exc
            columns = tuple(next(csv.reader(io.StringIO(decoded))))
            if not columns or any(not col.strip() for col in columns):
                raise ValueError(f"Header con colonne vuote: {info.filename}")

            key = (match["cloudbed"], match["source"])
            schemas[key][columns].append(info.filename)
            days[key].add(match["day"])
            telemetry_count += 1

    rows = []
    for cloudbed in ("cloudbed-1", "cloudbed-2"):
        for source in SOURCES:
            key = (cloudbed, source)
            variants = schemas.get(key, {})
            rows.append({
                "cloudbed": cloudbed,
                "source": source,
                "files_found": sum(len(paths) for paths in variants.values()),
                "days_found": len(days.get(key, set())),
                "schema_variants": [
                    {
                        "columns": list(columns),
                        "files": len(paths),
                        "example_path": min(paths),
                    }
                    for columns, paths in sorted(variants.items())
                ],
                "status": "observed_header_only" if variants else "no_file_matched",
            })

    return {
        "audit": "openrca_market_network_schema_gtfree_step1",
        "read_mode": "zip_member_names_and_allowed_csv_headers_only",
        "ground_truth_read": False,
        "kpi_values_read": False,
        "gemini_calls": 0,
        "archive_file_name": zip_path.name,
        "archive_size_bytes": zip_path.stat().st_size,
        "zip_member_count": member_count,
        "allowed_telemetry_files_scanned": telemetry_count,
        "sources": rows,
        "note": (
            "Uno schema osservato non dimostra che un segnale R03/R04/R05 "
            "esista. Nessuna finestra di casi e' stata esaminata."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("market_zip", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect_schema(args.market_zip), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
