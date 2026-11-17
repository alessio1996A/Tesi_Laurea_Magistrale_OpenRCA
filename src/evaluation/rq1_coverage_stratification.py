"""RQ1 esplorativo: l'effetto delle otto regole, per copertura della classe del guasto.

Domanda unica: nelle 295 run congelate di EVALUATION20, il vantaggio di A1_8R su A1
(e di A1 su A0) si concentra negli incidenti la cui classe e' coperta dalle otto
regole? E' un'analisi POST HOC di dati gia' congelati: nessuna chiamata a modelli,
nessuna modifica di record, regole o soglie; scrive solo un report create-only.

Due comandi:
  strata      ri-punteggia le run con lo scorer ufficiale (commit e hash fissati),
              verifica di riprodurre la tabella gia' riportata (medie per modello e
              variante), poi divide i 20 incidenti in coperti / non coperti / misti.
  separation  controlla, in forma aggregata (nessun case_id), che le quattro classi
              tenute fuori (RQ2) non compaiano nei gruppi development, evaluation
              e mixed_quarantine dello split.

ACCEDONO alla ground truth (query.csv e record.csv di Market.zip): vanno eseguiti
in un processo separato dall'inferenza e MAI importati da agente, tool o prompt.

Limiti dichiarati (anche nel report):
  * la classe di un incidente e' quella della riga di record.csv piu' le etichette
    note trovate in scoring_points; un guasto aggiuntivo di classe sconosciuta in un
    incidente multiguasto senza motivo nei punti di punteggio non e' visibile;
  * strati piccoli, una esecuzione per cella: confronti descrittivi, nessun intervallo;
  * la stratificazione e' decisa dopo aver visto i risultati complessivi.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from evaluation.ood_class_inventory import TARGETS, _normalized
from evaluation.rq2_a_offline_scoring import (
    OFFICIAL_COMMIT, OFFICIAL_EVALUATE_SHA256, QUERY_COLUMNS, RECORD_COLUMNS,
    ScoringError, _read_member, load_official_evaluate, write_report_create_only,
    write_text_create_only,
)
from evaluation.v2_case_window_audit import (
    MANIFEST_COLUMNS, SPLIT_COLUMNS, _read_csv,
)
from harness.rule_batch import RULE_SPECS

PROTOCOL = "openrca_harness_evaluation20_cross_model_v1"
MODELS = ("gemini", "sonnet", "haiku")
VARIANTS = ("A0", "A1", "A1_8R", "A1_8R_Planning", "A1_PAVE")
COVERED = tuple(spec[4] for spec in RULE_SPECS)   # le otto classi con regola
HELD_OUT = tuple(TARGETS)                         # le quattro classi di RQ2
VERSION = "rq1_coverage_stratification_v1"
STRATA = ("coperta", "non_coperta", "mista")

# Tabella gia' riportata (consolidamento, sez. 3.1): (run valutate, score medio).
REPORTED = {
    ("sonnet", "A0"): (20, 0.1165), ("sonnet", "A1"): (20, 0.3960),
    ("sonnet", "A1_8R"): (20, 0.4335), ("sonnet", "A1_8R_Planning"): (20, 0.3665),
    ("sonnet", "A1_PAVE"): (20, 0.5040),
    ("haiku", "A0"): (20, 0.1415), ("haiku", "A1"): (20, 0.2290),
    ("haiku", "A1_8R"): (20, 0.2750), ("haiku", "A1_8R_Planning"): (20, 0.2415),
    ("haiku", "A1_PAVE"): (20, 0.3210),
    ("gemini", "A0"): (19, 0.0789), ("gemini", "A1"): (19, 0.1668),
    ("gemini", "A1_8R"): (18, 0.1156), ("gemini", "A1_8R_Planning"): (20, 0.2205),
    ("gemini", "A1_PAVE"): (19, 0.2147),
}
TOLERANCE = 5.1e-5   # le medie riportate hanno quattro decimali


# ------------------------------------------------------------------ lettura

def _file_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plan_path(data_dir: Path) -> Path:
    return Path(data_dir) / "data/protocols/evaluation20" / (PROTOCOL + "_plan_v1.json")


def result_paths(data_dir: Path, run_id: str) -> tuple[Path, Path]:
    if not re.fullmatch(r"[A-Za-z0-9_.\-]+", run_id):
        raise ScoringError("run_id non sicuro")
    folder = Path(data_dir) / "data/results/evaluation20" / PROTOCOL
    return folder / (run_id + ".json"), folder / (run_id + ".sha256.json")


def load_plan(data_dir: Path, expected_runs: int = 300, expected_cases: int = 20) -> dict:
    path = plan_path(data_dir)
    if not path.is_file():
        raise ScoringError("Piano EVALUATION20 non trovato: " + str(path))
    plan = json.loads(path.read_text(encoding="utf-8"))
    runs, cases = plan.get("runs"), plan.get("cases")
    if (not isinstance(runs, list) or len(runs) != expected_runs
            or not isinstance(cases, list) or len(cases) != expected_cases):
        raise ScoringError("Piano non conforme: run o casi diversi dall'atteso")
    if len({r["run_id"] for r in runs}) != len(runs):
        raise ScoringError("run_id duplicati nel piano")
    case_ids = {c["case_id"] for c in cases}
    if any(r["case_id"] not in case_ids for r in runs):
        raise ScoringError("Run su un caso fuori dal piano")
    return plan


def load_result(data_dir: Path, run: dict) -> dict | None:
    """Risultato di una run, con hash verificato. None se non e' mai stato scritto."""
    output, sidecar = result_paths(data_dir, run["run_id"])
    if not output.is_file():
        return None
    if not sidecar.is_file():
        raise ScoringError("Manca lo sha256 del risultato: " + run["run_id"])
    expected = json.loads(sidecar.read_text(encoding="utf-8")).get("result_sha256")
    if expected != _file_sha(output):
        raise ScoringError("Risultato alterato (hash diverso): " + run["run_id"])
    result = json.loads(output.read_text(encoding="utf-8"))
    if result.get("case_id") != run["case_id"] or result.get("variant") != run["variant"]:
        raise ScoringError("Risultato non coerente col piano: " + run["run_id"])
    return result


