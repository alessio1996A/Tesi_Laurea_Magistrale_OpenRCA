"""Test offline di configurazione per A0, A1-R8 e A1_V2.

Nessuna chiamata a Gemini e nessun accesso alla ground truth di OpenRCA.
"""

import unittest

from agent.prompts import get_system_prompt
from evaluation.experiment_config import ExperimentConfig


CASO = "cloudbed-1_q067"


class TestConfigurazioneAblazione(unittest.TestCase):
    def test_prompt_identico_tra_varianti(self):
        """L'unica differenza deve essere il report nel prompt utente."""
        self.assertEqual(get_system_prompt("A0"), get_system_prompt("A1"))
        self.assertEqual(get_system_prompt("A1"), get_system_prompt("A1_V2"))

    def test_modello_e_budget_identici(self):
        """Il confronto non deve cambiare modello o budget di esplorazione."""
        configurazioni = [
            ExperimentConfig(variant=v, case_id=CASO)
            for v in ("A0", "A1", "A1_V2")
        ]
        self.assertEqual(len({c.model_name for c in configurazioni}), 1)
        self.assertEqual(len({c.max_tool_rounds for c in configurazioni}), 1)
        self.assertEqual(len({c.recursion_limit for c in configurazioni}), 1)

    def test_percorsi_distinti_senza_sovrascrittura(self):
        """Ogni variante deve avere un nome di output indipendente."""
        a0 = ExperimentConfig(variant="A0", case_id=CASO)
        a1 = ExperimentConfig(variant="A1", case_id=CASO)
        a1_v2 = ExperimentConfig(variant="A1_V2", case_id=CASO)
        self.assertEqual(len({a0.output_path, a1.output_path, a1_v2.output_path}), 3)
        self.assertIsNone(a0.evidence_path)
        self.assertIsNotNone(a1.evidence_path)
        self.assertIsNotNone(a1_v2.evidence_path)
        self.assertNotEqual(a1.evidence_path, a1_v2.evidence_path)

    def test_rifiuta_variante_sconosciuta(self):
        """Evitare che un refuso selezioni una variante non prevista."""
        with self.assertRaises(ValueError):
            ExperimentConfig(variant="SCONOSCIUTA", case_id=CASO)
        with self.assertRaises(ValueError):
            get_system_prompt("SCONOSCIUTA")


if __name__ == "__main__":
    unittest.main(verbosity=2)
