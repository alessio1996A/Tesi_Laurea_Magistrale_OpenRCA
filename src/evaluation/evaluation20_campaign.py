"""Safe evaluation20 campaign runner (300 planned runs).

DEFAULT: read-only preview/preflight. --execute requires --confirm-api,
a positive approved budget, model selection, and an existing frozen plan.
No automatic retries. Claim created before possible paid invocation. Writes
to a NEW protocol-specific directory, never historical results. Does not
read scoring_points, query.csv, record.csv or ground truth and cannot
perform scoring. Usage incomplete / interrupted runs are NEVER retried
automatically. No billed calls during import or dry-run.

IMPORTANT: approved_budget_usd is an *authorization record*, NOT a provider
hard spending cap. Execute in explicitly approved small batches only.
"""
from __future__ import annotations

from collections import Counter
from importlib.metadata import PackageNotFoundError, version
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re

from evaluation import evaluation20_preregister as registry
from evaluation.experiment_config import ExperimentConfig

HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_RUN = re.compile(r"^[a-z0-9_-]+$")
PROTOCOL = registry.PROTOCOL
SCORING_FIELDS = {"groundtruth", "scoring_points", "score", "passed", "failed"}


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_new(path: Path, obj: dict) -> None:
    # Exclusive creation: never touch a pre-existing file.
    data = (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as fp:
        fp.write(data)


def paths(data_dir: Path, run_id: str) -> tuple[Path, Path, Path]:
    if not SAFE_RUN.fullmatch(run_id):
        raise ValueError("Unsafe run identifier")
    folder = (Path(data_dir) / "data/results/evaluation20" / PROTOCOL)
    return (
        folder / (run_id + ".claim.json"),
        folder / (run_id + ".json"),
        folder / (run_id + ".sha256.json"),
    )


def load_plan(data_dir: Path, repo_dir: Path) -> tuple[dict, str]:
    # This recomputes the 20-case selection from original GT-free metadata.
    # The branch/head/working tree must match the recorded commit.
    current_commit = registry.git_head_clean(repo_dir)
    candidate = registry.build_plan(
        registry.evaluation20_preflight(data_dir, target=20),
        commit=current_commit,
    )
    path = registry.destination(data_dir)
    if not path.exists():
        raise FileNotFoundError("Frozen EVALUATION20 plan missing; no API")
    stored = json.loads(path.read_text(encoding="utf-8"))
    if stored != candidate:
        raise ValueError("Frozen plan differs from code/selection; no API")
    return stored, sha(path)


def _result_issues(result: dict, claim: dict, run: dict,
                   plan: dict, plan_sha: str) -> list[str]:
    if not isinstance(result, dict):
        return ["not_dict"]
    p = result.get("evaluation20_provenance") or {}
    errors = []
    checks = {
        "case": result.get("case_id") == run["case_id"],
        "variant": result.get("variant") == run["variant"],
        "scheme": result.get("variant_scheme") == "current",
        "model": result.get("model") == run["model_name"],
        "provider": result.get("model_provider") == run["model_provider"],
        "max_rounds": result.get("max_tool_rounds") == 6,
        "output_contract": result.get("output_contract_mode") == "v2_enforce",
        "v2_audit": isinstance(result.get("output_contract_v2"), dict),
        "prompt_hash": result.get("system_prompt_sha256")
                       == claim.get("prompt_sha256_before_api"),
        "evidence_hash": result.get("evidence_sha256")
                         == claim.get("evidence_sha256_before_api"),
        "provenance_run": p.get("run_id") == run["run_id"],
        "provenance_commit": p.get("git_commit") == plan["git_commit"],
        "provenance_plan": p.get("plan_sha256") == plan_sha,
        "claim_run": claim.get("run_id") == run["run_id"],
        "claim_commit": claim.get("git_commit") == plan["git_commit"],
        "claim_plan": claim.get("plan_sha256") == plan_sha,
    }
    errors.extend(k for k, passed in checks.items() if not passed)
    if run["variant"] == "A0":
        if result.get("evidence_sha256") is not None:
            errors.append("unexpected_A0_evidence")
    elif not (isinstance(result.get("evidence_sha256"), str)
              and HEX64.fullmatch(result["evidence_sha256"])):
        errors.append("evidence_sha_missing")

    # Scorer data must not be copied into runner outputs.
    if SCORING_FIELDS & set(result):
        errors.append("forbidden_scoring_keys")

    m = result.get("metrics")
    if not isinstance(m, dict):
        return errors + ["metrics_missing"]
    required_integers = ("input_tokens", "output_tokens", "total_tokens",
                         "llm_calls", "tool_calls", "tool_rounds")
    if any(type(m.get(key)) is not int or m[key] < 0
           for key in required_integers):
        errors.append("invalid_metrics_integers")
    else:
        if m["input_tokens"] + m["output_tokens"] != m["total_tokens"]:
            errors.append("token_sum_mismatch")
        if m["tool_rounds"] > plan["max_tool_rounds"]:
            errors.append("round_budget_exceeded")
        if m["llm_calls"] == 0 and result.get("error") is None:
            errors.append("no_llm_calls")
    if type(m.get("token_usage_complete")) is not bool:
        errors.append("missing_usage_flag")
    for key in ("duration_seconds", "preprocessing_seconds",
                "end_to_end_seconds"):
        if type(m.get(key)) not in (int, float) or m[key] < 0:
            errors.append("invalid_" + key)
    if all(type(m.get(k)) in (int, float) for k in (
            "duration_seconds", "end_to_end_seconds")):
        if m["end_to_end_seconds"] + 0.01 < m["duration_seconds"]:
            errors.append("bad_timing_order")
    if run["variant"] in ("A1_8R_Planning", "A1_PAVE"):
        if (result.get("max_verification_checks") != 2
                or result.get("exploration_round_limit") != 4
                or (result.get("verification") or {}).get("causa_verificata")
                is not False):
            errors.append("planner_contract")
        for key, mx in (("exploration_tool_rounds", 4),
                        ("verification_tool_rounds", 2)):
            if type(m.get(key)) is not int or not 0 <= m[key] <= mx:
                errors.append("invalid_" + key)
        if (type(m.get("exploration_tool_rounds")) is int
                and type(m.get("verification_tool_rounds")) is int
                and type(m.get("tool_rounds")) is int
                and m["tool_rounds"] != m["exploration_tool_rounds"]
                + m["verification_tool_rounds"]):
            errors.append("planner_round_sum")
    if not isinstance(result.get("raw_response"), (str, type(None))):
        errors.append("invalid_raw_type")
    return errors


def _run_state(data_dir: Path, run: dict, plan: dict,
               plan_sha: str) -> tuple[str, list[str]]:
    claim, output, sidecar = paths(data_dir, run["run_id"])
    available = (claim.exists(), output.exists(), sidecar.exists())
    if available == (False, False, False):
        return "ready", []
    if available == (True, False, False):
        return "CLAIM_PENDING_NO_AUTO_RETRY", []
    if available == (True, True, False):
        return "REVIEW_MISSING_HASH_NO_RETRY", []
    if available != (True, True, True):
        return "ORPHAN_REVIEW_NO_RETRY", []
    try:
        c = json.loads(claim.read_text(encoding="utf-8"))
        r = json.loads(output.read_text(encoding="utf-8"))
        h = json.loads(sidecar.read_text(encoding="utf-8"))
        ok = (h.get("run_id") == run["run_id"]
              and h.get("plan_sha256") == plan_sha
              and h.get("result_sha256") == sha(output))
        issues = _result_issues(r, c, run, plan, plan_sha)
        if not ok:
            issues.append("sidecar_sha_mismatch")
        if issues:
            return "REVIEW_INTEGRITY_NO_RETRY", issues
        if r.get("error") is not None:
            return "MODEL_ERROR_REVIEW_NO_RETRY", []
        if not isinstance(r.get("raw_response"), str) or not r["raw_response"].strip():
            return "REVIEW_EMPTY_RAW_NO_RETRY", []
        if not r["metrics"]["token_usage_complete"]:
            return "USAGE_INCOMPLETE_REVIEW_NO_RETRY", []
        return "complete", []
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return "REVIEW_CORRUPT_NO_RETRY", [type(exc).__name__]


def preflight(data_dir: Path, repo_dir: Path, *, _plan=None,
              _plan_sha=None) -> dict:
    """No calls or writes; injectable frozen plan is reserved for fake tests."""
    if _plan is None:
        plan, plan_sha = load_plan(data_dir, repo_dir)
    else:
        plan, plan_sha = _plan, _plan_sha
    if not (isinstance(plan, dict) and isinstance(plan_sha, str)
            and HEX64.fullmatch(plan_sha)):
        raise ValueError("Plan/sha not valid")
    statuses = []
    for run in plan["runs"]:
        status, issues = _run_state(data_dir, run, plan, plan_sha)
        statuses.append({**run, "status": status, "issues": issues})
    counts = Counter(row["status"] for row in statuses)
    return {
        "protocol": PROTOCOL,
        "git_commit": plan["git_commit"],
        "plan_sha256": plan_sha,
        "run_count": len(statuses),
        "counts": dict(sorted(counts.items())),
        "models": {
            model: dict(sorted(Counter(
                x["status"] for x in statuses if x["model_key"] == model
            ).items()))
            for model in plan["model_configs"]
        },
        "runs": statuses,
        "api_calls": 0, "scoring_performed": False,
    }


def _prompt_sha(variant: str, task: str, instruction: str) -> str:
    from agent.prompts import get_system_prompt
    from output.v2_task_contract import task_output_instruction
    prompt = get_system_prompt(variant) + task_output_instruction(
        task_index=task, instruction=instruction
    )
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _provider_versions(provider: str) -> dict:
    names = ["langgraph", "langchain-core"]
    names.extend(["langchain-anthropic", "anthropic"] if provider == "anthropic"
                 else ["langchain-google-genai", "google-genai"])
    found = {}
    for name in names:
        try:
            found[name] = version(name)
        except PackageNotFoundError:
            found[name] = "not-installed"
    return found


def _create_model(run: dict):
    """Explicitly disable provider-level retries for both API backends."""
    if run["model_provider"] == "anthropic":
        from agent.model_factory import crea_modello
        return crea_modello("anthropic", run["model_name"])
    if run["model_provider"] == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=run["model_name"], max_retries=0)
    raise ValueError("Unknown provider")


