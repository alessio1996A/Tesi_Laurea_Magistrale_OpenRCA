import json
import time
import hashlib
import zipfile

from pathlib import Path

import pandas as pd

from evaluation.experiment_config import ExperimentConfig
from agent.tool_factory import crea_tools_openrca
from agent.tools import _get_telemetry_csv_paths
from harness.evidence_builder import costruisci_report_evidenze


def carica_caso(config: ExperimentConfig) -> dict:
    """
    Recupera dal manifest il caso OpenRCA richiesto.

    Il manifest non contiene le etichette dei guasti.
    """

    manifest = pd.read_csv(config.manifest_path)

    # Le etichette non devono essere disponibili al runner.
    if {"reason", "scoring_points"} & set(manifest.columns):
        raise ValueError(
            "Il manifest contiene colonne di ground truth."
        )

    selezione = manifest.loc[
        manifest["case_id"] == config.case_id
    ]

    if len(selezione) != 1:
        raise ValueError(
            f"Case ID assente o duplicato: {config.case_id}"
        )

    riga = selezione.iloc[0]

    cloudbed = str(riga["cloudbed"])
    inizio = int(riga["start_unix"])
    fine = int(riga["end_unix"])

    if cloudbed not in ("cloudbed-1", "cloudbed-2"):
        raise ValueError("Cloudbed non valido nel manifest.")

    if inizio >= fine:
        raise ValueError("Intervallo non valido nel manifest.")

    return {
        "case_id": config.case_id,
        "cloudbed": cloudbed,
        "start_unix": inizio,
        "end_unix": fine,
        "instruction": str(riga["instruction"]),
        "task_index": str(riga["task_index"]),
        "query_index": int(riga["query_index"])
    }


def carica_metriche(
    config: ExperimentConfig,
    caso: dict,
    tipo: str
) -> pd.DataFrame:
    """
    Legge dal Market.zip le metriche appartenenti
    alla finestra ufficiale del caso.

    Non legge record.csv, query.csv o scoring_points.
    """

    if tipo not in ("node_metrics", "container_metrics"):
        raise ValueError("Tipo di metriche non supportato.")

    inizio = caso["start_unix"]
    fine = caso["end_unix"]

    colonne = ["timestamp", "cmdb_id", "kpi_name", "value"]

    percorsi = _get_telemetry_csv_paths(
        start_unix=inizio,
        end_unix=fine,
        market_system=caso["cloudbed"],
        data_kind=tipo
    )

    blocchi = []

    with zipfile.ZipFile(
        config.market_zip_path, "r"
    ) as archivio:

        for percorso in percorsi:

            with archivio.open(percorso) as file:

                for chunk in pd.read_csv(
                    file,
                    usecols=colonne,
                    chunksize=100_000
                ):

                    timestamps = pd.to_numeric(
                        chunk["timestamp"],
                        errors="coerce"
                    )

                    # Intervallo semiaperto [inizio, fine).
                    mask = (
                        timestamps.ge(inizio)
                        & timestamps.lt(fine)
                    )

                    if mask.any():
                        blocchi.append(
                            chunk.loc[mask, colonne].copy()
                        )

    # Restituiamo un DataFrame valido anche se vuoto.
    if not blocchi:
        return pd.DataFrame(columns=colonne)

    return pd.concat(blocchi, ignore_index=True)


def prepara_esperimento(
    config: ExperimentConfig
) -> dict:
    """
    Prepara un esperimento A0 oppure A1.

    A0:
        - recupera il caso dal manifest;
        - crea i cinque tool;
        - prepara l'istruzione OpenRCA.

    A1:
        - esegue gli stessi passaggi;
        - carica metriche nodo e container;
        - genera automaticamente le evidenze;
        - aggiunge il report all'istruzione.

    Questa funzione NON chiama Gemini.
    """

    # =====================================================
    # 1. SELEZIONE DEL CASO
    # =====================================================

    caso = carica_caso(config)

    cloudbed = caso["cloudbed"]
    inizio = caso["start_unix"]
    fine = caso["end_unix"]

    # =====================================================
    # 2. CREAZIONE DEI TOOL CONDIVISI
    # =====================================================

    tools = crea_tools_openrca(
        cloudbed=cloudbed,
        start_unix=inizio,
        end_unix=fine
    )

    # =====================================================
    # 3. ISTRUZIONE COMUNE AD A0 E A1
    # =====================================================

    richiesta = (
        f"Official OpenRCA instruction:\n"
        f"{caso['instruction']}\n\n"
        f"Telemetry system: {cloudbed}.\n"
        f"Use EXACT Unix seconds "
        f"start_unix={inizio}, end_unix={fine}.\n"
        "Tool calls must remain inside this interval. "
        "Respond only in the official OpenRCA JSON format."
    )

    evidence_report = None
    evidence_sha256 = None
    preprocessing_seconds = 0.0

    # =====================================================
    # 4. HARNESS DETERMINISTICO: SOLO A1
    # =====================================================

    if config.variant == "A1":

        inizio_preprocessing = time.perf_counter()

        # Carichiamo esclusivamente le metriche
        # della finestra ufficiale.
        df_nodi = carica_metriche(
            config, caso, "node_metrics"
        )

        df_container = carica_metriche(
            config, caso, "container_metrics"
        )

        # Generiamo il report da zero:
        # non utilizziamo report precomputati.
        evidence_report = costruisci_report_evidenze(
            df_nodi=df_nodi,
            df_container=df_container,
            cloudbed=cloudbed,
            start_unix=inizio,
            end_unix=fine
        )

        evidence_text = json.dumps(
            evidence_report,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False
        )

        evidence_sha256 = hashlib.sha256(
            evidence_text.encode("utf-8")
        ).hexdigest()

        # Aggiungiamo le evidenze all'istruzione.
        richiesta += (
            "\n\nDETERMINISTIC A1-v1 EVIDENCE REPORT\n"
            "The following observations were derived "
            "automatically from telemetry in the requested "
            "interval.\n"
            "They are NOT ground truth and do NOT establish "
            "the root cause.\n"
            "Correlated KPIs are not independent causal proofs.\n"
            "The absence of detected anomalies does not "
            "prove that a component is healthy.\n"
            "Use the available tools to investigate "
            "and verify hypotheses.\n"
            "Do not assume that the earliest detected anomaly "
            "is necessarily the cause.\n\n"
            f"{evidence_text}\n"
        )

        preprocessing_seconds = (
            time.perf_counter() - inizio_preprocessing
        )

    # =====================================================
    # 5. RESTITUZIONE DELL'ESPERIMENTO PREPARATO
    # =====================================================

    return {
        "config": config,
        "caso": caso,
        "tools": tools,
        "richiesta": richiesta,
        "evidence_report": evidence_report,
        "evidence_sha256": evidence_sha256,
        "preprocessing_seconds": preprocessing_seconds
    }