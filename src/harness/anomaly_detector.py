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

def rileva_anomalie_direzionali(
    df,
    sorgente: str,
    start_unix: int,
    end_unix: int,
    soglia: float = 3.5,
    min_consecutivi: int = 3,
    min_campioni: int = 10,
    max_gap_secondi: int = 90
) -> list[dict]:
    """
    Rileva variazioni persistenti nella direzione
    indicata dal catalogo semantico.

    Usa mediana e MAD per costruire uno score robusto.

    Gestisce:
        - direzione "alto"
        - direzione "basso"

    Analizza soltanto i KPI ammessi da signal_catalog.py.

    Non utilizza ground truth.
    Non stabilisce quale sia la root cause.
    """

    import pandas as pd
    import numpy as np

    from harness.signal_catalog import descrivi_kpi

    # =====================================================
    # 1. VALIDAZIONE DEI PARAMETRI
    # =====================================================

    if start_unix >= end_unix:
        raise ValueError("Intervallo temporale non valido.")

    if sorgente not in ("node_metrics", "container_metrics"):
        raise ValueError("Sorgente non supportata.")

    if soglia <= 0:
        raise ValueError("La soglia deve essere positiva.")

    if min_consecutivi < 1 or min_campioni < 3:
        raise ValueError("Parametri di campionamento non validi.")

    if max_gap_secondi <= 0:
        raise ValueError("Distanza temporale non valida.")

    colonne = {
        "timestamp",
        "cmdb_id",
        "kpi_name",
        "value"
    }

    if not colonne.issubset(df.columns):
        raise ValueError(
            f"Colonne mancanti: {colonne - set(df.columns)}"
        )

    # =====================================================
    # 2. PREPARAZIONE DEI DATI
    # =====================================================

    dati = df.copy()

    dati["timestamp"] = pd.to_numeric(
        dati["timestamp"],
        errors="coerce"
    )

    dati["value"] = pd.to_numeric(
        dati["value"],
        errors="coerce"
    )

    dati = dati.loc[
        dati["timestamp"].ge(start_unix)
        & dati["timestamp"].lt(end_unix)
    ]

    dati = dati.dropna(
        subset=["timestamp", "value", "cmdb_id", "kpi_name"]
    )

    dati = dati.loc[
        np.isfinite(dati["value"])
    ]

    anomalie = []

    # =====================================================
    # 3. ANALISI DELLE SINGOLE SERIE
    # =====================================================

    for (componente, kpi), gruppo in dati.groupby(
        ["cmdb_id", "kpi_name"]
    ):

        descrizione = descrivi_kpi(
            sorgente,
            str(kpi)
        )

        # Escludiamo KPI con semantica non verificata.
        if descrizione["tipo"] != "gauge_candidato":
            continue

        direzione = descrizione["direzione"]

        if direzione not in ("alto", "basso"):
            continue

        # Più campioni con lo stesso timestamp:
        # li consolidiamo usando la mediana.
        serie = (
            gruppo.groupby("timestamp", as_index=False)
            ["value"]
            .median()
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        if len(serie) < min_campioni:
            continue

        valori = serie["value"].to_numpy(
            dtype=float
        )

        if np.unique(valori).size < 3:
            continue

        # =================================================
        # 4. MEDIANA E MEDIAN ABSOLUTE DEVIATION
        # =================================================

        mediana = float(np.median(valori))

        mad = float(
            np.median(
                np.abs(valori - mediana)
            )
        )

        # Evitiamo divisioni per zero e amplificazioni
        # arbitrarie quando la scala robusta è nulla.
        if mad <= 0:
            continue

        scala_robusta = 1.4826 * mad

        # =================================================
        # 5. SCORE DIREZIONALE
        # =================================================

        if direzione == "alto":

            scores = (
                valori - mediana
            ) / scala_robusta

        else:

            scores = (
                mediana - valori
            ) / scala_robusta

        sospetti = scores >= soglia

        # =================================================
        # 6. RICERCA DI EPISODI PERSISTENTI
        # =================================================

        timestamps = serie["timestamp"].to_numpy()

        episodio = []

        def registra_episodio(indici):
            """
            Registra soltanto episodi sufficientemente
            lunghi in numero di campioni consecutivi.
            """

            if len(indici) < min_consecutivi:
                return

            # Individuiamo il punto più anomalo
            # all'interno dell'episodio.
            picco = max(
                indici,
                key=lambda i: float(scores[i])
            )

            anomalie.append({
                "sorgente": sorgente,
                "componente": str(componente),
                "kpi": str(kpi),
                "famiglia": descrizione["famiglia"],
                "direzione": direzione,
                "inizio_unix": int(timestamps[indici[0]]),
                "fine_unix": int(timestamps[indici[-1]]),
                "timestamp_picco_unix": int(
                    timestamps[picco]
                ),
                "campioni_consecutivi": len(indici),
                "valore_picco": float(valori[picco]),
                "mediana_serie": mediana,
                "score_picco": round(
                    float(scores[picco]), 3
                ),
                "metodo": "directional_median_mad_v1"
            })

        # Percorriamo la serie in ordine temporale.
        for i, sospetto in enumerate(sospetti):

            if not sospetto:

                registra_episodio(episodio)
                episodio = []
                continue

            # Un salto temporale eccessivo interrompe
            # la consecutività dell'episodio.
            if episodio:

                precedente = episodio[-1]

                distanza = (
                    timestamps[i]
                    - timestamps[precedente]
                )

                if distanza > max_gap_secondi:

                    registra_episodio(episodio)
                    episodio = []

            episodio.append(i)

        # Registriamo l'eventuale ultimo episodio.
        registra_episodio(episodio)

    # =====================================================
    # 7. ORDINAMENTO DEI RISULTATI
    # =====================================================

    anomalie.sort(
        key=lambda evento: (
            evento["inizio_unix"],
            evento["componente"],
            evento["kpi"]
        )
    )

    return anomalie