import zipfile
import pandas as pd
import re
from typing import Literal
from typing import Optional
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Costante per il percorso del dataset.
# Quando sei su Colab, lascia questo. Se testi in locale su PyCharm, metti il path del tuo PC.
DATASET_ZIP_PATH = '/content/drive/MyDrive/Tesi_OpenRCA/Market.zip'

TELEMETRY_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _get_telemetry_csv_paths(
    start_unix: int,
    end_unix: int,
    market_system: Literal["cloudbed-1", "cloudbed-2"],
    data_kind: Literal[
        "service_metrics",
        "container_metrics",
        "logs",
        "traces",
    ],
    log_type: Optional[Literal["service", "proxy"]] = None,
) -> list[str]:
    """
    Individua i percorsi dei CSV necessari per un intervallo temporale.

    I timestamp in ingresso sono Unix seconds.
    Le directory giornaliere seguono il calendario Asia/Shanghai.

    La funzione restituisce i percorsi; non legge né modifica i CSV.
    """

    if start_unix >= end_unix:
        raise ValueError(
            "L'inizio dell'intervallo deve precedere la fine."
        )

    if market_system not in ("cloudbed-1", "cloudbed-2"):
        raise ValueError(
            "market_system deve essere 'cloudbed-1' oppure 'cloudbed-2'."
        )

    percorsi_relativi = {
        "service_metrics": "metric/metric_service.csv",
        "container_metrics": "metric/metric_container.csv",
        "logs": f"log/log_{log_type}.csv",
        "traces": "trace/trace_span.csv",
    }

    if data_kind not in percorsi_relativi:
        raise ValueError(
            f"Tipo di telemetria non supportato: {data_kind}"
        )

    if data_kind == "logs" and log_type not in ("service", "proxy"):
        raise ValueError(
            "Per i log, log_type deve essere 'service' oppure 'proxy'."
        )

    data_inizio = (
        datetime.fromtimestamp(start_unix, tz=timezone.utc)
        .astimezone(TELEMETRY_TIMEZONE)
        .date()
    )

    # L'intervallo e' [start_unix, end_unix): il limite finale e' escluso.
    # Sottrarre un secondo evita di includere il giorno successivo
    # quando end_unix coincide esattamente con la mezzanotte locale.
    data_fine = (
        datetime.fromtimestamp(end_unix - 1, tz=timezone.utc)
        .astimezone(TELEMETRY_TIMEZONE)
        .date()
    )

    percorsi = []
    giorno = data_inizio

    while giorno <= data_fine:
        data_cartella = giorno.strftime("%Y_%m_%d")

        percorso = (
            f"Market/{market_system}/telemetry/"
            f"{data_cartella}/{percorsi_relativi[data_kind]}"
        )

        percorsi.append(percorso)
        giorno += timedelta(days=1)

    return percorsi



