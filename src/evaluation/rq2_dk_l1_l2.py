"""RQ2 - ablazione D->K: L1 e L2 applicati alle candidate di K senza causa (esplorativo, post hoc).

Domanda (Alessio, 18 novembre, dopo aver visto i risultati dei 60 K senza causa): le candidate
di D->K producono qualcosa di concreto, valutate con gli STESSI L1 e L2 del run congelato D->C->K?

Che cosa riusa (nessun file protetto da hash e' modificato)
----------------------------------------------------------
  * la classificazione e le regole di ammissione di L1 (`rq2_k_l1_preflight`, `rq2_k_l1_protocol`);
  * l'esecutore delle regole, L2a (`rq2_k_l2_execute`) e L2b (`rq2_k_l2_scoring`);
  * i parametri, la tabella semantica, il catalogo, i gruppi temporali e le soglie del freeze del
    16 novembre: letti dai file del run congelato, mai riscritti.
Prima di ogni comando si verifica che i moduli congelati abbiano ESATTAMENTE gli hash registrati
nel freeze e nell'addendum; se differiscono, nulla parte.

Che cosa fa di nuovo
--------------------
  l1    GT-free. Legge i 60 K senza causa (hash verificato), classifica le candidate, esegue le
        eseguibili sui 4 incidenti di discovery e scrive un report create-only.
  l2a   (`--authorize-sealed-telemetry`) scrive l'addendum derivato e le decisioni sulle regole
        ammesse da L1. Legge la telemetria dei sigillati, mai la ground truth.
  l2b   (`--authorize-ground-truth`, processo separato) verifica la catena di hash, legge la
        ground truth e produce il verdetto con i parametri congelati.
  compare  affianca D->C->K (congelato) e D->K per L1 e, se c'e', L2. Sola lettura.

Limite dichiarato: gli 11 incidenti sigillati sono gia' stati aperti nel run congelato, quindi L2
qui NON e' cieco. Le candidate nuove, pero', sono state scritte da un modello che ha visto solo la
traiettoria di discovery. Esito esplorativo, nessuna correzione per confronti multipli.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from evaluation import rq2_dk_ablation as dk
from evaluation import rq2_k_catalog as cat
from evaluation import rq2_k_l1_preflight as pf
from evaluation import rq2_k_l1_protocol as proto
from evaluation import rq2_k_l2_execute as l2x
from evaluation import rq2_k_records as rk
from evaluation import rq2_k_rule_inventory as inv
from evaluation import rq2_k_run_integrity as integ
from evaluation import rq2_v5_matrix_runner as mr

# NOTA: `rq2_k_l2_scoring` (il lato ground truth) NON si importa qui in alto: lo importa solo il
# comando `l2b`, come nel protocollo congelato in cui L2a e L2b sono processi separati.

VERSION = "rq2_dk_l1_l2_v1"
PROTOCOL = "rq2_dk_l1_l2_exploratory_v1"
OUT_RELATIVE = "data/rq2_dk_l1_l2_v1"
L1_FILE = "l1_report_dk.json"
ADDENDUM_FILE = "l2_addendum_dk.json"
L2A_FILE = "l2a_decisions_dk.json"
L2B_FILE = "l2b_evaluation_dk.json"
FROZEN_L2B_RELATIVE = "data/rq2_k_l2_v1/l2b_evaluation.json"      # uguale a rq2_k_l2_scoring.L2B_RELATIVE
L1_SCHEMA = "rq2_dk_l1_report_v1"
DERIVED_FREEZE_SCHEMA = "rq2_dk_derived_freeze_v1"
ADDENDUM_SCHEMA = "rq2_dk_l2_addendum_v1"
L2B_SCHEMA = "rq2_dk_l2b_evaluation_v1"

NOT_BLIND = ("Gli 11 incidenti sigillati erano gia' stati aperti nel run congelato (L2a/L2b del 16 "
             "novembre): questa valutazione NON e' cieca. Cio' che resta cieco e' la produzione delle "
             "candidate: il modello di K ha visto solo la traiettoria dei 4 incidenti di discovery. "
             "Parametri, soglie, tabella semantica e gruppi sono quelli del freeze, invariati.")


class DKScopeError(ValueError):
    """Ingresso fuori perimetro o catena di hash incoerente."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- lettura dei K senza causa