def _row_of(case_id: str) -> tuple[str, int]:
    match = re.fullmatch(r"(cloudbed-[12])_q(\d+)", case_id)
    if match is None:
        raise ScoringError("case_id malformato: " + case_id)
    return match.group(1), int(match.group(2))


def _archive_rows(zf: ZipFile) -> dict[str, tuple[list[dict], list[dict]]]:
    rows = {}
    for bed in ("cloudbed-1", "cloudbed-2"):
        base = f"Market/{bed}"
        query = _read_member(zf, base + "/query.csv", QUERY_COLUMNS)
        record = _read_member(zf, base + "/record.csv", RECORD_COLUMNS)
        if len(query) != len(record):
            raise ScoringError("query.csv e record.csv di righe diverse: " + bed)
        rows[bed] = (query, record)
    return rows


def load_references(market_zip: Path, cases: list[dict]) -> dict[str, dict]:
    """Ground truth dei casi del piano (riga = numero nel case_id, task verificato)."""
    out: dict[str, dict] = {}
    with ZipFile(Path(market_zip), "r") as zf:
        rows = _archive_rows(zf)
    for case in cases:
        bed, idx = _row_of(case["case_id"])
        query, record = rows[bed]
        if not 0 <= idx < len(query):
            raise ScoringError("Riga fuori archivio: " + case["case_id"])
        if query[idx]["task_index"] != case["task_index"]:
            raise ScoringError("Task diverso dal piano: " + case["case_id"])
        out[case["case_id"]] = {
            "task_index": query[idx]["task_index"],
            "scoring_points": query[idx]["scoring_points"],
            "row_reason": record[idx]["reason"].strip(),
        }
    return out


