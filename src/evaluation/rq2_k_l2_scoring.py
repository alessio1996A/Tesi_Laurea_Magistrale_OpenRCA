"""RQ2-K L2b: valutazione CON ground truth delle decisioni L2a. Processo SEPARATO da L2a.

Questo e' il solo modulo L2 in cui le etichette (record.csv) incontrano le decisioni della regola.
Non lo importa nulla che giri prima di L2a (un test lo verifica su `rq2_k_l2_execute`).

Che cosa fa
-----------
  1. verifica la catena di hash: freeze -> addendum -> decisioni L2a (nessuno manomesso, stesso
     codice L2, stesso commit, stessi parametri);
  2. costruisce i riferimenti per gruppo dalla ground truth, dopo gli stessi controlli di
     allineamento query/record dell'inventario (indice, task, istruzione, finestra, campi);
  3. chiama `rq2_k_rule_evaluation.evaluate_rule` con i parametri del freeze (H_pre, H, soglia
     esplorativa 2/3) e riporta il verdetto con gli intervalli di Clopper-Pearson;
  4. aggiunge, a solo scopo informativo, lo stato del componente di riferimento (in popolazione,
     escluso per KPI mancante, assente dalla telemetria del livello): se i nomi non coincidessero,
     lo si vedrebbe subito invece di leggere tanti NON_VALUTABILE senza spiegazione.

Il rapporto contiene dati a livello di gruppo, non l'associazione caso -> etichetta.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from zipfile import ZipFile

from evaluation import rq2_k_catalog as cat
from evaluation import rq2_k_l1_protocol as proto
from evaluation import rq2_k_l2_execute as l2x
from evaluation import rq2_k_rule_evaluation as ev
from evaluation.ood_class_inventory import (
    SCHEMAS, TARGET_REASONS, TARGETS, TASKS_COMPONENT, TASKS_REASON, TASKS_TIME,
    _load_member, _normalized,
)
from evaluation.v2_case_window_audit import MANIFEST_COLUMNS, _read_csv, _window

VERSION = "rq2_k_l2b_v1"
RESULT_SCHEMA = "rq2_k_l2b_evaluation_v1"
L2B_RELATIVE = "data/rq2_k_l2_v1/l2b_evaluation.json"
BEDS = ("cloudbed-1", "cloudbed-2")


class ReferenceError_(ValueError):
    """Allineamento query/record non verificato: la ground truth non e' utilizzabile."""


def read_reference_sources(zip_path: Path) -> dict:
    out = {}
    with ZipFile(zip_path, "r") as archive:
        for bed in BEDS:
            query, query_sha = _load_member(archive, f"Market/{bed}/query.csv", SCHEMAS["query"])
            record, record_sha = _load_member(archive, f"Market/{bed}/record.csv", SCHEMAS["record"])
            if len(query) != len(record):
                raise ReferenceError_(f"Numero di righe query/record diverso: {bed}")
            out[bed] = {"query": query, "record": record,
                        "query_csv_sha256": query_sha, "record_csv_sha256": record_sha}
    return out


def _case_record(case_id: str, entry: dict, sources: dict) -> dict:
    bed = entry["cloudbed"]
    match = re.fullmatch(r"(cloudbed-[12])_q(\d+)", case_id)
    if bed not in sources or match is None or match.group(1) != bed:
        raise ReferenceError_(f"Case ID o cloudbed incoerente: {case_id}")
    index = int(entry["query_index"])
    if index != int(match.group(2)) or not 0 <= index < len(sources[bed]["query"]):
        raise ReferenceError_(f"Indice di query incoerente: {case_id}")
    query, record = sources[bed]["query"][index], sources[bed]["record"][index]
    if query["task_index"] != entry["task_index"] or query["instruction"] != entry["instruction"]:
        raise ReferenceError_(f"Query archiviata diversa dal manifest: {case_id}")
    start, end = _window(entry)
    try:
        timestamp = int(record["timestamp"])
    except (TypeError, ValueError) as exc:
        raise ReferenceError_(f"Timestamp del record non valido: {case_id}") from exc
    if not start <= timestamp < end:
        raise ReferenceError_(f"Record fuori dalla finestra del manifest: {case_id}")
    if not record["reason"].strip() or not record["component"].strip():
        raise ReferenceError_(f"Campi della causa mancanti: {case_id}")
    score, task = query["scoring_points"], query["task_index"]
    if ((task in TASKS_REASON and record["reason"] not in score)
            or (task in TASKS_COMPONENT and record["component"] not in score)
            or (task in TASKS_TIME and record["datetime"] not in score)):
        raise ReferenceError_(f"Record non presente nei punti di punteggio: {case_id}")
    return {"record": record, "timestamp": timestamp}