def load_dk_entries(store_root: Path, rows: list[dict]) -> tuple[list[dict], dict]:
    """Legge i K senza causa (sola lettura, hash di ogni file verificato) e ne controlla l'integrita'.

    Argomenti: cartella dell'archivio `data/rq2_dk_ablation_v1` e righe K del piano.
    Restituisce (voci per `rq2_k_records.read_k_record`, rapporto di integrita'). Il rapporto ha
    `ok`, l'elenco dei problemi, gli stati e l'impronta dell'insieme dei record.
    """
    source = dk.SourceDRecords(store_root)             # errore se la cartella non esiste; non scrive
    problems: list[str] = []
    entries: list[dict] = []
    hashes: list[str] = []
    statuses: Counter = Counter()
    for row in rows:
        stage_id = row["stage_id"]
        try:
            record = source.load(stage_id)
        except mr.StoreError as exc:
            problems.append(f"{stage_id}: {type(exc).__name__}")
            continue
        if record is None:
            problems.append(f"{stage_id}: record_assente")
            continue
        if record.get("stage_id") != stage_id:
            problems.append(f"{stage_id}: stage_id_diverso")
        for field in integ.IDENTITY_FIELDS:
            if record.get(field) != row[field]:
                problems.append(f"{stage_id}: {field}_diverso")
        provenance = record.get("provenance")
        if provenance is not None:
            if (provenance.get("variant") != "K_NO_CAUSE"
                    or provenance.get("system_prompt_sha256") != dk.K_NO_CAUSE_SYSTEM_SHA256):
                problems.append(f"{stage_id}: non_e_un_K_senza_causa")
            claim = Path(store_root) / "claims" / f"V5_CLAIM_{mr._key(stage_id)}.json"
            if not claim.exists():
                problems.append(f"{stage_id}: claim_assente")
        statuses[record.get("status")] += 1
        hashes.append(record["record_sha256"])
        entries.append(rk.read_k_record(record))
    entries.sort(key=lambda e: (e["model"], e["harness"], e["case_id"]))
    return entries, {"ok": not problems, "problems": problems, "stages_in_plan": len(rows),
                     "records_found": len(hashes), "statuses": dict(sorted(statuses.items())),
                     "records_fingerprint_sha256": proto._sha(sorted(hashes))}


def k_outcome_counts(entries: list[dict]) -> dict:
    """Quante K per esito (candidate, astensione, non completo, altro)."""
    return dict(sorted(Counter(e["outcome"] for e in entries).items()))


# ---------------------------------------------------------------- codice e parametri congelati

def frozen_code_problems(freeze: dict, addendum: dict | None = None) -> list[str]:
    """Differenze tra il codice/parametri attuali e quelli registrati nel freeze (e nell'addendum).

    Lista vuota = i moduli L1/L2, la tabella semantica e i parametri sono quelli congelati il 16
    novembre. Nomina ogni file diverso.
    """
    problems = []
    if not proto.freeze_is_intact(freeze):
        problems.append("freeze_manomesso")
    current = proto.sources_sha256()
    different = sorted(k for k, v in current.items() if (freeze.get("sources_sha256") or {}).get(k) != v)
    if different:
        problems.append("sorgenti_L1_diversi_dal_freeze: " + ", ".join(different))
    if freeze.get("parameters_sha256") != proto.parameters_sha256() or freeze.get("parameters") != proto.PARAMETERS:
        problems.append("parametri_diversi_dal_freeze")
    if freeze.get("semantic_table_sha256") != pf.semantic_table_sha256():
        problems.append("tabella_semantica_diversa_dal_freeze")
    if addendum is not None:
        if not l2x.addendum_is_intact(addendum):
            problems.append("addendum_manomesso")
        if addendum.get("freeze_sha256") != freeze.get("sha256_of_body_without_this_field"):
            problems.append("addendum_di_un_altro_freeze")
        if addendum.get("l2_sources_sha256") != l2x.l2_sources_sha256():
            problems.append("moduli_L2_diversi_dall_addendum")
        if addendum.get("loaders_sha256") != l2x.loaders_sha256():
            problems.append("loader_diversi_dall_addendum")
        if addendum.get("parameters_sha256") != freeze.get("parameters_sha256"):
            problems.append("parametri_dell_addendum_diversi_dal_freeze")
    return problems


# ---------------------------------------------------------------- freeze derivato e report L1

