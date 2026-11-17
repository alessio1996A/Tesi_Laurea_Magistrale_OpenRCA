# -*- coding: utf-8 -*-
"""Controllo di sicurezza per il refactoring dei commenti: dimostra che il codice NON e' cambiato.

Cosa verifica
-------------
1. I 25 file bloccati da hash non sono stati toccati: i 13 con SHA-256 congelato (docs/CONSOLIDAMENTO..., sez. 7.2) e i
   13 con hash git SHA-1 verificato da `rq2_protocol_identity_preflight` (uno, `agent/tools.py`, e' in entrambi gli elenchi).
   In piu', cerca da solo nel codice ogni hash che coincide con un file sorgente del progetto (protezioni non elencate).
2. Nessun file di `src/` e' stato cancellato, rinominato o spostato rispetto al riferimento (`--base`).
3. Per ogni file `.py` modificato di `src/`, l'albero sintattico (AST) e' IDENTICO a quello del riferimento una volta
   tolte le docstring. Quindi sono cambiati soltanto commenti `#`, docstring e spazi: nessuna istruzione, nome,
   stringa del codice, prompt, etichetta o costante.
4. Avviso (non errore) se un modulo usa `__doc__` e la sua docstring e' cambiata: cambierebbe il testo di `--help`.

Uso (PowerShell, dalla radice del progetto)
    python .\\tools\\refactoring\\controlla_solo_commenti.py --base origin/feature/rq2a-offline-scoring-2026-11-17
    python .\\tools\\refactoring\\controlla_solo_commenti.py --base HEAD        # modifiche non ancora committate
Colab:  !python tools/refactoring/controlla_solo_commenti.py --base origin/feature/rq2a-offline-scoring-2026-11-17
Codice di uscita 0 = tutto in regola; 1 = almeno un controllo fallito.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import subprocess
import re
import sys
from pathlib import Path

# SHA-256 congelati (docs/CONSOLIDAMENTO_SCIENTIFICO_E_OPERATIVO_2026-11-16.md, sez. 7.2). Percorsi relativi a `src/`.
FROZEN_SHA256 = {
    "evaluation/rq2_k_l1_preflight.py": "673ab046419f8866665c83b383c22f41a072efdbb1d89a7a92b6ea3d07953e46",
    "evaluation/rq2_k_l1_protocol.py": "8de0ab363bad887512e6cd2811045210f709b569ad8e714092114306f7991065",
    "evaluation/rq2_k_records.py": "3a0a1641dfd6cef7660ab75794b0518462f8391e969e4326f024ed3eb3451982",
    "evaluation/rq2_k_rule_evaluation.py": "43b1dd98379ff49a50ccabada609b2e05ae4193a57bad03f4a5828fd2acda5de",
    "evaluation/rq2_k_rule_executor.py": "ed105d707dabb91f700409565fb55f075fa474fb0b712129a3d5798c1c3df1d8",
    "evaluation/rq2_rule_group_scorer.py": "c66c921d6b7e9d7274a2cedd2f7092976818b44cd3b08755c344b044648a6020",
    "evaluation/rq2_k_l2_execute.py": "1b79ed35068b12b906371e7950badd3926be6e7ad03f86859303fa04c7d371e4",
    "evaluation/rq2_k_l2_scoring.py": "6287f51abf0dbbec1d19d2eb3f7094063a542fdfc5f717a6eea40c19d7eec388",
    "agent/tools.py": "ec677c2f26d36109df3a6c614f5903333ddaa1b9e13e8c2cce844e5de464fab0",
    "evaluation/ood_class_inventory.py": "548b9fdcdb87f00a9c5bf917c17e0abbde08b97b5732c26d632903f761a55d81",
    "evaluation/ood_holdout_preflight.py": "10d4f328e530753c1b6b2805bf3ed6302e7291b1be148620c2cbdd848bd515d7",
    "evaluation/rq2_k_catalog.py": "c11d8b96f7210f6249ab9e8760d653e7442f14c2250263e48e3b08f2bc38e11f",
    "evaluation/v2_case_window_audit.py": "ebddc1312543e5b8eb8847c1c4267549681b895dbad93e82b4685abc501b68f0",
}

# Hash git (blob SHA-1, a-capo normalizzati a LF) dei sorgenti RQ1 verificati da
# `evaluation/rq2_protocol_identity_preflight.py` (commit di riferimento e4845e7). Percorsi relativi a `src/`.
FROZEN_BLOB_SHA1 = {
    "evaluation/evaluation20_preregister.py": "80bd3b0cac7150c76c2ba102329708e3ddb544ef",
    "evaluation/evaluation20_campaign.py": "e65603acc7fc26a62e7f5534af2fcf5d359eda9d",
    "evaluation/experiment_runner.py": "32f4a870a52b65edc66c52e5a5932cf87b42de56",
    "evaluation/experiment_config.py": "a488d180ae7891f4370c2d7dbc932161e1b187ae",
    "agent/model_factory.py": "05308d5740763db0444556dcb7330d8fb4c308ec",
    "agent/prompts.py": "f68eee79a2382828a11b446c19972e73794db9a3",
    "agent/graph_engine.py": "415bad3feaf77cd70da72308ec2219c05ca1b956",
    "agent/tool_factory.py": "70b6612d4438d7ebcf3b363bf712817854ae3e28",
    "agent/tools.py": "6e4617770d49476ebd4112d486d6cd1f4d079d34",
    "output/v2_task_contract.py": "9be3002a9e7d6d0d733662d953d462b4ee828c0d",
    "harness/evidence_builder.py": "fc9d05a9f6562823170cc6ed7ed29a2452c0eb1e",
    "harness/signal_catalog.py": "c1fec771c9d8876bc2e33eb49e7ddef067bb3963",
    "harness/rules/rule_container_cpu.py": "b7e560a4bd08dd5677c81774650205ff3b7ec8d7",
}
HEX_LITERAL = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def blob_sha1(content: bytes) -> str:
    """SHA-1 di un oggetto git `blob`, come lo calcola git (e come lo calcola il preflight, con a-capo LF)."""
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\x00" + content).hexdigest()


def hash_guarded_sources(src: Path, tests_dir: Path) -> dict[str, str]:
    """Trova nel codice (esclusi i test) ogni hash scritto a mano che coincide con un sorgente `.py` di `src/`.

    Restituisce {percorso relativo del sorgente protetto: hash che lo protegge}. Serve a scoprire protezioni
    non elencate sopra: se un file e' protetto da un hash, non si puo' nemmeno aggiungere un commento.
    """
    digests: dict[str, str] = {}
    for path in src.rglob("*.py"):
        raw = path.read_bytes()
        lf = raw.replace(b"\r\n", b"\n")
        rel = path.relative_to(src).as_posix()
        for content in (raw, lf):
            digests[hashlib.sha256(content).hexdigest()] = rel
            digests[blob_sha1(content)] = rel
    found: dict[str, str] = {}
    for path in src.rglob("*.py"):
        if tests_dir in path.parents:
            continue
        for literal in HEX_LITERAL.findall(path.read_text(encoding="utf-8")):
            if literal in digests:
                found[digests[literal]] = literal
    return found


def git(root: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True)
    return out.stdout.decode("utf-8")


def git_bytes(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True).stdout


def strip_docstrings(tree: ast.AST) -> ast.AST:
    """Toglie la docstring (prima istruzione costituita da una sola stringa) da modulo, classi e funzioni."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
    return tree


