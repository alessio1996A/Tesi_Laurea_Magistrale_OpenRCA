"""RQ2-K L2a: esecuzione della regola congelata sui gruppi temporali dei sigillati, SENZA ground truth.

Che cosa fa
-----------
Due comandi, entrambi GT-free:
  * `addendum`: scrive (create-only) l'addendum al freeze con l'elenco degli 11 sigillati, i gruppi
    temporali costruiti dalle sole finestre del manifest, l'hash del release pre-registrato, l'hash
    del report L1 letto da GPT e da Alessio, e l'hash dei moduli L2. Non legge telemetria.
  * `run` (serve `--authorize-sealed-telemetry`): verifica freeze e addendum, esegue la regola
    ammessa sui gruppi e scrive (create-only) le decisioni. Legge la telemetria dei sigillati, mai
    la ground truth. Le decisioni sono sigillate con hash PRIMA che qualcuno guardi le etichette.

Garanzie
--------
  * Nessun import del lato GT (valutatore, scorer di gruppo, inventario delle classi): un test lo
    verifica sul sorgente.
  * Il freeze originale resta valido: `run` ricalcola tabella, parametri, record e catalogo, e
    accetta solo modifiche al codice che siano nuovi file L2, test o documenti.
  * I gruppi sono componenti connesse di finestre (estremi inclusi, stesso cloudbed), come nella
    partizione pre-registrata; il loro numero deve coincidere con `test_window_groups` del release.
  * Il manifest e' rifiutato se contiene colonne di ground truth; i casi di discovery sono rifiutati.
"""
from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from evaluation import rq2_k_catalog as cat
from evaluation import rq2_k_l1_preflight as pf
from evaluation import rq2_k_l1_protocol as proto
from evaluation import rq2_k_rule_executor as ex

VERSION = "rq2_k_l2a_v1"
ADDENDUM_SCHEMA = "rq2_k_l2_addendum_v1"
RESULT_SCHEMA = "rq2_k_l2a_decisions_v1"
ADDENDUM_RELATIVE = "data/rq2_k_freeze_v1/l2_addendum.json"
L2A_RELATIVE = "data/rq2_k_l2_v1/l2a_decisions.json"
RELEASE_RELATIVE = "data/rq2/RQ2_SCIENTIFIC_DISCOVERY_RELEASE_V1.json"      # dentro il repository
L2_SOURCES = ("rq2_k_l2_execute.py", "rq2_k_l2_scoring.py")
# Moduli gia' esistenti che L2a/L2b usano per leggere telemetria, manifest e archivio: ne registriamo
# l'hash nell'addendum (percorsi relativi a `src`). Un test controlla che coprano tutti gli import.
LOADER_FILES = ("agent/tools.py", "evaluation/rq2_k_catalog.py", "evaluation/rq2_k_l1_preflight.py",
                "evaluation/rq2_k_l1_protocol.py", "evaluation/rq2_k_rule_executor.py",
                "evaluation/rq2_k_rule_evaluation.py", "evaluation/rq2_rule_group_scorer.py",
                "evaluation/ood_class_inventory.py", "evaluation/ood_holdout_preflight.py",
                "evaluation/v2_case_window_audit.py")
WINDOW_COLUMNS = ("case_id", "cloudbed", "start_unix", "end_unix")        # le sole colonne lette
ALLOWED_AFTER_FREEZE_FILES = frozenset("src/evaluation/" + name for name in L2_SOURCES)
ALLOWED_AFTER_FREEZE_PREFIXES = ("src/tests/", "docs/")


GROUP_DEFINITION = ("Componenti connesse delle finestre [start, end] dei casi sigillati, nello stesso "
                    "cloudbed, con estremi inclusi (due finestre che si toccano o si sovrappongono sono lo "
                    "stesso gruppo); finestra del gruppo = unione; id W01.. ordinati per cloudbed, inizio, "
                    "primo case_id. Il numero deve coincidere con test_window_groups del release.")
POPULATION_POLICY = ("Popolazione osservabile: componenti del livello con almeno un campione finito per "
                     "ogni KPI della regola nella finestra del gruppo; gli esclusi sono contati e nominati; "
                     "un negativo vale solo per la popolazione.")