def build_derived_freeze(*, frozen_freeze: dict, table: dict, eligibility: dict, integrity: dict,
                         catalog_sha256: str, code_commit: str, created_utc: str | None = None) -> dict:
    """Freeze DERIVATO per le candidate D->K: stessi parametri e codice, elenchi nuovi.

    Non sostituisce il freeze del 16 novembre; serve a `proto.run_l1` e a L2, che leggono
    `l2_eligible`, `code_commit` e l'hash del corpo.
    """
    if not integrity.get("ok"):
        raise DKScopeError("Integrita' dei K senza causa non verificata")
    if not code_commit:
        raise DKScopeError("Commit del codice sconosciuto")
    candidates = []
    for row in table["rows"]:
        candidates.append({
            "stage_id": row["stage_id"], "case_id": row["case_id"], "model": row["model"],
            "harness": row["harness"], "rule_name": row["rule_name"], "rule_sha256": row["rule_sha256"],
            "l1_outcome": row["l1_outcome"], "executable": row["executable"], "classes": row["classes"],
            "reason": row["reason"], "caveats": row["caveats"],
            "required_history_seconds": row["required_history_seconds"],
            "eligibility": eligibility.get(row["stage_id"])})
    executable = sorted((c["stage_id"], c["rule_sha256"]) for c in candidates if c["executable"])
    eligible = sorted((c["stage_id"], c["rule_sha256"], c["classes"][0]) for c in candidates
                      if (c["eligibility"] or {}).get("eligible_for_l2"))
    body = {
        "schema": DERIVED_FREEZE_SCHEMA, "protocol": PROTOCOL, "version": VERSION,
        "created_utc": created_utc or _now(), "code_commit": code_commit,
        "derived_from_freeze_sha256": frozen_freeze["sha256_of_body_without_this_field"],
        "frozen_code_commit": frozen_freeze["code_commit"],
        "sources_sha256": frozen_freeze["sources_sha256"],
        "semantic_table_sha256": table["semantic_table_sha256"],
        "parameters": frozen_freeze["parameters"], "parameters_sha256": frozen_freeze["parameters_sha256"],
        "catalog_sha256": catalog_sha256,
        "run": {"namespace": dk.NAMESPACE.as_posix(), "stages": integrity["stages_in_plan"],
                "records_fingerprint_sha256": integrity["records_fingerprint_sha256"]},
        "rules_tested": len(candidates),
        "rules_tested_both_pipelines": len(candidates) + frozen_freeze["rules_tested"],
        "candidates": candidates,
        "executable": [list(x) for x in executable], "executable_sha256": proto._sha(executable),
        "l2_eligible": [list(x) for x in eligible], "l2_eligible_sha256": proto._sha(eligible),
        "statement": ("Freeze DERIVATO per l'ablazione D->K, costruito DOPO aver visto il numero di "
                      "candidate dei 60 K senza causa e DOPO l'apertura dei sigillati nel run congelato. "
                      "Codice, tabella semantica, parametri e criteri sono quelli del freeze del 16 "
                      "novembre, verificati per hash."),
    }
    return {**body, "sha256_of_body_without_this_field": proto._sha(body)}


def describe_candidates(entries: list[dict], table: dict, derived: dict, l1: dict) -> list[dict]:
    """Una riga per candidata: cella, regola, KPI citati, esito L1, ammissione."""
    rows = {r["stage_id"]: r for r in table["rows"]}
    cands = {c["stage_id"]: c for c in derived["candidates"]}
    l1_rules = {r["stage_id"]: r for r in l1["rules"]}
    admitted = set(l1["admitted_to_l2"])
    out = []
    for entry in entries:
        if entry["outcome"] != "candidate":
            continue
        sid = entry["stage_id"]
        row, cand, l1_rule = rows[sid], cands[sid], l1_rules.get(sid)
        out.append({
            "stage_id": sid, "case_id": entry["case_id"], "model": entry["model"],
            "harness": entry["harness"], "rule_name": row["rule_name"],
            "rule_sha256": row["rule_sha256"],
            "hypothesized_fault_type": row["hypothesized_fault_type"],
            "metrics": inv.rule_metrics(entry["rule"]), "l1_outcome": row["l1_outcome"],
            "executable": row["executable"], "classes": row["classes"], "reason": row["reason"],
            "eligible_for_l2": bool((cand["eligibility"] or {}).get("eligible_for_l2")),
            "eligibility_notes": (cand["eligibility"] or {}).get("notes", []),
            "l1_pass": None if l1_rule is None else l1_rule["l1_pass"],
            "l1_failures": [] if l1_rule is None else l1_rule["l1_failures"],
            "admitted_to_l2": sid in admitted})
    return out


def run_dk_l1(*, entries: list[dict], integrity: dict, frozen_freeze: dict, catalog: dict,
              catalog_sha256: str, zip_path: Path, manifest_path: Path, code_commit: str,
              created_utc: str | None = None) -> dict:
    """L1 sulle candidate D->K con codice e parametri congelati. Nessuna etichetta in ingresso."""
    table = pf.build_table(entries, catalog)
    history = pf.history_report(zip_path, manifest_path, table["rows"])
    eligibility = proto.eligibility_for(table["rows"], history)
    derived = build_derived_freeze(frozen_freeze=frozen_freeze, table=table, eligibility=eligibility,
                                   integrity=integrity, catalog_sha256=catalog_sha256,
                                   code_commit=code_commit, created_utc=created_utc)
    l1 = proto.run_l1(freeze=derived, table=table, catalog=catalog, zip_path=zip_path,
                      manifest_path=manifest_path)
    body = {
        "schema": L1_SCHEMA, "protocol": PROTOCOL, "version": VERSION,
        "created_utc": created_utc or _now(), "code_commit": code_commit,
        "uses_ground_truth": False, "sealed_incidents_opened": False,
        "k_outcomes": k_outcome_counts(entries),
        "table_summary": {"candidates": table["candidates"], "outcome_counts": table["outcome_counts"],
                          "executable_sha256": table["executable_sha256"]},
        "derived_freeze": derived,
        "candidates": describe_candidates(entries, table, derived, l1),
        "l1_report": l1,
    }
    return {**body, "sha256_of_body_without_this_field": proto._sha(body)}


