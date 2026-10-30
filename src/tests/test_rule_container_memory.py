"""Test sintetici offline di R02; non consultano Market o ground truth."""
import unittest
import pandas as pd

from harness.rules.rule_container_memory import (
    valuta_r02_container_memory,
    WORKING_SET, MEMORY_USAGE, MEMORY_LIMIT,
)

START = 1000
BASE_END = START + 12 * 60
END = START + 30 * 60
COMP = "node-5.example-0"


def campioni(working=None, usage=None, limit=128, step=60, component=COMP):
    working = working if working is not None else [40.0] * 12 + [42.0] * 18
    usage = usage if usage is not None else [45.0] * 12 + [47.0] * 18
    rows = []
    for name, values in ((WORKING_SET, working), (MEMORY_USAGE, usage)):
        for i, value in enumerate(values):
            rows.append({"timestamp": START + i * step, "cmdb_id": component,
                         "kpi_name": name, "value": value})
    if limit is not None:
        for i in range(len(working)):
            rows.append({"timestamp": START + i * step, "cmdb_id": component,
                         "kpi_name": MEMORY_LIMIT, "value": limit})
    return pd.DataFrame(rows)


def valuta(df, **kwargs):
    return valuta_r02_container_memory(df, COMP, START, BASE_END, END, **kwargs)


class TestR02(unittest.TestCase):
    def test_aumento_persistente(self):
        ws = [40.0] * 12 + [40.0] * 5 + [65.0] * 13
        usage = [45.0] * 12 + [45.0] * 5 + [70.0] * 13
        out = valuta(campioni(ws, usage))
        self.assertEqual(out["status"], "candidato_da_verificare")
        self.assertEqual(out["ipotesi"]["timestamp_primo_segnale_unix"], START + 17 * 60)
        self.assertEqual(out["ipotesi"]["campioni_consecutivi"], 3)
        self.assertTrue(out["evidenze"]["uso_memoria_accessorio"]["aumento_rispetto_baseline"])

    def test_senza_aumento(self):
        out = valuta(campioni())
        self.assertEqual(out["status"], "nessun_candidato")

    def test_un_picco_isolato(self):
        ws = [40.0] * 12 + [42.0] * 18
        ws[17] = 100.0
        out = valuta(campioni(working=ws))
        self.assertEqual(out["status"], "nessun_candidato")
        self.assertEqual(out["evidenze"]["campioni_working_set_oltre_soglia"], 1)

    def test_baseline_incompleta(self):
        ws = [40.0] * 12 + [65.0] * 18
        df = campioni(working=ws)
        df = df.loc[~((df["kpi_name"] == WORKING_SET)
                      & (df["timestamp"] < BASE_END - 5*60))]
        self.assertEqual(valuta(df)["status"], "evidenza_insufficiente")

    def test_gap_temporale_interrompe_persistenza(self):
        ws = [40.0]*12 + [65.0]*18
        df = campioni(working=ws)
        df = df.loc[
            (df["kpi_name"] != WORKING_SET)
            | (df["timestamp"] < BASE_END)
            | (((df["timestamp"] - BASE_END) % 180) == 0)
        ]
        # Ci sono almeno 3 campioni di ricerca, ma non consecutivi a 60s.
        self.assertEqual(valuta(df)["status"], "nessun_candidato")

    def test_duplicati_aggregati_senza_sommare(self):
        ws = [40.0]*12 + [75.0]*18
        df = campioni(working=ws)
        duplicate = df.loc[(df["kpi_name"] == WORKING_SET)
                           & (df["timestamp"] == BASE_END)].copy()
        out = valuta(pd.concat([df, duplicate], ignore_index=True))
        self.assertEqual(out["status"], "candidato_da_verificare")

    def test_limite_non_e_diagnosi_automatica(self):
        ws = [40.0]*12 + [44.0]*18
        out = valuta(campioni(working=ws, limit=32))
        self.assertEqual(out["status"], "nessun_candidato")

    def test_limite_ambiguo_segnalato(self):
        ws = [40.0]*12 + [85.0]*18
        out = valuta(campioni(working=ws, limit=64))
        self.assertEqual(out["status"], "candidato_da_verificare")
        self.assertTrue(out["evidenze"]["limite_memoria_accessorio"]["rapporto_maggiore_di_uno"])
        self.assertTrue(any("semantica" in msg.lower() for msg in out["limitazioni"]))

    def test_input_incompleto(self):
        with self.assertRaises(ValueError):
            valuta(pd.DataFrame({"timestamp": [START]}))


if __name__ == "__main__":
    unittest.main()