def tool_get_service_metrics(
    start_unix: int,
    end_unix: int,
    service_name: Optional[str] = None,
    max_rows: int = 30,
    market_system: Literal["cloudbed-1", "cloudbed-2"] = "cloudbed-1",
) -> str:
    """[TOOL AGENTE A0] Estrae le metriche rr, sr e mrt dei servizi.

    market_system seleziona il cloudbed; per compatibilita' il default e' cloudbed-1.
    La finestra temporale e' [start_unix, end_unix), con estremo finale escluso.
    """
    try:
        if start_unix >= end_unix:
            return "Errore: l'inizio deve precedere la fine dell'intervallo."
        if max_rows < 1:
            return "Errore: max_rows deve essere almeno 1."

        percorsi_csv = _get_telemetry_csv_paths(
            start_unix=start_unix,
            end_unix=end_unix,
            market_system=market_system,
            data_kind="service_metrics",
        )

        numero_righe = 0
        righe_restituite = 0
        risultati_grezzi = []
        frammenti_esplorativi = []

        with zipfile.ZipFile(DATASET_ZIP_PATH, 'r') as z:
            for percorso_csv in percorsi_csv:
                with z.open(percorso_csv) as f:
                    for chunk in pd.read_csv(f, chunksize=100_000):
                        timestamp = pd.to_numeric(chunk['timestamp'], errors='coerce')
                        mask = (timestamp >= start_unix) & (timestamp < end_unix)
                        df_time_filtered = chunk.loc[mask]

                        if df_time_filtered.empty:
                            continue

                        if service_name:
                            df_filtered = df_time_filtered[
                                df_time_filtered['service'] == service_name
                            ]
                            numero_righe += len(df_filtered)
                            righe_disponibili = max_rows - righe_restituite
                            if righe_disponibili > 0 and not df_filtered.empty:
                                campione = df_filtered.head(righe_disponibili)
                                risultati_grezzi.append(campione)
                                righe_restituite += len(campione)
                        else:
                            frammenti_esplorativi.append(df_time_filtered)

        if service_name:
            if numero_righe == 0:
                return f"Nessuna metrica trovata per il servizio {service_name}."
            df_risultato = pd.concat(risultati_grezzi, ignore_index=True)
            return (
                f"Intervallo Unix: {start_unix} - {end_unix}\n"
                f"Servizio: {service_name}\n"
                f"Campioni trovati: {numero_righe}\n"
                f"Campioni restituiti: {len(df_risultato)}\n\n"
                f"{df_risultato.to_string(index=False)}"
            )

        if not frammenti_esplorativi:
            return "Nessuna metrica trovata in questo intervallo."

        df_completo = pd.concat(frammenti_esplorativi, ignore_index=True)
        riepilogo = df_completo.groupby('service').agg(
            campioni=('timestamp', 'size'),
            rr_media=('rr', 'mean'),
            sr_media=('sr', 'mean'),
            mrt_media=('mrt', 'mean'),
            mrt_max=('mrt', 'max'),
        ).reset_index()

        totale_servizi = len(riepilogo)
        risultato = riepilogo.head(max_rows)
        return (
            f"Intervallo Unix: {start_unix} - {end_unix}\n"
            f"Servizi trovati: {totale_servizi}\n"
            f"Servizi mostrati: {len(risultato)}\n\n"
            f"{risultato.to_string(index=False)}"
        )
    except Exception as e:
        return f"Errore del tool: {str(e)}"

