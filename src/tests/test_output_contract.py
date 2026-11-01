"""Test offline del contratto diagnostico model-agnostic.

Nessuna chiamata LLM, nessuna ground truth e nessun file Drive.
"""

import json
import unittest

from output.openrca_contract import (
    Diagnosis, RootCause, OutputContractError,
    parse_openrca_json, serialize_openrca_json,
)


def _fault(
    datetime_value="2022-03-20 13:00:00",
    component="node-5",
    reason="node CPU load",
):
    return {
        "root cause occurrence datetime": datetime_value,
        "root cause component": component,
        "root cause reason": reason,
    }


class TestOpenRCAContract(unittest.TestCase):
    def test_roundtrip_un_guasto(self):
        diagnosis = Diagnosis((RootCause(
            occurrence_datetime="2022-03-20 13:00:00",
            component="node-5",
            reason="node CPU load",
        ),))
        payload = serialize_openrca_json(diagnosis)
        self.assertEqual(parse_openrca_json(payload), diagnosis)
        self.assertEqual(list(json.loads(payload)), ["1"])

    def test_due_guasti_consecutivi(self):
        payload = json.dumps({
            "1": _fault(),
            "2": _fault(component="frontend-0", reason="container CPU load"),
        })
        parsed = parse_openrca_json(payload, expected_faults=2)
        self.assertEqual(len(parsed.root_causes), 2)
        self.assertEqual(parsed.root_causes[1].component, "frontend-0")

    def test_ordine_input_non_impone_ordine_output(self):
        payload = json.dumps({
            "2": _fault(component="frontend-0"),
            "1": _fault(component="node-5"),
        })
        canonical = json.loads(serialize_openrca_json(parse_openrca_json(payload)))
        self.assertEqual(list(canonical), ["1", "2"])

    def test_manca_reason_come_in_q012(self):
        payload = {"1": _fault()}
        payload["1"].pop("root cause reason")
        payload["1"]["root cause resource exhaustion"] = "system load increase"
        with self.assertRaisesRegex(OutputContractError, "mancanti"):
            parse_openrca_json(json.dumps(payload))

    def test_campo_extra_come_in_q052(self):
        payload = {"1": {**_fault(), "root cause operation": "iowait"}}
        with self.assertRaisesRegex(OutputContractError, "aggiuntivi"):
            parse_openrca_json(json.dumps(payload))

    def test_cardinalita_derivata_dalla_richiesta(self):
        payload = json.dumps({"1": _fault()})
        with self.assertRaisesRegex(OutputContractError, "Cardinalita"):
            parse_openrca_json(payload, expected_faults=2)
        self.assertEqual(len(parse_openrca_json(payload).root_causes), 1)

    def test_rifiuta_indici_non_consecutivi(self):
        with self.assertRaisesRegex(OutputContractError, "consecutive"):
            parse_openrca_json(json.dumps({"2": _fault()}))

    def test_rifiuta_timestamp_impossibile(self):
        with self.assertRaisesRegex(OutputContractError, "Timestamp"):
            parse_openrca_json(json.dumps({"1": _fault("2022-02-30 13:00:00")}))

    def test_rifiuta_timestamp_non_canonico(self):
        with self.assertRaisesRegex(OutputContractError, "Timestamp"):
            parse_openrca_json(json.dumps({"1": _fault("2022-3-20 13:00:00")}))

    def test_rifiuta_reason_vuota(self):
        with self.assertRaisesRegex(OutputContractError, "reason"):
            parse_openrca_json(json.dumps({"1": _fault(reason=" ")}))

    def test_rifiuta_json_markdown(self):
        payload = 'JSON:\n' + json.dumps({"1": _fault()})
        with self.assertRaises(OutputContractError):
            parse_openrca_json(payload)

    def test_rifiuta_chiave_json_duplicata(self):
        value = json.dumps(_fault())
        payload = '{"1":' + value + ',"1":' + value + '}'
        with self.assertRaisesRegex(OutputContractError, "duplicata"):
            parse_openrca_json(payload)

    def test_rifiuta_cardinalita_non_positiva(self):
        payload = json.dumps({"1": _fault()})
        for count in (0, True, "2"):
            with self.subTest(count=count):
                with self.assertRaises(OutputContractError):
                    parse_openrca_json(payload, expected_faults=count)

    def test_il_serializer_non_modifica_il_contenuto(self):
        d = Diagnosis((RootCause(
            "2022-03-20 13:12:21", "node-5", "container CPU load"
        ),))
        text = serialize_openrca_json(d)
        self.assertIn("2022-03-20 13:12:21", text)
        self.assertEqual(parse_openrca_json(text), d)


if __name__ == "__main__":
    unittest.main(verbosity=2)
