"""Controllo di qualità delle serie temporali (metriche) di OpenRCA.

Per ogni coppia componente/KPI dice se la serie ha abbastanza campioni, se è costante o se varia,
e quante volte il valore scende da un campione al successivo. È un controllo descrittivo: serve
all'harness per sapere quanto fidarsi di una serie, non per decidere se c'è un guasto.

Usato da `harness/evidence_builder.py` (CPU dei nodi e dei container). Nessun LLM, nessuna ground truth.
"""

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

    Argomenti:
      df            tabella con le colonne timestamp, cmdb_id, kpi_name, value.
      min_campioni  numero minimo di campioni validi per considerare utilizzabile una serie (almeno 2).

    Restituisce una lista con un dizionario per ogni coppia componente/KPI: campioni validi, valori
    distinti, numero di diminuzioni e `stato` ("campioni_insufficienti", "serie_costante" oppure
    "serie_variabile"). `semantica_verificata` è sempre False: il significato fisico del KPI non viene
    verificato qui.
    """

    # Le quattro colonne obbligatorie: istante (unix), componente, nome del KPI, valore.
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

    # Escludiamo soltanto i valori non validi (mancanti o non convertibili in numero).
    dati = dati.dropna(
        subset=["timestamp", "cmdb_id", "kpi_name", "value"]
    )

    # Scartiamo anche gli infiniti, che dropna non riconosce come mancanti.
    dati = dati[
        np.isfinite(dati["timestamp"])
        & np.isfinite(dati["value"])
    ]

    risultati = []

    # Controlliamo ciascuna coppia componente/KPI.
    for (componente, kpi), gruppo in dati.groupby(
        ["cmdb_id", "kpi_name"]
    ):

        # Ordine cronologico: le differenze tra campioni hanno senso solo così.
        gruppo = gruppo.sort_values("timestamp")

        valori = gruppo["value"]
        # Differenza tra ogni campione e il precedente (il primo non ne ha e viene scartato).
        differenze = valori.diff().dropna()

        campioni = len(gruppo)
        distinti = valori.nunique()

        # Le diminuzioni non dimostrano da sole un reset. La tolleranza -1e-9 evita di contare come
        # "diminuzione" le piccole imprecisioni dei numeri decimali.
        diminuzioni = int((differenze < -1e-9).sum())

        # Stato della serie, in ordine di priorità: pochi campioni, poi costante, altrimenti variabile.
        if campioni < min_campioni:
            stato = "campioni_insufficienti"

        elif distinti == 1:
            stato = "serie_costante"

        else:
            stato = "serie_variabile"

        # Una riga di risultato per coppia componente/KPI.
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