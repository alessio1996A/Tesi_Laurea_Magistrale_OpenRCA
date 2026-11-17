"""RQ2-A: valutazione OFFLINE delle diagnosi D e C sui 4 incidenti di discovery.

Risponde a una sola domanda: nei record gia' congelati del run V5 (180 stage),
le diagnosi dell'agente sulle quattro classi non coperte dalle regole sono
corrette? Non chiama modelli, non scrive nei record, non modifica nulla di
congelato. Scrive solo il report di uscita, in modalita' create-only.

Due misure, entrambe descrittive (4 incidenti, una esecuzione per cella):
  * D con lo scorer ufficiale Microsoft OpenRCA (commit fissato, hash del file
    verificato): componente, motivo e orario contano come nel benchmark.
    Il motivo e' un confronto di stringhe esatte: un testo libero non coincide.
  * C con la politica lessicale gia' congelata (rq2_fault_type_eval_policy):
    il tipo di guasto proposto da C contro la classe ufficiale del caso.

Regole di separazione (le stesse delle altre valutazioni con ground truth):
  * ACCEDE alla ground truth (query.csv e record.csv di Market.zip): va eseguito
    in un processo separato dall'inferenza e MAI importato da agente, tool,
    prompt o stage C/K;
  * accetta solo i 4 casi di discovery, quindi i casi sigillati non si aprono;
  * ogni record e' riletto con il suo SHA-256: un record alterato ferma tutto;
  * stage mancanti, non validi o bloccati restano nel denominatore pianificato;
  * nessuna soglia o alias nuovo: gli alias di C sono quelli congelati.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from evaluation import rq2_fault_type_eval_policy as fault_policy
from evaluation.rq2_k_records import parse_stage_id

VERSION = "rq2_a_offline_scoring_v1"

DISCOVERY_CASES = (
    "cloudbed-1_q032", "cloudbed-1_q050", "cloudbed-2_q026", "cloudbed-2_q045",
)
MODELS = ("gemini", "sonnet", "haiku")
HARNESSES = ("A0", "A1", "A1_8R", "A1_8R_Planning", "A1_PAVE")
STAGES = ("D", "C")
STATUS_COMPLETE = "RECORDED_COMPLETE"

OFFICIAL_COMMIT = "2a481ae63cb045c3eadbeca9eddaa10ec1151979"
# SHA-256 di main/evaluate.py a quel commit, calcolato sul checkout ufficiale.
OFFICIAL_EVALUATE_SHA256 = (
    "9a1c235139266c32b0e95c7e9938591b8fe014aad4cde95580f73f13a54d53f1"
)
QUERY_COLUMNS = {"task_index", "instruction", "scoring_points"}
RECORD_COLUMNS = {"timestamp", "level", "component", "reason", "datetime"}


class ScoringError(ValueError):
    """Input non verificabile: mai indovinare, mai riparare in silenzio."""


# ------------------------------------------------------------------ utilita'

def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=True,
    ).encode("utf-8")).hexdigest()


def _dig(obj, *path):
    for key in path:
        if not isinstance(obj, dict) or key not in obj:
            return None
        obj = obj[key]
    return obj


# ------------------------------------------------------------------ record

def load_records(records_dir: Path) -> dict[str, dict]:
    """Legge i record D e C dei 4 casi di discovery, verificando l'hash.

    Restituisce {stage_id: record}. I record K non servono a RQ2-A e vengono
    ignorati; un record con hash non coerente o con identita' fuori piano
    solleva ScoringError.
    """
    folder = Path(records_dir)
    if not folder.is_dir():
        raise ScoringError(f"Cartella dei record inesistente: {folder}")
    found: dict[str, dict] = {}
    for path in sorted(folder.glob("V5_RECORD_*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ScoringError(f"Record illeggibile: {path.name}") from exc
        if type(record) is not dict or "record_sha256" not in record:
            raise ScoringError(f"Record senza hash: {path.name}")
        core = {k: v for k, v in record.items() if k != "record_sha256"}
        if _sha(core) != record["record_sha256"]:
            raise ScoringError(f"Hash non coerente: {path.name}")
        ident = parse_stage_id(record["stage_id"])
        if ident["stage"] not in STAGES:
            continue
        if (ident["case_id"] not in DISCOVERY_CASES
                or ident["model"] not in MODELS
                or ident["harness"] not in HARNESSES):
            raise ScoringError(
                "Record fuori dal piano di discovery: " + record["stage_id"])
        if record["stage_id"] in found:
            raise ScoringError("stage_id duplicato: " + record["stage_id"])
        found[record["stage_id"]] = record
    return found


def planned_cells() -> list[tuple[str, str, str, str]]:
    """Le 60 celle (caso, modello, harness) per ciascuno stage D e C."""
    return [(case, model, harness, stage)
            for stage in STAGES for case in DISCOVERY_CASES
            for model in MODELS for harness in HARNESSES]


def index_records(records: dict[str, dict]) -> dict[tuple, dict]:
    """(caso, modello, harness, stage) -> record, con controllo di unicita'."""
    table: dict[tuple, dict] = {}
    for stage_id, record in records.items():
        ident = parse_stage_id(stage_id)
        key = (ident["case_id"], ident["model"], ident["harness"], ident["stage"])
        if key in table:
            raise ScoringError("Piu' record per la stessa cella: " + repr(key))
        table[key] = record
    return table