def build_group_references(*, groups: list[dict], manifest: dict, sources: dict) -> list[dict]:
    """Riferimenti per gruppo: classi, guasti (componente, istante) e completezza."""
    references = []
    for group in groups:
        faults, complete, windows = [], True, []
        for case_id in group["case_ids"]:
            if case_id not in manifest:
                raise ReferenceError_(f"Caso assente dal manifest: {case_id}")
            entry = manifest[case_id]
            windows.append(_window(entry))
            found = _case_record(case_id, entry, sources)
            label = TARGET_REASONS.get(_normalized(found["record"]["reason"]))
            if label is None:
                complete = False                  # classe non riconosciuta: gruppo non valutabile
                continue
            faults.append({"fault_type": label, "component": found["record"]["component"].strip(),
                           "t_gt": found["timestamp"], "level": found["record"]["level"]})
        if (min(w[0] for w in windows), max(w[1] for w in windows)) != (group["start_unix"],
                                                                         group["end_unix"]):
            raise ReferenceError_(f"Finestra del gruppo diversa dal manifest: {group['group_id']}")
        references.append({"group_id": group["group_id"], "case_ids": sorted(group["case_ids"]),
                           "fault_types": sorted({f["fault_type"] for f in faults}),
                           "reference_complete": complete, "faults": faults})
    return references


def reference_component_status(references: list[dict], rule: dict) -> dict:
    """Informativo: dove sta il componente di riferimento rispetto alla popolazione."""
    target, out = rule["target_fault_type"], {}
    for ref in references:
        if target not in ref["fault_types"]:
            continue
        summary = rule["per_group"][ref["group_id"]]
        statuses = {}
        for fault in (f for f in ref["faults"] if f["fault_type"] == target):
            if "error" in summary:
                statuses[fault["component"]] = "senza_risultato"
            elif fault["component"] in set(summary["population"]):
                statuses[fault["component"]] = "in_popolazione"
            elif fault["component"] in set(summary["components_excluded"]):
                statuses[fault["component"]] = "escluso_per_kpi_mancante"
            else:
                statuses[fault["component"]] = "assente_dalla_telemetria_del_livello"
        out[ref["group_id"]] = dict(sorted(statuses.items()))
    return out


def evaluate_all(*, freeze: dict, addendum: dict, l2a: dict, references: list[dict]) -> list[dict]:
    params = freeze["parameters"]
    results = []
    for rule in l2a["rules"]:
        target = rule["target_fault_type"]
        if target not in TARGETS:
            raise ValueError(f"Classe della regola fuori dalla tassonomia chiusa: {target}")
        evaluation = ev.evaluate_rule(
            target_fault_type=target, known_fault_types=TARGETS, group_references=references,
            group_results=rule["per_group"], h_pre_seconds=params["h_pre_seconds"],
            h_seconds=params["h_seconds"],
            negative_coverage_min=params["l2"]["negative_coverage_min_exploratory"],
            rules_tested=addendum["rules_tested"])
        results.append({"stage_id": rule["stage_id"], "rule_name": rule["rule_name"],
                        "rule_sha256": rule["rule_sha256"], "target_fault_type": target,
                        "decisions_sha256": rule["decisions_sha256"], "caveats": rule["caveats"],
                        "evaluation": evaluation,
                        "reference_component_status": reference_component_status(references, rule)})
    return results


def verify_chain(*, freeze: dict, addendum: dict, l2a: dict, changed_files: list[str],
                 manifest_sha256: str) -> list[str]:
    """Catena freeze -> addendum -> L2a: nessun anello manomesso, stesso codice."""
    problems = []
    if not proto.freeze_is_intact(freeze):
        problems.append("freeze_manomesso")
    if not l2x.addendum_is_intact(addendum):
        problems.append("addendum_manomesso")
    if not l2x.l2a_is_intact(l2a):
        problems.append("decisioni_l2a_manomesse")
    if problems:
        return problems
    freeze_sha = freeze["sha256_of_body_without_this_field"]
    if addendum["freeze_sha256"] != freeze_sha or l2a["freeze_sha256"] != freeze_sha:
        problems.append("freeze_sha_non_coerente")
    if l2a["addendum_sha256"] != addendum["sha256_of_body_without_this_field"]:
        problems.append("addendum_sha_non_coerente_con_l2a")
    if l2a["uses_ground_truth"] or l2a["ground_truth_opened"]:
        problems.append("l2a_dichiara_uso_di_gt")
    if l2a["groups"] != addendum["groups"]:
        problems.append("gruppi_diversi_dall_addendum")
    if addendum["l2_sources_sha256"] != l2x.l2_sources_sha256():
        problems.append("moduli_l2_diversi_dall_addendum")
    if addendum["loaders_sha256"] != l2x.loaders_sha256():
        problems.append("loader_diversi_dall_addendum")
    if l2a["l2_code_commit"] != addendum["l2_code_commit"]:
        problems.append("commit_l2_incoerente_con_l2a")
    if addendum["freeze_code_commit"] != freeze["code_commit"]:
        problems.append("commit_del_freeze_diverso")
    bad = [p for p in changed_files if not l2x._is_allowed_after_freeze(p)]
    if bad:
        problems.append("file_cambiati_dopo_il_freeze: " + ", ".join(bad))
    if addendum["manifest_sha256"] != manifest_sha256:
        problems.append("manifest_diverso_dall_addendum")
    if addendum["parameters_sha256"] != freeze["parameters_sha256"]:
        problems.append("parametri_diversi_dal_freeze")
    if [r["rule_sha256"] for r in l2a["rules"]] != [r["rule_sha256"] for r in addendum["rules"]]:
        problems.append("regole_diverse_dall_addendum")
    return problems


