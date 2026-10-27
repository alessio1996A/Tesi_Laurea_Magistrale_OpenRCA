import zipfile
import pandas as pd
import re
from typing import Optional

# Costante per il percorso del dataset.
# Quando sei su Colab, lascia questo. Se testi in locale su PyCharm, metti il path del tuo PC.
DATASET_ZIP_PATH = '/content/drive/MyDrive/Tesi_OpenRCA/Market.zip'


def tool_get_service_metrics(
        start_unix: int, end_unix: int, service_name: Optional[str] = None, max_rows: int = 30
) -> str:
    """[TOOL AGENTE A0] Estrae le metriche rr (Request Rate), sr (Success Rate) e mrt (Mean Response Time)."""
    target_csv = 'Market/cloudbed-1/telemetry/2022_03_20/metric/metric_service.csv'
    try:
        if start_unix > end_unix: return "Errore: l'inizio supera la fine dell'intervallo."
        if max_rows < 1: return "Errore: max_rows deve essere almeno 1."

        numero_righe = 0
        righe_restituite = 0
        risultati_grezzi = []
        frammenti_esplorativi = []

        with zipfile.ZipFile(DATASET_ZIP_PATH, 'r') as z:
            with z.open(target_csv) as f:
                for chunk in pd.read_csv(f, chunksize=100_000):
                    timestamp = pd.to_numeric(chunk['timestamp'], errors='coerce')
                    mask = timestamp.between(start_unix, end_unix)
                    df_time_filtered = chunk.loc[mask]

                    if df_time_filtered.empty: continue

                    if service_name:
                        df_filtered = df_time_filtered[df_time_filtered['service'] == service_name]
                        numero_righe += len(df_filtered)
                        righe_disponibili = max_rows - righe_restituite
                        if righe_disponibili > 0 and not df_filtered.empty:
                            campione = df_filtered.head(righe_disponibili)
                            risultati_grezzi.append(campione)
                            righe_restituite += len(campione)
                    else:
                        frammenti_esplorativi.append(df_time_filtered)

        if service_name:
            if numero_righe == 0: return f"Nessuna metrica trovata per il servizio {service_name}."
            df_risultato = pd.concat(risultati_grezzi, ignore_index=True)
            return (f"Intervallo Unix: {start_unix} - {end_unix}\nServizio: {service_name}\n"
                    f"Campioni trovati: {numero_righe}\nCampioni restituiti: {len(df_risultato)}\n\n"
                    f"{df_risultato.to_string(index=False)}")

        if not frammenti_esplorativi: return "Nessuna metrica trovata in questo intervallo."

        df_completo = pd.concat(frammenti_esplorativi, ignore_index=True)
        riepilogo = df_completo.groupby('service').agg(
            campioni=('timestamp', 'size'), rr_media=('rr', 'mean'),
            sr_media=('sr', 'mean'), mrt_media=('mrt', 'mean'), mrt_max=('mrt', 'max')
        ).reset_index()

        totale_servizi = len(riepilogo)
        risultato = riepilogo.head(max_rows)
        return (f"Intervallo Unix: {start_unix} - {end_unix}\nServizi trovati: {totale_servizi}\n"
                f"Servizi mostrati: {len(risultato)}\n\n{risultato.to_string(index=False)}")
    except Exception as e:
        return f"Errore del tool: {str(e)}"


def tool_get_container_metrics(
        start_unix: int, end_unix: int, cmdb_id: Optional[str] = None, kpi_name: Optional[str] = None,
        max_rows: int = 30
) -> str:
    """[TOOL AGENTE A0] Estrae i KPI infrastrutturali (CPU, Memoria, I/O, Network) dei container."""
    target_csv = 'Market/cloudbed-1/telemetry/2022_03_20/metric/metric_container.csv'
    try:
        if start_unix > end_unix: return "Errore: l'inizio supera la fine."
        if max_rows < 1: return "Errore: max_rows almeno 1."

        numero_righe = 0
        risultati = []

        with zipfile.ZipFile(DATASET_ZIP_PATH, 'r') as z:
            with z.open(target_csv) as f:
                for chunk in pd.read_csv(f, chunksize=100_000):
                    timestamp = pd.to_numeric(chunk['timestamp'], errors='coerce')
                    mask = timestamp.between(start_unix, end_unix)

                    if cmdb_id:
                        cmdb = chunk['cmdb_id'].astype(str)
                        mask &= (cmdb.eq(cmdb_id) | cmdb.str.endswith(f".{cmdb_id}", na=False))
                    if kpi_name:
                        mask &= chunk['kpi_name'].str.contains(kpi_name, case=False, na=False, regex=True)

                    df_filtered = chunk.loc[mask].copy()
                    numero_righe += len(df_filtered)
                    righe_disponibili = max_rows - sum(len(df) for df in risultati)

                    if righe_disponibili > 0 and not df_filtered.empty:
                        risultati.append(df_filtered.head(righe_disponibili))

        if numero_righe == 0: return f"Nessun dato per cmdb_id={cmdb_id} e kpi_name={kpi_name}."
        df_risultato = pd.concat(risultati, ignore_index=True)
        return (f"Intervallo Unix: {start_unix} - {end_unix}\nContainer: {cmdb_id or 'Tutti'}\n"
                f"Filtro KPI: {kpi_name or 'Nessuno'}\nRecord trovati: {numero_righe}\n"
                f"Record mostrati: {len(df_risultato)}\n\n{df_risultato.to_string(index=False)}")
    except Exception as e:
        return f"Errore del tool: {str(e)}"


