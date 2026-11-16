"""RQ2-V5: riga di comando per Colab (check, run, summary).

  python -m evaluation.rq2_v5_run_cli check   --drive-root ... --repo-dir ... [--models gemini ...]
  python -m evaluation.rq2_v5_run_cli run     --drive-root ... --repo-dir ... --models gemini --harnesses A0 --cases cloudbed-1_q032 --max-stages 3
  python -m evaluation.rq2_v5_run_cli summary --drive-root ...

`check` e `summary` non chiamano mai un provider. `run` chiama i provider solo
per gli stage selezionati, uno alla volta, con claim create-only.
Le chiavi si leggono SOLO dall'ambiente (mai stampate, mai salvate).
"""
from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
import os
import subprocess
import sys
from pathlib import Path

from evaluation import rq2_v5_matrix_runner as mr
from evaluation.rq2_v4_unified_gtfree_discovery_plan import (
    build_offline_v4_discovery_plan,
)
from evaluation.rq2_v5_response_normalization import (
    POLICY as FORMAT_POLICY, VERSION as FORMAT_VERSION,
)
from evaluation.rq2_v5_retry import (
    MAX_ATTEMPTS as RETRY_MAX_ATTEMPTS, RETRY_POLICY,
)

KEY_ENV = {"google": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
           "anthropic": ("ANTHROPIC_API_KEY",)}
PACKAGES = ("langchain-core", "langgraph", "langchain-anthropic",
            "langchain-google-genai", "anthropic", "google-genai")
MANIFEST = "manifest_v1.json"
# Campi che devono restare identici in tutti i lotti dello stesso esperimento.
INVARIANTS = ("protocol", "plan_preview_sha256", "format_policy",
              "format_version", "retry_policy", "retry_max_attempts",
              "C_system_prompt_sha256",
              "K_system_prompt_sha256", "d_budgets")


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args],
                         capture_output=True, text=True, check=False)
    return out.stdout.strip()


def _store_root(drive_root: Path, namespace: str | None = None) -> Path:
    """Archivio del run: di default quello scientifico; un pilota ne usa uno
    separato, cosi' non consuma gli stage reali (che sono create-only)."""
    return drive_root / (namespace or mr.NAMESPACE.as_posix())


def _key_present(provider: str) -> bool:
    return any(bool(os.environ.get(name, "").strip())
               for name in KEY_ENV[provider])


def _secrets() -> list[str]:
    return [os.environ[name] for names in KEY_ENV.values() for name in names
            if os.environ.get(name)]