def canonical(source: str) -> str:
    return ast.dump(strip_docstrings(ast.parse(source)), include_attributes=False)


def first_difference(a: str, b: str) -> str:
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return f"... {a[max(0, i - 60):i + 60]!r}  <->  {b[max(0, i - 60):i + 60]!r}"
    return "lunghezze diverse"


def uses_dunder_doc(source: str) -> bool:
    return any(isinstance(n, ast.Name) and n.id == "__doc__" for n in ast.walk(ast.parse(source)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Verifica che il refactoring abbia cambiato solo commenti e docstring")
    ap.add_argument("--base", required=True, help="riferimento git (tag, branch o commit) con il codice originale")
    ap.add_argument("--root", default=".", help="radice del repository (default: cartella corrente)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    problems, warnings = [], []

    # Prima di tutto: il riferimento git deve esistere e `root` deve essere un repository.
    try:
        git(root, "rev-parse", "--verify", "--quiet", f"{args.base}^{{commit}}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"ERRORE: il riferimento git `{args.base}` non esiste in {root} (oppure git non e' installato).")
        print("  Controlla i nomi con `git branch -a` e `git tag`; per le modifiche non ancora committate usa `--base HEAD`.")
        return 2

    print(f"[0] riferimento: {args.base} = {git(root, 'rev-parse', '--short', args.base + '^{commit}').strip()} "
          f"(se e' un ramo locale, controlla che sia aggiornato: `git fetch origin`, meglio usare `origin/<ramo>`)")

    # 1. Hash dei file bloccati (calcolati sul contenuto del file di lavoro, byte per byte).
    def sha256_ok(path: Path, expected: str) -> bool:
        """True se l'hash coincide, calcolato sui byte cosi' come sono oppure con a-capo normalizzati a LF."""
        if not path.is_file():
            return False
        raw = path.read_bytes()
        return expected in (hashlib.sha256(raw).hexdigest(),
                            hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest())

    bad_sha = [rel for rel, expected in FROZEN_SHA256.items()
               if not sha256_ok(root / "src" / rel, expected)]
    for rel in bad_sha:
        problems.append(f"FILE BLOCCATO (SHA-256) MODIFICATO O ASSENTE: src/{rel}")
    print(f"[1a] file bloccati con SHA-256 del consolidamento: {len(FROZEN_SHA256) - len(bad_sha)}/{len(FROZEN_SHA256)} identici")
    bad_blob = []
    for rel, expected in FROZEN_BLOB_SHA1.items():
        path = root / "src" / rel
        ok = path.is_file() and blob_sha1(path.read_bytes().replace(b"\r\n", b"\n")) == expected
        if not ok:
            bad_blob.append(rel)
            problems.append(f"FILE BLOCCATO (hash git RQ1) MODIFICATO O ASSENTE: src/{rel}")
    print(f"[1b] file bloccati con hash git del preflight RQ1: {len(FROZEN_BLOB_SHA1) - len(bad_blob)}/{len(FROZEN_BLOB_SHA1)} identici")
    guarded = hash_guarded_sources(root / "src", root / "src" / "tests")
    known = set(FROZEN_SHA256) | set(FROZEN_BLOB_SHA1)
    for rel in sorted(set(guarded) - known):
        problems.append(f"PROTEZIONE A HASH NON ELENCATA: src/{rel} e' citato da un hash nel codice; "
                        f"aggiungilo a questo controllo e non modificarlo")
    # un file protetto che il codice cita con un hash ma che e' stato modificato non coincide piu' con nessun hash:
    # lo si vede dal confronto con `--base` (vedi punto 3), qui si segnala solo il numero di protezioni trovate.
    print(f"[1c] sorgenti protetti scoperti automaticamente dal codice: {len(guarded)} (non elencati: {len(set(guarded) - known)})")
    print("    (se su Windows qualcuno risultasse diverso, controlla la conversione degli a-capo: `git config core.autocrlf false`)")

    # 2. Cancellazioni, rinomine, spostamenti.
    status = git(root, "diff", "--name-status", "-M", args.base, "--", "src").splitlines()
    changed = []
    for line in status:
        parts = line.split("\t")
        code, paths = parts[0], parts[1:]
        if code.startswith(("D", "R", "C")):
            problems.append(f"CANCELLATO/RINOMINATO/SPOSTATO: {' -> '.join(paths)}")
        elif code == "A":
            warnings.append(f"file nuovo (non confrontabile): {paths[0]}")
        elif code == "M" and paths[0].endswith(".py"):
            changed.append(paths[0])
    print(f"[2] file di src/ modificati: {len(changed)}; cancellati/rinominati: "
          f"{sum(p.startswith('CANCELLATO') for p in problems)}")

    # 3. Albero sintattico invariato (docstring escluse).
    ok_count = 0
    for rel in sorted(changed):
        old = git_bytes(root, "show", f"{args.base}:{rel}").decode("utf-8")
        new = (root / rel).read_text(encoding="utf-8")
        try:
            same = canonical(old) == canonical(new)
        except SyntaxError as exc:
            problems.append(f"ERRORE DI SINTASSI: {rel}: {exc}")
            continue
        if same:
            ok_count += 1
            if uses_dunder_doc(new) and ast.get_docstring(ast.parse(old)) != ast.get_docstring(ast.parse(new)):
                warnings.append(f"{rel}: usa __doc__ e la docstring del modulo e' cambiata (cambia il testo di --help)")
        else:
            problems.append(f"CODICE CAMBIATO (non solo commenti): {rel}\n      {first_difference(canonical(old), canonical(new))}")
    print(f"[3] file con SOLO commenti/docstring cambiati: {ok_count}/{len(changed)}")

    for w in warnings:
        print("  avviso:", w)
    for p in problems:
        print("  ERRORE:", p)
    print("\nESITO:", "TUTTO IN REGOLA" if not problems else f"{len(problems)} PROBLEMI: non committare")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