def tool_get_container_metrics(
    start_unix: int,
    end_unix: int,
    cmdb_id: Optional[str] = None,
    kpi_name: Optional[str] = None,
    max_rows: int = 100,
    market_system: Literal["cloudbed-1", "cloudbed-2"] = "cloudbed-1",
) -> str:
    """
    [TOOL AGENTE A0]
    Analizza le metriche dei container a blocchi e restituisce
    statistiche descrittive per ogni coppia componente/KPI.

    Le statistiche permettono di osservare minimo, massimo,
    media e relativa collocazione temporale senza restituire
    soltanto le prime righe del CSV.

    market_system seleziona il cloudbed, per default cloudbed-1.
    La finestra temporale e' [start_unix, end_unix).
    """

    try:
        if start_unix >= end_unix:
            return "Errore: l'inizio deve precedere la fine dell'intervallo."

        if max_rows < 1:
            return "Errore: max_rows deve essere almeno 1."

        # Una ricerca senza componente e senza KPI sarebbe
        # troppo ampia per restituire un riepilogo utile.
        if not cmdb_id and not kpi_name:
            return (
                "Query troppo ampia. Specificare almeno "
                "cmdb_id oppure kpi_name."
            )

        # Verifichiamo che il filtro regex sia valido.
        pattern = None

        if kpi_name:
            try:
                pattern = re.compile(kpi_name, re.IGNORECASE)
            except re.error as exc:
                return f"Errore: espressione regex non valida: {exc}"

        # Statistiche mantenute in memoria per ogni coppia
        # (componente, KPI), senza conservare tutto il CSV.
        statistiche = {}
        numero_record = 0

        percorsi_csv = _get_telemetry_csv_paths(
            start_unix=start_unix,
            end_unix=end_unix,
            market_system=market_system,
            data_kind="container_metrics",
        )

        with zipfile.ZipFile(DATASET_ZIP_PATH, "r") as archivio:
            for percorso_csv in percorsi_csv:
                with archivio.open(percorso_csv) as file_csv:

                    for chunk in pd.read_csv(
                        file_csv,
                        chunksize=100_000
                    ):
                        timestamp = pd.to_numeric(
                            chunk["timestamp"],
                            errors="coerce"
                        )

                        valori = pd.to_numeric(
                            chunk["value"],
                            errors="coerce"
                        )

                        mask = (
                            ((timestamp >= start_unix) & (timestamp < end_unix))
                            & valori.notna()
                            & timestamp.notna()
                        )

                        # Filtro del componente.
                        # Supporta sia l'ID semplice sia quello
                        # preceduto dal nodo, ad esempio node-6.
                        if cmdb_id:
                            cmdb = (
                                chunk["cmdb_id"]
                                .astype(str)
                                .str.lower()
                            )

                            cercato = cmdb_id.strip().lower()

                            mask &= (
                                cmdb.eq(cercato)
                                | cmdb.str.endswith(
                                    f".{cercato}",
                                    na=False
                                )
                            )

                        # Filtro per nome KPI.
                        if pattern is not None:
                            mask &= chunk["kpi_name"].astype(
                                str
                            ).str.contains(
                                pattern,
                                na=False
                            )

                        filtrati = chunk.loc[mask].copy()

                        if filtrati.empty:
                            continue

                        filtrati["timestamp"] = timestamp.loc[mask]
                        filtrati["value"] = valori.loc[mask]

                        numero_record += len(filtrati)

                        colonne = [
                            "timestamp",
                            "cmdb_id",
                            "kpi_name",
                            "value"
                        ]

                        for timestamp_riga, componente, kpi, valore in (
                            filtrati[colonne].itertuples(
                                index=False,
                                name=None
                            )
                        ):
                            timestamp_riga = float(timestamp_riga)
                            valore = float(valore)

                            chiave = (
                                str(componente),
                                str(kpi)
                            )

                            if chiave not in statistiche:
                                statistiche[chiave] = {
                                    "campioni": 0,
                                    "somma": 0.0,
                                    "minimo": valore,
                                    "timestamp_minimo": timestamp_riga,
                                    "massimo": valore,
                                    "timestamp_massimo": timestamp_riga,
                                    "primo_timestamp": timestamp_riga,
                                    "primo_valore": valore,
                                    "ultimo_timestamp": timestamp_riga,
                                    "ultimo_valore": valore,
                                }

                            s = statistiche[chiave]
                            s["campioni"] += 1
                            s["somma"] += valore

                            if valore < s["minimo"]:
                                s["minimo"] = valore
                                s["timestamp_minimo"] = timestamp_riga

                            if valore > s["massimo"]:
                                s["massimo"] = valore
                                s["timestamp_massimo"] = timestamp_riga

                            if timestamp_riga < s["primo_timestamp"]:
                                s["primo_timestamp"] = timestamp_riga
                                s["primo_valore"] = valore

                            if timestamp_riga >= s["ultimo_timestamp"]:
                                s["ultimo_timestamp"] = timestamp_riga
                                s["ultimo_valore"] = valore

        if not statistiche:
            return (
                f"Nessun dato per cmdb_id={cmdb_id} "
                f"e kpi_name={kpi_name}."
            )

        righe = []

        for (componente, kpi), s in statistiche.items():
            righe.append({
                "cmdb_id": componente,
                "kpi_name": kpi,
                "campioni": s["campioni"],
                "media": s["somma"] / s["campioni"],
                "minimo": s["minimo"],
                "timestamp_minimo": s["timestamp_minimo"],
                "massimo": s["massimo"],
                "timestamp_massimo": s["timestamp_massimo"],
                "primo_valore": s["primo_valore"],
                "primo_timestamp": s["primo_timestamp"],
                "ultimo_valore": s["ultimo_valore"],
                "ultimo_timestamp": s["ultimo_timestamp"],
            })

        riepilogo = pd.DataFrame(righe).sort_values(
            ["cmdb_id", "kpi_name"]
        )

        gruppi_totali = len(riepilogo)

        # Evita risposte eccessivamente lunghe se la query
        # produce moltissime combinazioni componente/KPI.
        if gruppi_totali > max_rows:
            riepilogo = riepilogo.head(max_rows)

        colonne_numeriche = [
            "media",
            "minimo",
            "massimo",
            "primo_valore",
            "ultimo_valore",
        ]

        riepilogo[colonne_numeriche] = (
            riepilogo[colonne_numeriche].round(6)
        )

        riepilogo[
            [
                "timestamp_minimo",
                "timestamp_massimo",
                "primo_timestamp",
                "ultimo_timestamp",
            ]
        ] = riepilogo[
            [
                "timestamp_minimo",
                "timestamp_massimo",
                "primo_timestamp",
                "ultimo_timestamp",
            ]
        ].astype("int64")

        return (
            f"Intervallo Unix (secondi): "
            f"{start_unix} - {end_unix}\n"
            f"Filtro componente: {cmdb_id or 'Tutti'}\n"
            f"Filtro KPI: {kpi_name or 'Nessuno'}\n"
            f"Record analizzati: {numero_record}\n"
            f"Gruppi componente/KPI trovati: {gruppi_totali}\n"
            f"Gruppi mostrati: {len(riepilogo)}\n\n"
            f"{riepilogo.to_string(index=False)}"
        )

    except Exception as exc:
        return f"Errore del tool: {type(exc).__name__}: {exc}"



