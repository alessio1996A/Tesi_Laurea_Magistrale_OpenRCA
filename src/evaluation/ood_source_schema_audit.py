"""Fase 2: inventario di SCHEMA delle sorgenti OpenRCA Market (solo header).

Non legge i record o le cause root, non attribuisce classi e non salva file.
Distingue i CSV a root Drive (di provenienza non attestata) dai membri ZIP
effettivamente collocati nei due cloudbed; non estrae telemetria.
Nessuna chiamata LLM e nessun esperimento.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile


TARGET_FILES = frozenset(("query.csv", "record.csv"))


def _headers_from_stream(stream) -> list[str]:
    """Elabora la prima riga CSV soltanto, senza iterare sulle istanze."""
    header = next(csv.reader(io.TextIOWrapper(
        stream, encoding="utf-8-sig", newline=""
    )), None)
    if not header or len(set(header)) != len(header):
        raise ValueError("Intestazione CSV assente o con colonne duplicate")
    return header


def inspect_schema(data_dir: Path) -> dict:
    """Restituisce soltanto path, dimensioni, intestazioni e statistiche ZIP."""
    root = Path(data_dir)
    archive = root / "Market.zip"
    if not archive.is_file():
        raise FileNotFoundError(f"Archivio Market.zip non trovato: {archive}")
    external = []
    for name in sorted(TARGET_FILES):
        p = root / name
        if p.is_file():
            with p.open("rb") as f:
                headers = _headers_from_stream(f)
            external.append({
                "file": name,
                "relative_location": name,
                "size_bytes": p.stat().st_size,
                "columns": headers,
                "provenance": "root_drive_unattributed_to_cloudbed",
            })

    members = []
    with ZipFile(archive, "r", allowZip64=True) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            if PurePosixPath(info.filename).name.lower() not in TARGET_FILES:
                continue
            with z.open(info, "r") as stream:
                headers = _headers_from_stream(stream)
            members.append({
                "archive_member": info.filename,
                "uncompressed_bytes": info.file_size,
                "columns": headers,
                "provenance": "Market.zip",
            })

    members.sort(key=lambda x: x["archive_member"])
    return {
        "audit": "ood_source_schema_only_v1",
        "archive_name": archive.name,
        "archive_bytes": archive.stat().st_size,
        "root_csv_headers": external,
        "archive_csv_headers": members,
        "total_archive_csv_matches": len(members),
        "read_records": False,
        "read_ground_truth_values": False,
        "read_telemetry": False,
        "read_prediction": False,
        "model_api_calls": 0,
        "files_written": False,
        "warnings": [
            "Gli schemi NON associano ancora una classe di guasto a un incidente.",
            "I CSV alla root Drive non sono attribuiti a cloudbed senza verificarne la provenienza.",
            "Nessuna query OOD è stata sbloccata per inferenza, discovery o test.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect_schema(args.data_dir), indent=2,
                     ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