DECISIONS_FORMAT = ("File create-only `l2a_decisions.json` con corpo e SHA-256 del corpo. Per ogni regola e "
                    "gruppo: decisione (positive/negative/abstain/error), popolazione, componenti esclusi con "
                    "KPI mancanti, componenti che scattano e primo istante di scatto (unix), celle vere/false/"
                    "sconosciute, copertura di popolazione; `decisions_sha256` = SHA-256 della mappa "
                    "gruppo -> decisione. L2b verifica tutti gli hash PRIMA di leggere la ground truth.")
HANDLING = {
    "reference_incomplete": ("un gruppo con una classe non riconosciuta nella ground truth ha "
                             "reference_complete=false: fuori dai denominatori di TP, FP, TN, FN, contato "
                             "come non valutabile"),
    "reference_component_not_observable": ("positivo con componente di riferimento fuori dalla popolazione: "
                                           "NON_VALUTABILE, fuori dai denominatori, contato e nominato a parte; "
                                           "non e' un falso negativo"),
    "abstain_or_error": ("astensione o errore su un positivo o su un negativo: nessuna conclusione, riportato "
                         "nella copertura; sui positivi impedisce VERIFICATA_OPERATIVAMENTE"),
    "negative_scope": "un negativo vale solo per i componenti osservabili, non per l'intero livello",
    "no_complete_positive": "nessun positivo completo e valutabile: NON_VALUTABILE",
}
ANNOTATIONS = (
    "Il documento di congelamento (prima versione) e il registro citavano il commit di codice "
    "2474886a551044565b062806a12a6ff9730b3299; il freeze effettivamente eseguito il 16 novembre registra "
    "invece 88e46580c38dd89cbfae8076ba0752776c1c12b5, commit successivo che isola il modulo L1 dal lato "
    "ground truth e aggiunge l'hash dei sorgenti congelati. Vale il commit registrato nel freeze. "
    "freeze.json non e' stato modificato.",
    "Le regole candidate, i risultati L1, il commit di discovery ddb2ca4 e i parametri non cambiano.",
)


class L2ScopeError(ValueError):
    """Ingresso fuori perimetro: caso non sigillato, manifest con GT, gruppi incoerenti."""


# ---------------------------------------------------------------- casi e gruppi (solo finestre)
def load_cases(manifest_path: Path, case_ids) -> list[dict]:
    """Finestre dei casi sigillati dal manifest (senza etichette)."""
    ids = sorted(case_ids)
    if not ids or len(set(ids)) != len(ids):
        raise L2ScopeError("Elenco dei casi vuoto o con duplicati")
    if set(ids) & set(cat.DISCOVERY_CASES):
        raise L2ScopeError("Un caso di discovery non puo' stare nell'insieme sigillato")
    header = set(pd.read_csv(manifest_path, nrows=0).columns)
    if cat.GT_COLUMNS & header:
        raise L2ScopeError("Il manifest contiene colonne di ground truth.")
    if not set(WINDOW_COLUMNS) <= header:
        raise L2ScopeError("Il manifest non ha le colonne delle finestre.")
    manifest = pd.read_csv(manifest_path, usecols=list(WINDOW_COLUMNS))      # nessun altro campo
    cases = []
    for case_id in ids:
        rows = manifest.loc[manifest["case_id"] == case_id]
        if len(rows) != 1:
            raise L2ScopeError(f"Case ID assente o duplicato nel manifest: {case_id}")
        row = rows.iloc[0]
        case = {"case_id": case_id, "cloudbed": str(row["cloudbed"]),
                "start_unix": int(row["start_unix"]), "end_unix": int(row["end_unix"])}
        if case["cloudbed"] not in ("cloudbed-1", "cloudbed-2"):
            raise L2ScopeError(f"Cloudbed non valido: {case_id}")
        if case["start_unix"] >= case["end_unix"]:
            raise L2ScopeError(f"Intervallo non valido: {case_id}")
        cases.append(case)
    return cases