def report_is_intact(report: dict) -> bool:
    body = {k: v for k, v in report.items() if k != "sha256_of_body_without_this_field"}
    return report.get("sha256_of_body_without_this_field") == proto._sha(body)


# ---------------------------------------------------------------- confronto L1 / L2 col run congelato

def side_counts(candidates: list[dict]) -> dict:
    """Conteggi L1 di un insieme di candidate (campi: l1_outcome, executable, eligible_for_l2, admitted)."""
    outcomes = Counter(c["l1_outcome"] for c in candidates)
    return {"candidates": len(candidates),
            "non_formalizzabili": outcomes.get(pf.NOT_FORMALIZABLE, 0),
            "eseguibili": sum(1 for c in candidates if c["executable"]),
            "non_classificabili": outcomes.get(pf.NOT_CLASSIFIABLE, 0),
            "formalizzabili": outcomes.get(pf.FORMALIZABLE, 0),
            "ammissibili_a_L2": sum(1 for c in candidates if c["eligible_for_l2"]),
            "ammesse_a_L2": sum(1 for c in candidates if c["admitted"])}


def frozen_side(frozen_freeze: dict, frozen_l1: dict) -> list[dict]:
    """Le 8 candidate del run congelato nella stessa forma delle D->K."""
    admitted = set(frozen_l1["admitted_to_l2"])
    return [{"stage_id": c["stage_id"], "case_id": c["case_id"], "model": c["model"],
             "harness": c["harness"], "rule_name": c["rule_name"], "rule_sha256": c["rule_sha256"],
             "l1_outcome": c["l1_outcome"], "executable": c["executable"],
             "eligible_for_l2": bool((c["eligibility"] or {}).get("eligible_for_l2")),
             "admitted": c["stage_id"] in admitted, "reason": c["reason"]}
            for c in frozen_freeze["candidates"]]


def dk_side(dk_report: dict) -> list[dict]:
    return [{**c, "admitted": c["admitted_to_l2"]} for c in dk_report["candidates"]]


def overlap(frozen: list[dict], ablated: list[dict]) -> dict:
    """Le stesse celle e le stesse regole nei due run (descrittivo)."""
    by_stage = {c["stage_id"]: c for c in frozen}
    frozen_hashes = {c["rule_sha256"]: c["stage_id"] for c in frozen}
    cells = []
    for c in ablated:
        twin = by_stage.get(c["stage_id"])
        cells.append({"stage_id": c["stage_id"], "case_id": c["case_id"], "model": c["model"],
                      "harness": c["harness"], "candidata_anche_nel_run_con_C": twin is not None,
                      "stessa_regola_della_stessa_cella": bool(twin and twin["rule_sha256"] == c["rule_sha256"]),
                      "stessa_regola_in_altra_cella": (c["rule_sha256"] in frozen_hashes
                                                       and frozen_hashes[c["rule_sha256"]] != c["stage_id"])})
    return {"cells": cells,
            "celle_candidate_in_entrambi": sum(1 for x in cells if x["candidata_anche_nel_run_con_C"]),
            "regole_identiche": sum(1 for x in cells if x["stessa_regola_della_stessa_cella"]
                                    or x["stessa_regola_in_altra_cella"])}


def l2_results_summary(l2b_report: dict | None) -> list[dict]:
    """Verdetto e conteggi per regola da un report L2b (o lista vuota)."""
    if not l2b_report:
        return []
    out = []
    for res in l2b_report["results"]:
        ev = res["evaluation"]
        out.append({"stage_id": res["stage_id"], "rule_name": res["rule_name"],
                    "rule_sha256": res["rule_sha256"], "target_fault_type": res["target_fault_type"],
                    "verdict": ev["verdict"], "reasons": ev["reasons"], "counts": ev["counts"],
                    "false_positives": ev["false_positives"],
                    "positives_not_observable": ev["positives_not_observable"],
                    "detection": ev["detection"]})
    return out


def build_comparison(*, dk_report: dict, frozen_freeze: dict, frozen_l1: dict,
                     frozen_l2b: dict | None, dk_l2b: dict | None) -> dict:
    """Confronto descrittivo D->C->K (congelato) contro D->K: L1 e, se esiste, L2."""
    frozen, ablated = frozen_side(frozen_freeze, frozen_l1), dk_side(dk_report)
    dk_l2 = l2_results_summary(dk_l2b["l2b"] if dk_l2b else None)
    return {"with_cause": side_counts(frozen), "without_cause": side_counts(ablated),
            "overlap": overlap(frozen, ablated),
            "l2_with_cause": l2_results_summary(frozen_l2b), "l2_without_cause": dk_l2,
            "l2_without_cause_status": ("eseguita" if dk_l2b else
                                        ("non_applicabile_nessuna_ammessa"
                                         if not dk_report["l1_report"]["admitted_to_l2"]
                                         else "non_ancora_eseguita"))}