def d_entry(record: dict | None) -> dict:
    """Stato e predizione ufficiale di uno stage D (None = record assente)."""
    if record is None:
        return {"status": "MISSING", "prediction": None,
                "task_index": None, "query_index": None}
    entry = {"status": record.get("status"), "prediction": None,
             "task_index": None, "query_index": None}
    if entry["status"] != STATUS_COMPLETE:
        return entry
    run = _dig(record, "receipt", "artifact", "diagnostic_run")
    prediction = _dig(run, "prediction") if run is not None else None
    if type(prediction) is not str or not prediction.strip():
        raise ScoringError("D completo senza predizione: " + record["stage_id"])
    entry.update(prediction=prediction, task_index=run.get("task_index"),
                 query_index=run.get("query_index"))
    return entry


def c_entry(record: dict | None) -> dict:
    """Stato, decisione e tipo di guasto di uno stage C."""
    if record is None:
        return {"status": "MISSING", "decision": None,
                "predicted_fault_type": None, "predicted_component": None}
    status = record.get("status")
    out = {"status": status, "decision": None, "predicted_fault_type": None,
           "predicted_component": None}
    if status != STATUS_COMPLETE:
        return out
    raw = _dig(record, "receipt", "artifact", "raw_response")
    try:
        body = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ScoringError("C completo senza JSON: " + record["stage_id"]) from exc
    if type(body) is not dict or body.get("decision") not in ("diagnosis", "abstain"):
        raise ScoringError("C completo con decisione non valida: " + record["stage_id"])
    out["decision"] = body["decision"]
    out["predicted_fault_type"] = body.get("predicted_fault_type")
    out["predicted_component"] = body.get("predicted_component")
    return out


# --------------------------------------------------------------- riferimenti

def _read_member(zf: ZipFile, member: str, columns: set[str]) -> list[dict]:
    if member not in zf.namelist():
        raise ScoringError("File assente nell'archivio: " + member)
    text = zf.read(member).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not columns.issubset(set(reader.fieldnames or [])):
        raise ScoringError("Colonne inattese in " + member)
    return list(reader)


def load_references(market_zip: Path, cases=DISCOVERY_CASES) -> dict[str, dict]:
    """Ground truth dei soli casi di discovery, da query.csv e record.csv.

    Il numero nel case_id e' la riga (da 0) del file del suo cloudbed, come
    verificato dall'inventario delle classi. Qui si ricontrolla solo che la
    riga esista; la coerenza con task e indice dei record D e' in score_all.
    """
    for case in cases:
        if case not in DISCOVERY_CASES:
            raise ScoringError("Caso non ammesso (non e' discovery): " + case)
    references: dict[str, dict] = {}
    with ZipFile(Path(market_zip), "r") as zf:
        cache: dict[str, tuple[list[dict], list[dict]]] = {}
        for case in cases:
            match = re.fullmatch(r"(cloudbed-[12])_q(\d+)", case)
            if match is None:
                raise ScoringError("case_id malformato: " + case)
            bed, row = match.group(1), int(match.group(2))
            if bed not in cache:
                base = f"Market/{bed}"
                cache[bed] = (
                    _read_member(zf, base + "/query.csv", QUERY_COLUMNS),
                    _read_member(zf, base + "/record.csv", RECORD_COLUMNS),
                )
            query_rows, record_rows = cache[bed]
            if len(query_rows) != len(record_rows) or not 0 <= row < len(query_rows):
                raise ScoringError("Riga di riferimento fuori archivio: " + case)
            q, rec = query_rows[row], record_rows[row]
            references[case] = {
                "row_index": row, "task_index": q["task_index"],
                "scoring_points": q["scoring_points"],
                "reference_class": rec["reason"].strip(),
            }
    return references