def build_window_groups(cases: list[dict]) -> list[dict]:
    """Componenti connesse di finestre nello stesso cloudbed (estremi inclusi)."""
    parent = {c["case_id"]: c["case_id"] for c in cases}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in itertools.combinations(cases, 2):
        if (a["cloudbed"] == b["cloudbed"] and a["start_unix"] <= b["end_unix"]
                and b["start_unix"] <= a["end_unix"]):
            parent[find(a["case_id"])] = find(b["case_id"])
    members: dict[str, list[dict]] = {}
    for case in cases:
        members.setdefault(find(case["case_id"]), []).append(case)
    groups = [{"cloudbed": ms[0]["cloudbed"], "case_ids": sorted(m["case_id"] for m in ms),
               "start_unix": min(m["start_unix"] for m in ms), "end_unix": max(m["end_unix"] for m in ms)}
              for ms in members.values()]
    groups.sort(key=lambda g: (g["cloudbed"], g["start_unix"], g["case_ids"][0]))
    return [{"group_id": f"W{i:02d}", **g} for i, g in enumerate(groups, start=1)]


# ---------------------------------------------------------------- addendum al freeze
def l2_sources_sha256() -> dict[str, str]:
    base = Path(__file__).parent
    return {name: proto._file_sha256(base / name) for name in L2_SOURCES}


def loaders_sha256() -> dict[str, str]:
    base = Path(__file__).parent.parent
    return {name: proto._file_sha256(base / name) for name in LOADER_FILES}


def _git_changed_files(repo_dir: Path, base_commit: str) -> list[str]:
    out = subprocess.run(["git", "-C", str(repo_dir), "diff", "--name-only", base_commit, "HEAD"],
                         check=True, capture_output=True, text=True).stdout
    return sorted(line for line in out.splitlines() if line.strip())


def _is_allowed_after_freeze(path: str) -> bool:
    return path in ALLOWED_AFTER_FREEZE_FILES or path.startswith(ALLOWED_AFTER_FREEZE_PREFIXES)


def verify_frozen_inputs(freeze: dict, *, table: dict, integrity: dict, catalog_sha256: str,
                         repo_dir: Path) -> list[str]:
    """Il freeze originale deve valere ancora: tabella, parametri, record, catalogo, sorgenti.

    Il commit del codice puo' essere piu' recente, ma solo per nuovi moduli L2, test e documenti.
    """
    problems = proto.verify_freeze(freeze, table=table, integrity=integrity,
                                   catalog_sha256=catalog_sha256, code_commit=freeze["code_commit"])
    bad = [p for p in _git_changed_files(repo_dir, freeze["code_commit"]) if not _is_allowed_after_freeze(p)]
    if bad:
        problems.append("file_cambiati_dopo_il_freeze: " + ", ".join(bad))
    return problems


