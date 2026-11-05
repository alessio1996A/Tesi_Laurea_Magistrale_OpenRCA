"""Fase 1: ablation Gemini 4+2 vs 5+1 sui soli 8 casi development V3.

Default = SOLO preflight offline. --write-plan crea un piano distinto da V3.
Le esecuzioni sono UNA ALLA VOLTA, dopo --confirm-api e budget esplicito.
Ogni tentativo ha un claim permanente prima di qualunque invoke a pagamento;
un claim senza risultato NON viene mai ripetuto automaticamente.
NON legge query.csv, record.csv, score o predizioni storiche.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import subprocess

from evaluation.experiment_config import ExperimentConfig
from evaluation.v2_cohort_selector import PROTOCOL as V3_PROTOCOL
from evaluation.v2_preregister import EXPECTED_CASES, _overlap

PROTOCOL = "openrca_planner_budget_4p2_5p1_development_v1"
BRANCH = "feature/planner-budget-ablation-2026-11-05"
ARMS = {"4p2": 2, "5p1": 1}
EXPECTED_BASE = "1cdd223e74baa9d48ba057b5d5c719acd915d989"
SHA40 = re.compile(r"^[a-f0-9]{40}$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json_digest(value: dict) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _git_head(repo_dir: Path) -> str:
    def git(*args):
        return subprocess.run(
            ["git", "-C", str(repo_dir), *args],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    if git("branch", "--show-current") != BRANCH:
        raise ValueError("Branch non corrispondente all'ablation Fase 1")
    if git("status", "--porcelain"):
        raise ValueError("Working tree non pulito: blocco preregistrazione")
    sha = git("rev-parse", "HEAD")
    if not SHA40.fullmatch(sha):
        raise ValueError("SHA commit non valido")
    return sha


def _read_csv_by_case(path: Path) -> dict:
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if "case_id" not in (reader.fieldnames or []):
            raise ValueError("CSV senza case_id")
        if {"reason", "scoring_points", "root_cause"} & set(reader.fieldnames):
            raise ValueError("CSV con potenziale ground truth")
        rows = {}
        for row in reader:
            cid = row["case_id"]
            if not cid or cid in rows:
                raise ValueError("Case_id vuoto o duplicato")
            rows[cid] = row
        return rows


def _source(data_dir: Path) -> tuple[dict, str, dict]:
    """Legge SOLO il piano V3 e manifest/split GT-free, mai output V3."""
    root = Path(data_dir)
    source_file = root / "data/protocols/v2" / f"{V3_PROTOCOL}_plan_v1.json"
    source = json.loads(source_file.read_text(encoding="utf-8"))
    if any((
        source.get("protocol") != V3_PROTOCOL,
        source.get("status") != "PREREGISTERED_NOT_EXECUTED",
        source.get("git_commit") != "6747eecc77c1b2fff7d581c7284578b5c574b4f7",
        source.get("model_provider") != "google",
        source.get("model_name") != "gemini-3.5-flash-lite",
        source.get("max_tool_rounds") != 6,
        source.get("max_verification_checks") != 2,
        source.get("output_contract_mode") != "v2_enforce",
        source.get("case_count") != 8,
        source.get("run_count") != 40,
        source.get("ground_truth_accessed") is not False,
    )):
        raise ValueError("Il piano V3 sorgente non e' quello congelato")
    split_path = root / "data/processed/split_market_v1.csv"
    manifest_path = root / "data/processed/benchmark_inputs_market.csv"
    if (_sha(split_path) != source["split_sha256"]
            or _sha(manifest_path) != source["manifest_sha256"]):
        raise ValueError("SHA-256 split/manifest diversi dalla V3")
    split, manifest = _read_csv_by_case(split_path), _read_csv_by_case(manifest_path)
    cases = source.get("cases")
    if not isinstance(cases, list) or len(cases) != 8:
        raise ValueError("V3 non contiene gli 8 casi")
    if {x["case_id"] for x in cases} != EXPECTED_CASES:
        raise ValueError("I casi non corrispondono alla coorte V3")
    for i, case in enumerate(cases):
        cid = case["case_id"]
        if cid not in manifest or cid not in split or split[cid]["split"] != "development":
            raise ValueError(f"Caso non development nel manifest: {cid}")
        for row in (split[cid], manifest[cid]):
            if (str(row["cloudbed"]) != case["cloudbed"]
                    or int(row["start_unix"]) != case["start_unix"]
                    or int(row["end_unix"]) != case["end_unix"]):
                raise ValueError(f"Finestra non coerente: {cid}")
        if (manifest[cid]["task_index"] != case["task_index"]
                or any(_overlap(case, other) for other in cases[i + 1:])):
            raise ValueError(f"Task o overlap non valido: {cid}")
    return source, _sha(source_file), manifest


def _prompt_hash(case: dict, manifest: dict) -> str:
    """Hash del prompt di sistema identico per entrambi i bracci."""
    from agent.prompts import get_system_prompt
    from output.v2_task_contract import task_output_instruction
    row = manifest[case["case_id"]]
    prompt = (get_system_prompt("A1_8R_Planning")
              + task_output_instruction(
                  task_index=case["task_index"], instruction=row["instruction"]))
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def build_plan(data_dir: Path, repo_sha: str) -> dict:
    """Costruisce in memoria un piano immutabile; nessuna scrittura/API."""
    if not SHA40.fullmatch(repo_sha):
        raise ValueError("SHA Git non valido")
    source, source_sha, manifest = _source(data_dir)
    planned = []
    for i, case in enumerate(source["cases"]):
        # Rotazione contro un bias fisso d'ordine dei due bracci.
        order = ["4p2", "5p1"] if i % 2 == 0 else ["5p1", "4p2"]
        planned.append({
            "case_id": case["case_id"],
            "cloudbed": case["cloudbed"],
            "task_index": case["task_index"],
            "start_unix": case["start_unix"],
            "end_unix": case["end_unix"],
            "requested_fault_count": case["requested_fault_count"],
            "system_prompt_sha256": _prompt_hash(case, manifest),
            "arm_order": order,
            "run_ids": [
                f"{PROTOCOL}__{case['case_id']}__{arm}__r01"
                for arm in order
            ],
        })
    return {
        "protocol": PROTOCOL,
        "status": "PREREGISTERED_NOT_EXECUTED",
        "development_only": True,
        "git_commit": repo_sha,
        "base_commit": EXPECTED_BASE,
        "v3_commit_frozen": source["git_commit"],
        "v3_plan_sha256": source_sha,
        "split_sha256": source["split_sha256"],
        "manifest_sha256": source["manifest_sha256"],
        "model_provider": "google",
        "model_name": source["model_name"],
        "variant": "A1_8R_Planning",
        "variant_scheme": "current",
        "max_tool_rounds": 6,
        "recursion_limit": 30,
        "output_contract_mode": "v2_enforce",
        "max_verification_checks_by_arm": ARMS,
        "case_count": 8,
        "run_count": 16,
        "replicas": 1,
        "scoring_performed": False,
        "ground_truth_accessed": False,
        "cases": planned,
        "limitations": "Exploratory/tuning development cohort; not independent evaluation.",
    }


def _plan_path(data_dir: Path) -> Path:
    return Path(data_dir) / "data/protocols/v2" / f"{PROTOCOL}_plan_v1.json"


def _exclusive_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(data, f, sort_keys=True, ensure_ascii=False,
                  allow_nan=False, indent=2)
        f.write("\n")


def write_plan(data_dir: Path, repo_dir: Path) -> Path:
    path = _plan_path(data_dir)
    _exclusive_json(path, build_plan(data_dir, _git_head(repo_dir)))
    return path


def load_plan(data_dir: Path, repo_dir: Path) -> tuple[dict, str]:
    path = _plan_path(data_dir)
    plan = json.loads(path.read_text(encoding="utf-8"))
    expected = build_plan(data_dir, _git_head(repo_dir))
    if plan != expected:
        raise ValueError("Piano ablation incoerente con SHA Git/manifest/V3")
    return plan, _sha(path)


def _paths(data_dir: Path, run_id: str) -> tuple[Path, Path]:
    if not re.fullmatch(r"[a-z0-9_-]+", run_id):
        raise ValueError("run_id non sicuro")
    root = Path(data_dir) / "data/results/v2" / PROTOCOL
    return root / (run_id + ".claim.json"), root / (run_id + ".json")


def _valid_result(result: dict, claim: dict, plan: dict,
                  case: dict, arm: str, run_id: str, plan_sha: str) -> bool:
    """Non confonde file presente e run validata."""
    metrics = result.get("metrics")
    proof = result.get("ablation_provenance") or {}
    checks = ARMS[arm]
    return all((
        claim.get("run_id") == run_id,
        claim.get("plan_sha256") == plan_sha,
        claim.get("git_commit") == plan["git_commit"],
        result.get("case_id") == case["case_id"],
        result.get("variant") == "A1_8R_Planning",
        result.get("variant_scheme") == "current",
        result.get("model_provider") == "google",
        result.get("model") == plan["model_name"],
        result.get("max_tool_rounds") == 6,
        result.get("max_verification_checks") == checks,
        result.get("exploration_round_limit") == 6 - checks,
        result.get("system_prompt_sha256") == case["system_prompt_sha256"],
        result.get("evidence_sha256") == claim.get("evidence_sha256_before_api"),
        result.get("error") is None,
        isinstance(result.get("output_contract_v2"), dict),
        proof.get("run_id") == run_id,
        proof.get("plan_sha256") == plan_sha,
        proof.get("arm") == arm,
        proof.get("git_commit") == plan["git_commit"],
        isinstance(metrics, dict),
        isinstance(metrics.get("exploration_tool_rounds") if isinstance(metrics, dict) else None, int),
        isinstance(metrics.get("verification_tool_rounds") if isinstance(metrics, dict) else None, int),
        isinstance(metrics.get("tool_rounds") if isinstance(metrics, dict) else None, int),
        isinstance(metrics, dict) and 0 <= metrics["exploration_tool_rounds"] <= 6 - checks,
        isinstance(metrics, dict) and 0 <= metrics["verification_tool_rounds"] <= checks,
        isinstance(metrics, dict) and metrics["tool_rounds"] ==
            metrics["exploration_tool_rounds"] + metrics["verification_tool_rounds"],
        isinstance(result.get("evidence_sha256"), str)
            and bool(HEX64.fullmatch(result["evidence_sha256"])),
    ))


def preflight(data_dir: Path, repo_dir: Path) -> dict:
    """Solo letture; claim pendenti e output corrotti sono BLOCCATI."""
    plan, plan_sha = load_plan(data_dir, repo_dir)
    rows = []
    for case in plan["cases"]:
        prior_complete = True
        for index, (arm, run_id) in enumerate(zip(case["arm_order"], case["run_ids"])):
            claim_path, out_path = _paths(data_dir, run_id)
            if claim_path.exists() and out_path.exists():
                try:
                    claim = json.loads(claim_path.read_text(encoding="utf-8"))
                    result = json.loads(out_path.read_text(encoding="utf-8"))
                    good = _valid_result(result, claim, plan, case, arm, run_id, plan_sha)
                    status = "complete" if good else "REVIEW_INTEGRITY"
                except (OSError, ValueError, TypeError, KeyError):
                    status = "REVIEW_CORRUPT"
            elif claim_path.exists():
                status = "CLAIM_PENDING_NO_AUTO_RETRY"
            elif out_path.exists():
                status = "ORPHAN_OUTPUT_REVIEW"
            else:
                status = "ready" if prior_complete else "blocked_by_previous"
            rows.append({"case_id": case["case_id"], "arm": arm,
                         "run_id": run_id, "order": index, "status": status})
            prior_complete = status == "complete"
    return {
        "protocol": PROTOCOL, "git_commit": plan["git_commit"],
        "plan_sha256": plan_sha, "case_count": 8, "planned_runs": 16,
        "status_counts": {s: sum(r["status"] == s for r in rows)
                          for s in sorted({x["status"] for x in rows})},
        "runs": rows, "llm_called": False, "scoring_performed": False,
        "note": "Nessuna esecuzione automatica; costo da approvare prima di invoke.",
    }


def run_exactly_one(data_dir: Path, repo_dir: Path, *, run_id: str,
                    confirm_api: bool = False, approved_budget_usd: float | None = None,
                    _runner=None, _llm=None) -> dict:
    """Una sola run con claim create-only. _runner/_llm sono per test offline."""
    if confirm_api is not True or approved_budget_usd is None or approved_budget_usd <= 0:
        raise PermissionError("Servono --confirm-api e budget USD approvato")
    state = preflight(data_dir, repo_dir)
    rows = [x for x in state["runs"] if x["run_id"] == run_id]
    if len(rows) != 1 or rows[0]["status"] != "ready":
        raise FileExistsError("Run non pronta, effettuata o ambigua: NO retry")
    plan, plan_sha = load_plan(data_dir, repo_dir)
    row = rows[0]
    case = next(c for c in plan["cases"] if c["case_id"] == row["case_id"])
    arm = row["arm"]
    cfg = ExperimentConfig(
        variant="A1_8R_Planning", variant_scheme="current",
        case_id=case["case_id"], data_dir=Path(data_dir),
        repo_dir=Path(repo_dir), model_provider="google",
        model_name=plan["model_name"], max_tool_rounds=6,
        max_verification_checks=ARMS[arm], recursion_limit=30,
        output_contract_mode="v2_enforce",
    )
    from evaluation.experiment_runner import prepara_esperimento, run_experiment
    prepared = prepara_esperimento(cfg)  # GT-free, prima del claim
    for key in ("case_id", "cloudbed", "task_index", "start_unix", "end_unix"):
        if prepared["caso"][key] != case[key]:
            raise ValueError("Preprocessing non coerente: " + key)
    evidence_sha = prepared["evidence_sha256"]
    if not isinstance(evidence_sha, str) or not HEX64.fullmatch(evidence_sha):
        raise ValueError("SHA evidence mancante: nessuna API")
    llm = _llm
    provider_library_version = "offline_fake"
    if _runner is None:
        if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
            raise RuntimeError("API Secret Google assente")
        provider_library_version = version("langchain-google-genai")
        if provider_library_version.split(".")[0] != "4":
            raise RuntimeError("Verificare compatibilita' retry: serve langchain-google-genai 4.x")
        from langchain_google_genai import ChatGoogleGenerativeAI
        # Su google-genai 4.x max_retries=1 => una sola attempt complessiva.
        # Registrare versione esatta; NON cambiare tra i due bracci.
        llm = ChatGoogleGenerativeAI(model=cfg.model_name, max_retries=1)
    latest = preflight(data_dir, repo_dir)
    current = next(x for x in latest["runs"] if x["run_id"] == run_id)
    if current["status"] != "ready":
        raise FileExistsError("Run reclamata durante preflight")
    claim, out = _paths(data_dir, run_id)
    _exclusive_json(claim, {
        "run_id": run_id, "arm": arm, "case_id": cfg.case_id,
        "plan_sha256": plan_sha, "git_commit": plan["git_commit"],
        "evidence_sha256_before_api": evidence_sha,
        "approved_budget_usd": approved_budget_usd,
        "status": "STARTED_PERMANENT_NO_AUTO_RETRY",
    })
    try:
        result = (_runner(cfg) if _runner is not None
                  else run_experiment(cfg, llm=llm, verbose=False, salva=False))
        if not isinstance(result, dict):
            raise TypeError("Runner non ha restituito un dict")
        result = dict(result)
        result["ablation_provenance"] = {
            "run_id": run_id, "arm": arm,
            "git_commit": plan["git_commit"],
            "plan_sha256": plan_sha,
            "provider_library_version": provider_library_version,
        }
        _exclusive_json(out, result)
    except Exception:
        # Claim lasciato intenzionalmente: un crash puo' avere gia' fatturato.
        raise
    good = _valid_result(result, json.loads(claim.read_text(encoding="utf-8")),
                         plan, case, arm, run_id, plan_sha)
    return {"run_id": run_id, "saved": str(out),
            "integrity": "complete" if good else "REVIEW_INTEGRITY",
            "api_calls_rerun": False, "scoring_performed": False}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", required=True, type=Path)
    p.add_argument("--repo-dir", required=True, type=Path)
    p.add_argument("--write-plan", action="store_true")
    p.add_argument("--run-id")
    p.add_argument("--confirm-api", action="store_true")
    p.add_argument("--approved-budget-usd", type=float)
    a = p.parse_args()
    if a.write_plan:
        if a.run_id or a.confirm_api or a.approved_budget_usd is not None:
            p.error("--write-plan non puo' avviare API")
        path = write_plan(a.data_dir, a.repo_dir)
        result = {"written": str(path), "sha256": _sha(path), "llm_called": False}
    elif a.run_id:
        result = run_exactly_one(
            a.data_dir, a.repo_dir, run_id=a.run_id,
            confirm_api=a.confirm_api, approved_budget_usd=a.approved_budget_usd,
        )
    else:
        if a.confirm_api or a.approved_budget_usd is not None:
            p.error("Flag API non utilizzabili in preflight")
        result = preflight(a.data_dir, a.repo_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
