import json
import time
import hashlib
import zipfile
from agent.prompts import get_system_prompt
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

def carica_telemetria_mesh_runtime(
    config: ExperimentConfig,
    caso: dict,
    sorgente: str
):
    """
    Carica dal Market.zip le metriche Mesh o Runtime
    nella finestra temporale del caso OpenRCA.

    Legge soltanto i KPI utilizzati dal detector.

    Non legge la ground truth.
    Non modifica file.
    Non chiama Gemini.
    """

    import zipfile
    import pandas as pd

    from harness.mesh_runtime_detector import (
        PREFISSO_DURATA,
        PREFISSO_RICHIESTE,
        KPI_RUNTIME
    )

    if sorgente not in ("mesh", "runtime"):
        raise ValueError(
            f"Sorgente non supportata: {sorgente}"
        )

    start = int(caso["start_unix"])
    end = int(caso["end_unix"])

    if start >= end:
        raise ValueError(
            "Finestra temporale non valida."
        )

    colonne = [
        "timestamp",
        "cmdb_id",
        "kpi_name",
        "value"
    ]

    # =====================================================
    # 1. GIORNI COPERTI DALLA FINESTRA
    # =====================================================

    # OpenRCA utilizza file organizzati per giorno.
    # Gestiamo anche finestre che attraversano
    # la mezzanotte locale del dataset.

    inizio_locale = pd.to_datetime(
        start,
        unit="s",
        utc=True
    ).tz_convert("Asia/Shanghai")

    fine_locale = pd.to_datetime(
        end - 1,
        unit="s",
        utc=True
    ).tz_convert("Asia/Shanghai")

    giorni = pd.date_range(
        start=inizio_locale.normalize(),
        end=fine_locale.normalize(),
        freq="D"
    )

    # =====================================================
    # 2. SELEZIONE DEI FILE ZIP
    # =====================================================

    blocchi = []

    with zipfile.ZipFile(
        config.market_zip_path
    ) as archivio:

        nomi = archivio.namelist()

        for giorno in giorni:

            data = giorno.strftime("%Y_%m_%d")

            suffisso = (
                f"{caso['cloudbed']}/telemetry/"
                f"{data}/metric/"
                f"metric_{sorgente}.csv"
            )

            percorsi = [
                nome
                for nome in nomi
                if nome.endswith(suffisso)
            ]

            if len(percorsi) != 1:
                raise FileNotFoundError(
                    "File di telemetria non trovato "
                    "univocamente: "
                    f"{suffisso}"
                )

            # =================================================
            # 3. LETTURA A BLOCCHI
            # =================================================

            with archivio.open(percorsi[0]) as file:

                for blocco in pd.read_csv(
                    file,
                    usecols=colonne,
                    chunksize=250_000
                ):

                    blocco["timestamp"] = (
                        pd.to_numeric(
                            blocco["timestamp"],
                            errors="coerce"
                        )
                    )

                    # La finestra è [start, end).
                    filtro_temporale = (
                        blocco["timestamp"].ge(start)
                        & blocco["timestamp"].lt(end)
                    )

                    if sorgente == "mesh":

                        filtro_kpi = (
                            blocco["kpi_name"]
                            .str.startswith(
                                (
                                    PREFISSO_DURATA,
                                    PREFISSO_RICHIESTE
                                ),
                                na=False
                            )
                        )

                    else:

                        filtro_kpi = (
                            blocco["kpi_name"].isin(
                                KPI_RUNTIME
                            )
                        )

                    filtrato = blocco.loc[
                        filtro_temporale
                        & filtro_kpi,
                        colonne
                    ]

                    if not filtrato.empty:

                        blocchi.append(
                            filtrato.copy()
                        )

    # =====================================================
    # 4. RESTITUZIONE
    # =====================================================

    if not blocchi:

        return pd.DataFrame(
            columns=colonne
        )

    return pd.concat(
        blocchi,
        ignore_index=True
    )





