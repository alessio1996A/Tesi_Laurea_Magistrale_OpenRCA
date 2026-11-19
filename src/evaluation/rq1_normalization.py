"""RQ1: risultati di EVALUATION20 normalizzati rispetto ad A0 (richiesta del relatore, 19 novembre).

Il relatore ha chiesto di presentare i risultati con un riferimento comune e gli altri come multipli,
per mostrare il vantaggio. Qui il riferimento e' A0 DELLO STESSO MODELLO: cosi' non si confrontano
provider diversi (i token non sono confrontabili tra provider, i punteggi dipendono dal modello).

E' un'analisi POST HOC di dati gia' congelati: nessuna chiamata a modelli, nessuna modifica di
record, regole o soglie, nessuna lettura della ground truth (non apre Market.zip, query.csv ne'
record.csv). Scrive solo un report create-only.

Per ogni modello e variante riporta, SEMPRE insieme:
  * il valore assoluto (punteggio medio, token medi, secondi medi) e il numero di run (n);
  * il rapporto rispetto ad A0 (multiplo) e la differenza rispetto ad A0;
  * un intervallo bootstrap al 95% (ricampionamento degli INCIDENTI, seme fisso).
Il rapporto non e' definito se la media di A0 e' zero: in quel caso resta il valore assoluto.
Un rapporto con riferimento basso ingigantisce le differenze piccole: va letto con l'intervallo.

Popolazione: le run con punteggio ufficiale congelato (stato "complete", quindi con conteggio dei
token completo). Le run con errore del modello, mai riprovate, restano fuori da punteggi, token e
tempi: l'n di ogni cella e' riportato accanto al valore.

Regola fissata prima di leggere i numeri: se le medie dei punteggi non riproducono la tabella gia'
riportata (stessa regola della stratificazione), il comando si ferma e nessun numero e' usabile.
Il confronto di token e tempo con le percentuali della relazione del 9 novembre e' INFORMATIVO:
si riportano tutte le definizioni provate (media/mediana, end_to_end/duration) e quale coincide.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from evaluation.rq1_coverage_stratification import (
    MODELS, PROTOCOL, REPORTED, TOLERANCE, VARIANTS, ScoringError, _file_sha, load_plan,
    load_scoring_report, plan_path, result_paths, score_runs,
)
from evaluation.rq2_a_offline_scoring import write_report_create_only

VERSION = "rq1_normalization_v1"
BASE = "A0"
SEED = 20261119
DRAWS = 10000
MEASURES = ("score", "total_tokens", "end_to_end_seconds", "duration_seconds")
TIME_KEYS = ("end_to_end_seconds", "duration_seconds")
# Relazione del 9 novembre (consolidamento, sez. 3.1): A1_8R -> A1_8R_Planning,
# (variazione % dei token, variazione % del tempo) per modello.
REPORTED_EFFICIENCY = {"sonnet": (-27.9, -22.1), "haiku": (17.0, 15.2), "gemini": (-27.8, -17.2)}
LIMITS = (
    "Analisi post hoc di dati congelati; una esecuzione per cella (variabilita' tra esecuzioni non misurata).",
    "Il riferimento e' A0 dello stesso modello: nessun confronto tra modelli o provider.",
    "Il rapporto con un A0 basso ingigantisce le differenze piccole; leggerlo con l'intervallo.",
    "Intervalli bootstrap sugli incidenti, non corretti per confronti multipli.",
    "Le medie di cella sono sugli incidenti con punteggio: Gemini ha 5 run senza punteggio "
    "(errori del modello mai riprovati), quindi n diverso da 20 in alcune celle.",
)


# ------------------------------------------------------------------ calcolo

def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


def _quantile(sorted_values: list[float], q: float) -> float:
    pos = q * (len(sorted_values) - 1)
    low = int(pos)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (pos - low)


def cell_values(rows: list[dict], key: str) -> dict:
    """{(modello, variante): {incidente: valore}}, solo run con punteggio; una run per cella e incidente."""
    out: dict = {}
    for row in rows:
        if row["score"] is None or row.get(key) is None:
            continue
        cell = out.setdefault((row["model"], row["variant"]), {})
        if row["case_id"] in cell:
            raise ScoringError("Piu' di una run per cella e incidente: " + str(row["run_id"]))
        cell[row["case_id"]] = float(row[key])
    return out


def summarize(values: dict) -> dict:
    """Per modello e variante: n, media, mediana, rapporto e differenza rispetto ad A0 (sulle medie)."""
    out: dict = {}
    for model in MODELS:
        base_mean = _mean(list(values.get((model, BASE), {}).values()))
        out[model] = {}
        for variant in VARIANTS:
            vals = list(values.get((model, variant), {}).values())
            mean = _mean(vals)
            out[model][variant] = {
                "n": len(vals), "mean": mean, "median": _median(vals),
                "ratio_vs_A0": (mean / base_mean) if (mean is not None and base_mean) else None,
                "difference_vs_A0": None if (mean is None or base_mean is None) else mean - base_mean,
            }
    return out


def make_samples(cases: list[str], seed: int = SEED, draws: int = DRAWS) -> list[list[str]]:
    """Ricampionamenti degli incidenti con seme fisso (gli stessi per ogni misura)."""
    rng = random.Random(seed)
    n = len(cases)
    return [[cases[rng.randrange(n)] for _ in range(n)] for _ in range(draws)]


def bootstrap(values: dict, samples: list[list[str]]) -> dict:
    """Intervalli al 95% di rapporto e differenza rispetto ad A0, per modello e variante.

    In ogni ricampionamento la media di cella e' calcolata sugli incidenti estratti che hanno
    un punteggio in quella cella. I ricampionamenti con A0 a zero non danno un rapporto e si contano.
    """
    out: dict = {}
    for model in MODELS:
        base = values.get((model, BASE), {})
        out[model] = {}
        for variant in VARIANTS:
            if variant == BASE:
                continue
            cell = values.get((model, variant), {})
            ratios, diffs, undefined = [], [], 0
            for sample in samples:
                b = [base[c] for c in sample if c in base]
                v = [cell[c] for c in sample if c in cell]
                if not b or not v:
                    undefined += 1
                    continue
                b_mean, v_mean = sum(b) / len(b), sum(v) / len(v)
                diffs.append(v_mean - b_mean)
                if b_mean > 0:
                    ratios.append(v_mean / b_mean)
                else:
                    undefined += 1
            ratios.sort()
            diffs.sort()
            out[model][variant] = {
                "ratio_ci95": [_quantile(ratios, 0.025), _quantile(ratios, 0.975)] if ratios else None,
                "difference_ci95": [_quantile(diffs, 0.025), _quantile(diffs, 0.975)] if diffs else None,
                "draws_ratio_defined": len(ratios), "draws_total": len(samples),
                "draws_ratio_undefined": undefined,
            }
    return out


def attach_metrics(data_dir: Path, rows: list[dict]) -> list[dict]:
    """Aggiunge token e tempi, letti dai risultati congelati, alle sole run con punteggio."""
    enriched = []
    for row in rows:
        item = dict(row)
        if row["score"] is not None:
            output, _ = result_paths(data_dir, row["run_id"])
            if not output.is_file():
                raise ScoringError("Risultato mancante: " + row["run_id"])
            metrics = json.loads(output.read_text(encoding="utf-8")).get("metrics")
            if not isinstance(metrics, dict) or metrics.get("token_usage_complete") is not True:
                raise ScoringError("Metriche mancanti o conteggio token incompleto: " + row["run_id"])
            for key in ("total_tokens",) + TIME_KEYS:
                value = metrics.get(key)
                if type(value) not in (int, float) or value < 0:
                    raise ScoringError(f"Metrica {key} non valida: {row['run_id']}")
                item[key] = value
        enriched.append(item)
    return enriched


def reproduction(rows: list[dict], reported: dict) -> dict:
    """Le medie ricalcolate coincidono con la tabella gia' riportata (stessa regola della stratificazione)?"""
    cells, ok = {}, True
    for (model, variant), (n_rep, mean_rep) in reported.items():
        scored = [r["score"] for r in rows
                  if r["model"] == model and r["variant"] == variant and r["score"] is not None]
        mean = _mean(scored)
        match = len(scored) == n_rep and mean is not None and abs(mean - mean_rep) <= TOLERANCE
        ok = ok and match
        cells[f"{model}|{variant}"] = {"n": len(scored), "n_reported": n_rep, "mean": mean,
                                       "mean_reported": mean_rep, "match": match}
    return {"all_match": ok, "cells": cells}


