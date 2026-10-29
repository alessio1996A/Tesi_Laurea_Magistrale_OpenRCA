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
def run_experiment(
    config: ExperimentConfig,
    system_prompt: str,
    llm=None,
    verbose: bool = True,
    salva: bool = False
) -> dict:
    """
    Esegue un esperimento OpenRCA completo.

    Utilizza lo stesso motore LangGraph per A0 e A1.

    Se llm è None, crea il modello Gemini indicato nella
    configurazione. Nei test possiamo passare un Fake LLM.

    Non utilizza ground truth.
    """

    # Importiamo qui il motore condiviso.
    from agent.graph_engine import (
        crea_grafo_rca,
        esegui_grafo_rca
    )

    import hashlib
    import json
    import time

    from datetime import datetime

    if not system_prompt.strip():
        raise ValueError("Prompt di sistema vuoto.")

    # =====================================================
    # 1. INIZIO MISURAZIONE COMPLETA
    # =====================================================

    inizio_totale = time.perf_counter()

    # =====================================================
    # 2. PREPARAZIONE DEL CASO
    # =====================================================

    esperimento = prepara_esperimento(config)

    caso = esperimento["caso"]
    tools = esperimento["tools"]
    richiesta = esperimento["richiesta"]

    # La preparazione di A1 genera automaticamente
    # le evidenze e misura il tempo del preprocessing.
    preprocessing_seconds = esperimento[
        "preprocessing_seconds"
    ]

    # =====================================================
    # 3. CREAZIONE DEL MODELLO
    # =====================================================

    if llm is None:

        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model=config.model_name
        )

    # =====================================================
    # 4. COSTRUZIONE DEL GRAFO CONDIVISO
    # =====================================================

    grafo = crea_grafo_rca(
        llm=llm,
        tools=tools,
        system_prompt=system_prompt,
        max_tool_rounds=config.max_tool_rounds
    )

    # =====================================================
    # 5. ESECUZIONE DELL'AGENTE
    # =====================================================

    esecuzione = esegui_grafo_rca(
        grafo=grafo,
        richiesta=richiesta,
        recursion_limit=config.recursion_limit,
        verbose=verbose
    )

    risposta = esecuzione["raw_response"]

    # =====================================================
    # 6. VALIDAZIONE DEL FORMATO OPENRCA
    # =====================================================

    predizione = None
    json_status = None

    if risposta is not None:

        try:

            predizione = json.loads(risposta)

            if not isinstance(predizione, dict) or not predizione:
                raise ValueError(
                    "La predizione deve essere un dizionario non vuoto."
                )

            campi_richiesti = {
                "root cause occurrence datetime",
                "root cause component",
                "root cause reason"
            }

            for indice, guasto in predizione.items():

                if not str(indice).isdigit():
                    raise ValueError(
                        "Indice del guasto non numerico."
                    )

                if not isinstance(guasto, dict):
                    raise ValueError(
                        "Struttura del guasto non valida."
                    )

                if not campi_richiesti.issubset(guasto):
                    raise ValueError(
                        "Campi OpenRCA mancanti."
                    )

                datetime.strptime(
                    guasto["root cause occurrence datetime"],
                    "%Y-%m-%d %H:%M:%S"
                )

                for campo in (
                    "root cause component",
                    "root cause reason"
                ):
                    if not isinstance(guasto[campo], str):
                        raise ValueError(
                            f"Campo {campo} non testuale."
                        )

            json_status = "valid_json"

        except (ValueError, TypeError) as exc:

            predizione = None

            json_status = (
                f"invalid_json: {type(exc).__name__}: {exc}"
            )

    # =====================================================
    # 7. MISURAZIONE DEI TEMPI
    # =====================================================

    tempo_totale = round(
        time.perf_counter() - inizio_totale,
        3
    )

    metriche = dict(esecuzione["metrics"])

    # Tempo misurato durante la preparazione A1.
    metriche["preprocessing_seconds"] = round(
        preprocessing_seconds,
        3
    )

    # Tempo completo: preparazione, creazione del modello
    # ed esecuzione del grafo.
    metriche["end_to_end_seconds"] = tempo_totale

    # =====================================================
    # 8. COSTRUZIONE DEL RISULTATO
    # =====================================================

    prompt_sha256 = hashlib.sha256(
        system_prompt.encode("utf-8")
    ).hexdigest()

    risultato = {
        "variant": config.variant,
        "case_id": config.case_id,
        "cloudbed": caso["cloudbed"],
        "task_index": caso["task_index"],
        "query_index": caso["query_index"],
        "model": config.model_name,
        "max_tool_rounds": config.max_tool_rounds,
        "system_prompt_sha256": prompt_sha256,
        "evidence_sha256": esperimento["evidence_sha256"],
        "prediction": (
            json.dumps(predizione, ensure_ascii=False)
            if predizione is not None
            else None
        ),
        "raw_response": risposta,
        "json_status": json_status,
        "error": esecuzione["error"],
        "metrics": metriche,
        "tool_trajectory": esecuzione["tool_trajectory"]
    }

    # =====================================================
    # 9. SALVATAGGIO OPZIONALE
    # =====================================================

    if salva:

        # Usiamo un nome diverso dai vecchi piloti:
        # non dobbiamo sovrascrivere i risultati A0/A1
        # già valutati ufficialmente.

        destinazione = (
            config.results_dir
            / f"{config.variant.lower()}_unified_"
              f"{config.case_id}.json"
        )

        destinazione.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        # Modalità "x": se il file esiste già,
        # Python solleva un errore anziché sovrascriverlo.
        with destinazione.open(
            "x",
            encoding="utf-8"
        ) as file:

            json.dump(
                risultato,
                file,
                indent=2,
                ensure_ascii=False
            )

        if verbose:
            print("Risultato salvato:", destinazione)

    return risultato
