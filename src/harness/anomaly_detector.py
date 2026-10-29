import numpy as np
import pandas as pd


def rileva_anomalie(
    df: pd.DataFrame,
    start_unix: int,
    end_unix: int,
    soglia: float = 3.5,
    min_consecutivi: int = 3
) -> list[dict]:
    """
    Individua aumenti anomali e persistenti nelle serie temporali.

    Utilizza mediana e MAD come statistiche robuste.
    Non identifica automaticamente la causa del guasto.

    Da utilizzare inizialmente su KPI istantanei, non cumulativi.
    """

    if start_unix >= end_unix:
        raise ValueError("Intervallo temporale non valido.")

    if soglia <= 0 or min_consecutivi < 2:
        raise ValueError("Parametri del rilevatore non validi.")

    colonne = ["timestamp", "cmdb_id", "kpi_name", "value"]

    if not set(colonne).issubset(df.columns):
        raise ValueError("Colonne mancanti.")

    # Copiamo i dati senza modificare il DataFrame originale.
    dati = df[colonne].copy()

    dati["timestamp"] = pd.to_numeric(
        dati["timestamp"], errors="coerce"
    )

    dati["value"] = pd.to_numeric(
        dati["value"], errors="coerce"
    )

    # Manteniamo soltanto i campioni validi nella finestra.
    mask = (
        dati["timestamp"].ge(start_unix)
        & dati["timestamp"].lt(end_unix)
        & np.isfinite(dati["timestamp"])
        & np.isfinite(dati["value"])
        & dati["cmdb_id"].notna()
        & dati["kpi_name"].notna()
    )

    dati = dati.loc[mask].copy()

    anomalie = []

    # Analizziamo separatamente ogni componente e KPI.
    for (componente, kpi), gruppo in dati.groupby(
        ["cmdb_id", "kpi_name"]
    ):

        gruppo = gruppo.sort_values(
            "timestamp", kind="stable"
        )

        # Evitiamo decisioni su serie troppo brevi.
        if len(gruppo) < 10:
            continue

        valori = gruppo["value"].to_numpy(dtype=float)

        mediana = float(np.median(valori))

        # Median Absolute Deviation.
        mad = float(np.median(np.abs(valori - mediana)))

        # Stima robusta della dispersione.
        # Il minimo relativo evita soglie nulle.
        dispersione = max(
            1.4826 * mad,
            0.05 * abs(mediana),
            1e-9
        )

        limite = mediana + soglia * dispersione

        # Cerchiamo aumenti superiori alla soglia.
        supera = valori > limite

        consecutivi = 0
        inizio_anomalia = None

        for i, anomalo in enumerate(supera):

            if anomalo:
                consecutivi += 1

                if consecutivi == 1:
                    inizio_anomalia = i

            else:
                consecutivi = 0
                inizio_anomalia = None

            # Richiediamo almeno N campioni consecutivi.
            if consecutivi == min_consecutivi:

                anomalie.append({
                    "componente": str(componente),
                    "kpi": str(kpi),
                    "tipo": "aumento_persistente",
                    "timestamp_inizio": int(
                        gruppo["timestamp"].iloc[inizio_anomalia]
                    ),
                    "mediana": mediana,
                    "mad": mad,
                    "soglia_superamento": float(limite),
                    "valore_massimo": float(np.max(valori)),
                    "campioni": len(valori)
                })

                # Registriamo una segnalazione per serie.
                break

    return anomalie