def build_addendum(*, freeze: dict, freeze_file_sha256: str, release: dict, release_sha256: str,
                   manifest_sha256: str, l1_report: dict, l1_report_sha256: str, cases: list[dict],
                   l2_sources: dict, loaders: dict, l2_code_commit: str,
                   created_utc: str | None = None) -> dict:
    if not proto.freeze_is_intact(freeze):
        raise L2ScopeError("Freeze manomesso: nessun addendum")
    if len(str(l2_code_commit)) != 40:
        raise L2ScopeError("Serve il commit completo del codice L2")
    sealed = sorted(release["test_case_ids"])
    if sorted(c["case_id"] for c in cases) != sealed or set(sealed) & set(cat.DISCOVERY_CASES):
        raise L2ScopeError("I casi letti dal manifest non coincidono con i sigillati del release")
    groups = build_window_groups(cases)
    if len(groups) != release["test_window_groups"]:
        raise L2ScopeError(f"Gruppi costruiti {len(groups)} != gruppi del release "
                           f"{release['test_window_groups']}")
    if l1_report.get("freeze_sha256") != freeze["sha256_of_body_without_this_field"]:
        raise L2ScopeError("Il report L1 non e' quello di questo freeze")
    if l1_report.get("uses_ground_truth") or l1_report.get("sealed_incidents_opened"):
        raise L2ScopeError("Il report L1 dichiara uso di GT o apertura dei sigillati")
    by_stage = {c["stage_id"]: c for c in freeze["candidates"]}
    rules = []
    for entry in freeze["l2_eligible"]:
        stage_id, rule_sha, frozen_class = entry[0], entry[1], entry[2]
        cand = by_stage[stage_id]
        if stage_id not in l1_report["admitted_to_l2"] or cand["rule_sha256"] != rule_sha:
            raise L2ScopeError(f"Regola non ammessa dal report L1: {stage_id}")
        if cand["classes"] != [frozen_class]:
            raise L2ScopeError(f"La regola non ha una classe unica e coerente col freeze: {stage_id}")
        rules.append({"stage_id": stage_id, "rule_sha256": rule_sha, "rule_name": cand["rule_name"],
                      "target_fault_type": cand["classes"][0], "caveats": cand["caveats"]})
    if not rules:
        raise L2ScopeError("Nessuna regola ammessa a L2")
    body = {
        "schema": ADDENDUM_SCHEMA, "protocol_version": VERSION,
        "created_utc": created_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "freeze_sha256": freeze["sha256_of_body_without_this_field"],
        "freeze_file_sha256": freeze_file_sha256,
        "freeze_code_commit": freeze["code_commit"], "l2_code_commit": l2_code_commit,
        "l2_sources_sha256": dict(sorted(l2_sources.items())),
        "loaders_sha256": dict(sorted(loaders.items())),
        "window_source": {"file": "data/processed/benchmark_inputs_market.csv (manifest GT-free)",
                          "columns_read": list(WINDOW_COLUMNS), "sha256": manifest_sha256},
        "release_sha256": release_sha256, "manifest_sha256": manifest_sha256,
        "l1_report_sha256": l1_report_sha256, "l1_admitted_to_l2": sorted(l1_report["admitted_to_l2"]),
        "sealed_case_ids": sealed, "sealed_case_ids_sha256": proto._sha(sealed),
        "expected_group_count": release["test_window_groups"],
        "group_definition": GROUP_DEFINITION,
        "groups": groups, "groups_sha256": proto._sha(groups),
        "rules": rules, "rules_sha256": proto._sha(rules),
        "parameters": freeze["parameters"], "parameters_sha256": freeze["parameters_sha256"],
        "population_policy": POPULATION_POLICY, "decisions_format": DECISIONS_FORMAT,
        "handling": HANDLING, "annotations": list(ANNOTATIONS),
        "rules_tested": freeze["rules_tested"],
        "procedure": ("L2a (questo modulo): esecuzione della regola sui gruppi, senza GT, decisioni "
                      "sigillate con hash. L2b (rq2_k_l2_scoring, processo separato): lettura della "
                      "ground truth, riferimenti per gruppo e chiamata a evaluate_rule con i parametri "
                      "del freeze. Nessun parametro, regola o soglia puo' cambiare dopo L2a."),
        "statement": ("Addendum scritto PRIMA di leggere la telemetria e la ground truth dei sigillati, "
                      "dopo la lettura del report L1 reale. Il perimetro e' un caso di studio "
                      "preliminare su una sola regola, senza generalizzazione."),
    }
    return {**body, "sha256_of_body_without_this_field": proto._sha(body)}


def addendum_is_intact(addendum: dict) -> bool:
    body = {k: v for k, v in addendum.items() if k != "sha256_of_body_without_this_field"}
    return addendum.get("sha256_of_body_without_this_field") == proto._sha(body)


def verify_addendum(addendum: dict, **inputs) -> list[str]:
    """Ricostruisce l'addendum dagli stessi ingressi e nomina ogni differenza."""
    if not addendum_is_intact(addendum):
        return ["addendum_manomesso"]
    # Il commit e' informativo (un commit di soli documenti dopo l'addendum non lo invalida):
    # contano gli hash dei moduli L2, dei loader, dei parametri e dei file congelati.
    rebuilt = build_addendum(created_utc=addendum["created_utc"],
                             **{**inputs, "l2_code_commit": addendum["l2_code_commit"]})
    return [f"{key}_diverso" for key in sorted(rebuilt) if rebuilt[key] != addendum.get(key)]


# ---------------------------------------------------------------- esecuzione (L2a)
def _rule_from_row(row: dict) -> dict:
    return {"status": "candidate", "combination": row["combination"],
            "conditions": [{k: c[k] for k in ("metric", "operator", "threshold", "aggregation",
                                              "window_seconds")} | {"unit": c["unit_declared"]}
                           for c in row["conditions"]]}


