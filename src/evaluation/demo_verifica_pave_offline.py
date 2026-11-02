"""Demo offline PAVE-inspired: non utilizza Gemini né ground truth.

Il verificatore strutturale/temporale è un prototipo indipendente dal runner.
La demo usa esclusivamente segnali sintetici e non modifica le predizioni.
Esecuzione dalla root del repository:
    PYTHONPATH=src python src/evaluation/demo_verifica_pave_offline.py
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from harness.structural_temporal_verifier import (
    verifica_relazioni_strutturali_temporali,
)
from output.openrca_contract import RootCause

# Finestra di esempio in ora locale del benchmark (Asia/Shanghai).
ORA = "2022-03-20 13:00:00"
T = int(datetime.strptime(ORA, "%Y-%m-%d %H:%M:%S")
        .replace(tzinfo=ZoneInfo("Asia/Shanghai")).timestamp())
INIZIO, FINE = T - 600, T + 1200

ETICHETTE = {"R01": "container CPU load", "R07": "node CPU load"}


def candidato(regola, componente, istante):
    """Costruisce una semplice anomalia osservativa sintetica."""
    return {
        "regola": regola,
        "classe_candidata": ETICHETTE[regola],
        "componente_telemetria": componente,
        "timestamp_primo_segnale_unix": istante,
        "timestamp_ultimo_segnale_unix": istante + 30,
    }


def verifica(diagnosi, candidati):
    """Adatta le anomalie al formato richiesto dal modulo esistente."""
    report = {
        "versione": "unified_evidence_v2",
        "caso": {"start_unix": INIZIO, "end_unix": FINE},
        "evidenze": [],
        "regole_diagnostiche_v0": {
            "versione": "rule_based_A1_R_v1",
            "finestra": {"start_unix": INIZIO, "end_unix": FINE},
            "candidati_riportati": candidati,
            "candidati_omessi_per_budget": 0,
        },
    }
    return verifica_relazioni_strutturali_temporali(
        diagnosi, report, start_unix=INIZIO, end_unix=FINE,
        tolleranza_secondi=60,
    )


def main():
    print("=== VERIFICA STRUTTURALE/TEMPORALE: DEMO SINTETICA ===")

    # A) Stesso host, stessa famiglia CPU: registriamo la precedenza,
    # ma non affermiamo che il nodo abbia causato il guasto del container.
    diagnosi_nodo = RootCause(ORA, "node-5", "node CPU load")
    stesso_host = verifica(diagnosi_nodo, [
        candidato("R07", "node-5", T),
        candidato("R01", "node-5.frontend-0", T + 180),
    ])
    assert stesso_host["stato"] == "relazioni_osservate"
    print("A) Stesso host:", stesso_host["stato"])
    print("   Ordine:", stesso_host["relazioni_cross_layer"][0]["ordine_osservato"])

    # B) Host diverso: il verificatore NON inventa una relazione.
    host_diversi = verifica(diagnosi_nodo, [
        candidato("R07", "node-5", T),
        candidato("R01", "node-6.frontend-0", T + 180),
    ])
    assert host_diversi["stato"] == "nessuna_relazione_osservata"
    print("B) Host diversi:", host_diversi["stato"])

    # C) Nome container non qualificato, presente su due nodi.
    diagnosi_container = RootCause(ORA, "frontend-0", "container CPU load")
    ambiguo = verifica(diagnosi_container, [
        candidato("R07", "node-5", T),
        candidato("R01", "node-5.frontend-0", T),
        candidato("R01", "node-6.frontend-0", T),
    ])
    assert ambiguo["stato"] == "host_ambiguo"
    print("C) Container ambiguo:", ambiguo["host_candidati"])

    for risultato in (stesso_host, host_diversi, ambiguo):
        assert risultato["causa_verificata"] is False
        assert risultato["propagazione_verificata"] is False
    print("NESSUNA prova causale; chiamate LLM: 0; ground truth: 0")


if __name__ == "__main__":
    main()