def tool_get_logs(
    start_unix: int,
    end_unix: int,
    log_type: Literal["service", "proxy"] = "service",
    cmdb_id: Optional[str] = None,
    keyword: Optional[str] = None,
    max_rows: int = 30,
    market_system: Literal["cloudbed-1", "cloudbed-2"] = "cloudbed-1",
) -> str:
    """[TOOL AGENTE A0] Estrae log ordinati cronologicamente (Rolling Top-K).

    La finestra temporale e' [start_unix, end_unix), con fine esclusa.
    Il cloudbed predefinito resta cloudbed-1 per compatibilita' con A0.
    """
    if start_unix >= end_unix:
        return "Errore: l'inizio deve precedere la fine."
    if max_rows < 1:
        return "Errore: max_rows almeno 1."
    if log_type not in ("service", "proxy"):
        return "Errore: log_type deve essere 'service' o 'proxy'."

    numero_righe = 0
    risultati = pd.DataFrame()

    try:
        percorsi_csv = _get_telemetry_csv_paths(
            start_unix=start_unix,
            end_unix=end_unix,
            market_system=market_system,
            data_kind="logs",
            log_type=log_type,
        )

        with zipfile.ZipFile(DATASET_ZIP_PATH, "r") as archivio:
            for percorso_csv in percorsi_csv:
                with archivio.open(percorso_csv) as file_csv:
                    for chunk in pd.read_csv(file_csv, chunksize=100_000):
                        timestamp = pd.to_numeric(chunk["timestamp"], errors="coerce")
                        mask = (timestamp >= start_unix) & (timestamp < end_unix)

                        if cmdb_id:
                            cmdb = chunk["cmdb_id"].astype(str).str.lower()
                            cercato = cmdb_id.strip().lower()
                            mask &= (
                                cmdb.eq(cercato)
                                | cmdb.str.startswith(f"{cercato}-", na=False)
                            )
                        if keyword:
                            mask &= chunk["value"].astype(str).str.contains(
                                keyword, case=False, na=False, regex=False
                            )

                        df_filtered = chunk.loc[mask].copy()
                        df_filtered["timestamp"] = timestamp.loc[mask]
                        numero_righe += len(df_filtered)

                        if not df_filtered.empty:
                            campione = df_filtered.sort_values(
                                ["timestamp", "log_id"], kind="stable"
                            ).head(max_rows)
                            if risultati.empty:
                                risultati = campione.copy()
                            else:
                                risultati = pd.concat(
                                    [risultati, campione], ignore_index=True
                                )
                            risultati = risultati.sort_values(
                                ["timestamp", "log_id"], kind="stable"
                            ).head(max_rows).reset_index(drop=True)

        if numero_righe == 0:
            return (
                f"Nessun log '{log_type}' per cmdb_id={cmdb_id} "
                f"e keyword='{keyword}'."
            )
        return (
            f"Intervallo Unix: {start_unix} - {end_unix}\n"
            f"Tipo Log: {log_type}\n"
            f"Componente: {cmdb_id or 'Tutti'}\n"
            f"Filtro: {keyword or 'Nessuna'}\n"
            f"Record trovati: {numero_righe}\n"
            f"Record mostrati: {len(risultati)}\n\n"
            f"{risultati.to_string(index=False)}"
        )
    except Exception as e:
        return f"Errore del tool: {str(e)}"


