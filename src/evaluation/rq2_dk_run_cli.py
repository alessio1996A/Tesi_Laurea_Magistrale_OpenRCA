"""RQ2 - ablazione D->K: riga di comando per PowerShell e Colab (check, run, summary, compare).

  python -m evaluation.rq2_dk_run_cli check   --drive-root ... --repo-dir ... [--models gemini ...]
  python -m evaluation.rq2_dk_run_cli run     --drive-root ... --repo-dir ... --models gemini --harnesses A0 --max-stages 3
  python -m evaluation.rq2_dk_run_cli summary --drive-root ...
  python -m evaluation.rq2_dk_run_cli compare --drive-root ...

`check`, `summary` e `compare` NON chiamano mai un provider. `run` chiama i provider
solo per gli stadi K selezionati, uno alla volta, con claim create-only. I record D
del run congelato (`data/rq2_v5_format_fair_v1`) si leggono soltanto; i nuovi K
vanno in `data/rq2_dk_ablation_v1`. Le chiavi si leggono SOLO dall'ambiente.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evaluation import rq2_dk_ablation as dk
from evaluation import rq2_v5_matrix_runner as mr
from evaluation.rq2_v5_response_normalization import (
    POLICY as FORMAT_POLICY, VERSION as FORMAT_VERSION,
)
from evaluation.rq2_v5_retry import (
    MAX_ATTEMPTS as RETRY_MAX_ATTEMPTS, RETRY_POLICY,
)
from evaluation.rq2_v5_run_cli import (
    _git, _key_present, _secrets, _versions,
)

MANIFEST = "manifest_dk_v1.json"
# Campi che devono restare identici in tutti i lotti dello stesso esperimento.
INVARIANTS = ("protocol", "plan_preview_sha256", "format_policy",
              "format_version", "retry_policy", "retry_max_attempts",
              "K_no_cause_system_prompt_sha256", "source_namespace")


def build_manifest(repo: Path, plan: dict) -> dict:
    """Manifest dell'esperimento: protocollo, prompt, politiche, commit e pacchetti."""
    return {
        "protocol": dk.PROTOCOL,
        "ablation_version": dk.VERSION,
        "plan_preview_sha256": plan["preview_sha256"],
        "format_policy": FORMAT_POLICY,
        "format_version": FORMAT_VERSION,
        "retry_policy": RETRY_POLICY,
        "retry_max_attempts": RETRY_MAX_ATTEMPTS,
        "K_no_cause_system_prompt_sha256": dk.K_NO_CAUSE_SYSTEM_SHA256,
        "source_namespace": dk.SOURCE_NAMESPACE.as_posix(),
        "created_commit": _git(repo, "rev-parse", "HEAD"),
        "python": sys.version.split()[0],
        "packages": _versions(),
    }


def ensure_manifest(root: Path, manifest: dict) -> str:
    """Create-only al primo lotto; dai lotti successivi verifica che gli invarianti non siano cambiati."""
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


def _select(rows, args):
    """Filtra le righe K per modello, harness e caso (nomi sconosciuti = errore)."""
    return mr.select_rows(rows, models=args.models, harnesses=args.harnesses,
                          cases=args.cases)


def _roots(args) -> tuple[Path, Path]:
    """Cartella del run congelato (sola lettura) e cartella dei nuovi K."""
    drive = Path(args.drive_root)
    return drive / dk.SOURCE_NAMESPACE, drive / (args.namespace or dk.NAMESPACE.as_posix())


def cmd_check(args) -> int:
    """Nessuna API: runtime, record D di origine, pacchetti K costruibili, chiavi (solo True/False)."""
    from evaluation.rq2_model_factory import assert_exact_runtime_snapshot
    plan, rows = dk.build_dk_plan()
    selected = _select(rows, args)
    source_root, _ = _roots(args)
    source = dk.SourceDRecords(source_root)
    assert_exact_runtime_snapshot()
    executor = dk.DKExecutor(data_dir=Path(args.drive_root))
    report = {"plan_k_stages": len(rows), "selected": len(selected),
              "k_no_cause_prompt_sha256": dk.K_NO_CAUSE_SYSTEM_SHA256}
    complete = missing = other = prepared = 0
    for row in selected:
        d_record = source.load(dk.d_parent_id(row))
        if d_record is None:
            missing += 1
        elif d_record["status"] != mr.STATUS_COMPLETE:
            other += 1
        else:
            complete += 1
            executor.prepare(row, d_record)
            prepared += 1
    report.update({"d_complete": complete, "d_missing": missing,
                   "d_not_complete": other, "k_packages_prepared_ok": prepared})
    providers = sorted({r["model_provider"] for r in selected})
    report["keys_present"] = {p: _key_present(p) for p in providers}
    repo = Path(args.repo_dir)
    report["git_head"] = _git(repo, "rev-parse", "HEAD")
    report["git_clean"] = _git(repo, "status", "--porcelain") == ""
    print(json.dumps(report, indent=2, ensure_ascii=False))
    ok = (all(report["keys_present"].values()) and report["git_clean"]
          and missing == 0)
    return 0 if ok else 2


