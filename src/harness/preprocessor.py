"""Statistiche descrittive delle metriche OpenRCA in una finestra temporale.

Per ogni coppia componente/KPI nella finestra [start, end) calcola media, mediana, minimo, massimo,
deviazione standard, primo/ultimo valore e l'istante del massimo. Sono i numeri che l'harness mette
a disposizione dell'agente come evidenza di base, senza interpretarli.

Usato da `harness/evidence_builder.py` (metriche di container e di nodi). Nessun LLM, nessuna diagnosi.
"""

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

    Argomenti:
      df          tabella con le colonne timestamp, cmdb_id, kpi_name, value.
      start_unix  inizio della finestra (compreso), in secondi unix.
      end_unix    fine della finestra (escluso); deve essere maggiore di start_unix.
      sorgente    "container" oppure "node": viene solo riportata in ogni risultato.

    Restituisce una lista di dizionari, uno per coppia componente/KPI (lista vuota se nella finestra
    non c'è nessun campione valido). Il risultato è ordinato per componente e KPI.
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

    # Selezioniamo i campioni validi nella finestra [inizio, fine): dentro l'intervallo, senza valori
    # mancanti o infiniti e con componente e KPI noti.
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

    # Ordiniamo i campioni per componente, KPI e tempo. L'ordinamento "stable" mantiene l'ordine originale
    # dei campioni con lo stesso istante, così il risultato è sempre lo stesso a parità di dati.
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

        # Individuiamo quando compare il valore massimo (indice di riga di `dati`, usato più sotto
        # per leggerne il timestamp; se il massimo è ripetuto vale la prima occorrenza).
        indice_massimo = valori.idxmax()

        # Calcoliamo statistiche descrittive. La deviazione standard usa ddof=0 (divisione per N,
        # cioè sull'intera serie osservata e non come stima su un campione).
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