def run_l2a(*, addendum: dict, freeze: dict, table: dict, catalog: dict, zip_path: Path,
            head_commit: str = "non_registrato") -> dict:
    """Esegue le regole dell'addendum sui gruppi. Nessuna etichetta in ingresso."""
    if not addendum_is_intact(addendum):
        raise L2ScopeError("Addendum manomesso")
    if addendum["freeze_sha256"] != freeze["sha256_of_body_without_this_field"]:
        raise L2ScopeError("L'addendum non appartiene a questo freeze")
    kpi_levels = pf.kpi_level_map(catalog)
    kinds = {level: kind for kind, level in cat.LEVELS.items()}
    rows = {r["stage_id"]: r for r in table["rows"]}
    out_rules, missing_files = [], {}
    for info in addendum["rules"]:
        row = rows[info["stage_id"]]
        if row["rule_sha256"] != info["rule_sha256"] or not row["executable"]:
            raise L2ScopeError(f"La regola non coincide con l'addendum: {info['stage_id']}")
        level = row["conditions"][0]["level"]
        history = row["required_history_seconds"]
        rule = _rule_from_row(row)
        per_group, decisions = {}, {}
        for group in addendum["groups"]:
            gid = group["group_id"]
            lo = group["start_unix"] - history
            frame, missing = pf.read_interval(zip_path, group["cloudbed"], kinds[level], lo,
                                              group["end_unix"])
            if missing:
                missing_files[f"{gid}:{level}"] = missing
            telemetry = {lv: proto._empty_frame() for lv in ex.LEVELS}
            telemetry[level] = frame
            try:
                result = ex.execute_rule(rule, telemetry, start_unix=group["start_unix"],
                                         end_unix=group["end_unix"], history_start_unix=lo,
                                         kpi_levels=kpi_levels)
                summary = proto._summarise(result) | {"population": list(result["population"])}
                decision = summary["decision"]
            except ex.RuleExecutionError as exc:
                summary, decision = {"error": str(exc)[:200]}, "error"
            per_group[gid], decisions[gid] = summary, decision
        out_rules.append({**info, "level": level, "per_group": per_group, "decisions": decisions,
                          "decisions_sha256": proto._sha(decisions)})
    body = {"schema": RESULT_SCHEMA, "protocol_version": VERSION,
            "addendum_sha256": addendum["sha256_of_body_without_this_field"],
            "freeze_sha256": addendum["freeze_sha256"], "l2_code_commit": addendum["l2_code_commit"],
            "run_head_commit": head_commit, "uses_ground_truth": False, "ground_truth_opened": False,
            "groups": addendum["groups"], "rules": out_rules, "history_files_missing": missing_files}
    return {**body, "sha256_of_body_without_this_field": proto._sha(body)}


def l2a_is_intact(report: dict) -> bool:
    return addendum_is_intact(report)           # stessa regola: hash del corpo senza il campo


def render_addendum(addendum: dict) -> str:
    lines = [f"ADDENDUM AL FREEZE ({addendum['schema']}) | freeze {addendum['freeze_sha256'][:16]} | "
             f"codice L2 {addendum['l2_code_commit'][:12]}",
             f"  release             : {addendum['release_sha256']}",
             f"  report L1           : {addendum['l1_report_sha256']}",
             f"  manifest            : {addendum['manifest_sha256']}",
             f"  moduli L2           : " + ", ".join(f"{k[:-3]}={v[:8]}"
                                                       for k, v in addendum["l2_sources_sha256"].items()),
             f"  freeze (file)       : {addendum['freeze_file_sha256']}",
             f"  loader              : {len(addendum['loaders_sha256'])} file con hash",
             f"  sigillati           : {len(addendum['sealed_case_ids'])} casi, "
             f"{len(addendum['groups'])} gruppi (release: {addendum['expected_group_count']}) "
             f"{addendum['groups_sha256'][:16]}"]
    for group in addendum["groups"]:
        lines.append(f"    {group['group_id']} {group['cloudbed']} [{group['start_unix']}, "
                     f"{group['end_unix']}) casi: {len(group['case_ids'])}")
    for rule in addendum["rules"]:
        lines.append(f"  regola: {rule['rule_name']} -> {rule['target_fault_type']}")
        lines += [f"    CAUTELA: {c}" for c in rule["caveats"]]
    lines += [f"  NOTA: {note}" for note in addendum["annotations"]]
    lines.append(f"  corpo: {addendum['sha256_of_body_without_this_field']}")
    return "\n".join(lines)


