"""RQ2-K: preflight L1 delle regole candidate (GT-FREE, solo lettura).

Scopo
-----
Prima di eseguire davvero le regole sui dati, dire per ognuna delle K `candidate`:
  * se l'interprete node/container puo' formalizzarla (livello dei KPI FISSATO dal
    catalogo, mai dedotto dai dati caricati);
  * a quale delle quattro classi RQ2 e' associabile secondo una TABELLA SEMANTICA
    (famiglia di KPI -> classi), oppure se e' NON_CLASSIFICABILE;
  * se la storia temporale che richiede e' disponibile, se le unita' dichiarate sono
    coerenti coi nomi dei KPI, se la soglia e' raggiungibile nell'intervallo dei valori
    osservati e se il KPI sembra un contatore cumulativo.

Cosa NON fa
-----------
  * Non conosce etichette, classi dei casi, componente di riferimento o istante del
    guasto; legge solo i 4 incidenti di scoperta (`rq2_k_catalog.DISCOVERY_CASES`).
  * Non estende l'esecutore per recuperare le regole non formalizzabili: le segnala.
  * Non esegue la regola: non produce nessuna decisione di gruppo.
  * La tabella semantica (v1, approvata da GPT e da Alessio il 16 nov) e' una mappatura di
    COMPATIBILITA' tra famiglia di KPI e classe, NON di causalita': dice che un KPI e' una
    firma osservabile di una classe, non che la regola ne provi la causa. Qui e' solo
    applicata, in modo deterministico.

Esiti L1 (interpretazione di Claude delle tre voci richieste, da confermare)
----------------------------------------------------------------------------
  FORMALIZZABILE                      eseguibile a un solo livello node/container E associata
                                      a UNA sola classe tra le quattro (pronta per L2)
  NON_FORMALIZZABILE_NODE_CONTAINER   cita KPI fuori dal catalogo node/container (servizio,
                                      log, trace, nomi inventati), livelli misti o una
                                      regola che l'esecutore rifiuta
  NON_CLASSIFICABILE                  eseguibile ma senza una classe unica: nessuna firma
                                      diretta di una delle quattro classi, o classi in conflitto
La colonna `executable` dice a parte se l'esecutore la puo' far girare.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from agent.tools import _get_telemetry_csv_paths
from evaluation import rq2_k_catalog as cat
from evaluation import rq2_k_records as rk
from evaluation import rq2_k_rule_executor as ex

VERSION = "rq2_k_l1_preflight_v1"
SEMANTIC_TABLE_VERSION = "rq2_k_semantic_table_v1"

FORMALIZABLE = "FORMALIZZABILE"
NOT_FORMALIZABLE = "NON_FORMALIZZABILE_NODE_CONTAINER"
NOT_CLASSIFIABLE = "NON_CLASSIFICABILE"

# Le quattro classi dell'esperimento (stesse stringhe di rq2_fault_type_eval_policy.CANONICAL;
# un test verifica l'uguaglianza, qui non si importa il modulo di valutazione).
C_NODE_CPU = "node CPU spike"
C_WRITE_IO = "container write I/O load"
C_PROCESS = "container process termination"
C_PACKET_LOSS = "container packet loss"
CLASSES = (C_NODE_CPU, C_WRITE_IO, C_PROCESS, C_PACKET_LOSS)

# Tabella semantica v1 (compatibilita', non causalita'): la prima famiglia che corrisponde per livello e nome vince.
# `classes` = classi per cui il KPI e' una firma DIRETTA; () = nessuna firma diretta.
FAMILIES = (
    {"id": "node_cpu_usage", "level": "node",
     "pattern": r"^system\.cpu\.(pct_usage|user|system|idle)$", "classes": (C_NODE_CPU,),
     "rationale": "uso della CPU del nodo: firma diretta di un picco di CPU. Non distingue dal "
                  "carico di CPU (classe gia' coperta dalle regole fisse, assente dai sigillati)"},
    {"id": "node_cpu_iowait", "level": "node", "pattern": r"^system\.cpu\.iowait$", "classes": (),
     "rationale": "attesa di I/O: effetto indiretto del disco, nessuna firma diretta delle quattro classi"},
    {"id": "node_ping_can_connect", "level": "node", "pattern": r"^ping\.can_connect$", "classes": (),
     "rationale": "raggiungibilita' del nodo (ping): nessuna firma diretta delle quattro classi"},
    {"id": "node_other", "level": "node", "pattern": r"^system\.", "classes": (),
     "rationale": "altri KPI di nodo (memoria, disco, I/O, carico): nessuna firma diretta delle quattro classi"},
    {"id": "container_start_time", "level": "container",
     "pattern": r"^container_start_time_seconds$", "classes": (C_PROCESS,),
     "rationale": "l'istante di avvio del container cambia quando il processo termina e riparte",
     "caveat": "Rileva un RIAVVIO OSSERVABILE del container; non dimostra di per se' la causa "
               "della terminazione del processo."},
    {"id": "container_fs_write", "level": "container",
     "pattern": r"^container_fs_writes(_MB)?(\.|$)", "classes": (C_WRITE_IO,),
     "rationale": "scritture su disco del container: firma diretta del carico di scrittura"},
    {"id": "container_network_loss", "level": "container",
     "pattern": r"^container_network_(receive|transmit)_.*(dropped|errors?)", "classes": (C_PACKET_LOSS,),
     "rationale": "pacchetti scartati o in errore: firma diretta della perdita di pacchetti"},
    {"id": "container_network_other", "level": "container", "pattern": r"^container_network_",
     "classes": (),
     "rationale": "volumi di rete: ambigui (perdita, latenza, ritrasmissione), nessuna firma diretta"},
    {"id": "container_cpu_cfs", "level": "container", "pattern": r"^container_cpu_cfs_", "classes": (),
     "rationale": "throttling CPU del container: classe CPU del container, non tra le quattro"},
    {"id": "container_other", "level": "container", "pattern": r"^container_", "classes": (),
     "rationale": "altri KPI di container: nessuna firma diretta delle quattro classi"},
)

_UNIT_ALIASES = {"pct": "percent", "percent": "percent", "percentage": "percent", "%": "percent",
                 "mb": "MB", "megabyte": "MB", "megabytes": "MB",
                 "s": "seconds", "sec": "seconds", "second": "seconds", "seconds": "seconds"}
SAMPLING_STEP_SECONDS = ex.GRID_SECONDS_DEFAULT


class CatalogLevelError(ValueError):
    """Il catalogo non permette di fissare il livello di un KPI (assente o ambiguo)."""


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def semantic_table_sha256() -> str:
    return _sha([{**f, "classes": list(f["classes"])} for f in FAMILIES])


# ---------------------------------------------------------------- livello e famiglia

def kpi_level_map(catalog: dict) -> dict[str, str]:
    """KPI -> livello, letto UNA volta dal catalogo. Un KPI in due livelli e' un errore."""
    levels: dict[str, str] = {}
    for level, kpis in (catalog.get("aggregate") or {}).items():
        if level not in ex.LEVELS:
            raise CatalogLevelError(f"Livello sconosciuto nel catalogo: {level}")
        for kpi in kpis:
            if kpi in levels and levels[kpi] != level:
                raise CatalogLevelError(f"KPI presente in due livelli: {kpi}")
            levels[kpi] = level
    if not levels:
        raise CatalogLevelError("Catalogo senza KPI")
    return levels


