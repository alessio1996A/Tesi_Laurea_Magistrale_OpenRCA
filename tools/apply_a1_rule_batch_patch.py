"""Safely inject the six-rule A1 adapter into experiment_runner.py.

Commands:
    python tools/apply_a1_rule_batch_patch.py --apply
    python tools/apply_a1_rule_batch_patch.py --stage-only

--stage-only stages solely the injected lines from HEAD, avoiding unrelated
unstaged cosmetic edits in experiment_runner.py.
"""
from __future__ import annotations

import argparse
import difflib
from pathlib import Path
import subprocess

RELATIVE = "src/evaluation/experiment_runner.py"
ANCHOR = '''        if (
            evidence_report["versione"]
            != "unified_evidence_v2"
        ):'''
INJECTION = '''        # =====================================================
        # 9 BIS. SEI REGOLE DIAGNOSTICHE OFFLINE (A1-R)
        # =====================================================
        # Solo telemetria nella finestra corrente: nessuna ground truth.
        # Non modifica i tool, il modello, o il ramo A0.
        from harness.rule_batch import costruisci_evidenze_regole

        evidence_report["regole_diagnostiche_v0"] = costruisci_evidenze_regole(
            df_nodi=df_nodi,
            df_container=df_container,
            start_unix=int(inizio),
            end_unix=int(fine),
        )

'''
MARKER = 'evidence_report["regole_diagnostiche_v0"] = costruisci_evidenze_regole('


def inject(content: str) -> str:
    if MARKER in content:
        raise RuntimeError("Patch A1-R gia' presente; applicazione interrotta")
    if content.count(ANCHOR) != 1:
        raise RuntimeError("Punto di inserimento A1 ambiguo o assente: non modifico il runner")
    return content.replace(ANCHOR, INJECTION + ANCHOR, 1)


def git(*args, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], text=True, input=input_text,
        encoding="utf-8", capture_output=True, check=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--apply", action="store_true")
    group.add_argument("--stage-only", action="store_true")
    args = parser.parse_args()

    target = Path(RELATIVE)
    if not target.is_file():
        raise SystemExit(f"File non trovato: {target}; eseguire dalla root del repository")

    if args.apply:
        raw = target.read_bytes()
        newline = "\r\n" if b"\r\n" in raw else "\n"
        # Normalize only in memory, then restore the same newline convention.
        original = raw.decode("utf-8").replace("\r\n", "\n")
        updated = inject(original).replace("\n", newline)
        target.write_bytes(updated.encode("utf-8"))
        print("Integrazione A1-R aggiunta al runner; A0 e i tool sono invariati.")
        print("Per stage isolato: python tools/apply_a1_rule_batch_patch.py --stage-only")
        return

    if MARKER not in target.read_text(encoding="utf-8"):
        raise SystemExit("Applicare prima --apply, poi --stage-only")
    if git("diff", "--cached", "--quiet", "--", RELATIVE).returncode != 0:
        raise SystemExit("Runner gia' modificato nell'indice Git: stage-only interrotto")
    original = subprocess.run(
        ["git", "show", f"HEAD:{RELATIVE}"], capture_output=True, check=False
    )
    if original.returncode != 0:
        raise SystemExit("Impossibile leggere runner da HEAD: " + original.stderr.decode("utf-8", errors="replace"))
    original_text = original.stdout.decode("utf-8")
    newline = "\r\n" if b"\r\n" in original.stdout else "\n"
    updated = inject(original_text.replace("\r\n", "\n")).replace("\n", newline)
    patch = "".join(difflib.unified_diff(
        original_text.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=f"a/{RELATIVE}",
        tofile=f"b/{RELATIVE}",
    ))
    validation = git("apply", "--cached", "--check", "-", input_text=patch)
    if validation.returncode != 0:
        raise SystemExit("La patch non e' applicabile allo stage: " + validation.stderr)
    outcome = git("apply", "--cached", "-", input_text=patch)
    if outcome.returncode != 0:
        raise SystemExit("Impossibile stage isolato: " + outcome.stderr)
    print("Stage completato: SOLO le righe dell'integrazione A1-R, senza le modifiche cosmetiche locali.")


if __name__ == "__main__":
    main()
