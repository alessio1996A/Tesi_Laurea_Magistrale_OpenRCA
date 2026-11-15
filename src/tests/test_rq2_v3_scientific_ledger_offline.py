"""Targeted V3 ledger tests: TemporaryDirectory only, no API/GT/Colab.

Source verification is explicitly MOCKED only within this test module.
Production has no V3 source-release verifier yet and therefore fails closed.
Do not re-run the preceding 83 adapter/extractor tests as part of this gate.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.rq2_v2_unified_scientific_ledger import _canonical, _sha
from evaluation.rq2_v3_scientific_ledger import (
    RELEASE_SCHEMA, V3ScientificLedger, V3ScientificLedgerBlocked,
)
from evaluation.rq2_v3_scientific_receipt_adapter_candidate import (
    normalize_v3_d_capture, normalize_v3_ck_call,
)
from evaluation.rq2_v3_unified_gtfree_discovery_plan import (
    VERSION as PROTOCOL, NAMESPACE, RELEASE_FILE,
    build_offline_v3_discovery_plan,
)
from test_rq2_v3_scientific_receipt_adapter_candidate_offline import (
    sid, source_d, capture, ck_call, cause, rule,
)

GEMINI_MODEL_ID = build_offline_v3_discovery_plan()["model_ids"]["gemini"]
PIN = "a" * 40
INVENTORY_SHA = "b" * 64


class V3ScientificLedgerOfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="V3_LEDGER_TEST_ONLY_")
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)
        self.repo = self.data / "isolated_repo"
        self.repo.mkdir()
        plan = build_offline_v3_discovery_plan()
        self.release = {
            "schema": RELEASE_SCHEMA,
            "protocol": PROTOCOL,
            "source_commit": PIN,
            "plan_sha256": plan["preview_sha256"],
            "scientific_namespace": NAMESPACE.as_posix(),
            "source_inventory_sha256": INVENTORY_SHA,
            "ood_test_cases_locked": plan["ood_test_cases_locked"],
            "can_run_ood_test": False,
            "can_execute_api": False,
        }
        self.sha = _sha(self.release)
        (self.data / NAMESPACE).mkdir(parents=True)
        (self.data / RELEASE_FILE).write_bytes(_canonical(self.release))
        self.git_patcher = patch(
            "evaluation.rq2_v3_scientific_ledger._repository_commit",
            return_value=(PIN, ""),
        )
        self.git_mock = self.git_patcher.start()
        self.addCleanup(self.git_patcher.stop)
        self.source_patcher = patch.object(
            V3ScientificLedger, "_source_release",
            return_value={
                "status": "V3_SOURCE_BOUND_RELEASE_VERIFIED",
                "source_commit": PIN,
                "release_sha256": self.sha,
                "source_inventory_sha256": INVENTORY_SHA,
                "plan_sha256": plan["preview_sha256"],
                "can_execute_api": False,
                "can_run_ood_test": False,
                "can_create_claim": False,
            },
        )
        self.source_mock = self.source_patcher.start()
        self.addCleanup(self.source_patcher.stop)
        self.ledger = self.new_ledger()

    def new_ledger(self):
        return V3ScientificLedger(
            data_dir=self.data, repo_dir=self.repo,
            expected_commit=PIN, approved_release_sha256=self.sha,
        )

    def auth(self, stage_id, model_id=GEMINI_MODEL_ID, budget="0.10"):
        return {
            "scope": "ONE_V3_STAGE_CLAIM_ONLY",
            "stage_id": stage_id,
            "model_id": model_id,
            "source_commit": PIN,
            "release_sha256": self.sha,
            "approval_reference": "TEST_ONLY_" + stage_id.rsplit(":", 1)[-1],
            "stage_budget_usd": budget,
        }

    def claim_and_record(self, stage_id, receipt, *, model_id=GEMINI_MODEL_ID):
        claim = self.ledger.claim_stage(
            stage_id=stage_id, model_id=model_id,
            stage_authorization=self.auth(stage_id, model_id),
        )
        record = self.ledger.record_stage(
            stage_id=stage_id, model_id=model_id, receipt=receipt,
            expected_claim_sha256=claim["claim_sha256"],
        )
        return self.ledger.load_record(stage_id=stage_id), record

    def d_receipt(self, run_dict=None):
        return normalize_v3_d_capture(
            stage_id=sid(), logical_model="gemini",
            captured=capture(source_d() if run_dict is None else run_dict),
        )

    def test_empty_readonly_audit_is_distinct_and_api_disabled(self):
        result = self.ledger.audit_restart()
        self.assertEqual((result["claims"], result["records"],
                          result["orphan_claims"]), (0, 0, 0))
        self.assertFalse(result["can_execute_api"])
        self.assertFalse(result["can_run_ood_test"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertEqual(result["source_inventory_sha256"], INVENTORY_SHA)
        self.assertEqual(len(self.ledger.rows), 180)

    def test_complete_d_c_k_readback_and_restart_retains_provenance(self):
        diag = source_d()
        d, _ = self.claim_and_record(sid(), self.d_receipt(diag))
        self.assertEqual(d["status"], "RECORDED_COMPLETE")
        for stage, output in (("C", cause()), ("K", rule())):
            receipt = normalize_v3_ck_call(
                stage_id=sid(stage=stage), logical_model="gemini",
                call=ck_call(output), diagnostic_run=diag,
            )
            record, _ = self.claim_and_record(sid(stage=stage), receipt)
            self.assertEqual(record["status"], "RECORDED_COMPLETE")
            self.assertEqual(record["artifact"]["text_extraction"]["text_blocks"], 2)
            self.assertEqual(record["source_commit"], PIN)
            self.assertEqual(record["source_inventory_sha256"], INVENTORY_SHA)
        self.assertEqual(
            self.ledger.load_record(stage_id=sid(stage="K"))["dependencies"][
                sid(stage="C")
            ],
            self.ledger.load_record(stage_id=sid(stage="C"))["record_sha256"],
        )
        check = self.new_ledger().audit_restart()
        self.assertEqual((check["claims"], check["records"],
                          check["orphan_claims"]), (3, 3, 0))
        self.assertEqual(
            self.ledger.load_record(stage_id=sid())["artifact"][
                "d_final_text_extraction"]["content_kind"], "str",
        )

    def test_failed_d_blocks_c_and_k_without_claim_or_new_api(self):
        failed = source_d()
        failed["error"] = "synthetic timeout with fake credential"
        failed["raw_response"] = None
        failed["metrics"]["token_usage_complete"] = False
        d, _ = self.claim_and_record(sid(), self.d_receipt(failed))
        self.assertEqual(d["status"], "PROVIDER_ERROR")
        self.assertNotIn("fake credential", str(d))
        for stage in ("C", "K"):
            blocked_id = sid(stage=stage)
            result = self.ledger.record_stage(
                stage_id=blocked_id, model_id=GEMINI_MODEL_ID, blocked=True,
            )
            self.assertEqual(result["status"], "BLOCKED_DEPENDENCY")
            record = self.ledger.load_record(stage_id=blocked_id)
            self.assertIsNone(record["claim_sha256"])
            self.assertEqual(record["artifact"], {})
            self.assertIsNone(self.ledger.load_claim(stage_id=blocked_id))
        check = self.ledger.audit_restart()
        self.assertEqual((check["claims"], check["records"],
                          check["orphan_claims"]), (1, 3, 0))

    def test_orphan_blocks_other_claims_and_no_automatic_retry(self):
        first = sid()
        existing = self.ledger.claim_stage(
            stage_id=first, model_id=GEMINI_MODEL_ID,
            stage_authorization=self.auth(first),
        )
        self.assertEqual(self.new_ledger().audit_restart()["orphan_claims"], 1)
        another = sid(harness="A1")
        with self.assertRaises(V3ScientificLedgerBlocked):
            self.ledger.claim_stage(
                stage_id=another, model_id=GEMINI_MODEL_ID,
                stage_authorization=self.auth(another),
            )
        with self.assertRaises(V3ScientificLedgerBlocked):
            self.ledger.claim_stage(
                stage_id=first, model_id=GEMINI_MODEL_ID,
                stage_authorization=self.auth(first),
            )
        with self.assertRaises(V3ScientificLedgerBlocked):
            self.ledger.record_stage(
                stage_id=first, model_id=GEMINI_MODEL_ID, receipt=self.d_receipt(),
                expected_claim_sha256="0" * 64,
            )
        self.ledger.record_stage(
            stage_id=first, model_id=GEMINI_MODEL_ID, receipt=self.d_receipt(),
            expected_claim_sha256=existing["claim_sha256"],
        )
        self.assertEqual(self.ledger.audit_restart()["orphan_claims"], 0)
        with self.assertRaises(V3ScientificLedgerBlocked):
            self.ledger.record_stage(
                stage_id=first, model_id=GEMINI_MODEL_ID, receipt=self.d_receipt(),
                expected_claim_sha256=existing["claim_sha256"],
            )

    def test_v2_ood_wrong_model_and_wrong_approval_blocked(self):
        ood = sid(case="cloudbed-2_q000")
        v2 = sid().replace(PROTOCOL, "rq2_v2_unified_five_harness_discovery_v0")
        for stage_id in (ood, v2):
            with self.assertRaises(V3ScientificLedgerBlocked):
                self.ledger.claim_stage(
                    stage_id=stage_id, model_id=GEMINI_MODEL_ID,
                    stage_authorization=self.auth(stage_id),
                )
        with self.assertRaises(V3ScientificLedgerBlocked):
            self.ledger.claim_stage(
                stage_id=sid(), model_id="wrong", stage_authorization=self.auth(sid()),
            )
        # Logical name is not the provider model_id: prevent silent aliasing.
        with self.assertRaises(V3ScientificLedgerBlocked):
            self.ledger.claim_stage(
                stage_id=sid(), model_id="gemini",
                stage_authorization=self.auth(sid()),
            )
        wrong = self.auth(sid())
        wrong["release_sha256"] = "c" * 64
        with self.assertRaises(V3ScientificLedgerBlocked):
            self.ledger.claim_stage(
                stage_id=sid(), model_id=GEMINI_MODEL_ID, stage_authorization=wrong,
            )
        with self.assertRaises(V3ScientificLedgerBlocked):
            self.ledger.record_stage(stage_id=sid(), model_id=GEMINI_MODEL_ID, blocked=True)

    def test_invalid_json_c_not_repaired_and_k_blocked(self):
        diag = source_d()
        self.claim_and_record(sid(), self.d_receipt(diag))
        corrupted = cause().replace("rq2_cause_probe_v0", "rq2_cause\n_probe_v0")
        receipt = normalize_v3_ck_call(
            stage_id=sid(stage="C"), logical_model="gemini",
            call=ck_call(corrupted, n=1), diagnostic_run=diag,
        )
        c, _ = self.claim_and_record(sid(stage="C"), receipt)
        self.assertEqual(c["status"], "INVALID_OUTPUT")
        self.assertEqual(c["artifact"]["raw_response"], corrupted)
        self.ledger.record_stage(
            stage_id=sid(stage="K"), model_id=GEMINI_MODEL_ID, blocked=True,
        )
        self.assertEqual(
            self.ledger.load_record(stage_id=sid(stage="K"))["status"],
            "BLOCKED_DEPENDENCY",
        )

    def test_tampering_even_with_rehashed_json_rejected_by_provenance(self):
        self.claim_and_record(sid(), self.d_receipt())
        path = self.ledger._path(sid(), claim=False)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["artifact"]["d_final_text_extraction"]["policy"] = "injected"
        data["artifact_sha256"] = _sha(data["artifact"])
        data["record_sha256"] = _sha({
            k: v for k, v in data.items() if k != "record_sha256"
        })
        path.write_bytes(_canonical(data))
        with self.assertRaises(V3ScientificLedgerBlocked):
            self.ledger.load_record(stage_id=sid())
        with self.assertRaises(V3ScientificLedgerBlocked):
            self.ledger.audit_restart()

    def test_parent_digest_change_rejected_even_with_valid_parent_record(self):
        diag = source_d()
        self.claim_and_record(sid(), self.d_receipt(diag))
        self.claim_and_record(
            sid(stage="C"),
            normalize_v3_ck_call(
                stage_id=sid(stage="C"), logical_model="gemini",
                call=ck_call(cause()), diagnostic_run=diag,
            ),
        )
        path = self.ledger._path(sid(), claim=False)
        d = json.loads(path.read_text(encoding="utf-8"))
        d["artifact"]["stage_meter"]["observed_model_requests"] += 1
        d["artifact_sha256"] = _sha(d["artifact"])
        d["record_sha256"] = _sha({
            k: v for k, v in d.items() if k != "record_sha256"
        })
        path.write_bytes(_canonical(d))
        with self.assertRaises(V3ScientificLedgerBlocked):
            self.ledger.load_record(stage_id=sid(stage="C"))

    def test_release_git_proof_and_missing_source_gate_are_fail_closed(self):
        self.git_mock.return_value = (PIN, " M src/foo.py")
        with self.assertRaises(V3ScientificLedgerBlocked):
            self.new_ledger()
        self.git_mock.return_value = (PIN, "")
        self.source_mock.return_value = {"status": "FAKE_PASS"}
        with self.assertRaises(V3ScientificLedgerBlocked):
            self.new_ledger()
        self.source_mock.side_effect = V3ScientificLedgerBlocked("NO INVENTORY")
        with self.assertRaises(V3ScientificLedgerBlocked):
            self.new_ledger()
        self.source_mock.side_effect = None
        self.source_patcher.stop()
        with self.assertRaises(V3ScientificLedgerBlocked):
            self.new_ledger()

    def test_unexpected_record_and_forbidden_gt_keys_fail_audit(self):
        claims = self.data / NAMESPACE / "claims"
        records = self.data / NAMESPACE / "records"
        records.mkdir(exist_ok=True)
        (records / "unexpected.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(V3ScientificLedgerBlocked):
            self.ledger.audit_restart()
        (records / "unexpected.json").unlink()
        self.claim_and_record(sid(), self.d_receipt())
        record_path = self.ledger._path(sid(), claim=False)
        record = json.loads(record_path.read_text("utf-8"))
        record["artifact"]["ground_truth"] = "NEVER"
        record["artifact_sha256"] = _sha(record["artifact"])
        record["record_sha256"] = _sha({
            k: v for k, v in record.items() if k != "record_sha256"
        })
        record_path.write_bytes(_canonical(record))
        with self.assertRaises(V3ScientificLedgerBlocked):
            self.ledger.load_record(stage_id=sid())


if __name__ == "__main__":
    unittest.main()
