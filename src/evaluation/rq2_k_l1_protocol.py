"""RQ2-K: congelamento del protocollo L1/L2 e run L1 sui 4 incidenti di discovery.

Due comandi, nessuna etichetta, nessuna chiamata a modelli, nessun incidente sigillato:

  freeze  legge i record K, il catalogo e la telemetria dei SOLI 4 casi di discovery, verifica
          l'integrita' del run e scrive UN file create-only (`freeze.json`) con: commit del
          codice, hash della tabella semantica, elenco delle candidate (con hash della regola),
          elenco delle eseguibili, elenco delle ammesse a L2, parametri (H_pre, H, griglia,
          popolazione, soglie) e criteri L1/L2.
  run     rilegge il freeze e SI RIFIUTA di partire se codice, tabella, record, catalogo o
          elenchi non coincidono; poi esegue le regole eseguibili sui 4 casi di discovery e
          scrive un report create-only. Niente confronto con la ground truth: L1 e' solo
          eseguibilita' (la GT entra solo in L2, in un processo separato, dopo la lettura del
          report).

Controlli separati dalla classificazione (decisione (b) del 16 nov)
------------------------------------------------------------------
Una regola FORMALIZZABILE (un solo livello e una sola classe) non e' per questo ammessa a L2:
servono anche, ciascuno dichiarato a parte, i controlli su UNITA' (nessuna incoerenza col nome
del KPI), STORIA (ogni componente che espone il KPI ha campione nella prima finestra e storia
completa, in tutti i casi) e CONDIZIONI (nessuna soglia irraggiungibile in tutti i casi, nessun
contatore cumulativo usato senza `delta`). Ammessa a L2 = FORMALIZZABILE + tutti i controlli.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from evaluation import rq2_k_catalog as cat
from evaluation import rq2_k_l1_preflight as pf
from evaluation import rq2_k_records as rk
from evaluation import rq2_k_rule_evaluation as ev
from evaluation import rq2_k_rule_executor as ex
from evaluation import rq2_k_run_integrity as integ

VERSION = "rq2_k_l1_protocol_v1"
FREEZE_SCHEMA = "rq2_k_l1_l2_freeze_v1"
REPORT_SCHEMA = "rq2_k_l1_report_v1"
FREEZE_RELATIVE = "data/rq2_k_freeze_v1/freeze.json"
REPORT_RELATIVE = "data/rq2_k_l1_v1/l1_report.json"
CATALOG_RELATIVE = "data/rq2_k_catalog_v1/catalog_discovery.json"
STORE_RELATIVE = "data/rq2_v5_format_fair_v1"

L1_MIN_EVALUABLE_FRACTION = 0.95
UNREACHABLE = ("soglia_sopra_il_massimo_osservato", "soglia_sotto_il_minimo_osservato")

# Parametri CONGELATI (valgono per tutte le regole, fissati prima di aprire i sigillati).
PARAMETERS = {
    "grid_seconds": ex.GRID_SECONDS_DEFAULT,
    "h_pre_seconds": 60,
    "h_seconds": 300,
    "h_note": ("convenzione operativa uguale per tutte le regole, pari a 1 e 5 passi di "
               "campionamento (60 s); NON e' una tolleranza certificata dallo scorer Microsoft"),
    "windows": "finestre causali (t - w, t], estremo sinistro escluso; storia caricata da "
               "start - max(window_seconds) della regola",
    "unknown_logic": "Kleene a tre valori: una lacuna non e' mai trasformata in falso",
    "population": ("componenti del livello con almeno un campione finito per OGNI KPI della "
                   "regola nella finestra di gruppo; gli esclusi sono tutti contati e nominati; "
                   "la copertura e' popolazione/totale; un negativo vale solo per la popolazione"),
    "group_decision": ("positive se almeno una cella e' vera; negative solo se nessuna cella e' "
                       "vera e nessuna e' sconosciuta nella popolazione; abstain altrimenti"),
    "l1": {"cases": list(cat.DISCOVERY_CASES), "uses_ground_truth": False,
           "pass_criteria": {"executes_without_error": True,
                             "population_nonempty_in_every_case": True,
                             "min_evaluable_fraction": L1_MIN_EVALUABLE_FRACTION,
                             "history_files_present": True,
                             "components_total_matches_catalog": True}},
    "l2": {"unit": "temporal_window_group",
           "target_class": "quella della tabella semantica congelata; nessuna regola senza classe",
           "verdict_gate": ("VERIFICATA_OPERATIVAMENTE solo con 0 FN, 0 FP, ogni positivo "
                            "valutabile rilevato E localizzato (componente di riferimento tra "
                            "quelli che scattano, primo scatto in [t_gt - H_pre, t_gt + H]) e "
                            "copertura dei negativi ammissibili >= soglia esplorativa; altrimenti "
                            "NON_VERIFICATA (prova contraria) o NON_VALUTABILE (lacuna)"),
           "negative_coverage_min_exploratory": ev.NEGATIVE_COVERAGE_MIN,
           "reference_component_not_observable": ("il positivo e' NON_VALUTABILE: fuori dai "
                                                 "denominatori di TP/FN, contato e nominato a parte"),
           "negatives_scope": "un TN vale solo per i componenti osservabili, non per l'intero livello",
           "interval": "Clopper-Pearson 95% (esatto)",
           "claim": ("caso di studio di verifica operativa preliminare su una sola candidata; "
                     "nessuna affermazione di generalizzazione"),
           "reported_with": "numero di regole provate (rules_tested) = tutte le candidate"},
    "l3": "non rivendicato",
}


class FreezeError(RuntimeError):
    """Il congelamento non puo' essere scritto o verificato."""


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def parameters_sha256() -> str:
    return _sha(PARAMETERS)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------- controlli per regola