# ------------------------------------------------------------------ classi

def _known() -> dict[str, str]:
    return {_normalized(label): label for label in COVERED + HELD_OUT}


def case_classes(reference: dict) -> dict:
    """Etichette note del caso e strato di copertura (vedi i limiti nel docstring)."""
    known = _known()
    row_norm = _normalized(reference["row_reason"])
    found: set[str] = set()
    if row_norm in known:
        found.add(known[row_norm])
    text = _normalized(reference["scoring_points"])
    for norm, label in known.items():
        if re.search(r"(?<![a-z0-9])" + re.escape(norm) + r"(?![a-z0-9])", text):
            found.add(label)
    covered = {x for x in found if x in COVERED}
    row_unknown = row_norm not in known     # es. classi di rete senza regola
    if covered and not (found - covered) and not row_unknown:
        stratum = "coperta"
    elif not covered:
        stratum = "non_coperta"
    else:
        stratum = "mista"
    return {"labels": sorted(found), "row_class_known": not row_unknown,
            "held_out_classes_in_case": sorted(x for x in found if x in HELD_OUT),
            "stratum": stratum}


# ------------------------------------------------------------------ punteggi

def score_runs(data_dir: Path, plan: dict, references: dict[str, dict], evaluate) -> list[dict]:
    rows = []
    for run in plan["runs"]:
        result = load_result(data_dir, run)
        row = {"run_id": run["run_id"], "case_id": run["case_id"],
               "model": run["model_key"], "variant": run["variant"],
               "status": "scored", "score": None}
        if result is None:
            row["status"] = "missing"
        else:
            prediction = result.get("prediction")
            if not isinstance(prediction, str) or not prediction.strip():
                row["status"] = "no_prediction"
            else:
                _, _, score = evaluate(prediction, references[run["case_id"]]["scoring_points"])
                row["score"] = float(score)
        rows.append(row)
    return rows


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def reproduction_check(rows: list[dict]) -> dict:
    """Le medie ricalcolate coincidono con la tabella gia' riportata?"""
    cells, ok = {}, True
    for (model, variant), (n_rep, mean_rep) in REPORTED.items():
        scored = [r["score"] for r in rows
                  if r["model"] == model and r["variant"] == variant and r["score"] is not None]
        mean = _mean(scored)
        match = (len(scored) == n_rep and mean is not None
                 and abs(mean - mean_rep) <= TOLERANCE)
        ok = ok and match
        cells[f"{model}|{variant}"] = {"n": len(scored), "n_reported": n_rep,
                                       "mean": mean, "mean_reported": mean_rep, "match": match}
    return {"all_match": ok, "cells": cells,
            "note": "Se non coincide, i numeri per strato NON sono confrontabili con la tabella gia' riportata."}


def stratum_means(rows: list[dict], strata: dict[str, str]) -> dict:
    out = {}
    for model in MODELS:
        for stratum in STRATA + ("tutti",):
            for variant in VARIANTS:
                vals = [r["score"] for r in rows
                        if r["model"] == model and r["variant"] == variant
                        and r["score"] is not None
                        and (stratum == "tutti" or strata[r["case_id"]] == stratum)]
                out[f"{model}|{stratum}|{variant}"] = {"n": len(vals), "mean": _mean(vals)}
    return out


