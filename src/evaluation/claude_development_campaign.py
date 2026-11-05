"""Claude V2 recovery campaign: 80 runs (40 Sonnet + 40 Haiku), GT-free.

DEFAULT: offline preview/preflight. --write-plan: create-only plan.
--execute: exactly one model and at most N *new* runs (N <= 8),
requires --confirm-api and --approved-budget-usd.
No retries or automatic rerun of attempted IDs. Every attempt persists
a claim before API; output and SHA-256 are written create-only.
This program NEVER reads query.csv/record.csv, scores or previous V3 outputs.
Approved budget is NOT an enforced provider spending cap.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess

from agent.variant_names import VARIANTI_FINALI, nome_presentazione
from agent.model_factory import ANTHROPIC_MAX_OUTPUT_TOKENS_PER_REQUEST
from evaluation.experiment_config import ExperimentConfig
from evaluation.v2_cohort_selector import PROTOCOL as V3_PROTOCOL
from evaluation.v2_preregister import EXPECTED_CASES, _overlap

PROTOCOL = "openrca_claude_five_agents_development_v2"
BRANCH = "feature/claude-clean-recovery-v2-2026-11-05"
PREVIOUS_PROTOCOL = "openrca_claude_five_agents_development_v1"
PREVIOUS_PLAN_SHA = "fb828dfcd7f2ac9e07b6d916ffd51e61b6a23052c1edbf7a06e965acb5a26158"
PREVIOUS_INTERRUPTED_RUN = (
    "openrca_claude_five_agents_development_v1__sonnet__cloudbed-1_q005__a0__r01"
)
V3_SHA = "6747eecc77c1b2fff7d581c7284578b5c574b4f7"
V3_PLAN_SHA = "002aadbee9cf5339ffb2ed36d90eaa492ca3c0900cbf32b3682629beb5610d68"
BASE_SHA = "1cdd223e74baa9d48ba057b5d5c719acd915d989"
MODELS = {
    "sonnet": "claude-sonnet-5-5",
    "haiku": "claude-haiku-5-5",
}
VARIANTS = tuple(VARIANTI_FINALI)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SAFE_ID = re.compile(r"^[a-z0-9_-]+$")


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _git_head(repo_dir: Path) -> str:
    def git(*args):
        return subprocess.run(["git", "-C", str(repo_dir), *args],
                              check=True, capture_output=True,
                              text=True).stdout.strip()
    if git("branch", "--show-current") != BRANCH:
        raise ValueError("Branch Claude non corretto")
    if git("status", "--porcelain"):
        raise ValueError("Working tree non pulito: freeze/preflight bloccati")
    head = git("rev-parse", "HEAD")
    if not SHA40.fullmatch(head):
        raise ValueError("Git SHA invalido")
    return head


def _load_gtfree(data_dir: Path) -> tuple[dict, str, dict]:
    """Solo sorgente preregistrata e manifest/split senza ground truth."""
    import csv
    root = Path(data_dir)
    source_path = root / "data/protocols/v2" / f"{V3_PROTOCOL}_plan_v1.json"
    if _sha(source_path) != V3_PLAN_SHA:
        raise ValueError("SHA piano V3 diverso dal congelamento noto")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if any((
        source.get("protocol") != V3_PROTOCOL,
        source.get("status") != "PREREGISTERED_NOT_EXECUTED",
        source.get("git_commit") != V3_SHA,
        source.get("case_count") != 8,
        source.get("run_count") != 40,
        source.get("model_provider") != "google",
        source.get("model_name") != "gemini-3.5-flash-lite",
        source.get("max_tool_rounds") != 6,
        source.get("max_verification_checks") != 2,
        source.get("output_contract_mode") != "v2_enforce",
        source.get("ground_truth_accessed") is not False,
    )):
        raise ValueError("Protocollo V3 sorgente non riconosciuto")
    split_path = root / "data/processed/split_market_v1.csv"
    manifest_path = root / "data/processed/benchmark_inputs_market.csv"
    if (_sha(split_path) != source["split_sha256"]
            or _sha(manifest_path) != source["manifest_sha256"]):
        raise ValueError("Manifest/split diversi dal piano V3")

    def records(path):
        with path.open(newline="", encoding="utf-8-sig") as fp:
            reader = csv.DictReader(fp)
            fields = set(reader.fieldnames or ())
            if "case_id" not in fields:
                raise ValueError("CSV senza case_id")
            if fields & {
                "reason", "scoring_points", "root_cause",
                "root cause component", "root cause reason",
            }:
                raise ValueError("Colonne ground truth nel CSV")
            rows = {}
            for row in reader:
                cid = row["case_id"]
                if not cid or cid in rows:
                    raise ValueError("Case ID duplicato/vuoto")
                rows[cid] = row
            return rows

    split, manifest = records(split_path), records(manifest_path)
    cases = source.get("cases")
    if not isinstance(cases, list) or len(cases) != 8:
        raise ValueError("Otto casi V3 mancanti")
    if {c["case_id"] for c in cases} != EXPECTED_CASES:
        raise ValueError("Coorte diversa dagli otto development storici")
    for i, c in enumerate(cases):
        cid = c["case_id"]
        if cid not in split or cid not in manifest:
            raise ValueError("Caso non presente nei file GT-free")
        if split[cid]["split"] != "development":
            raise ValueError("Coorte non development")
        for row in (manifest[cid], split[cid]):
            if (
                str(row["cloudbed"]) != c["cloudbed"]
                or int(row["start_unix"]) != c["start_unix"]
                or int(row["end_unix"]) != c["end_unix"]
            ):
                raise ValueError("Finestra caso discordante")
        if manifest[cid]["task_index"] != c["task_index"]:
            raise ValueError("Task discordante")
        if any(_overlap(c, other) for other in cases[i+1:]):
            raise ValueError("Finestre sovrapposte")
        historic_order = c["ordered_variants"]
        expected_historic = tuple(("A0", "A1_V2", "A1",
                                   "A1_VERIFY", "A1_VERIFY_ST"))
        if (len(historic_order) != 5
                or set(historic_order) != set(expected_historic)
                or [nome_presentazione(v) for v in historic_order]
                != list(VARIANTS[i % 5:] + VARIANTS[:i % 5])):
            raise ValueError("Rotazione V3 non coerente")
    return source, _sha(source_path), manifest


def _prompt_sha(variant: str, case: dict, manifest: dict) -> str:
    from agent.prompts import get_system_prompt
    from output.v2_task_contract import task_output_instruction
    instruction = manifest[case["case_id"]]["instruction"]
    text = get_system_prompt(variant) + task_output_instruction(
        task_index=case["task_index"], instruction=instruction)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_plan(data_dir: Path, code_commit: str) -> dict:
    if not SHA40.fullmatch(code_commit):
        raise ValueError("Commit SHA non valido")
    source, source_sha, manifest = _load_gtfree(data_dir)
    cases = []
    runs = []
    for i, c in enumerate(source["cases"]):
        cases.append({
            "case_id": c["case_id"], "cloudbed": c["cloudbed"],
            "task_index": c["task_index"],
            "start_unix": c["start_unix"],
            "end_unix": c["end_unix"],
            "requested_fault_count": c["requested_fault_count"],
            "ordered_variants": list(VARIANTS[i % 5:] + VARIANTS[:i % 5]),
            "prompt_sha256": {
                variant: _prompt_sha(variant, c, manifest)
                for variant in VARIANTS
            },
        })
    # 40 Sonnet prima dei 40 Haiku, ordine per caso ruotato come V3.
    for model_key, model_id in MODELS.items():
        for c in cases:
            for v in c["ordered_variants"]:
                run_id = f"{PROTOCOL}__{model_key}__{c['case_id']}__{v.lower()}__r01"
                assert SAFE_ID.fullmatch(run_id)
                runs.append({
                    "run_id": run_id, "model_key": model_key,
                    "model_name": model_id, "variant": v,
                    "case_id": c["case_id"],
                    "system_prompt_sha256": c["prompt_sha256"][v],
                })
    if len(runs) != 80 or len({x["run_id"] for x in runs}) != 80:
        raise ValueError("Piano 80 run incompleto")
    return {
        "protocol": PROTOCOL,
        "status": "PREREGISTERED_NOT_EXECUTED",
        "git_commit": code_commit,
        "base_git_commit": BASE_SHA,
        "source_v3_commit": V3_SHA,
        "source_v3_plan_sha256": source_sha,
        "recovery_provenance": {
            "previous_protocol": PREVIOUS_PROTOCOL,
            "previous_plan_sha256": PREVIOUS_PLAN_SHA,
            "interrupted_run_id": PREVIOUS_INTERRUPTED_RUN,
            "previous_run_status": "CLAIM_PENDING_NO_AUTO_RETRY",
            "reason": "KeyboardInterrupt during ToolNode; warning-only fix in tools.py",
            "previous_results_reused": False,
            "previous_claim_or_results_modified": False,
        },
        "split_sha256": source["split_sha256"],
        "manifest_sha256": source["manifest_sha256"],
        "case_count": 8, "variant_count": 5, "run_count": 80,
        "runs_per_model": 40, "replicas": 1,
        "models": MODELS,
        "variants": list(VARIANTS),
        "max_tool_rounds": 6,
        "max_verification_checks": 2,
        "max_output_tokens_per_llm_request": ANTHROPIC_MAX_OUTPUT_TOKENS_PER_REQUEST,
        "anthropic_max_retries": 0,
        "reasoning_effort": "provider_default",
        "recursion_limit": 30,
        "output_contract_mode": "v2_enforce",
        "variant_scheme": "current",
        "cases": cases, "runs": runs,
        "ground_truth_accessed": False,
        "scoring_performed": False,
        "limitations": (
            "Known development cohort, exploratory, no independent evaluation; "
            "PAVE-inspired does not implement full OpenRCA 2.0 PAVE."
        ),
    }


def _plan_path(data_dir: Path) -> Path:
    return Path(data_dir) / "data/protocols/v2" / f"{PROTOCOL}_plan_v1.json"


def _paths(data_dir: Path, run_id: str) -> tuple[Path, Path, Path]:
    if not SAFE_ID.fullmatch(run_id):
        raise ValueError("Run ID non sicuro")
    base = Path(data_dir) / "data/results/v2" / PROTOCOL
    return (base / f"{run_id}.claim.json",
            base / f"{run_id}.json",
            base / f"{run_id}.sha256.json")


def _write_only_new(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as fp:
        json.dump(obj, fp, sort_keys=True, ensure_ascii=False,
                  allow_nan=False, indent=2)
        fp.write("\n")


def write_plan(data_dir: Path, repo_dir: Path) -> Path:
    path = _plan_path(data_dir)
    _write_only_new(path, build_plan(data_dir, _git_head(repo_dir)))
    return path


def load_plan(data_dir: Path, repo_dir: Path):
    path = _plan_path(data_dir)
    plan = json.loads(path.read_text(encoding="utf-8"))
    expected = build_plan(data_dir, _git_head(repo_dir))
    if plan != expected:
        raise ValueError("Piano diverso da commit/dati congelati")
    return plan, _sha(path)


def _valid_output(result: dict, claim: dict, plan: dict,
                  run: dict, plan_sha: str):
    issues = []
    provenance = result.get("claude_provenance") or {}
    for description, ok in (
        ("claim_run", claim.get("run_id") == run["run_id"]),
        ("claim_plan", claim.get("plan_sha256") == plan_sha),
        ("claim_commit", claim.get("git_commit") == plan["git_commit"]),
        ("result_case", result.get("case_id") == run["case_id"]),
        ("result_variant", result.get("variant") == run["variant"]),
        ("variant_scheme", result.get("variant_scheme") == "current"),
        ("result_provider", result.get("model_provider") == "anthropic"),
        ("result_model", result.get("model") == run["model_name"]),
        ("max_tool_rounds", result.get("max_tool_rounds") == 6),
        ("prompt_hash", result.get("system_prompt_sha256")
         == run["system_prompt_sha256"]),
        ("output_contract", isinstance(result.get("output_contract_v2"), dict)),
        ("provenance_run", provenance.get("run_id") == run["run_id"]),
        ("provenance_plan", provenance.get("plan_sha256") == plan_sha),
        ("provenance_commit", provenance.get("git_commit") == plan["git_commit"]),
        ("provenance_provider", provenance.get("model_name") == run["model_name"]),
        ("evidence_hash", result.get("evidence_sha256") ==
         claim.get("evidence_sha256_before_api")),
    ):
        if not ok:
            issues.append(description)
    if run["variant"] == "A0":
        if result.get("evidence_sha256") is not None:
            issues.append("unexpected_a0_evidence")
    else:
        ev = result.get("evidence_sha256")
        if not isinstance(ev, str) or not HEX64.fullmatch(ev):
            issues.append("missing_evidence_sha")
    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        issues.append("missing_metrics")
    else:
        rounds = metrics.get("tool_rounds")
        if type(rounds) is not int or not 0 <= rounds <= 6:
            issues.append("invalid_rounds")
        if run["variant"] in ("A1_8R_Planning", "A1_PAVE"):
            e = metrics.get("exploration_tool_rounds")
            v = metrics.get("verification_tool_rounds")
            if (result.get("max_verification_checks") != 2
                    or result.get("exploration_round_limit") != 4
                    or type(e) is not int or type(v) is not int
                    or not 0 <= e <= 4 or not 0 <= v <= 2
                    or rounds != e + v):
                issues.append("invalid_planner_budget")
            if (result.get("verification") or {}).get("causa_verificata") is not False:
                issues.append("unjustified_causal_verification")
    if not isinstance(result.get("raw_response"), (str, type(None))):
        issues.append("invalid_raw_response")
    return issues


def preflight(data_dir: Path, repo_dir: Path) -> dict:
    plan, plan_sha = load_plan(data_dir, repo_dir)
    statuses = []
    for run in plan["runs"]:
        claim_path, out_path, hash_path = _paths(data_dir, run["run_id"])
        if claim_path.exists() and out_path.exists() and hash_path.exists():
            try:
                claim = json.loads(claim_path.read_text(encoding="utf-8"))
                result = json.loads(out_path.read_text(encoding="utf-8"))
                sidecar = json.loads(hash_path.read_text(encoding="utf-8"))
                digest_ok = all((
                    sidecar.get("run_id") == run["run_id"],
                    sidecar.get("plan_sha256") == plan_sha,
                    sidecar.get("output_sha256") == _sha(out_path),
                ))
                issues = _valid_output(result, claim, plan, run, plan_sha)
                if not digest_ok or issues:
                    status = "REVIEW_INTEGRITY"
                elif result.get("error") is not None:
                    status = "MODEL_ERROR_REVIEW_NO_RETRY"
                else:
                    status = "complete"
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                status = "REVIEW_CORRUPT"
        elif claim_path.exists():
            if out_path.exists():
                status = "REVIEW_MISSING_HASH"
            else:
                status = "CLAIM_PENDING_NO_AUTO_RETRY"
        elif out_path.exists() or hash_path.exists():
            status = "ORPHAN_OUTPUT_REVIEW"
        else:
            status = "ready"
        statuses.append({**run, "status": status})
    return {
        "protocol": PROTOCOL,
        "git_commit": plan["git_commit"],
        "plan_sha256": plan_sha,
        "run_count": 80,
        "counts": dict(sorted(Counter(x["status"] for x in statuses).items())),
        "models": {
            key: dict(sorted(Counter(
                x["status"] for x in statuses if x["model_key"] == key
            ).items()))
            for key in MODELS
        },
        "runs": statuses,
        "llm_called": False, "scoring_performed": False,
    }


def run_one(data_dir: Path, repo_dir: Path, *,
            run_id: str, confirm_api=False, approved_budget_usd=None,
            _runner=None, _model=None):
    """Una run senza retry automatico, claim prima di ogni possibile invoke."""
    if (confirm_api is not True or type(approved_budget_usd) not in (float, int)
            or not math.isfinite(approved_budget_usd) or approved_budget_usd <= 0):
        raise PermissionError("Serve consenso API e budget positivo.")
    state = preflight(data_dir, repo_dir)
    match = [r for r in state["runs"] if r["run_id"] == run_id]
    if len(match) != 1 or match[0]["status"] != "ready":
        raise FileExistsError("Run non ready o gia' tentata: STOP, nessun retry")
    run = match[0]
    plan, plan_sha = load_plan(data_dir, repo_dir)
    case = next(c for c in plan["cases"] if c["case_id"] == run["case_id"])

    cfg = ExperimentConfig(
        variant=run["variant"], variant_scheme="current",
        case_id=run["case_id"], model_provider="anthropic",
        model_name=run["model_name"], data_dir=Path(data_dir),
        repo_dir=Path(repo_dir), max_tool_rounds=6,
        max_verification_checks=2, recursion_limit=30,
        output_contract_mode="v2_enforce",
    )
    from evaluation.experiment_runner import (
        carica_caso, prepara_esperimento, run_experiment,
    )
    # Preprocessing e verifica solo dei dati GT-free PRIMA del claim.
    loaded = carica_caso(cfg)
    prepared = prepara_esperimento(cfg)
    for data in (loaded, prepared["caso"]):
        for key in ("case_id", "cloudbed", "task_index",
                    "start_unix", "end_unix"):
            if data[key] != case[key]:
                raise ValueError(f"Preprocessing non coerente: {key}")
    ev = prepared.get("evidence_sha256")
    if run["variant"] == "A0":
        if ev is not None:
            raise ValueError("A0 non deve generare report")
    elif not isinstance(ev, str) or not HEX64.fullmatch(ev):
        raise ValueError("SHA evidenze assente prima di API")

    llm = _model
    if _runner is None and llm is None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY assente")
        from agent.model_factory import crea_modello
        llm = crea_modello("anthropic", run["model_name"])
        if not (hasattr(llm, "bind_tools") and hasattr(llm, "invoke")):
            raise RuntimeError("Provider Claude non compatibile con LangGraph")

    refreshed = preflight(data_dir, repo_dir)
    if next(x for x in refreshed["runs"] if x["run_id"] == run_id)["status"] != "ready":
        raise FileExistsError("Run occupata durante preflight")

    claim, output, checksum = _paths(data_dir, run_id)
    _write_only_new(claim, {
        "run_id": run_id, "case_id": run["case_id"],
        "variant": run["variant"], "model_name": run["model_name"],
        "plan_sha256": plan_sha, "git_commit": plan["git_commit"],
        "approved_budget_usd": approved_budget_usd,
        "evidence_sha256_before_api": ev,
        "status": "STARTED_PERMANENT_NO_AUTO_RETRY",
    })
    try:
        result = (_runner(cfg) if _runner is not None
                  else run_experiment(cfg, llm=llm, verbose=False, salva=False))
        if not isinstance(result, dict):
            raise RuntimeError("Runner non ha restituito dict")
        result = dict(result)
        provider_versions = {"execution": "offline_fake"}
        if _runner is None:
            from importlib.metadata import version
            provider_versions = {
                name: version(name)
                for name in ("langchain-anthropic", "anthropic",
                             "langgraph", "langchain-core")
            }
        result["claude_provenance"] = {
            "provider_versions": provider_versions,
            "max_retries": 0,
            "max_tokens_per_request": ANTHROPIC_MAX_OUTPUT_TOKENS_PER_REQUEST,
            "run_id": run_id, "plan_sha256": plan_sha,
            "git_commit": plan["git_commit"],
            "model_name": run["model_name"],
            "model_key": run["model_key"],
        }
        _write_only_new(output, result)
        _write_only_new(checksum, {
            "run_id": run_id, "plan_sha256": plan_sha,
            "output_sha256": _sha(output),
        })
    except Exception:
        # La chiamata potrebbe essere stata fatturata: lascia claim per audit.
        raise
    updated = preflight(data_dir, repo_dir)
    status = next(x["status"] for x in updated["runs"]
                  if x["run_id"] == run_id)
    return {"run_id": run_id, "status": status, "saved": str(output),
            "scoring_performed": False, "retry_performed": False}


def run_batch(data_dir: Path, repo_dir: Path, *,
              model_key: str, max_new_runs: int = 1,
              confirm_api=False, approved_budget_usd=None,
              _runner=None):
    """Invocazioni sequenziali: salvo e verifico una run alla volta.

    Default e' 1. Massimo 8 per singola invocazione; per 40 servono
    cinque blocchi autorizzati e con verifica a ogni confine.
    Nessun retry, nemmeno se provider segnala 429/503.
    """
    if model_key not in MODELS:
        raise ValueError("Modello non registrato")
    if (confirm_api is not True or type(max_new_runs) is not int
            or not 1 <= max_new_runs <= 8
            or type(approved_budget_usd) not in (int, float)
            or not math.isfinite(approved_budget_usd) or approved_budget_usd <= 0):
        raise PermissionError("Serve consenso, budget e max_new_runs 1..8")
    initial = preflight(data_dir, repo_dir)
    candidates = [r for r in initial["runs"] if r["model_key"] == model_key]
    invalid = [r for r in candidates if r["status"] not in ("ready", "complete")]
    if invalid:
        raise RuntimeError(
            "Esistono run ambigue o fallite: revisione umana, NO batch: "
            + ", ".join(r["run_id"] for r in invalid[:3])
        )
    done = []
    for candidate in candidates:
        if len(done) == max_new_runs:
            break
        current = preflight(data_dir, repo_dir)
        if (current["git_commit"] != initial["git_commit"]
                or current["plan_sha256"] != initial["plan_sha256"]):
            raise RuntimeError("Codice/piano modificati durante batch")
        latest = next(r for r in current["runs"]
                      if r["run_id"] == candidate["run_id"])
        if latest["status"] == "complete":
            continue
        if latest["status"] != "ready":
            raise RuntimeError("Run ambigua durante batch: stop")
        answer = run_one(
            data_dir, repo_dir, run_id=candidate["run_id"],
            confirm_api=True, approved_budget_usd=approved_budget_usd,
            _runner=_runner,
        )
        if answer["status"] != "complete":
            raise RuntimeError(
                "Risultato salvato con stato " + answer["status"]
                + ": stop, non ritentare automaticamente"
            )
        done.append(candidate["run_id"])
        print("COMPLETATA", len(done), "/", max_new_runs,
              candidate["model_key"], candidate["variant"],
              candidate["case_id"])
    final = preflight(data_dir, repo_dir)
    return {
        "model_key": model_key, "new_runs": done,
        "new_run_count": len(done),
        "counts": final["models"][model_key],
        "scoring_performed": False,
        "note": "Budget NON applicato come hard cap lato Anthropic.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--repo-dir", type=Path, required=True)
    parser.add_argument("--write-plan", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--model", choices=list(MODELS))
    parser.add_argument("--max-new-runs", type=int)
    parser.add_argument("--approved-budget-usd", type=float)
    parser.add_argument("--confirm-api", action="store_true")
    args = parser.parse_args()
    if args.execute:
        if args.write_plan or args.model is None:
            parser.error("--execute richiede --model e non --write-plan")
        reply = run_batch(
            args.data_dir, args.repo_dir, model_key=args.model,
            max_new_runs=args.max_new_runs,
            confirm_api=args.confirm_api,
            approved_budget_usd=args.approved_budget_usd,
        )
    elif args.write_plan:
        if args.model or args.max_new_runs or args.confirm_api or args.approved_budget_usd:
            parser.error("--write-plan solo offline")
        path = write_plan(args.data_dir, args.repo_dir)
        reply = {"written": str(path), "sha256": _sha(path),
                 "scoring_performed": False, "llm_called": False}
    else:
        if args.model or args.max_new_runs or args.confirm_api or args.approved_budget_usd:
            parser.error("Il preflight non ammette flag API")
        if _plan_path(args.data_dir).exists():
            reply = preflight(args.data_dir, args.repo_dir)
        else:
            reply = build_plan(args.data_dir, _git_head(args.repo_dir))
            reply = {
                "preview": True, "git_commit": reply["git_commit"],
                "case_count": reply["case_count"],
                "planned_runs": reply["run_count"],
                "models": reply["models"], "variants": reply["variants"],
                "llm_called": False, "scoring_performed": False,
            }
    print(json.dumps(reply, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
