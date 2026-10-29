import pandas as pd


# ============================================================
# 1. CATALOGO DEI SEGNALI
# ============================================================
#
# Ogni KPI viene associato a:
#
# - famiglia: tipologia della risorsa
# - tipo: gauge oppure altro tipo ancora da verificare
# - direzione: variazione potenzialmente sospetta
#
# "alto" = aumenti potenzialmente anomali
# "basso" = diminuzioni potenzialmente anomale
#
# ATTENZIONE:
# Un'anomalia non dimostra da sola una root cause.
# ============================================================

GAUGE_NODI = {

    # CPU e load
    "system.cpu.pct_usage": ("cpu", "alto"),
    "system.cpu.user": ("cpu", "alto"),
    "system.cpu.system": ("cpu", "alto"),
    "system.cpu.iowait": ("io", "alto"),
    "system.load.1": ("cpu", "alto"),
    "system.load.5": ("cpu", "alto"),
    "system.load.15": ("cpu", "alto"),

    # Memoria
    "system.mem.pct_usage": ("memoria", "alto"),
    "system.mem.real.pct_useage": ("memoria", "alto"),
    "system.mem.real.used": ("memoria", "alto"),
    "system.mem.used": ("memoria", "alto"),
    "system.mem.free": ("memoria", "basso"),
    "system.mem.usable": ("memoria", "basso"),

    # Disco
    "system.disk.pct_usage": ("disco", "alto"),
    "system.disk.used": ("disco", "alto"),
    "system.disk.free": ("disco", "basso"),

    # I/O
    "system.io.util": ("io", "alto"),
    "system.io.await": ("io", "alto"),
    "system.io.r_await": ("io", "alto"),
    "system.io.w_await": ("io", "alto"),
    "system.io.avg_q_sz": ("io", "alto"),
}


GAUGE_CONTAINER = {

    # Memoria container
    "container_memory_usage_MB": ("memoria", "alto"),
    "container_memory_working_set_MB": ("memoria", "alto"),
    "container_memory_rss": ("memoria", "alto"),
    "container_memory_swap": ("memoria", "alto"),

    # Load CPU, se effettivamente variabile
    "container_cpu_load_average_10s": ("cpu", "alto"),
}


def descrivi_kpi(sorgente: str, kpi_name: str) -> dict:
    """
    Restituisce la descrizione semantica del KPI.

    I KPI sconosciuti NON vengono interpretati
    automaticamente come gauge.

    Questa è una whitelist iniziale, non un catalogo
    esaustivo di tutte le metriche OpenRCA.
    """

    if sorgente == "node_metrics":
        catalogo = GAUGE_NODI

    elif sorgente == "container_metrics":
        catalogo = GAUGE_CONTAINER

    else:
        raise ValueError(
            f"Sorgente non supportata: {sorgente}"
        )

    if kpi_name not in catalogo:
        return {
            "famiglia": "non_classificato",
            "tipo": "non_verificato",
            "direzione": None
        }

    famiglia, direzione = catalogo[kpi_name]

    return {
        "famiglia": famiglia,
        "tipo": "gauge_candidato",
        "direzione": direzione
    }


# ============================================================
# 2. PROFILAZIONE DELLE SERIE
# ============================================================