def paired(rows: list[dict], strata: dict[str, str], base: str, other: str) -> dict:
    """other - base, appaiato per incidente; solo le coppie con entrambe le run valutate."""
    by = {(r["model"], r["case_id"], r["variant"]): r["score"] for r in rows
          if r["score"] is not None}
    out, pooled = {}, {s: Counter() for s in STRATA + ("tutti",)}
    for model in MODELS:
        for stratum in STRATA + ("tutti",):
            diffs = []
            for case, st in strata.items():
                if stratum != "tutti" and st != stratum:
                    continue
                a, b = by.get((model, case, base)), by.get((model, case, other))
                if a is None or b is None:
                    continue
                diffs.append(b - a)
            wins = sum(d > 0 for d in diffs)
            losses = sum(d < 0 for d in diffs)
            ties = sum(d == 0 for d in diffs)
            pooled[stratum].update(win=wins, tie=ties, loss=losses)
            out[f"{model}|{stratum}"] = {"pairs": len(diffs), "mean_difference": _mean(diffs),
                                         "win": wins, "tie": ties, "loss": losses}
    out["tutti_i_modelli"] = {s: dict(c) for s, c in pooled.items()}
    out["nota"] = ("Il totale su piu' modelli conta lo stesso incidente tre volte: descrittivo, "
                   "non indipendente.")
    return out


def run_strata(data_dir: Path, market_zip: Path, openrca_dir: Path, evaluate=None,
               expected_runs: int = 300, expected_cases: int = 20) -> dict:
    plan = load_plan(data_dir, expected_runs, expected_cases)
    references = load_references(market_zip, plan["cases"])
    classes = {c: case_classes(ref) for c, ref in references.items()}
    strata = {c: v["stratum"] for c, v in classes.items()}
    if evaluate is None:
        evaluate = load_official_evaluate(openrca_dir)
    rows = score_runs(data_dir, plan, references, evaluate)
    multi = sum(1 for c in plan["cases"] if int(c.get("requested_fault_count", 1)) >= 2)
    return {
        "version": VERSION, "provider_calls": 0,
        "scope": "EVALUATION20, analisi post hoc esplorativa dei dati congelati.",
        "official_scorer_commit": OFFICIAL_COMMIT,
        "official_evaluate_sha256": OFFICIAL_EVALUATE_SHA256,
        "plan_sha256": _file_sha(plan_path(data_dir)),
        "covered_classes": list(COVERED), "held_out_classes": list(HELD_OUT),
        "reproduction_check": reproduction_check(rows),
        "cases_per_stratum": dict(Counter(strata.values())),
        "multi_fault_cases": multi,
        "held_out_classes_found_in_evaluation_cases": sum(
            1 for v in classes.values() if v["held_out_classes_in_case"]),
        "cases_with_unknown_row_class": sum(
            1 for v in classes.values() if not v["row_class_known"]),
        "case_strata": {c: {"stratum": v["stratum"], "labels": v["labels"]}
                        for c, v in sorted(classes.items())},
        "runs_not_scored": dict(Counter(r["status"] for r in rows if r["score"] is None)),
        "means": stratum_means(rows, strata),
        "paired_A1_8R_minus_A1": paired(rows, strata, "A1", "A1_8R"),
        "paired_A1_minus_A0": paired(rows, strata, "A0", "A1"),
        "limits": ["Post hoc: strati decisi dopo aver visto i risultati complessivi.",
                   "Strati piccoli, una esecuzione per cella: nessun intervallo.",
                   "Un guasto aggiuntivo di classe sconosciuta, in un incidente multiguasto senza motivo "
                   "nei punti di punteggio, non e' visibile."],
    }


# ------------------------------------------------------------------ separazione