def _check_api_permission(confirm_api, approved_budget_usd):
    if (confirm_api is not True
            or type(approved_budget_usd) not in (int, float)
            or not math.isfinite(approved_budget_usd)
            or approved_budget_usd <= 0):
        raise PermissionError(
            "No API without explicit confirmation and positive USD budget"
        )


def run_one(data_dir: Path, repo_dir: Path, *, run_id: str,
            confirm_api=False, approved_budget_usd=None,
            _runner=None, _prepared=None, _model=None,
            _plan=None, _plan_sha=None) -> dict:
    """Exactly one attempt. _runner/_prepared/_plan are for offline tests."""
    _check_api_permission(confirm_api, approved_budget_usd)
    state = preflight(data_dir, repo_dir, _plan=_plan, _plan_sha=_plan_sha)
    found = [r for r in state["runs"] if r["run_id"] == run_id]
    if len(found) != 1 or found[0]["status"] != "ready":
        raise FileExistsError("Run is not ready; do NOT retry")
    run = found[0]
    plan, plan_sha = ((_plan, _plan_sha) if _plan is not None
                      else load_plan(data_dir, repo_dir))
    case = next(c for c in plan["cases"] if c["case_id"] == run["case_id"])
    cfg = ExperimentConfig(
        case_id=run["case_id"], variant=run["variant"],
        variant_scheme="current", model_name=run["model_name"],
        model_provider=run["model_provider"], repo_dir=Path(repo_dir),
        data_dir=Path(data_dir), max_tool_rounds=plan["max_tool_rounds"],
        max_verification_checks=plan["max_verification_checks"],
        recursion_limit=plan["recursion_limit"],
        output_contract_mode=plan["output_contract_mode"],
    )

    # Validate case and prepare deterministic evidence before claim/invoke.
    if _prepared is not None:
        loaded, evidence_sha = _prepared(cfg, case)
    else:
        from evaluation.experiment_runner import (
            carica_caso, prepara_esperimento
        )
        loaded = carica_caso(cfg)
        prepared = prepara_esperimento(cfg)
        if prepared["caso"] != loaded:
            raise ValueError("Prepared case differs from GT-free manifest")
        evidence_sha = prepared.get("evidence_sha256")

    for key in ("case_id", "cloudbed", "task_index",
                "start_unix", "end_unix"):
        if loaded[key] != case[key]:
            raise ValueError("Case does not match preregistered metadata: " + key)
    if run["variant"] == "A0":
        if evidence_sha is not None:
            raise ValueError("A0 must not have evidence")
    elif not (isinstance(evidence_sha, str) and HEX64.fullmatch(evidence_sha)):
        raise ValueError("Missing evidence SHA")
    prompt_sha = _prompt_sha(
        run["variant"], case["task_index"], loaded["instruction"]
    )

    # Build model only after offline case verification; no invocation yet.
    model = _model
    if _runner is None and model is None:
        key = ("ANTHROPIC_API_KEY" if run["model_provider"] == "anthropic"
               else "GOOGLE_API_KEY")
        if not os.getenv(key):
            raise RuntimeError("Missing provider API secret: " + key)
        model = _create_model(run)
        if not (hasattr(model, "bind_tools") and hasattr(model, "invoke")):
            raise RuntimeError("Provider model incompatible with runner")

    # Check state again to avoid accidental double calls.
    latest = preflight(data_dir, repo_dir, _plan=_plan, _plan_sha=_plan_sha)
    status = next(r["status"] for r in latest["runs"]
                  if r["run_id"] == run_id)
    if status != "ready":
        raise FileExistsError("Run not ready after preparation: stop")

    claim, output, checksum = paths(data_dir, run_id)
    _write_new(claim, {
        "run_id": run_id, "case_id": run["case_id"],
        "variant": run["variant"], "model_key": run["model_key"],
        "model_name": run["model_name"], "model_provider": run["model_provider"],
        "plan_sha256": plan_sha, "git_commit": plan["git_commit"],
        "approved_budget_usd": approved_budget_usd,
        "prompt_sha256_before_api": prompt_sha,
        "evidence_sha256_before_api": evidence_sha,
        "status": "CLAIM_STARTED_NO_AUTO_RETRY",
    })
    try:
        if _runner is None:
            from evaluation.experiment_runner import run_experiment
            result = run_experiment(cfg, llm=model, verbose=False, salva=False)
        else:
            result = _runner(cfg)
        if not isinstance(result, dict):
            raise RuntimeError("Runner did not return a dict")
        result = dict(result)
        result["evaluation20_provenance"] = {
            "run_id": run_id,
            "model_key": run["model_key"],
            "model_name": run["model_name"],
            "provider": run["model_provider"],
            "plan_sha256": plan_sha,
            "git_commit": plan["git_commit"],
            "provider_max_retries": 0,
            "provider_versions": ({"execution": "offline_fake"}
                                  if _runner is not None
                                  else _provider_versions(run["model_provider"])),
        }
        _write_new(output, result)
        _write_new(checksum, {
            "run_id": run_id, "plan_sha256": plan_sha,
            "result_sha256": sha(output),
        })
    except BaseException:
        # Includes Ctrl-C or crash: any paid invocation may have happened.
        # Leave claim forever; never retry automatically.
        raise

    latest = preflight(data_dir, repo_dir, _plan=_plan, _plan_sha=_plan_sha)
    status = next(r["status"] for r in latest["runs"]
                  if r["run_id"] == run_id)
    return {
        "run_id": run_id, "status": status,
        "output_path": str(output),
        "api_retry_performed": False,
        "scoring_performed": False,
    }


