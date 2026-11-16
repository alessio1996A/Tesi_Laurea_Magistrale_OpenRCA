"""Test offline del catalogo KPI discovery (dati completamente sintetici).

Nessuna API, nessun Market.zip reale, nessun caso sigillato.
"""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import pandas as pd

from agent.tools import _get_telemetry_csv_paths
from evaluation import rq2_k_catalog as cat

START = 1647748800          # inizio finestra sintetica (secondi Unix)
WINDOW = 1800               # 30 minuti, come i casi OpenRCA
END = START + WINDOW


def _rows(cmdb_id, kpi, step=60, skip=(), start=START, end=END):
    """Righe sintetiche a passo fisso; 'skip' = indici dei campioni mancanti."""
    out = []
    for i, ts in enumerate(range(start, end, step)):
        if i in skip:
            continue
        out.append({"timestamp": ts, "cmdb_id": cmdb_id, "kpi_name": kpi,
                    "value": float(i)})
    return out


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "data/processed").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _manifest(self, cases, extra_columns=None):
        rows = []
        for case_id, cloudbed in cases:
            row = {"case_id": case_id, "cloudbed": cloudbed,
                   "start_unix": START, "end_unix": END}
            row.update(extra_columns or {})
            rows.append(row)
        path = self.root / cat.MANIFEST_RELATIVE
        pd.DataFrame(rows).to_csv(path, index=False)
        return path

    def _zip(self, content):
        """content: {(cloudbed, kind): [righe]} -> Market.zip sintetico."""
        path = self.root / "Market.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for (cloudbed, kind), rows in content.items():
                name = _get_telemetry_csv_paths(START, END, cloudbed, kind)[0]
                frame = pd.DataFrame(rows, columns=cat.COLUMNS)
                archive.writestr(name, frame.to_csv(index=False))
        return path

    def test_step_and_coverage_with_missing_samples(self):
        manifest = self._manifest([("cloudbed-1_q032", "cloudbed-1")])
        rows = (_rows("node-1", "cpu") + _rows("node-2", "cpu", skip=range(10)))
        zip_path = self._zip({("cloudbed-1", "node_metrics"): rows,
                              ("cloudbed-1", "container_metrics"): []})
        catalog = cat.build_catalog(zip_path, manifest, ("cloudbed-1_q032",))
        stats = catalog["per_case"]["cloudbed-1_q032"]["levels"]["node"]["cpu"]
        self.assertEqual(stats["components"], 2)
        self.assertEqual(stats["step_seconds"], 60.0)
        self.assertAlmostEqual(stats["coverage_min"], 20 / 30)
        self.assertEqual(stats["coverage_median"], (1.0 + 20 / 30) / 2)

    def test_levels_are_separate(self):
        manifest = self._manifest([("cloudbed-1_q032", "cloudbed-1")])
        zip_path = self._zip({
            ("cloudbed-1", "node_metrics"): _rows("node-1", "node_cpu"),
            ("cloudbed-1", "container_metrics"): _rows("node-1.svc-0", "ctr_cpu"),
        })
        catalog = cat.build_catalog(zip_path, manifest, ("cloudbed-1_q032",))
        self.assertEqual(list(catalog["aggregate"]["node"]), ["node_cpu"])
        self.assertEqual(list(catalog["aggregate"]["container"]), ["ctr_cpu"])

    def test_kpi_present_in_one_cloudbed_only(self):
        manifest = self._manifest([("cloudbed-1_q032", "cloudbed-1"),
                                   ("cloudbed-2_q026", "cloudbed-2")])
        zip_path = self._zip({
            ("cloudbed-1", "node_metrics"): _rows("node-1", "shared") + _rows("node-1", "only1"),
            ("cloudbed-1", "container_metrics"): [],
            ("cloudbed-2", "node_metrics"): _rows("node-1", "shared"),
            ("cloudbed-2", "container_metrics"): [],
        })
        catalog = cat.build_catalog(zip_path, manifest,
                                    ("cloudbed-1_q032", "cloudbed-2_q026"))
        node = catalog["aggregate"]["node"]
        self.assertEqual(node["shared"]["cloudbeds"], ["cloudbed-1", "cloudbed-2"])
        self.assertEqual(node["only1"]["cloudbeds"], ["cloudbed-1"])

    def test_samples_outside_window_are_ignored(self):
        manifest = self._manifest([("cloudbed-1_q032", "cloudbed-1")])
        rows = _rows("node-1", "cpu") + _rows("node-1", "cpu", start=END, end=END + 600)
        zip_path = self._zip({("cloudbed-1", "node_metrics"): rows,
                              ("cloudbed-1", "container_metrics"): []})
        catalog = cat.build_catalog(zip_path, manifest, ("cloudbed-1_q032",))
        stats = catalog["per_case"]["cloudbed-1_q032"]["levels"]["node"]["cpu"]
        self.assertEqual(stats["coverage_min"], 1.0)   # i campioni dopo END non contano

    def test_non_discovery_case_is_refused_before_any_read(self):
        manifest = self._manifest([("cloudbed-1_q014", "cloudbed-1")])
        missing_zip = self.root / "non_esiste.zip"       # se lo aprisse, fallirebbe diversamente
        with self.assertRaises(cat.CatalogScopeError):
            cat.build_catalog(missing_zip, manifest, ("cloudbed-1_q014",))

    def test_manifest_with_ground_truth_columns_is_refused(self):
        manifest = self._manifest([("cloudbed-1_q032", "cloudbed-1")],
                                  extra_columns={"reason": "x"})
        with self.assertRaises(cat.CatalogScopeError):
            cat.load_case(manifest, "cloudbed-1_q032")

    def test_discovery_cases_are_exactly_the_four_declared(self):
        self.assertEqual(set(cat.DISCOVERY_CASES), {
            "cloudbed-1_q032", "cloudbed-1_q050", "cloudbed-2_q026", "cloudbed-2_q045"})

    def test_write_is_create_only_and_records_digest(self):
        catalog = {"version": cat.VERSION, "cases": [], "per_case": {}, "aggregate": {},
                   "median_step_seconds_by_level": {}}
        target = cat.write_catalog(self.root / "out", catalog, "abc123")
        saved = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(saved["code_commit"], "abc123")
        self.assertEqual(len(saved["sha256_of_body_without_this_field"]), 64)
        with self.assertRaises(FileExistsError):
            cat.write_catalog(self.root / "out", catalog, "abc123")

    def test_format_reports_horizon_as_calculation_not_decision(self):
        manifest = self._manifest([("cloudbed-1_q032", "cloudbed-1")])
        zip_path = self._zip({("cloudbed-1", "node_metrics"): _rows("node-1", "cpu"),
                              ("cloudbed-1", "container_metrics"): []})
        catalog = cat.build_catalog(zip_path, manifest, ("cloudbed-1_q032",))
        text = cat.format_catalog(catalog)
        self.assertIn("H = 5 x passo = 300s", text)
        self.assertIn("da approvare", text)


if __name__ == "__main__":
    unittest.main()
