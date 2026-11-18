"""Test offline di L1/L2 applicati alle candidate D->K (dati sintetici, nessuna API, nessun dato reale).

L'ambiente sintetico e' quello dei test L1/L2 congelati: freeze, report L1, addendum, L2a e L2b del
"run con C" sono prodotti prima; poi si scrivono i K senza causa e si lanciano i nuovi comandi.
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest import mock

import test_rq2_k_l1_protocol_offline as l1t
import test_rq2_k_l2_offline as l2t
from evaluation import rq2_dk_ablation as dk
from evaluation import rq2_dk_l1_l2 as mod
from evaluation import rq2_k_catalog as cat
from evaluation import rq2_k_l1_preflight as pf
from evaluation import rq2_k_l1_protocol as proto
from evaluation import rq2_k_l2_execute as l2x
from evaluation import rq2_k_l2_scoring as l2b
from evaluation import rq2_v5_matrix_runner as mr

DK_COMMIT = "d" * 40
ABSTAIN = {"status": "insufficient_evidence", "reason": "dati insufficienti"}


def _restart_rule(name="riavvio_container"):
    return {"schema_version": "rq2_candidate_rule_v0", "status": "candidate", "combination": "all",
            "rule_name": name, "hypothesized_fault_type": "container process termination",
            "conditions": [l1t._cond(l1t.START_TIME)], "pseudocode": "ignorato"}


def _service_rule():
    return {"schema_version": "rq2_candidate_rule_v0", "status": "candidate", "combination": "all",
            "rule_name": "latenza_servizio", "hypothesized_fault_type": "container packet loss",
            "conditions": [l1t._cond("mrt_max", aggregation="max", unit="ms")], "pseudocode": "ignorato"}


class DKL1L2Base(unittest.TestCase):
    """Ambiente sintetico completo: run congelato (freeze, L1, addendum, L2a, L2b) piu' i K senza causa."""

    _call = l2t.CliTests._call
    _l2a = l2t.CliTests._l2a
    _main_l1 = l2t.CliTests._main_l1
    tearDown = l2t.CliTests.tearDown

    outcomes = {"m1": _restart_rule(), "m2": _service_rule(), "m3": ABSTAIN}

    def setUp(self):
        l2t.CliTests.setUp(self)
        self.assertEqual(self._l2a("addendum")[0], 0)
        self.assertEqual(self._l2a("run", "--authorize-sealed-telemetry")[0], 0)
        self.assertEqual(self._call(l2b, ["--authorize-ground-truth"])[0], 0)
        base = self.rows[2]
        self.k_rows = [{**base, "stage_id": f"plan:case-1:{m}:A1:K", "logical_model": m,
                        "depends_on": [f"plan:case-1:{m}:A1:D", f"plan:case-1:{m}:A1:C"]}
                       for m in ("m1", "m2", "m3")]
        self._write_dk(self.outcomes)

    def _write_dk(self, outcomes):
        store = mr.StageStore(self.root / dk.NAMESPACE)
        for row in self.k_rows:
            claim = store.claim(row["stage_id"], {**mr._identity(row), "source_commit": "x" * 40})
            store.write_record(row["stage_id"], {
                **mr._identity(row), "status": mr.STATUS_COMPLETE,
                "receipt": {"artifact": {"raw_response": json.dumps(outcomes[row["logical_model"]])}},
                "format": None, "error_summary": None, "blocked_by": None,
                "provenance": {"variant": "K_NO_CAUSE", "system_prompt_sha256": dk.K_NO_CAUSE_SYSTEM_SHA256},
                "claim_sha256": claim["claim_sha256"], "started_at_utc": "t", "finished_at_utc": "t",
                "elapsed_seconds": 1.0, "source_commit": "x" * 40})

    def _dk(self, argv, commit=DK_COMMIT):
        out = io.StringIO()
        with mock.patch.object(dk, "build_dk_plan", return_value=({"preview_sha256": "p" * 64}, self.k_rows)), \
                mock.patch.object(cat, "_git_head", return_value=commit), contextlib.redirect_stdout(out):
            code = mod.main(argv + ["--drive-root", str(self.root), "--repo-dir", str(self.root)])
        return code, out.getvalue()

    @property
    def out(self) -> Path:
        return self.root / mod.OUT_RELATIVE

    def _l1_report(self):
        return json.loads((self.out / mod.L1_FILE).read_text(encoding="utf-8"))


