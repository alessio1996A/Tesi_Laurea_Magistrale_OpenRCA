"""Test sintetici offline: non consultano alcuna etichetta OpenRCA."""
import unittest
import pandas as pd

from harness.rules.rule_container_cpu import valuta_r01_container_cpu


COMP = "container-sintetico"
START = 1000
CUT = 1600
END = 2200


def make_df(cpu_base, cpu_after, cfs=False):
    ts = list(range(START, END, 60))
    values = list(cpu_base) + list(cpu_after)
    assert len(ts) == len(values)
    rows = [
        {"timestamp": t, "cmdb_id": COMP,
         "kpi_name": "container_cpu_usage_seconds", "value": v}
        for t, v in zip(ts, values)
    ]
    if cfs:
        for t in ts:
            rows.append({"timestamp": t, "cmdb_id": COMP,
                         "kpi_name": "container_cpu_cfs_periods", "value": 100.0})
            rows.append({"timestamp": t, "cmdb_id": COMP,
                         "kpi_name": "container_cpu_cfs_throttled_periods",
                         "value": 3.0 if t >= CUT else 0.0})
    return pd.DataFrame(rows)


class TestR01(unittest.TestCase):
    def test_persistent_shift_candidates(self):
        df = make_df([.09, .1, .11, .1, .09, .11, .1, .09, .11, .1],
                     [.1, .11, .6, .7, .8, .7, .6, .1, .1, .1], cfs=True)
        res = valuta_r01_container_cpu(df, COMP, START, CUT, END)
        self.assertEqual(res["status"], "candidato_da_verificare")
        self.assertEqual(res["ipotesi"]["timestamp_primo_segnale_unix"], 1720)
        self.assertEqual(res["evidenze"]["cfs"]["rapporti_positivi"], 3)

    def test_isolated_spike_not_candidate(self):
        df = make_df([.09, .1, .11, .1, .09, .11, .1, .09, .11, .1],
                     [.1, .11, .6, .1, .1, .1, .1, .1, .1, .1])
        self.assertEqual(valuta_r01_container_cpu(df, COMP, START, CUT, END)["status"],
                         "nessun_candidato")

    def test_flat_baseline_abstains(self):
        df = make_df([0.0] * 10, [.8] * 10)
        self.assertEqual(valuta_r01_container_cpu(df, COMP, START, CUT, END)["status"],
                         "evidenza_insufficiente")

    def test_outside_interval_ignored(self):
        df = make_df([.09, .1, .11, .1, .09, .11, .1, .09, .11, .1], [.1] * 10)
        extra = pd.DataFrame([{"timestamp": END + 60, "cmdb_id": COMP,
                               "kpi_name": "container_cpu_usage_seconds", "value": 999.0}])
        df = pd.concat([df, extra], ignore_index=True)
        self.assertEqual(valuta_r01_container_cpu(df, COMP, START, CUT, END)["status"],
                         "nessun_candidato")

    def test_invalid_cfs_ratio_reported_not_clipped(self):
        df = make_df([.09, .1, .11, .1, .09, .11, .1, .09, .11, .1],
                     [.1, .11, .6, .7, .8, .7, .6, .1, .1, .1], cfs=True)
        ix = ((df["kpi_name"] == "container_cpu_cfs_throttled_periods")
              & (df["timestamp"] == 1720))
        df.loc[ix, "value"] = 200.0
        res = valuta_r01_container_cpu(df, COMP, START, CUT, END)
        self.assertEqual(res["evidenze"]["cfs"]["rapporti_maggiori_di_uno"], 1)
        self.assertEqual(res["evidenze"]["cfs"]["rapporti_ammissibili"], 2)

    def test_invalid_window_rejected(self):
        df = make_df([.09, .1, .11, .1, .09, .11, .1, .09, .11, .1], [.1] * 10)
        with self.assertRaises(ValueError):
            valuta_r01_container_cpu(df, COMP, START, START, END)


if __name__ == "__main__":
    unittest.main()