def render_l2a(report: dict) -> str:
    lines = [f"L2a ({report['protocol_version']}) | addendum {report['addendum_sha256'][:16]} | "
             f"GT usata: {report['uses_ground_truth']}"]
    if report["history_files_missing"]:
        lines.append(f"  FILE STORICI ASSENTI: {report['history_files_missing']}")
    for rule in report["rules"]:
        lines += ["-" * 74, f"{rule['rule_name']}  (decisioni {rule['decisions_sha256'][:16]})"]
        for gid, summary in sorted(rule["per_group"].items()):
            if "error" in summary:
                lines.append(f"    {gid}: ERRORE {summary['error']}")
                continue
            lines.append(f"    {gid}: {summary['decision']:8s} popolazione "
                         f"{summary['components_in_population']}/{summary['components_total']} | "
                         f"valutabili {summary['evaluable_fraction']} | componenti che scattano "
                         f"{summary['firing_component_count']} | sconosciuti {summary['unknown_by_cause']}")
    lines += ["=" * 74, f"corpo: {report['sha256_of_body_without_this_field']}",
              "Le decisioni sono sigillate: la ground truth NON e' stata letta."]
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI
def _load_inputs(args, ctx: dict) -> dict:
    root, repo = ctx["root"], args.repo_dir
    freeze = json.loads((root / proto.FREEZE_RELATIVE).read_text(encoding="utf-8"))
    problems = verify_frozen_inputs(freeze, table=ctx["table"], integrity=ctx["integrity"],
                                    catalog_sha256=ctx["catalog_sha256"], repo_dir=repo)
    release_path = repo / RELEASE_RELATIVE
    report_path = root / proto.REPORT_RELATIVE
    release = json.loads(release_path.read_text(encoding="utf-8"))
    return {"freeze": freeze, "problems": problems, "release": release,
            "inputs": {"freeze": freeze, "release": release,
                       "freeze_file_sha256": proto._file_sha256(root / proto.FREEZE_RELATIVE),
                       "release_sha256": proto._file_sha256(release_path),
                       "manifest_sha256": proto._file_sha256(ctx["manifest"]),
                       "l1_report": json.loads(report_path.read_text(encoding="utf-8")),
                       "l1_report_sha256": proto._file_sha256(report_path),
                       "cases": load_cases(ctx["manifest"], release["test_case_ids"]),
                       "l2_sources": l2_sources_sha256(), "loaders": loaders_sha256(),
                       "l2_code_commit": ctx["code_commit"]}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("addendum", "run"):
        p = sub.add_parser(name)
        p.add_argument("--drive-root", type=Path, required=True)
        p.add_argument("--repo-dir", type=Path, required=True)
        p.add_argument("--no-write", action="store_true")
        if name == "run":
            p.add_argument("--authorize-sealed-telemetry", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "run" and not args.authorize_sealed_telemetry:
        print("Serve --authorize-sealed-telemetry: L2a legge la telemetria dei sigillati "
              "(mai la ground truth).")
        return 2
    ctx = proto._context(args)
    loaded = _load_inputs(args, ctx)
    if loaded["problems"]:
        print("FREEZE NON COINCIDE, L2 non parte:", *loaded["problems"], sep="\n  - ")
        return 2
    addendum_path = ctx["root"] / ADDENDUM_RELATIVE

    if args.command == "addendum":
        addendum = build_addendum(**loaded["inputs"])
        print(render_addendum(addendum))
        if not args.no_write:
            proto._write_new(addendum_path, addendum)
            print(f"\nScritto (create-only): {addendum_path}")
        return 0

    addendum = json.loads(addendum_path.read_text(encoding="utf-8"))
    differences = verify_addendum(addendum, **loaded["inputs"])
    if differences:
        print("ADDENDUM NON COINCIDE, L2a non parte:", *differences, sep="\n  - ")
        return 2
    print("Freeze e addendum verificati.\n")
    report = run_l2a(addendum=addendum, freeze=loaded["freeze"], table=ctx["table"],
                     catalog=ctx["catalog"], zip_path=ctx["zip"], head_commit=ctx["code_commit"])
    print(render_l2a(report))
    if not args.no_write:
        target = ctx["root"] / L2A_RELATIVE
        proto._write_new(target, report)
        print(f"\nScritto (create-only): {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
