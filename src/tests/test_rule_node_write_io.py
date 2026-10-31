
import unittest
import pandas as pd

from harness.rules.rule_node_write_io import (
    WRITE_RATE,
    WRITE_AWAIT,
    valuta_r10_node_disk_write_io,
)

START = 1000
BASE_END = START + 12 * 60
END = START + 30 * 60
NODE = "node-1"


def crea_telemetria(valori, nodo=NODE):
    righe = []

    for i, valore in enumerate(valori):
        t = START + i * 60

        righe.append({
            "timestamp": t,
            "cmdb_id": nodo,
            "kpi_name": WRITE_RATE,
            "value": valore,
        })

        righe.append({
            "timestamp": t,
            "cmdb_id": nodo,
            "kpi_name": WRITE_AWAIT,
            "value": 0.5,
        })

    return pd.DataFrame(righe)


class TestR10(unittest.TestCase):

    def valuta(self, df):
        return valuta_r10_node_disk_write_io(
            df, NODE, START, BASE_END, END
        )

    def test_aumento_persistente(self):
        valori = [0] * 15 + [25] * 3 + [0] * 12

        esito = self.valuta(crea_telemetria(valori))

        self.assertEqual(
            esito["status"], "candidato_da_verificare"
        )
        self.assertEqual(
            esito["ipotesi"]["timestamp_primo_segnale_unix"],
            START + 15 * 60
        )

    def test_carico_alto_stabile(self):
        valori = [300] * 30

        esito = self.valuta(crea_telemetria(valori))

        self.assertEqual(
            esito["status"], "nessun_candidato"
        )

    def test_picco_isolato(self):
        valori = [0] * 30
        valori[16] = 150

        esito = self.valuta(crea_telemetria(valori))

        self.assertEqual(
            esito["status"], "nessun_candidato"
        )

    def test_baseline_insufficiente(self):
        valori = [0] * 12 + [25] * 18
        df = crea_telemetria(valori)

        df = df.loc[
            ~(
                (df["kpi_name"] == WRITE_RATE)
                & (df["timestamp"] < BASE_END - 5 * 60)
            )
        ]

        esito = self.valuta(df)

        self.assertEqual(
            esito["status"], "evidenza_insufficiente"
        )

    def test_gap_temporale(self):
        tempi = [START + i * 60 for i in range(12)]
        tempi += [BASE_END, BASE_END + 120, BASE_END + 240]

        valori = [0] * 12 + [25] * 3

        df = pd.DataFrame([
            {
                "timestamp": t,
                "cmdb_id": NODE,
                "kpi_name": WRITE_RATE,
                "value": v,
            }
            for t, v in zip(tempi, valori)
        ])

        esito = self.valuta(df)

        self.assertEqual(
            esito["status"], "nessun_candidato"
        )

    def test_duplicati(self):
        valori = [0] * 15 + [25] * 3 + [0] * 12
        df = crea_telemetria(valori)

        duplicato = df.loc[
            (df["kpi_name"] == WRITE_RATE)
            & (df["timestamp"] == START + 15 * 60)
        ]

        df = pd.concat([df, duplicato], ignore_index=True)

        esito = self.valuta(df)

        self.assertEqual(
            esito["status"], "candidato_da_verificare"
        )

    def test_valori_negativi(self):
        valori = [0] * 12 + [-1] + [25] * 17

        esito = self.valuta(crea_telemetria(valori))

        self.assertEqual(
            esito["status"], "evidenza_insufficiente"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
