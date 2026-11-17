"""RQ2-V5: riga di comando per Colab (check, run, summary).

  python -m evaluation.rq2_v5_run_cli check   --drive-root ... --repo-dir ... [--models gemini ...]
  python -m evaluation.rq2_v5_run_cli run     --drive-root ... --repo-dir ... --models gemini --harnesses A0 --cases cloudbed-1_q032 --max-stages 3
  python -m evaluation.rq2_v5_run_cli summary --drive-root ...

`check` e `summary` non chiamano mai un provider. `run` chiama i provider solo
per gli stage selezionati, uno alla volta, con claim create-only.
Le chiavi si leggono SOLO dall'ambiente (mai stampate, mai salvate).

Comandi
-------
- `check`: verifica offline che tutto sia pronto (runtime pinned, dati GT-free, prompt, chiavi
  presenti sotto forma di vero/falso, repository pulito); esce con 2 se manca una chiave o il
  checkout non e' pulito;
- `run`: esegue gli stage selezionati con il runner a matrice; rifiuta se il checkout non e' pulito
  (salvo `--allow-dirty`) o se manca una chiave; scrive/verifica il manifest dell'esperimento;
- `summary`: stampa il riepilogo degli esiti gia' registrati (nessuna chiamata);
- `release-orphan`: sblocca UN claim orfano, con motivazione obbligatoria e traccia (mai automatico).
I filtri `--models --harnesses --cases --stages` restringono il piano; `--namespace` sceglie una
cartella di archivio diversa (un pilota usa un archivio separato, per non consumare gli stage reali).
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

# Variabili d'ambiente che possono contenere la chiave API di ciascun provider.
KEY_ENV = {"google": ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
           "anthropic": ("ANTHROPIC_API_KEY",)}
# Pacchetti di cui si registra la versione nel manifest (ambiente pinned).
PACKAGES = ("langchain-core", "langgraph", "langchain-anthropic",
            "langchain-google-genai", "anthropic", "google-genai")
# Nome del file manifest nella cartella dell'archivio.
MANIFEST = "manifest_v1.json"
# Campi che devono restare identici in tutti i lotti dello stesso esperimento.
INVARIANTS = ("protocol", "plan_preview_sha256", "format_policy",
              "format_version", "retry_policy", "retry_max_attempts",
              "C_system_prompt_sha256",
              "K_system_prompt_sha256", "d_budgets")


def _git(repo: Path, *args: str) -> str:
    """Esegue `git -C <repo> <args>` e restituisce l'output senza spazi finali.

    Non solleva eccezioni se git fallisce (`check=False`): in quel caso l'output e' vuoto.
    """
    out = subprocess.run(["git", "-C", str(repo), *args],
                         capture_output=True, text=True, check=False)
    return out.stdout.strip()


def _store_root(drive_root: Path, namespace: str | None = None) -> Path:
    """Archivio del run: di default quello scientifico; un pilota ne usa uno
    separato, cosi' non consuma gli stage reali (che sono create-only)."""
    return drive_root / (namespace or mr.NAMESPACE.as_posix())


def _key_present(provider: str) -> bool:
    """True se per il provider ("google" o "anthropic") c'e' almeno una chiave non vuota
    nell'ambiente. Restituisce solo vero/falso: la chiave non viene mai letta fuori da qui."""
    return any(bool(os.environ.get(name, "").strip())
               for name in KEY_ENV[provider])


def _secrets() -> list[str]:
    """Valori delle chiavi presenti nell'ambiente, per oscurarli nei messaggi di errore."""
    return [os.environ[name] for names in KEY_ENV.values() for name in names
            if os.environ.get(name)]


