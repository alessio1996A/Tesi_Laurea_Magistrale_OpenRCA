"""Preregistrazione create-only delle 300 run EVALUATION20, senza API.

Default: preview offline GT-free. --write: scrive il piano una volta sola
su Drive; non modifica, completa o sovrascrive piani preesistenti.
NON apre query.csv/record.csv/Market.zip, scoring, predizioni o telemetria.

Esempio:
 PYTHONPATH=src python -m evaluation.evaluation20_preregister \
   --data-dir /content/drive/MyDrive/Tesi_OpenRCA \
   --repo-dir /content/Tesi_OpenRCA_Evaluation20

Dopo verifica: aggiungere --write per il freeze create-only.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

from evaluation.evaluation20_preflight import (
    evaluation20_preflight, MODELS, VARIANTS, SEED,
    SPLIT_SHA256, MANIFEST_SHA256, V3_PLAN_SHA,
)

PROTOCOL = "openrca_harness_evaluation20_cross_model_v1"
BRANCH = "feature/evaluation20-gtfree-preflight-2026-11-06"
EXPECTED_IDS = (
    "cloudbed-1_q000", "cloudbed-1_q003", "cloudbed-1_q006",
    "cloudbed-1_q012", "cloudbed-1_q015", "cloudbed-1_q019",
    "cloudbed-1_q023", "cloudbed-1_q026", "cloudbed-1_q058",
    "cloudbed-1_q062",
    "cloudbed-2_q028", "cloudbed-2_q031", "cloudbed-2_q036",
    "cloudbed-2_q039", "cloudbed-2_q044", "cloudbed-2_q047",
    "cloudbed-2_q054", "cloudbed-2_q064", "cloudbed-2_q069",
    "cloudbed-2_q074",
)
MODELS_CONFIG = {
    "gemini": {"provider": "google", "model_name": "gemini-3.5-flash-lite"},
    "sonnet": {"provider": "anthropic", "model_name": "claude-sonnet-5-5"},
    "haiku": {"provider": "anthropic", "model_name": "claude-haiku-5-5"},
}
HEX40 = re.compile(r"^[0-9a-f]{40}$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def destination(data_dir: Path) -> Path:
    return (Path(data_dir) / "data/protocols/evaluation20" /
            (PROTOCOL + "_plan_v1.json"))


def git_head_clean(repo_dir: Path) -> str:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repo_dir), *args],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    if git("branch", "--show-current") != BRANCH:
        raise ValueError("STOP: branch sbagliato; nessuna scrittura")
    if git("status", "--porcelain"):
        raise ValueError("STOP: working tree non pulito")
    commit = git("rev-parse", "HEAD")
    if not HEX40.fullmatch(commit):
        raise ValueError("STOP: commit non valido")
    return commit


def build_plan(audit: dict, *, commit: str) -> dict:
    if not isinstance(audit, dict):
        raise ValueError("Audit non valido")
    if not HEX40.fullmatch(commit):
        raise ValueError("Commit Git non valido")
    if audit.get("status") != "PROPOSED_GT_FREE_NOT_FROZEN_NOT_EXECUTED":
        raise ValueError("STOP: audit non ha trovato i venti casi")
    if (audit.get("target_new_cases") != 20
            or audit.get("evaluation_rows_checked") != 23
            or audit.get("strict_candidate_count") != 23
            or audit.get("split_sha256") != SPLIT_SHA256
            or audit.get("manifest_sha256") != MANIFEST_SHA256
            or audit.get("development_v3_plan_sha256") != V3_PLAN_SHA
            or audit.get("selection_seed") != SEED
            or audit.get("read_ground_truth") is not False
            or audit.get("read_query_csv") is not False
            or audit.get("read_record_csv") is not False
            or audit.get("read_telemetry") is not False
            or audit.get("read_predictions") is not False
            or audit.get("scoring_performed") is not False
            or audit.get("model_api_calls") != 0
            or audit.get("files_written") is not False):
        raise ValueError("STOP: audit non conforme ai prerequisiti")
    selected = audit.get("proposed_cases")
    if not isinstance(selected, list) or len(selected) != 20:
        raise ValueError("STOP: numero casi non conforme")
    if tuple(r.get("case_id") for r in selected) != EXPECTED_IDS:
        raise ValueError("STOP: selezione diversa dai 20 ID verificati")
    if Counter(r["cloudbed"] for r in selected) != {
        "cloudbed-1": 10, "cloudbed-2": 10,
    }:
        raise ValueError("STOP: coorte non bilanciata")
    if {r["task_index"] for r in selected} != {
        "task_1", "task_2", "task_3", "task_4",
        "task_5", "task_6", "task_7",
    }:
        raise ValueError("STOP: task non coperti")
    if any(
        not any(r["cloudbed"] == cb and r["requested_fault_count"] >= 2
                for r in selected)
        for cb in ("cloudbed-1", "cloudbed-2")
    ):
        raise ValueError("STOP: mancano casi multiguasto")
    for r in selected:
        if (type(r.get("start_unix")) is not int
                or type(r.get("end_unix")) is not int
                or r["end_unix"] - r["start_unix"] != 1800):
            raise ValueError("STOP: finestre non valide")
    if tuple(MODELS) != tuple(MODELS_CONFIG) or len(VARIANTS) != 5:
        raise ValueError("Modelli/varianti inattesi")

    cases = []
    ordered_runs = []
    for i, row in enumerate(selected):
        # Rotazione deterministica del primo provider per caso e della
        # prima variante per provider; nessuna funzione dei risultati.
        model_order = list(MODELS[i % len(MODELS):] + MODELS[:i % len(MODELS)])
        run_ids = []
        for j, model in enumerate(model_order):
            offset = (i + j) % len(VARIANTS)
            variant_order = list(
                VARIANTS[offset:] + VARIANTS[:offset]
            )
            for variant in variant_order:
                run_id = f"{PROTOCOL}__{model}__{row['case_id']}__{variant.lower()}__r01"
                run_ids.append(run_id)
                ordered_runs.append({
                    "run_id": run_id,
                    "case_id": row["case_id"],
                    "model_key": model,
                    "model_provider": MODELS_CONFIG[model]["provider"],
                    "model_name": MODELS_CONFIG[model]["model_name"],
                    "variant": variant,
                    "order_index": len(ordered_runs),
                })
        cases.append({**row, "ordered_run_ids": run_ids})
    ids = [r["run_id"] for r in ordered_runs]
    if len(ids) != 300 or len(set(ids)) != 300:
        raise ValueError("300 run uniche non generate")
    if any(len(c["ordered_run_ids"]) != 15 for c in cases):
        raise ValueError("15 combinazioni mancanti per caso")
    return {
        "protocol": PROTOCOL,
        "status": "PREREGISTERED_NOT_EXECUTED",
        "selection_origin": "evaluation20_preflight_v1",
        "selection_seed": SEED,
        "git_commit": commit,
        "split_sha256": SPLIT_SHA256,
        "manifest_sha256": MANIFEST_SHA256,
        "development_v3_plan_sha256": V3_PLAN_SHA,
        "candidate_evaluation_count": 23,
        "case_count": 20,
        "run_count": 300,
        "replicas_per_combination": 1,
        "model_configs": MODELS_CONFIG,
        "variants": list(VARIANTS),
        "cases": cases,
        "runs": ordered_runs,
        "execution_order_policy": "rotate_model_by_case_and_variant_by_case_model",
        "output_contract_mode": "v2_enforce",
        "variant_scheme": "current",
        "max_tool_rounds": 6,
        "max_verification_checks": 2,
        "recursion_limit": 30,
        "timestamp_zone": "Asia/Shanghai",
        "telemetry_window": "[start_unix,end_unix)",
        "official_scorer_commit": "2a481ae63cb045c3eadbeca9eddaa10ec1151979",
        "primary_comparison": "paired_official_raw_score_A1_minus_A0_within_each_model",
        "other_comparisons": [
            "A1_8R_minus_A1", "A1_8R_Planning_minus_A1_8R",
            "A1_PAVE_minus_A1_8R_Planning",
        ],
        "metrics_required": [
            "input_tokens", "output_tokens", "total_tokens",
            "token_usage_complete", "llm_calls", "tool_calls",
            "tool_rounds", "duration_seconds",
            "preprocessing_seconds", "end_to_end_seconds",
        ],
        "required_pre_api_checks": [
            "offline_fake_llm_tests",
            "token_usage_complete_for_all_variants",
            "no_hidden_retry",
            "provider_version_and_model_id_check",
            "cost_estimate_and_explicit_budget_approval",
            "create_only_claim_result_and_sha_per_run",
        ],
        "read_ground_truth": False,
        "read_predictions": False,
        "scoring_performed": False,
        "api_calls_performed": False,
        "authorization_granted": False,
        "notes": [
            "I 120 run development rimangono distinti e congelati.",
            "Questo piano non autorizza chiamate API né afferma che il runner per 300 run esista.",
            "Non selezionare in base a scoring_points, query.csv, record.csv o score.",
            "Finestre disgiunte non garantiscono indipendenza statistica.",
            "Le metriche di token devono essere collaudate su tutte le varianti.",
        ],
    }


def render(plan: dict) -> bytes:
    return (json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True,
                       allow_nan=False) + "\n").encode("utf-8")


def create_only(path: Path, data: bytes) -> str:
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"STOP: protocollo già presente: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
    if path.read_bytes() != data:
        raise RuntimeError("Scrittura non verificabile")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--repo-dir", required=True, type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    commit = git_head_clean(args.repo_dir)
    proposal = evaluation20_preflight(args.data_dir, target=20)
    plan = build_plan(proposal, commit=commit)
    payload = render(plan)
    path = destination(args.data_dir)
    result = {
        "status": plan["status"],
        "protocol": PROTOCOL,
        "run_count": plan["run_count"],
        "case_count": plan["case_count"],
        "models": list(MODELS),
        "variants": list(VARIANTS),
        "plan_sha256": hashlib.sha256(payload).hexdigest(),
        "destination": str(path),
        "git_commit": commit,
        "api_calls": 0,
        "scoring_performed": False,
    }
    if args.write:
        result["written_sha256"] = create_only(path, payload)
        result["written"] = True
    else:
        result["written"] = False
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