def eligibility_for(rows: list[dict], history: dict) -> dict[str, dict]:
    """Per ogni regola eseguibile: controlli separati e ammissione a L2."""
    by_id = {c["stage_id"]: c for c in history["checks"]}
    out: dict[str, dict] = {}
    for row in rows:
        if not row["executable"]:
            continue
        check = by_id.get(row["stage_id"])
        unit_ok = not any(str(c["unit_check"]).startswith("incoerente") for c in row["conditions"])
        history_ok, conditions_ok, notes = check is not None, check is not None, []
        for cond, hist in zip(row["conditions"], (check or {"conditions": []})["conditions"]):
            cases = hist["cases"]
            if len(cases) != len(cat.DISCOVERY_CASES) or any(
                    i["components_with_kpi"] == 0
                    or i["with_sample_in_first_window"] != i["components_with_kpi"]
                    or i["with_full_history"] != i["components_with_kpi"] for i in cases.values()):
                history_ok = False
                notes.append(f"storia_incompleta:{cond['metric']}")
            if cases and all(i["threshold"] in UNREACHABLE for i in cases.values()):
                conditions_ok = False
                notes.append(f"soglia_mai_raggiungibile:{cond['metric']}")
            if any(i["cumulative_counter_hint"] for i in cases.values()):
                conditions_ok = False
                notes.append(f"contatore_cumulativo_senza_delta:{cond['metric']}")
        if not unit_ok:
            notes.append("unita_incoerente")
        classifiable = row["l1_outcome"] == pf.FORMALIZABLE
        out[row["stage_id"]] = {
            "classification": row["l1_outcome"], "classes": row["classes"],
            "unit_ok": unit_ok, "history_ok": history_ok, "conditions_ok": conditions_ok,
            "notes": notes,
            "eligible_for_l2": bool(classifiable and unit_ok and history_ok and conditions_ok)}
    return out


# ---------------------------------------------------------------- freeze

def build_freeze(*, table: dict, history: dict, integrity: dict, catalog_sha256: str,
                 code_commit: str | None, created_utc: str | None = None) -> dict:
    if not integrity.get("ok"):
        raise FreezeError("Integrita' del run non verificata: niente congelamento")
    if not code_commit:
        raise FreezeError("Commit del codice sconosciuto: niente congelamento")
    eligibility = eligibility_for(table["rows"], history)
    candidates = []
    for row in table["rows"]:
        candidates.append({
            "stage_id": row["stage_id"], "case_id": row["case_id"], "model": row["model"],
            "harness": row["harness"], "rule_name": row["rule_name"],
            "rule_sha256": row["rule_sha256"], "l1_outcome": row["l1_outcome"],
            "executable": row["executable"], "classes": row["classes"], "reason": row["reason"],
            "caveats": row["caveats"],
            "required_history_seconds": row["required_history_seconds"],
            "eligibility": eligibility.get(row["stage_id"])})
    executable = sorted((c["stage_id"], c["rule_sha256"]) for c in candidates if c["executable"])
    eligible = sorted((c["stage_id"], c["rule_sha256"], c["classes"][0]) for c in candidates
                      if (c["eligibility"] or {}).get("eligible_for_l2"))
    body = {
        "schema": FREEZE_SCHEMA, "protocol_version": VERSION,
        "created_utc": created_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "code_commit": code_commit,
        "versions": {"preflight": pf.VERSION, "executor": ex.VERSION, "evaluation": ev.VERSION,
                     "semantic_table": pf.SEMANTIC_TABLE_VERSION},
        "semantic_table_sha256": table["semantic_table_sha256"],
        "parameters": PARAMETERS, "parameters_sha256": parameters_sha256(),
        "run": {"frozen_discovery_commit": integrity["expected_commit"],
                "records_fingerprint_sha256": integrity["records_fingerprint_sha256"],
                "plan_preview_sha256": (integrity.get("manifest") or {}).get("plan_preview_sha256"),
                "stages": integrity["stages_in_plan"], "integrity_ok": True},
        "catalog_sha256": catalog_sha256,
        "rules_tested": len(candidates),
        "candidates": candidates,
        "executable": [list(x) for x in executable], "executable_sha256": _sha(executable),
        "l2_eligible": [list(x) for x in eligible], "l2_eligible_sha256": _sha(eligible),
        "statement": ("Congelato PRIMA di aprire gli 11 incidenti sigillati e prima di leggere "
                      "qualunque ground truth. I criteri di ammissione sono stati scritti dopo "
                      "aver visto il preflight sui 4 casi di discovery (non ciechi) ma non usano "
                      "etichette."),
    }
    return {**body, "sha256_of_body_without_this_field": _sha(body)}