def _versions() -> dict:
    found = {}
    for name in PACKAGES:
        try:
            found[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            found[name] = None
    return found


def build_manifest(repo: Path, plan: dict) -> dict:
    from evaluation.rq2_v5_stage_executor import (
        D_MAX_ROUNDS, PLANNER_CHECKS, RECURSION_LIMIT, prompt_hashes,
    )
    return {
        "protocol": mr.PROTOCOL,
        "runner_version": mr.VERSION,
        "plan_preview_sha256": plan["preview_sha256"],
        "format_policy": FORMAT_POLICY,
        "format_version": FORMAT_VERSION,
        "retry_policy": RETRY_POLICY,
        "retry_max_attempts": RETRY_MAX_ATTEMPTS,
        **prompt_hashes(),
        "d_budgets": {"max_tool_rounds": D_MAX_ROUNDS,
                      "max_verification_checks": PLANNER_CHECKS,
                      "recursion_limit": RECURSION_LIMIT},
        "created_commit": _git(repo, "rev-parse", "HEAD"),
        "python": sys.version.split()[0],
        "packages": _versions(),
    }


def ensure_manifest(root: Path, manifest: dict) -> str:
    """Create-only al primo lotto; dai lotti successivi verifica gli invarianti."""
    path = root / MANIFEST
    root.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        mr.StageStore._write_new(path, manifest)
        return "CREATED"
    saved = json.loads(path.read_text(encoding="utf-8"))
    drift = [k for k in INVARIANTS if saved.get(k) != manifest.get(k)]
    if drift:
        raise SystemExit("MANIFEST DIVERSO dai lotti precedenti: " + str(drift))
    return "MATCHES"


def _plan_rows() -> tuple[dict, list[dict]]:
    plan = build_offline_v4_discovery_plan()
    rows = plan["entries"]
    mr.validate_plan(rows)
    return plan, rows


def _select(rows, args):
    return mr.select_rows(
        rows, models=args.models, harnesses=args.harnesses,
        cases=args.cases, stages=args.stages,
    )


def cmd_check(args) -> int:
    """Nessuna API: runtime pinned, dati GT-free, prompt, chiavi (solo True/False)."""
    from evaluation.rq2_model_factory import assert_exact_runtime_snapshot
    from evaluation.rq2_v5_stage_executor import V5StageExecutor
    plan, rows = _plan_rows()
    selected = _select(rows, args)
    report = {"plan_stages": len(rows), "selected_stages": len(selected)}
    assert_exact_runtime_snapshot()
    report["runtime_snapshot"] = "OK"
    providers = sorted({r["model_provider"] for r in selected})
    report["keys_present"] = {p: _key_present(p) for p in providers}
    drive_root, repo = Path(args.drive_root), Path(args.repo_dir)
    executor = V5StageExecutor(data_dir=drive_root, repo_dir=repo)
    prepared = 0
    for row in selected:
        if row["stage"] == "D":
            executor.prepare(row, {})
            prepared += 1
    report["d_stages_prepared_ok"] = prepared
    report["git_head"] = _git(repo, "rev-parse", "HEAD")
    report["git_clean"] = _git(repo, "status", "--porcelain") == ""
    report["manifest_would_be"] = build_manifest(repo, plan)["created_commit"]
    print(json.dumps(report, indent=2, ensure_ascii=False))
    ok = all(report["keys_present"].values()) and report["git_clean"]
    return 0 if ok else 2


def cmd_run(args) -> int:
    from evaluation.rq2_model_factory import assert_exact_runtime_snapshot
    from evaluation.rq2_v5_stage_executor import V5StageExecutor
    plan, rows = _plan_rows()
    selected = _select(rows, args)
    repo = Path(args.repo_dir)
    if _git(repo, "status", "--porcelain") and not args.allow_dirty:
        print("Il checkout non e' pulito: run rifiutato.")
        return 2
    for provider in sorted({r["model_provider"] for r in selected}):
        if not _key_present(provider):
            print(f"Chiave mancante per il provider {provider}: run rifiutato.")
            return 2
    assert_exact_runtime_snapshot()
    root = _store_root(Path(args.drive_root), args.namespace)
    print("Manifest:", ensure_manifest(root, build_manifest(repo, plan)))
    store = mr.StageStore(root)
    executor = V5StageExecutor(data_dir=Path(args.drive_root), repo_dir=repo)
    outcome = mr.run_matrix(
        selected, plan=rows, store=store, executor=executor,
        source_commit=_git(repo, "rev-parse", "HEAD"),
        max_stages=args.max_stages,
        time_budget_seconds=(args.time_budget_minutes * 60
                             if args.time_budget_minutes else None),
        secrets=_secrets(),
    )
    print(json.dumps(outcome, indent=2))
    print(mr.format_summary(mr.summarize(rows, store)))
    return 0


def cmd_summary(args) -> int:
    _, rows = _plan_rows()
    store = mr.StageStore(_store_root(Path(args.drive_root), args.namespace))
    selected = _select(rows, args)
    print(mr.format_summary(mr.summarize(selected, store)))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rq2_v5_run_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "run", "summary"):
        p = sub.add_parser(name)
        p.add_argument("--drive-root", required=True)
        p.add_argument("--repo-dir")
        p.add_argument("--namespace", help="cartella archivio sotto drive-root "
                       "(default: data/rq2_v5_format_fair_v1)")
        p.add_argument("--models", nargs="+")
        p.add_argument("--harnesses", nargs="+")
        p.add_argument("--cases", nargs="+")
        p.add_argument("--stages", nargs="+")
        if name == "run":
            p.add_argument("--max-stages", type=int)
            p.add_argument("--time-budget-minutes", type=float)
            p.add_argument("--allow-dirty", action="store_true")
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    if args.command in ("check", "run") and not args.repo_dir:
        print("--repo-dir obbligatorio")
        return 2
    return {"check": cmd_check, "run": cmd_run,
            "summary": cmd_summary}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
