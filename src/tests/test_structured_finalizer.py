"""Test offline della finalizzazione strutturata: nessuna chiamata a provider."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from output.structured_finalizer import (
    StructuredDiagnosis,
    StructuredFault,
    StructuredOutputError,
    formatta_diagnosi_strutturata,
)


def risposta_grezza():
    return json.dumps({
        "1": {
            "root cause occurrence datetime": "2022-03-20 13:00:00",
            "root cause component": "node-5",
            "root cause resource exhaustion": "node CPU load",
        }
    })


def fake_llm(parsed, usage=None, error=None):
    model = Mock()
    output = Mock()
    output.invoke.return_value = {
        "parsed": parsed,
        "raw": SimpleNamespace(usage_metadata=usage or {}),
        "parsing_error": error,
    }
    model.with_structured_output.return_value = output
    return model


class TestStructuredFinalizer(unittest.TestCase):
    def test_converte_valori_presenti_in_json_openrca(self):
        parsed = StructuredDiagnosis(root_causes=[
            StructuredFault(
                occurrence_datetime="2022-03-20 13:00:00",
                component="node-5",
                reason="node CPU load",
            )
        ])
        llm = fake_llm(parsed, {
            "input_tokens": 80,
            "output_tokens": 20,
            "total_tokens": 100,
        })
        result = formatta_diagnosi_strutturata(llm, risposta_grezza())
        payload = json.loads(result.prediction)
        self.assertEqual(list(payload), ["1"])
        self.assertEqual(payload["1"]["root cause reason"], "node CPU load")
        self.assertEqual(result.total_tokens, 100)
        llm.with_structured_output.assert_called_once_with(
            StructuredDiagnosis, include_raw=True
        )

    def test_rifiuta_reason_inventata(self):
        parsed = StructuredDiagnosis(root_causes=[
            StructuredFault(
                occurrence_datetime="2022-03-20 13:00:00",
                component="node-5",
                reason="disk write saturation",
            )
        ])
        with self.assertRaisesRegex(StructuredOutputError, "non presente"):
            formatta_diagnosi_strutturata(
                fake_llm(parsed), risposta_grezza()
            )

    def test_rifiuta_componente_inventato(self):
        parsed = StructuredDiagnosis(root_causes=[
            StructuredFault(
                occurrence_datetime="2022-03-20 13:00:00",
                component="node-6",
                reason="node CPU load",
            )
        ])
        with self.assertRaisesRegex(StructuredOutputError, "component"):
            formatta_diagnosi_strutturata(
                fake_llm(parsed), risposta_grezza()
            )

    def test_rifiuta_timestamp_inventato(self):
        parsed = StructuredDiagnosis(root_causes=[
            StructuredFault(
                occurrence_datetime="2022-03-20 13:12:21",
                component="node-5",
                reason="node CPU load",
            )
        ])
        with self.assertRaisesRegex(StructuredOutputError, "occurrence_datetime"):
            formatta_diagnosi_strutturata(
                fake_llm(parsed), risposta_grezza()
            )

    def test_rifiuta_timestamp_impossibile_pur_presente(self):
        raw = json.dumps({
            "1": {
                "root cause occurrence datetime": "2022-02-30 13:00:00",
                "root cause component": "node-5",
                "root cause reason": "node CPU load",
            }
        })
        parsed = StructuredDiagnosis(root_causes=[
            StructuredFault(
                occurrence_datetime="2022-02-30 13:00:00",
                component="node-5",
                reason="node CPU load",
            )
        ])
        with self.assertRaisesRegex(StructuredOutputError, "Timestamp"):
            formatta_diagnosi_strutturata(fake_llm(parsed), raw)

    def test_rifiuta_risposta_vuota(self):
        llm = Mock()
        with self.assertRaisesRegex(StructuredOutputError, "vuota"):
            formatta_diagnosi_strutturata(llm, "  ")
        llm.with_structured_output.assert_not_called()

    def test_provider_senza_supporto_rifiutato(self):
        llm = Mock()
        llm.with_structured_output.side_effect = NotImplementedError()
        with self.assertRaisesRegex(StructuredOutputError, "non supporta"):
            formatta_diagnosi_strutturata(llm, risposta_grezza())

    def test_rifiuta_output_provider_senza_parsed(self):
        llm = fake_llm(None)
        with self.assertRaisesRegex(StructuredOutputError, "Parsing"):
            formatta_diagnosi_strutturata(llm, risposta_grezza())

    def test_controllo_cardinalita_solo_se_esplicito(self):
        parsed = StructuredDiagnosis(root_causes=[
            StructuredFault(
                occurrence_datetime="2022-03-20 13:00:00",
                component="node-5",
                reason="node CPU load",
            )
        ])
        with self.assertRaisesRegex(StructuredOutputError, "Cardinalita"):
            formatta_diagnosi_strutturata(
                fake_llm(parsed), risposta_grezza(), expected_faults=2
            )

    def test_failure_provider_non_fa_retry_nascosti(self):
        llm = Mock()
        formatter = Mock()
        llm.with_structured_output.return_value = formatter
        formatter.invoke.side_effect = RuntimeError("offline test")
        with self.assertRaisesRegex(StructuredOutputError, "finalizzazione fallita"):
            formatta_diagnosi_strutturata(llm, risposta_grezza())
        formatter.invoke.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
