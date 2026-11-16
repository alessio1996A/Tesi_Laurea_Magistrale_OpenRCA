"""Test sintetici di L2a (esecuzione senza GT) e L2b (valutazione con GT).

Nessun dato reale, nessuna API, nessun incidente sigillato: solo archivi e manifest inventati.
"""
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

import test_rq2_k_l1_protocol_offline as l1t
from agent.tools import _get_telemetry_csv_paths
from evaluation import rq2_k_catalog as cat
from evaluation import rq2_k_l1_protocol as proto
from evaluation import rq2_k_l2_execute as l2x
from evaluation import rq2_k_l2_scoring as l2b
from evaluation import rq2_k_rule_executor as ex

START = l1t.START
START_TIME = l1t.START_TIME
L2_COMMIT = "e" * 40
TARGET = "container process termination"


def _case(case_id, bed, start, end):
    return {"case_id": case_id, "cloudbed": bed, "start_unix": start, "end_unix": end}


def _write_manifest(path: Path, cases, extra_columns=None):
    rows = [{"case_id": c["case_id"], "cloudbed": c["cloudbed"], "start_unix": c["start_unix"],
             "end_unix": c["end_unix"], **(extra_columns or {})} for c in cases]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


class WindowGroupTests(unittest.TestCase):
    def test_touching_windows_form_one_group(self):
        groups = l2x.build_window_groups([_case("a", "cloudbed-1", 0, 100), _case("b", "cloudbed-1", 100, 200)])
        self.assertEqual(len(groups), 1)
        self.assertEqual((groups[0]["start_unix"], groups[0]["end_unix"]), (0, 200))
        self.assertEqual(groups[0]["case_ids"], ["a", "b"])

    def test_a_gap_of_one_second_keeps_groups_apart(self):
        self.assertEqual(len(l2x.build_window_groups(
            [_case("a", "cloudbed-1", 0, 100), _case("b", "cloudbed-1", 101, 200)])), 2)

    def test_same_window_in_different_cloudbeds_is_not_grouped(self):
        self.assertEqual(len(l2x.build_window_groups(
            [_case("a", "cloudbed-1", 0, 100), _case("b", "cloudbed-2", 0, 100)])), 2)

    def test_chains_are_connected_transitively(self):
        groups = l2x.build_window_groups([_case("a", "cloudbed-1", 0, 100), _case("c", "cloudbed-1", 200, 300),
                                          _case("b", "cloudbed-1", 100, 200)])
        self.assertEqual([g["case_ids"] for g in groups], [["a", "b", "c"]])

    def test_ids_and_order_do_not_depend_on_input_order(self):
        cases = [_case("x", "cloudbed-2", 50, 80), _case("a", "cloudbed-1", 0, 100),
                 _case("b", "cloudbed-1", 500, 600)]
        first = l2x.build_window_groups(cases)
        second = l2x.build_window_groups(list(reversed(cases)))
        self.assertEqual(first, second)
        self.assertEqual([g["group_id"] for g in first], ["W01", "W02", "W03"])
        self.assertEqual([g["cloudbed"] for g in first], ["cloudbed-1", "cloudbed-1", "cloudbed-2"])

    def test_eleven_cases_can_make_ten_groups(self):
        cases = [_case(f"c{i}", "cloudbed-1", i * 1000, i * 1000 + 500) for i in range(10)]
        cases.append(_case("c10", "cloudbed-1", 500, 900))                  # tocca c0
        self.assertEqual(len(l2x.build_window_groups(cases)), 10)


class LoadCasesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "manifest.csv"

    def tearDown(self):
        self._tmp.cleanup()

    def test_reads_only_the_requested_windows(self):
        _write_manifest(self.path, [_case("cloudbed-1_q1", "cloudbed-1", 10, 20),
                                    _case("cloudbed-1_q2", "cloudbed-1", 30, 40)])
        cases = l2x.load_cases(self.path, ["cloudbed-1_q2"])
        self.assertEqual(cases, [_case("cloudbed-1_q2", "cloudbed-1", 30, 40)])

    def test_only_the_window_columns_are_read(self):
        _write_manifest(self.path, [_case("cloudbed-1_q1", "cloudbed-1", 10, 20)],
                        {"instruction": "testo della domanda", "task_index": "task_3"})
        with mock.patch.object(l2x.pd, "read_csv", wraps=pd.read_csv) as spy:
            l2x.load_cases(self.path, ["cloudbed-1_q1"])
        self.assertIn(list(l2x.WINDOW_COLUMNS), [c.kwargs.get("usecols") for c in spy.call_args_list])

    def test_ground_truth_columns_are_refused(self):
        _write_manifest(self.path, [_case("cloudbed-1_q1", "cloudbed-1", 10, 20)], {"reason": "x"})
        with self.assertRaises(l2x.L2ScopeError):
            l2x.load_cases(self.path, ["cloudbed-1_q1"])

    def test_discovery_cases_are_refused(self):
        _write_manifest(self.path, [_case(cat.DISCOVERY_CASES[0], "cloudbed-1", 10, 20)])
        with self.assertRaises(l2x.L2ScopeError):
            l2x.load_cases(self.path, [cat.DISCOVERY_CASES[0]])

    def test_missing_duplicated_or_invalid_rows_are_refused(self):
        _write_manifest(self.path, [_case("cloudbed-1_q1", "cloudbed-1", 10, 20),
                                    _case("cloudbed-1_q1", "cloudbed-1", 10, 20),
                                    _case("cloudbed-1_q3", "cloudbed-9", 10, 20),
                                    _case("cloudbed-1_q4", "cloudbed-1", 20, 10)])
        for bad in (["cloudbed-1_q1"], ["cloudbed-1_q9"], ["cloudbed-1_q3"], ["cloudbed-1_q4"], []):
            with self.assertRaises(l2x.L2ScopeError):
                l2x.load_cases(self.path, bad)


