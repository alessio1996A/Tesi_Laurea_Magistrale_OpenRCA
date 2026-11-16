"""Test sintetici del congelamento e del run L1 (nessun dato reale, nessuna API, nessun sigillato)."""
from __future__ import annotations

import contextlib
import copy
import inspect
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import pandas as pd

from agent.tools import _get_telemetry_csv_paths
from evaluation import rq2_k_catalog as cat
from evaluation import rq2_k_l1_preflight as pf
from evaluation import rq2_k_l1_protocol as proto
from evaluation import rq2_k_rule_evaluation as ev
from evaluation import rq2_k_run_integrity as integ
from evaluation import rq2_v5_matrix_runner as mr

START = 1647748800
END = START + 1800
CASE = "cloudbed-1_q032"
START_TIME = "container_start_time_seconds"
COMMIT = "c" * 40

NODE_KPIS = ("system.cpu.pct_usage", "system.cpu.iowait", "ping.can_connect")
CONTAINER_KPIS = (START_TIME, "container_fs_writes./dev/vda", "container_cpu_cfs_throttled_seconds",
                  "container_memory_usage_MB")


def _catalog(containers=3, cases=(CASE,)):
    levels = {"node": NODE_KPIS, "container": CONTAINER_KPIS}
    totals = {"node": 3, "container": containers}
    per_case = {c: {"cloudbed": "cloudbed-1", "window_seconds": 1800, "components_total": dict(totals),
                    "levels": {lv: {k: {"components": totals[lv], "step_seconds": 60.0,
                                        "coverage_min": 1.0, "coverage_median": 1.0}
                                    for k in kpis} for lv, kpis in levels.items()}} for c in cases}
    aggregate = {lv: {k: {"cloudbeds": ["cloudbed-1"], "cases": list(cases), "step_seconds": 60.0,
                          "coverage_min": 1.0, "components_missing_max": 0} for k in kpis}
                 for lv, kpis in levels.items()}
    return {"version": "t", "cases": list(cases), "per_case": per_case, "aggregate": aggregate,
            "median_step_seconds_by_level": {"node": 60.0, "container": 60.0}}


def _cond(metric, operator=">", threshold=0, aggregation="delta", window=600, unit="seconds"):
    return {"metric": metric, "operator": operator, "threshold": threshold, "unit": unit,
            "aggregation": aggregation, "window_seconds": window}


def _entry(conds, stage_id="p:case:sonnet:A1:K", name="regola", combination="all"):
    rule = {"status": "candidate", "combination": combination, "conditions": conds,
            "hypothesized_fault_type": "container process termination", "rule_name": name,
            "pseudocode": "ignorato"}
    return {"stage_id": stage_id, "case_id": CASE, "model": "sonnet", "harness": "A1", "stage": "K",
            "record_status": "RECORDED_COMPLETE", "rule": rule, "outcome": "candidate"}


def _table(entries, catalog=None):
    return pf.build_table(entries, catalog or _catalog())


def _history(table, *, cases=4, components=3, first=3, full=3, threshold="raggiungibile", cumulative=False):
    """Storia sintetica con `cases` casi, per tutte le regole eseguibili."""
    checks = []
    for row in table["rows"]:
        if not row["executable"]:
            continue
        info = {"components_with_kpi": components, "with_sample_in_first_window": first,
                "with_full_history": full, "threshold": threshold,
                "cumulative_counter_hint": cumulative}
        checks.append({"stage_id": row["stage_id"], "rule_name": row["rule_name"],
                       "conditions": [{"metric": c["metric"], "aggregation": c["aggregation"],
                                       "window_seconds": c["window_seconds"],
                                       "cases": {f"case{i}": dict(info) for i in range(cases)}}
                                      for c in row["conditions"]]})
    return {"profiles": {}, "files_missing": [], "checks": checks}


INTEGRITY = {"ok": True, "expected_commit": "d" * 40, "records_fingerprint_sha256": "f" * 64,
             "stages_in_plan": 180, "manifest": {"plan_preview_sha256": "p" * 64}}


def _freeze(table=None, history=None, integrity=None):
    table = table or _table([_entry([_cond(START_TIME)])])
    return table, proto.build_freeze(table=table, history=history or _history(table),
                                     integrity=integrity or INTEGRITY, catalog_sha256="a" * 64,
                                     code_commit=COMMIT, created_utc="2026-11-16T00:00:00Z")