def kpi_family(kpi: str, level: str) -> dict | None:
    for family in FAMILIES:
        if family["level"] == level and re.search(family["pattern"], kpi):
            return family
    return None


def family_coverage(catalog: dict) -> dict:
    """La tabella semantica applicata ai KPI del catalogo (da ispezionare prima del freeze)."""
    by_family: dict[str, list[str]] = {}
    unmatched = []
    for kpi, level in sorted(kpi_level_map(catalog).items()):
        family = kpi_family(kpi, level)
        if family is None:
            unmatched.append(f"{level}:{kpi}")
        else:
            by_family.setdefault(family["id"], []).append(kpi)
    return {"by_family": by_family, "unmatched": unmatched}


def unit_hint(kpi: str) -> str | None:
    if re.search(r"_MB(\.|$)", kpi):
        return "MB"
    if "pct" in kpi.lower():
        return "percent"
    if "seconds" in kpi.lower():
        return "seconds"
    return None


def unit_check(kpi: str, declared: object) -> str:
    hint = unit_hint(kpi)
    if hint is None:
        return "non_verificabile_dal_nome"
    normalized = _UNIT_ALIASES.get(str(declared).strip().lower(), str(declared).strip())
    return "coerente" if normalized == hint else f"incoerente(dichiarata={declared}, nome_suggerisce={hint})"


