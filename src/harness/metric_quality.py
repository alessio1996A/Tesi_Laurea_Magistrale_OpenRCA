import numpy as np
import pandas as pd


def valuta_qualita_metriche(
    df: pd.DataFrame,
    min_campioni: int = 10
) -> list[dict]:
    """
    Controlla la qualità delle serie temporali OpenRCA.

    Non effettua anomaly detection.
    Non deduce automaticamente la semantica dei KPI.
    """

    colonne = {"timestamp", "cmdb_id", "kpi_name", "value"}

    if not colonne.issubset(df.columns):
        raise ValueError("Colonne necessarie mancanti.")

    if min_campioni < 2:
        raise ValueError("min_campioni deve essere almeno 2.")

    dati = df[
        ["timestamp", "cmdb_id", "kpi_name", "value"]
    ].copy()

    # Convertiamo timestamp e valori in numeri.
    dati["timestamp"] = pd.to_numeric(
        dati["timestamp"], errors="coerce"
    )

    dati["value"] = pd.to_numeric(
        dati["value"], errors="coerce"
    )

    # Escludiamo soltanto i valori non validi.
    dati = dati.dropna(
        subset=["timestamp", "cmdb_id", "kpi_name", "value"]
    )

    dati = dati[
        np.isfinite(dati["timestamp"])
        & np.isfinite(dati["value"])
    ]

    risultati = []

    # Controlliamo ciascuna coppia componente/KPI.
    for (componente, kpi), gruppo in dati.groupby(
        ["cmdb_id", "kpi_name"]
    ):

        gruppo = gruppo.sort_values("timestamp")

        valori = gruppo["value"]
        differenze = valori.diff().dropna()

        campioni = len(gruppo)
        distinti = valori.nunique()

        # Le diminuzioni non dimostrano da sole un reset.
        diminuzioni = int((differenze < -1e-9).sum())

        if campioni < min_campioni:
            stato = "campioni_insufficienti"

        elif distinti == 1:
            stato = "serie_costante"

        else:
            stato = "serie_variabile"

        risultati.append({
            "componente": str(componente),
            "kpi": str(kpi),
            "campioni": campioni,
            "valori_distinti": int(distinti),
            "diminuzioni": diminuzioni,
            "stato": stato,
            "semantica_verificata": False
        })

    return risultati