def prepara_esperimento(
    config: ExperimentConfig
) -> dict:
    """
    Prepara A0, A1 (solo evidenze) oppure A1_8R (con otto regole).

    A0:
        - recupera il caso dal manifest;
        - crea i cinque tool;
        - prepara l'istruzione OpenRCA.

    A1:
        - esegue gli stessi passaggi;
        - carica metriche nodo e container;
        - genera automaticamente le evidenze;
        - aggiunge il report all'istruzione.

    A1_8R aggiunge le otto regole alle evidenze di A1.
    I vecchi piani V3 sono interpretati tramite config.variant_scheme.
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

    # =====================================================
    # 3 BIS. COMPLETEZZA DELLA DIAGNOSI (A0 E A1)
    # =====================================================
    # Questo vincolo dipende solo dall'istruzione ufficiale
    # visibile all'agente. Non usa record.csv o scoring_points.
    richiesta += (
        "\n\n"
        "DIAGNOSTIC COMPLETENESS REQUIREMENTS:\n"
        "Read the official incident instruction carefully.\n"
        "If it specifies multiple failures, investigate "
        "and report EACH requested failure separately.\n"
        "The number of numbered root-cause entries in the "
        "final JSON must match the number of failures "
        "explicitly stated in the official instruction.\n"
        "Use consecutive JSON keys starting from \"1\".\n"
        "For every requested failure, identify its own "
        "root cause occurrence datetime and root cause component.\n"
        "Do not combine distinct failures into one diagnosis.\n"
        "Do not assume that all failures share the same "
        "root cause or affected component.\n"
        "Only report conclusions supported by available telemetry; "
        "do not invent evidence or fabricate root causes.\n"
        "Before responding, check that every requested failure "
        "has been addressed and that the JSON is valid.\n"
    )

    evidence_report = None
    evidence_sha256 = None
    preprocessing_seconds = 0.0

    # =====================================================
    # 4. HARNESS DETERMINISTICO: A1 E VARIANTI SUCCESSIVE
    # =====================================================

    if config.canonical_variant in ("A1", "A1_8R", "A1_8R_Planning", "A1_PAVE"):

        # =====================================================
        # 1. IMPORT DELL'HARNESS UNIFICATO
        # =====================================================

        from harness.evidence_builder import (
            costruisci_report_evidenze_v2
        )

        from harness.evidence_selector import (
            annota_qualita_evidenze
        )

        from harness.evidence_summarizer import (
            sintetizza_evidenze
        )

        from harness.mesh_runtime_detector import (
            rileva_evidenze_mesh_runtime,
            aggrega_evidenze_mesh
        )

        from harness.unified_report import (
            costruisci_report_unificato_v2
        )

        inizio_preprocessing = time.perf_counter()

        # =====================================================
        # 2. CARICAMENTO NODE E CONTAINER
        # =====================================================

        df_nodi = carica_metriche(
            config=config,
            caso=caso,
            tipo="node_metrics"
        )

        df_container = carica_metriche(
            config=config,
            caso=caso,
            tipo="container_metrics"
        )

        # =====================================================
        # 3. EVIDENCE BUILDER A1-v2
        # =====================================================

        report_v2 = (
            costruisci_report_evidenze_v2(
                df_nodi=df_nodi,
                df_container=df_container,
                cloudbed=cloudbed,
                start_unix=inizio,
                end_unix=fine
            )
        )

        # =====================================================
        # 4. QUALITÀ DELLE EVIDENZE
        # =====================================================

        annotazioni = (
            annota_qualita_evidenze(
                report_v2=report_v2,
                df_nodi=df_nodi,
                df_container=df_container
            )
        )

        # =====================================================
        # 5. SINTESI NODE / CONTAINER
        # =====================================================

        sintesi = sintetizza_evidenze(
            annotazioni=annotazioni,
            max_evidenze=8,
            tolleranza_secondi=60
        )

        # =====================================================
        # 6. CARICAMENTO MESH E RUNTIME
        # =====================================================

        df_mesh = carica_telemetria_mesh_runtime(
            config=config,
            caso=caso,
            sorgente="mesh"
        )

        df_runtime = carica_telemetria_mesh_runtime(
            config=config,
            caso=caso,
            sorgente="runtime"
        )

        # =====================================================
        # 7. DETECTOR MESH / RUNTIME
        # =====================================================

        # Budget locale elevato:
        # tutte le anomalie devono poter partecipare
        # all'aggregazione e alla selezione globale.

        report_mr = rileva_evidenze_mesh_runtime(
            df_mesh=df_mesh,
            df_runtime=df_runtime,
            start_unix=int(inizio),
            end_unix=int(fine),
            max_evidenze_mesh=1000,
            max_evidenze_runtime=1000
        )

        # Non accettiamo evidenze troncate
        # prima dell'aggregazione.

        for sorgente in ("mesh", "runtime"):

            rilevate = (
                report_mr["conteggi"][
                    f"{sorgente}_rilevate"
                ]
            )

            selezionate = (
                report_mr["conteggi"][
                    f"{sorgente}_selezionate"
                ]
            )

            if rilevate != selezionate:

                raise ValueError(
                    f"Evidenze {sorgente} "
                    "troncate prima del budget globale."
                )

        # =====================================================
        # 8. AGGREGAZIONE MESH MULTI-REPLICA
        # =====================================================

        aggregazione_mesh = aggrega_evidenze_mesh(
            report=report_mr,
            tolleranza_secondi=180
        )

        # =====================================================
        # 9. REPORT UNIFICATO A1-v2
        # =====================================================

        evidence_report = (
            costruisci_report_unificato_v2(
                report_v2=report_v2,
                sintesi=sintesi,
                aggregazione_mesh=aggregazione_mesh,
                report_mesh_runtime=report_mr,
                max_evidenze_totali=10
            )
        )

        # =====================================================
        # 9 BIS. ABLAZIONE DELLE OTTO REGOLE DIAGNOSTICHE
        # =====================================================
        # A1_8R: report unificato + regole R01, R02, R06-R11.
        # A1: stesso report unificato, ma senza la sezione delle regole.
        # In questo modo isoliamo l'effetto informativo delle regole,
        # senza cambiare tool, modello, selezione Mesh/Runtime o prompt.
        # Nessuna lettura della ground truth.
        if config.canonical_variant in ("A1_8R", "A1_8R_Planning", "A1_PAVE"):
            from harness.rule_batch import costruisci_evidenze_regole

            evidence_report["regole_diagnostiche_v0"] = costruisci_evidenze_regole(
                df_nodi=df_nodi,
                df_container=df_container,
                start_unix=int(inizio),
                end_unix=int(fine),
            )

        if (
            evidence_report["versione"]
            != "unified_evidence_v2"
        ):

            raise ValueError(
                "Versione del report A1 non valida."
            )

        # =====================================================
        # 10. SERIALIZZAZIONE DETERMINISTICA
        # =====================================================

        evidence_text = json.dumps(
            evidence_report,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False
        )

        evidence_sha256 = hashlib.sha256(
            evidence_text.encode("utf-8")
        ).hexdigest()

        # =====================================================
        # 11. AGGIUNTA AL PROMPT A1
        # =====================================================

        richiesta += (
            "\n\n"
            "DETERMINISTIC A1 UNIFIED EVIDENCE REPORT v2\n"
            "\n"
            "The following observations were generated "
            "automatically from telemetry in the "
            "requested time interval.\n"
            "\n"
            "The report may contain evidence from:\n"
            "- Node metrics\n"
            "- Container metrics\n"
            "- Service Mesh metrics\n"
            "- Runtime metrics\n"
            "\n"
            "These observations are NOT ground truth.\n"
            "They do NOT establish the root cause.\n"
            "Temporal correlation does NOT prove causality.\n"
            "Correlated replicas and KPIs are not "
            "independent causal proofs.\n"
            "The absence of detected anomalies does not "
            "prove that a component is healthy.\n"
            "Some evidence may have been excluded "
            "by deterministic selection budgets.\n"
            "\n"
            "Treat the report as investigative context, "
            "not as a verified diagnosis.\n"
            "Use the available tools to investigate "
            "and verify hypotheses.\n"
            "Do not automatically assume that the "
            "earliest anomaly is the root cause.\n"
            "\n"
            "UNIFIED EVIDENCE JSON:\n"
            f"{evidence_text}\n"
        )

        # =====================================================
        # 12. TEMPO DI PREPROCESSING
        # =====================================================

        preprocessing_seconds = (
            time.perf_counter()
            - inizio_preprocessing
        )

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
    llm=None,
    verbose: bool = True,
    salva: bool = False
) -> dict:
    """
    Esegue un esperimento OpenRCA completo.

    Utilizza lo stesso motore LangGraph per A0 e A1.

    Se llm e\u0027 None, crea il modello con la Model Factory indicata nella
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

    # Il prompt viene recuperato automaticamente
    # in base alla variante sperimentale.
    system_prompt = get_system_prompt(config.canonical_variant)

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

    # V2 enforce: stessa istruzione per tutti i cinque agenti, costruita
    # SOLO da task_index e instruction del manifest GT-free. Non altera V1.
    if config.output_contract_mode == "v2_enforce":
        from output.v2_task_contract import task_output_instruction
        system_prompt += task_output_instruction(
            task_index=caso["task_index"],
            instruction=caso["instruction"],
        )

    # La preparazione di A1 genera automaticamente
    # le evidenze e misura il tempo del preprocessing.
    preprocessing_seconds = esperimento[
        "preprocessing_seconds"
    ]

    # =====================================================
    # 3. CREAZIONE DEL MODELLO
    # =====================================================

    if llm is None:

        from agent.model_factory import crea_modello

        llm = crea_modello(
            provider=config.model_provider,
            model_name=config.model_name
        )

    # =====================================================
    # 4. COSTRUZIONE DEL GRAFO CONDIVISO
    # =====================================================

    # A1_PAVE: il contesto ST e' calcolato in assenza di ground truth.
    # In A1_8R_Planning rimane None e il codice del grafo si comporta
    # come nella versione storica, senza aggiungere token al contesto.
    structural_context = None
    if config.canonical_variant == "A1_PAVE":
        from harness.structural_temporal_verifier import (
            costruisci_contesto_strutturale_temporale,
        )
        structural_context = costruisci_contesto_strutturale_temporale(
            esperimento["evidence_report"],
            start_unix=int(caso["start_unix"]),
            end_unix=int(caso["end_unix"]),
        )

    if config.canonical_variant in ("A1_8R_Planning", "A1_PAVE"):
        # Nuovo braccio sperimentale, completamente separato dal grafo
        # A0/A1. Budget totale: esplorazione + verifiche pre-finale.
        from agent.verify_graph import (
            crea_grafo_rca_verify,
            esegui_grafo_rca_verify,
        )
        grafo = crea_grafo_rca_verify(
            llm=llm,
            tools=tools,
            system_prompt=system_prompt,
            max_tool_rounds=config.max_tool_rounds,
            max_verification_checks=config.max_verification_checks,
            evidence_report=esperimento["evidence_report"],
            start_unix=int(caso["start_unix"]),
            end_unix=int(caso["end_unix"]),
            structural_context=structural_context,
        )
        esecuzione = esegui_grafo_rca_verify(
            grafo=grafo,
            richiesta=richiesta,
            recursion_limit=config.recursion_limit,
            verbose=verbose,
        )
    else:
        grafo = crea_grafo_rca(
            llm=llm,
            tools=tools,
            system_prompt=system_prompt,
            max_tool_rounds=config.max_tool_rounds
        )
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
    # 6 BIS. AUDIT OPZIONALE: SOLO OSSERVAZIONE
    # =====================================================
    # Non cambia la predizione o lo stato del parser storico.
    # Non ripara JSON e non consulta ground truth.
    output_contract_audit = None

    if config.output_contract_mode == "audit":
        from output.openrca_contract import (
            OutputContractError,
            parse_openrca_json,
        )

        try:
            diagnosi_canonica = parse_openrca_json(risposta)
            output_contract_audit = {
                "status": "valid",
                "fault_count": len(diagnosi_canonica.root_causes),
                "error": None,
                "cardinality_checked": False,
            }
        except OutputContractError as exc:
            output_contract_audit = {
                "status": "invalid",
                "fault_count": None,
                "error": str(exc),
                "cardinality_checked": False,
            }

    # =====================================================
    # 6 TER. FINALIZZAZIONE STRUTTURATA (NUOVA VARIANTE)
    # =====================================================
    # Una chiamata LLM aggiuntiva, contabilizzata separatamente.
    # Non modifica raw_response; nessuna ground truth.
    structured_report = None
    structured_usage = None

    if config.output_contract_mode == "structured":
        from output.structured_finalizer import (
            StructuredOutputError,
            formatta_diagnosi_strutturata,
        )

        # Registriamo anche la diagnosi accettata dal vecchio parser.
        original_json_status = json_status
        original_prediction = (
            json.dumps(predizione, ensure_ascii=False)
            if predizione is not None else None
        )
        try:
            output_strutturato = formatta_diagnosi_strutturata(
                llm=llm,
                raw_response=risposta,
                # Cardinalita': ancora non verificata in questa fase.
                expected_faults=None,
            )
            predizione = json.loads(output_strutturato.prediction)
            json_status = "valid_json"
            structured_usage = output_strutturato
            structured_report = {
                "status": "valid",
                "error": None,
                "original_json_status": original_json_status,
                "original_prediction": original_prediction,
                "cardinality_checked": False,
                "additional_llm_calls": 1,
                "elapsed_seconds": output_strutturato.elapsed_seconds,
                "usage_complete": output_strutturato.usage_available,
            }
        except (StructuredOutputError, ValueError, TypeError) as exc:
            predizione = None
            json_status = (
                f"invalid_structured_output: {type(exc).__name__}: {exc}"
            )
            structured_report = {
                "status": "invalid",
                "error": str(exc),
                "original_json_status": original_json_status,
                "original_prediction": original_prediction,
                "cardinality_checked": False,
                # Una chiamata API potrebbe essere stata fatturata
                # prima di un errore del provider/parsing.
                "additional_llm_calls": None,
                "elapsed_seconds": None,
                "usage_complete": False,
            }

    # =====================================================
    # 6 QUATER. CONTRATTO V2 TASK-AWARE, UGUALE PER TUTTI GLI AGENTI
    # =====================================================
    # I vincoli richiesti dallo specifico task sono controllati prima di
    # accettare una predizione; il fuori finestra resta un warning.
    # v2_audit non tocca le predizioni legacy; v2_enforce e' esplicito.
    # Nessuna chiamata LLM aggiuntiva, nessun repair automatico.
    v2_task_audit = None
    if config.output_contract_mode in ("v2_audit", "v2_enforce"):
        from output.v2_task_contract import (
            audit_task_output,
            enforce_task_output,
        )
        v2_context = {
            "task_index": caso["task_index"],
            "instruction": caso["instruction"],
            "start_unix": int(caso["start_unix"]),
            "end_unix": int(caso["end_unix"]),
        }
        if config.output_contract_mode == "v2_audit":
            v2_task_audit = audit_task_output(risposta, **v2_context)
        else:
            validated_json, json_status, v2_task_audit = enforce_task_output(
                risposta, **v2_context
            )
            predizione = (
                json.loads(validated_json)
                if validated_json is not None else None
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
    # Il costo della finalizzazione non va nascosto nel confronto.
    if config.output_contract_mode == "structured":
        metriche["structured_usage_complete"] = (
            structured_usage is not None and structured_usage.usage_available
        )
        if structured_usage is not None:
            metriche["llm_calls"] += 1
            metriche["input_tokens"] += structured_usage.input_tokens
            metriche["output_tokens"] += structured_usage.output_tokens
            metriche["total_tokens"] += structured_usage.total_tokens
            metriche["structured_output_seconds"] = (
                structured_usage.elapsed_seconds
            )
            metriche["structured_output_tokens"] = (
                structured_usage.total_tokens
            )
        else:
            metriche["structured_output_seconds"] = None
            metriche["structured_output_tokens"] = None

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
        "model_provider": config.model_provider,
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

    if config.canonical_variant in ("A1_8R_Planning", "A1_PAVE"):
        risultato["verification"] = esecuzione["verification"]
        risultato["max_verification_checks"] = config.max_verification_checks
        risultato["exploration_round_limit"] = (
            config.max_tool_rounds - config.max_verification_checks
        )

    if config.canonical_variant == "A1_PAVE":
        # Il report osservativo e' conservato separato dalla diagnosi.
        risultato["structural_temporal_context"] = structural_context
        risultato["structural_temporal_context_sha256"] = hashlib.sha256(
            json.dumps(
                structural_context, sort_keys=True, ensure_ascii=False,
                separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()

    # Per i nuovi audit conserviamo separatamente l'esito canonico:
    # la predizione originale e le metriche restano invariate.
    # Nelle run correnti registriamo il significato dell'etichetta
    # e la traduzione verso i JSON V3, senza alterare il formato storico.
    if config.variant_scheme == "current":
        from agent.variant_names import id_interno
        risultato["variant_scheme"] = "current"
        risultato["historical_variant"] = id_interno(config.canonical_variant)

    if output_contract_audit is not None:
        risultato["output_contract_audit"] = output_contract_audit

    if structured_report is not None:
        risultato["structured_output"] = structured_report

    if v2_task_audit is not None:
        risultato["output_contract_v2"] = v2_task_audit
        risultato["output_contract_mode"] = config.output_contract_mode

    # =====================================================
    # 9. SALVATAGGIO OPZIONALE
    # =====================================================

    if salva:

        # Usiamo un nome diverso dai vecchi piloti:
        # non dobbiamo sovrascrivere i risultati A0/A1
        # già valutati ufficialmente.

        suffisso_output = {
            "legacy": "",
            "audit": "_contract_audit",
            "structured": "_structured",
            "v2_audit": "_v2_audit",
            "v2_enforce": "_v2_enforce",
        }[config.output_contract_mode]
        # V2 salva in una directory distinta, sempre create-only.
        results_directory = (
            config.results_dir / "v2"
            if config.output_contract_mode in ("v2_audit", "v2_enforce")
            else config.results_dir
        )
        # Isolamento dei nuovi ID: "a1" non deve collidere con
        # il vecchio "a1" (che significava A1 con otto regole).
        if config.variant_scheme == "current":
            results_directory = results_directory / "final_names_v1"

        destinazione = (
            results_directory
            / f"{config.variant.lower()}_unified_"
              f"{config.case_id}{suffisso_output}.json"
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
