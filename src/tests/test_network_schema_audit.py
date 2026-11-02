"""Test offline: soltanto ZIP sintetici, mai Market o ground truth reali."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from evaluation.network_schema_audit import inspect_schema


class TestNetworkSchemaAudit(unittest.TestCase):
    def test_whitelist_and_schema_variants(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Market.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("Market/record.csv",
                           "fault_label,secret\nA,DO_NOT_READ\n")
                z.writestr(
                    "Market/cloudbed-1/telemetry/2022_03_20/metric/metric_container.csv",
                    "timestamp,cmdb_id,kpi_name,value\n123,svc,secret,7\n",
                )
                z.writestr(
                    "Market/cloudbed-1/telemetry/2022_03_21/metric/metric_container.csv",
                    "timestamp,cmdb_id,kpi_name,value,unit\n124,svc,secret,2,ms\n",
                )
                z.writestr(
                    "Market/cloudbed-2/telemetry/2022_03_21/trace/trace_span.csv",
                    "timestamp,trace_id,parent_span,duration\n123,abc,def,500\n",
                )
                z.writestr("Market/cloudbed-1/telemetry/2022_03_20/answers.csv",
                           "ground_truth\nSECRET\n")
            result = inspect_schema(path)
            self.assertFalse(result["ground_truth_read"])
            self.assertFalse(result["kpi_values_read"])
            self.assertEqual(result["allowed_telemetry_files_scanned"], 3)
            self.assertEqual(result["zip_member_count"], 5)
            row = next(
                r for r in result["sources"]
                if r["cloudbed"] == "cloudbed-1"
                and r["source"] == "metric/metric_container.csv"
            )
            self.assertEqual(row["files_found"], 2)
            self.assertEqual(len(row["schema_variants"]), 2)
            self.assertNotIn("DO_NOT_READ", str(result))
            self.assertNotIn("SECRET", str(result))

    def test_missing_zip_raises(self):
        with self.assertRaises(FileNotFoundError):
            inspect_schema("__impossible__.zip")

    def test_rejects_malformed_header(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Market.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr(
                    "Market/cloudbed-2/telemetry/2022_03_20/metric/metric_mesh.csv",
                    "incomplete_header_without_newline",
                )
            with self.assertRaises(ValueError):
                inspect_schema(path)


if __name__ == "__main__":
    unittest.main()