def build_report(*, freeze, addendum, l2a, references, results, sources) -> dict:
    body = {
        "schema": RESULT_SCHEMA, "protocol_version": VERSION,
        "freeze_sha256": freeze["sha256_of_body_without_this_field"],
        "addendum_sha256": addendum["sha256_of_body_without_this_field"],
        "l2a_sha256": l2a["sha256_of_body_without_this_field"],
        "l2_code_commit": addendum["l2_code_commit"],
        "uses_ground_truth": True, "rules_tested": addendum["rules_tested"],
        "source_csv_sha256": {bed: {"query": s["query_csv_sha256"], "record": s["record_csv_sha256"]}
                              for bed, s in sources.items()},
        "groups": [{"group_id": r["group_id"], "cases": len(r["case_ids"]),
                    "fault_types": r["fault_types"], "reference_complete": r["reference_complete"]}
                   for r in references],
        "results": results,
        "claim": freeze["parameters"]["l2"]["claim"],
    }
    return {**body, "sha256_of_body_without_this_field": proto._sha(body)}


def render_report(report: dict) -> str:
    lines = [f"L2b ({report['protocol_version']}) | addendum {report['addendum_sha256'][:16]} | "
             f"decisioni L2a {report['l2a_sha256'][:16]} | regole provate: {report['rules_tested']}"]
    for res in report["results"]:
        evaluation, counts = res["evaluation"], res["evaluation"]["counts"]
        det = evaluation["detection"]
        lines += ["-" * 74, f"{res['rule_name']} -> {res['target_fault_type']}",
                  f"  VERDETTO: {evaluation['verdict']} {evaluation['reasons']}",
                  f"  TP {counts['tp']} FN {counts['fn']} TN {counts['tn']} FP {counts['fp']} | "
                  f"positivi completi {det['positives_complete']} | localizzati {det['tp_localized']} "
                  f"| IC95% {det['interval95_localized_over_positives']}",
                  f"  FP: {evaluation['false_positives']['fp']}/"
                  f"{evaluation['false_positives']['negatives_complete']} "
                  f"IC95% {evaluation['false_positives']['interval95']}",
                  f"  positivi non osservabili: {evaluation['positives_not_observable']['count']} "
                  f"{evaluation['positives_not_observable']['groups']}",
                  f"  copertura popolazione: {evaluation['population']}",
                  f"  stato del componente di riferimento: {res['reference_component_status']}"]
        lines += [f"  CAUTELA: {c}" for c in res["caveats"]]
        lines.append(f"  {evaluation['caveat']}")
    lines += ["=" * 74, f"claim: {report['claim']}",
              f"corpo: {report['sha256_of_body_without_this_field']}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--drive-root", type=Path, required=True)
    parser.add_argument("--repo-dir", type=Path, required=True)
    parser.add_argument("--authorize-ground-truth", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    if not args.authorize_ground_truth:
        print("Serve --authorize-ground-truth: L2b legge la ground truth dei sigillati.")
        return 2
    root = args.drive_root
    freeze = json.loads((root / proto.FREEZE_RELATIVE).read_text(encoding="utf-8"))
    addendum = json.loads((root / l2x.ADDENDUM_RELATIVE).read_text(encoding="utf-8"))
    l2a = json.loads((root / l2x.L2A_RELATIVE).read_text(encoding="utf-8"))
    manifest_path = root / cat.MANIFEST_RELATIVE
    problems = verify_chain(freeze=freeze, addendum=addendum, l2a=l2a,
                            changed_files=l2x._git_changed_files(args.repo_dir, freeze["code_commit"]),
                            manifest_sha256=proto._file_sha256(manifest_path))
    if problems:
        print("CATENA DI HASH NON COERENTE, L2b non parte:", *problems, sep="\n  - ")
        return 2
    print("Catena freeze -> addendum -> decisioni L2a verificata.\n")
    manifest = _read_csv(manifest_path, MANIFEST_COLUMNS)
    sources = read_reference_sources(root / "Market.zip")
    references = build_group_references(groups=addendum["groups"], manifest=manifest, sources=sources)
    results = evaluate_all(freeze=freeze, addendum=addendum, l2a=l2a, references=references)
    report = build_report(freeze=freeze, addendum=addendum, l2a=l2a, references=references,
                          results=results, sources=sources)
    print(render_report(report))
    if not args.no_write:
        target = root / L2B_RELATIVE
        proto._write_new(target, report)
        print(f"\nScritto (create-only): {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