def tool_get_traces(
        start_unix: int,
        end_unix: int,
        cmdb_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        min_duration_ms: Optional[int] = None,
        max_rows: int = 30,
        market_system: Literal["cloudbed-1", "cloudbed-2"] = "cloudbed-1",
) -> str:
    """[TOOL AGENTE A0] Estrae i trace span piu' lenti (Rolling Top-K).

    market_system sceglie cloudbed-1 o cloudbed-2 (default cloudbed-1).
    Intervallo [start_unix, end_unix); gli input sono secondi Unix,
    il timestamp CSV e' in millisecondi e duration e' in microsecondi.
    """

    # Validazione dei parametri ricevuti dal tool.
    if start_unix >= end_unix:
        return "Errore: l'inizio deve precedere la fine."

    if max_rows < 1:
        return "Errore: max_rows almeno 1."

    if min_duration_ms is not None and min_duration_ms < 0:
        return "Errore: min_duration_ms non negativo."

    # Il parametro temporale ricevuto è espresso in secondi Unix.
    # Nel CSV, timestamp è espresso in millisecondi Unix.
    start_ms = start_unix * 1000
    end_ms = end_unix * 1000

    # Contatore di tutti gli span che soddisfano i filtri.
    numero_righe = 0

    # Manteniamo in memoria soltanto i migliori max_rows span.
    risultati = pd.DataFrame()

    try:
        percorsi_csv = _get_telemetry_csv_paths(
            start_unix=start_unix,
            end_unix=end_unix,
            market_system=market_system,
            data_kind="traces",
        )

        # Apriamo lo ZIP senza estrarlo e leggiamo i giorni necessari.
        with zipfile.ZipFile(DATASET_ZIP_PATH, 'r') as z:
            for percorso_csv in percorsi_csv:
                with z.open(percorso_csv) as f:

                    # Leggiamo il file a blocchi per contenere l'utilizzo
                    # della memoria, dato che il dataset è molto grande.
                    for chunk in pd.read_csv(f, chunksize=100_000):

                        # Convertiamo i timestamp in valori numerici.
                        timestamp_ms = pd.to_numeric(
                            chunk['timestamp'],
                            errors='coerce'
                        )

                        # La durata grezza è trattata come microsecondi.
                        duration_us = pd.to_numeric(
                            chunk['duration'],
                            errors='coerce'
                        )

                        # Selezioniamo gli span nella finestra temporale
                        # ed escludiamo le durate mancanti o non numeriche.
                        mask = (
                            (timestamp_ms >= start_ms)
                            & (timestamp_ms < end_ms)
                            & duration_us.notna()
                        )

                        # Filtro opzionale per componente.
                        if cmdb_id:
                            cercato = re.escape(cmdb_id.strip().lower())

                            cmdb = chunk['cmdb_id'].astype(str).str.lower()

                            mask &= cmdb.str.contains(
                                rf"(?:^|\.){cercato}(?:-\d+)?$",
                                regex=True,
                                na=False
                            )

                        # Filtro opzionale per identificativo della trace.
                        if trace_id:
                            mask &= chunk['trace_id'].astype(str).eq(trace_id)

                        # Convertiamo la soglia da millisecondi a microsecondi
                        # prima di confrontarla con la durata grezza.
                        if min_duration_ms is not None:
                            min_duration_us = min_duration_ms * 1000

                            mask &= duration_us >= min_duration_us

                        # Conserviamo soltanto le righe che soddisfano
                        # tutti i filtri applicati.
                        df_filtered = chunk.loc[mask].copy()

                        # Manteniamo timestamp in millisecondi Unix.
                        df_filtered['timestamp'] = timestamp_ms.loc[mask]

                        # Manteniamo duration in microsecondi durante
                        # i filtri e l'ordinamento.
                        df_filtered['duration'] = duration_us.loc[mask]

                        # Contiamo tutti gli span corrispondenti,
                        # non soltanto quelli che verranno mostrati.
                        numero_righe += len(df_filtered)

                        if not df_filtered.empty:

                            # Selezioniamo i max_rows span più lenti
                            # del blocco corrente.
                            # In caso di parità, preferiamo il timestamp
                            # più vecchio.
                            campione = df_filtered.sort_values(
                                ['duration', 'timestamp'],
                                ascending=[False, True]
                            ).head(max_rows)

                            # Inizializziamo i risultati oppure li uniamo
                            # ai migliori span già trovati.
                            if risultati.empty:
                                risultati = campione.copy()
                            else:
                                risultati = pd.concat(
                                    [risultati, campione],
                                    ignore_index=True
                                )

                            # Rolling Top-K: dopo ogni blocco conserviamo
                            # soltanto i max_rows span più lenti trovati
                            # fino a quel momento.
                            risultati = (
                                risultati
                                .sort_values(
                                    ['duration', 'timestamp'],
                                    ascending=[False, True]
                                )
                                .head(max_rows)
                                .reset_index(drop=True)
                            )

        # Se nessuno span soddisfa i filtri, restituiamo un messaggio.
        if numero_righe == 0:
            return (
                f"Nessuna traccia per cmdb_id={cmdb_id} "
                f"e trace_id={trace_id}."
            )

        # Selezioniamo le colonne che vogliamo esporre all'agente.
        colonne_output = [
            'timestamp',
            'cmdb_id',
            'span_id',
            'trace_id',
            'duration',
            'operation_name',
            'parent_span',
            'status_code'
        ]

        colonne_presenti = [
            c for c in colonne_output
            if c in risultati.columns
        ]

        risultati = risultati[colonne_presenti]

        # Creiamo una copia destinata esclusivamente all'output.
        # I risultati originali mantengono la durata in microsecondi.
        risultati_output = risultati.copy()

        # Convertiamo la durata in millisecondi per renderla
        # leggibile e coerente con il parametro min_duration_ms.
        risultati_output['duration'] = (
            pd.to_numeric(
                risultati_output['duration'],
                errors='coerce'
            ) / 1000
        ).round(3)

        # Usiamo un controllo esplicito per gestire correttamente
        # anche una soglia uguale a zero.
        durata_minima_testo = (
            min_duration_ms
            if min_duration_ms is not None
            else 'Nessuna'
        )

        # Restituiamo il riepilogo e gli span selezionati.
        return (
            f"Intervallo: {start_unix} - {end_unix}\n"
            f"Componente: {cmdb_id or 'Tutti'}\n"
            f"Trace ID: {trace_id or 'Tutti'}\n"
            f"Durata Minima (ms): {durata_minima_testo}\n"
            f"Span trovati: {numero_righe}\n"
            f"Span mostrati: {len(risultati_output)}\n\n"
            f"{risultati_output.to_string(index=False)}"
        )

    except Exception as e:
        return f"Errore del tool: {str(e)}"


# ESPORTAZIONE LISTA TOOLS PER LANGGRAPH
A0_TOOLS = [
    tool_get_service_metrics,
    tool_get_container_metrics,
    tool_get_logs,
    tool_get_traces
]