class ParametersTests(unittest.TestCase):
    def test_frozen_parameters_are_the_approved_ones(self):
        params = proto.PARAMETERS
        self.assertEqual((params["h_pre_seconds"], params["h_seconds"], params["grid_seconds"]), (60, 300, 60))
        self.assertEqual(params["l1"]["pass_criteria"]["min_evaluable_fraction"], 0.95)
        self.assertEqual(params["l2"]["negative_coverage_min_exploratory"], 2 / 3)
        self.assertEqual(params["l1"]["cases"], list(cat.DISCOVERY_CASES))
        self.assertFalse(params["l1"]["uses_ground_truth"])
        self.assertIn("non e' una tolleranza certificata", params["h_note"].lower().replace("’", "'"))

    def test_parameters_hash_is_pinned(self):
        # Se cambia, serve un nuovo congelamento.
        self.assertEqual(proto.parameters_sha256(), "7875e28f6075eb6e6b1ff3b29f963a06b38dbbc933bfe453fb54041f656a5ce0")


class IsolationTests(unittest.TestCase):
    def test_the_protocol_module_does_not_import_the_ground_truth_side(self):
        source = Path(proto.__file__).read_text(encoding="utf-8")
        for forbidden in ("import rq2_k_rule_evaluation", "rq2_rule_group_scorer import",
                          "rq2_fault_type_eval_policy"):
            self.assertNotIn("from evaluation " + forbidden, source)
            self.assertNotIn(forbidden, source.split("FROZEN_SOURCES")[0])

    def test_duplicated_constants_agree_with_the_evaluator(self):
        self.assertEqual(proto.NEGATIVE_COVERAGE_MIN, ev.NEGATIVE_COVERAGE_MIN)
        self.assertEqual(proto._declared_version("rq2_k_rule_evaluation.py"), ev.VERSION)
        self.assertEqual(proto._declared_version("rq2_k_rule_executor.py"), ex_version())

    def test_frozen_sources_exist_and_are_hashed(self):
        hashes = proto.sources_sha256()
        self.assertEqual(sorted(hashes), sorted(proto.FROZEN_SOURCES))
        self.assertTrue(all(len(h) == 64 for h in hashes.values()))


def ex_version():
    from evaluation import rq2_k_rule_executor
    return rq2_k_rule_executor.VERSION


class EligibilityTests(unittest.TestCase):
    def _eligibility(self, conds, **history_kwargs):
        table = _table([_entry(conds)])
        return table, proto.eligibility_for(table["rows"], _history(table, **history_kwargs))

    def test_formalizable_with_all_checks_is_eligible(self):
        table, el = self._eligibility([_cond(START_TIME)])
        self.assertTrue(el[table["rows"][0]["stage_id"]]["eligible_for_l2"])

    def test_classifiable_does_not_pass_automatically_a_bad_unit(self):
        table, el = self._eligibility([_cond(START_TIME, unit="MB")])
        only = el[table["rows"][0]["stage_id"]]
        self.assertEqual(table["rows"][0]["l1_outcome"], pf.FORMALIZABLE)     # classificabile...
        self.assertFalse(only["unit_ok"])                                     # ...ma unita' incoerente
        self.assertFalse(only["eligible_for_l2"])

    def test_incomplete_history_blocks_eligibility(self):
        for kwargs in ({"full": 2}, {"first": 2}, {"components": 0, "first": 0, "full": 0}, {"cases": 3}):
            _, el = self._eligibility([_cond(START_TIME)], **kwargs)
            only = next(iter(el.values()))
            self.assertFalse(only["history_ok"], kwargs)
            self.assertFalse(only["eligible_for_l2"], kwargs)

    def test_threshold_unreachable_in_every_case_blocks_eligibility(self):
        _, el = self._eligibility([_cond(START_TIME)], threshold="soglia_sopra_il_massimo_osservato")
        self.assertFalse(next(iter(el.values()))["conditions_ok"])

    def test_cumulative_counter_without_delta_blocks_eligibility(self):
        _, el = self._eligibility([_cond(START_TIME)], cumulative=True)
        only = next(iter(el.values()))
        self.assertFalse(only["conditions_ok"])
        self.assertTrue(any("contatore_cumulativo" in n for n in only["notes"]))

    def test_not_classifiable_rule_is_executable_but_never_eligible(self):
        table, el = self._eligibility([_cond("system.cpu.iowait", aggregation="max", window=60, unit="percent")])
        self.assertEqual(table["rows"][0]["l1_outcome"], pf.NOT_CLASSIFIABLE)
        self.assertFalse(el[table["rows"][0]["stage_id"]]["eligible_for_l2"])

    def test_not_formalizable_rule_has_no_eligibility_entry(self):
        table, el = self._eligibility([_cond("mrt_max", aggregation="max", unit="ms")])
        self.assertEqual(el, {})