def profila_segnali(
    df: pd.DataFrame,
    sorgente: str,
    min_campioni: int = 10,
    min_valori_distinti: int = 3
) -> pd.DataFrame:
    """
    Costruisce il catalogo dei segnali osservati
    nella finestra temporale.

    Una serie è identificata da:
        (cmdb_id, kpi_name)

    Una serie è candidata all'analisi quando:
        - il KPI è nella whitelist;
        - ha abbastanza campioni numerici;
        - presenta abbastanza valori distinti.

    Non identifica anomalie o root cause.
    """

    colonne = {
        "cmdb_id",
        "kpi_name",
        "timestamp",
        "value"
    }

    if not colonne.issubset(df.columns):
        raise ValueError(
            f"Colonne mancanti: {colonne - set(df.columns)}"
        )

    if sorgente not in ("node_metrics", "container_metrics"):
        raise ValueError("Sorgente non valida.")

    if min_campioni < 1 or min_valori_distinti < 1:
        raise ValueError("Soglie di qualità non valide.")

    records = []

    # GroupBy per identificare ogni serie temporale.
    for (componente, kpi), gruppo in df.groupby(
        ["cmdb_id", "kpi_name"],
        dropna=False
    ):

        valori = pd.to_numeric(
            gruppo["value"],
            errors="coerce"
        )

        validi = valori.dropna()

        descrizione = descrivi_kpi(
            sorgente,
            str(kpi)
        )

        numero_validi = len(validi)
        numero_distinti = validi.nunique()

        sufficiente = (
            numero_validi >= min_campioni
        )

        variabile = (
            numero_distinti >= min_valori_distinti
        )

        candidato = (
            descrizione["tipo"] == "gauge_candidato"
            and sufficiente
            and variabile
        )

        records.append({
            "sorgente": sorgente,
            "cmdb_id": str(componente),
            "kpi_name": str(kpi),
            "famiglia": descrizione["famiglia"],
            "tipo": descrizione["tipo"],
            "direzione": descrizione["direzione"],
            "campioni": len(gruppo),
            "validi": numero_validi,
            "distinti": int(numero_distinti),
            "costante": (
                numero_validi > 0
                and numero_distinti == 1
            ),
            "candidato": bool(candidato)
        })

    risultato = pd.DataFrame(
        records,
        columns=[
            "sorgente",
            "cmdb_id",
            "kpi_name",
            "famiglia",
            "tipo",
            "direzione",
            "campioni",
            "validi",
            "distinti",
            "costante",
            "candidato"
        ]
    )

    if not risultato.empty:

        risultato = risultato.sort_values(
            ["famiglia", "cmdb_id", "kpi_name"]
        ).reset_index(drop=True)

    return risultato
def descrivi_kpi_mesh_runtime(
    sorgente: str,
    kpi_name: str
) -> dict | None:
    """
    Catalogo semantico preliminare per Mesh e Runtime.

    Non classifica automaticamente tutti i KPI.
    Riconosce soltanto famiglie studiate sui dati.

    Restituisce None per KPI non riconosciuti.
    """

    if not isinstance(kpi_name, str):
        return None

    # =====================================================
    # 1. METRICHE MESH
    # =====================================================

    if sorgente == "mesh":

        famiglie = {
            "istio_requests.": (
                "traffico_richieste",
                "livello_osservato",
                None
            ),

            "istio_request_duration_milliseconds.": (
                "durata_richieste",
                "livello_osservato",
                "alto"
            ),

            "istio_request_bytes.": (
                "volume_richieste",
                "livello_osservato",
                None
            ),

            "istio_response_bytes.": (
                "volume_risposte",
                "livello_osservato",
                None
            )
        }

        for prefisso, dati in famiglie.items():

            if (
                kpi_name.startswith(prefisso)
                and len(kpi_name) > len(prefisso)
            ):

                famiglia, trasformazione, direzione = dati

                return {
                    "sorgente": "mesh",
                    "kpi": kpi_name,
                    "famiglia": famiglia,
                    "tipo": "livello_non_cumulativo_candidato",
                    "trasformazione": trasformazione,
                    "direzione": direzione,
                    "semantica_verificata": False,
                    "nota": (
                        "La serie osservata non va "
                        "interpretata automaticamente "
                        "come contatore, tasso o media."
                    )
                }

    # =====================================================
    # 2. CONTATORI CANDIDATI RUNTIME
    # =====================================================

    if sorgente == "runtime":

        contatori = {
            "java_lang_GarbageCollector_CollectionCount.Copy":
                "frequenza_gc",

            "java_lang_GarbageCollector_CollectionTime.Copy":
                "tempo_gc"
        }

        if kpi_name in contatori:

            return {
                "sorgente": "runtime",
                "kpi": kpi_name,
                "famiglia": contatori[kpi_name],
                "tipo": "contatore_cumulativo_candidato",
                "trasformazione": "incremento_per_minuto",
                "direzione": None,
                "semantica_verificata": False,
                "nota": (
                    "Controllare incrementi negativi, "
                    "reset e unita di misura. "
                    "I valori possono essere aggregati."
                )
            }

        # =================================================
        # 3. GAUGE CANDIDATE RUNTIME
        # =================================================

        gauge = {
            "java_lang_Memory_HeapMemoryUsage_used":
                ("memoria_heap", "alto"),

            "jvm_threads_current":
                ("thread", None)
        }

        if kpi_name in gauge:

            famiglia, direzione = gauge[kpi_name]

            return {
                "sorgente": "runtime",
                "kpi": kpi_name,
                "famiglia": famiglia,
                "tipo": "gauge_candidata",
                "trasformazione": "livello_osservato",
                "direzione": direzione,
                "semantica_verificata": False,
                "nota": (
                    "Interpretare i valori nel contesto "
                    "del runtime e della copertura."
                )
            }

    return None


