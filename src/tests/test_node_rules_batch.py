"""Offline synthetic tests for node R07/R08/R11; no Market labels or model calls."""
import unittest
import pandas as pd
from harness.rules.rule_node_cpu_load import valuta_r07_node_cpu_load, CPU_USAGE, CPU_IOWAIT
from harness.rules.rule_node_memory import valuta_r08_node_memory, MEM_PCT, MEM_USED
from harness.rules.rule_node_disk_space import valuta_r11_node_disk_space, DISK_PCT, DISK_USED

S, B, E = 1000, 1720, 2800
NODE = "node-5"
CASES = [
    (valuta_r07_node_cpu_load, CPU_USAGE, CPU_IOWAIT, 20., 35.),
    (valuta_r08_node_memory, MEM_PCT, MEM_USED, 40., 55.),
    (valuta_r11_node_disk_space, DISK_PCT, DISK_USED, 50., 55.),
]

def sample(primary, aux, base_value, elevated_value, event=True, node=NODE):
    vals = [base_value]*12 + ([base_value]*4 + [elevated_value]*14 if event else [base_value]*18)
    data = []
    for kpi, data_values in ((primary, vals), (aux, vals)):
        for i, value in enumerate(data_values):
            data.append(dict(timestamp=S+i*60, cmdb_id=node, kpi_name=kpi, value=value))
    return pd.DataFrame(data)

class TestNodeRules(unittest.TestCase):
    def test_persistent_candidates(self):
        for fn, primary, aux, base, high in CASES:
            with self.subTest(fn=fn.__name__):
                out=fn(sample(primary, aux, base, high), NODE, S, B, E)
                self.assertEqual(out['status'], 'candidato_da_verificare')
                self.assertEqual(out['ipotesi']['campioni_consecutivi'], 3)
                self.assertEqual(out['ipotesi']['timestamp_primo_segnale_unix'], B+4*60)

    def test_stable_no_candidate(self):
        for fn, primary, aux, base, high in CASES:
            with self.subTest(fn=fn.__name__):
                out=fn(sample(primary, aux, base, high, False), NODE, S, B, E)
                self.assertEqual(out['status'], 'nessun_candidato')

    def test_single_spike_does_not_trigger(self):
        for fn, primary, aux, base, high in CASES:
            with self.subTest(fn=fn.__name__):
                df=sample(primary, aux, base, high, False)
                df.loc[(df.kpi_name == primary) & (df.timestamp == B+4*60), 'value'] = high
                out=fn(df, NODE, S, B, E)
                self.assertEqual(out['status'], 'nessun_candidato')

    def test_baseline_missing_abstains(self):
        for fn, primary, aux, base, high in CASES:
            with self.subTest(fn=fn.__name__):
                df=sample(primary, aux, base, high)
                df=df.loc[~((df.kpi_name == primary) & (df.timestamp < B-5*60))]
                out=fn(df, NODE, S, B, E)
                self.assertEqual(out['status'], 'evidenza_insufficiente')

    def test_duplicate_median_does_not_double_count(self):
        for fn, primary, aux, base, high in CASES:
            with self.subTest(fn=fn.__name__):
                df=sample(primary, aux, base, high)
                repeated=df.loc[(df.kpi_name == primary) & (df.timestamp == B+4*60)]
                out=fn(pd.concat([df, repeated], ignore_index=True), NODE, S, B, E)
                self.assertEqual(out['status'], 'candidato_da_verificare')

    def test_interrupted_streak_does_not_trigger(self):
        for fn, primary, aux, base, high in CASES:
            with self.subTest(fn=fn.__name__):
                df=sample(primary, aux, base, high)
                # Only every third search timestamp: gaps 180s, above max gap 90s.
                df=df.loc[(df.kpi_name != primary) | (df.timestamp < B) | (((df.timestamp - B) % 180) == 0)]
                out=fn(df, NODE, S, B, E)
                self.assertEqual(out['status'], 'nessun_candidato')

    def test_nonfinite_readings_are_excluded(self):
        fn, primary, aux, base, high = CASES[0]
        df=sample(primary, aux, base, high)
        df.loc[(df.kpi_name == primary) & (df.timestamp == B+5*60), 'value'] = float('inf')
        self.assertEqual(fn(df, NODE, S, B, E)['status'], 'candidato_da_verificare')

    def test_other_node_not_used(self):
        fn, primary, aux, base, high = CASES[1]
        df=sample(primary, aux, base, high, node='node-6')
        self.assertEqual(fn(df, NODE, S, B, E)['status'], 'evidenza_insufficiente')

    def test_invalid_time(self):
        fn, primary, aux, base, high = CASES[0]
        with self.assertRaises(ValueError):
            fn(sample(primary, aux, base, high), NODE, B, S, E)

    def test_negative_values_abstain(self):
        fn, primary, aux, base, high = CASES[0]
        df=sample(primary, aux, base, high)
        df.loc[(df.kpi_name == primary) & (df.timestamp == B), 'value'] = -1
        self.assertEqual(fn(df, NODE, S, B, E)['status'], 'evidenza_insufficiente')

if __name__ == '__main__':
    unittest.main(verbosity=2)
