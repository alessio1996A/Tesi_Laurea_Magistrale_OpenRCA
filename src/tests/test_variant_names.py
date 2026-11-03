"""Test offline della corrispondenza fra nomi del relatore e ID congelati."""
import unittest

from agent.variant_names import (
    VARIANTI_INTERNE,
    NOMI_PRESENTAZIONE,
    nome_presentazione,
    id_interno,
)


class TestNomiVarianti(unittest.TestCase):
    def test_cinque_varianti_distinte(self):
        self.assertEqual(len(VARIANTI_INTERNE), 5)
        self.assertEqual(len(set(NOMI_PRESENTAZIONE.values())), 5)

    def test_andata_e_ritorno(self):
        for identificativo in VARIANTI_INTERNE:
            with self.subTest(variante=identificativo):
                nome = nome_presentazione(identificativo)
                self.assertEqual(id_interno(nome), identificativo)

    def test_varianti_sconosciute(self):
        with self.assertRaises(ValueError):
            nome_presentazione("A1_V3_inventata")
        with self.assertRaises(ValueError):
            id_interno("PAVE_completo")


if __name__ == "__main__":
    unittest.main()
