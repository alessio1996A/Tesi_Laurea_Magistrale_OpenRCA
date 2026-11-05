"""Pure offline tests of targeted Pandas warning elimination.

Do not read Market.zip, use API keys, or modify output artifacts.
The regex semantics (including capturing groups and backreferences)
must stay byte-for-byte the same; only the warning emission changes.
"""
import re
import unittest
import warnings

import pandas as pd

from agent.tools import _kpi_regex_contains


class TestKpiWarningStability(unittest.TestCase):
    def test_capturing_groups_preserve_mask_without_warning(self):
        series = pd.Series([
            "container_cpu_usage", "MEMORY_RSS", "disk_io",
            None, "cpu throttled", "", "memory_pressure",
        ])
        pattern = re.compile(r"(cpu|memory)", re.IGNORECASE)

        with warnings.catch_warnings(record=True) as old_warnings:
            warnings.simplefilter("always")
            original = series.astype(str).str.contains(
                pattern, na=False
            )
        self.assertGreaterEqual(len(old_warnings), 1)

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            updated = _kpi_regex_contains(series, pattern)

        self.assertEqual(original.tolist(), updated.tolist())
        self.assertEqual(captured, [])

    def test_backreference_regex_is_not_rewritten(self):
        series = pd.Series(["cpu-cpu", "cpu-memory", "MEMORY-memory",
                            "cpu-cpu-memory", "disk-disk"])
        pattern = re.compile(r"(cpu|memory)-\1", re.IGNORECASE)
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            baseline = series.astype(str).str.contains(
                pattern, na=False
            )
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            revised = _kpi_regex_contains(series, pattern)
        self.assertEqual(baseline.tolist(), revised.tolist())
        self.assertEqual(captured, [])

    def test_non_group_regex_identical(self):
        series = pd.Series(["load5", "load_1", "CPU_usage", None])
        pattern = re.compile(r"load.*", re.IGNORECASE)
        before = series.astype(str).str.contains(pattern, na=False)
        after = _kpi_regex_contains(series, pattern)
        self.assertEqual(before.tolist(), after.tolist())


if __name__ == "__main__":
    unittest.main(verbosity=2)