def freeze_is_intact(freeze: dict) -> bool:
    core = {k: v for k, v in freeze.items() if k != "sha256_of_body_without_this_field"}
    return _sha(core) == freeze.get("sha256_of_body_without_this_field")


def _write_new(path: Path, payload: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as handle:             # create-only
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)


def verify_freeze(freeze: dict, *, table: dict, integrity: dict, catalog_sha256: str,
                  code_commit: str | None) -> list[str]:
    """Elenco delle differenze tra il freeze e lo stato attuale (vuoto = coincide)."""
    problems = []
    if not freeze_is_intact(freeze):
        problems.append("freeze_manomesso_o_corrotto")
    if freeze.get("schema") != FREEZE_SCHEMA:
        problems.append("schema_diverso")
    if freeze.get("code_commit") != code_commit:
        problems.append(f"commit_del_codice_diverso: {freeze.get('code_commit')} != {code_commit}")
    if freeze.get("parameters_sha256") != parameters_sha256() or freeze.get("parameters") != PARAMETERS:
        problems.append("parametri_diversi")
    if freeze.get("semantic_table_sha256") != table["semantic_table_sha256"]:
        problems.append("tabella_semantica_diversa")
    if freeze.get("catalog_sha256") != catalog_sha256:
        problems.append("catalogo_diverso")
    if not integrity.get("ok"):
        problems.append("integrita_del_run_non_verificata")
    run = freeze.get("run") or {}
    if run.get("records_fingerprint_sha256") != integrity.get("records_fingerprint_sha256"):
        problems.append("impronta_dei_record_diversa")
    current = sorted((r["stage_id"], r["rule_sha256"]) for r in table["rows"] if r["executable"])
    if freeze.get("executable_sha256") != _sha(current):
        problems.append("elenco_delle_eseguibili_diverso")
    if freeze.get("rules_tested") != len(table["rows"]):
        problems.append("numero_di_candidate_diverso")
    return problems


# ---------------------------------------------------------------- run L1

def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=cat.COLUMNS)


def _summarise(result: dict) -> dict:
    fires = result["first_fire_unix_by_component"]
    return {k: result[k] for k in (
        "decision", "reason", "level", "components_total", "components_in_population",
        "population_coverage", "components_excluded", "excluded_missing_metrics", "cells",
        "evaluable_fraction", "unknown_by_cause")} | {
        "firing_components": sorted(fires), "firing_component_count": len(fires),
        "first_fire_unix_by_component": fires}