class LoadEntriesTests(DKL1L2Base):
    def _load(self):
        return mod.load_dk_entries(self.root / dk.NAMESPACE, self.k_rows)

    def test_reads_the_records_and_reports_the_integrity(self):
        entries, integrity = self._load()
        self.assertTrue(integrity["ok"], integrity["problems"])
        self.assertEqual(integrity["records_found"], 3)
        self.assertEqual(integrity["statuses"], {"RECORDED_COMPLETE": 3})
        self.assertEqual(mod.k_outcome_counts(entries), {"candidate": 2, "insufficient_evidence": 1})

    def test_the_fingerprint_does_not_depend_on_the_order_of_the_rows(self):
        _, a = self._load()
        _, b = mod.load_dk_entries(self.root / dk.NAMESPACE, list(reversed(self.k_rows)))
        self.assertEqual(a["records_fingerprint_sha256"], b["records_fingerprint_sha256"])

    def test_a_missing_record_is_a_problem(self):
        mr.StageStore(self.root / dk.NAMESPACE)._record_path(self.k_rows[0]["stage_id"]).unlink()
        _, integrity = self._load()
        self.assertFalse(integrity["ok"])
        self.assertTrue(any("record_assente" in p for p in integrity["problems"]))

    def test_an_altered_record_is_a_problem_and_never_raises(self):
        path = mr.StageStore(self.root / dk.NAMESPACE)._record_path(self.k_rows[0]["stage_id"])
        data = json.loads(path.read_text(encoding="utf-8"))
        data["elapsed_seconds"] = 99.0
        path.write_text(json.dumps(data), encoding="utf-8")
        _, integrity = self._load()
        self.assertFalse(integrity["ok"])
        self.assertTrue(any("StoreCorrupt" in p for p in integrity["problems"]))

    def test_a_record_that_is_not_a_k_without_cause_is_refused(self):
        path = mr.StageStore(self.root / dk.NAMESPACE)._record_path(self.k_rows[1]["stage_id"])
        data = json.loads(path.read_text(encoding="utf-8"))
        data["provenance"]["variant"] = "K_CON_CAUSA"
        data["record_sha256"] = mr._sha({k: v for k, v in data.items() if k != "record_sha256"})
        path.write_text(json.dumps(data), encoding="utf-8")
        _, integrity = self._load()
        self.assertTrue(any("non_e_un_K_senza_causa" in p for p in integrity["problems"]))

    def test_a_missing_store_is_an_error_not_a_new_folder(self):
        with self.assertRaises(mr.StoreError):
            mod.load_dk_entries(self.root / "non_esiste", self.k_rows)
        self.assertFalse((self.root / "non_esiste").exists())