def efficiency_check(summaries: dict) -> dict:
    """Variazione % A1_8R -> A1_8R_Planning con ogni definizione provata, contro la relazione."""
    result = {}
    for time_key in TIME_KEYS:
        for stat in ("mean", "median"):
            tok, tim = summaries["total_tokens"], summaries[time_key]
            cells, tok_ok, tim_ok = {}, True, True
            for model, (rep_tok, rep_tim) in REPORTED_EFFICIENCY.items():
                a_t, b_t = tok[model]["A1_8R"][stat], tok[model]["A1_8R_Planning"][stat]
                a_s, b_s = tim[model]["A1_8R"][stat], tim[model]["A1_8R_Planning"][stat]
                pct_tok = None if not a_t or b_t is None else (b_t / a_t - 1) * 100
                pct_tim = None if not a_s or b_s is None else (b_s / a_s - 1) * 100
                m_tok = pct_tok is not None and round(pct_tok, 1) == rep_tok
                m_tim = pct_tim is not None and round(pct_tim, 1) == rep_tim
                tok_ok, tim_ok = tok_ok and m_tok, tim_ok and m_tim
                cells[model] = {"tokens_pct": pct_tok, "tokens_pct_reported": rep_tok, "tokens_match": m_tok,
                                "time_pct": pct_tim, "time_pct_reported": rep_tim, "time_match": m_tim}
            result[f"{stat}|{time_key}"] = {"tokens_all_match": tok_ok, "time_all_match": tim_ok, "cells": cells}
    return result


