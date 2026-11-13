"""Test di sicurezza della policy RQ2-V2, rigorosamente offline.

Non crea claim, record o directory scientifiche. Nessun provider o GT.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.rq2_v2_isolation_policy import (
    ARTIFACTS_RELATIVE,
    CLAIMS_RELATIVE,
    DRAFT_PROTOCOL,
    ROOT_RELATIVE,
    RQ2V2IsolationError,
    preview_v2_destination,
)


def sid(*, case="cloudbed-1_q032", model="sonnet",
        harness="A1", stage="D", protocol=DRAFT_PROTOCOL):
    return f"{protocol}:{case}:{model}:{harness}:{stage}"


class RQ2V2IsolationPolicyTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)

    def test_destination_disjoint_from_v1_and_no_files_created(self):
        result = preview_v2_destination(
            data_dir=self.root, stage_id=sid()
        )
        self.assertEqual(result["protocol"], DRAFT_PROTOCOL)
        self.assertEqual(result["status"], "DRAFT_NOT_EXECUTABLE")
        self.assertEqual(result["stage"], "D")
        self.assertEqual(result["namespace"], str(self.root / ROOT_RELATIVE))
        self.assertEqual(
            Path(result["claim_path_preview"]).parent,
            self.root / CLAIMS_RELATIVE
        )
        self.assertEqual(
            Path(result["artifact_path_preview"]).parent,
            self.root / ARTIFACTS_RELATIVE
        )
        for preview in (result["claim_path_preview"],
                        result["artifact_path_preview"]):
            self.assertNotIn(self.root / "data/rq2", Path(preview).parents)
        self.assertFalse(result["can_write"])
        self.assertFalse(result["can_execute_api"])
        self.assertFalse(result["can_execute_test"])
        self.assertFalse(result["scientific_release_frozen"])
        self.assertEqual(result["data_files_written"], 0)
        self.assertEqual(result["provider_api_calls"], 0)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_preview_determinism_and_stages_get_distinct_paths(self):
        a = preview_v2_destination(data_dir=self.root, stage_id=sid())
        b = preview_v2_destination(data_dir=self.root, stage_id=sid())
        c = preview_v2_destination(data_dir=self.root, stage_id=sid(stage="C"))
        self.assertEqual(a, b)
        self.assertNotEqual(a["claim_path_preview"], c["claim_path_preview"])
        self.assertNotEqual(a["artifact_path_preview"], c["artifact_path_preview"])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_rejects_v1_stage_namespace_even_on_known_case(self):
        with self.assertRaisesRegex(RQ2V2IsolationError, "Unplanned"):
            preview_v2_destination(
                data_dir=self.root,
                stage_id="rq2_dryrun_workflow_preview_v0:cloudbed-1_q032:sonnet:A1:D",
            )

    def test_locked_ood_test_case_cannot_be_previewed(self):
        for case in ("cloudbed-1_q014", "cloudbed-2_q077"):
            with self.subTest(case=case):
                with self.assertRaisesRegex(RQ2V2IsolationError, "test-locked"):
                    preview_v2_destination(
                        data_dir=self.root, stage_id=sid(case=case)
                    )

    def test_injected_and_unplanned_stage_ids_refused(self):
        bad = (
            sid(case="cloudbed-1_q999"),
            sid(model="wrong-model"),
            sid(harness="A0"),
            sid(stage="TEST"),
            sid(stage="../D"),
            sid() + ":extra",
            "",
        )
        for value in bad:
            with self.subTest(stage_id=value):
                with self.assertRaises(RQ2V2IsolationError):
                    preview_v2_destination(data_dir=self.root, stage_id=value)

    def test_rejects_relative_string_and_traversal_data_root(self):
        for bad in (Path("relative"), str(self.root), self.root / ".."):
            with self.subTest(root=str(bad)):
                with self.assertRaises(RQ2V2IsolationError):
                    preview_v2_destination(data_dir=bad, stage_id=sid())

    def test_symlink_to_v2_namespace_rejected_without_creating_link(self):
        # Simula un symlink per essere portabile anche su Windows senza
        # privilegi Developer Mode.
        target = self.root / ROOT_RELATIVE
        def fake_is_symlink(value):
            return value == target
        with patch.object(Path, "is_symlink", fake_is_symlink):
            with self.assertRaisesRegex(RQ2V2IsolationError, "Symbolic link"):
                preview_v2_destination(data_dir=self.root, stage_id=sid())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_reject_non_str_id_and_no_unknown_files_created(self):
        for candidate in (None, [], 123):
            with self.subTest(candidate=candidate):
                with self.assertRaises(RQ2V2IsolationError):
                    preview_v2_destination(
                        data_dir=self.root, stage_id=candidate
                    )
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
