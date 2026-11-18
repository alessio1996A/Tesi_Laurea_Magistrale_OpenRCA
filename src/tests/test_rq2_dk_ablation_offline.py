"""Test offline dell'ablazione D->K (senza LangChain, senza API, senza chiavi).

Dimostrano che: il prompt K senza causa differisce da quello congelato per UNA sola
frase; il pacchetto non contiene la causa ne' la risposta di D; il piano ha 60 stadi K;
l'archivio del run congelato non viene mai scritto; claim e record sono create-only;
uno stadio con D non completo viene bloccato senza chiamate; il confronto e' corretto.
"""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from evaluation import rq2_dk_ablation as dk
from evaluation import rq2_v5_matrix_runner as mr
from evaluation.rq2_probe_adapter import RULE_SYSTEM, ProbeInputError
from test_rq2_probe_adapter import INSTRUCTION, TOOLS, sample_run

K_PROMPT_SHA256 = (
    "7ffe92fab8e48230ef38e51ca8644b838a9f04788d8a7fa01c11401545446b63"
)


def _d_record(row, status=mr.STATUS_COMPLETE):
    """Record D sintetico del run 'congelato' (stessa forma usata dall'esecutore)."""
    return {
        "stage_id": dk.d_parent_id(row), "status": status,
        "receipt": {"artifact": {"diagnostic_run": sample_run()}},
    }


def _write_source(root: Path, rows, *, bad_d=()):
    """Crea un archivio 'congelato' con un record D per ogni riga K."""
    store = mr.StageStore(root)
    for row in rows:
        stem = row["stage_id"].rsplit(":", 1)[0]
        status = (mr.STATUS_PROVIDER_ERROR if row["stage_id"] in bad_d
                  else mr.STATUS_COMPLETE)
        store.write_record(stem + ":D", {
            **mr._identity({**row, "stage": "D"}), "status": status,
            "receipt": {"artifact": {"diagnostic_run": sample_run()}},
            "format": None, "provenance": None, "error_summary": None,
            "blocked_by": None, "claim_sha256": None,
        })
    return store


class FakeCall:
    """Chiamata finta al provider: restituisce un JSON di K con candidate o astensione."""

    def __init__(self, raw='{"status":"insufficient_evidence"}', error=None):
        self.raw, self.error, self.calls = raw, error, []

    def __call__(self, provider, model_id, payload):
        self.calls.append((provider, model_id, payload))
        return {"raw_response": None if self.error else self.raw,
                "provider_error": self.error, "api_attempts": 1,
                "usage": {"total_tokens": 10}, "finish_reason": "stop",
                "elapsed_seconds": 0.1}


def _fake_normalize(**kwargs):
    call = kwargs["call"]
    status = ("PROVIDER_ERROR" if call.get("provider_error")
              else "RECORDED_COMPLETE")
    return {"stage_id": kwargs["stage_id"], "status": status,
            "artifact": {"raw_response": call.get("raw_response")}}


def _executor(call, sleep=lambda s: None):
    return dk.DKExecutor(
        data_dir=Path("."), sleep=sleep, call_fn=call,
        normalize_fn=_fake_normalize,
        instruction_fn=lambda data_dir, case_id: INSTRUCTION)


def _tree(root: Path):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


class PromptAndPackageTests(unittest.TestCase):
    def test_prompt_differs_from_frozen_rule_system_by_one_sentence(self):
        self.assertNotEqual(dk.K_NO_CAUSE_SYSTEM, RULE_SYSTEM)
        restored = dk.K_NO_CAUSE_SYSTEM.replace(
            dk._NO_CAUSE_SENTENCE, dk._CAUSE_SENTENCE)
        self.assertEqual(restored, RULE_SYSTEM)
        self.assertNotIn("cause\nprobe", dk.K_NO_CAUSE_SYSTEM)
        self.assertNotIn("previously frozen", dk.K_NO_CAUSE_SYSTEM)

    def test_prompt_hash_is_pinned(self):
        self.assertEqual(dk.K_NO_CAUSE_SYSTEM_SHA256, K_PROMPT_SHA256)

    def test_package_has_no_cause_and_no_d_answer(self):
        package = dk.prepare_k_no_cause(
            original_instruction=INSTRUCTION, diagnostic_run=sample_run(),
            phase="discovery", allowed_tool_names=TOOLS)
        text = json.dumps(package)
        self.assertEqual(package["stage"], dk.K_STAGE_NAME)
        self.assertNotIn("unverified_model_cause_probe", text)
        self.assertNotIn("untrusted_diagnosis", text)
        self.assertEqual(package["system_prompt_sha256"], K_PROMPT_SHA256)
        self.assertFalse(package["ready_for_api"])
        self.assertEqual(package["model_api_calls"], 0)
        self.assertIn("E001", package["messages"][1]["content"])

    def test_package_is_deterministic(self):
        kwargs = dict(original_instruction=INSTRUCTION, phase="discovery",
                      allowed_tool_names=TOOLS)
        a = dk.prepare_k_no_cause(diagnostic_run=sample_run(), **kwargs)
        b = dk.prepare_k_no_cause(diagnostic_run=copy.deepcopy(sample_run()),
                                  **kwargs)
        self.assertEqual(a, b)

    def test_k_is_refused_outside_discovery_and_with_failed_d(self):
        with self.assertRaises(ProbeInputError):
            dk.prepare_k_no_cause(
                original_instruction=INSTRUCTION, diagnostic_run=sample_run(),
                phase="test", allowed_tool_names=TOOLS)
        failed = sample_run()
        failed["error"] = "boom"
        with self.assertRaises(ProbeInputError):
            dk.prepare_k_no_cause(
                original_instruction=INSTRUCTION, diagnostic_run=failed,
                phase="discovery", allowed_tool_names=TOOLS)


