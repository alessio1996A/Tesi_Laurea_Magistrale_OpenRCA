"""Preview frozen paired cohort; explicitly opt in to ONE API-funded pair.

Default invocation performs NO telemetry reads, NO API calls and NO writes.

Preview:
  PYTHONPATH=src python src/evaluation/manual_paired_batch.py
Explicit single-pair execution (later, after approval):
  PYTHONPATH=src python src/evaluation/manual_paired_batch.py \\
    --execute-pair cloudbed-1_q063 --confirm-api

There is intentionally NO "execute all" or automatic retry command.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.paired_runner import (
    esegui_coppia,
    preflight_paired,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path,
        default=Path("/content/drive/MyDrive/Tesi_OpenRCA"),
    )
    parser.add_argument(
        "--repo-dir", type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument(
        "--execute-pair", type=str,
        default=None,
        help="Run exactly one already frozen pair (two model calls/arms).",
    )
    parser.add_argument(
        "--confirm-api", action="store_true",
        help="Explicitly authorize paid provider calls for --execute-pair.",
    )
    args = parser.parse_args()

    if args.confirm_api and args.execute_pair is None:
        parser.error("--confirm-api requires --execute-pair")
    if args.execute_pair is not None and not args.confirm_api:
        parser.error("--execute-pair requires --confirm-api")

    if args.execute_pair is not None:
        result = esegui_coppia(
            args.data_dir,
            repo_dir=args.repo_dir,
            case_id=args.execute_pair,
            confirm_api=True,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        preview = preflight_paired(
            args.data_dir,
            repo_dir=args.repo_dir,
        )
        print(json.dumps(preview, indent=2, ensure_ascii=False))
        print(
            "\nSOLO PREFLIGHT: nessun file scritto, "
            "nessun dato di telemetria letto, "
            "nessuna chiamata API."
        )


if __name__ == "__main__":
    main()