def _fixture(case_ids=("s1", "s2", "s3")):
    """Freeze con una regola ammessa, report L1 coerente, release e finestre dei sigillati."""
    table, freeze = l1t._freeze()
    stage = freeze["l2_eligible"][0][0]
    l1_report = {"freeze_sha256": freeze["sha256_of_body_without_this_field"], "uses_ground_truth": False,
                 "sealed_incidents_opened": False, "admitted_to_l2": [stage]}
    cases = [_case("s1", "cloudbed-1", START + 7200, START + 9000),
             _case("s2", "cloudbed-1", START + 9000, START + 10800),
             _case("s3", "cloudbed-1", START + 14400, START + 16200)]
    release = {"test_case_ids": list(case_ids), "test_window_groups": 2}
    inputs = {"freeze": freeze, "freeze_file_sha256": "z" * 64, "release": release, "release_sha256": "r" * 64,
              "manifest_sha256": "m" * 64, "l1_report": l1_report, "l1_report_sha256": "l" * 64, "cases": cases,
              "l2_sources": l2x.l2_sources_sha256(), "loaders": l2x.loaders_sha256(),
              "l2_code_commit": L2_COMMIT}
    return table, freeze, inputs


class AddendumTests(unittest.TestCase):
    def test_contents_and_hashes(self):
        _, freeze, inputs = _fixture()
        addendum = l2x.build_addendum(created_utc="2026-11-17T00:00:00Z", **inputs)
        self.assertTrue(l2x.addendum_is_intact(addendum))
        self.assertEqual(addendum["freeze_sha256"], freeze["sha256_of_body_without_this_field"])
        self.assertEqual(addendum["sealed_case_ids"], ["s1", "s2", "s3"])
        self.assertEqual([g["case_ids"] for g in addendum["groups"]], [["s1", "s2"], ["s3"]])
        self.assertEqual(addendum["rules"][0]["target_fault_type"], TARGET)
        self.assertTrue(addendum["rules"][0]["caveats"])
        self.assertEqual(addendum["parameters_sha256"], proto.parameters_sha256())
        self.assertEqual(set(addendum["l2_sources_sha256"]), set(l2x.L2_SOURCES))
        self.assertEqual(addendum, l2x.build_addendum(created_utc="2026-11-17T00:00:00Z", **inputs))

    def test_addendum_carries_everything_gpt_asked_for(self):
        _, freeze, inputs = _fixture()
        addendum = l2x.build_addendum(**inputs)
        self.assertEqual(addendum["freeze_sha256"], freeze["sha256_of_body_without_this_field"])
        self.assertEqual(addendum["freeze_file_sha256"], "z" * 64)
        self.assertEqual(addendum["freeze_code_commit"], freeze["code_commit"])
        self.assertEqual(set(addendum["loaders_sha256"]), set(l2x.LOADER_FILES))
        self.assertEqual(addendum["parameters"], freeze["parameters"])
        self.assertEqual(addendum["rules"][0]["rule_sha256"], freeze["l2_eligible"][0][1])
        self.assertEqual(addendum["window_source"]["columns_read"], list(l2x.WINDOW_COLUMNS))
        for key in ("group_definition", "population_policy", "decisions_format"):
            self.assertTrue(addendum[key], key)
        self.assertEqual(set(addendum["handling"]), {"reference_incomplete", "reference_component_not_observable",
                                                      "abstain_or_error", "negative_scope", "no_complete_positive"})
        notes = " ".join(addendum["annotations"])
        self.assertIn("2474886a551044565b062806a12a6ff9730b3299", notes)
        self.assertIn("88e46580c38dd89cbfae8076ba0752776c1c12b5", notes)
        self.assertIn("freeze.json non e' stato modificato", notes)

    def test_tampering_is_detected(self):
        _, _, inputs = _fixture()
        addendum = l2x.build_addendum(**inputs)
        addendum["groups"][0]["case_ids"] = ["s1"]
        self.assertFalse(l2x.addendum_is_intact(addendum))
        self.assertEqual(l2x.verify_addendum(addendum, **inputs), ["addendum_manomesso"])

    def test_group_count_must_match_the_release(self):
        _, _, inputs = _fixture()
        inputs["release"] = {**inputs["release"], "test_window_groups": 3}
        with self.assertRaises(l2x.L2ScopeError):
            l2x.build_addendum(**inputs)

    def test_sealed_list_must_match_the_manifest_cases(self):
        _, _, inputs = _fixture(case_ids=("s1", "s2", "s9"))
        with self.assertRaises(l2x.L2ScopeError):
            l2x.build_addendum(**inputs)

    def test_a_discovery_case_cannot_be_sealed(self):
        _, _, inputs = _fixture(case_ids=("s1", "s2", cat.DISCOVERY_CASES[0]))
        inputs["cases"] = inputs["cases"][:2] + [_case(cat.DISCOVERY_CASES[0], "cloudbed-1", START + 14400, START + 16200)]
        with self.assertRaises(l2x.L2ScopeError):
            l2x.build_addendum(**inputs)

    def test_l1_report_must_belong_to_this_freeze_and_be_gt_free(self):
        for change in ({"freeze_sha256": "0" * 64}, {"uses_ground_truth": True},
                       {"sealed_incidents_opened": True}, {"admitted_to_l2": []}):
            _, _, inputs = _fixture()
            inputs["l1_report"] = {**inputs["l1_report"], **change}
            with self.assertRaises(l2x.L2ScopeError, msg=str(change)):
                l2x.build_addendum(**inputs)

    def test_verify_addendum_names_each_difference(self):
        _, _, inputs = _fixture()
        addendum = l2x.build_addendum(**inputs)
        self.assertEqual(l2x.verify_addendum(addendum, **inputs), [])
        for key, value, expected in (("release_sha256", "x" * 64, "release_sha256_diverso"),
                                     ("manifest_sha256", "y" * 64, "manifest_sha256_diverso"),
                                     ("l1_report_sha256", "z" * 64, "l1_report_sha256_diverso"),
                                     ("freeze_file_sha256", "q" * 64, "freeze_file_sha256_diverso")):
            changed = {**inputs, key: value}
            self.assertIn(expected, l2x.verify_addendum(addendum, **changed))
        changed = {**inputs, "l2_sources": {**inputs["l2_sources"], "rq2_k_l2_scoring.py": "0" * 64}}
        self.assertIn("l2_sources_sha256_diverso", l2x.verify_addendum(addendum, **changed))
        changed = {**inputs, "loaders": {**inputs["loaders"], "agent/tools.py": "0" * 64}}
        self.assertIn("loaders_sha256_diverso", l2x.verify_addendum(addendum, **changed))

    def test_a_docs_only_commit_after_the_addendum_does_not_invalidate_it(self):
        _, _, inputs = _fixture()
        addendum = l2x.build_addendum(**inputs)
        later = {**inputs, "l2_code_commit": "f" * 40}
        self.assertEqual(l2x.verify_addendum(addendum, **later), [])

    def test_frozen_inputs_accept_only_new_l2_files_tests_and_docs(self):
        table, freeze, _ = _fixture()
        kwargs = dict(table=table, integrity=l1t.INTEGRITY, catalog_sha256="a" * 64, repo_dir=Path("."))
        allowed = ["src/evaluation/rq2_k_l2_execute.py", "src/evaluation/rq2_k_l2_scoring.py",
                   "src/tests/test_rq2_k_l2_offline.py", "docs/REGISTRO_DECISIONI_RQ2.md"]
        with mock.patch.object(l2x, "_git_changed_files", return_value=allowed):
            self.assertEqual(l2x.verify_frozen_inputs(freeze, **kwargs), [])
        for forbidden in ("src/evaluation/rq2_k_rule_executor.py", "src/evaluation/rq2_v5_matrix_runner.py",
                          "src/evaluation/rq2_k_l1_protocol.py"):
            with mock.patch.object(l2x, "_git_changed_files", return_value=allowed + [forbidden]):
                problems = l2x.verify_frozen_inputs(freeze, **kwargs)
            self.assertTrue(any(forbidden in p for p in problems), forbidden)