def calcola_incrementi_runtime(
    df,
    componente: str,
    kpi_name: str,
    start_unix: int,
    end_unix: int
):
    """
    Calcola incrementi normalizzati a 60 secondi
    per un contatore candidato Runtime.

    - Filtra la finestra temporale.
    - Ordina i campioni.
    - Gestisce timestamp duplicati.
    - Riconosce incrementi negativi sospetti.
    - Non interpreta incrementi negativi come
      un'attivita normale del contatore.
    - Non stabilisce se il GC sia anomalo.

    L'unita dell'incremento rimane quella originale
    del KPI per minuto, ancora da verificare.
    """

    import numpy as np
    import pandas as pd

    # =====================================================
    # 1. VALIDAZIONE
    # =====================================================

    if start_unix >= end_unix:
        raise ValueError("Finestra temporale non valida.")

    descrizione = descrivi_kpi_mesh_runtime(
        "runtime",
        kpi_name
    )

    if (
        descrizione is None
        or descrizione["trasformazione"]
        != "incremento_per_minuto"
    ):
        raise ValueError(
            "Il KPI non è un contatore Runtime "
            "candidato supportato."
        )

    colonne = {
        "timestamp",
        "cmdb_id",
        "kpi_name",
        "value"
    }

    if not colonne.issubset(df.columns):
        raise ValueError("Colonne telemetria mancanti.")

    # =====================================================
    # 2. FILTRO DELLA SERIE
    # =====================================================

    serie = df.loc[
        (df["cmdb_id"] == componente)
        & (df["kpi_name"] == kpi_name)
    ].copy()

    serie["timestamp"] = pd.to_numeric(
        serie["timestamp"],
        errors="coerce"
    )

    serie["value"] = pd.to_numeric(
        serie["value"],
        errors="coerce"
    )

    serie = serie.replace(
        [np.inf, -np.inf],
        np.nan
    )

    serie = serie.dropna(
        subset=["timestamp", "value"]
    )

    serie = serie.loc[
        serie["timestamp"].ge(start_unix)
        & serie["timestamp"].lt(end_unix)
    ]

    # =====================================================
    # 3. ORDINAMENTO E DEDUPLICAZIONE
    # =====================================================

    serie = (
        serie.groupby(
            "timestamp",
            as_index=False
        )["value"]
        .median()
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    colonne_output = [
        "timestamp",
        "value",
        "intervallo_secondi",
        "incremento",
        "incremento_per_minuto",
        "reset_sospetto"
    ]

    if len(serie) < 2:
        return pd.DataFrame(
            columns=colonne_output
        )

    # =====================================================
    # 4. DIFFERENZE TEMPORALI
    # =====================================================

    serie["intervallo_secondi"] = (
        serie["timestamp"].diff()
    )

    serie["incremento"] = (
        serie["value"].diff()
    )

    # La prima osservazione non ha un campione
    # precedente nella finestra.
    serie = serie.iloc[1:].copy()

    serie = serie.loc[
        serie["intervallo_secondi"] > 0
    ].copy()

    # Un decremento può indicare reset,
    # discontinuità o semantica diversa.
    serie["reset_sospetto"] = (
        serie["incremento"] < 0
    )

    serie["incremento_per_minuto"] = (
        serie["incremento"]
        / serie["intervallo_secondi"]
        * 60.0
    )

    # Non utilizziamo gli incrementi negativi
    # come normali valori del tasso.
    serie.loc[
        serie["reset_sospetto"],
        "incremento_per_minuto"
    ] = np.nan

    return serie[colonne_output].reset_index(
        drop=True
    )