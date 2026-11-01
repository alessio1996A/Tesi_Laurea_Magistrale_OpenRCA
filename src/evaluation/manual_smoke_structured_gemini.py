"""Smoke test manuale: UNA chiamata Gemini per verificare lo structured output.

Eseguire SOLO dopo aver configurato GOOGLE_API_KEY nell'ambiente.
NON legge dati OpenRCA, ground truth o risultati storici; NON scrive file.
Questo modulo NON e' parte dei test unittest automatici.
"""

import json
import os

from agent.model_factory import crea_modello
from output.openrca_contract import parse_openrca_json
from output.structured_finalizer import formatta_diagnosi_strutturata


def main() -> None:
    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError(
            "GOOGLE_API_KEY non configurata: impostarla come variabile "
            "d'ambiente prima dello smoke test."
        )

    model = "gemini-3.5-flash-lite"

    # Dato interamente sintetico. Il campo reason compare con un nome
    # non conforme, come negli errori osservati nel pilot.
    original = json.dumps({
        "1": {
            "root cause occurrence datetime": "2022-03-20 13:00:00",
            "root cause component": "node-5",
            "root cause resource exhaustion": "node CPU load",
        }
    }, ensure_ascii=False)

    llm = crea_modello(provider="google", model_name=model)

    result = formatta_diagnosi_strutturata(
        llm=llm,
        raw_response=original,
        expected_faults=1,
    )

    diagnosis = parse_openrca_json(result.prediction, expected_faults=1)
    assert len(diagnosis.root_causes) == 1
    assert diagnosis.root_causes[0].occurrence_datetime == "2022-03-20 13:00:00"
    assert diagnosis.root_causes[0].component == "node-5"
    assert diagnosis.root_causes[0].reason == "node CPU load"

    print("SMOKE TEST STRUTTURATO: OK")
    print("Modello:", model)
    print("JSON prodotto:", result.prediction)
    print("Token finalizzazione:", result.total_tokens)
    print("Misurazione token disponibile:", result.usage_available)
    print("Durata finalizzazione (s):", result.elapsed_seconds)


if __name__ == "__main__":
    main()
