"""Freeze read-only validation of all 40 Claude runs for ONE model.

It never reads query.csv, record.csv, scores or ground truth.
--write creates a model-specific JSON manifest once; source outputs
and their sidecar hashes remain immutable.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation import claude_development_campaign as campaign


def freeze_path(data_dir: Path, model_key: str) -> Path:
    if model_key not in campaign.MODELS:
        raise ValueError("Model key non valido")
    return (Path(data_dir) / "data/protocols/v2" /
            f"{campaign.PROTOCOL}_{model_key}_results_freeze_v1.json")


def build_freeze(data_dir: Path, repo_dir: Path, model_key: str):
    if model_key not in campaign.MODELS:
        raise ValueError("Model key non valido")
    state = campaign.preflight(data_dir, repo_dir)
    plan, plan_sha = campaign.load_plan(data_dir, repo_dir)
    rows = [r for r in state["runs"] if r["model_key"] == model_key]
    if len(rows) != 40:
        raise ValueError("Non ci sono 40 run pianificate per il modello")
    allowed = {"complete", "MODEL_ERROR_REVIEW_NO_RETRY"}
    if any(r["status"] not in allowed for r in rows):
        raise ValueError("Freeze bloccato: 40 output mancanti o da revisionare")
    output_files = []
    for r in rows:
        claim, output, sidecar = campaign._paths(data_dir, r["run_id"])
        result = json.loads(output.read_text(encoding="utf-8"))
        output_files.append({
            "run_id": r["run_id"],
            "case_id": r["case_id"],
            "variant": r["variant"],
            "status": r["status"],
            "result_sha256": campaign._sha(output),
            "claim_sha256": campaign._sha(claim),
            "sidecar_sha256": campaign._sha(sidecar),
            "json_status": result.get("json_status"),
            "raw_response_present": isinstance(result.get("raw_response"), str)
            and bool(result["raw_response"].strip()),
            "token_usage_complete": result.get("metrics", {}).get(
                "token_usage_complete") is True,
        })
    return {
        "freeze": "claude_development_model_results_freeze_v1",
        "protocol": campaign.PROTOCOL,
        "model_key": model_key,
        "model_name": campaign.MODELS[model_key],
        "plan_sha256": plan_sha,
        "git_commit": plan["git_commit"],
        "case_count": 8,
        "variant_count": 5,
        "run_count": 40,
        "complete": sum(r["status"] == "complete" for r in rows),
        "model_errors": sum(r["status"] == "MODEL_ERROR_REVIEW_NO_RETRY"
                            for r in rows),
        "files": output_files,
        "scoring_performed": False,
        "read_ground_truth": False,
        "read_query_csv": False,
        "notes": (
            "Solo freeze, non scorer. Predizioni e outputs rimangono immutati. "
            "Score soltanto in processo offline separato."
        ),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--repo-dir", type=Path, required=True)
    p.add_argument("--model", choices=list(campaign.MODELS), required=True)
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    frozen = build_freeze(args.data_dir, args.repo_dir, args.model)
    if args.write:
        path = freeze_path(args.data_dir, args.model)
        campaign._write_only_new(path, frozen)
        result = {"written": str(path), "sha256": campaign._sha(path),
                  "model": args.model, "runs": 40,
                  "scoring_performed": False}
    else:
        result = frozen
    print(json.dumps(result, indent=2, ensure_ascii=False,
                     allow_nan=False))


if __name__ == "__main__":
    main()
