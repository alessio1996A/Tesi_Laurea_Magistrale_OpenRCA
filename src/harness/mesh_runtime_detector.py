"""
Rilevatore preliminare di evidenze Mesh/Runtime per A1.

Obiettivo:
- Identificare aumenti persistenti nei segnali selezionati.
- Conservare la provenienza temporale e il componente.
- Evitare diagnosi causali automatiche.
- Limitare il numero di evidenze da inviare all'LLM.

Non usa ground truth e non chiama Gemini.
"""

import numpy as np
import pandas as pd

from harness.signal_catalog import (
    calcola_incrementi_runtime
)


# ============================================================
# 1. CONFIGURAZIONE
# ============================================================

KPI_RUNTIME = (
    "java_lang_Memory_HeapMemoryUsage_used",
    "java_lang_GarbageCollector_CollectionCount.Copy",
    "java_lang_GarbageCollector_CollectionTime.Copy",
)

PREFISSO_DURATA = (
    "istio_request_duration_milliseconds."
)

PREFISSO_RICHIESTE = "istio_requests."


# ============================================================
# 2. PREPARAZIONE DEI DATI
# ============================================================

def _prepara(df, start_unix, end_unix):
    """
    Filtra e normalizza i campioni, senza
    modificare il DataFrame originale.
    """

    colonne = {
        "timestamp", "cmdb_id",
        "kpi_name", "value"
    }

    if not colonne.issubset(df.columns):
        raise ValueError("Colonne telemetria mancanti.")

    dati = df[
        ["timestamp", "cmdb_id", "kpi_name", "value"]
    ].copy()

    dati["timestamp"] = pd.to_numeric(
        dati["timestamp"], errors="coerce"
    )

    dati["value"] = pd.to_numeric(
        dati["value"], errors="coerce"
    )

    dati["value"] = dati["value"].replace(
        [np.inf, -np.inf], np.nan
    )

    dati = dati.dropna(
        subset=["timestamp", "value",
                "cmdb_id", "kpi_name"]
    )

    return dati.loc[
        (dati["timestamp"] >= start_unix)
        & (dati["timestamp"] < end_unix)
    ].copy()


# ============================================================
# 3. RILEVAMENTO DI AUMENTI PERSISTENTI
# ============================================================

