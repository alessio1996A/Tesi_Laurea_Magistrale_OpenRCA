"""Run-only preflight for the GT-free A1 vs A1_VERIFY development cohort.

Default: DRY RUN. No API calls, no telemetry reads, no file writes.
To freeze the cohort, explicitly provide --freeze after reviewing output.
Usage (Colab):
  python src/evaluation/manual_preregister_dev.py --data-dir /content/drive/MyDrive/Tesi_OpenRCA
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.paired_cohort import (
    PROTOCOL,
    costruisci_piano_abbinato,
    save_plan_exclusive,
)

EXPECTED_COUNTS = {
    "development": 92,
    "evaluation": 23,
    "mixed_quarantine": 18,
    "ood_holdout": 15,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path,
        default=Path("/content/drive/MyDrive/Tesi_OpenRCA"),
    )
    parser.add_argument("--per-cloudbed", type=int, default=4)
    parser.add_argument(
        "--freeze", action="store_true",
        help="Create the immutable plan with exclusive file mode x.",
    )
    args = parser.parse_args()

    data_dir = args.data_dir
    plan = costruisci_piano_abbinato(
        data_dir / "data/processed/split_market_v1.csv",
        data_dir / "data/processed/benchmark_inputs_market.csv",
        per_cloudbed=args.per_cloudbed,
    )
    if plan["split_counts"] != EXPECTED_COUNTS:
        raise ValueError(
            "Split diverso dalla versione congelata (non creare piano): "
            f"atteso={EXPECTED_COUNTS}, ricevuto={plan['split_counts']}"
        )

    print(json.dumps(plan, indent=2, ensure_ascii=False))
    if args.freeze:
        target = (
            data_dir / "data/protocols"
            / f"{PROTOCOL}_cohort_v1.json"
        )
        save_plan_exclusive(plan, target)
        print(f"PIANO CONGELATO: {target}")
    else:
        print(
            "\nSOLO ANTEPRIMA: nessun file scritto, "
            "nessun LLM o tool eseguito."
        )


if __name__ == "__main__":
    main()