# ---------------------------------------------------------------- classificazione L1

def _components_per_case(catalog: dict, kpi: str, level: str) -> dict:
    out = {}
    for case_id, info in catalog["per_case"].items():
        stats = info["levels"].get(level, {}).get(kpi)
        out[case_id] = {"with_kpi": stats["components"] if stats else 0,
                        "components_total": info["components_total"][level]}
    return out


def classify_candidate(entry: dict, catalog: dict, kpi_levels: dict[str, str]) -> dict:
    rule = entry["rule"]
    row = {"stage_id": entry["stage_id"], "case_id": entry["case_id"], "model": entry["model"],
           "harness": entry["harness"], "rule_name": rule.get("rule_name"),
           "hypothesized_fault_type": rule.get("hypothesized_fault_type"),
           "rule_sha256": _sha(rule), "combination": rule.get("combination"),
           "executable": False, "classes": [], "required_history_seconds": None,
           "conditions": [], "caveats": [], "reason": None, "l1_outcome": NOT_FORMALIZABLE}
    try:
        conditions = ex._check_rule(rule)
    except ex.RuleExecutionError as exc:
        return {**row, "reason": f"regola_rifiutata_dall_esecutore: {str(exc)[:160]}"}

    row["required_history_seconds"] = max(c["window_seconds"] for c in conditions)
    levels = set()
    for cond in conditions:
        metric = cond["metric"]
        level = kpi_levels.get(metric)
        family = kpi_family(metric, level) if level else None
        levels.add(level)
        row["conditions"].append({
            "metric": metric, "aggregation": cond["aggregation"], "operator": cond["operator"],
            "threshold": cond["threshold"], "unit_declared": cond.get("unit"),
            "window_seconds": cond["window_seconds"], "level": level,
            "in_catalog": level is not None,
            "family": family["id"] if family else None,
            "family_classes": list(family["classes"]) if family else [],
            "unit_check": unit_check(metric, cond.get("unit")) if level else None,
            "components_per_case": _components_per_case(catalog, metric, level) if level else {}})

    row["caveats"] = sorted({kpi_family(c["metric"], c["level"]).get("caveat")
                             for c in row["conditions"]
                             if c["level"] and kpi_family(c["metric"], c["level"])
                             and kpi_family(c["metric"], c["level"]).get("caveat")})
    outside = sorted({c["metric"] for c in row["conditions"] if not c["in_catalog"]})
    if outside:
        return {**row, "reason": "kpi_fuori_dal_catalogo_node_container: " + ", ".join(outside)}
    if len(levels) != 1:
        return {**row, "reason": "livelli_misti: " + ", ".join(sorted(levels))}

    row["executable"] = True
    class_sets = [set(c["family_classes"]) for c in row["conditions"]]
    no_signature = sorted({c["metric"] for c in row["conditions"] if not c["family_classes"]})
    common = set.intersection(*class_sets)
    row["classes"] = sorted(common)
    if no_signature:
        return {**row, "l1_outcome": NOT_CLASSIFIABLE,
                "reason": "nessuna_firma_diretta_delle_quattro_classi: " + ", ".join(no_signature)}
    if len(common) != 1:
        return {**row, "l1_outcome": NOT_CLASSIFIABLE,
                "reason": "classi_in_conflitto_tra_le_condizioni: " + "; ".join(
                    f"{c['metric']}->{c['family_classes']}" for c in row["conditions"])}
    return {**row, "l1_outcome": FORMALIZABLE, "reason": f"classe: {next(iter(common))}"}


