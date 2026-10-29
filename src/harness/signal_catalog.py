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