class FreezeTests(unittest.TestCase):
    def test_freeze_contents_and_hashes(self):
        table, freeze = _freeze()
        self.assertTrue(proto.freeze_is_intact(freeze))
        self.assertEqual(freeze["code_commit"], COMMIT)
        self.assertEqual(freeze["rules_tested"], 1)
        self.assertEqual(len(freeze["executable"]), 1)
        self.assertEqual(freeze["l2_eligible"][0][2], pf.C_PROCESS)
        self.assertEqual(freeze["semantic_table_sha256"], pf.semantic_table_sha256())
        self.assertEqual(freeze["parameters_sha256"], proto.parameters_sha256())
        self.assertEqual(freeze["run"]["records_fingerprint_sha256"], "f" * 64)
        self.assertIn("PRIMA di aprire gli 11 incidenti sigillati", freeze["statement"])

    def test_freeze_is_deterministic(self):
        self.assertEqual(_freeze()[1], _freeze()[1])

    def test_tampering_is_detected(self):
        _, freeze = _freeze()
        broken = copy.deepcopy(freeze)
        broken["parameters"]["h_seconds"] = 999
        self.assertFalse(proto.freeze_is_intact(broken))

    def test_refuses_without_integrity_or_commit(self):
        table = _table([_entry([_cond(START_TIME)])])
        with self.assertRaises(proto.FreezeError):
            proto.build_freeze(table=table, history=_history(table), integrity={"ok": False},
                               catalog_sha256="a" * 64, code_commit=COMMIT)
        with self.assertRaises(proto.FreezeError):
            proto.build_freeze(table=table, history=_history(table), integrity=INTEGRITY,
                               catalog_sha256="a" * 64, code_commit=None)

    def test_verify_freeze_matches_when_nothing_changed(self):
        table, freeze = _freeze()
        self.assertEqual(proto.verify_freeze(freeze, table=table, integrity=INTEGRITY,
                                             catalog_sha256="a" * 64, code_commit=COMMIT), [])

    def test_verify_freeze_names_every_difference(self):
        table, freeze = _freeze()
        other = _table([_entry([_cond(START_TIME, threshold=5)])])
        problems = proto.verify_freeze(
            freeze, table=other, integrity={**INTEGRITY, "records_fingerprint_sha256": "0" * 64},
            catalog_sha256="b" * 64, code_commit="e" * 40)
        text = " ".join(problems)
        for needle in ("commit_del_codice_diverso", "catalogo_diverso", "impronta_dei_record_diversa",
                       "elenco_delle_eseguibili_diverso"):
            self.assertIn(needle, text)
        tampered = copy.deepcopy(freeze)
        tampered["sources_sha256"]["rq2_k_rule_executor.py"] = "0" * 64
        tampered["sha256_of_body_without_this_field"] = proto._sha(
            {k: v for k, v in tampered.items() if k != "sha256_of_body_without_this_field"})
        problems = proto.verify_freeze(tampered, table=table, integrity=INTEGRITY,
                                       catalog_sha256="a" * 64, code_commit=COMMIT)
        self.assertEqual(len(problems), 1)
        self.assertIn("sorgenti_diversi: rq2_k_rule_executor.py", problems[0])
        self.assertIn("integrita_del_run_non_verificata", " ".join(proto.verify_freeze(
            freeze, table=table, integrity={**INTEGRITY, "ok": False},
            catalog_sha256="a" * 64, code_commit=COMMIT)))

    def test_create_only_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x" / "freeze.json"
            proto._write_new(path, {"a": 1})
            with self.assertRaises(FileExistsError):
                proto._write_new(path, {"a": 2})
            self.assertIn('"a": 1', path.read_text(encoding="utf-8"))

    def test_render_freeze_mentions_the_key_numbers(self):
        _, freeze = _freeze()
        text = proto.render_freeze(freeze)
        for needle in (COMMIT, "H_pre=60", "H=300", freeze["executable_sha256"], "ammessa=True"):
            self.assertIn(needle, text)


