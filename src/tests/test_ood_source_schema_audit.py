"""Test sintetici del solo schema CSV: nessuna API e nessuna GT reale."""
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from evaluation.ood_source_schema_audit import inspect_schema


class SourceSchemaAuditTests(unittest.TestCase):
    def make_archive(self, root: Path) -> Path:
        path = root / "Market.zip"
        with ZipFile(path, "w", compression=ZIP_DEFLATED) as z:
            for cb in ("cloudbed-1", "cloudbed-2"):
                for base in ("query.csv", "record.csv"):
                    z.writestr(
                        f"Market/{cb}/{base}",
                        "time,reason,component\n1,SECRET_FAULT,SECRET_SERVICE\n",
                    )
            z.writestr("Market/cloudbed-1/telemetry/log.csv", "fault\nSECRET\n")
        (root / "record.csv").write_text(
            "reason,component\nROOT_SECRET,INSTANCE\n", encoding="utf-8"
        )
        return path

    def test_headers_no_rows_no_telemetry(self):
        with tempfile.TemporaryDirectory() as temp:
            self.make_archive(Path(temp))
            result = inspect_schema(Path(temp))
        self.assertEqual(result["total_archive_csv_matches"], 4)
        self.assertTrue(all(
            x["columns"] == ["time", "reason", "component"]
            for x in result["archive_csv_headers"]
        ))
        self.assertEqual(len(result["root_csv_headers"]), 1)
        self.assertEqual(
            result["root_csv_headers"][0]["provenance"],
            "root_drive_unattributed_to_cloudbed",
        )
        self.assertFalse(result["read_ground_truth_values"])
        self.assertFalse(result["read_telemetry"])
        self.assertEqual(result["model_api_calls"], 0)
        self.assertFalse(result["files_written"])
        self.assertNotIn("SECRET_FAULT", str(result))
        self.assertNotIn("ROOT_SECRET", str(result))
        self.assertNotIn("telemetry", str(result["archive_csv_headers"]))

    def test_duplicate_header_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Market.zip"
            with ZipFile(path, "w", compression=ZIP_DEFLATED) as z:
                z.writestr("Market/cloudbed-1/query.csv", "reason,reason\nsecret,secret\n")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                inspect_schema(Path(temp))

    def test_missing_archive_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):
                inspect_schema(Path(temp))

    def test_schema_from_zip_with_missing_root_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Market.zip"
            with ZipFile(path, "w") as z:
                z.writestr("Market/cloudbed-2/record.csv", "a,b\n1,2\n")
            data = inspect_schema(Path(temp))
        self.assertEqual(data["root_csv_headers"], [])
        self.assertEqual(data["archive_csv_headers"][0]["columns"], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