def run_l1(*, freeze: dict, table: dict, catalog: dict, zip_path: Path, manifest_path: Path,
           cases: tuple[str, ...] = cat.DISCOVERY_CASES) -> dict:
    """Esegue le regole eseguibili sui casi di discovery. Nessuna etichetta in ingresso."""
    kpi_levels = pf.kpi_level_map(catalog)
    kinds = {level: kind for kind, level in cat.LEVELS.items()}
    runnable = [r for r in table["rows"] if r["executable"]]
    eligible_ids = {x[0] for x in freeze["l2_eligible"]}
    max_window = {"node": 0, "container": 0}
    for row in runnable:
        level = row["conditions"][0]["level"]
        max_window[level] = max(max_window[level], row["required_history_seconds"])

    frames: dict[tuple[str, str], pd.DataFrame] = {}
    missing_files: dict[str, list[str]] = {}
    loaded = {c: cat.load_case(manifest_path, c) for c in cases}           # solo discovery
    needed_levels = sorted({r["conditions"][0]["level"] for r in runnable})
    for case_id, case in loaded.items():
        for level in needed_levels:
            frame, missing = pf.read_interval(zip_path, case["cloudbed"], kinds[level],
                                              case["start_unix"] - max_window[level], case["end_unix"])
            frames[(case_id, level)] = frame
            if missing:
                missing_files[f"{case_id}:{level}"] = missing

    out_rules = []
    for row in runnable:
        level = row["conditions"][0]["level"]
        per_case, failures = {}, []
        for case_id, case in loaded.items():
            telemetry = {lv: _empty_frame() for lv in ex.LEVELS}
            telemetry[level] = frames[(case_id, level)]
            try:
                result = ex.execute_rule(
                    {"status": "candidate", "combination": row["combination"],
                     "conditions": [{k: c[k] for k in ("metric", "operator", "threshold",
                                                       "aggregation", "window_seconds")}
                                    | {"unit": c["unit_declared"]} for c in row["conditions"]]},
                    telemetry, start_unix=case["start_unix"], end_unix=case["end_unix"],
                    history_start_unix=case["start_unix"] - row["required_history_seconds"],
                    kpi_levels=kpi_levels)
            except ex.RuleExecutionError as exc:
                per_case[case_id] = {"error": str(exc)[:200]}
                failures.append(f"{case_id}:errore_dell_esecutore")
                continue
            summary = _summarise(result)
            expected_total = catalog["per_case"][case_id]["components_total"][level]
            summary["components_total_in_catalog"] = expected_total
            per_case[case_id] = summary
            if summary["components_in_population"] == 0:
                failures.append(f"{case_id}:popolazione_vuota")
            fraction = summary["evaluable_fraction"]
            if fraction is None or fraction < L1_MIN_EVALUABLE_FRACTION:
                failures.append(f"{case_id}:copertura_valutabile_{fraction}")
            if summary["components_total"] != expected_total:
                failures.append(f"{case_id}:componenti_totali_diversi_dal_catalogo")
            if missing_files.get(f"{case_id}:{level}"):
                failures.append(f"{case_id}:file_storici_assenti")
        eligible = row["stage_id"] in eligible_ids
        out_rules.append({
            "stage_id": row["stage_id"], "rule_name": row["rule_name"],
            "rule_sha256": row["rule_sha256"], "l1_outcome": row["l1_outcome"],
            "classes": row["classes"], "caveats": row["caveats"],
            "eligible_for_l2": eligible,
            "reporting": "candidata_a_L2" if eligible else "descrittivo_solo_L1",
            "l1_pass": not failures, "l1_failures": failures, "per_case": per_case})
    admitted = sorted(r["stage_id"] for r in out_rules if r["eligible_for_l2"] and r["l1_pass"])
    return {"schema": REPORT_SCHEMA, "protocol_version": VERSION,
            "freeze_sha256": freeze["sha256_of_body_without_this_field"],
            "code_commit": freeze["code_commit"], "cases": list(cases),
            "uses_ground_truth": False, "sealed_incidents_opened": False,
            "rules": out_rules, "admitted_to_l2": admitted,
            "admitted_to_l2_sha256": _sha(admitted),
            "history_files_missing": missing_files}


def render_report(report: dict) -> str:
    lines = [f"Report L1 ({report['protocol_version']}) | freeze {report['freeze_sha256'][:16]} | "
             f"commit {str(report['code_commit'])[:12]}",
             f"  GT usata: {report['uses_ground_truth']} | sigillati aperti: "
             f"{report['sealed_incidents_opened']} | casi: {', '.join(report['cases'])}"]
    if report["history_files_missing"]:
        lines.append(f"  FILE STORICI ASSENTI: {report['history_files_missing']}")
    for rule in report["rules"]:
        lines += ["-" * 74, f"{rule['rule_name']}  [{rule['stage_id'].split(':', 1)[-1]}]",
                  f"  classificazione: {rule['l1_outcome']} {rule['classes']} | "
                  f"ammessa a L2 dal freeze: {rule['eligible_for_l2']} | resoconto: {rule['reporting']}",
                  f"  L1: {'PASSATO' if rule['l1_pass'] else 'NON PASSATO'} {rule['l1_failures']}"]
        lines += [f"  CAUTELA: {c}" for c in rule["caveats"]]
        for case_id, info in sorted(rule["per_case"].items()):
            if "error" in info:
                lines.append(f"    {case_id}: ERRORE {info['error']}")
                continue
            lines.append(
                f"    {case_id}: {info['decision']:8s} popolazione {info['components_in_population']}/"
                f"{info['components_total']} (catalogo {info['components_total_in_catalog']}, "
                f"esclusi {len(info['components_excluded'])}) | valutabili "
                f"{info['evaluable_fraction']} | celle vere {info['cells']['true']}/"
                f"{info['cells']['total']} | componenti che scattano {info['firing_component_count']} "
                f"| sconosciuti {info['unknown_by_cause']}")
    lines += ["=" * 74, f"AMMESSE A L2 (eleggibili nel freeze E L1 passato): {report['admitted_to_l2']}",
              "I sigillati NON sono stati aperti. Prima si legge questo report."]
    return "\n".join(lines)


