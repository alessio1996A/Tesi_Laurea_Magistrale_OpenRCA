"""Test offline delle cinque varianti con nomi definitivi.

La baseline e le quattro estensioni mantengono modello e budget uguali;
gli identificativi storici sono gestiti esplicitamente da variant_scheme.
Nessuna chiamata a Gemini o ground truth.
"""
import unittest

from agent.prompts import get_system_prompt
from agent.variant_names import VARIANTI_FINALI
from evaluation.experiment_config import ExperimentConfig

CASO = "cloudbed-1_q067"


class TestConfigurazioneAblazione(unittest.TestCase):
    def test_prompt_identico_tra_varianti(self):
        prompt = get_system_prompt("A0")
        for variante in VARIANTI_FINALI:
            with self.subTest(variante=variante):
                self.assertEqual(get_system_prompt(variante), prompt)

    def test_modello_e_budget_identici(self):
        config = [
            ExperimentConfig(variant=variante, case_id=CASO)
            for variante in VARIANTI_FINALI
        ]
        self.assertEqual({c.model_name for c in config}, {"gemini-3.5-flash-lite"})
        self.assertEqual({c.max_tool_rounds for c in config}, {6})
        self.assertEqual({c.recursion_limit for c in config}, {30})

    def test_ogni_variante_ha_output_distinto(self):
        config = [
            ExperimentConfig(variant=variante, case_id=CASO)
            for variante in VARIANTI_FINALI
        ]
        self.assertEqual(len({c.output_path for c in config}), 5)
        self.assertEqual(len({c.evidence_path for c in config}), 5)
        self.assertIsNone(config[0].evidence_path)
        for caso in config[1:]:
            self.assertIsNotNone(caso.evidence_path)
            self.assertIn("final_names_v1", str(caso.output_path))

    def test_variante_non_valida(self):
        with self.assertRaises(ValueError):
            ExperimentConfig(variant="SCONOSCIUTA", case_id=CASO)
        with self.assertRaises(ValueError):
            get_system_prompt("SCONOSCIUTA")

    def test_vecchio_nome_esplicito(self):
        with self.assertRaises(ValueError):
            ExperimentConfig(variant="A1_VERIFY", case_id=CASO)
        vecchia = ExperimentConfig(
            variant="A1_VERIFY", case_id=CASO, variant_scheme="historic_v3"
        )
        self.assertEqual(vecchia.canonical_variant, "A1_8R_Planning")
        self.assertNotIn("final_names_v1", str(vecchia.output_path))

    def test_ambiguita_A1_risolta_dal_protocollo(self):
        nuova = ExperimentConfig(variant="A1", case_id=CASO)
        vecchia = ExperimentConfig(
            variant="A1", case_id=CASO, variant_scheme="historic_v3"
        )
        self.assertEqual(nuova.canonical_variant, "A1")
        self.assertEqual(vecchia.canonical_variant, "A1_8R")
        self.assertNotEqual(nuova.output_path, vecchia.output_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