class FrozenCodeTests(DKL1L2Base):
    def setUp(self):
        super().setUp()
        self.freeze = json.loads((self.root / proto.FREEZE_RELATIVE).read_text(encoding="utf-8"))
        self.addendum = json.loads((self.root / l2x.ADDENDUM_RELATIVE).read_text(encoding="utf-8"))

    def test_the_real_frozen_modules_match_the_freeze_and_the_addendum(self):
        self.assertEqual(mod.frozen_code_problems(self.freeze, self.addendum), [])

    def test_a_different_frozen_source_is_named(self):
        altered = dict(proto.sources_sha256())
        altered["rq2_k_rule_executor.py"] = "0" * 64
        with mock.patch.object(proto, "sources_sha256", return_value=altered):
            problems = mod.frozen_code_problems(self.freeze, self.addendum)
        self.assertTrue(any("rq2_k_rule_executor.py" in p for p in problems), problems)

    def test_different_parameters_or_semantic_table_or_l2_modules_are_named(self):
        with mock.patch.object(proto, "parameters_sha256", return_value="0" * 64):
            self.assertIn("parametri_diversi_dal_freeze", mod.frozen_code_problems(self.freeze))
        with mock.patch.object(pf, "semantic_table_sha256", return_value="0" * 64):
            self.assertIn("tabella_semantica_diversa_dal_freeze", mod.frozen_code_problems(self.freeze))
        with mock.patch.object(l2x, "l2_sources_sha256", return_value={}):
            self.assertIn("moduli_L2_diversi_dall_addendum", mod.frozen_code_problems(self.freeze, self.addendum))
        with mock.patch.object(l2x, "loaders_sha256", return_value={}):
            self.assertIn("loader_diversi_dall_addendum", mod.frozen_code_problems(self.freeze, self.addendum))

    def test_a_tampered_freeze_is_detected(self):
        self.freeze["rules_tested"] = 99
        self.assertIn("freeze_manomesso", mod.frozen_code_problems(self.freeze))


class PureFunctionTests(unittest.TestCase):
    def _c(self, sid, outcome, executable=False, eligible=False, admitted=False, sha="a"):
        return {"stage_id": sid, "case_id": "q", "model": "m", "harness": "A0", "rule_name": "r",
                "rule_sha256": sha * 64, "l1_outcome": outcome, "executable": executable,
                "eligible_for_l2": eligible, "admitted": admitted}

    def test_side_counts_separate_the_l1_levels(self):
        cands = [self._c("a", pf.NOT_FORMALIZABLE), self._c("b", pf.NOT_FORMALIZABLE),
                 self._c("c", pf.NOT_CLASSIFIABLE, executable=True),
                 self._c("d", pf.FORMALIZABLE, executable=True, eligible=True, admitted=True)]
        counts = mod.side_counts(cands)
        self.assertEqual(counts, {"candidates": 4, "non_formalizzabili": 2, "eseguibili": 2,
                                  "non_classificabili": 1, "formalizzabili": 1, "ammissibili_a_L2": 1,
                                  "ammesse_a_L2": 1})

    def test_overlap_distinguishes_same_cell_same_rule_and_other_cell(self):
        frozen = [self._c("s1", pf.NOT_FORMALIZABLE, sha="a"), self._c("s2", pf.NOT_FORMALIZABLE, sha="b")]
        ablated = [self._c("s1", pf.NOT_FORMALIZABLE, sha="a"),       # stessa cella, stessa regola
                   self._c("s3", pf.NOT_FORMALIZABLE, sha="b"),       # cella nuova, regola gia' vista altrove
                   self._c("s4", pf.NOT_FORMALIZABLE, sha="c")]       # tutto nuovo
        result = mod.overlap(frozen, ablated)
        self.assertEqual(result["celle_candidate_in_entrambi"], 1)
        self.assertEqual(result["regole_identiche"], 2)
        flags = {c["stage_id"]: (c["candidata_anche_nel_run_con_C"], c["stessa_regola_della_stessa_cella"],
                                 c["stessa_regola_in_altra_cella"]) for c in result["cells"]}
        self.assertEqual(flags, {"s1": (True, True, False), "s3": (False, False, True), "s4": (False, False, False)})

    def test_l2_summary_of_nothing_is_empty(self):
        self.assertEqual(mod.l2_results_summary(None), [])

    def test_the_hash_of_a_report_covers_its_body(self):
        body = {"a": 1}
        report = {**body, "sha256_of_body_without_this_field": proto._sha(body)}
        self.assertTrue(mod.report_is_intact(report))
        report["a"] = 2
        self.assertFalse(mod.report_is_intact(report))

    def test_the_module_does_not_import_the_ground_truth_side_at_top_level(self):
        source = Path(mod.__file__).read_text(encoding="utf-8")
        top = [n for n in ast.parse(source).body if isinstance(n, (ast.Import, ast.ImportFrom))]
        names = {a.name for n in top for a in n.names} | {getattr(n, "module", None) or "" for n in top}
        self.assertFalse(any("rq2_k_l2_scoring" in name for name in names), names)
        self.assertIn("from evaluation import rq2_k_l2_scoring as l2b", source)       # solo dentro cmd_l2b

    def test_the_frozen_l2b_path_is_the_real_one(self):
        self.assertEqual(mod.FROZEN_L2B_RELATIVE, l2b.L2B_RELATIVE)


