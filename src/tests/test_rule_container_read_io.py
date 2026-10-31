"""Test offline R06 senza Gemini e senza dati reali/ground truth."""

import unittest

import pandas as pd

from harness.rules.rule_container_read_io import (
    READ_MB, READ_OPS, valuta_r06_container_read_io
)

START = 1_000_000
BASE_END = START + 12 * 60
END = START + 30 * 60
COMPONENTE = "node-6.example-0"


def df_di_prova(valori, ops=None, componente=COMPONENTE, *, step=60):
    t = [START + i * step for i in range(len(valori))]
    righe = [
        {"timestamp": ts, "cmdb_id": componente, "kpi_name": READ_MB, "value": v}
        for ts, v in zip(t, valori)
    ]
    if ops is not None:
        righe += [
            {"timestamp": ts, "cmdb_id": componente, "kpi_name": READ_OPS, "value": v}
            for ts, v in zip(t, ops)
        ]
    return pd.DataFrame(righe)


class TestR06ContainerReadIO(unittest.TestCase):
    def valuta(self, df, **kwargs):
        return valuta_r06_container_read_io(
            df, COMPONENTE, START, BASE_END, END, **kwargs
        )

    def test_01_baseline_zero_e_tre_campioni_persistenti(self):
        values = [0.0] * 12 + [0.0, 0.0, 3.0, 4.0, 5.0] + [0.0] * 13
        ops = [0.0] * 14 + [12, 15, 18] + [0.0] * 13
        esito = self.valuta(df_di_prova(values, ops=ops))
        self.assertEqual(esito["status"], "candidato_da_verificare")
        self.assertEqual(esito["ipotesi"]["timestamp_primo_segnale_unix"], START + 14 * 60)
        self.assertEqual(esito["ipotesi"]["campioni_consecutivi"], 3)
        self.assertEqual(esito["evidenze"]["operazioni_lettura_accessorie"]["campioni_positivi"], 3)

    def test_02_solo_picco_isolato_non_diventa_causa(self):
        values = [0.0] * 12 + [0.0, 8.0, 0.0, 9.0] + [0.0] * 14
        esito = self.valuta(df_di_prova(values))
        self.assertEqual(esito["status"], "nessun_candidato")
        self.assertEqual(esito["evidenze"]["campioni_reads_mb_oltre_soglia"], 2)

    def test_03_nessuna_attivita(self):
        esito = self.valuta(df_di_prova([0.0] * 30))
        self.assertEqual(esito["status"], "nessun_candidato")

    def test_04_baseline_insufficiente_astensione(self):
        vals = [float("nan")] * 9 + [0.0] * 3 + [10.0] * 18
        esito = self.valuta(df_di_prova(vals))
        self.assertEqual(esito["status"], "evidenza_insufficiente")

    def test_05_valori_negativi_astensione(self):
        esito = self.valuta(df_di_prova([0.0] * 12 + [-2.0] + [10.0] * 17))
        self.assertEqual(esito["status"], "evidenza_insufficiente")

    def test_06_gap_interrompe_persistenza(self):
        # 120s fra osservazioni: gap superiore a 1.5x della cadenza
        vals = [0.0] * 12 + [5.0, 5.0, 5.0]
        times = [START + i * 60 for i in range(12)] + [BASE_END, BASE_END + 60, BASE_END + 180]
        df = pd.DataFrame({"timestamp": times, "cmdb_id": COMPONENTE, "kpi_name": READ_MB, "value": vals})
        self.assertEqual(self.valuta(df)["status"], "nessun_candidato")

    def test_07_duplicati_medianati(self):
        vals = [0.0] * 12 + [4.0] * 3 + [0.0] * 15
        df = df_di_prova(vals)
        duplicate = df.loc[df["timestamp"].eq(START + 13 * 60)].copy()
        df = pd.concat([df, duplicate], ignore_index=True)
        self.assertEqual(self.valuta(df)["status"], "candidato_da_verificare")

    def test_08_validazione_schema(self):
        with self.assertRaises(ValueError):
            self.valuta(pd.DataFrame({"timestamp": [START]}))
        with self.assertRaises(ValueError):
            self.valuta(df_di_prova([0.0] * 30), incremento_minimo_mb=-1)
        with self.assertRaises(ValueError):
            self.valuta(df_di_prova([0.0] * 30), consecutivi_minimi=1)

    def test_09_evidenza_non_ground_truth(self):
        vals = [0.0] * 12 + [6.0] * 18
        esito = self.valuta(df_di_prova(vals))
        self.assertEqual(esito["status"], "candidato_da_verificare")
        self.assertEqual(esito["rule_id"], "R06")
        self.assertEqual(esito["classe_candidata"], "container read I/O load")
        self.assertIn("root cause", " ".join(esito["limitazioni"]))
        self.assertNotIn("root cause reason", esito)


if __name__ == "__main__":
    unittest.main()
