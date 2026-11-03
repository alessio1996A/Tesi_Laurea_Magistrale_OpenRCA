"""Test sintetici: due freeze e 32 predizioni non sensibili."""
import csv
from datetime import datetime, timedelta
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

from evaluation.v2_frozen_prediction_audit import (
    BASE_COMMITS, FREEZE_NAMES, PROTOCOLS,
    audit_frozen_predictions,
)


TZ = ZoneInfo("Asia/Shanghai")
DAY = datetime(2022, 3, 20, 10, tzinfo=TZ)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_fixture(root: Path) -> None:
    processed = root / "data/processed"
    plans = root / "data/protocols"
    processed.mkdir(parents=True)
    plans.mkdir(parents=True)
    split = []
    manifest = []
    for i in range(1, 17):
        start = int((DAY + timedelta(hours=i)).timestamp())
        case_id = f"cloudbed-1_q{i:03d}"
        split.append({
            "case_id": case_id, "cloudbed": "cloudbed-1",
            "start_unix": str(start), "end_unix": str(start + 1800),
            "split": "development",
        })
        manifest.append({
            "case_id": case_id, "cloudbed": "cloudbed-1",
            "start_unix": str(start), "end_unix": str(start + 1800),
            "instruction": (
                "Two failures happened." if i % 2 == 0
                else "The service experienced a failure."
            ),
            "task_index": "task_1", "query_index": str(i),
        })

    def write_csv(path, rows, cols):
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=cols)
            writer.writeheader()
            writer.writerows(rows)

    write_csv(processed / "split_market_v1.csv", split, [
        "case_id", "cloudbed", "start_unix", "end_unix", "split",
    ])
    write_csv(processed / "benchmark_inputs_market.csv", manifest, [
        "case_id", "cloudbed", "query_index", "task_index",
        "instruction", "start_unix", "end_unix",
    ])
    split_sha = sha(processed / "split_market_v1.csv")
    manifest_sha = sha(processed / "benchmark_inputs_market.csv")
    for study, protocol in enumerate(PROTOCOLS):
        branch_names = (
            ("A1", "A1_VERIFY") if study == 0
            else ("A1_VERIFY", "A1_VERIFY_ST")
        )
        cases = manifest[study * 8:(study + 1) * 8]
        base = root / "data/results/paired" / protocol
        base.mkdir(parents=True)
        pairs = []
        for case in cases:
            case_id = case["case_id"]
            run_ids = [
                f"{protocol}__{case_id}__{variant.lower()}__r01"
                for variant in branch_names
            ]
            pairs.append({
                "case_id": case_id,
                "cloudbed": "cloudbed-1",
                "ordered_variants": list(branch_names),
                "run_ids": run_ids,
            })
        plan = {
            "protocol": protocol, "case_count": 8, "run_count": 16,
            "split_file_sha256": split_sha,
            "input_manifest_sha256": manifest_sha,
            "pairs": pairs,
        }
        plan_path = plans / f"{protocol}_cohort_v1.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        plan_sha = sha(plan_path)

        hashes = {}
        st_results = []
        for case, pair in zip(cases, pairs):
            case_id = case["case_id"]
            # Identica evidence tra i due bracci.
            evidence = hashlib.sha256(case_id.encode()).hexdigest()
            instruction_two = "Two failures" in case["instruction"]
            fault_count = 2 if instruction_two else 1
            start_unix = int(case["start_unix"])
            local = datetime.fromtimestamp(start_unix + 100, TZ)
            payload = {
                str(n): {
                    "root cause occurrence datetime": local.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "root cause component": f"synthetic-{n}",
                    "root cause reason": "synthetic fault",
                }
                for n in range(1, fault_count + 1)
            }
            for order, (variant, run_id) in enumerate(
                zip(pair["ordered_variants"], pair["run_ids"])
            ):
                result = {
                    "variant": variant,
                    "case_id": case_id,
                    "json_status": "valid_json",
                    "raw_response": json.dumps(payload),
                    "evidence_sha256": evidence,
                    "paired_provenance": {
                        "protocol": protocol, "run_id": run_id,
                        "frozen_plan_sha256": plan_sha,
                        "git_commit": BASE_COMMITS[study],
                        "execution_order_index": order,
                        "paired_evidence_sha256": evidence,
                    },
                }
                result_path = base / f"{run_id}.json"
                result_path.write_text(json.dumps(result), encoding="utf-8")
                if study == 0:
                    hashes[result_path.name] = sha(result_path)
                else:
                    st_results.append({
                        "case_id": case_id,
                        "variant": variant,
                        "run_id": run_id,
                        "result_relative_path": (
                            f"data/results/paired/{protocol}/{run_id}.json"
                        ),
                        "result_file_sha256": sha(result_path),
                        "json_status": "valid_json",
                        "evidence_sha256": evidence,
                    })
            if study == 0:
                claim = base / f"{case_id}__r01.pair_started.json"
                claim.write_text('{"synthetic_claim":true}', encoding="utf-8")
                hashes[claim.name] = sha(claim)
        freeze = {
            "protocol": protocol,
            "case_count": 8, "run_count": 16,
            "frozen_plan_sha256": plan_sha,
            "git_commit": BASE_COMMITS[study],
            "scoring_performed": False,
        }
        if study == 0:
            freeze["ground_truth_accessed"] = False
            freeze["file_sha256"] = hashes
        else:
            freeze["results"] = st_results
        (plans / FREEZE_NAMES[study]).write_text(
            json.dumps(freeze), encoding="utf-8",
        )