def run_batch(data_dir: Path, repo_dir: Path, *, model_key: str,
              max_new_runs: int = 1, confirm_api=False,
              approved_budget_usd=None) -> dict:
    """Never invoke more than 5 *new* runs in an approved batch."""
    _check_api_permission(confirm_api, approved_budget_usd)
    if model_key not in registry.MODELS_CONFIG:
        raise ValueError("Unknown model")
    if type(max_new_runs) is not int or not 1 <= max_new_runs <= 5:
        raise ValueError("max_new_runs must be 1..5")
    initial = preflight(data_dir, repo_dir)
    pending = [r for r in initial["runs"] if r["model_key"] == model_key]
    bad = [r for r in pending if r["status"] not in ("ready", "complete")]
    if bad:
        raise RuntimeError(
            "Ambiguous or problematic run; stop without retry: " +
            ", ".join(x["run_id"] for x in bad[:3])
        )
    done = []
    for r in pending:
        if len(done) >= max_new_runs:
            break
        if r["status"] == "complete":
            continue
        latest = preflight(data_dir, repo_dir)
        if latest["plan_sha256"] != initial["plan_sha256"]:
            raise RuntimeError("Plan changed during batch")
        match = next(x for x in latest["runs"] if x["run_id"] == r["run_id"])
        if match["status"] != "ready":
            raise RuntimeError("Ambiguous attempt; stop without retry")
        answer = run_one(
            data_dir, repo_dir, run_id=r["run_id"],
            confirm_api=True, approved_budget_usd=approved_budget_usd,
        )
        if answer["status"] != "complete":
            raise RuntimeError(
                "Run saved but requires review: " + answer["status"]
            )
        done.append(r["run_id"])
    return {
        "model": model_key,
        "new_runs": done, "new_run_count": len(done),
        "counts": preflight(data_dir, repo_dir)["models"][model_key],
        "approved_budget_is_not_provider_hard_cap": True,
        "scoring_performed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--repo-dir", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--model", choices=list(registry.MODELS_CONFIG))
    parser.add_argument("--max-new-runs", type=int, default=1)
    parser.add_argument("--approved-budget-usd", type=float)
    parser.add_argument("--confirm-api", action="store_true")
    args = parser.parse_args()
    if args.execute:
        if args.model is None:
            parser.error("--execute requires --model")
        answer = run_batch(
            args.data_dir, args.repo_dir, model_key=args.model,
            max_new_runs=args.max_new_runs,
            confirm_api=args.confirm_api,
            approved_budget_usd=args.approved_budget_usd,
        )
    else:
        if (args.model is not None or args.confirm_api
                or args.approved_budget_usd is not None
                or args.max_new_runs != 1):
            parser.error("Read-only preflight does not accept API flags")
        if registry.destination(args.data_dir).exists():
            answer = preflight(args.data_dir, args.repo_dir)
            answer = {k: v for k, v in answer.items() if k != "runs"}
        else:
            answer = {
                "protocol": PROTOCOL,
                "status": "PLAN_NOT_FROZEN",
                "planned_cases": 20, "planned_runs": 300,
                "api_calls": 0, "written": False,
                "scoring_performed": False,
            }
    print(json.dumps(answer, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