class L1Tests(DKL1L2Base):
    def test_l1_classifies_runs_and_is_create_only(self):
        code, text = self._dk(["l1"])
        self.assertEqual(code, 0, text)
        report = self._l1_report()
        self.assertTrue(mod.report_is_intact(report))
        self.assertFalse(report["uses_ground_truth"] or report["sealed_incidents_opened"])
        self.assertEqual(report["k_outcomes"], {"candidate": 2, "insufficient_evidence": 1})
        by_name = {c["rule_name"]: c for c in report["candidates"]}
        self.assertEqual(by_name["riavvio_container"]["l1_outcome"], pf.FORMALIZABLE)
        self.assertTrue(by_name["riavvio_container"]["admitted_to_l2"])
        self.assertEqual(by_name["latenza_servizio"]["l1_outcome"], pf.NOT_FORMALIZABLE)
        self.assertFalse(by_name["latenza_servizio"]["admitted_to_l2"])
        self.assertEqual(report["l1_report"]["admitted_to_l2"], [by_name["riavvio_container"]["stage_id"]])
        for needle in ("CONFRONTO L1", "CONFRONTO L2", "NON e' cieca", "AMMESSA A L2: True"):
            self.assertIn(needle, text)
        with self.assertRaises(FileExistsError):
            self._dk(["l1"])

    def test_the_derived_freeze_keeps_parameters_and_points_to_the_frozen_one(self):
        self._dk(["l1"])
        derived = self._l1_report()["derived_freeze"]
        frozen = json.loads((self.root / proto.FREEZE_RELATIVE).read_text(encoding="utf-8"))
        self.assertTrue(proto.freeze_is_intact(derived))
        self.assertEqual(derived["parameters"], frozen["parameters"])
        self.assertEqual(derived["parameters_sha256"], proto.parameters_sha256())
        self.assertEqual(derived["derived_from_freeze_sha256"], frozen["sha256_of_body_without_this_field"])
        self.assertEqual(derived["rules_tested"], 2)
        self.assertEqual(derived["rules_tested_both_pipelines"], 2 + frozen["rules_tested"])
        self.assertEqual(len(derived["l2_eligible"]), 1)

    def test_no_write_writes_nothing(self):
        code, _ = self._dk(["l1", "--no-write"])
        self.assertEqual(code, 0)
        self.assertFalse((self.out / mod.L1_FILE).exists())

    def test_l1_refuses_when_a_frozen_module_differs_and_writes_nothing(self):
        altered = dict(proto.sources_sha256())
        altered["rq2_k_l1_preflight.py"] = "0" * 64
        with mock.patch.object(proto, "sources_sha256", return_value=altered):
            code, text = self._dk(["l1"])
        self.assertEqual(code, 2)
        self.assertIn("sorgenti_L1_diversi_dal_freeze", text)
        self.assertFalse((self.out / mod.L1_FILE).exists())

    def test_l1_refuses_a_different_catalog(self):
        path = self.root / proto.CATALOG_RELATIVE
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        code, text = self._dk(["l1"])
        self.assertEqual(code, 2)
        self.assertIn("catalogo_diverso_dal_freeze", text)

    def test_l1_refuses_altered_records(self):
        path = mr.StageStore(self.root / dk.NAMESPACE)._record_path(self.k_rows[0]["stage_id"])
        data = json.loads(path.read_text(encoding="utf-8"))
        data["elapsed_seconds"] = 7.0
        path.write_text(json.dumps(data), encoding="utf-8")
        code, text = self._dk(["l1"])
        self.assertEqual(code, 2)
        self.assertIn("NON INTEGRI", text)

    def test_l1_and_l2a_never_read_the_ground_truth(self):
        with mock.patch.object(l2b, "read_reference_sources", side_effect=AssertionError("GT letta")):
            self.assertEqual(self._dk(["l1"])[0], 0)
            self.assertEqual(self._dk(["l2a", "--authorize-sealed-telemetry"])[0], 0)