# ---------------------------------------------------------------- addendum derivato e catena L2

def build_dk_addendum(*, derived: dict, frozen_addendum: dict, l1_report_sha256: str,
                      admitted: list[str], l2_code_commit: str, created_utc: str | None = None) -> dict:
    """Addendum DERIVATO: gruppi e parametri dell'addendum congelato, regole nuove ammesse da L1."""
    if not proto.freeze_is_intact(derived):
        raise DKScopeError("Freeze derivato manomesso")
    by_stage = {c["stage_id"]: c for c in derived["candidates"]}
    rules = []
    for stage_id, rule_sha, frozen_class in derived["l2_eligible"]:
        if stage_id not in admitted:
            continue
        cand = by_stage[stage_id]
        if cand["rule_sha256"] != rule_sha or cand["classes"] != [frozen_class]:
            raise DKScopeError(f"Regola senza classe unica e coerente: {stage_id}")
        rules.append({"stage_id": stage_id, "rule_sha256": rule_sha, "rule_name": cand["rule_name"],
                      "target_fault_type": frozen_class, "caveats": cand["caveats"]})
    if not rules:
        raise DKScopeError("Nessuna regola D->K ammessa a L2")
    if sorted(admitted) != sorted(r["stage_id"] for r in rules):
        raise DKScopeError("Le regole ammesse da L1 non coincidono con quelle eleggibili del freeze derivato")
    body = {
        "schema": ADDENDUM_SCHEMA, "protocol": PROTOCOL, "version": VERSION,
        "created_utc": created_utc or _now(),
        "freeze_sha256": derived["sha256_of_body_without_this_field"],
        "freeze_code_commit": derived["code_commit"], "l2_code_commit": l2_code_commit,
        "derived_from_frozen_addendum_sha256": frozen_addendum["sha256_of_body_without_this_field"],
        "l2_sources_sha256": frozen_addendum["l2_sources_sha256"],
        "loaders_sha256": frozen_addendum["loaders_sha256"],
        "manifest_sha256": frozen_addendum["manifest_sha256"],
        "release_sha256": frozen_addendum["release_sha256"],
        "sealed_case_ids": frozen_addendum["sealed_case_ids"],
        "groups": frozen_addendum["groups"], "groups_sha256": frozen_addendum["groups_sha256"],
        "l1_report_sha256": l1_report_sha256, "l1_admitted_to_l2": sorted(admitted),
        "rules": rules, "rules_sha256": proto._sha(rules),
        "parameters": derived["parameters"], "parameters_sha256": derived["parameters_sha256"],
        "rules_tested": derived["rules_tested"],
        "rules_tested_both_pipelines": derived["rules_tested_both_pipelines"],
        "not_blind": NOT_BLIND,
        "statement": ("Addendum DERIVATO scritto dopo l'apertura dei sigillati nel run congelato; "
                      "stessi gruppi, stessi parametri, stesse soglie. Esplorativo."),
    }
    return {**body, "sha256_of_body_without_this_field": proto._sha(body)}


def verify_dk_chain(*, derived: dict, addendum: dict, l2a: dict, frozen_freeze: dict,
                    frozen_addendum: dict, manifest_sha256: str) -> list[str]:
    """Catena freeze derivato -> addendum derivato -> decisioni L2a, piu' codice congelato."""
    problems = []
    if not proto.freeze_is_intact(derived):
        problems.append("freeze_derivato_manomesso")
    if not l2x.addendum_is_intact(addendum):
        problems.append("addendum_derivato_manomesso")
    if not l2x.l2a_is_intact(l2a):
        problems.append("decisioni_l2a_manomesse")
    if problems:
        return problems
    sha = derived["sha256_of_body_without_this_field"]
    if derived["derived_from_freeze_sha256"] != frozen_freeze["sha256_of_body_without_this_field"]:
        problems.append("freeze_derivato_di_un_altro_freeze")
    if addendum["freeze_sha256"] != sha or l2a["freeze_sha256"] != sha:
        problems.append("freeze_sha_non_coerente")
    if l2a["addendum_sha256"] != addendum["sha256_of_body_without_this_field"]:
        problems.append("addendum_sha_non_coerente_con_l2a")
    if l2a["uses_ground_truth"] or l2a["ground_truth_opened"]:
        problems.append("l2a_dichiara_uso_di_gt")
    if not (l2a["groups"] == addendum["groups"] == frozen_addendum["groups"]):
        problems.append("gruppi_diversi_dall_addendum_congelato")
    if addendum["derived_from_frozen_addendum_sha256"] != frozen_addendum["sha256_of_body_without_this_field"]:
        problems.append("addendum_derivato_di_un_altro_addendum")
    if [r["rule_sha256"] for r in l2a["rules"]] != [r["rule_sha256"] for r in addendum["rules"]]:
        problems.append("regole_diverse_dall_addendum")
    eligible = {(x[0], x[1]) for x in derived["l2_eligible"]}
    if any((r["stage_id"], r["rule_sha256"]) not in eligible for r in addendum["rules"]):
        problems.append("regola_non_eleggibile_nel_freeze_derivato")
    if addendum["manifest_sha256"] != manifest_sha256 or frozen_addendum["manifest_sha256"] != manifest_sha256:
        problems.append("manifest_diverso_dall_addendum")
    problems += frozen_code_problems(frozen_freeze, frozen_addendum)
    return problems