def build_table(entries: list[dict], catalog: dict) -> dict:
    kpi_levels = kpi_level_map(catalog)
    rows = [classify_candidate(e, catalog, kpi_levels) for e in entries if e["outcome"] == "candidate"]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["l1_outcome"]] = counts.get(row["l1_outcome"], 0) + 1
    executable = sorted((r["stage_id"], r["rule_sha256"]) for r in rows if r["executable"])
    ready = sorted((r["stage_id"], r["rule_sha256"]) for r in rows if r["l1_outcome"] == FORMALIZABLE)
    return {"version": VERSION, "semantic_table_version": SEMANTIC_TABLE_VERSION,
            "semantic_table_sha256": semantic_table_sha256(),
            "candidates": len(rows), "outcome_counts": dict(sorted(counts.items())),
            "executable_sha256": _sha(executable), "l2_ready_sha256": _sha(ready),
            "rows": rows, "family_coverage": family_coverage(catalog)}


def render_table(table: dict) -> str:
    lines = [f"Preflight L1 ({table['version']}) | tabella semantica {table['semantic_table_version']}",
             f"  sha256 tabella semantica : {table['semantic_table_sha256']}",
             f"  candidate                : {table['candidates']}   esiti: {table['outcome_counts']}",
             f"  sha256 elenco eseguibili : {table['executable_sha256']}",
             f"  sha256 elenco pronte L2  : {table['l2_ready_sha256']}", ""]
    for row in table["rows"]:
        lines += ["-" * 70,
                  f"{row['case_id']} | {row['model']} | {row['harness']} | {row['rule_name']}",
                  f"  esito L1     : {row['l1_outcome']}  (eseguibile: {row['executable']})",
                  f"  motivo       : {row['reason']}",
                  f"  ipotesi LLM  : {row['hypothesized_fault_type']}   (solo provenienza)",
                  f"  combinazione : {row['combination']}   storia richiesta: "
                  f"{row['required_history_seconds']} s   sha256 regola: {row['rule_sha256'][:12]}"]
        lines += [f"  CAUTELA      : {c}" for c in row["caveats"]]
        for c in row["conditions"]:
            cases = ", ".join(f"{k.split('_')[-1]}:{v['with_kpi']}/{v['components_total']}"
                              for k, v in sorted(c["components_per_case"].items())) or "-"
            lines.append(f"    {c['metric']} {c['aggregation']}({c['window_seconds']}s) {c['operator']} "
                         f"{c['threshold']} [{c['unit_declared']}] | livello={c['level']} "
                         f"famiglia={c['family']} unita={c['unit_check']} | componenti col KPI: {cases}")
    cov = table["family_coverage"]
    lines += ["", "Tabella semantica applicata al catalogo (KPI per famiglia):"]
    by_id = {f["id"]: f for f in FAMILIES}
    for fid, kpis in sorted(cov["by_family"].items()):
        lines.append(f"  {fid} -> {list(by_id[fid]['classes']) or 'nessuna classe'}  ({len(kpis)} KPI)")
        lines.append("      " + ", ".join(kpis[:12]) + (" ..." if len(kpis) > 12 else ""))
    if cov["unmatched"]:
        lines.append(f"  KPI senza famiglia: {cov['unmatched']}")
    return "\n".join(lines)


# ---------------------------------------------------------------- storia e valori (telemetria)