class PlanTests(unittest.TestCase):
    def test_plan_is_the_60_k_stages(self):
        _, rows = dk.build_dk_plan()
        self.assertEqual(len(rows), 60)
        self.assertEqual({r["stage"] for r in rows}, {"K"})
        self.assertEqual({r["logical_model"] for r in rows},
                         {"gemini", "sonnet", "haiku"})
        self.assertEqual(len({r["case_id"] for r in rows}), 4)
        self.assertEqual(len({r["harness"] for r in rows}), 5)

    def test_parent_ids_point_to_d_and_c(self):
        _, rows = dk.build_dk_plan()
        row = rows[0]
        self.assertTrue(dk.d_parent_id(row).endswith(":D"))
        self.assertTrue(dk.c_parent_id(row).endswith(":C"))


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        _, self.rows = dk.build_dk_plan()
        self.rows = self.rows[:3]
        self.source_root = base / "frozen"
        self.out_root = base / "ablation"
        self.source_store = _write_source(self.source_root, self.rows)
        self.source = dk.SourceDRecords(self.source_root)
        self.store = mr.StageStore(self.out_root)

    def test_source_is_never_written(self):
        before = _tree(self.source_root)
        call = FakeCall()
        dk.run_dk_matrix(self.rows, source=self.source, store=self.store,
                         executor=_executor(call), log=lambda *_: None)
        self.assertEqual(_tree(self.source_root), before)
        self.assertEqual(len(call.calls), 3)

    def test_records_carry_ablation_provenance_and_protocol(self):
        dk.run_dk_matrix(self.rows, source=self.source, store=self.store,
                         executor=_executor(FakeCall()), log=lambda *_: None)
        record = self.store.load_record(self.rows[0]["stage_id"])
        self.assertEqual(record["protocol"], dk.PROTOCOL)
        self.assertEqual(record["status"], mr.STATUS_COMPLETE)
        prov = record["provenance"]
        self.assertEqual(prov["variant"], "K_NO_CAUSE")
        self.assertEqual(prov["system_prompt_sha256"], K_PROMPT_SHA256)
        d = self.source.load(dk.d_parent_id(self.rows[0]))
        self.assertEqual(prov["source_d_record_sha256"], d["record_sha256"])

    def test_the_prompt_sent_to_the_model_has_no_cause(self):
        call = FakeCall()
        dk.run_dk_matrix(self.rows[:1], source=self.source, store=self.store,
                         executor=_executor(call), log=lambda *_: None)
        payload = call.calls[0][2]
        self.assertEqual(payload[0]["content"], dk.K_NO_CAUSE_SYSTEM)
        self.assertNotIn("unverified_model_cause_probe", payload[1]["content"])

    def test_rerun_does_not_call_again(self):
        call = FakeCall()
        run = lambda: dk.run_dk_matrix(  # noqa: E731
            self.rows, source=self.source, store=self.store,
            executor=_executor(call), log=lambda *_: None)
        first, second = run(), run()
        self.assertEqual(first["executed"], 3)
        self.assertEqual(second["executed"], 0)
        self.assertEqual(second["actions"], {mr.ACTION_ALREADY: 3})
        self.assertEqual(len(call.calls), 3)

    def test_orphan_claim_is_never_rerun(self):
        row = self.rows[0]
        self.store.claim(row["stage_id"], {"protocol": dk.PROTOCOL})
        call = FakeCall()
        action = dk.run_dk_stage(row, source=self.source, store=self.store,
                                 executor=_executor(call), log=lambda *_: None)
        self.assertEqual(action, mr.ACTION_ORPHAN)
        self.assertEqual(call.calls, [])

    def test_failed_d_blocks_k_without_calls(self):
        bad = self.rows[0]["stage_id"]
        root = Path(self._tmp.name) / "frozen_bad"
        _write_source(root, self.rows, bad_d={bad})
        call = FakeCall()
        action = dk.run_dk_stage(
            self.rows[0], source=dk.SourceDRecords(root), store=self.store,
            executor=_executor(call), log=lambda *_: None)
        self.assertEqual(action, mr.ACTION_BLOCKED)
        self.assertEqual(call.calls, [])
        record = self.store.load_record(bad)
        self.assertEqual(record["status"], mr.STATUS_BLOCKED)
        self.assertEqual(record["protocol"], dk.PROTOCOL)

    def test_missing_d_waits(self):
        empty = Path(self._tmp.name) / "frozen_empty"
        mr.StageStore(empty)
        call = FakeCall()
        action = dk.run_dk_stage(
            self.rows[0], source=dk.SourceDRecords(empty), store=self.store,
            executor=_executor(call), log=lambda *_: None)
        self.assertEqual(action, mr.ACTION_WAITING)
        self.assertEqual(call.calls, [])

    def test_missing_source_archive_is_an_error(self):
        with self.assertRaises(mr.StoreError):
            dk.SourceDRecords(Path(self._tmp.name) / "inesistente")

    def test_prepare_failure_stops_the_batch_without_claim(self):
        def broken(data_dir, case_id):
            raise RuntimeError("manifest assente")
        executor = dk.DKExecutor(
            data_dir=Path("."), call_fn=FakeCall(),
            normalize_fn=_fake_normalize, instruction_fn=broken)
        outcome = dk.run_dk_matrix(
            self.rows, source=self.source, store=self.store,
            executor=executor, log=lambda *_: None)
        self.assertEqual(outcome["stopped"], "prepare_failed")
        self.assertIsNone(self.store.load_claim(self.rows[0]["stage_id"]))

    def test_transport_error_is_retried_once(self):
        results = iter([
            {"raw_response": None, "provider_error": "PROVIDER_ERROR: 503",
             "api_attempts": 1, "usage": None, "finish_reason": None,
             "elapsed_seconds": 0.1},
            {"raw_response": '{"status":"insufficient_evidence"}',
             "provider_error": None, "api_attempts": 1,
             "usage": {"total_tokens": 5}, "finish_reason": "stop",
             "elapsed_seconds": 0.1},
        ])
        sleeps = []
        executor = dk.DKExecutor(
            data_dir=Path("."), sleep=sleeps.append,
            call_fn=lambda *a: next(results), normalize_fn=_fake_normalize,
            instruction_fn=lambda d, c: INSTRUCTION)
        dk.run_dk_stage(self.rows[0], source=self.source, store=self.store,
                        executor=executor, log=lambda *_: None)
        record = self.store.load_record(self.rows[0]["stage_id"])
        self.assertEqual(record["status"], mr.STATUS_COMPLETE)
        self.assertEqual(len(record["provenance"]["retry"]["attempts"]), 2)
        self.assertEqual(len(sleeps), 1)

    def test_rejected_receipt_is_recorded_not_retried(self):
        def reject(**kwargs):
            raise ValueError("ricevuta non conforme")
        call = FakeCall()
        executor = dk.DKExecutor(
            data_dir=Path("."), call_fn=call, normalize_fn=reject,
            instruction_fn=lambda d, c: INSTRUCTION)
        dk.run_dk_stage(self.rows[0], source=self.source, store=self.store,
                        executor=executor, log=lambda *_: None)
        record = self.store.load_record(self.rows[0]["stage_id"])
        self.assertEqual(record["status"], mr.STATUS_RECEIPT_REJECTED)
        self.assertEqual(len(call.calls), 1)
        self.assertEqual(record["error_summary"]["code"], "V4_RECEIPT_REJECTED")