# ---------------------------------------------------------------- resa a video

def render_l1(report: dict) -> str:
    """Testo del report L1 delle candidate D->K."""
    lines = [f"L1 su D->K ({report['version']}) | commit {str(report['code_commit'])[:12]} | "
             f"GT usata: {report['uses_ground_truth']} | sigillati aperti: {report['sealed_incidents_opened']}",
             f"  esiti dei K senza causa: {report['k_outcomes']}"]
    for c in report["candidates"]:
        lines += ["-" * 74, f"{c['case_id']} | {c['model']} | {c['harness']} | {c['rule_name']}",
                  f"  esito L1: {c['l1_outcome']} (eseguibile: {c['executable']}) classi: {c['classes']}",
                  f"  motivo: {c['reason']}",
                  f"  KPI citati: {c['metrics']} | ipotesi del modello (provenienza): {c['hypothesized_fault_type']}",
                  f"  ammissibile a L2: {c['eligible_for_l2']} {c['eligibility_notes']} | L1 passato: "
                  f"{c['l1_pass']} {c['l1_failures']} | AMMESSA A L2: {c['admitted_to_l2']}"]
    lines += ["=" * 74, proto.render_report(report["l1_report"])]
    return "\n".join(lines)


def render_comparison(cmp: dict) -> str:
    """Tabella D->C->K contro D->K (L1 e L2)."""
    a, b = cmp["with_cause"], cmp["without_cause"]
    names = [("candidate (K che propone una regola)", "candidates"),
             ("  non formalizzabili (fuori da nodo/container)", "non_formalizzabili"),
             ("  eseguibili", "eseguibili"),
             ("    non classificabili", "non_classificabili"),
             ("    formalizzabili (una sola classe)", "formalizzabili"),
             ("  ammissibili a L2 (unita', storia, condizioni)", "ammissibili_a_L2"),
             ("  ammesse a L2 (ammissibili e L1 passato)", "ammesse_a_L2")]
    lines = ["CONFRONTO L1:  D->C->K (congelato) | D->K (senza causa)", "-" * 74]
    lines += [f"  {label:52s} {a[key]:>4d} | {b[key]:>4d}" for label, key in names]
    ov = cmp["overlap"]
    lines += ["", f"Celle candidate in entrambi i run: {ov['celle_candidate_in_entrambi']} | "
              f"regole identiche (stesso hash): {ov['regole_identiche']}"]
    for cell in ov["cells"]:
        lines.append(f"  {cell['case_id']} {cell['model']:7s} {cell['harness']:15s} "
                     f"anche con C: {cell['candidata_anche_nel_run_con_C']} | stessa regola: "
                     f"{cell['stessa_regola_della_stessa_cella'] or cell['stessa_regola_in_altra_cella']}")
    lines += ["", "CONFRONTO L2:"]
    for title, key in (("D->C->K (congelato)", "l2_with_cause"), ("D->K (senza causa)", "l2_without_cause")):
        results = cmp[key]
        lines.append(f"  {title}: " + ("nessuna regola valutata" if not results else ""))
        for res in results:
            fp = res["false_positives"]
            lines.append(f"    {res['rule_name']} -> {res['target_fault_type']}: {res['verdict']} "
                         f"{res['reasons']} | TP {res['counts']['tp']} FN {res['counts']['fn']} "
                         f"TN {res['counts']['tn']} FP {res['counts']['fp']} | FP {fp['fp']}/"
                         f"{fp['negatives_complete']} IC95% {fp['interval95']} | positivi non osservabili "
                         f"{res['positives_not_observable']['count']}")
    lines.append(f"  stato L2 D->K: {cmp['l2_without_cause_status']}")
    lines += ["", NOT_BLIND]
    return "\n".join(lines)


# ---------------------------------------------------------------- riga di comando