class L2Tests(DKL1L2Base):
    def setUp(self):
        super().setUp()
        self.assertEqual(self._dk(["l1"])[0], 0)

    def test_l2a_needs_its_authorisation(self):
        code, text = self._dk(["l2a"])
        self.assertEqual(code, 2)
        self.assertIn("--authorize-sealed-telemetry", text)
        self.assertFalse((self.out / mod.L2A_FILE).exists())

    def test_the_whole_chain_is_create_only_and_gives_the_same_verdict_as_the_same_rule(self):
        code, text = self._dk(["l2a", "--authorize-sealed-telemetry"])
        self.assertEqual(code, 0, text)
        addendum = json.loads((self.out / mod.ADDENDUM_FILE).read_text(encoding="utf-8"))
        frozen_addendum = json.loads((self.root / l2x.ADDENDUM_RELATIVE).read_text(encoding="utf-8"))
        self.assertTrue(l2x.addendum_is_intact(addendum))
        self.assertEqual(addendum["groups"], frozen_addendum["groups"])
        self.assertEqual(addendum["parameters"], frozen_addendum["parameters"])
        self.assertEqual(addendum["rules_tested"], 2)
        self.assertEqual([r["rule_name"] for r in addendum["rules"]], ["riavvio_container"])
        decisions = json.loads((self.out / mod.L2A_FILE).read_text(encoding="utf-8"))["rules"][0]["decisions"]
        self.assertEqual(decisions, {"W01": "positive", "W02": "negative", "W03": "negative"})
        code, text = self._dk(["l2b"])
        self.assertEqual(code, 2)
        self.assertFalse((self.out / mod.L2B_FILE).exists())
        code, text = self._dk(["l2b", "--authorize-ground-truth"])
        self.assertEqual(code, 0, text)
        self.assertIn("VERDETTO: VERIFICATA_OPERATIVAMENTE", text)
        self.assertIn("NON e' cieca", text)
        report = json.loads((self.out / mod.L2B_FILE).read_text(encoding="utf-8"))
        self.assertTrue(mod.report_is_intact(report))
        self.assertEqual(report["l2b"]["results"][0]["evaluation"]["verdict"], "VERIFICATA_OPERATIVAMENTE")
        self.assertEqual(report["rules_tested_both_pipelines"], 2 + 1)
        for argv in (["l2a", "--authorize-sealed-telemetry"], ["l2b", "--authorize-ground-truth"]):
            with self.assertRaises(FileExistsError):
                self._dk(argv)

    def test_compare_puts_the_two_pipelines_side_by_side(self):
        self._dk(["l2a", "--authorize-sealed-telemetry"])
        self._dk(["l2b", "--authorize-ground-truth"])
        code, text = self._dk(["compare"])
        self.assertEqual(code, 0, text)
        for needle in ("D->C->K (congelato)", "D->K (senza causa)", "CONFRONTO L2", "stato L2 D->K: eseguita"):
            self.assertIn(needle, text)
        frozen = json.loads((self.root / l2t.l2b.L2B_RELATIVE).read_text(encoding="utf-8"))
        self.assertIn(frozen["results"][0]["evaluation"]["verdict"], text)

    def test_l2b_refuses_decisions_altered_after_l2a_and_never_reads_the_ground_truth(self):
        self._dk(["l2a", "--authorize-sealed-telemetry"])
        path = self.out / mod.L2A_FILE
        data = json.loads(path.read_text(encoding="utf-8"))
        data["rules"][0]["decisions"]["W01"] = "negative"
        path.write_text(json.dumps(data), encoding="utf-8")
        with mock.patch.object(l2b, "read_reference_sources", side_effect=AssertionError("GT letta")):
            code, text = self._dk(["l2b", "--authorize-ground-truth"])
        self.assertEqual(code, 2)
        self.assertIn("decisioni_l2a_manomesse", text)
        self.assertFalse((self.out / mod.L2B_FILE).exists())

    def test_l2b_refuses_a_different_l1_report_or_addendum(self):
        self._dk(["l2a", "--authorize-sealed-telemetry"])
        path = self.out / mod.ADDENDUM_FILE
        data = json.loads(path.read_text(encoding="utf-8"))
        data["rules_tested"] = 99
        path.write_text(json.dumps(data), encoding="utf-8")
        with mock.patch.object(l2b, "read_reference_sources", side_effect=AssertionError("GT letta")):
            code, text = self._dk(["l2b", "--authorize-ground-truth"])
        self.assertEqual(code, 2)
        self.assertIn("addendum_derivato_manomesso", text)

    def test_l2a_refuses_when_the_records_changed_after_l1(self):
        path = mr.StageStore(self.root / dk.NAMESPACE)._record_path(self.k_rows[2]["stage_id"])
        data = json.loads(path.read_text(encoding="utf-8"))
        data["elapsed_seconds"] = 3.0
        path.write_text(json.dumps(data), encoding="utf-8")
        code, _ = self._dk(["l2a", "--authorize-sealed-telemetry"])
        self.assertEqual(code, 2)
        self.assertFalse((self.out / mod.ADDENDUM_FILE).exists())

    def test_l2a_refuses_when_the_l2_modules_differ_from_the_addendum(self):
        with mock.patch.object(l2x, "l2_sources_sha256", return_value={}):
            code, text = self._dk(["l2a", "--authorize-sealed-telemetry"])
        self.assertEqual(code, 2)
        self.assertIn("moduli_L2_diversi_dall_addendum", text)
        self.assertFalse((self.out / mod.ADDENDUM_FILE).exists())

    def test_no_write_writes_nothing(self):
        code, _ = self._dk(["l2a", "--authorize-sealed-telemetry", "--no-write"])
        self.assertEqual(code, 0)
        self.assertFalse((self.out / mod.ADDENDUM_FILE).exists() or (self.out / mod.L2A_FILE).exists())


