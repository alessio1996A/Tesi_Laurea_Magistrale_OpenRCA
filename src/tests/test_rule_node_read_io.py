
import unittest
import pandas as pd

from harness.rules.rule_node_read_io import (
    READ_RATE,
    READ_THROUGHPUT,
    valuta_r09_node_disk_read_io,
)


START = 1000
BASE_END = START + 12 * 60
END = START + 30 * 60

NODE = "node-1"


def crea_telemetria(valori, nodo=NODE):
    righe = []

    for i, valore in enumerate(valori):
        timestamp = START + i * 60

        righe.append({
            "timestamp": timestamp,
            "cmdb_id": nodo,
            "kpi_name": READ_RATE,
            "value": valore,
        })

        righe.append({
            "timestamp": timestamp,
            "cmdb_id": nodo,
            "kpi_name": READ_THROUGHPUT,
            "value": valore * 8,
        })

    return pd.DataFrame(righe)


class TestR09(unittest.TestCase):

    def valuta(self, df):
        return valuta_r09_node_disk_read_io(
            df, NODE, START, BASE_END, END
        )

    def test_incremento_persistente(self):
        valori = [0] * 15 + [20] * 3 + [0] * 12

        esito = self.valuta(crea_telemetria(valori))

        self.assertEqual(
            esito["status"], "candidato_da_verificare"
        )
        self.assertEqual(
            esito["ipotesi"]["campioni_consecutivi"], 3
        )
        self.assertEqual(
            esito["ipotesi"]["timestamp_primo_segnale_unix"],
            START + 15 * 60
        )

    def test_carico_alto_ma_stabile(self):
        valori = [300] * 30

        esito = self.valuta(crea_telemetria(valori))

        self.assertEqual(
            esito["status"], "nessun_candidato"
        )

    def test_picco_isolato(self):
        valori = [0] * 30
        valori[17] = 150

        esito = self.valuta(crea_telemetria(valori))

        self.assertEqual(
            esito["status"], "nessun_candidato"
        )

    def test_baseline_insufficiente(self):
        valori = [0] * 12 + [20] * 18
        df = crea_telemetria(valori)

        df = df.loc[
            ~(
                (df["kpi_name"] == READ_RATE)
                & (df["timestamp"] < BASE_END - 5 * 60)
            )
        ]

        esito = self.valuta(df)

        self.assertEqual(
            esito["status"], "evidenza_insufficiente"
        )

    def test_isolamento_componenti(self):
        valori = [0] * 12 + [20] * 18
        df = crea_telemetria(valori, nodo="node-6")

        esito = self.valuta(df)

        self.assertEqual(
            esito["status"], "evidenza_insufficiente"
        )

    def test_duplicati_timestamp(self):
        valori = [0] * 15 + [20] * 3 + [0] * 12
        df = crea_telemetria(valori)

        # Duplichiamo un campione di lettura
        duplicato = df.loc[
            (df["kpi_name"] == READ_RATE)
            & (df["timestamp"] == START + 15 * 60)
        ]

        df = pd.concat([df, duplicato], ignore_index=True)

        esito = self.valuta(df)

        self.assertEqual(
            esito["status"], "candidato_da_verificare"
        )

    def test_gap_temporale(self):
        righe = []

        # 12 campioni regolari nella baseline
        tempi = [START + i * 60 for i in range(12)]

        # Campioni elevati distanziati di 120 secondi
        tempi += [BASE_END, BASE_END + 120, BASE_END + 240]

        valori = [0] * 12 + [20] * 3

        for t, valore in zip(tempi, valori):
            righe.append({
                "timestamp": t,
                "cmdb_id": NODE,
                "kpi_name": READ_RATE,
                "value": valore
            })

        df = pd.DataFrame(righe)
        esito = self.valuta(df)

        self.assertEqual(
            esito["status"], "nessun_candidato"
        )

    def test_valori_negativi(self):
        valori = [0] * 12 + [-1] + [20] * 17

        esito = self.valuta(crea_telemetria(valori))

        self.assertEqual(
            esito["status"], "evidenza_insufficiente"
        )

    def test_valori_nan(self):
        valori = [0] * 15 + [20] * 4 + [0] * 11
        df = crea_telemetria(valori)

        # Rendiamo mancante un campione anomalo
        df.loc[
            (df["kpi_name"] == READ_RATE)
            & (df["timestamp"] == START + 16 * 60),
            "value"
        ] = float("nan")

        esito = self.valuta(df)

        self.assertEqual(
            esito["status"], "nessun_candidato"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
