"""Synthetic V3-result-only compatibility audit tests. Never touch Market."""
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.rq2_historical_trajectory_audit import (
    SUBDIR, HistoryAuditError, audit_history,
)


def output_dir(root: Path) -> Path:
    path = root / SUBDIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def result(trajectory=None, error=None):
    return {
        "variant": "A1",
        "tool_trajectory": (
            [
                {"tipo": "tool_call", "nome": "tool_get_node_metrics",
                 "parametri": {"start_unix": 100, "end_unix": 200}},
                {"tipo": "tool_result", "nome": "tool_get_node_metrics",
                 "risposta": "cpu=0.55 synthetic observation"},
            ] if trajectory is None else trajectory
        ),
        "error": error,
        "raw_response": '{"1":{"root cause reason":"synthetic"}}',
    }


class RQ2HistoricalTrajectoryAuditTests(unittest.TestCase):
    def test_missing_frozen_directory_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(HistoryAuditError, "missing"):
                audit_history(Path(td))

    def test_empty_dir_has_no_invented_records(self):
        with tempfile.TemporaryDirectory() as td:
            output_dir(Path(td))
            report = audit_history(Path(td))
        self.assertEqual(report["counts"], {})
        self.assertEqual(report["status"], "HISTORICAL_COMPATIBILITY_ONLY")
        self.assertFalse(report["read_ground_truth"])
        self.assertEqual(report["model_api_calls"], 0)
        self.assertFalse(report["files_written"])

    def test_simple_legacy_result_is_usable(self):
        with tempfile.TemporaryDirectory() as td:
            output_dir(Path(td)).joinpath("synthetic_result.json").write_text(
                json.dumps(result()), encoding="utf-8"
            )
            report = audit_history(Path(td))
        self.assertEqual(report["counts"]["result_records_with_trajectory"], 1)
        self.assertEqual(report["counts"]["bundle_structurally_usable"], 1)
        self.assertEqual(report["counts"]["observations"], 1)
        self.assertEqual(report["incompatibility_reasons"], {})

    def test_nested_result_envelope_supported(self):
        with tempfile.TemporaryDirectory() as td:
            output_dir(Path(td)).joinpath("synthetic_result.json").write_text(
                json.dumps({"result": result()}), encoding="utf-8"
            )
            report = audit_history(Path(td))
        self.assertEqual(report["counts"]["result_records_with_trajectory"], 1)
        self.assertEqual(report["counts"]["bundle_structurally_usable"], 1)

    def test_parallel_legacy_same_tool_is_not_usable(self):
        events = [
            {"tipo": "tool_call", "nome": "tool_get_node_metrics", "parametri": {"x": 1}},
            {"tipo": "tool_call", "nome": "tool_get_node_metrics", "parametri": {"x": 2}},
            {"tipo": "tool_result", "nome": "tool_get_node_metrics", "risposta": "?"}
        ]
        with tempfile.TemporaryDirectory() as td:
            output_dir(Path(td)).joinpath("synthetic_result.json").write_text(
                json.dumps(result(trajectory=events)), encoding="utf-8"
            )
            report = audit_history(Path(td))
        self.assertEqual(report["counts"]["bundle_not_usable"], 1)
        self.assertEqual(report["counts"]["bundle_structurally_usable"], 0)
        self.assertTrue(any("Ambiguous" in key for key in
                            report["incompatibility_reasons"]))

    def test_malformed_json_counted_without_reading_scoring(self):
        with tempfile.TemporaryDirectory() as td:
            output_dir(Path(td)).joinpath("bad_result.json").write_bytes(b'{broken')
            report = audit_history(Path(td))
        self.assertEqual(report["counts"]["unparseable_files"], 1)
        self.assertEqual(report["counts"]["result_records_with_trajectory"], 0)

    def test_unrelated_json_in_known_result_dir_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            output_dir(Path(td)).joinpath("claim.json").write_text(
                json.dumps({"status": "COMPLETE"}), encoding="utf-8"
            )
            report = audit_history(Path(td))
        self.assertEqual(report["counts"]["other_json_files"], 1)
        self.assertEqual(report["counts"]["result_records_with_trajectory"], 0)

    def test_top_level_ground_truth_field_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            item = result()
            item["ground_truth"] = "synthetic forbidden label"
            output_dir(Path(td)).joinpath("bad_result.json").write_text(
                json.dumps(item), encoding="utf-8"
            )
            with self.assertRaisesRegex(HistoryAuditError, "scoring/GT"):
                audit_history(Path(td))

    def test_empty_trajectory_is_counted_not_fabricated(self):
        with tempfile.TemporaryDirectory() as td:
            output_dir(Path(td)).joinpath("empty_result.json").write_text(
                json.dumps(result(trajectory=[])), encoding="utf-8"
            )
            report = audit_history(Path(td))
        self.assertEqual(report["counts"]["empty_bundles"], 1)
        self.assertEqual(report["counts"]["observations"], 0)

    def test_runner_error_is_distinguished_from_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            output_dir(Path(td)).joinpath("fail_result.json").write_text(
                json.dumps(result(error="synthetic provider error")), encoding="utf-8"
            )
            report = audit_history(Path(td))
        self.assertEqual(report["counts"]["runner_error_results"], 1)
        self.assertEqual(report["counts"]["bundle_structurally_usable"], 1)

    def test_never_reads_sibling_scoring_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output_dir(root).joinpath("good.json").write_text(
                json.dumps(result()), encoding="utf-8"
            )
            scoring = root / "data" / "results" / "scoring" / "v2" / "fake"
            scoring.mkdir(parents=True)
            (scoring / "gt.json").write_text(
                json.dumps({"ground_truth": "secret"}), encoding="utf-8"
            )
            report = audit_history(root)
        self.assertEqual(report["counts"]["json_files"], 1)
        self.assertFalse(report["read_scoring"])

    def test_does_not_modify_original_files(self):
        with tempfile.TemporaryDirectory() as td:
            path = output_dir(Path(td)) / "immutable.json"
            before = json.dumps(result()).encode("utf-8")
            path.write_bytes(before)
            audit_history(Path(td))
            after = path.read_bytes()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