def _rileva_aumento(
    serie,
    min_campioni=10,
    consecutivi=3,
    max_gap_secondi=90,
    scostamento_minimo=0.30,
):
    """
    Identifica il più intenso episodio persistente
    di aumento all'interno di una singola serie.

    La soglia usa:
      mediana + max(4 * 1.4826 * MAD,
                    30% della mediana)

    Restituisce None se non trova episodi idonei.
    """

    serie = (
        serie.groupby("timestamp", as_index=False)["value"]
        .median()
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    if len(serie) < min_campioni:
        return None

    valori = serie["value"].to_numpy(dtype=float)
    tempi = serie["timestamp"].to_numpy(dtype=float)

    mediana = float(np.median(valori))

    mad = float(
        np.median(np.abs(valori - mediana))
    )

    soglia = mediana + max(
        4.0 * 1.4826 * mad,
        scostamento_minimo * abs(mediana),
        1e-9
    )

    sopra_soglia = valori > soglia

    episodi = []
    inizio = None
    precedente = None

    # Individuiamo sequenze consecutive di campioni
    # sopra soglia, senza attraversare buchi temporali.
    for i, anomalo in enumerate(sopra_soglia):

        consecutivo = (
            precedente is not None
            and tempi[i] - tempi[precedente]
            <= max_gap_secondi
        )

        if anomalo:

            if inizio is None or not consecutivo:

                if inizio is not None:
                    episodi.append((inizio, precedente))

                inizio = i

            precedente = i

        else:

            if inizio is not None:
                episodi.append((inizio, precedente))

            inizio = None
            precedente = None

    if inizio is not None:
        episodi.append((inizio, precedente))

    # Almeno tre campioni anomali consecutivi.
    episodi = [
        (a, b)
        for a, b in episodi
        if b - a + 1 >= consecutivi
    ]

    if not episodi:
        return None

    # Manteniamo l'episodio con il maggiore
    # superamento della soglia.
    inizio, fine = max(
        episodi,
        key=lambda ab: float(
            np.max(valori[ab[0]:ab[1] + 1]) - soglia
        )
    )

    massimo = float(
        np.max(valori[inizio:fine + 1])
    )

    return {
        "timestamp_inizio": int(tempi[inizio]),
        "timestamp_fine": int(tempi[fine]),
        "campioni_consecutivi": int(fine - inizio + 1),
        "mediana_riferimento": mediana,
        "mad": mad,
        "soglia": float(soglia),
        "valore_massimo": massimo,
        "aumento_pct": (
            round(
                (massimo - mediana)
                / abs(mediana) * 100,
                2
            )
            if abs(mediana) > 1e-9
            else None
        ),
        "intensita_relativa": float(
            (massimo - soglia)
            / max(abs(mediana), 1e-9)
        )
    }


# ============================================================
# 4. EVIDENZE MESH
# ============================================================

def _analizza_mesh(df):
    """
    Esamina soltanto le durate osservate
    delle richieste per le quali esiste anche
    una serie di richieste accoppiata.

    Non interpreta i valori come medie,
    contatori cumulativi o tassi.
    """

    segnalazioni = []
    coppie_esaminate = 0

    # Numero di serie Mesh con mediana della durata
    # nulla: non sono adatte a questo rilevatore
    # basato sullo scostamento relativo.
    baseline_zero_escluse = 0

    richieste = df.loc[
        df["kpi_name"].str.startswith(
            PREFISSO_RICHIESTE
        )
    ]

    durate = df.loc[
        df["kpi_name"].str.startswith(
            PREFISSO_DURATA
        )
    ]

    # Indicizzazione per componente e nome KPI.
    gruppi_richieste = {
        chiave: gruppo
        for chiave, gruppo in richieste.groupby(
            ["cmdb_id", "kpi_name"]
        )
    }

    for (componente, kpi), gruppo in durate.groupby(
        ["cmdb_id", "kpi_name"]
    ):

        if ".destination." not in str(componente):
            continue

        suffisso = kpi[len(PREFISSO_DURATA):]

        kpi_richieste = PREFISSO_RICHIESTE + suffisso

        gruppo_richieste = gruppi_richieste.get(
            (componente, kpi_richieste)
        )

        if gruppo_richieste is None:
            continue

        # Accoppiamo gli stessi timestamp.
        serie_durata = (
            gruppo.groupby("timestamp", as_index=False)
            ["value"].median()
            .rename(columns={"value": "durata"})
        )

        serie_richieste = (
            gruppo_richieste.groupby(
                "timestamp", as_index=False
            )["value"].median()
            .rename(columns={"value": "richieste"})
        )

        coppia = serie_durata.merge(
            serie_richieste,
            on="timestamp",
            how="inner"
        ).sort_values("timestamp")

        if len(coppia) < 10:
            continue

        coppie_esaminate += 1

        # =====================================================
        # CONTROLLO DELLA BASELINE MESH
        # =====================================================

        # Utilizziamo esattamente i campioni accoppiati
        # tra richieste e durate.
        mediana_durata = float(
            coppia["durata"].median()
        )

        # Una mediana nulla crea un rapporto relativo
        # instabile e può produrre priorità enormi
        # per variazioni assolute molto piccole.
        #
        # La serie viene esclusa soltanto dal rilevatore
        # attuale, non cancellata dalla telemetria.
        if mediana_durata <= 1e-9:
            baseline_zero_escluse += 1
            continue

        # =====================================================
        # RILEVAMENTO SULLE SERIE AMMISSIBILI
        # =====================================================

        episodio = _rileva_aumento(
            coppia[["timestamp", "durata"]]
            .rename(columns={"durata": "value"})
        )

        if episodio is None:
            continue

        durante = coppia.loc[
            coppia["timestamp"].between(
                episodio["timestamp_inizio"],
                episodio["timestamp_fine"]
            )
        ]

        segnalazioni.append({
            "sorgente": "mesh",
            "famiglia": "durata_richieste",
            "componente": str(componente),
            "kpi": str(kpi),
            "tipo": "aumento_persistente_candidato",
            "evidenza": episodio,
            "contesto_richieste": {
                "kpi": kpi_richieste,
                "mediana_finestra": float(
                    coppia["richieste"].median()
                ),
                "mediana_durante_episodio": float(
                    durante["richieste"].median()
                ),
                "interpretazione": "livello_osservato"
            },
            "causa_verificata": False
        })

    return (
    segnalazioni,
    coppie_esaminate,
    baseline_zero_escluse
)


# ============================================================
# 5. EVIDENZE RUNTIME
# ============================================================

def _analizza_runtime(df, start_unix, end_unix):
    """
    Esamina:
    - Heap: livello osservato.
    - GC Count: incremento al minuto.
    - GC Time: incremento al minuto.

    I reset dei contatori vengono registrati,
    ma non generano un normale tasso negativo.
    """

    segnalazioni = []
    serie_esaminate = 0
    reset_sospetti = 0

    df = df.loc[
        df["kpi_name"].isin(KPI_RUNTIME)
    ]

    for (componente, kpi), gruppo in df.groupby(
        ["cmdb_id", "kpi_name"]
    ):

        if kpi == "java_lang_Memory_HeapMemoryUsage_used":

            serie = gruppo[["timestamp", "value"]]

            famiglia = "memoria_heap"
            trasformazione = "livello_osservato"

        else:

            trasformata = calcola_incrementi_runtime(
                df=gruppo,
                componente=componente,
                kpi_name=kpi,
                start_unix=start_unix,
                end_unix=end_unix
            )

            reset_sospetti += int(
                trasformata["reset_sospetto"].sum()
            )

            serie = (
                trasformata[
                    ["timestamp", "incremento_per_minuto"]
                ]
                .rename(
                    columns={
                        "incremento_per_minuto": "value"
                    }
                )
                .dropna(subset=["value"])
            )

            famiglia = (
                "frequenza_gc"
                if "CollectionCount" in kpi
                else "tempo_gc"
            )

            trasformazione = "incremento_per_minuto"

        if len(serie) < 10:
            continue

        serie_esaminate += 1

        episodio = _rileva_aumento(serie)

        if episodio is None:
            continue

        segnalazioni.append({
            "sorgente": "runtime",
            "famiglia": famiglia,
            "componente": str(componente),
            "kpi": str(kpi),
            "tipo": "aumento_persistente_candidato",
            "trasformazione": trasformazione,
            "evidenza": episodio,
            "causa_verificata": False
        })

    return (
        segnalazioni,
        serie_esaminate,
        reset_sospetti
    )


# ============================================================
# 6. ORDINAMENTO E BUDGET
# ============================================================

def _seleziona(segnalazioni, limite):
    """
    Ordina secondo l'intensità dello scostamento
    rispetto alla mediana della stessa serie.

    Il punteggio NON è una probabilità di guasto.
    """

    ordinate = sorted(
        segnalazioni,
        key=lambda s: (
            -s["evidenza"]["intensita_relativa"],
            s["evidenza"]["timestamp_inizio"],
            s["componente"],
            s["kpi"]
        )
    )

    return ordinate[:limite]


# ============================================================
# 7. FUNZIONE PUBBLICA
# ============================================================

def rileva_evidenze_mesh_runtime(
    df_mesh,
    df_runtime,
    start_unix: int,
    end_unix: int,
    max_evidenze_mesh: int = 5,
    max_evidenze_runtime: int = 5
) -> dict:
    """
    Costruisce un report preliminare Mesh/Runtime.

    Nessuna ground truth.
    Nessuna chiamata all'LLM.
    Nessuna diagnosi causale.
    """

    if start_unix >= end_unix:
        raise ValueError("Finestra temporale non valida.")

    if max_evidenze_mesh < 0 or max_evidenze_runtime < 0:
        raise ValueError("Budget negativo.")

    mesh = _prepara(
        df_mesh, start_unix, end_unix
    )

    runtime = _prepara(
        df_runtime, start_unix, end_unix
    )

    (
        evidenze_mesh,
        coppie_mesh,
        baseline_zero_mesh
    ) = _analizza_mesh(mesh)

    (
        evidenze_runtime,
        serie_runtime,
        reset_runtime
    ) = _analizza_runtime(
        runtime, start_unix, end_unix
    )

    selezionate_mesh = _seleziona(
        evidenze_mesh,
        max_evidenze_mesh
    )

    selezionate_runtime = _seleziona(
        evidenze_runtime,
        max_evidenze_runtime
    )

    selezionate = (
        selezionate_mesh + selezionate_runtime
    )

    return {
        "versione": "mesh_runtime_evidence_v1",
        "finestra": {
            "start_unix": int(start_unix),
            "end_unix": int(end_unix)
        },
        "copertura": {
            "coppie_mesh_esaminate": coppie_mesh,

            # Serie Mesh escluse dal rilevamento
            # a causa della mediana della durata nulla.
            "baseline_zero_mesh_escluse": baseline_zero_mesh,

            "serie_runtime_esaminate": serie_runtime,
            "reset_runtime_sospetti": reset_runtime
        },
        "conteggi": {
            "mesh_rilevate": len(evidenze_mesh),
            "runtime_rilevate": len(evidenze_runtime),
            "mesh_selezionate": len(selezionate_mesh),
            "runtime_selezionate": len(selezionate_runtime),
            "totale_selezionato": len(selezionate),
            "omesse_per_budget": (
                len(evidenze_mesh)
                + len(evidenze_runtime)
                - len(selezionate)
            )
        },
        "evidenze": selezionate,
        "limitazioni": [
            "Le evidenze non identificano la root cause.",
            "Le soglie sono euristiche e preliminari.",
            "Le durate Mesh sono valori osservati.",
            "I livelli di richieste non sono tassi verificati.",
            "I contatori GC hanno semantica preliminare.",
            "Il rilevatore può non identificare guasti "
            "privi di aumenti persistenti.",
            "La baseline usa la finestra analizzata."
        ]
    }