def _paths(args) -> dict:
    root = Path(args.drive_root)
    return {"root": root,
            "store": root / (args.namespace or dk.NAMESPACE.as_posix()),
            "out": root / OUT_RELATIVE,
            "freeze": root / proto.FREEZE_RELATIVE,
            "addendum": root / l2x.ADDENDUM_RELATIVE,
            "frozen_l1": root / proto.REPORT_RELATIVE,
            "frozen_l2b": root / FROZEN_L2B_RELATIVE,
            "catalog": root / proto.CATALOG_RELATIVE,
            "zip": root / "Market.zip",
            "manifest": root / cat.MANIFEST_RELATIVE}


def _frozen_inputs(paths: dict, *, need_addendum: bool) -> tuple[dict, dict | None, list[str]]:
    freeze = _read_json(paths["freeze"])
    addendum = _read_json(paths["addendum"]) if need_addendum else None
    return freeze, addendum, frozen_code_problems(freeze, addendum)


def _load_l1(paths: dict) -> dict:
    report = _read_json(paths["out"] / L1_FILE)
    if not report_is_intact(report) or report.get("uses_ground_truth") or report.get("sealed_incidents_opened"):
        raise DKScopeError("Report L1 D->K manomesso o con GT/sigillati dichiarati")
    return report


def cmd_l1(args) -> int:
    paths = _paths(args)
    _, rows = dk.build_dk_plan()
    entries, integrity = load_dk_entries(paths["store"], rows)
    if not integrity["ok"]:
        print("K SENZA CAUSA NON INTEGRI, L1 non parte:", *integrity["problems"][:20], sep="\n  - ")
        return 2
    freeze, _, problems = _frozen_inputs(paths, need_addendum=False)
    catalog_sha = proto._file_sha256(paths["catalog"])
    if catalog_sha != freeze["catalog_sha256"]:
        problems.append("catalogo_diverso_dal_freeze")
    if problems:
        print("CODICE O DATI NON COINCIDONO COL FREEZE, L1 non parte:", *problems, sep="\n  - ")
        return 2
    code_commit = cat._git_head(Path(args.repo_dir))
    print(f"Verificati: {integrity['records_found']} record K senza causa, codice L1/L2 e parametri "
          f"congelati, catalogo.\n")
    report = run_dk_l1(entries=entries, integrity=integrity, frozen_freeze=freeze,
                       catalog=_read_json(paths["catalog"]), catalog_sha256=catalog_sha,
                       zip_path=paths["zip"], manifest_path=paths["manifest"], code_commit=code_commit)
    print(render_l1(report))
    comparison = build_comparison(dk_report=report, frozen_freeze=freeze,
                                  frozen_l1=_read_json(paths["frozen_l1"]),
                                  frozen_l2b=_safe_json(paths["frozen_l2b"]), dk_l2b=None)
    print("\n" + render_comparison(comparison))
    if not args.no_write:
        target = paths["out"] / L1_FILE
        proto._write_new(target, report)
        print(f"\nScritto (create-only): {target}")
    return 0


def _safe_json(path: Path) -> dict | None:
    return _read_json(path) if Path(path).exists() else None


def cmd_l2a(args) -> int:
    if not args.authorize_sealed_telemetry:
        print("Serve --authorize-sealed-telemetry: L2a legge la telemetria dei sigillati (mai la ground truth).")
        return 2
    paths = _paths(args)
    freeze, frozen_addendum, problems = _frozen_inputs(paths, need_addendum=True)
    if problems:
        print("CODICE O DATI NON COINCIDONO COL FREEZE, L2a non parte:", *problems, sep="\n  - ")
        return 2
    l1_report = _load_l1(paths)
    admitted = l1_report["l1_report"]["admitted_to_l2"]
    if not admitted:
        print("Nessuna candidata D->K ammessa a L2: L2 NON APPLICABILE. Nessun file scritto.")
        return 0
    derived = l1_report["derived_freeze"]
    _, rows = dk.build_dk_plan()
    entries, integrity = load_dk_entries(paths["store"], rows)
    if not integrity["ok"] or integrity["records_fingerprint_sha256"] != derived["run"]["records_fingerprint_sha256"]:
        print("I record dei K senza causa sono cambiati dopo L1: L2a non parte.")
        return 2
    catalog = _read_json(paths["catalog"])
    table = pf.build_table(entries, catalog)
    if proto._sha(sorted((r["stage_id"], r["rule_sha256"]) for r in table["rows"] if r["executable"])) \
            != derived["executable_sha256"]:
        print("L'elenco delle eseguibili non coincide col freeze derivato: L2a non parte.")
        return 2
    release_path = Path(args.repo_dir) / l2x.RELEASE_RELATIVE
    release = _read_json(release_path)
    cases = l2x.load_cases(paths["manifest"], release["test_case_ids"])
    if (l2x.build_window_groups(cases) != frozen_addendum["groups"]
            or proto._file_sha256(release_path) != frozen_addendum["release_sha256"]
            or proto._file_sha256(paths["manifest"]) != frozen_addendum["manifest_sha256"]):
        print("Gruppi, release o manifest diversi dall'addendum congelato: L2a non parte.")
        return 2
    head = cat._git_head(Path(args.repo_dir)) or "non_registrato"
    addendum = build_dk_addendum(derived=derived, frozen_addendum=frozen_addendum, admitted=admitted,
                                 l1_report_sha256=proto._file_sha256(paths["out"] / L1_FILE),
                                 l2_code_commit=head)
    print(f"Verificati: codice congelato, catena, {len(addendum['groups'])} gruppi, "
          f"{len(addendum['rules'])} regola/e ammessa/e.\n")
    if not args.no_write:
        proto._write_new(paths["out"] / ADDENDUM_FILE, addendum)
    report = l2x.run_l2a(addendum=addendum, freeze=derived, table=table, catalog=catalog,
                         zip_path=paths["zip"], head_commit=head)
    print(l2x.render_l2a(report))
    if not args.no_write:
        target = paths["out"] / L2A_FILE
        proto._write_new(target, report)
        print(f"\nScritto (create-only): {paths['out'] / ADDENDUM_FILE}\nScritto (create-only): {target}")
    return 0