def cmd_run(args) -> int:
    """Esegue i K senza causa selezionati (le chiamate ai provider sono a pagamento)."""
    from evaluation.rq2_model_factory import assert_exact_runtime_snapshot
    plan, rows = dk.build_dk_plan()
    selected = _select(rows, args)
    repo = Path(args.repo_dir)
    if _git(repo, "status", "--porcelain") and not args.allow_dirty:
        print("Il checkout non e' pulito: run rifiutato.")
        return 2
    for provider in sorted({r["model_provider"] for r in selected}):
        if not _key_present(provider):
            print(f"Chiave mancante per il provider {provider}: run rifiutato.")
            return 2
    source_root, out_root = _roots(args)
    source = dk.SourceDRecords(source_root)
    assert_exact_runtime_snapshot()
    print("Manifest:", ensure_manifest(out_root, build_manifest(repo, plan)))
    store = mr.StageStore(out_root)
    executor = dk.DKExecutor(data_dir=Path(args.drive_root))
    outcome = dk.run_dk_matrix(
        selected, source=source, store=store, executor=executor,
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
    """Stato dei K senza causa: esiti, conformita' di formato, retry (nessuna API)."""
    _, rows = dk.build_dk_plan()
    _, out_root = _roots(args)
    store = mr.StageStore(out_root)
    print(mr.format_summary(mr.summarize(_select(rows, args), store)))
    return 0


def cmd_compare(args) -> int:
    """Confronto descrittivo: K con la causa di C (run congelato) contro K senza causa."""
    _, rows = dk.build_dk_plan()
    source_root, out_root = _roots(args)
    result = dk.compare_with_frozen(
        _select(rows, args), source=dk.SourceDRecords(source_root),
        store=mr.StageStore(out_root))
    for title, table in (("Per modello", result["by_model"]),
                         ("Per harness", result["by_harness"])):
        print(title + " (con causa | senza causa):")
        for key, slot in sorted(table.items()):
            with_c = ", ".join(f"{k}={v}" for k, v in sorted(slot["with_cause"].items()))
            without = ", ".join(f"{k}={v}" for k, v in sorted(slot["without_cause"].items()))
            print(f"  {key:15s} {with_c}  |  {without}")
        print()
    print("Celle (modello | harness | caso: con causa -> senza causa):")
    for cell in result["cells"]:
        print(f"  {cell['model']:7s} {cell['harness']:15s} {cell['case_id']}: "
              f"{cell['with_cause']} -> {cell['without_cause']}")
    return 0


def _parser() -> argparse.ArgumentParser:
    """Argomenti della riga di comando (sottocomandi check, run, summary, compare)."""
    parser = argparse.ArgumentParser(prog="rq2_dk_run_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "run", "summary", "compare"):
        p = sub.add_parser(name)
        p.add_argument("--drive-root", required=True)
        p.add_argument("--repo-dir")
        p.add_argument("--namespace", help="cartella dei nuovi K sotto drive-root "
                       "(default: data/rq2_dk_ablation_v1)")
        p.add_argument("--models", nargs="+")
        p.add_argument("--harnesses", nargs="+")
        p.add_argument("--cases", nargs="+")
        if name == "run":
            p.add_argument("--max-stages", type=int)
            p.add_argument("--time-budget-minutes", type=float)
            p.add_argument("--allow-dirty", action="store_true")
    return parser


def main(argv=None) -> int:
    """Punto d'ingresso: `check` e `run` richiedono anche `--repo-dir`."""
    args = _parser().parse_args(argv)
    if args.command in ("check", "run") and not args.repo_dir:
        print("--repo-dir obbligatorio")
        return 2
    return {"check": cmd_check, "run": cmd_run, "summary": cmd_summary,
            "compare": cmd_compare}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