def run_normalization(data_dir: Path, expected_runs: int = 300, expected_cases: int = 20,
                      reported: dict | None = REPORTED, draws: int = DRAWS, seed: int = SEED) -> dict:
    data_dir = Path(data_dir)
    plan = load_plan(data_dir, expected_runs, expected_cases)
    scoring = load_scoring_report(data_dir, plan)
    rows, hash_mismatches = score_runs(data_dir, plan, scoring)
    if reported is not None:
        check = reproduction(rows, reported)
        if not check["all_match"]:
            bad = [k for k, v in check["cells"].items() if not v["match"]]
            raise ScoringError("Le medie dei punteggi non riproducono la tabella gia' riportata "
                               "(celle: " + ", ".join(bad) + "): nessun numero e' usabile")
    else:
        check = {"all_match": None, "note": "controllo saltato (solo test)"}
    rows = attach_metrics(data_dir, rows)
    cases = sorted({r["case_id"] for r in rows})
    samples = make_samples(cases, seed, draws)
    summaries, intervals = {}, {}
    for name in MEASURES:
        values = cell_values(rows, name)
        summaries[name] = summarize(values)
        intervals[name] = bootstrap(values, samples)
    return {
        "version": VERSION, "protocol": PROTOCOL, "base": BASE, "provider_calls": 0,
        "ground_truth_accessed": False,
        "population": "run con punteggio ufficiale congelato (stato complete, token completi)",
        "plan_sha256": _file_sha(plan_path(data_dir)),
        "source_result_hash_mismatches": hash_mismatches,
        "runs_total": len(rows), "runs_scored": sum(r["score"] is not None for r in rows),
        "runs_not_scored": sum(r["score"] is None for r in rows),
        "cases": len(cases),
        "reproduction_of_reported_means": check,
        "summaries": summaries, "intervals": intervals,
        "efficiency_vs_report_of_9_nov": efficiency_check(summaries),
        "bootstrap": {"unit": "incidente", "seed": seed, "draws": draws, "confidence": 0.95},
        "limits": list(LIMITS),
    }


