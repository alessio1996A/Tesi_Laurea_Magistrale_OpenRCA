"""Audit di integrazione su telemetria OpenRCA REALE, senza API o ground truth.

Ricostruisce esclusivamente il report deterministico A1-R8 e verifica
l'integrita' rispetto allo SHA-256 di un risultato storico immutabile.
Usa poi i verificatori PAVE-inspired per analizzare la predizione
precedentemente salvata, SENZA correggerla o ricalcolarla con un LLM.

I casi q040 e q006 sono *gia' esplorati* e non costituiscono evaluation.
Nessun file viene scritto o sovrascritto.
"""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.experiment_config import ExperimentConfig
from evaluation.experiment_runner import prepara_esperimento
from harness.observational_verifier import verifica_coerenza_osservativa
from harness.hypothesis_coverage_audit import verifica_copertura_ipotesi
from harness.structural_temporal_verifier import (
    verifica_relazioni_strutturali_temporali,
)
from output.openrca_contract import parse_openrca_json


BASE_COMMIT = "e4951737640e4c690b4e7e89e3358dd7a016e624"
HISTORICAL_CASES = {
    "cloudbed-1_q040": {
        "filename": "a1r8_q040_e495173_trial01.json",
        "evidence_sha256": (
            "507d608476963a2b561042614c4ba4a889f2069c7ec26ea19c9a9c800e7eadeb"
        ),
    },
    "cloudbed-2_q006": {
        "filename": "a1r8_q006_e495173_trial01.json",
        "evidence_sha256": (
            "4adca7f48332f8df5eb69f1d179e100fe65e255fce551f1650d471e874276252"
        ),
    },
}


def esegui_audit_offline(
    case_id: str,
    *,
    data_dir: Path,
) -> dict:
    """Controllo di regressione su un caso A1-R8 gia' analizzato.

    Non legge scoring_points, record.csv o query.csv per valutare le
    predizioni, e non utilizza chiavi o chiamate LLM.
    """
    if case_id not in HISTORICAL_CASES:
        raise ValueError("Usare solo q040/q006, casi gia' esplorati")
    data_dir = Path(data_dir)
    item = HISTORICAL_CASES[case_id]
    source_path = (
        data_dir / "data" / "results" / "development_pilots"
        / item["filename"]
    )

    with source_path.open("r", encoding="utf-8") as stream:
        historical = json.load(stream)

    if historical.get("case_id") != case_id or historical.get("variant") != "A1":
        raise ValueError("Risultato storico non corrispondente")
    if (historical.get("provenance") or {}).get("git_commit") != BASE_COMMIT:
        raise ValueError("Commit sperimentale storico inatteso")
    if historical.get("evidence_sha256") != item["evidence_sha256"]:
        raise ValueError("SHA evidenze storico inatteso")

    config = ExperimentConfig(
        variant="A1",
        case_id=case_id,
        data_dir=data_dir,
    )
    prepared = prepara_esperimento(config)
    if prepared["evidence_sha256"] != historical["evidence_sha256"]:
        raise ValueError(
            "REGRESSIONE: report deterministico diverso dallo snapshot "
            "storico; fermare l'audit e indagare prima di procedere"
        )

    prediction = historical.get("prediction")
    diagnosis = parse_openrca_json(prediction)
    case = prepared["caso"]
    report = prepared["evidence_report"]
    results = []

    for index, fault in enumerate(diagnosis.root_causes, 1):
        observed = verifica_coerenza_osservativa(
            fault,
            report,
            start_unix=int(case["start_unix"]),
            end_unix=int(case["end_unix"]),
        )
        structural = verifica_relazioni_strutturali_temporali(
            fault,
            report,
            start_unix=int(case["start_unix"]),
            end_unix=int(case["end_unix"]),
        )

        results.append({
            "numero_guasto": index,
            "componente_predetto": fault.component,
            "reason_predetta": fault.reason,
            "timestamp_predetto": fault.occurrence_datetime,
            "stato_osservativo": observed["stato"],
            "stato_strutturale": structural["stato"],
            "numero_match_osservativi": len(observed["matches"]),
            "numero_relazioni_cross_layer": len(
                structural["relazioni_cross_layer"]
            ),
            "causa_verificata": False,
        })

    # Audit solo descrittivo: il report R8 e la tool_trajectory storica
    # rimangono inalterati. Non dedurre che una causa sia confermata.
    coverage = verifica_copertura_ipotesi(
        diagnosis,
        report,
        historical.get("tool_trajectory", []),
    )
    rules = report["regole_diagnostiche_v0"]
    return {
        "case_id": case_id,
        "modalita": "audit_offline_non_causale",
        "commit_storico": BASE_COMMIT,
        "evidence_sha256": prepared["evidence_sha256"],
        "sha_evidenze_storiche_coerente": True,
        "candidati_regole": rules["totale_candidati"],
        "candidati_omessi": rules["candidati_omessi_per_budget"],
        "copertura_indagine": coverage,
        "diagnosi": results,
        "ground_truth_consultata": False,
        "llm_chiamato": False,
        "file_modificati": False,
    }
