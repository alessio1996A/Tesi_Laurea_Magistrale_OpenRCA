"""Rilevatori deterministici di anomalie sulle serie temporali delle metriche (mediana e MAD).

Contiene due rilevatori, entrambi basati su statistiche robuste (mediana e MAD, cioè la mediana delle
distanze dalla mediana), che resistono ai picchi isolati:
- `rileva_anomalie`: cerca aumenti persistenti di un KPI rispetto alla mediana della sua stessa serie;
- `rileva_anomalie_direzionali`: usa il catalogo dei segnali (`signal_catalog`) per sapere se per un KPI
  è anomalo un aumento o una diminuzione, e raggruppa i campioni sospetti in "episodi".

Entrambi lavorano solo sui dati della finestra indicata, senza ground truth e senza LLM, e non stabiliscono
la causa del guasto. Usati da `harness/evidence_builder.py`.
"""

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

    Argomenti:
      df               tabella con le colonne timestamp, cmdb_id, kpi_name, value.
      start_unix, end_unix  finestra [start, end) da analizzare, in secondi unix.
      soglia           di quante "dispersioni robuste" il valore deve superare la mediana per essere sospetto.
      min_consecutivi  quanti campioni consecutivi sospetti servono per registrare un'anomalia (almeno 2).

    Restituisce una lista con al più una anomalia per coppia componente/KPI (la prima trovata), con
    `timestamp_inizio` dell'aumento, mediana, MAD, soglia superata e valore massimo della serie.
    Le serie con meno di 10 campioni nella finestra non vengono valutate.
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

    # Conversione numerica tollerante: i valori non convertibili diventano NaN e vengono scartati sotto.
    dati["timestamp"] = pd.to_numeric(
        dati["timestamp"], errors="coerce"
    )

    dati["value"] = pd.to_numeric(
        dati["value"], errors="coerce"
    )

    # Manteniamo soltanto i campioni validi nella finestra [start, end): numeri finiti e nomi presenti.
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

        # Ordine cronologico ("stable" mantiene l'ordine originale dei campioni con lo stesso istante).
        gruppo = gruppo.sort_values(
            "timestamp", kind="stable"
        )

        # Evitiamo decisioni su serie troppo brevi.
        if len(gruppo) < 10:
            continue

        valori = gruppo["value"].to_numpy(dtype=float)

        mediana = float(np.median(valori))

        # MAD (deviazione assoluta mediana): mediana delle distanze dei valori dalla mediana.
        mad = float(np.median(np.abs(valori - mediana)))

        # Stima robusta della dispersione: 1.4826 * MAD equivale a una deviazione standard per dati
        # normali. Il minimo relativo (5% della mediana) e il minimo assoluto evitano soglie nulle
        # quando la serie è quasi costante.
        dispersione = max(
            1.4826 * mad,
            0.05 * abs(mediana),
            1e-9
        )

        # Limite oltre il quale un valore è sospetto: mediana + soglia volte la dispersione robusta.
        limite = mediana + soglia * dispersione

        # Cerchiamo aumenti superiori alla soglia.
        supera = valori > limite

        # `consecutivi` conta i campioni sospetti di fila; `inizio_anomalia` è la posizione del primo.
        consecutivi = 0
        inizio_anomalia = None

        for i, anomalo in enumerate(supera):

            if anomalo:
                consecutivi += 1

                if consecutivi == 1:
                    inizio_anomalia = i

            else:
                # Un campione normale interrompe la sequenza.
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

    Argomenti:
      df               tabella con le colonne timestamp, cmdb_id, kpi_name, value.
      sorgente         "node_metrics" oppure "container_metrics": serve a consultare il catalogo dei segnali.
      start_unix, end_unix  finestra [start, end) da analizzare, in secondi unix.
      soglia           score robusto minimo (distanza dalla mediana in unità di 1.4826 * MAD) per un campione sospetto.
      min_consecutivi  campioni sospetti consecutivi necessari per registrare un episodio.
      min_campioni     campioni minimi per valutare una serie.
      max_gap_secondi  salto temporale massimo tra due campioni sospetti dello stesso episodio.

    Restituisce gli episodi trovati, ordinati per istante d'inizio, componente e KPI. Ogni episodio riporta
    inizio, fine, istante e valore del picco, mediana della serie e score del picco.
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