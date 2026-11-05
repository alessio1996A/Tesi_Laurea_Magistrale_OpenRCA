"""Orchestratore Fase 1: avvia solo gli otto run Gemini 5+1, una alla volta.

Modalita' predefinita: preflight in sola lettura. Non crea piani ne' output.
Prima di qualunque API sono obbligatori: --execute, --confirm-api,
--approved-budget-usd e --max-new-runs. Non esiste retry automatico.
Il budget dichiarato NON e' un tetto tecnico imposto dal provider.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path

from evaluation import planner_budget_ablation as ablation

ARM = "5p1"
EXPECTED_TOTAL = 8
BLOCKING_STATUSES = frozenset({
    "CLAIM_PENDING_NO_AUTO_RETRY",
    "ORPHAN_OUTPUT_REVIEW",
    "REVIEW_INTEGRITY",
    "REVIEW_CORRUPT",
})


def preflight_5p1(data_dir: Path, repo_dir: Path) -> dict:
    """Mostra lo stato delle sole 8 run 5+1. Zero chiamate LLM."""
    overall = ablation.preflight(data_dir, repo_dir)
    rows = [r for r in overall["runs"] if r["arm"] == ARM]
    if (len(rows) != EXPECTED_TOTAL
            or len({r["case_id"] for r in rows}) != EXPECTED_TOTAL
            or len({r["run_id"] for r in rows}) != EXPECTED_TOTAL
            or any(r["order"] != 0 for r in rows)):
        raise ValueError("Piano non conforme: 5+1 deve precedere 4+2")
    counts = Counter(r["status"] for r in rows)
    return {
        "protocol": overall["protocol"],
        "git_commit": overall["git_commit"],
        "plan_sha256": overall["plan_sha256"],
        "arm": ARM,
        "model_provider": "google",
        "planned_runs": EXPECTED_TOTAL,
        "status_counts": dict(sorted(counts.items())),
        "runs": rows,
        "blocked": any(row["status"] in BLOCKING_STATUSES
                       or row["status"] not in ("ready", "complete")
                       for row in rows),
        "llm_called": False,
        "scoring_performed": False,
        "note": "La configurazione 4+2 NON viene eseguita da questo modulo.",
    }


def run_5p1_campaign(
    data_dir: Path,
    repo_dir: Path,
    *,
    confirm_api: bool = False,
    approved_budget_usd: float | None = None,
    max_new_runs: int | None = None,
    _run_one=None,
) -> dict:
    """Una run alla volta. Il piano deve essere gia' congelato su Drive.

    _run_one e' iniettato esclusivamente nei test fake, senza API.
    Le run completate sono saltate, quelle pendenti bloccano la campagna.
    """
    if (confirm_api is not True
            or type(max_new_runs) is not int
            or not 1 <= max_new_runs <= EXPECTED_TOTAL
            or type(approved_budget_usd) not in (int, float)
            or not math.isfinite(approved_budget_usd)
            or approved_budget_usd <= 0):
        raise PermissionError(
            "Sono richiesti --execute --confirm-api, un budget valido "
            "e --max-new-runs tra 1 e 8, dopo autorizzazione umana."
        )

    initial = preflight_5p1(data_dir, repo_dir)
    if initial["blocked"]:
        raise RuntimeError(
            "Campagna 5+1 bloccata: claim pendente/output ambiguo. "
            "Nessun retry automatico."
        )

    run_one = _run_one or ablation.run_exactly_one
    started = []
    for proposed in initial["runs"]:
        if len(started) >= max_new_runs:
            break
        # Rileggiamo sempre Drive e validiamo il piano immutabile.
        current = preflight_5p1(data_dir, repo_dir)
        if current["plan_sha256"] != initial["plan_sha256"]:
            raise RuntimeError("Hash del piano cambiato: STOP")
        if current["git_commit"] != initial["git_commit"]:
            raise RuntimeError("Commit cambiato durante la campagna: STOP")
        if current["blocked"]:
            raise RuntimeError(
                "Stato ambiguo dopo la run precedente: STOP senza retry."
            )
        current_row = next(r for r in current["runs"]
                           if r["run_id"] == proposed["run_id"])
        if current_row["status"] == "complete":
            continue
        if current_row["status"] != "ready":
            raise RuntimeError("Run non ready: STOP senza retry.")
        print(f"[{len(started)+1}/{max_new_runs}] "
              f"{current_row['case_id']} - {ARM}: avvio singola run")
        # run_exactly_one crea un claim prima di ogni possibile invoke;
        # dopo ogni run salva subito il JSON con modalita' create-only.
        outcome = run_one(
            data_dir, repo_dir, run_id=current_row["run_id"],
            confirm_api=True,
            approved_budget_usd=approved_budget_usd,
        )
        if outcome.get("integrity") != "complete":
            raise RuntimeError(
                "Run salvata ma da verificare: STOP, nessun retry."
            )
        # Verifica persistente dei file, non basta il return del runner.
        refreshed = preflight_5p1(data_dir, repo_dir)
        refreshed_row = next(r for r in refreshed["runs"]
                             if r["run_id"] == current_row["run_id"])
        if refreshed_row["status"] != "complete":
            raise RuntimeError(
                "Risultato non confermato su Drive: STOP senza retry."
            )
        started.append(current_row["run_id"])
        print(f"Salvata e verificata: {current_row['run_id']}")

    final = preflight_5p1(data_dir, repo_dir)
    return {
        "protocol": final["protocol"],
        "arm": ARM,
        "new_runs_this_invocation": len(started),
        "new_run_ids": started,
        "status_counts": final["status_counts"],
        "llm_called": bool(started),
        "scoring_performed": False,
        "note": "Il parametro budget autorizza la campagna, ma NON "
                "impone un hard cap dei costi lato provider.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--repo-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-api", action="store_true")
    parser.add_argument("--approved-budget-usd", type=float)
    parser.add_argument("--max-new-runs", type=int)
    args = parser.parse_args()
    if args.execute:
        result = run_5p1_campaign(
            args.data_dir, args.repo_dir,
            confirm_api=args.confirm_api,
            approved_budget_usd=args.approved_budget_usd,
            max_new_runs=args.max_new_runs,
        )
    else:
        if (args.confirm_api or args.approved_budget_usd is not None
                or args.max_new_runs is not None):
            parser.error(
                "Nessun flag API consentito senza --execute."
            )
        result = preflight_5p1(args.data_dir, args.repo_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False,
                     allow_nan=False))


if __name__ == "__main__":
    main()
