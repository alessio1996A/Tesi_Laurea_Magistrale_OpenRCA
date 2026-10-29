import pandas as pd
import numpy as np


def preprocessa_metriche(
    df: pd.DataFrame,
    start_unix: int,
    end_unix: int,
    sorgente: str
) -> list[dict]:
    """
    Preprocessing deterministico delle metriche OpenRCA.

    Riceve le metriche di container o nodi e restituisce
    statistiche per ogni coppia componente/KPI.

    Non utilizza LLM e non formula diagnosi.
    """

    # Controlliamo la sorgente e la finestra richiesta.
    if sorgente not in ("container", "node"):
        raise ValueError("Sorgente non supportata.")

    if start_unix >= end_unix:
        raise ValueError("Intervallo temporale non valido.")

    # Verifichiamo la presenza delle colonne necessarie.
    colonne = {"timestamp", "cmdb_id", "kpi_name", "value"}

    if not colonne.issubset(df.columns):
        raise ValueError("Colonne delle metriche mancanti.")

    # Lavoriamo su una copia per non modificare il DataFrame originale.
    dati = df[list(colonne)].copy()

    # Convertiamo timestamp e valori in numeri.
    dati["timestamp"] = pd.to_numeric(
        dati["timestamp"], errors="coerce"
    )

    dati["value"] = pd.to_numeric(
        dati["value"], errors="coerce"
    )

    # Selezioniamo i campioni validi nella finestra [inizio, fine).
    mask = (
        dati["timestamp"].ge(start_unix)
        & dati["timestamp"].lt(end_unix)
        & dati["timestamp"].notna()
        & dati["value"].notna()
        & np.isfinite(dati["value"])
        & dati["cmdb_id"].notna()
        & dati["kpi_name"].notna()
    )

    dati = dati.loc[mask].copy()

    if dati.empty:
        return []

    # Ordiniamo i campioni cronologicamente.
    dati = dati.sort_values(
        ["cmdb_id", "kpi_name", "timestamp"],
        kind="stable"
    )

    evidenze = []

    # Analizziamo separatamente ogni componente e KPI.
    for (componente, kpi), gruppo in dati.groupby(
        ["cmdb_id", "kpi_name"]
    ):

        valori = gruppo["value"]

        # Individuiamo quando compare il valore massimo.
        indice_massimo = valori.idxmax()

        # Calcoliamo statistiche descrittive.
        evidenza = {
            "sorgente": sorgente,
            "componente": str(componente),
            "kpi": str(kpi),
            "campioni": int(len(gruppo)),
            "media": float(valori.mean()),
            "mediana": float(valori.median()),
            "minimo": float(valori.min()),
            "massimo": float(valori.max()),
            "deviazione_standard": float(valori.std(ddof=0)),
            "primo_valore": float(valori.iloc[0]),
            "ultimo_valore": float(valori.iloc[-1]),
            "primo_timestamp": int(gruppo["timestamp"].iloc[0]),
            "ultimo_timestamp": int(gruppo["timestamp"].iloc[-1]),
            "timestamp_massimo": int(
                dati.loc[indice_massimo, "timestamp"]
            )
        }

        evidenze.append(evidenza)

    return evidenze