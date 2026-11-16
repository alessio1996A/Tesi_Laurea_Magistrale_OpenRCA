"""Test offline dell'inventario regole-catalogo (catalogo e regole sintetici)."""
import unittest

from evaluation import rq2_k_rule_inventory as inv


def _catalog():
    stats = lambda n: {"components": n, "step_seconds": 60.0, "coverage_min": 1.0}
    return {
        "aggregate": {"node": {"system.cpu.iowait": {}}, "container": {
            "container_start_time_seconds": {}, "container_cpu_cfs_throttled_seconds": {}}},
        "per_case": {
            "c1": {"components_total": {"node": 6, "container": 40}, "levels": {
                "node": {"system.cpu.iowait": stats(6)},
                "container": {"container_start_time_seconds": stats(38),
                              "container_cpu_cfs_throttled_seconds": stats(40)}}},
            "c2": {"components_total": {"node": 6, "container": 50}, "levels": {
                "node": {"system.cpu.iowait": stats(6)},
                "container": {"container_start_time_seconds": stats(50),
                              "container_cpu_cfs_throttled_seconds": stats(50)}}}},
    }


def _entry(metrics, outcome="candidate", name="r"):
    rule = {"rule_name": name, "hypothesized_fault_type": "x",
            "conditions": [{"metric": m} for m in metrics]}
    return {"stage_id": "c1:m:h:K", "case_id": "c1", "model": "m", "harness": "h",
            "outcome": outcome, "rule": rule if outcome == "candidate" else None}


class InventoryTests(unittest.TestCase):
    def test_supported_container_rule_reports_missing_components_per_case(self):
        item = inv.inventory_entry(_entry(["container_start_time_seconds"]), _catalog())
        self.assertEqual(item["support"], "nomi_presenti_a_livello_container")
        self.assertEqual(item["metrics"]["container_start_time_seconds"]["per_case"]["c1"],
                         {"level": "container", "with_metric": 38, "components_total": 40})

    def test_node_rule_and_two_metrics_same_level(self):
        self.assertEqual(inv.inventory_entry(_entry(["system.cpu.iowait"]), _catalog())["support"],
                         "nomi_presenti_a_livello_node")
        both = inv.inventory_entry(_entry(["container_start_time_seconds",
                                           "container_cpu_cfs_throttled_seconds"]), _catalog())
        self.assertEqual(both["support"], "nomi_presenti_a_livello_container")

    def test_log_trace_and_service_metrics_are_not_in_the_catalog(self):
        for metric in ("mrt_max", "log_adservice-service_application_errors",
                       "cartservice-0 trace span duration"):
            self.assertEqual(inv.inventory_entry(_entry([metric]), _catalog())["support"],
                             "metrica_non_nel_catalogo")

    def test_mixed_levels_and_one_absent_metric(self):
        mixed = inv.inventory_entry(_entry(["system.cpu.iowait", "container_start_time_seconds"]),
                                    _catalog())
        self.assertEqual(mixed["support"], "livelli_misti")
        partly = inv.inventory_entry(_entry(["system.cpu.iowait", "mrt_max"]), _catalog())
        self.assertEqual(partly["support"], "metrica_non_nel_catalogo")

    def test_only_candidates_are_listed_and_render_is_readable(self):
        entries = [_entry(["system.cpu.iowait"]), _entry([], outcome="insufficient_evidence")]
        items = inv.inventory(entries, _catalog())
        self.assertEqual(len(items), 1)
        text = inv.render(items)
        self.assertIn("Regole candidate: 1", text)
        self.assertIn("c1: 6/6 componenti node con il KPI", text)


if __name__ == "__main__":
    unittest.main()
