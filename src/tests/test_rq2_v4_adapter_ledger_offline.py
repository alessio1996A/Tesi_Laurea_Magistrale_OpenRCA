"""Integrazione V4 adapter/ledger, totalmente sintetica e offline.

Il source/release gate V4 reale deve SEMPRE bloccare; per provare la
logica del ledger si usa unicamente TemporaryDirectory e un mock
esplicito di quel confine. Nessun vero release, claim, record, dataset
OpenRCA, modello, rete o credenziale.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.rq2_v2_ck_text_extraction_candidate import POLICY
from evaluation.rq2_v2_unified_scientific_ledger import (
    _canonical, _sha, _read, _write_once,
)
from evaluation.rq2_v3_d_runner_capture_candidate import VERSION as D_CAPTURE
from evaluation.rq2_v3_d_final_stream_candidate import D_META_SCHEMA
from evaluation.rq2_v3_scientific_receipt_adapter_candidate import VERSION as V3_RECEIPT
from evaluation.rq2_v3_unified_gtfree_discovery_plan import VERSION as V3_PROTOCOL
from evaluation.rq2_v4_scientific_source_release_gate import V4SourceReleaseBlocked
from evaluation.rq2_v4_scientific_receipt_adapter_candidate import (
    VERSION as V4_RECEIPT, V4ScientificReceiptBlocked,
    normalize_v4_d_capture, normalize_v4_ck_call,
    validate_v4_scientific_artifact,
)
from evaluation.rq2_v4_scientific_ledger import (
    V4ScientificLedger, V4ScientificLedgerBlocked, RELEASE_SCHEMA,
)
from evaluation.rq2_v4_unified_gtfree_discovery_plan import (
    VERSION as V4_PROTOCOL, NAMESPACE, RELEASE_FILE,
    build_offline_v4_discovery_plan,
)

PIN = "a" * 40
INVENTORY = "b" * 64
SID = V4_PROTOCOL + ":cloudbed-1_q032:gemini:A0:D"
PLAN = build_offline_v4_discovery_plan()
ROW = next(r for r in PLAN["entries"] if r["stage_id"] == SID)
RAW = '{"1":{"root cause reason":"synthetic database failure"}}'


def make_run(*, valid=True):
    return {
        "case_id": ROW["case_id"],
        "variant": ROW["harness"],
        "variant_scheme": "current",
        "model": ROW["model_id"],
        "model_provider": ROW["model_provider"],
        "output_contract_mode": "v2_enforce",
        "max_tool_rounds": 6,
        "task_index": "task_2",
        "raw_response": RAW if valid else "not a json",
        "prediction": RAW if valid else None,
        "json_status": "valid_json" if valid else "invalid_v2_task_output",
        "error": None,
        "tool_trajectory": [],
        "metrics": {
            "llm_calls": 1,
            "input_tokens": 20,
            "output_tokens": 15,
            "total_tokens": 35,
            "token_usage_complete": True,
        },
        "output_contract_v2": {
            "contract": "openrca_v2_task_aware_v1",
            "valid": valid,
            "error": None if valid else "invalid JSON",
            "task_index": "task_2",
            "required_fields": ["root cause reason"],
            "expected_faults": 1,
            "diagnosed_faults": 1 if valid else None,
            "timestamp_in_window": None,
            "temporal_outliers": [],
            "chronological_order": None,
            "extra_fields": [],
        },
    }


def captured(run):
    return {
        "version": D_CAPTURE,
        "diagnostic_run": run,
        "d_final_text_extraction": {
            "schema": D_META_SCHEMA,
            "policy": POLICY,
            "content_kind": "list",
            "text_blocks": 1,
            "nontext_blocks": 0,
        },
        "can_execute_api": False,
        "can_write_scientific_records": False,
        "scientific_release_frozen": False,
    }


class V4AdapterOfflineTests(unittest.TestCase):
    def test_task_2_only_reason_is_recorded_complete(self):
        with patch(
            "evaluation.rq2_v4_d_task_aware_contract.audit_captured_v2_d",
            return_value={"status": "SYNTHETIC_ONLY"},
        ):
            result = normalize_v4_d_capture(
                stage_id=SID, logical_model="gemini",
                captured=captured(make_run()),
            )
        self.assertEqual(result["version"], V4_RECEIPT)
        self.assertEqual(result["stage_id"], SID)
        self.assertEqual(result["status"], "RECORDED_COMPLETE")
        self.assertEqual(result["artifact"]["diagnostic_run"]["task_index"], "task_2")
        self.assertFalse(result["can_execute_api"])

    def test_invalid_task_status_is_still_invalid(self):
        with patch(
            "evaluation.rq2_v4_d_task_aware_contract.audit_captured_v2_d",
            return_value={},
        ):
            result = normalize_v4_d_capture(
                stage_id=SID, logical_model="gemini",
                captured=captured(make_run(valid=False)),
            )
        self.assertEqual(result["status"], "INVALID_OUTPUT")

    def test_adapter_and_readback_reject_conflicting_status(self):
        with patch(
            "evaluation.rq2_v4_d_task_aware_contract.audit_captured_v2_d",
            return_value={},
        ):
            result = normalize_v4_d_capture(
                stage_id=SID, logical_model="gemini",
                captured=captured(make_run()),
            )
            with self.assertRaises(V4ScientificReceiptBlocked):
                validate_v4_scientific_artifact(
                    stage_id=SID, logical_model="gemini",
                    status="INVALID_OUTPUT", artifact=result["artifact"],
                )

    def test_no_v3_scientific_ids_accepted(self):
        with self.assertRaises(V4ScientificReceiptBlocked):
            normalize_v4_d_capture(
                stage_id=V3_PROTOCOL + SID[len(V4_PROTOCOL):],
                logical_model="gemini", captured=captured(make_run()),
            )

    def test_C_K_validation_uses_v3_pure_code_not_v3_records(self):
        cid = SID.rsplit(":", 1)[0] + ":C"
        with patch(
            "evaluation.rq2_v4_scientific_receipt_adapter_candidate."
            "validate_v3_scientific_artifact",
            return_value=None,
        ) as pure:
            validate_v4_scientific_artifact(
                stage_id=cid, logical_model="gemini",
                status="PROVIDER_ERROR",
                artifact={"text_extraction": {}, "provider_error": "fake"},
                diagnostic_run=make_run(),
            )
        self.assertEqual(
            pure.call_args.kwargs["stage_id"],
            V3_PROTOCOL + cid[len(V4_PROTOCOL):],
        )
        self.assertEqual(pure.call_count, 1)

    def test_ck_normalizer_isolation_of_stage_identity(self):
        cid = SID.rsplit(":", 1)[0] + ":C"
        with (
            patch(
                "evaluation.rq2_v4_scientific_receipt_adapter_candidate."
                "normalize_v3_ck_call",
                return_value={
                    "version": V3_RECEIPT,
                    "stage_id": V3_PROTOCOL + cid[len(V4_PROTOCOL):],
                    "status": "INVALID_OUTPUT",
                    "artifact": {"synthetic": True},
                },
            ) as ck,
            patch(
                "evaluation.rq2_v4_scientific_receipt_adapter_candidate."
                "validate_v3_scientific_artifact",
                return_value=None,
            ),
        ):
            receipt = normalize_v4_ck_call(
                stage_id=cid, logical_model="gemini",
                call={"synthetic": True}, diagnostic_run=make_run(),
            )
        self.assertEqual(receipt["version"], V4_RECEIPT)
        self.assertEqual(receipt["stage_id"], cid)
        self.assertFalse(receipt["can_execute_api"])
        self.assertEqual(ck.call_count, 1)


class V4LedgerOfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        work = Path(self.tmp.name)
        self.data = work / "data_root"
        self.repo = work / "source_repo"
        self.data.mkdir()
        self.repo.mkdir()
        release = {
            "schema": RELEASE_SCHEMA,
            "protocol": V4_PROTOCOL,
            "source_commit": PIN,
            "plan_sha256": PLAN["preview_sha256"],
            "scientific_namespace": NAMESPACE.as_posix(),
            "ood_test_cases_locked": PLAN["ood_test_cases_locked"],
            "source_inventory_sha256": INVENTORY,
            "can_run_ood_test": False,
            "can_execute_api": False,
        }
        self.release = release
        self.release_sha = _sha(release)
        folder = self.data / NAMESPACE
        folder.mkdir(parents=True)
        _write_once(self.data / RELEASE_FILE, release)
        self.proof = {
            "status": "V4_SOURCE_BOUND_RELEASE_VERIFIED",
            "source_commit": PIN,
            "release_sha256": self.release_sha,
            "source_inventory_sha256": INVENTORY,
            "plan_sha256": PLAN["preview_sha256"],
            "can_execute_api": False,
            "can_create_claim": False,
            "can_run_ood_test": False,
        }
        self.git = patch(
            "evaluation.rq2_v4_scientific_ledger._repository_commit",
            return_value=(PIN, ""),
        )
        self.git.start()
        self.addCleanup(self.git.stop)

    def ledger_with_synthetic_gate(self):
        # Solo per TemporaryDirectory: bypass esplicito del gate NO-GO.
        with patch.object(
            V4ScientificLedger, "_source_release",
            return_value=self.proof,
        ):
            return V4ScientificLedger(
                data_dir=self.data, repo_dir=self.repo,
                expected_commit=PIN,
                approved_release_sha256=self.release_sha,
            )

    def auth(self):
        return {
            "scope": "ONE_V4_STAGE_CLAIM_ONLY",
            "stage_id": SID,
            "model_id": ROW["model_id"],
            "source_commit": PIN,
            "release_sha256": self.release_sha,
            "approval_reference": "SYNTHETIC_V4_APPROVAL_ONLY",
            "stage_budget_usd": "0.10",
        }

    def test_real_v4_gate_is_fail_closed_even_with_mock_git(self):
        with self.assertRaises(V4ScientificLedgerBlocked):
            V4ScientificLedger(
                data_dir=self.data, repo_dir=self.repo,
                expected_commit=PIN,
                approved_release_sha256=self.release_sha,
            )
        with self.assertRaises(V4SourceReleaseBlocked):
            from evaluation.rq2_v4_scientific_source_release_gate import (
                verify_v4_source_release,
            )
            verify_v4_source_release(
                data_dir=self.data, repo_dir=self.repo,
                release=self.release, expected_commit=PIN,
                approved_release_sha256=self.release_sha,
            )

    def test_empty_ledger_audit_synthetic_gate(self):
        ledger = self.ledger_with_synthetic_gate()
        with patch.object(
            ledger, "_source_release", return_value=self.proof,
        ):
            result = ledger.audit_restart()
        self.assertEqual(result["claims"], 0)
        self.assertEqual(result["records"], 0)
        self.assertEqual(result["orphan_claims"], 0)
        self.assertFalse(result["can_execute_api"])

    def test_claim_complete_record_and_readback_same_d_contract(self):
        # Tutti gli artefatti sono sintetici: niente token a pagamento.
        with (
            patch.object(V4ScientificLedger, "_source_release", return_value=self.proof),
            patch(
                "evaluation.rq2_v4_d_task_aware_contract.audit_captured_v2_d",
                return_value={"status": "SYNTHETIC_ONLY"},
            ),
        ):
            ledger = self.ledger_with_synthetic_gate()
            claim = ledger.claim_stage(
                stage_id=SID, model_id=ROW["model_id"],
                stage_authorization=self.auth(),
            )
            receipt = normalize_v4_d_capture(
                stage_id=SID, logical_model="gemini",
                captured=captured(make_run()),
            )
            record = ledger.record_stage(
                stage_id=SID, model_id=ROW["model_id"],
                receipt=receipt,
                expected_claim_sha256=claim["claim_sha256"],
            )
            check = ledger.load_record(stage_id=SID)
            audit = ledger.audit_restart()
        self.assertEqual(record["status"], "RECORDED_COMPLETE")
        self.assertEqual(check["record_sha256"], record["record_sha256"])
        self.assertEqual(audit["claims"], 1)
        self.assertEqual(audit["records"], 1)
        self.assertEqual(audit["orphan_claims"], 0)
        self.assertEqual(list((self.data / NAMESPACE / "claims").glob("V4_CLAIM_*.json")).__len__(), 1)
        self.assertEqual(list((self.data / NAMESPACE / "records").glob("V4_RECORD_*.json")).__len__(), 1)

    def test_duplicate_claim_does_not_retry(self):
        with patch.object(V4ScientificLedger, "_source_release", return_value=self.proof):
            ledger = self.ledger_with_synthetic_gate()
            ledger.claim_stage(
                stage_id=SID, model_id=ROW["model_id"],
                stage_authorization=self.auth(),
            )
            with self.assertRaises(V4ScientificLedgerBlocked):
                ledger.claim_stage(
                    stage_id=SID, model_id=ROW["model_id"],
                    stage_authorization=self.auth(),
                )
            audit = ledger.audit_restart()
        self.assertEqual(audit["orphan_claims"], 1)

    def test_status_tamper_detected_on_canonical_readback(self):
        with (
            patch.object(V4ScientificLedger, "_source_release", return_value=self.proof),
            patch(
                "evaluation.rq2_v4_d_task_aware_contract.audit_captured_v2_d",
                return_value={"status": "SYNTHETIC_ONLY"},
            ),
        ):
            ledger = self.ledger_with_synthetic_gate()
            claim = ledger.claim_stage(
                stage_id=SID, model_id=ROW["model_id"],
                stage_authorization=self.auth(),
            )
            receipt = normalize_v4_d_capture(
                stage_id=SID, logical_model="gemini",
                captured=captured(make_run()),
            )
            ledger.record_stage(
                stage_id=SID, model_id=ROW["model_id"],
                receipt=receipt,
                expected_claim_sha256=claim["claim_sha256"],
            )
            path = ledger._path(SID, claim=False)
            saved = _read(path)
            saved["status"] = "INVALID_OUTPUT"
            saved["record_sha256"] = _sha({
                k: v for k, v in saved.items() if k != "record_sha256"
            })
            # In un TEST solo: riscrittura volontaria per testare il readback.
            path.write_bytes(_canonical(saved))
            with self.assertRaises(V4ScientificLedgerBlocked):
                ledger.load_record(stage_id=SID)

    def test_v3_records_not_discovered_by_v4_audit(self):
        with patch.object(V4ScientificLedger, "_source_release", return_value=self.proof):
            ledger = self.ledger_with_synthetic_gate()
            older = self.data / "data/rq2_v3_unified_scientific_v1"
            older.mkdir()
            (older / "historical-marker").write_text("NOT READ")
            audit = ledger.audit_restart()
        self.assertEqual(audit["claims"], 0)
        self.assertEqual(audit["records"], 0)


if __name__ == "__main__":
    unittest.main()