class NothingAdmittedTests(DKL1L2Base):
    outcomes = {"m1": _service_rule(), "m2": ABSTAIN, "m3": ABSTAIN}

    def test_l2_is_not_applicable_and_writes_nothing(self):
        self.assertEqual(self._dk(["l1"])[0], 0)
        self.assertEqual(self._l1_report()["l1_report"]["admitted_to_l2"], [])
        code, text = self._dk(["l2a", "--authorize-sealed-telemetry"])
        self.assertEqual(code, 0)
        self.assertIn("L2 NON APPLICABILE", text)
        self.assertFalse((self.out / mod.ADDENDUM_FILE).exists())
        self.assertFalse((self.out / mod.L2A_FILE).exists())
        code, text = self._dk(["compare"])
        self.assertEqual(code, 0)
        self.assertIn("non_applicabile_nessuna_ammessa", text)

    def test_the_addendum_builder_refuses_an_empty_admission(self):
        self._dk(["l1"])
        report = self._l1_report()
        frozen_addendum = json.loads((self.root / l2x.ADDENDUM_RELATIVE).read_text(encoding="utf-8"))
        with self.assertRaises(mod.DKScopeError):
            mod.build_dk_addendum(derived=report["derived_freeze"], frozen_addendum=frozen_addendum,
                                  admitted=[], l1_report_sha256="x" * 64, l2_code_commit=DK_COMMIT)


class CliArgumentsTests(unittest.TestCase):
    def test_l1_and_l2a_require_repo_dir(self):
        for command in ("l1", "l2a"):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(mod.main([command, "--drive-root", "x"]), 2)

    def test_l2b_needs_its_authorisation_before_touching_anything(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(mod.main(["l2b", "--drive-root", "/non/esiste"]), 2)
        self.assertIn("--authorize-ground-truth", out.getvalue())


if __name__ == "__main__":
    unittest.main()