def tool_get_logs(
        start_unix: int, end_unix: int, log_type: str = 'service', cmdb_id: Optional[str] = None,
        keyword: Optional[str] = None, max_rows: int = 30
) -> str:
    """[TOOL AGENTE A0] Estrae e analizza i log di sistema con Rolling Top-K per l'ordinamento cronologico."""
    target_csv = f'Market/cloudbed-1/telemetry/2022_03_20/log/log_{log_type}.csv'
    if start_unix > end_unix: return "Errore: l'inizio supera la fine."
    if max_rows < 1: return "Errore: max_rows almeno 1."
    if log_type not in ('service', 'proxy'): return "Errore: log_type deve essere 'service' o 'proxy'."

    numero_righe = 0
    risultati = pd.DataFrame()

    try:
        with zipfile.ZipFile(DATASET_ZIP_PATH, 'r') as z:
            with z.open(target_csv) as f:
                for chunk in pd.read_csv(f, chunksize=100_000):
                    timestamp = pd.to_numeric(chunk['timestamp'], errors='coerce')
                    mask = timestamp.between(start_unix, end_unix)

                    if cmdb_id:
                        cmdb = chunk['cmdb_id'].astype(str).str.lower()
                        cercato = cmdb_id.strip().lower()
                        mask &= (cmdb.eq(cercato) | cmdb.str.startswith(f"{cercato}-", na=False))
                    if keyword:
                        mask &= chunk['value'].astype(str).str.contains(keyword, case=False, na=False, regex=False)

                    df_filtered = chunk.loc[mask].copy()
                    df_filtered['timestamp'] = timestamp.loc[mask]
                    numero_righe += len(df_filtered)

                    if not df_filtered.empty:
                        campione = df_filtered.sort_values(['timestamp', 'log_id'], kind='stable').head(max_rows)
                        if risultati.empty:
                            risultati = campione.copy()
                        else:
                            risultati = pd.concat([risultati, campione], ignore_index=True)
                        risultati = risultati.sort_values(['timestamp', 'log_id'], kind='stable').head(
                            max_rows).reset_index(drop=True)

        if numero_righe == 0: return f"Nessun log '{log_type}' per cmdb_id={cmdb_id} e keyword='{keyword}'."
        return (f"Intervallo Unix: {start_unix} - {end_unix}\nTipo Log: {log_type}\n"
                f"Componente: {cmdb_id or 'Tutti'}\nFiltro: {keyword or 'Nessuna'}\n"
                f"Record trovati: {numero_righe}\nRecord mostrati: {len(risultati)}\n\n{risultati.to_string(index=False)}")
    except Exception as e:
        return f"Errore del tool: {str(e)}"


def tool_get_traces(
        start_unix: int,
        end_unix: int,
        cmdb_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        min_duration_ms: Optional[int] = None,
        max_rows: int = 30
) -> str:
    """[TOOL AGENTE A0] Estrae i trace span filtrandoli e ordinandoli per quelli più lenti (Rolling Top-K decrescente)."""

    # Percorso del file delle trace all'interno di Market.zip.
    target_csv = 'Market/cloudbed-1/telemetry/2022_03_20/trace/trace_span.csv'

    # Validazione dei parametri ricevuti dal tool.
    if start_unix > end_unix:
        return "Errore: l'inizio supera la fine."

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
        # Apriamo il dataset ZIP senza estrarlo interamente su disco.
        with zipfile.ZipFile(DATASET_ZIP_PATH, 'r') as z:
            with z.open(target_csv) as f:

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
                        timestamp_ms.between(start_ms, end_ms)
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