def cmd_l2b(args) -> int:
    if not args.authorize_ground_truth:
        print("Serve --authorize-ground-truth: L2b legge la ground truth dei sigillati.")
        return 2
    paths = _paths(args)
    freeze, frozen_addendum, problems = _frozen_inputs(paths, need_addendum=True)
    l1_report = _load_l1(paths)
    addendum = _read_json(paths["out"] / ADDENDUM_FILE)
    l2a = _read_json(paths["out"] / L2A_FILE)
    problems += verify_dk_chain(derived=l1_report["derived_freeze"], addendum=addendum, l2a=l2a,
                                frozen_freeze=freeze, frozen_addendum=frozen_addendum,
                                manifest_sha256=proto._file_sha256(paths["manifest"]))
    if problems:
        print("CATENA DI HASH NON COERENTE, L2b non parte (la ground truth non e' stata letta):",
              *sorted(set(problems)), sep="\n  - ")
        return 2
    print("Catena freeze derivato -> addendum derivato -> decisioni L2a verificata; codice congelato.\n")
    from evaluation import rq2_k_l2_scoring as l2b                      # lato ground truth: solo qui
    from evaluation.v2_case_window_audit import MANIFEST_COLUMNS, _read_csv
    derived = l1_report["derived_freeze"]
    manifest = _read_csv(paths["manifest"], MANIFEST_COLUMNS)
    sources = l2b.read_reference_sources(paths["zip"])
    references = l2b.build_group_references(groups=addendum["groups"], manifest=manifest, sources=sources)
    results = l2b.evaluate_all(freeze=derived, addendum=addendum, l2a=l2a, references=references)
    inner = l2b.build_report(freeze=derived, addendum=addendum, l2a=l2a, references=references,
                             results=results, sources=sources)
    body = {"schema": L2B_SCHEMA, "protocol": PROTOCOL, "version": VERSION, "created_utc": _now(),
            "not_blind": NOT_BLIND, "rules_tested": addendum["rules_tested"],
            "rules_tested_both_pipelines": addendum["rules_tested_both_pipelines"], "l2b": inner}
    report = {**body, "sha256_of_body_without_this_field": proto._sha(body)}
    print(l2b.render_report(inner))
    print(f"\nRegole provate: {addendum['rules_tested']} in D->K, {addendum['rules_tested_both_pipelines']} "
          f"contando anche le 8 del run congelato.\n{NOT_BLIND}")
    if not args.no_write:
        target = paths["out"] / L2B_FILE
        proto._write_new(target, report)
        print(f"\nScritto (create-only): {target}")
    return 0


def cmd_compare(args) -> int:
    paths = _paths(args)
    freeze = _read_json(paths["freeze"])
    comparison = build_comparison(
        dk_report=_load_l1(paths), frozen_freeze=freeze, frozen_l1=_read_json(paths["frozen_l1"]),
        frozen_l2b=_safe_json(paths["frozen_l2b"]), dk_l2b=_safe_json(paths["out"] / L2B_FILE))
    print(render_comparison(comparison))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rq2_dk_l1_l2", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("l1", "l2a", "l2b", "compare"):
        p = sub.add_parser(name)
        p.add_argument("--drive-root", required=True)
        p.add_argument("--repo-dir")
        p.add_argument("--namespace", help="cartella dei K senza causa sotto drive-root "
                       "(default: data/rq2_dk_ablation_v1)")
        if name != "compare":
            p.add_argument("--no-write", action="store_true")
        if name == "l2a":
            p.add_argument("--authorize-sealed-telemetry", action="store_true")
        if name == "l2b":
            p.add_argument("--authorize-ground-truth", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command in ("l1", "l2a") and not args.repo_dir:
        print("--repo-dir obbligatorio")
        return 2
    return {"l1": cmd_l1, "l2a": cmd_l2a, "l2b": cmd_l2b, "compare": cmd_compare}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