def render_freeze(freeze: dict) -> str:
    lines = [f"CONGELAMENTO ({freeze['schema']}) | codice {freeze['code_commit']}",
             f"  tabella semantica   : {freeze['versions']['semantic_table']} "
             f"{freeze['semantic_table_sha256']}",
             f"  parametri           : {freeze['parameters_sha256']}  "
             f"(H_pre={freeze['parameters']['h_pre_seconds']} s, H={freeze['parameters']['h_seconds']} s)",
             f"  run (impronta record): {freeze['run']['records_fingerprint_sha256']}",
             f"  catalogo            : {freeze['catalog_sha256']}",
             f"  candidate provate   : {freeze['rules_tested']}",
             f"  eseguibili          : {len(freeze['executable'])}  {freeze['executable_sha256']}",
             f"  ammesse a L2        : {len(freeze['l2_eligible'])}  {freeze['l2_eligible_sha256']}"]
    for cand in freeze["candidates"]:
        el = cand["eligibility"]
        extra = ("" if el is None else
                 f" | unita={el['unit_ok']} storia={el['history_ok']} condizioni={el['conditions_ok']} "
                 f"-> ammessa={el['eligible_for_l2']} {el['notes']}")
        lines.append(f"  - {cand['rule_name'][:48]:48s} {cand['l1_outcome']:36s}{extra}")
    lines.append(f"  corpo: {freeze['sha256_of_body_without_this_field']}")
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI

def _context(args) -> dict:
    root = args.drive_root
    store = root / STORE_RELATIVE
    catalog_path = root / CATALOG_RELATIVE
    from evaluation.rq2_v5_run_cli import _plan_rows
    plan, rows = _plan_rows()
    integrity = integ.check_integrity(store, rows, plan_preview_sha256=plan["preview_sha256"])
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    table = pf.build_table(rk.load_k_entries(store / "records"), catalog)
    return {"root": root, "integrity": integrity, "catalog": catalog, "table": table,
            "catalog_sha256": _file_sha256(catalog_path),
            "zip": root / "Market.zip", "manifest": root / cat.MANIFEST_RELATIVE,
            "code_commit": cat._git_head(args.repo_dir)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("freeze", "run"):
        p = sub.add_parser(name)
        p.add_argument("--drive-root", type=Path, required=True)
        p.add_argument("--repo-dir", type=Path, required=True)
        p.add_argument("--no-write", action="store_true")
    args = parser.parse_args(argv)
    ctx = _context(args)
    freeze_path = ctx["root"] / FREEZE_RELATIVE

    if args.command == "freeze":
        history = pf.history_report(ctx["zip"], ctx["manifest"], ctx["table"]["rows"])
        freeze = build_freeze(table=ctx["table"], history=history, integrity=ctx["integrity"],
                              catalog_sha256=ctx["catalog_sha256"], code_commit=ctx["code_commit"])
        print(render_freeze(freeze))
        if not args.no_write:
            _write_new(freeze_path, freeze)
            print(f"\nScritto (create-only): {freeze_path}")
        return 0

    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    problems = verify_freeze(freeze, table=ctx["table"], integrity=ctx["integrity"],
                             catalog_sha256=ctx["catalog_sha256"], code_commit=ctx["code_commit"])
    if problems:
        print("FREEZE NON COINCIDE, il run L1 non parte:", *problems, sep="\n  - ")
        return 2
    print("Freeze verificato: codice, tabella, parametri, record, catalogo ed elenchi coincidono.\n")
    report = run_l1(freeze=freeze, table=ctx["table"], catalog=ctx["catalog"],
                    zip_path=ctx["zip"], manifest_path=ctx["manifest"])
    print(render_report(report))
    if not args.no_write:
        target = ctx["root"] / REPORT_RELATIVE
        _write_new(target, report)
        print(f"\nScritto (create-only): {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
