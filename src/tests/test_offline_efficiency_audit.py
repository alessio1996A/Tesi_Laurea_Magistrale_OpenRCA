"""Test del profiler offline: soltanto dati sintetici, nessuna chiamata LLM."""
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.offline_efficiency_audit import (
    PROTOCOLLO_V3,
    leggi_profili,
    profilo_run,
    riepilogo_varianti,
)


def evento(nome: str, **kwargs) -> dict:
    return {"tipo": "tool_call", "nome": nome, "parametri": kwargs}


def fake_run(*, calls=None, variant="A1", elapsed=45.0):
    return {
        "case_id": "cloudbed-1_q013",
        "variant": variant,
        "metrics": {
            "llm_calls": 3,
            "tool_rounds": 2,
            "total_tokens": 1234,
            "end_to_end_seconds": elapsed,
            "preprocessing_seconds": 12.5,
        },
        "tool_trajectory": calls if calls is not None else [],
        "prediction": {"1": {"root cause reason": "non leggere questo campo"}},
    }


class OfflineEfficiencyTests(unittest.TestCase):
    def test_chiamate_simili_non_sono_duplicati_esatti(self):
        run = fake_run(calls=[
            evento("tool_get_traces", start_unix=100, end_unix=200),
            evento("tool_get_traces", start_unix=100, end_unix=150),
            evento("tool_get_traces", start_unix=100, end_unix=200),
            {"tipo": "tool_result", "nome": "tool_get_traces"},
        ])
        profilo = profilo_run(run)
        self.assertEqual(profilo.chiamate_tool, 3)
        self.assertEqual(profilo.ripetizioni_famiglia_tool, 2)
        self.assertEqual(profilo.duplicati_esatti_tool, 1)
        self.assertEqual(profilo.tempo_modello_e_tool_s, 32.5)

    def test_ignorare_claim_e_altri_file(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            run_id = f"{PROTOCOLLO_V3}__cloudbed-1_q013__a1__r01"
            (directory / f"{run_id}.json").write_text(
                json.dumps(fake_run()), encoding="utf-8"
            )
            (directory / f"{run_id}.claim.json").write_text(
                json.dumps({"status": "started"}), encoding="utf-8"
            )
            (directory / "query.csv").write_text(
                "scoring_points\nDATO_DA_NON_LEGGERE\n", encoding="utf-8"
            )
            rows = leggi_profili(directory)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].caso, "cloudbed-1_q013")

    def test_aggregazione_non_legge_diagnosi(self):
        profili = [
            profilo_run(fake_run(variant="A1", elapsed=45)),
            profilo_run(fake_run(variant="A1", elapsed=55)),
            profilo_run(fake_run(variant="A0", elapsed=20)),
        ]
        risultati = riepilogo_varianti(profili)
        self.assertEqual([r["variante"] for r in risultati], ["A0", "A1"])
        self.assertEqual(risultati[1]["run"], 2)
        self.assertEqual(risultati[1]["tempo_medio_s"], 50)

    def test_metriche_errate_bloccate(self):
        with self.assertRaises(ValueError):
            profilo_run(fake_run(elapsed=5.0))  # preprocessing > tempo totale
        with self.assertRaises(ValueError):
            profilo_run({"case_id": "cloudbed-1_q013", "variant": "A0"})

    def test_cartella_mancante(self):
        with self.assertRaises(FileNotFoundError):
            leggi_profili(Path("/cartella_che_non_esiste_esclusivo_audit"))


if __name__ == "__main__":
    unittest.main()
