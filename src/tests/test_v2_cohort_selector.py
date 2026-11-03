"""Test sintetici della selezione V2.5 senza ground truth, scorer o API."""
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.v2_case_window_audit import PROTOCOLS
from evaluation.v2_cohort_selector import (
    AUDIT_SEED, HISTORICAL_SEEN, _rank, propose_v2_cohort,
)


def _overlaps(a, b):
    return (
        a["cloudbed"] == b["cloudbed"]
        and int(a["start_unix"]) < int(b["end_unix"])
        and int(b["start_unix"]) < int(a["end_unix"])
    )


def _csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        w = csv.DictWriter(stream, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(root):
    proc = root / "data/processed"
    plans = root / "data/protocols"
    plans.mkdir(parents=True)
    rows = []
    manifest = []
    for cb in ("cloudbed-1", "cloudbed-2"):
        for i in range(91):
            # q090 ripete ESATTAMENTE il pilot q002 nel cloudbed-1.
            slot = 2 if cb == "cloudbed-1" and i == 90 else i
            start = 1000000 * (1 if cb == "cloudbed-1" else 2) + slot * 3600
            case_id = f"{cb}_q{i:03d}"
            row = {
                "case_id": case_id, "cloudbed": cb,
                "start_unix": str(start), "end_unix": str(start + 1800),
                "split": "evaluation" if i == 88 else "development",
            }
            rows.append(row)
            manifest.append({
                "case_id": case_id, "cloudbed": cb,
                "start_unix": row["start_unix"],
                "end_unix": row["end_unix"],
                "query_index": str(i), "task_index": f"task_{i % 7 + 1}",
                "instruction": "Two failures occurred." if i % 2 else
                               "The system experienced a failure.",
            })
    split_path = proc / "split_market_v1.csv"
    manifest_path = proc / "benchmark_inputs_market.csv"
    _csv(split_path, ["case_id", "cloudbed", "start_unix", "end_unix", "split"], rows)
    _csv(manifest_path, [
        "case_id", "cloudbed", "query_index", "task_index",
        "instruction", "start_unix", "end_unix",
    ], manifest)
    split_sha, manifest_sha = _sha(split_path), _sha(manifest_path)
    first = [
        "cloudbed-1_q063", "cloudbed-2_q007", "cloudbed-2_q046",
        "cloudbed-1_q035", "cloudbed-1_q002", "cloudbed-2_q033",
        "cloudbed-1_q038", "cloudbed-2_q067",
    ]
    second = [
        "cloudbed-2_q073", "cloudbed-2_q055", "cloudbed-2_q066",
        "cloudbed-1_q043", "cloudbed-2_q053", "cloudbed-1_q036",
        "cloudbed-1_q016", "cloudbed-1_q065",
    ]
    for protocol, ids in zip(PROTOCOLS, [first, second]):
        (plans / f"{protocol}_cohort_v1.json").write_text(
            json.dumps({
                "protocol": protocol, "run_count": 16, "case_count": 8,
                "split_file_sha256": split_sha,
                "input_manifest_sha256": manifest_sha,
                "pairs": [{"case_id": id_} for id_ in ids],
            }), encoding="utf-8",
        )
    protected = [
        r for r in rows
        if r["split"] != "development" or r["case_id"] in HISTORICAL_SEEN
    ]
    eligible = [
        r for r in rows
        if r["split"] == "development"
        and r["case_id"] not in HISTORICAL_SEEN
        and not any(_overlaps(r, old) for old in protected)
    ]
    chosen = []
    for cb in ("cloudbed-1", "cloudbed-2"):
        group = []
        for row in sorted(
            (r for r in eligible if r["cloudbed"] == cb),
            key=lambda r: (_rank(AUDIT_SEED, r["case_id"]), r["case_id"]),
        ):
            if not any(_overlaps(row, other) for other in group):
                group.append(row)
            if len(group) == 2:
                break
        chosen.extend(group)
    consumed = sorted({
        r["case_id"] for r in rows
        if r["split"] == "development"
        and any(_overlaps(r, other) for other in chosen)
    })
    inventory_path = root / "network_kpi_inventory_v1.json"
    inventory_path.write_text(json.dumps({
        "audit": "network_kpi_inventory_v1",
        "selection_seed": AUDIT_SEED,
        "split_sha256": split_sha,
        "manifest_sha256": manifest_sha,
        "read_ground_truth": False,
        "read_metric_values": False,
        "gemini_calls": 0,
        "selected_windows": chosen,
        "development_case_ids_now_seen": consumed,
    }), encoding="utf-8")
    return {
        "data_dir": root,
        "inventory_path": inventory_path,
        "verify_original_hashes": False,
    }


class V2CohortSelectorTests(unittest.TestCase):
    def test_propose_eight_new_nonoverlapping_cases_with_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = fixture(Path(tmp))
            plan = propose_v2_cohort(**args)
        self.assertEqual(plan["case_count"], 8)
        self.assertEqual(plan["planned_runs"], 40)
        self.assertEqual(plan["task_coverage"], [f"task_{i}" for i in range(1, 8)])
        self.assertEqual(
            set(plan["multi_fault_cases_per_cloudbed"]),
            {"cloudbed-1", "cloudbed-2"},
        )
        self.assertEqual(len({x["case_id"] for x in plan["selected_cases"]}), 8)
        self.assertEqual(
            {x["cloudbed"] for x in plan["selected_cases"]},
            {"cloudbed-1", "cloudbed-2"},
        )
        seen = set(plan["historical_case_ids"])
        audit_seen = set(plan["network_audit_consumed_case_ids"])
        self.assertTrue(all(
            x["case_id"] not in seen | audit_seen
            for x in plan["selected_cases"]
        ))
        self.assertTrue(all(
            x["case_id"] != "cloudbed-1_q090"
            for x in plan["selected_cases"]
        ))
        self.assertFalse(plan["read_ground_truth"])
        self.assertFalse(plan["read_scorer"])
        self.assertEqual(plan["gemini_calls"], 0)

    def test_deterministic_same_seed_same_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = fixture(Path(tmp))
            first = propose_v2_cohort(**args)
            second = propose_v2_cohort(**args)
        self.assertEqual(first, second)

    def test_altered_a2_windows_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = fixture(Path(tmp))
            path = args["inventory_path"]
            inventory = json.loads(path.read_text(encoding="utf-8"))
            inventory["selected_windows"][0]["case_id"] = "cloudbed-1_q090"
            path.write_text(json.dumps(inventory), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "A/2"):
                propose_v2_cohort(**args)

    def test_missing_inventory_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = fixture(Path(tmp))
            args["inventory_path"].unlink()
            with self.assertRaises(FileNotFoundError):
                propose_v2_cohort(**args)

    def test_historical_protocol_outside_register_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = fixture(Path(tmp))
            path = args["data_dir"] / "data/protocols" / (
                PROTOCOLS[0] + "_cohort_v1.json"
            )
            plan = json.loads(path.read_text(encoding="utf-8"))
            plan["pairs"][0]["case_id"] = "cloudbed-1_q080"
            path.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Registro storico"):
                propose_v2_cohort(**args)

    def test_original_hash_guard_blocks_synthetic_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = fixture(Path(tmp))
            args["verify_original_hashes"] = True
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                propose_v2_cohort(**args)

    def test_no_candidate_policy_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = fixture(Path(tmp))
            args["per_cloudbed"] = 100
            with self.assertRaisesRegex(ValueError, "bilanciata|insufficienti"):
                propose_v2_cohort(**args)


if __name__ == "__main__":
    unittest.main()
