"""Test offline della conversione biunivoca dei nomi delle cinque varianti."""
import unittest

from agent.variant_names import (
    VARIANTI_INTERNE,
    VARIANTI_FINALI,
    NOMI_PRESENTAZIONE,
    nome_presentazione,
    id_interno,
    variante_canonica,
)


class TestNomiVarianti(unittest.TestCase):
    def test_cinque_varianti_distinte(self):
        self.assertEqual(len(VARIANTI_INTERNE), 5)
        self.assertEqual(len(set(VARIANTI_FINALI)), 5)
        self.assertEqual(len(set(NOMI_PRESENTAZIONE.values())), 5)

    def test_andata_e_ritorno(self):
        for identificativo in VARIANTI_INTERNE:
            with self.subTest(variante=identificativo):
                nome = nome_presentazione(identificativo)
                self.assertEqual(id_interno(nome), identificativo)

    def test_ambiguita_A1_esplicita(self):
        self.assertEqual(variante_canonica("A1"), "A1")
        self.assertEqual(variante_canonica("A1", schema="historic_v3"), "A1_8R")

    def test_tutti_i_nomi_legacy_si_convertano(self):
        for nome in VARIANTI_INTERNE:
            self.assertIn(
                variante_canonica(nome, schema="historic_v3"),
                VARIANTI_FINALI,
            )

    def test_identificativi_sconosciuti(self):
        with self.assertRaises(ValueError):
            nome_presentazione("A1_V3_inventata")
        with self.assertRaises(ValueError):
            id_interno("PAVE_completo")
        with self.assertRaises(ValueError):
            variante_canonica("A1_VERIFY")  # senza schema storico
        with self.assertRaises(ValueError):
            variante_canonica("A1", schema="inatteso")


if __name__ == "__main__":
    unittest.main(verbosity=2)
