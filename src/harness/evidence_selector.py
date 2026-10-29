import re
from copy import deepcopy
from collections import Counter

import numpy as np
import pandas as pd


def annota_qualita_evidenze(
    report_v2: dict,
    df_nodi: pd.DataFrame,
    df_container: pd.DataFrame,
    soglia_salto_capacita_pct: float = 10.0,
    tolleranza_repliche_secondi: int = 60
) -> dict:
    """
    Analizza la qualità delle evidenze A1-v2.

    Identifica:
      - variazioni relative dei KPI;
      - possibili discontinuità della capacità disco;
      - anomalie sincronizzate tra repliche;
      - episodi vicini al bordo della finestra.

    NON elimina nessun gruppo.
    NON determina la root cause.
    NON utilizza ground truth.
    """

    if report_v2.get("versione") != "A1-v2":
        raise ValueError("È richiesto un report A1-v2.")

    if soglia_salto_capacita_pct <= 0:
        raise ValueError("Soglia capacità non valida.")

    if tolleranza_repliche_secondi < 0:
        raise ValueError("Tolleranza temporale non valida.")

    gruppi = deepcopy(
        report_v2["estensione_multi_risorsa"]["gruppi"]
    )

    sorgenti = {}

    # Normalizziamo le due sorgenti una sola volta.
    for nome, originale in (
        ("node_metrics", df_nodi),
        ("container_metrics", df_container)
    ):

        df = originale.copy()

        df["timestamp"] = pd.to_numeric(
            df["timestamp"], errors="coerce"
        )

        df["value"] = pd.to_numeric(
            df["value"], errors="coerce"
        )

        df = df.dropna(
            subset=["timestamp", "value"]
        )

        sorgenti[nome] = df.loc[
            np.isfinite(df["value"])
        ]

    # =====================================================
    # 1. RICONOSCIMENTO DELLE REPLICHE
    # =====================================================

    def servizio_replica(componente: str):
        """
        Esempio:
          node-6.paymentservice-2

        Restituisce:
          ("paymentservice", "2")
        """

        match = re.fullmatch(
            r"node-\d+\.(.+)-(\d+)",
            componente
        )

        if match is None:
            return None

        return match.group(1), match.group(2)

    # =====================================================
    # 2. ANALISI DI OGNI GRUPPO
    # =====================================================

    for gruppo in gruppi:

        sorgente = gruppo["sorgente"]
        componente = gruppo["componente"]
        direzione = gruppo["direzione"]

        df = sorgenti[sorgente]

        variazioni = {}

        for kpi in gruppo["kpi"]:

            serie = df.loc[
                (df["cmdb_id"] == componente)
                & (df["kpi_name"] == kpi)
            ]

            valori = serie["value"]

            if valori.empty:
                continue

            mediana = float(valori.median())

            episodio = serie.loc[
                serie["timestamp"].between(
                    gruppo["inizio_osservato_unix"],
                    gruppo["fine_osservata_unix"]
                )
            ]

            if episodio.empty:
                continue

            if direzione == "alto":
                estremo = float(
                    episodio["value"].max()
                )
            else:
                estremo = float(
                    episodio["value"].min()
                )

            # Vicino a zero, una percentuale relativa
            # non è una misura affidabile.
            if abs(mediana) < 1e-9:
                variazione_pct = None
            else:
                variazione_pct = (
                    abs(estremo - mediana)
                    / abs(mediana)
                    * 100
                )

            variazioni[kpi] = (
                round(variazione_pct, 4)
                if variazione_pct is not None
                else None
            )

        gruppo["variazioni_percentuali"] = variazioni

        percentuali_valide = [
            valore
            for valore in variazioni.values()
            if valore is not None
        ]

        gruppo["variazione_massima_pct"] = (
            max(percentuali_valide)
            if percentuali_valide
            else None
        )

        # È soltanto un indicatore descrittivo:
        # non eliminiamo automaticamente il gruppo.
        gruppo["variazioni_tutte_inferiori_1_pct"] = (
            bool(percentuali_valide)
            and len(percentuali_valide) == len(variazioni)
            and all(v < 1.0 for v in percentuali_valide)
        )

        # =================================================
        # 3. CONTROLLO DELLA CAPACITÀ DISCO
        # =================================================

        gruppo["salto_capacita_iniziale_pct"] = None
        gruppo["capacita_disco_da_verificare"] = False

        if (
            sorgente == "node_metrics"
            and gruppo["famiglia"] == "disco"
            and gruppo["vicino_inizio_finestra"]
        ):

            serie_totale = sorgenti["node_metrics"].loc[
                (
                    sorgenti["node_metrics"]["cmdb_id"]
                    == componente
                )
                & (
                    sorgenti["node_metrics"]["kpi_name"]
                    == "system.disk.total"
                )
            ]

            serie_totale = (
                serie_totale
                .groupby("timestamp")["value"]
                .median()
                .sort_index()
            )

            if len(serie_totale) >= 2:

                primo_timestamp = int(
                    serie_totale.index[0]
                )

                # Controlliamo la discontinuità soltanto
                # quando la misura parte dal bordo
                # della finestra del report.
                if primo_timestamp == int(
                    report_v2["finestra"]["start_unix"]
                ):

                    primo = float(
                        serie_totale.iloc[0]
                    )

                    secondo = float(
                        serie_totale.iloc[1]
                    )

                    if abs(secondo) > 1e-9:

                        salto_pct = (
                            abs(primo - secondo)
                            / abs(secondo)
                            * 100
                        )

                        gruppo[
                            "salto_capacita_iniziale_pct"
                        ] = round(salto_pct, 3)

                        gruppo[
                            "capacita_disco_da_verificare"
                        ] = (
                            salto_pct
                            >= soglia_salto_capacita_pct
                        )

        # =================================================
        # 4. CORRELAZIONE TRA REPLICHE
        # =================================================

        replica = servizio_replica(componente)

        repliche_correlate = set()

        if replica is not None:

            servizio, _ = replica

            for altro in gruppi:

                altra_replica = servizio_replica(
                    altro["componente"]
                )

                if altra_replica is None:
                    continue

                if altra_replica[0] != servizio:
                    continue

                if altro["sorgente"] != sorgente:
                    continue

                if altro["famiglia"] != gruppo["famiglia"]:
                    continue

                if altro["direzione"] != direzione:
                    continue

                distanza = abs(
                    int(altro["inizio_osservato_unix"])
                    - int(gruppo["inizio_osservato_unix"])
                )

                if distanza <= tolleranza_repliche_secondi:
                    repliche_correlate.add(
                        altro["componente"]
                    )

        gruppo["repliche_sincronizzate"] = sorted(
            repliche_correlate
        )

        gruppo["numero_repliche_sincronizzate"] = len(
            repliche_correlate
        )

        # =================================================
        # 5. PRIORITÀ DI INDAGINE
        # =================================================

        # Queste etichette sono provvisorie:
        # non equivalgono a diagnosi o probabilità.

        if gruppo["capacita_disco_da_verificare"]:

            priorita = "verificare_coerenza_telemetria"

        elif (
            gruppo["numero_repliche_sincronizzate"] >= 2
        ):

            priorita = "correlazione_multi_replica"

        elif gruppo["variazioni_tutte_inferiori_1_pct"]:

            priorita = "variazione_relativa_modesta"

        else:

            priorita = "da_approfondire"

        gruppo["priorita_indagine"] = priorita

    # =====================================================
    # 6. REPORT RIASSUNTIVO
    # =====================================================

    distribuzione = Counter(
        g["priorita_indagine"]
        for g in gruppi
    )

    return {
        "versione": "quality_annotations_v1",
        "gruppi_totali": len(gruppi),
        "distribuzione_priorita": dict(
            sorted(distribuzione.items())
        ),
        "gruppi": gruppi,
        "nota": (
            "La priorità indica soltanto quali evidenze "
            "approfondire. Non identifica la root cause."
        )
    }