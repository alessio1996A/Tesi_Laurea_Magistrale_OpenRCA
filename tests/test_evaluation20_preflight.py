"""Test puri e offline del selettore evaluation20: nessuna API o dataset."""
import unittest

from evaluation.evaluation20_preflight import choose_balanced


def make_rows():
    rows = []
    for cb in (1, 2):
        for i in range(10):
            start = 1647700000 + i * 1900
            rows.append({
                "case_id": f"cloudbed-{cb}_q{i:03d}",
                "cloudbed": f"cloudbed-{cb}",
                "start_unix": str(start),
                "end_unix": str(start + 1800),
                "task_index": f"task_{(i % 7) + 1}",
                "requested_fault_count": 2 if i == 0 else 1,
            })
    return rows


class Evaluation20SelectionTests(unittest.TestCase):
    def test_balanced_20_is_deterministic(self):
        rows = make_rows()
        first = choose_balanced(rows, 20)
        second = choose_balanced(list(reversed(rows)), 20)
        self.assertIsNotNone(first)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 20)
        self.assertEqual(sum(x["cloudbed"] == "cloudbed-1"
                             for x in first), 10)
        self.assertEqual(sum(x["cloudbed"] == "cloudbed-2"
                             for x in first), 10)

    def test_19_are_not_enough(self):
        self.assertIsNone(choose_balanced(make_rows()[:19], 20))

    def test_overlap_blocks_selection(self):
        rows = make_rows()
        rows[1]["start_unix"] = rows[0]["start_unix"]
        rows[1]["end_unix"] = rows[0]["end_unix"]
        self.assertIsNone(choose_balanced(rows, 20))

    def test_missing_task_blocks_selection(self):
        rows = make_rows()
        for row in rows:
            row["task_index"] = "task_1"
        self.assertIsNone(choose_balanced(rows, 20))

    def test_multifault_required_per_cloudbed(self):
        rows = make_rows()
        for row in rows:
            row["requested_fault_count"] = 1
        self.assertIsNone(choose_balanced(rows, 20))

    def test_duplicate_id_is_rejected(self):
        rows = make_rows()
        rows[1]["case_id"] = rows[0]["case_id"]
        with self.assertRaises(ValueError):
            choose_balanced(rows, 20)

    def test_invalid_target_is_rejected(self):
        with self.assertRaises(ValueError):
            choose_balanced(make_rows(), 7)


if __name__ == "__main__":
    unittest.main()