class RunL1Tests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "data/processed").mkdir(parents=True)
        pd.DataFrame([{"case_id": CASE, "cloudbed": "cloudbed-1",
                       "start_unix": START, "end_unix": END}]).to_csv(
            self.root / cat.MANIFEST_RELATIVE, index=False)

    def tearDown(self):
        self._tmp.cleanup()

    def _rows(self, cmdb, kpi, first, last, value=lambda i, t: 1000.0, step=60):
        return [{"timestamp": t, "cmdb_id": cmdb, "kpi_name": kpi, "value": value(i, t)}
                for i, t in enumerate(range(first, last, step))]

    def _zip(self, rows, lo=START - 600):
        path = self.root / "Market.zip"
        names = _get_telemetry_csv_paths(lo, END, "cloudbed-1", "container_metrics")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(names[-1], pd.DataFrame(rows, columns=cat.COLUMNS).to_csv(index=False))
        return path

    def _telemetry(self):
        jump = lambda i, t: 1000.0 if t < START + 300 else 2000.0           # noqa: E731
        return (self._rows("c1", START_TIME, START - 600, END, jump)
                + self._rows("c2", START_TIME, START - 600, END)
                + self._rows("c3", "container_memory_usage_MB", START - 600, END))   # senza il KPI

    def _run(self, table, containers=3, zip_rows=None, cases=(CASE,)):
        table_, freeze = _freeze(table)
        catalog = _catalog(containers)
        return proto.run_l1(freeze=freeze, table=table_, catalog=catalog,
                            zip_path=self._zip(zip_rows or self._telemetry()),
                            manifest_path=self.root / cat.MANIFEST_RELATIVE, cases=cases)

    def test_end_to_end_population_and_decision(self):
        table = _table([_entry([_cond(START_TIME)])])
        report = self._run(table)
        rule = report["rules"][0]
        info = rule["per_case"][CASE]
        self.assertEqual(info["decision"], "positive")
        self.assertEqual((info["components_total"], info["components_in_population"]), (3, 2))
        self.assertEqual(info["components_excluded"], ["c3"])
        self.assertEqual(info["excluded_missing_metrics"], {"c3": [START_TIME]})
        self.assertEqual(info["firing_components"], ["c1"])
        self.assertEqual(info["first_fire_unix_by_component"], {"c1": START + 300})
        self.assertAlmostEqual(info["population_coverage"], 2 / 3)
        self.assertTrue(rule["l1_pass"], rule["l1_failures"])
        self.assertEqual(report["admitted_to_l2"], [rule["stage_id"]])
        self.assertFalse(report["uses_ground_truth"] or report["sealed_incidents_opened"])

    def test_non_eligible_rule_is_reported_descriptively_only(self):
        table = _table([_entry([_cond("system.cpu.iowait", aggregation="max", window=60, unit="percent")])])
        report = proto.run_l1(freeze=_freeze(table)[1], table=table, catalog=_catalog(),
                              zip_path=self._node_zip(), manifest_path=self.root / cat.MANIFEST_RELATIVE,
                              cases=(CASE,))
        rule = report["rules"][0]
        self.assertEqual(rule["reporting"], "descrittivo_solo_L1")
        self.assertEqual(report["admitted_to_l2"], [])

    def _node_zip(self):
        path = self.root / "Market.zip"
        name = _get_telemetry_csv_paths(START - 60, END, "cloudbed-1", "node_metrics")[-1]
        rows = (self._rows("n1", "system.cpu.iowait", START - 60, END, lambda i, t: 3.0)
                + self._rows("n2", "system.cpu.iowait", START - 60, END, lambda i, t: 3.0)
                + self._rows("n3", "system.cpu.iowait", START - 60, END, lambda i, t: 3.0))
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(name, pd.DataFrame(rows, columns=cat.COLUMNS).to_csv(index=False))
        return path

    def test_catalog_total_mismatch_fails_l1(self):
        report = self._run(_table([_entry([_cond(START_TIME)])]), containers=40)
        rule = report["rules"][0]
        self.assertFalse(rule["l1_pass"])
        self.assertTrue(any("componenti_totali_diversi_dal_catalogo" in f for f in rule["l1_failures"]))
        self.assertEqual(report["admitted_to_l2"], [])

    def test_missing_history_file_fails_l1_and_is_reported(self):
        table = _table([_entry([_cond(START_TIME, window=46800)])])      # storia fino al giorno prima
        report = self._run(table)
        self.assertTrue(report["history_files_missing"])
        self.assertFalse(report["rules"][0]["l1_pass"])

    def test_low_evaluable_fraction_fails_l1(self):
        # nessun campione nelle ultime finestre: la regola e' quasi tutta sconosciuta
        rows = (self._rows("c1", START_TIME, START - 600, START + 120) + self._rows("c2", START_TIME, START - 600, START + 120)
                + self._rows("c3", "container_memory_usage_MB", START - 600, END))
        report = self._run(_table([_entry([_cond(START_TIME)])]), zip_rows=rows)
        self.assertFalse(report["rules"][0]["l1_pass"])

    def test_sealed_case_is_refused(self):
        table = _table([_entry([_cond(START_TIME)])])
        with self.assertRaises(cat.CatalogScopeError):
            self._run(table, cases=("cloudbed-1_q014",))

    def test_no_parameter_or_field_can_carry_labels(self):
        names = list(inspect.signature(proto.run_l1).parameters)
        self.assertEqual(names, ["freeze", "table", "catalog", "zip_path", "manifest_path", "cases"])
        report = self._run(_table([_entry([_cond(START_TIME)])]))
        self.assertFalse([k for k in report if k.lower() in ("gt", "label", "labels", "truth", "reference")])

    def test_render_report(self):
        report = self._run(_table([_entry([_cond(START_TIME)])]))
        text = proto.render_report(report)
        for needle in ("PASSATO", "AMMESSE A L2", "I sigillati NON sono stati aperti", "CAUTELA", "RIAVVIO OSSERVABILE"):
            self.assertIn(needle, text)


