"""Test offline dell'audit di sola lettura del run (record sintetici)."""
import json
import tempfile
import unittest
from pathlib import Path

from evaluation import rq2_k_run_audit as aud


def _rec(stage_id, status="RECORDED_COMPLETE", deviation="NONE", attempts=None,
         error_summary=None, original=None, blocked_by=None):
    prov = {"retry": {"attempts": attempts}} if attempts else {}
    return {"stage_id": stage_id, "status": status, "provenance": prov,
            "format": {"deviation": deviation, "original_response": original},
            "error_summary": error_summary, "blocked_by": blocked_by}


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            _rec("c1:gemini:A0:D"),
            _rec("c1:gemini:A1:D", attempts=[
                {"attempt": 1, "status": "PROVIDER_ERROR", "error_type": "ServerError", "elapsed_seconds": 3.0},
                {"attempt": 2, "status": "RECORDED_COMPLETE", "error_type": None, "elapsed_seconds": 40.0}]),
            _rec("c1:haiku:A1:K", status="INVALID_OUTPUT", error_summary="schema non valido",
                 original="x" * 1000),
            _rec("c1:haiku:A0:K", deviation="SINGLE_JSON_FENCE"),
            _rec("c1:haiku:A1:C", status="BLOCKED_DEPENDENCY", blocked_by=["c1:haiku:A1:D"]),
        ]

    def test_counts_retries_and_non_complete(self):
        report = aud.audit(self.records)
        self.assertEqual(report["records"], 5)
        self.assertEqual(report["status"]["RECORDED_COMPLETE"], 3)
        self.assertEqual(len(report["retried"]), 1)
        retried = report["retried"][0]
        self.assertEqual(retried["final_status"], "RECORDED_COMPLETE")
        self.assertEqual([a["status"] for a in retried["attempts"]],
                         ["PROVIDER_ERROR", "RECORDED_COMPLETE"])
        self.assertEqual({e["status"] for e in report["non_complete"]},
                         {"INVALID_OUTPUT", "BLOCKED_DEPENDENCY"})
        self.assertEqual(report["format_deviation_by_model"]["haiku"]["SINGLE_JSON_FENCE"], 1)

    def test_long_text_is_clipped_not_dumped(self):
        report = aud.audit(self.records)
        item = next(e for e in report["non_complete"] if e["status"] == "INVALID_OUTPUT")
        self.assertLess(len(item["original_response"]), 500)
        self.assertIn("[...]", item["original_response"])

    def test_render_and_load_do_not_modify_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i, rec in enumerate(self.records):
                (Path(tmp) / f"V5_RECORD_{i}.json").write_text(json.dumps(rec), encoding="utf-8")
            before = {p.name: p.read_bytes() for p in Path(tmp).iterdir()}
            text = aud.render(aud.audit(aud.load_records(Path(tmp))))
            after = {p.name: p.read_bytes() for p in Path(tmp).iterdir()}
        self.assertEqual(before, after)
        self.assertIn("Stage ritentati: 1", text)
        self.assertIn("Stage non completi: 2", text)


if __name__ == "__main__":
    unittest.main()