# ------------------------------------------------------------------ uscita

def _it(value: float | None, digits: int, sign: bool = False) -> str:
    if value is None:
        return "n.d."
    text = f"{value:+.{digits}f}" if sign else f"{value:.{digits}f}"
    return text.replace(".", ",")


def _table(report: dict, name: str, label: str, digits: int) -> list[str]:
    lines = [label, "  " + f"{'':8s}" + "".join(f"{v:>28s}" for v in VARIANTS)]
    for model in MODELS:
        cells = []
        for variant in VARIANTS:
            s = report["summaries"][name][model][variant]
            if variant == BASE:
                ratio = "rif."
            else:
                ratio = "n.d." if s["ratio_vs_A0"] is None else _it(s["ratio_vs_A0"], 2) + "x"
            cells.append(f"{_it(s['mean'], digits)} (n={s['n']}) {ratio}")
        lines.append("  " + f"{model:8s}" + "".join(f"{c:>28s}" for c in cells))
    lines.append("  intervalli 95% del rapporto rispetto ad A0:")
    for model in MODELS:
        parts = []
        for variant in VARIANTS[1:]:
            ci = report["intervals"][name][model][variant]["ratio_ci95"]
            parts.append(f"{variant}: " + ("n.d." if ci is None else f"[{_it(ci[0], 2)}; {_it(ci[1], 2)}]"))
        lines.append(f"    {model:8s} " + "  ".join(parts))
    return lines


def format_report(report: dict) -> str:
    rep = report["reproduction_of_reported_means"]
    lines = [f"Riproduzione delle 15 medie gia' riportate: {'OK' if rep['all_match'] else rep['all_match']}",
             f"Run: {report['runs_total']}  con punteggio: {report['runs_scored']}  "
             f"senza: {report['runs_not_scored']}  incidenti: {report['cases']}  "
             f"discordanze hash risultati sorgente: {report['source_result_hash_mismatches']}",
             f"Riferimento: {report['base']} dello stesso modello. Bootstrap: {report['bootstrap']['draws']} "
             f"ricampionamenti degli incidenti, seme {report['bootstrap']['seed']}.", ""]
    lines += _table(report, "score", "PUNTEGGIO medio (rapporto rispetto ad A0)", 3) + [""]
    lines += _table(report, "total_tokens", "TOKEN totali medi per run (rapporto rispetto ad A0)", 0) + [""]
    lines += _table(report, "end_to_end_seconds", "TEMPO end-to-end medio, secondi (rapporto rispetto ad A0)", 1) + [""]
    lines.append("Confronto con la relazione del 9 novembre (A1_8R -> A1_8R_Planning), variazione %:")
    for key, entry in report["efficiency_vs_report_of_9_nov"].items():
        lines.append(f"  definizione {key}: token {'coincidono' if entry['tokens_all_match'] else 'NON coincidono'}, "
                     f"tempo {'coincide' if entry['time_all_match'] else 'NON coincide'}")
        for model, c in entry["cells"].items():
            lines.append(f"     {model:7s} token {_it(c['tokens_pct'], 1, True)}% (relazione {_it(c['tokens_pct_reported'], 1, True)}%)  "
                         f"tempo {_it(c['time_pct'], 1, True)}% (relazione {_it(c['time_pct_reported'], 1, True)}%)")
    lines += ["", "Limiti:"] + ["  - " + text for text in report["limits"]]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = run_normalization(args.data_dir)
        text = format_report(report)
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