class CompareTests(unittest.TestCase):
    def test_compare_counts_with_and_without_cause(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _, rows = dk.build_dk_plan()
            rows = rows[:2]
            source_store = _write_source(base / "frozen", rows)
            for row, raw in zip(rows, (
                    '{"status":"candidate"}',
                    '{"status":"insufficient_evidence"}')):
                source_store.write_record(row["stage_id"], {
                    **mr._identity(row), "status": mr.STATUS_COMPLETE,
                    "receipt": {"artifact": {"raw_response": raw}},
                    "format": None, "provenance": None,
                    "error_summary": None, "blocked_by": None,
                    "claim_sha256": None})
            store = mr.StageStore(base / "ablation")
            dk.run_dk_matrix(
                rows, source=dk.SourceDRecords(base / "frozen"), store=store,
                executor=_executor(FakeCall()), log=lambda *_: None)
            result = dk.compare_with_frozen(
                rows, source=dk.SourceDRecords(base / "frozen"), store=store)
            self.assertEqual(
                [c["with_cause"] for c in result["cells"]],
                ["candidate", "insufficient_evidence"])
            self.assertEqual(
                [c["without_cause"] for c in result["cells"]],
                ["insufficient_evidence", "insufficient_evidence"])
            total = sum(v for m in result["by_model"].values()
                        for v in m["with_cause"].values())
            self.assertEqual(total, 2)


if __name__ == "__main__":
    unittest.main()