def read_interval(zip_path: Path, cloudbed: str, kind: str, lo_unix: int, hi_unix: int,
                  kpis: set[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Righe con lo <= timestamp < hi di un livello, anche su piu' giorni.

    Restituisce (tabella, file previsti ma assenti nello zip). Un file assente non
    solleva: e' proprio cio' che il controllo della storia deve far vedere.
    """
    paths = _get_telemetry_csv_paths(start_unix=lo_unix, end_unix=hi_unix,
                                     market_system=cloudbed, data_kind=kind)
    blocks, missing = [], []
    with zipfile.ZipFile(zip_path, "r") as archive:
        names = set(archive.namelist())
        for path in paths:
            if path not in names:
                missing.append(path)
                continue
            with archive.open(path) as handle:
                for chunk in pd.read_csv(handle, usecols=cat.COLUMNS, chunksize=cat.CHUNK_ROWS):
                    stamps = pd.to_numeric(chunk["timestamp"], errors="coerce")
                    mask = stamps.ge(lo_unix) & stamps.lt(hi_unix)
                    if kpis is not None:
                        mask &= chunk["kpi_name"].isin(kpis)
                    if mask.any():
                        blocks.append(chunk.loc[mask, cat.COLUMNS].copy())
    frame = pd.concat(blocks, ignore_index=True) if blocks else pd.DataFrame(columns=cat.COLUMNS)
    return frame, missing


def profile_kpi(frame: pd.DataFrame, kpi: str, *, start_unix: int, window_seconds: int) -> dict:
    """Storia e valori di un KPI in `frame` (gia' limitato a [start - storia, end))."""
    sub = frame.loc[frame["kpi_name"] == kpi, ["timestamp", "cmdb_id", "value"]]
    sub = sub.assign(timestamp=pd.to_numeric(sub["timestamp"], errors="coerce"),
                     value=pd.to_numeric(sub["value"], errors="coerce")).dropna()
    sub = sub[np.isfinite(sub["value"].to_numpy(dtype=float))]
    history_lo = start_unix - window_seconds
    base = {"window_seconds": window_seconds, "history_from_unix": history_lo}
    if sub.empty:
        return {**base, "components_with_kpi": 0, "components_with_sample_in_first_window": 0,
                "components_with_full_history": 0, "value_min": None, "value_p50": None,
                "value_p95": None, "value_max": None, "rising_series_fraction": None,
                "cumulative_counter_hint": False}
    in_first, full, monotone, monotone_total = 0, 0, 0, 0
    for _, group in sub.groupby("cmdb_id", sort=True):
        ordered = group.sort_values("timestamp")
        stamps = ordered["timestamp"].to_numpy(dtype="int64")
        in_first += int(((stamps > history_lo) & (stamps <= start_unix)).any())
        full += int(stamps[0] <= history_lo + SAMPLING_STEP_SECONDS)
        if len(stamps) >= 3:
            # Contatore cumulativo = serie che non scende mai E finisce piu' in alto di dove
            # inizia. Una serie costante (es. istante di avvio) NON e' un contatore.
            series_values = ordered["value"].to_numpy(dtype=float)
            monotone_total += 1
            monotone += int(bool(np.all(np.diff(series_values) >= 0) and series_values[-1] > series_values[0]))
    values = sub["value"].to_numpy(dtype=float)
    fraction = (monotone / monotone_total) if monotone_total else None
    return {**base, "components_with_kpi": int(sub["cmdb_id"].nunique()),
            "components_with_sample_in_first_window": in_first,
            "components_with_full_history": full,
            "value_min": float(values.min()), "value_p50": float(np.percentile(values, 50)),
            "value_p95": float(np.percentile(values, 95)), "value_max": float(values.max()),
            "rising_series_fraction": fraction,
            "cumulative_counter_hint": bool(fraction is not None and fraction >= 0.95)}


def threshold_check(condition: dict, profile: dict) -> str:
    """La soglia e' raggiungibile dai valori osservati? (aggregazioni limitate dal campione)"""
    if profile.get("value_max") is None:
        return "nessun_dato"
    if condition["aggregation"] not in {"mean", "max", "min", "p95", "last"}:
        return "non_confrontabile_con_l_intervallo"
    op, thr = condition["operator"], condition["threshold"]
    lo, hi = profile["value_min"], profile["value_max"]
    if op == ">" and thr >= hi or op == ">=" and thr > hi:
        return "soglia_sopra_il_massimo_osservato"
    if op == "<" and thr <= lo or op == "<=" and thr < lo:
        return "soglia_sotto_il_minimo_osservato"
    if op == "==":
        return "non_confrontabile_con_l_intervallo"
    return "raggiungibile"


def history_report(zip_path: Path, manifest_path: Path, rows: list[dict],
                   cases: tuple[str, ...] = cat.DISCOVERY_CASES) -> dict:
    """Per ogni regola eseguibile e per ogni caso di scoperta: storia e valori dei suoi KPI."""
    runnable = [r for r in rows if r["executable"]]
    need: dict[str, dict[str, int]] = {"node": {}, "container": {}}
    for row in runnable:
        for c in row["conditions"]:
            slot = need[c["level"]]
            slot[c["metric"]] = max(slot.get(c["metric"], 0), c["window_seconds"])
    kinds = {level: kind for kind, level in cat.LEVELS.items()}
    profiles: dict[str, dict] = {}
    files_missing: list[str] = []
    for case_id in cases:
        case = cat.load_case(manifest_path, case_id)
        for level, kpis in need.items():
            if not kpis:
                continue
            lo = case["start_unix"] - max(kpis.values())
            frame, missing = read_interval(zip_path, case["cloudbed"], kinds[level], lo,
                                           case["end_unix"], set(kpis))
            files_missing += [f"{case_id}:{m}" for m in missing]
            for kpi, window in kpis.items():
                profiles.setdefault(kpi, {})[case_id] = {
                    "level": level, **profile_kpi(frame, kpi, start_unix=case["start_unix"],
                                                  window_seconds=window)}
    checks = []
    for row in runnable:
        per_condition = []
        for c in row["conditions"]:
            cases_info = {}
            for case_id, prof in profiles.get(c["metric"], {}).items():
                cases_info[case_id] = {
                    "components_with_kpi": prof["components_with_kpi"],
                    "with_sample_in_first_window": prof["components_with_sample_in_first_window"],
                    "with_full_history": prof["components_with_full_history"],
                    "threshold": threshold_check(c, prof),
                    "cumulative_counter_hint": prof["cumulative_counter_hint"]
                    and c["aggregation"] != "delta"}
            per_condition.append({"metric": c["metric"], "aggregation": c["aggregation"],
                                  "window_seconds": c["window_seconds"], "cases": cases_info})
        checks.append({"stage_id": row["stage_id"], "rule_name": row["rule_name"],
                       "conditions": per_condition})
    return {"profiles": profiles, "files_missing": sorted(set(files_missing)), "checks": checks}


def render_history(report: dict) -> str:
    lines = ["Storia temporale e valori (solo 4 incidenti di scoperta, nessuna etichetta)"]
    if report["files_missing"]:
        lines.append(f"  FILE PREVISTI MA ASSENTI NELLO ZIP: {report['files_missing']}")
    for check in report["checks"]:
        lines += ["-" * 70, f"{check['stage_id']} | {check['rule_name']}"]
        for c in check["conditions"]:
            lines.append(f"  {c['metric']} {c['aggregation']}({c['window_seconds']}s)")
            for case_id, info in sorted(c["cases"].items()):
                flag = "  CONTATORE CUMULATIVO senza delta" if info["cumulative_counter_hint"] else ""
                lines.append(
                    f"    {case_id}: componenti col KPI={info['components_with_kpi']} "
                    f"| campione nella prima finestra={info['with_sample_in_first_window']} "
                    f"| storia completa={info['with_full_history']} | soglia: {info['threshold']}{flag}")
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI

def _write_new(path: Path, payload: dict) -> None:
    with open(path, "x", encoding="utf-8") as handle:       # create-only
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("records_dir", type=Path)
    parser.add_argument("catalog_json", type=Path)
    parser.add_argument("--drive-root", type=Path, default=None,
                        help="se presente, legge anche la telemetria dei 4 casi di scoperta")
    parser.add_argument("--out", type=Path, default=None, help="JSON create-only con tabella e storia")
    args = parser.parse_args(argv)
    catalog = json.loads(args.catalog_json.read_text(encoding="utf-8"))
    table = build_table(rk.load_k_entries(args.records_dir), catalog)
    print(render_table(table))
    output = {"table": table}
    if args.drive_root is not None:
        history = history_report(args.drive_root / "Market.zip",
                                 args.drive_root / cat.MANIFEST_RELATIVE, table["rows"])
        print("\n" + render_history(history))
        output["history"] = history
    if args.out is not None:
        _write_new(args.out, output)
        print(f"\nScritto (create-only): {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
