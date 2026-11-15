"""V3 source inventory unit tests, exclusively mocked GT-free baseline.

No actual benchmark data, network, SDK, model requests, ledger or release.
All test files live in TemporaryDirectory and are synthetic stand-ins.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import evaluation.rq2_v3_scientific_source_inventory as inventory
from evaluation.rq2_probe_adapter import CAUSE_SYSTEM, RULE_SYSTEM
from evaluation.rq2_v2_unified_discovery_plan import (
    VERSION as V2_PROTOCOL,
    EXPECTED_SPLIT_SHA256, EXPECTED_MANIFEST_SHA256,
    DISCOVERY, HARNESSES,
)
from evaluation.rq2_v2_unified_release_preflight import (
    VERSION as SOURCE_V2_VERSION, SOURCE_PATHS as BASELINE_PATHS,
)
from evaluation.rq2_v3_unified_gtfree_discovery_plan import (
    VERSION as PROTOCOL, build_offline_v3_discovery_plan,
)


class V3ScientificSourceInventoryOfflineTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="V3_INVENTORY_OFFLINE_")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.data = self.root / "data"
        self.src = self.root / "src"
        self.data.mkdir()
        self.src.mkdir()
        self.plan = build_offline_v3_discovery_plan()
        for name in (*BASELINE_PATHS, *inventory.V3_SOURCE_PATHS):
            path = self.src / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("# synthetic source " + name + "\r\n").encode())
        self.preview = {
            "version": SOURCE_V2_VERSION,
            "status": "OFFLINE_SOURCE_BOUND_NO_RELEASE_NO_API",
            "protocol": V2_PROTOCOL,
            "plan_preview_sha256": self.plan["base_v2_plan_sha256"],
            "entries_sha256": self.plan["base_v2_entries_sha256"],
            "source_file_count": len(BASELINE_PATHS),
            "gt_free_source_verified": True,
            "frozen_rq1_source_identity_verified": True,
            "split_sha256": EXPECTED_SPLIT_SHA256,
            "manifest_sha256": EXPECTED_MANIFEST_SHA256,
            "C_system_prompt_sha256": hashlib.sha256(
                CAUSE_SYSTEM.encode("utf-8")
            ).hexdigest(),
            "K_system_prompt_sha256": hashlib.sha256(
                RULE_SYSTEM.encode("utf-8")
            ).hexdigest(),
            "model_ids": self.plan["model_ids"],
            "harnesses": list(HARNESSES),
            "discovery_cases": list(DISCOVERY),
            "ood_test_cases_locked": 11,
            "stage_counts": {"D": 60, "C": 60, "K": 60},
            "logical_stages": 180,
            "d_max_tool_rounds": 6,
            "planning_checks_reserved": 2,
            "d_output_contract": "v2_enforce",
            "ground_truth_read": False,
            "can_execute_api": False,
            "can_run_ood_test": False,
            "scientific_release_frozen": False,
            "claims_written": 0,
            "data_files_written": False,
            "model_requests_sent": 0,
            "source_commit_pinned_for_release": False,
            "source_files_sha256": {
                name: hashlib.sha256(
                    (self.src / name).read_bytes().replace(b"\r\n", b"\n")
                ).hexdigest()
                for name in BASELINE_PATHS
            },
        }
        self.patcher = patch.object(
            inventory, "preview_unified_source_bound", return_value=self.preview
        )
        self.mock_v2 = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def invoke(self):
        return inventory.preview_v3_scientific_source_inventory(
            data_dir=self.data, src_root=self.src,
        )

    def test_180_stage_and_11_ood_preview_is_no_go(self):
        result = self.invoke()
        self.assertEqual(result["protocol"], PROTOCOL)
        self.assertEqual(result["status"], inventory.STATUS)
        self.assertEqual(result["logical_stages"], 180)
        self.assertEqual(result["stage_counts"], {"D": 60, "C": 60, "K": 60})
        self.assertEqual(result["ood_test_cases_locked"],
                         self.plan["ood_test_cases_locked"])
        self.assertEqual(len(result["ood_test_cases_locked"]), 11)
        self.assertEqual(len(result["v2_source_files_sha256"]),
                         len(BASELINE_PATHS))
        self.assertEqual(len(result["v3_source_files_sha256"]),
                         len(inventory.V3_SOURCE_PATHS))
        self.assertEqual(result["missing_future_paths"],
                         list(inventory.FUTURE_REQUIRED_PATHS))
        for flag in ("source_commit_pinned", "scientific_release_frozen",
                     "can_create_claim", "can_execute_api",
                     "can_run_ood_test", "ground_truth_read", "files_written"):
            self.assertIs(result[flag], False)

    def test_repeated_preview_is_deterministic_and_read_only(self):
        before = {
            p.relative_to(self.root).as_posix(): p.read_bytes()
            for p in self.root.rglob("*") if p.is_file()
        }
        first, second = self.invoke(), self.invoke()
        self.assertEqual(first, second)
        after = {
            p.relative_to(self.root).as_posix(): p.read_bytes()
            for p in self.root.rglob("*") if p.is_file()
        }
        self.assertEqual(before, after)
        self.assertEqual(self.mock_v2.call_count, 2)
        self.assertEqual(first["model_requests_sent"], 0)

    def test_v3_file_tamper_changes_candidate_sha_not_baseline_sha(self):
        first = self.invoke()
        path = self.src / inventory.V3_SOURCE_PATHS[0]
        path.write_bytes(path.read_bytes() + b"# synthetic edit\n")
        changed = self.invoke()
        self.assertNotEqual(first["candidate_inventory_sha256"],
                            changed["candidate_inventory_sha256"])
        self.assertNotEqual(first["v3_source_files_sha256"],
                            changed["v3_source_files_sha256"])
        self.assertEqual(first["v2_source_files_sha256"],
                         changed["v2_source_files_sha256"])

    def test_v2_file_modified_since_preflight_rejected(self):
        self.invoke()
        target = self.src / BASELINE_PATHS[0]
        target.write_bytes(target.read_bytes() + b"unsafe drift")
        with self.assertRaises(inventory.V3SourceInventoryBlocked):
            self.invoke()

    def test_v3_file_missing_and_symlink_rejected(self):
        target = self.src / inventory.V3_SOURCE_PATHS[0]
        target.unlink()
        with self.assertRaises(inventory.V3SourceInventoryBlocked):
            self.invoke()
        try:
            target.symlink_to(self.src / inventory.V3_SOURCE_PATHS[1])
        except (OSError, NotImplementedError):
            return  # Windows may disallow creating a symlink
        with self.assertRaises(inventory.V3SourceInventoryBlocked):
            self.invoke()

    def test_v2_file_hashes_must_match_exact_set_and_digest(self):
        for mutation in ("remove", "foreign", "bad_hash"):
            with self.subTest(mutation=mutation):
                bad = copy.deepcopy(self.preview)
                hashes = bad["source_files_sha256"]
                if mutation == "remove":
                    del hashes[BASELINE_PATHS[0]]
                elif mutation == "foreign":
                    hashes["fake/extra.py"] = "f" * 64
                else:
                    hashes[BASELINE_PATHS[0]] = "f" * 64
                self.mock_v2.return_value = bad
                with self.assertRaises(inventory.V3SourceInventoryBlocked):
                    self.invoke()
        self.mock_v2.return_value = self.preview

    def test_frozen_gt_free_status_split_and_ood_count_fail_closed(self):
        for key, bad in (
            ("gt_free_source_verified", False),
            ("ground_truth_read", True),
            ("can_run_ood_test", True),
            ("split_sha256", "0" * 64),
            ("manifest_sha256", "0" * 64),
            ("ood_test_cases_locked", 10),
            ("scientific_release_frozen", True),
        ):
            with self.subTest(key=key):
                tampered = {**self.preview, key: bad}
                self.mock_v2.return_value = tampered
                with self.assertRaises(inventory.V3SourceInventoryBlocked):
                    self.invoke()
        self.mock_v2.return_value = self.preview

    def test_c_k_prompt_hashes_and_model_ids_must_be_unchanged(self):
        for key, bad in (
            ("C_system_prompt_sha256", "0" * 64),
            ("K_system_prompt_sha256", "0" * 64),
            ("model_ids", {"gemini": "wrong"}),
        ):
            with self.subTest(key=key):
                self.mock_v2.return_value = {**self.preview, key: bad}
                with self.assertRaises(inventory.V3SourceInventoryBlocked):
                    self.invoke()
        self.mock_v2.return_value = self.preview

    def test_v3_plan_must_not_unlock_ood_or_change_models(self):
        for key, bad in (
            ("ood_test_cases_locked", ["unlocked"]),
            ("logical_stages", 181),
            ("models", ["gemini", "haiku"]),
            ("uniform_final_text_extraction_policy_candidate", "altered"),
        ):
            with self.subTest(key=key):
                bad_plan = copy.deepcopy(self.plan)
                bad_plan[key] = bad
                with patch.object(
                    inventory, "build_offline_v3_discovery_plan",
                    return_value=bad_plan,
                ):
                    with self.assertRaises(inventory.V3SourceInventoryBlocked):
                        self.invoke()

    def test_unavailable_or_unsafe_roots_fail_closed(self):
        with self.assertRaises(inventory.V3SourceInventoryBlocked):
            inventory.preview_v3_scientific_source_inventory(
                data_dir=Path("relative"), src_root=self.src,
            )
        with self.assertRaises(inventory.V3SourceInventoryBlocked):
            inventory.preview_v3_scientific_source_inventory(
                data_dir=self.data, src_root=self.src / "missing",
            )

    def test_future_file_presence_never_authorizes_release(self):
        future = self.src / inventory.FUTURE_REQUIRED_PATHS[0]
        future.parent.mkdir(parents=True, exist_ok=True)
        future.write_text("# intentionally still unverified\n", encoding="utf-8")
        result = self.invoke()
        self.assertEqual(len(result["missing_future_paths"]),
                         len(inventory.FUTURE_REQUIRED_PATHS) - 1)
        self.assertIs(result["can_execute_api"], False)
        self.assertIs(result["scientific_release_frozen"], False)
        self.assertEqual(result["status"], inventory.STATUS)

    def test_baseline_preflight_exception_is_fail_closed(self):
        self.mock_v2.side_effect = ValueError("synthetic source mismatch")
        with self.assertRaises(inventory.V3SourceInventoryBlocked):
            self.invoke()


if __name__ == "__main__":
    unittest.main()