def _versions() -> dict:
    """Versione installata di ogni pacchetto di `PACKAGES` (None se non installato)."""
    found = {}
    for name in PACKAGES:
        try:
            found[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            found[name] = None
    return found


def build_manifest(repo: Path, plan: dict) -> dict:
    """Costruisce il manifest dell'esperimento (identita' del run, non i risultati).

    Argomenti: `repo` (checkout del codice) e `plan` (piano offline, con `preview_sha256`).
    Contiene protocollo, versione del runner, hash del piano, politiche di formato e di retry,
    hash dei prompt C/K, budget di D, commit del codice, versione di Python e dei pacchetti.
    """
    # Import locale: il modulo dell'esecutore importa LangChain, che serve solo qui.
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
    """Create-only al primo lotto; dai lotti successivi verifica gli invarianti.

    Restituisce "CREATED" (manifest scritto) o "MATCHES" (gli `INVARIANTS` coincidono con quelli
    salvati); se differiscono interrompe il programma con `SystemExit` e l'elenco dei campi.
    """
    path = root / MANIFEST
    root.mkdir(parents=True, exist_ok=True)
    # Primo lotto: si scrive il manifest (create-only, mai sovrascritto).
    if not path.exists():
        mr.StageStore._write_new(path, manifest)
        return "CREATED"
    # Lotti successivi: i campi invarianti devono essere identici a quelli del primo lotto.
    saved = json.loads(path.read_text(encoding="utf-8"))
    drift = [k for k in INVARIANTS if saved.get(k) != manifest.get(k)]
    if drift:
        raise SystemExit("MANIFEST DIVERSO dai lotti precedenti: " + str(drift))
    return "MATCHES"


def _plan_rows() -> tuple[dict, list[dict]]:
    """Piano offline V4 (4 incidenti discovery) e le sue righe, gia' validato.

    Restituisce la coppia (piano completo, righe/stage in ordine).
    """
    plan = build_offline_v4_discovery_plan()
    rows = plan["entries"]
    mr.validate_plan(rows)
    return plan, rows


def _select(rows, args):
    """Applica alle righe del piano i filtri della riga di comando (modelli, harness, casi, stage)."""
    return mr.select_rows(
        rows, models=args.models, harnesses=args.harnesses,
        cases=args.cases, stages=args.stages,
    )


def cmd_check(args) -> int:
    """Nessuna API: runtime pinned, dati GT-free, prompt, chiavi (solo True/False).

    Restituisce 0 se ogni provider selezionato ha la chiave e il checkout e' pulito, 2 altrimenti.
    """
    # Import locali: richiedono LangChain/SDK, che servono solo ai comandi `check` e `run`.
    from evaluation.rq2_model_factory import assert_exact_runtime_snapshot
    from evaluation.rq2_v5_stage_executor import V5StageExecutor
    plan, rows = _plan_rows()
    selected = _select(rows, args)
    report = {"plan_stages": len(rows), "selected_stages": len(selected)}
    # Le versioni dei pacchetti devono essere esattamente quelle pinned (altrimenti solleva).
    assert_exact_runtime_snapshot()
    report["runtime_snapshot"] = "OK"
    # Per ogni provider selezionato: la chiave e' presente? (solo vero/falso, mai il valore)
    providers = sorted({r["model_provider"] for r in selected})
    report["keys_present"] = {p: _key_present(p) for p in providers}
    drive_root, repo = Path(args.drive_root), Path(args.repo_dir)
    executor = V5StageExecutor(data_dir=drive_root, repo_dir=repo)
    # Si prepara (offline) ogni stage D selezionato: se la configurazione e' sbagliata si scopre ora.
    prepared = 0
    for row in selected:
        if row["stage"] == "D":
            executor.prepare(row, {})
            prepared += 1
    report["d_stages_prepared_ok"] = prepared
    # Stato del repository: commit attuale e checkout pulito.
    report["git_head"] = _git(repo, "rev-parse", "HEAD")
    report["git_clean"] = _git(repo, "status", "--porcelain") == ""
    report["manifest_would_be"] = build_manifest(repo, plan)["created_commit"]
    print(json.dumps(report, indent=2, ensure_ascii=False))
    ok = all(report["keys_present"].values()) and report["git_clean"]
    return 0 if ok else 2


def cmd_run(args) -> int:
    """Esegue gli stage selezionati (chiama i provider, uno stage alla volta).

    Restituisce 0 a lotto concluso, 2 se rifiuta di partire (checkout non pulito senza
    `--allow-dirty`, oppure chiave mancante per un provider).

    Passi: piano e selezione; controlli di sicurezza prima di spendere; manifest (creato o
    verificato); esecuzione con `run_matrix`; riepilogo e orfani.
    """
    from evaluation.rq2_model_factory import assert_exact_runtime_snapshot
    from evaluation.rq2_v5_stage_executor import V5StageExecutor
    plan, rows = _plan_rows()
    selected = _select(rows, args)
    repo = Path(args.repo_dir)
    # Controlli di sicurezza: checkout pulito e chiave presente per ogni provider coinvolto.
    if _git(repo, "status", "--porcelain") and not args.allow_dirty:
        print("Il checkout non e' pulito: run rifiutato.")
        return 2
    for provider in sorted({r["model_provider"] for r in selected}):
        if not _key_present(provider):
            print(f"Chiave mancante per il provider {provider}: run rifiutato.")
            return 2
    assert_exact_runtime_snapshot()
    # Archivio del run e manifest: al primo lotto si crea, poi si verificano gli invarianti.
    root = _store_root(Path(args.drive_root), args.namespace)
    print("Manifest:", ensure_manifest(root, build_manifest(repo, plan)))
    store = mr.StageStore(root)
    executor = V5StageExecutor(data_dir=Path(args.drive_root), repo_dir=repo)
    # Esecuzione del lotto, con i tetti di stage e di tempo (minuti -> secondi).
    outcome = mr.run_matrix(
        selected, plan=rows, store=store, executor=executor,
        source_commit=_git(repo, "rev-parse", "HEAD"),
        max_stages=args.max_stages,
        time_budget_seconds=(args.time_budget_minutes * 60
                             if args.time_budget_minutes else None),
        secrets=_secrets(),
    )
    # Resoconto: esito del lotto, riepilogo dell'intero piano ed eventuali orfani.
    print(json.dumps(outcome, indent=2))
    print(mr.format_summary(mr.summarize(rows, store)))
    _print_orphans(store, rows)
    return 0


def _print_orphans(store, rows) -> None:
    """Elenca gli stage con claim ma senza record (run interrotto)."""
    orphans = store.orphans([r["stage_id"] for r in rows])
    if not orphans:
        return
    print()
    print(f"ATTENZIONE: {len(orphans)} stage orfani (claim senza record). "
          "Non vengono mai rieseguiti da soli. Se il run e' stato interrotto "
          "e vuoi sbloccarli: comando release-orphan, con motivazione.")
    for stage_id in orphans:
        print("  -", stage_id)


def cmd_release_orphan(args) -> int:
    """Sblocca UN claim orfano, con motivazione e traccia (mai in automatico).

    Restituisce 0 se lo sblocco riesce, 2 se lo stage non e' nel piano o `release_orphan` rifiuta.
    """
    _, rows = _plan_rows()
    if args.stage_id not in {r["stage_id"] for r in rows}:
        print("Stage non presente nel piano: rifiutato.")
        return 2
    store = mr.StageStore(_store_root(Path(args.drive_root), args.namespace))
    try:
        entry = store.release_orphan(args.stage_id, args.reason)
    except mr.StoreError as exc:
        print("Rifiutato:", exc)
        return 2
    print(json.dumps(entry, indent=2, ensure_ascii=False))
    return 0


def cmd_summary(args) -> int:
    """Stampa il riepilogo degli esiti gia' registrati per gli stage selezionati.
    Sola lettura: nessuna chiamata a provider. Restituisce sempre 0."""
    _, rows = _plan_rows()
    store = mr.StageStore(_store_root(Path(args.drive_root), args.namespace))
    selected = _select(rows, args)
    print(mr.format_summary(mr.summarize(selected, store)))
    _print_orphans(store, selected)
    return 0


def _parser() -> argparse.ArgumentParser:
    """Costruisce il parser: un sotto-comando per ognuno di check, run, summary, release-orphan."""
    parser = argparse.ArgumentParser(prog="rq2_v5_run_cli")
    sub = parser.add_subparsers(dest="command", required=True)
    # Opzioni comuni a check, run e summary (le ultime tre solo per `run`).
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
    # Sblocco di un claim orfano: richiede lo stage e una motivazione esplicita.
    rel = sub.add_parser("release-orphan")
    rel.add_argument("--drive-root", required=True)
    rel.add_argument("--namespace")
    rel.add_argument("--stage-id", required=True)
    rel.add_argument("--reason", required=True,
                     help="motivazione esplicita (almeno 10 caratteri)")
    return parser


def main(argv=None) -> int:
    """Punto d'ingresso: legge gli argomenti ed esegue il sotto-comando scelto.

    `argv` e' la lista di argomenti (None = quelli del processo). Restituisce il codice di uscita:
    0 = ok; 2 = rifiuto o controllo non superato.
    """
    args = _parser().parse_args(argv)
    # `check` e `run` hanno bisogno del checkout del codice.
    if args.command in ("check", "run") and not args.repo_dir:
        print("--repo-dir obbligatorio")
        return 2
    return {"check": cmd_check, "run": cmd_run, "summary": cmd_summary,
            "release-orphan": cmd_release_orphan}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