class IsolationTests(unittest.TestCase):
    def test_l2a_does_not_import_the_ground_truth_side(self):
        import ast
        tree = ast.parse(Path(l2x.__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                imported |= {f"{node.module}.{a.name}" for a in node.names}
        for forbidden in ("rq2_k_rule_evaluation", "rq2_k_l2_scoring", "ood_class_inventory",
                          "rq2_rule_group_scorer", "rq2_fault_type_eval_policy"):
            self.assertFalse(any(forbidden in name for name in imported), forbidden)
        code = Path(l2x.__file__).read_text(encoding="utf-8").split('"""', 2)[2]
        for forbidden in ("record.csv", "scoring_points"):
            self.assertNotIn(forbidden, code)

    def test_every_project_import_of_the_l2_modules_has_a_recorded_hash(self):
        import ast
        covered = set(l2x.LOADER_FILES) | {"evaluation/" + n for n in l2x.L2_SOURCES}
        for module in (l2x, l2b):
            tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    names = [f"{node.module}.{a.name}" for a in node.names] + [node.module]
                elif isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                for name in names:
                    if name.split(".")[0] in ("evaluation", "agent"):
                        candidate = name.replace(".", "/") + ".py"
                        exists = (Path(l2x.__file__).parent.parent / candidate).exists()
                        if exists:
                            self.assertIn(candidate, covered, f"{module.__name__}: {name}")

    def test_no_function_parameter_can_carry_labels(self):
        for fn in (l2x.run_l2a, l2x.build_addendum, l2x.build_window_groups, l2x.load_cases):
            for name in inspect.signature(fn).parameters:
                self.assertFalse(any(h in name.lower() for h in ("gt", "label", "truth", "reference", "fault")),
                                 f"{fn.__name__}:{name}")

    def test_l2_sources_are_hashed_from_the_real_files(self):
        hashes = l2x.l2_sources_sha256()
        self.assertEqual(sorted(hashes), sorted(l2x.L2_SOURCES))
        self.assertEqual(hashes["rq2_k_l2_execute.py"], proto._file_sha256(Path(l2x.__file__)))
        self.assertEqual(hashes["rq2_k_l2_scoring.py"], proto._file_sha256(Path(l2b.__file__)))


# ------------------------------------------------------------------------------ esecuzione L2a
def _telemetry_rows(cmdb, kpi, first, last, value, step=60):
    return [{"timestamp": t, "cmdb_id": cmdb, "kpi_name": kpi, "value": value(t)} for t in range(first, last, step)]


class RunL2aTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.table, self.freeze, self.inputs = _fixture()
        # gruppo W02 su un altro giorno: il suo file di telemetria manca nell'archivio
        self.inputs["cases"][2] = _case("s3", "cloudbed-1", START + 2 * 86400 + 14400, START + 2 * 86400 + 16200)
        self.addendum = l2x.build_addendum(**self.inputs)
        self.catalog = l1t._catalog(3)

    def tearDown(self):
        self._tmp.cleanup()

    def _zip(self, with_second_day=False):
        jump = lambda t: 1000.0 if t < START + 7500 else 2000.0                      # noqa: E731
        rows = (_telemetry_rows("c1", START_TIME, START, START + 11000, jump)
                + _telemetry_rows("c2", START_TIME, START, START + 11000, lambda t: 1000.0)
                + _telemetry_rows("c3", "container_memory_usage_MB", START, START + 11000, lambda t: 1.0))
        path = self.root / "Market.zip"
        with zipfile.ZipFile(path, "w") as archive:
            name = _get_telemetry_csv_paths(START, START + 11000, "cloudbed-1", "container_metrics")[-1]
            archive.writestr(name, pd.DataFrame(rows, columns=cat.COLUMNS).to_csv(index=False))
        return path

    def _run(self, **override):
        zip_path = override.pop("zip_path", None) or self._zip()
        args = {"addendum": self.addendum, "freeze": self.freeze, "table": self.table,
                "catalog": self.catalog, "zip_path": zip_path} | override
        return l2x.run_l2a(**args)

    def test_decisions_population_and_first_fire(self):
        report = self._run()
        rule = report["rules"][0]
        first = rule["per_group"]["W01"]
        self.assertEqual(rule["decisions"]["W01"], "positive")
        self.assertEqual(first["population"], ["c1", "c2"])
        self.assertEqual(first["components_excluded"], ["c3"])
        self.assertEqual(first["first_fire_unix_by_component"], {"c1": START + 7500})
        self.assertAlmostEqual(first["population_coverage"], 2 / 3)
        self.assertEqual(report["uses_ground_truth"], False)
        self.assertEqual(report["ground_truth_opened"], False)
        self.assertTrue(l2x.l2a_is_intact(report))
        self.assertEqual(rule["decisions_sha256"], proto._sha(rule["decisions"]))

    def test_missing_telemetry_gives_abstain_and_is_reported_not_raised(self):
        report = self._run()
        rule = report["rules"][0]
        self.assertEqual(rule["decisions"]["W02"], "abstain")
        self.assertEqual(rule["per_group"]["W02"]["reason"], {"code": "empty_population"})
        self.assertIn("W02:container", report["history_files_missing"])
        self.assertNotIn("W01:container", report["history_files_missing"])

    def test_a_group_without_restart_is_negative(self):
        jump_free = lambda t: 1000.0                                                  # noqa: E731
        rows = (_telemetry_rows("c1", START_TIME, START, START + 11000, jump_free)
                + _telemetry_rows("c2", START_TIME, START, START + 11000, jump_free))
        path = self.root / "Market.zip"
        name = _get_telemetry_csv_paths(START, START + 11000, "cloudbed-1", "container_metrics")[-1]
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(name, pd.DataFrame(rows, columns=cat.COLUMNS).to_csv(index=False))
        report = self._run(zip_path=path)
        self.assertEqual(report["rules"][0]["decisions"]["W01"], "negative")

    def test_addendum_of_another_freeze_or_tampered_is_refused(self):
        other_freeze = copy.deepcopy(self.freeze)
        other_freeze["sha256_of_body_without_this_field"] = "0" * 64
        with self.assertRaises(l2x.L2ScopeError):
            self._run(freeze=other_freeze)
        tampered = copy.deepcopy(self.addendum)
        tampered["rules"][0]["rule_sha256"] = "0" * 64
        with self.assertRaises(l2x.L2ScopeError):
            self._run(addendum=tampered)

    def test_a_rule_that_differs_from_the_addendum_is_refused(self):
        changed = l1t._table([l1t._entry([l1t._cond(START_TIME, threshold=5)])])
        with self.assertRaises(l2x.L2ScopeError):
            self._run(table=changed)

    def test_render_mentions_ground_truth_not_read(self):
        text = l2x.render_l2a(self._run())
        self.assertIn("ground truth NON e' stata letta", text)
        self.assertIn("W01", text)


# ---------------------------------------------------------------------------- valutazione L2b
BED_ROWS = {"cloudbed-1": 5, "cloudbed-2": 2}


def _reference_zip(path: Path, records: dict[int, tuple], task="task_3"):
    """query.csv e record.csv sintetici; `records[i] = (reason, component, timestamp)`."""
    with zipfile.ZipFile(path, "w") as archive:
        for bed, count in BED_ROWS.items():
            queries, recs = [], []
            for i in range(count):
                reason, component, stamp = records.get(i, ("container packet loss", "c2", START)) if bed == "cloudbed-1" \
                    else ("container packet loss", "c2", START)
                queries.append({"task_index": task, "instruction": f"istruzione {bed} {i}",
                                "scoring_points": f"component: {component}"})
                recs.append({"timestamp": stamp, "level": "container", "component": component,
                             "reason": reason, "datetime": "2022-03-20 04:00:00"})
            archive.writestr(f"Market/{bed}/query.csv", pd.DataFrame(queries).to_csv(index=False))
            archive.writestr(f"Market/{bed}/record.csv", pd.DataFrame(recs).to_csv(index=False))
    return path


def _manifest(entries):
    """Voci del manifest nel formato chiuso a sette colonne (tutte stringhe)."""
    return {cid: {"case_id": cid, "cloudbed": bed, "query_index": str(i), "task_index": "task_3",
                  "instruction": f"istruzione {bed} {i}", "start_unix": str(s), "end_unix": str(e)}
            for cid, bed, i, s, e in entries}


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        a0, a1 = START + 7200, START + 9000
        self.groups = [{"group_id": "W01", "cloudbed": "cloudbed-1", "case_ids": ["cloudbed-1_q1", "cloudbed-1_q2"],
                        "start_unix": a0, "end_unix": a1 + 1800},
                       {"group_id": "W02", "cloudbed": "cloudbed-1", "case_ids": ["cloudbed-1_q3"],
                        "start_unix": START + 14400, "end_unix": START + 16200}]
        self.manifest = _manifest([("cloudbed-1_q1", "cloudbed-1", 1, a0, a1),
                                   ("cloudbed-1_q2", "cloudbed-1", 2, a1, a1 + 1800),
                                   ("cloudbed-1_q3", "cloudbed-1", 3, START + 14400, START + 16200)])
        self.records = {1: (TARGET, "c1", START + 7500), 2: ("container packet loss", "c2", START + 9500),
                        3: ("container write I/O load", "c2", START + 14700)}

    def tearDown(self):
        self._tmp.cleanup()

    def _refs(self, records=None, manifest=None, groups=None):
        sources = l2b.read_reference_sources(_reference_zip(self.root / "Market.zip", records or self.records))
        return l2b.build_group_references(groups=groups or self.groups, manifest=manifest or self.manifest,
                                          sources=sources)

    def test_groups_get_classes_faults_and_completeness(self):
        refs = self._refs()
        self.assertEqual(refs[0]["fault_types"], ["container packet loss", TARGET])
        self.assertEqual({f["component"] for f in refs[0]["faults"]}, {"c1", "c2"})
        self.assertEqual([f["t_gt"] for f in refs[0]["faults"] if f["component"] == "c1"], [START + 7500])
        self.assertEqual(refs[1]["fault_types"], ["container write I/O load"])
        self.assertTrue(all(r["reference_complete"] for r in refs))

    def test_an_unrecognised_reason_makes_the_group_incomplete(self):
        refs = self._refs(records={**self.records, 3: ("disk full", "c2", START + 14700)})
        self.assertFalse(refs[1]["reference_complete"])
        self.assertEqual(refs[1]["fault_types"], [])

    def test_alignment_errors_are_refused(self):
        bad_manifests = {
            "indice": {**self.manifest, "cloudbed-1_q1": {**self.manifest["cloudbed-1_q1"], "query_index": "2"}},
            "task": {**self.manifest, "cloudbed-1_q1": {**self.manifest["cloudbed-1_q1"], "task_index": "task_9"}},
            "istruzione": {**self.manifest, "cloudbed-1_q1": {**self.manifest["cloudbed-1_q1"], "instruction": "x"}},
            "finestra": {**self.manifest, "cloudbed-1_q1": {**self.manifest["cloudbed-1_q1"],
                                                           "start_unix": str(START + 8000)}},
        }
        for name, manifest in bad_manifests.items():
            with self.assertRaises(l2b.ReferenceError_, msg=name):
                self._refs(manifest=manifest)

    def test_a_record_outside_the_case_window_is_refused(self):
        with self.assertRaises(l2b.ReferenceError_):
            self._refs(records={**self.records, 1: (TARGET, "c1", START + 99999)})

    def test_a_group_window_that_differs_from_the_manifest_is_refused(self):
        groups = [{**self.groups[0], "end_unix": self.groups[0]["end_unix"] + 60}, self.groups[1]]
        with self.assertRaises(l2b.ReferenceError_):
            self._refs(groups=groups)

    def test_a_record_missing_from_scoring_points_is_refused(self):
        sources = l2b.read_reference_sources(_reference_zip(self.root / "Market.zip", self.records))
        sources["cloudbed-1"]["query"][1]["scoring_points"] = "component: altro"
        with self.assertRaises(l2b.ReferenceError_):
            l2b.build_group_references(groups=self.groups, manifest=self.manifest, sources=sources)


def _l2a(decisions, population=("c1", "c2"), excluded=("c3",), fires=None):
    """Decisioni L2a sintetiche per W01 e W02 (stesso formato di run_l2a)."""
    fires = {"W01": {"c1": START + 7500}, "W02": {}} if fires is None else fires
    per_group = {gid: {"decision": decision, "population": list(population),
                       "components_excluded": list(excluded), "components_total": 3,
                       "components_in_population": len(population),
                       "population_coverage": len(population) / 3, "first_fire_unix_by_component": fires[gid]}
                 for gid, decision in decisions.items()}
    rule = {"stage_id": "s", "rule_name": "regola", "rule_sha256": "a" * 64, "caveats": ["cautela"],
            "target_fault_type": TARGET, "per_group": per_group, "decisions": decisions,
            "decisions_sha256": proto._sha(decisions)}
    return {"rules": [rule]}


class EvaluateTests(unittest.TestCase):
    def setUp(self):
        _, self.freeze, _ = _fixture()
        self.addendum = {"rules_tested": 8}
        self.refs = [
            {"group_id": "W01", "case_ids": ["a", "b"], "fault_types": ["container packet loss", TARGET],
             "reference_complete": True,
             "faults": [{"fault_type": TARGET, "component": "c1", "t_gt": START + 7500, "level": "container"},
                        {"fault_type": "container packet loss", "component": "c2", "t_gt": START + 9500,
                         "level": "container"}]},
            {"group_id": "W02", "case_ids": ["c"], "fault_types": ["container write I/O load"],
             "reference_complete": True,
             "faults": [{"fault_type": "container write I/O load", "component": "c2", "t_gt": START + 14700,
                         "level": "container"}]}]

    def _verdict(self, l2a, refs=None):
        results = l2b.evaluate_all(freeze=self.freeze, addendum=self.addendum, l2a=l2a,
                                   references=refs or self.refs)
        return results[0]

    def test_a_perfect_sample_is_verified_with_rules_tested_reported(self):
        res = self._verdict(_l2a({"W01": "positive", "W02": "negative"}))
        self.assertEqual(res["evaluation"]["verdict"], "VERIFICATA_OPERATIVAMENTE", res["evaluation"]["reasons"])
        self.assertEqual(res["evaluation"]["rules_tested"], 8)
        self.assertEqual(res["reference_component_status"], {"W01": {"c1": "in_popolazione"}})
        self.assertEqual(res["evaluation"]["parameters"], {"h_pre_seconds": 60, "h_seconds": 300})

    def test_a_false_negative_wins_over_coverage(self):
        res = self._verdict(_l2a({"W01": "negative", "W02": "negative"}))
        self.assertEqual(res["evaluation"]["verdict"], "NON_VERIFICATA")
        self.assertIn("false_negative", res["evaluation"]["reasons"])

    def test_a_false_positive_is_not_verified(self):
        res = self._verdict(_l2a({"W01": "positive", "W02": "positive"}))
        self.assertEqual(res["evaluation"]["verdict"], "NON_VERIFICATA")
        self.assertIn("false_positive", res["evaluation"]["reasons"])

    def test_a_detection_outside_the_time_window_is_not_localized(self):
        res = self._verdict(_l2a({"W01": "positive", "W02": "negative"},
                                 fires={"W01": {"c1": START + 7500 + 301}, "W02": {}}))
        self.assertEqual(res["evaluation"]["verdict"], "NON_VERIFICATA")
        self.assertIn("detected_but_not_localized_or_timed", res["evaluation"]["reasons"])

    def test_reference_outside_the_population_is_not_evaluable_and_explained(self):
        res = self._verdict(_l2a({"W01": "negative", "W02": "negative"}, population=("c2",), excluded=("c1", "c3")))
        self.assertEqual(res["evaluation"]["verdict"], "NON_VALUTABILE")
        self.assertEqual(res["evaluation"]["positives_not_observable"]["count"], 1)
        self.assertEqual(res["reference_component_status"], {"W01": {"c1": "escluso_per_kpi_mancante"}})

    def test_a_reference_component_unknown_to_the_telemetry_is_named_as_such(self):
        res = self._verdict(_l2a({"W01": "negative", "W02": "negative"}, population=("c2",), excluded=("c3",)))
        self.assertEqual(res["reference_component_status"], {"W01": {"c1": "assente_dalla_telemetria_del_livello"}})

    def test_low_negative_coverage_is_not_evaluable_with_the_frozen_threshold(self):
        other = {"fault_types": ["container write I/O load"], "reference_complete": True,
                 "faults": [{"fault_type": "container write I/O load", "component": "c2",
                             "t_gt": START + 14700, "level": "container"}]}
        refs = self.refs + [{"group_id": "W03", "case_ids": ["d"], **other},
                            {"group_id": "W04", "case_ids": ["e"], **other}]
        decisions = {"W01": "positive", "W02": "negative", "W03": "abstain", "W04": "abstain"}
        fires = {"W01": {"c1": START + 7500}, "W02": {}, "W03": {}, "W04": {}}
        res = self._verdict(_l2a(decisions, fires=fires), refs)
        self.assertEqual(res["evaluation"]["verdict"], "NON_VALUTABILE")
        self.assertIn("negative_coverage_below_exploratory_threshold", res["evaluation"]["reasons"])
        self.assertAlmostEqual(res["evaluation"]["coverage"]["negatives"], 1 / 3)

    def test_a_rule_class_outside_the_closed_taxonomy_is_refused(self):
        l2a = _l2a({"W01": "positive", "W02": "negative"})
        l2a["rules"][0]["target_fault_type"] = "classe inventata"
        with self.assertRaises(ValueError):
            self._verdict(l2a)

    def test_render_report(self):
        res = self._verdict(_l2a({"W01": "positive", "W02": "negative"}))
        report = l2b.build_report(freeze=self.freeze, addendum={**self.addendum, "sha256_of_body_without_this_field": "a" * 64,
                                                                "l2_code_commit": L2_COMMIT},
                                  l2a={"sha256_of_body_without_this_field": "b" * 64}, references=self.refs,
                                  results=[res], sources={"cloudbed-1": {"query_csv_sha256": "q", "record_csv_sha256": "r"}})
        text = l2b.render_report(report)
        for needle in ("VERDETTO: VERIFICATA_OPERATIVAMENTE", "regole provate: 8", "CAUTELA: cautela", "claim:"):
            self.assertIn(needle, text)
        self.assertNotIn("cloudbed-1_q", json.dumps(report["groups"]))      # niente associazione caso -> etichetta


class ChainTests(unittest.TestCase):
    def setUp(self):
        self.table, self.freeze, self.inputs = _fixture()
        self.addendum = l2x.build_addendum(**self.inputs)
        self.l2a = {"schema": "x", "addendum_sha256": self.addendum["sha256_of_body_without_this_field"],
                    "freeze_sha256": self.addendum["freeze_sha256"], "l2_code_commit": L2_COMMIT,
                    "uses_ground_truth": False, "ground_truth_opened": False,
                    "groups": self.addendum["groups"],
                    "rules": [{"rule_sha256": r["rule_sha256"]} for r in self.addendum["rules"]]}
        self.l2a["sha256_of_body_without_this_field"] = proto._sha(self.l2a)

    def _problems(self, **change):
        args = {"freeze": self.freeze, "addendum": self.addendum, "l2a": self.l2a, "changed_files": [],
                "manifest_sha256": "m" * 64} | change
        return l2b.verify_chain(**args)

    def _rehash(self, obj):
        obj.pop("sha256_of_body_without_this_field", None)
        obj["sha256_of_body_without_this_field"] = proto._sha(obj)
        return obj

    def test_a_consistent_chain_has_no_problems(self):
        self.assertEqual(self._problems(), [])

    def test_each_link_is_checked(self):
        tampered = copy.deepcopy(self.l2a)
        tampered["rules"][0]["rule_sha256"] = "0" * 64
        self.assertEqual(self._problems(l2a=tampered), ["decisioni_l2a_manomesse"])
        self.assertEqual(self._problems(changed_files=["docs/a.md", "src/tests/t.py"]), [])
        self.assertEqual(self._problems(changed_files=["src/evaluation/rq2_k_rule_executor.py"]),
                         ["file_cambiati_dopo_il_freeze: src/evaluation/rq2_k_rule_executor.py"])
        self.assertEqual(self._problems(l2a=self._rehash({**self.l2a, "l2_code_commit": "f" * 40})),
                         ["commit_l2_incoerente_con_l2a"])
        self.assertEqual(self._problems(manifest_sha256="x" * 64), ["manifest_diverso_dall_addendum"])
        gt = self._rehash({**{k: v for k, v in self.l2a.items()}, "uses_ground_truth": True})
        self.assertEqual(self._problems(l2a=gt), ["l2a_dichiara_uso_di_gt"])
        other = self._rehash({**self.l2a, "addendum_sha256": "0" * 64})
        self.assertEqual(self._problems(l2a=other), ["addendum_sha_non_coerente_con_l2a"])
        with mock.patch.object(l2x, "l2_sources_sha256", return_value={"rq2_k_l2_scoring.py": "0" * 64}):
            self.assertEqual(self._problems(), ["moduli_l2_diversi_dall_addendum"])
        with mock.patch.object(l2x, "loaders_sha256", return_value={"agent/tools.py": "0" * 64}):
            self.assertEqual(self._problems(), ["loader_diversi_dall_addendum"])


# ----------------------------------------------------------------------------------- CLI end-to-end
class CliTests(unittest.TestCase):
    """freeze -> run L1 -> addendum -> L2a -> L2b su un mini-archivio sintetico."""

    def setUp(self):
        l1t.CliSmokeTests.setUp(self)
        self.assertEqual(self._main_l1("freeze")[0], 0)
        self.assertEqual(self._main_l1("run")[0], 0)
        s = START
        self.sealed = [("cloudbed-1_q1", s + 7200, s + 9000), ("cloudbed-1_q2", s + 9000, s + 10800),
                       ("cloudbed-1_q3", s + 14400, s + 16200), ("cloudbed-1_q4", s + 21600, s + 23400)]
        rows = [{"case_id": c, "cloudbed": "cloudbed-1", "query_index": 0, "task_index": "task_3",
                 "instruction": "x", "start_unix": a, "end_unix": b} for c, a, b in
                [(c, START, START + 1800) for c in cat.DISCOVERY_CASES]]
        rows += [{"case_id": c, "cloudbed": "cloudbed-1", "query_index": int(c.split("_q")[1]), "task_index": "task_3",
                  "instruction": f"istruzione cloudbed-1 {c.split('_q')[1]}", "start_unix": a, "end_unix": b}
                 for c, a, b in self.sealed]
        pd.DataFrame(rows).to_csv(self.root / cat.MANIFEST_RELATIVE, index=False)
        jump = lambda t: 1000.0 if t < s + 7500 else 2000.0                          # noqa: E731
        telemetry = (_telemetry_rows("c1", START_TIME, s - 600, s + 23400, jump)
                     + _telemetry_rows("c2", START_TIME, s - 600, s + 23400, lambda t: 1000.0)
                     + _telemetry_rows("c3", "container_memory_usage_MB", s - 600, s + 23400, lambda t: 1.0))
        records = {1: (TARGET, "c1", s + 7500), 2: ("container packet loss", "c2", s + 9500),
                   3: ("container write I/O load", "c2", s + 14700), 4: ("node CPU spike", "node-1", s + 21900)}
        self.records = records
        zip_path = _reference_zip(self.root / "Market.zip", records)
        with zipfile.ZipFile(zip_path, "a") as archive:
            name = _get_telemetry_csv_paths(s - 600, s + 23400, "cloudbed-1", "container_metrics")[-1]
            archive.writestr(name, pd.DataFrame(telemetry, columns=cat.COLUMNS).to_csv(index=False))
        release = self.root / l2x.RELEASE_RELATIVE
        release.parent.mkdir(parents=True, exist_ok=True)
        release.write_text(json.dumps({"test_case_ids": [c for c, _, _ in self.sealed], "test_window_groups": 3}),
                           encoding="utf-8")
        self.changed = ["src/evaluation/rq2_k_l2_execute.py", "src/evaluation/rq2_k_l2_scoring.py", "docs/x.md"]

    def tearDown(self):
        l1t.CliSmokeTests.tearDown(self)

    def _main_l1(self, command):
        return l1t.CliSmokeTests._main(self, command)

    def _call(self, module, argv, commit=L2_COMMIT, changed=None):
        out = io.StringIO()
        with mock.patch("evaluation.rq2_v5_run_cli._plan_rows", return_value=(self.plan, self.rows)), \
                mock.patch.object(cat, "_git_head", return_value=commit), \
                mock.patch.object(l2x, "_git_changed_files", return_value=changed or self.changed), \
                contextlib.redirect_stdout(out):
            code = module.main(argv + ["--drive-root", str(self.root), "--repo-dir", str(self.root)])
        return code, out.getvalue()

    def _l2a(self, command="run", *extra):
        return self._call(l2x, [command, *extra])

    def test_full_chain_gives_a_verified_verdict_and_every_file_is_create_only(self):
        code, text = self._l2a("addendum")
        self.assertEqual(code, 0, text)
        self.assertIn("3 gruppi (release: 3)", text)
        code, text = self._l2a("run")
        self.assertEqual(code, 2)
        self.assertIn("--authorize-sealed-telemetry", text)
        self.assertFalse((self.root / l2x.L2A_RELATIVE).exists())
        code, text = self._l2a("run", "--authorize-sealed-telemetry")
        self.assertEqual(code, 0, text)
        decisions = json.loads((self.root / l2x.L2A_RELATIVE).read_text(encoding="utf-8"))["rules"][0]["decisions"]
        self.assertEqual(decisions, {"W01": "positive", "W02": "negative", "W03": "negative"})
        code, text = self._call(l2b, ["--authorize-ground-truth"])
        self.assertEqual(code, 0, text)
        self.assertIn("VERDETTO: VERIFICATA_OPERATIVAMENTE", text)
        report = json.loads((self.root / l2b.L2B_RELATIVE).read_text(encoding="utf-8"))
        self.assertTrue(report["uses_ground_truth"])
        for call in (lambda: self._l2a("addendum"), lambda: self._l2a("run", "--authorize-sealed-telemetry"),
                     lambda: self._call(l2b, ["--authorize-ground-truth"])):
            with self.assertRaises(FileExistsError):
                call()

    def test_l2b_needs_its_explicit_authorisation(self):
        self._l2a("addendum")
        self._l2a("run", "--authorize-sealed-telemetry")
        code, text = self._call(l2b, [])
        self.assertEqual(code, 2)
        self.assertFalse((self.root / l2b.L2B_RELATIVE).exists())

    def test_l2b_refuses_decisions_altered_after_l2a(self):
        self._l2a("addendum")
        self._l2a("run", "--authorize-sealed-telemetry")
        path = self.root / l2x.L2A_RELATIVE
        data = json.loads(path.read_text(encoding="utf-8"))
        data["rules"][0]["decisions"]["W01"] = "negative"
        path.write_text(json.dumps(data), encoding="utf-8")
        code, text = self._call(l2b, ["--authorize-ground-truth"])
        self.assertEqual(code, 2)
        self.assertIn("decisioni_l2a_manomesse", text)
        self.assertFalse((self.root / l2b.L2B_RELATIVE).exists())

    def test_a_failed_chain_never_reads_the_ground_truth(self):
        self._l2a("addendum")
        self._l2a("run", "--authorize-sealed-telemetry")
        path = self.root / l2x.L2A_RELATIVE
        data = json.loads(path.read_text(encoding="utf-8"))
        data["rules"][0]["decisions"]["W01"] = "negative"
        path.write_text(json.dumps(data), encoding="utf-8")
        with mock.patch.object(l2b, "read_reference_sources", side_effect=AssertionError("GT letta")) as spy:
            code, _ = self._call(l2b, ["--authorize-ground-truth"])
        self.assertEqual(code, 2)
        spy.assert_not_called()

    def test_run_refuses_changed_loaders_or_a_different_release_but_not_a_docs_commit(self):
        self._l2a("addendum")
        with mock.patch.object(l2x, "loaders_sha256", return_value={"agent/tools.py": "0" * 64}):
            code, text = self._call(l2x, ["run", "--authorize-sealed-telemetry"])
        self.assertEqual(code, 2)
        self.assertIn("loaders_sha256_diverso", text)
        self.assertFalse((self.root / l2x.L2A_RELATIVE).exists())
        release = self.root / l2x.RELEASE_RELATIVE
        release.write_text(json.dumps({"test_case_ids": [c for c, _, _ in self.sealed], "test_window_groups": 3,
                                       "nota": "modificato"}), encoding="utf-8")
        code, text = self._l2a("run", "--authorize-sealed-telemetry")
        self.assertEqual(code, 2)
        self.assertIn("release_sha256_diverso", text)

    def test_a_later_docs_commit_does_not_block_l2a_and_is_recorded(self):
        self._l2a("addendum")
        code, text = self._call(l2x, ["run", "--authorize-sealed-telemetry"], commit="f" * 40)
        self.assertEqual(code, 0, text)
        report = json.loads((self.root / l2x.L2A_RELATIVE).read_text(encoding="utf-8"))
        self.assertEqual(report["run_head_commit"], "f" * 40)
        self.assertEqual(report["l2_code_commit"], L2_COMMIT)
        code, text = self._call(l2b, ["--authorize-ground-truth"], commit="f" * 40)
        self.assertEqual(code, 0, text)

    def test_changes_to_frozen_code_after_the_freeze_block_everything(self):
        code, text = self._l2a("addendum", "--no-write") if False else self._call(
            l2x, ["addendum"], changed=self.changed + ["src/evaluation/rq2_k_rule_executor.py"])
        self.assertEqual(code, 2)
        self.assertIn("file_cambiati_dopo_il_freeze", text)
        self.assertFalse((self.root / l2x.ADDENDUM_RELATIVE).exists())

    def test_a_wrong_group_count_blocks_the_addendum(self):
        release = self.root / l2x.RELEASE_RELATIVE
        release.write_text(json.dumps({"test_case_ids": [c for c, _, _ in self.sealed], "test_window_groups": 4}),
                           encoding="utf-8")
        with self.assertRaises(l2x.L2ScopeError):
            self._l2a("addendum")
        self.assertFalse((self.root / l2x.ADDENDUM_RELATIVE).exists())

    def test_no_write_flag_writes_nothing(self):
        self.assertEqual(self._l2a("addendum", "--no-write")[0], 0)
        self.assertFalse((self.root / l2x.ADDENDUM_RELATIVE).exists())


if __name__ == "__main__":
    unittest.main()