def load_official_evaluate(openrca_dir: Path):
    """Carica `evaluate` dal checkout ufficiale, dopo aver verificato l'hash."""
    path = Path(openrca_dir) / "main" / "evaluate.py"
    if not path.is_file():
        raise ScoringError(f"Scorer ufficiale non trovato: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != OFFICIAL_EVALUATE_SHA256:
        raise ScoringError(
            "main/evaluate.py non e' quello del commit " + OFFICIAL_COMMIT
            + " (hash " + digest + ")")
    spec = importlib.util.spec_from_file_location("openrca_official_evaluate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.evaluate


# ------------------------------------------------------------------ punteggi

def score_d(d_table: dict[tuple, dict], references: dict[str, dict], evaluate) -> list[dict]:
    """Un punteggio ufficiale per ciascuna delle 60 celle D pianificate."""
    rows = []
    for case, model, harness, _ in [c for c in planned_cells() if c[3] == "D"]:
        entry = d_entry(d_table.get((case, model, harness, "D")))
        ref = references[case]
        row = {"case_id": case, "model": model, "harness": harness,
               "status": entry["status"], "task_index": ref["task_index"],
               "score": None, "passed": [], "failed": []}
        if entry["status"] == STATUS_COMPLETE:
            if (entry["task_index"] != ref["task_index"]
                    or entry["query_index"] != ref["row_index"]):
                raise ScoringError(
                    "Task o indice del record D incoerenti con il riferimento: "
                    + repr((case, model, harness)))
            passed, failed, score = evaluate(entry["prediction"], ref["scoring_points"])
            row.update(score=float(score), passed=sorted(passed), failed=sorted(failed))
        rows.append(row)
    return rows


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize_d(rows: list[dict]) -> dict:
    """Medie per modello e harness e confronto appaiato A1_8R contro A1."""
    arms: dict[str, dict] = {}
    for model in MODELS:
        for harness in HARNESSES:
            cell = [r for r in rows if r["model"] == model and r["harness"] == harness]
            scored = [r["score"] for r in cell if r["score"] is not None]
            planned = [r["score"] if r["score"] is not None else 0.0 for r in cell]
            arms[f"{model}|{harness}"] = {
                "planned": len(cell), "scored": len(scored),
                "mean_planned": _mean(planned), "mean_scored": _mean(scored),
                "strict": sum(1 for s in scored if s == 1.0),
                "not_scored": dict(Counter(
                    r["status"] for r in cell if r["score"] is None)),
            }
    paired = {}
    for model in MODELS:
        by = {(r["case_id"], r["harness"]): r["score"] for r in rows
              if r["model"] == model}
        wins = ties = losses = 0
        diffs = []
        for case in DISCOVERY_CASES:
            a1 = by.get((case, "A1")) or 0.0
            a8 = by.get((case, "A1_8R")) or 0.0
            diffs.append(a8 - a1)
            wins += a8 > a1
            losses += a8 < a1
            ties += a8 == a1
        paired[model] = {"pairs": len(diffs), "mean_difference_A1_8R_minus_A1": _mean(diffs),
                         "win_A1_8R": wins, "tie": ties, "loss_A1_8R": losses}
    return {"arms": arms, "paired_A1_8R_vs_A1": paired,
            "note": "Descrittivo: 4 incidenti, una esecuzione per cella, nessun intervallo."}


def score_c(c_table: dict[tuple, dict], references: dict[str, dict]) -> dict:
    """C con la politica lessicale congelata, per arm e appaiato."""
    labels = {case: references[case]["reference_class"] for case in DISCOVERY_CASES}
    per_arm, predictions = {}, {}
    for model in MODELS:
        for harness in HARNESSES:
            items = []
            for case in DISCOVERY_CASES:
                entry = c_entry(c_table.get((case, model, harness, "C")))
                status = entry["status"]
                if status == "MISSING":
                    status = "BLOCKED_DEPENDENCY"
                if status not in ("RECORDED_COMPLETE", "INVALID_OUTPUT",
                                  "PROVIDER_ERROR", "BLOCKED_DEPENDENCY"):
                    raise ScoringError("Stato C non gestito: " + str(status))
                complete = status == STATUS_COMPLETE
                items.append({
                    "case_id": case, "stage_status": status,
                    "decision": entry["decision"] if complete else None,
                    "predicted_fault_type":
                        entry["predicted_fault_type"] if complete else None,
                })
            predictions[(model, harness)] = items
            per_arm[f"{model}|{harness}"] = fault_policy.score_cause_cases(
                case_ids=DISCOVERY_CASES, reference_labels=labels, predictions=items)
    paired = {m: fault_policy.paired_harness_outcomes(
        case_ids=DISCOVERY_CASES, reference_labels=labels,
        a1=predictions[(m, "A1")], a1_8r=predictions[(m, "A1_8R")])
        for m in MODELS}
    return {"per_arm": per_arm, "paired_A1_8R_vs_A1": paired,
            "reference_classes_by_case": labels}


def run_scoring(records_dir, market_zip, openrca_dir) -> dict:
    records = load_records(Path(records_dir))
    table = index_records(records)
    references = load_references(Path(market_zip))
    evaluate = load_official_evaluate(Path(openrca_dir))
    d_rows = score_d(table, references, evaluate)
    return {
        "version": VERSION,
        "official_scorer_commit": OFFICIAL_COMMIT,
        "official_evaluate_sha256": OFFICIAL_EVALUATE_SHA256,
        "records_read": len(records),
        "records_sha256_digest": _sha(sorted(
            r["record_sha256"] for r in records.values())),
        "provider_calls": 0,
        "d_official": {"rows": d_rows, "summary": summarize_d(d_rows)},
        "c_fault_type": score_c(table, references),
        "scope": "4 incidenti di discovery, una esecuzione per cella; descrittivo.",
    }


def list_free_text(records_dir) -> list[dict]:
    """Testo libero proposto da D e C, cella per cella. NON legge la ground truth.

    Serve a leggere con gli occhi cosa ha scritto il modello, perche' la
    corrispondenza esatta dello scorer e della politica lessicale non lo mostra.
    """
    table = index_records(load_records(Path(records_dir)))
    rows = []
    for case, model, harness, stage in planned_cells():
        record = table.get((case, model, harness, stage))
        base = {"stage": stage, "case_id": case, "model": model, "harness": harness}
        if stage == "D":
            entry = d_entry(record)
            reasons, components, times = [], [], []
            if entry["prediction"]:
                try:
                    parsed = json.loads(entry["prediction"])
                except ValueError:
                    parsed = None
                for item in (parsed.values() if isinstance(parsed, dict) else []):
                    if isinstance(item, dict):
                        reasons.append(str(item.get("root cause reason", "")))
                        components.append(str(item.get("root cause component", "")))
                        times.append(str(item.get("root cause occurrence datetime", "")))
            rows.append({**base, "status": entry["status"],
                         "text": " | ".join(r for r in reasons if r) or None,
                         "component": " | ".join(c for c in components if c) or None,
                         "datetime": " | ".join(t for t in times if t) or None})
        else:
            entry = c_entry(record)
            rows.append({**base, "status": entry["status"],
                         "text": entry["predicted_fault_type"] if entry["decision"] == "diagnosis"
                         else ("(astensione)" if entry["decision"] == "abstain" else None),
                         "component": entry["predicted_component"], "datetime": None})
    return rows


def plan_check(records_dir) -> dict:
    """Senza ground truth: quante celle D e C ci sono e con che stato."""
    table = index_records(load_records(Path(records_dir)))
    out = {}
    for stage in STAGES:
        statuses = Counter(
            (table[c]["status"] if c in table else "MISSING")
            for c in planned_cells() if c[3] == stage)
        out[stage] = dict(sorted(statuses.items()))
    return {"version": VERSION, "planned_per_stage": 60, "status_counts": out,
            "reads_ground_truth": False, "provider_calls": 0}


def write_report_create_only(report: dict, path: Path) -> str:
    body = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    data = body.encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    return hashlib.sha256(data).hexdigest()


def write_text_create_only(text: str, path: Path) -> None:
    data = text.encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)


def format_summary(report: dict) -> str:
    lines = ["RQ2-A — D con scorer ufficiale (media sul piano; non valutati = 0)", ""]
    lines.append(f"{'modello|harness':22s} {'media':>6s} {'media(valutati)':>16s} "
                 f"{'strict':>6s} {'non valutati':>14s}")
    for arm, a in report["d_official"]["summary"]["arms"].items():
        mean_scored = ("-" if a["mean_scored"] is None
                       else f"{a['mean_scored']:.3f}")
        lines.append(f"{arm:22s} {a['mean_planned']:6.3f} {mean_scored:>16s} "
                     f"{a['strict']:6d} {sum(a['not_scored'].values()):14d}")
    lines += ["", "D — A1_8R contro A1, stessi casi e modello:"]
    for model, p in report["d_official"]["summary"]["paired_A1_8R_vs_A1"].items():
        lines.append(f"  {model:7s} diff media {p['mean_difference_A1_8R_minus_A1']:+.3f}  "
                     f"vittorie {p['win_A1_8R']} pari {p['tie']} sconfitte {p['loss_A1_8R']}")
    lines += ["", "RQ2-A — C, tipo di guasto (politica lessicale congelata)", ""]
    lines.append(f"{'modello|harness':22s} {'corrette':>8s} {'sbagliate':>9s} "
                 f"{'non mappate':>11s} {'astenute':>8s} {'invalide/err.':>13s}")
    for arm, c in report["c_fault_type"]["per_arm"].items():
        n = c["counts"]
        other = n["invalid_output"] + n["provider_error"] + n["blocked_dependency"] + n["missing"]
        lines.append(f"{arm:22s} {n['correct']:8d} {n['wrong_known_class']:9d} "
                     f"{n['unmatched_diagnosis']:11d} {n['abstain']:8d} {other:13d}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="RQ2-A: valutazione offline di D e C")
    parser.add_argument("--records-dir", required=True,
                        help="cartella records/ del run V5 (sola lettura)")
    parser.add_argument("--market-zip", help="Market.zip (query.csv e record.csv)")
    parser.add_argument("--openrca-dir", help="checkout Microsoft OpenRCA al commit fissato")
    parser.add_argument("--out", help="report JSON di uscita (create-only)")
    parser.add_argument("--plan-check", action="store_true",
                        help="solo conteggio delle celle, senza ground truth")
    parser.add_argument("--list-text", action="store_true",
                        help="stampa il testo libero di D e C (senza ground truth)")
    parser.add_argument("--csv-out", help="con --list-text: CSV create-only")
    args = parser.parse_args(argv)
    if args.plan_check:
        print(json.dumps(plan_check(args.records_dir), indent=2, sort_keys=True))
        return 0
    if args.list_text:
        rows = list_free_text(args.records_dir)
        for r in rows:
            print(f"{r['stage']} | {r['case_id']} | {r['model']:6s} | {r['harness']:15s} | "
                  f"{(r['text'] or r['datetime'] or '-')[:110]} | {(r['component'] or '-')[:40]}")
        if args.csv_out:
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=[
                "stage", "case_id", "model", "harness", "status", "text", "component", "datetime"])
            writer.writeheader()
            writer.writerows(rows)
            write_text_create_only(buf.getvalue(), Path(args.csv_out))
            print("\nCSV scritto (create-only): " + args.csv_out)
        return 0
    if not (args.market_zip and args.openrca_dir):
        parser.error("servono --market-zip e --openrca-dir")
    report = run_scoring(args.records_dir, args.market_zip, args.openrca_dir)
    print(format_summary(report))
    if args.out:
        digest = write_report_create_only(report, Path(args.out))
        print(f"\nReport scritto (create-only): {args.out}\nSHA-256: {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