class CliSmokeTests(unittest.TestCase):
    """freeze e run da riga di comando su un mini-archivio sintetico (piano di 3 stage)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        stem = "plan:case-1:m1:A1"
        self.rows = [
            {"stage_id": f"{stem}:{s}", "stage": s, "case_id": "case-1", "logical_model": "m1",
             "model_id": "model-x", "model_provider": "google", "harness": "A1",
             "depends_on": [f"{stem}:{d}" for d in deps], "d_engine": "x", "execution_status": "planned"}
            for s, deps in (("D", []), ("C", ["D"]), ("K", ["D", "C"]))]
        self.plan = {"preview_sha256": "p" * 64}
        store_root = self.root / proto.STORE_RELATIVE
        store = mr.StageStore(store_root)
        rule = {"schema_version": "rq2_candidate_rule_v0", "status": "candidate", "combination": "all",
                "rule_name": "container_restart", "hypothesized_fault_type": "container process termination",
                "conditions": [_cond(START_TIME)], "pseudocode": "ignorato"}
        for row in self.rows:
            claim = store.claim(row["stage_id"], {**mr._identity(row), "source_commit": integ.FROZEN_COMMIT})
            receipt = ({"artifact": {"raw_response": json.dumps(rule)}} if row["stage"] == "K" else {})
            store.write_record(row["stage_id"], {
                **mr._identity(row), "status": mr.STATUS_COMPLETE, "receipt": receipt, "format": None,
                "provenance": None, "error_summary": None, "blocked_by": None,
                "claim_sha256": claim["claim_sha256"], "started_at_utc": "t", "finished_at_utc": "t",
                "elapsed_seconds": 1.0, "source_commit": integ.FROZEN_COMMIT})
        (store_root / integ.MANIFEST).write_text(json.dumps(
            {"protocol": mr.PROTOCOL, "plan_preview_sha256": "p" * 64,
             "created_commit": integ.FROZEN_COMMIT}), encoding="utf-8")
        catalog_path = self.root / proto.CATALOG_RELATIVE
        catalog_path.parent.mkdir(parents=True)
        catalog_path.write_text(json.dumps(_catalog(3, cases=cat.DISCOVERY_CASES)), encoding="utf-8")
        (self.root / "data/processed").mkdir(parents=True, exist_ok=True)
        pd.DataFrame([{"case_id": c, "cloudbed": "cloudbed-1", "start_unix": START, "end_unix": END}
                      for c in cat.DISCOVERY_CASES]).to_csv(self.root / cat.MANIFEST_RELATIVE, index=False)
        jump = lambda i, t: 1000.0 if t < START + 300 else 2000.0               # noqa: E731
        rows = []
        for cmdb, value in (("c1", jump), ("c2", lambda i, t: 1000.0)):
            rows += [{"timestamp": t, "cmdb_id": cmdb, "kpi_name": START_TIME, "value": value(i, t)}
                     for i, t in enumerate(range(START - 600, END, 60))]
        rows += [{"timestamp": t, "cmdb_id": "c3", "kpi_name": "container_memory_usage_MB", "value": 1.0}
                 for t in range(START - 600, END, 60)]
        name = _get_telemetry_csv_paths(START - 600, END, "cloudbed-1", "container_metrics")[-1]
        with zipfile.ZipFile(self.root / "Market.zip", "w") as archive:
            archive.writestr(name, pd.DataFrame(rows, columns=cat.COLUMNS).to_csv(index=False))

    def tearDown(self):
        self._tmp.cleanup()

    def _main(self, command, commit=COMMIT):
        out = io.StringIO()
        with mock.patch("evaluation.rq2_v5_run_cli._plan_rows", return_value=(self.plan, self.rows)), \
                mock.patch.object(cat, "_git_head", return_value=commit), contextlib.redirect_stdout(out):
            code = proto.main([command, "--drive-root", str(self.root), "--repo-dir", str(self.root)])
        return code, out.getvalue()

    def test_freeze_then_run_end_to_end(self):
        code, text = self._main("freeze")
        self.assertEqual(code, 0, text)
        freeze = json.loads((self.root / proto.FREEZE_RELATIVE).read_text(encoding="utf-8"))
        self.assertTrue(proto.freeze_is_intact(freeze))
        self.assertEqual(len(freeze["l2_eligible"]), 1, text)
        code, text = self._main("run")
        self.assertEqual(code, 0, text)
        self.assertIn("Freeze verificato", text)
        report = json.loads((self.root / proto.REPORT_RELATIVE).read_text(encoding="utf-8"))
        self.assertEqual(len(report["admitted_to_l2"]), 1, text)
        self.assertEqual(sorted(report["rules"][0]["per_case"]), sorted(cat.DISCOVERY_CASES))
        self.assertFalse(report["uses_ground_truth"] or report["sealed_incidents_opened"])

    def test_freeze_and_report_are_create_only(self):
        self._main("freeze")
        with self.assertRaises(FileExistsError):
            self._main("freeze")
        self._main("run")
        with self.assertRaises(FileExistsError):
            self._main("run")

    def test_run_refuses_when_the_code_commit_differs_and_writes_nothing(self):
        self._main("freeze")
        code, text = self._main("run", commit="e" * 40)
        self.assertEqual(code, 2)
        self.assertIn("commit_del_codice_diverso", text)
        self.assertFalse((self.root / proto.REPORT_RELATIVE).exists())

    def test_run_refuses_when_a_record_was_altered_after_the_freeze(self):
        self._main("freeze")
        store = mr.StageStore(self.root / proto.STORE_RELATIVE)
        path = store._record_path(self.rows[0]["stage_id"])
        data = json.loads(path.read_text(encoding="utf-8"))
        data["elapsed_seconds"] = 99.0
        path.write_text(json.dumps(data), encoding="utf-8")
        code, text = self._main("run")
        self.assertEqual(code, 2)
        self.assertIn("integrita_del_run_non_verificata", text)

    def test_freeze_refuses_a_run_that_fails_the_integrity_check(self):
        store = mr.StageStore(self.root / proto.STORE_RELATIVE)
        store._record_path(self.rows[1]["stage_id"]).unlink()
        with self.assertRaises(proto.FreezeError):
            self._main("freeze")
        self.assertFalse((self.root / proto.FREEZE_RELATIVE).exists())

    def test_no_write_flag_writes_nothing(self):
        out = io.StringIO()
        with mock.patch("evaluation.rq2_v5_run_cli._plan_rows", return_value=(self.plan, self.rows)), \
                mock.patch.object(cat, "_git_head", return_value=COMMIT), contextlib.redirect_stdout(out):
            proto.main(["freeze", "--drive-root", str(self.root), "--repo-dir", str(self.root), "--no-write"])
        self.assertFalse((self.root / proto.FREEZE_RELATIVE).exists())


if __name__ == "__main__":
    unittest.main()