def run_separation(data_dir: Path, market_zip: Path) -> dict:
    """Quante righe delle quattro classi cadono in ciascun gruppo dello split (solo conteggi)."""
    root = Path(data_dir)
    split = _read_csv(root / "data/processed/split_market_v1.csv", SPLIT_COLUMNS)
    manifest = _read_csv(root / "data/processed/benchmark_inputs_market.csv", MANIFEST_COLUMNS)
    if set(split) != set(manifest):
        raise ScoringError("Split e manifest con case_id diversi")
    with ZipFile(Path(market_zip), "r") as zf:
        rows = _archive_rows(zf)
    target = {_normalized(x): x for x in HELD_OUT}
    per_split: dict[str, Counter] = {}
    for case_id, entry in manifest.items():
        bed, idx = _row_of(case_id)
        if entry["cloudbed"] != bed or int(entry["query_index"]) != idx:
            raise ScoringError("Indice o cloudbed incoerenti: " + case_id)
        query, record = rows[bed]
        if not 0 <= idx < len(query):
            raise ScoringError("Riga fuori archivio: " + case_id)
        if (query[idx]["task_index"] != entry["task_index"]
                or query[idx]["instruction"] != entry["instruction"]):
            raise ScoringError("Task o istruzione diversi dall'archivio: " + case_id)
        counter = per_split.setdefault(split[case_id]["split"], Counter())
        counter["cases"] += 1
        label = target.get(_normalized(record[idx]["reason"]))
        if label is not None:
            counter["in_four_classes"] += 1
            counter["class:" + label] += 1
    outside = sum(c["in_four_classes"] for s, c in per_split.items() if s != "ood_holdout")
    return {
        "version": VERSION + "_separation", "provider_calls": 0,
        "per_split": {s: dict(c) for s, c in sorted(per_split.items())},
        "four_classes_outside_ood_holdout": outside,
        "separation_holds": outside == 0,
        "note": ("Solo la riga di record.csv del caso (non i guasti aggiuntivi dei multiguasto); "
                 "conteggi aggregati, nessun case_id."),
    }


# ------------------------------------------------------------------ uscita

def format_strata(report: dict) -> str:
    lines = ["Riproduzione della tabella gia' riportata: "
             + ("OK" if report["reproduction_check"]["all_match"] else "NON COINCIDE"),
             f"Casi per strato: {report['cases_per_stratum']}  multiguasto: {report['multi_fault_cases']}",
             f"Run non valutate: {report['runs_not_scored']}",
             f"Casi con una delle 4 classi di RQ2: {report['held_out_classes_found_in_evaluation_cases']}",
             "", "Differenza media A1_8R - A1 (coppie; vittorie/pareggi/sconfitte)"]
    for stratum in STRATA + ("tutti",):
        for model in MODELS:
            p = report["paired_A1_8R_minus_A1"][f"{model}|{stratum}"]
            md = "-" if p["mean_difference"] is None else f"{p['mean_difference']:+.3f}"
            lines.append(f"  {stratum:12s} {model:7s} n={p['pairs']:2d} {md:>7s}  "
                         f"{p['win']}/{p['tie']}/{p['loss']}")
    lines += ["", "Differenza media A1 - A0"]
    for stratum in STRATA + ("tutti",):
        for model in MODELS:
            p = report["paired_A1_minus_A0"][f"{model}|{stratum}"]
            md = "-" if p["mean_difference"] is None else f"{p['mean_difference']:+.3f}"
            lines.append(f"  {stratum:12s} {model:7s} n={p['pairs']:2d} {md:>7s}  "
                         f"{p['win']}/{p['tie']}/{p['loss']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s1 = sub.add_parser("strata")
    s1.add_argument("--data-dir", required=True, type=Path)
    s1.add_argument("--market-zip", type=Path)
    s1.add_argument("--openrca-dir", required=True, type=Path)
    s1.add_argument("--out", required=True, type=Path)
    s2 = sub.add_parser("separation")
    s2.add_argument("--data-dir", required=True, type=Path)
    s2.add_argument("--market-zip", type=Path)
    s2.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    zip_path = args.market_zip or (args.data_dir / "Market.zip")
    try:
        if args.cmd == "strata":
            report = run_strata(args.data_dir, zip_path, args.openrca_dir)
            text = format_strata(report)
        else:
            report = run_separation(args.data_dir, zip_path)
            text = json.dumps(report, indent=2, ensure_ascii=False)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        digest = write_report_create_only(report, args.out)
    except (ScoringError, FileExistsError) as exc:
        print("STOP: " + str(exc), file=sys.stderr)
        return 2
    print(text)
    print(f"\nReport scritto (create-only): {args.out}\nSHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