def update_sha_after_mutation(root: Path, study: int, run_id: str) -> None:
    protocol = PROTOCOLS[study]
    path = root / "data/results/paired" / protocol / f"{run_id}.json"
    freeze_path = root / "data/protocols" / FREEZE_NAMES[study]
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if study == 0:
        freeze["file_sha256"][path.name] = sha(path)
    else:
        for item in freeze["results"]:
            if item["run_id"] == run_id:
                item["result_file_sha256"] = sha(path)
                break
    freeze_path.write_text(json.dumps(freeze), encoding="utf-8")


class FrozenPredictionAuditTests(unittest.TestCase):
    def test_32_synthetic_predictions_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_fixture(root)
            report = audit_frozen_predictions(
                root, verify_original_hashes=False,
            )
            self.assertEqual(report["runs_checked"], 32)
            self.assertEqual(len(report["studies"]), 2)
            self.assertEqual(report["by_variant"]["A1"]["runs"], 8)
            self.assertEqual(report["by_variant"]["A1_VERIFY"]["runs"], 16)
            self.assertEqual(report["by_variant"]["A1_VERIFY_ST"]["runs"], 8)
            self.assertTrue(all(row["v2_valid"] for row in report["runs"]))
            self.assertFalse(report["read_ground_truth"])
            self.assertFalse(report["files_written"])
            self.assertEqual(report["gemini_calls"], 0)

    def test_nonconforming_response_reported_not_repaired(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_fixture(root)
            protocol = PROTOCOLS[0]
            run_id = f"{protocol}__cloudbed-1_q001__a1__r01"
            path = root / "data/results/paired" / protocol / f"{run_id}.json"
            result = json.loads(path.read_text(encoding="utf-8"))
            old = result["raw_response"]
            result["raw_response"] = '{"1":{"root cause component":"x"}}'
            path.write_text(json.dumps(result), encoding="utf-8")
            update_sha_after_mutation(root, 0, run_id)
            before = path.read_bytes()
            report = audit_frozen_predictions(
                root, verify_original_hashes=False,
            )
            self.assertEqual(path.read_bytes(), before)
            item = next(x for x in report["runs"] if x["run_id"] == run_id)
            self.assertFalse(item["v2_valid"])
            self.assertTrue(item["json_legacy_valid"])
            self.assertIn("aggiuntivi", item["v2_reason"])
            self.assertNotEqual(result["raw_response"], old)

    def test_mismatched_hash_rejected_before_interpretation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_fixture(root)
            protocol = PROTOCOLS[0]
            path = next(
                (root / "data/results/paired" / protocol).glob("*__a1__r01.json")
            )
            path.write_text('{"tampered":true}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                audit_frozen_predictions(root, verify_original_hashes=False)

    def test_provenance_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_fixture(root)
            protocol = PROTOCOLS[1]
            run_id = f"{protocol}__cloudbed-1_q009__a1_verify__r01"
            path = root / "data/results/paired" / protocol / f"{run_id}.json"
            result = json.loads(path.read_text(encoding="utf-8"))
            result["paired_provenance"]["git_commit"] = "wrong"
            path.write_text(json.dumps(result), encoding="utf-8")
            update_sha_after_mutation(root, 1, run_id)
            with self.assertRaisesRegex(ValueError, "Metadati"):
                audit_frozen_predictions(root, verify_original_hashes=False)

    def test_gt_column_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_fixture(root)
            path = root / "data/processed/benchmark_inputs_market.csv"
            old = path.read_text(encoding="utf-8")
            path.write_text(old.replace(
                "case_id,cloudbed", "case_id,ground_truth,cloudbed", 1
            ), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Schema GT-free"):
                audit_frozen_predictions(root, verify_original_hashes=False)

    def test_original_sha_guard_rejects_synthetic_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_fixture(root)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                audit_frozen_predictions(root, verify_original_hashes=True)


if __name__ == "__main__":
    unittest.main()
