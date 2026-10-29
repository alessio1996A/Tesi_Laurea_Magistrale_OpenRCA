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
# ============================================================
# 8. AGGREGAZIONE DELLE EVIDENZE MESH MULTI-REPLICA
# ============================================================

def aggrega_evidenze_mesh(
    report: dict,
    tolleranza_secondi: int = 180
) -> dict:
    """
    Aggrega anomalie Mesh temporalmente vicine
    su repliche dello stesso servizio.

    Vincoli:
    - stesso servizio;
    - stessa comunicazione (destinazione);
    - stesso KPI;
    - inizio degli episodi entro la tolleranza;
    - almeno due repliche distinte per aggregare.

    Riceve tutte le evidenze Mesh rilevate,
    NON un report già troncato dal budget.

    Non modifica il report originale.
    Non utilizza ground truth.
    Non attribuisce cause.
    """

    import re

    # =====================================================
    # 1. VALIDAZIONE
    # =====================================================

    if report.get("versione") != "mesh_runtime_evidence_v1":
        raise ValueError(
            "Versione del report Mesh/Runtime non valida."
        )

    if tolleranza_secondi < 0:
        raise ValueError(
            "La tolleranza temporale non può essere negativa."
        )

    conteggi = report["conteggi"]

    # L'aggregazione deve vedere anche le anomalie
    # che normalmente sarebbero escluse dal budget.
    if (
        conteggi["mesh_rilevate"]
        != conteggi["mesh_selezionate"]
    ):
        raise ValueError(
            "Il report Mesh è già troncato dal budget. "
            "Generare un report diagnostico con "
            "max_evidenze_mesh sufficientemente elevato."
        )

    # =====================================================
    # 2. ESTRAZIONE DELLE EVIDENZE MESH
    # =====================================================

    elementi = []

    for indice, evidenza in enumerate(report["evidenze"]):

        if evidenza["sorgente"] != "mesh":
            continue

        componente = evidenza["componente"]

        # Esempio:
        # emailservice-2.destination.checkoutservice.emailservice
        #
        # servizio = emailservice
        # replica = 2
        # comunicazione = checkoutservice.emailservice
        match = re.fullmatch(
            r"(.+)-(\d+)\.destination\.(.+)",
            componente
        )

        if match is None:

            # Non inventiamo il nome di un servizio.
            # L'evidenza rimane singola.
            servizio = None
            replica = None
            comunicazione = None

        else:

            servizio = match.group(1)
            replica = match.group(2)
            comunicazione = match.group(3)

        episodio = evidenza["evidenza"]

        elementi.append({
            "indice_origine": indice,
            "servizio": servizio,
            "replica": replica,
            "comunicazione": comunicazione,
            "componente": componente,
            "kpi": evidenza["kpi"],
            "inizio": int(
                episodio["timestamp_inizio"]
            ),
            "fine": int(
                episodio["timestamp_fine"]
            ),
            "mediana": float(
                episodio["mediana_riferimento"]
            ),
            "massimo": float(
                episodio["valore_massimo"]
            ),
            "aumento_pct": episodio["aumento_pct"],
            "campioni": int(
                episodio["campioni_consecutivi"]
            ),
            "richieste_durante": evidenza.get(
                "contesto_richieste", {}
            ).get(
                "mediana_durante_episodio"
            )
        })

    # =====================================================
    # 3. RAGGRUPPAMENTO PER SERVIZIO, ROTTA E KPI
    # =====================================================

    raggruppabili = {}
    singole_non_identificabili = []

    for elemento in elementi:

        if elemento["servizio"] is None:

            singole_non_identificabili.append(
                [elemento]
            )
            continue

        chiave = (
            elemento["servizio"],
            elemento["comunicazione"],
            elemento["kpi"]
        )

        raggruppabili.setdefault(
            chiave, []
        ).append(elemento)

    gruppi = list(singole_non_identificabili)

    # =====================================================
    # 4. AGGREGAZIONE TEMPORALE
    # =====================================================

    for chiave in sorted(raggruppabili):

        candidati = sorted(
            raggruppabili[chiave],
            key=lambda x: (
                x["inizio"],
                x["componente"],
                x["indice_origine"]
            )
        )

        gruppo_corrente = []

        for elemento in candidati:

            if not gruppo_corrente:

                gruppo_corrente = [elemento]
                continue

            # Confrontiamo con il PRIMO evento:
            # così la distanza complessiva del gruppo
            # non può superare la tolleranza.
            primo_inizio = gruppo_corrente[0]["inizio"]

            distanza = (
                elemento["inizio"] - primo_inizio
            )

            repliche_presenti = {
                e["componente"]
                for e in gruppo_corrente
            }

            if (
                distanza <= tolleranza_secondi
                and elemento["componente"]
                not in repliche_presenti
            ):

                gruppo_corrente.append(elemento)

            else:

                gruppi.append(gruppo_corrente)
                gruppo_corrente = [elemento]

        if gruppo_corrente:
            gruppi.append(gruppo_corrente)

    # =====================================================
    # 5. COSTRUZIONE DELLE UNITÀ AGGREGATE
    # =====================================================

    unita = []

    for gruppo in gruppi:

        gruppo = sorted(
            gruppo,
            key=lambda x: (
                x["inizio"],
                x["componente"]
            )
        )

        primo = gruppo[0]

        componenti = sorted({
            e["componente"]
            for e in gruppo
        })

        repliche = sorted({
            e["replica"]
            for e in gruppo
            if e["replica"] is not None
        })

        # Un gruppo è multi-replica soltanto
        # quando coinvolge almeno due repliche.
        multi_replica = (
            primo["servizio"] is not None
            and len(repliche) >= 2
            and len(componenti) >= 2
        )

        dettagli = []

        for elemento in gruppo:

            dettagli.append({
                "indice_origine": elemento[
                    "indice_origine"
                ],
                "componente": elemento["componente"],
                "timestamp_inizio": elemento["inizio"],
                "timestamp_fine": elemento["fine"],
                "mediana": elemento["mediana"],
                "massimo": elemento["massimo"],
                "aumento_pct": elemento["aumento_pct"],
                "campioni_consecutivi": elemento[
                    "campioni"
                ],
                "richieste_durante_episodio": elemento[
                    "richieste_durante"
                ]
            })

        incrementi_assoluti = [
            max(
                0.0,
                e["massimo"] - e["mediana"]
            )
            for e in gruppo
        ]

        unita.append({
            "tipo": (
                "mesh_multi_replica"
                if multi_replica
                else "mesh_singola"
            ),
            "famiglia": "durata_richieste",
            "servizio": primo["servizio"],
            "comunicazione": primo["comunicazione"],
            "kpi": primo["kpi"],
            "componenti": componenti,
            "numero_repliche": (
                len(repliche)
                if multi_replica
                else 1
            ),
            "timestamp_inizio": min(
                e["inizio"] for e in gruppo
            ),
            "timestamp_fine": max(
                e["fine"] for e in gruppo
            ),
            "incremento_massimo_assoluto": max(
                incrementi_assoluti
            ),
            "indici_origine": sorted(
                e["indice_origine"]
                for e in gruppo
            ),
            "dettagli_repliche": dettagli,
            "causa_verificata": False
        })

    # =====================================================
    # 6. ORDINAMENTO INVESTIGATIVO
    # =====================================================

    # Prima le correlazioni tra più repliche.
    # A parità di repliche, maggior incremento
    # assoluto osservato nella stessa famiglia KPI.
    #
    # Non è una probabilità di causalità.

    unita.sort(
        key=lambda u: (
            -u["numero_repliche"],
            -u["incremento_massimo_assoluto"],
            u["timestamp_inizio"],
            str(u["servizio"]),
            str(u["comunicazione"]),
            u["kpi"]
        )
    )

    # =====================================================
    # 7. CONTROLLO DELLA PROVENIENZA
    # =====================================================

    indici_originali = sorted(
        e["indice_origine"]
        for e in elementi
    )

    indici_aggregati = sorted(
        indice
        for u in unita
        for indice in u["indici_origine"]
    )

    if indici_originali != indici_aggregati:
        raise AssertionError(
            "Le evidenze Mesh sono state perse "
            "o duplicate durante l'aggregazione."
        )

    # =====================================================
    # 8. REPORT
    # =====================================================

    multi = sum(
        u["tipo"] == "mesh_multi_replica"
        for u in unita
    )

    return {
        "versione": "mesh_aggregation_v1",

        "tolleranza_secondi": tolleranza_secondi,

        "conteggi": {
            "evidenze_mesh_originali": len(elementi),
            "unita_dopo_aggregazione": len(unita),
            "gruppi_multi_replica": multi,
            "unita_singole": len(unita) - multi,
            "evidenze_perse": 0
        },

        "unita": unita,

        "limitazioni": [
            "La simultaneita non prova causalita.",
            "Gli aumenti descrivono durate osservate.",
            "L'aggregazione richiede stessa rotta e KPI.",
            "La tolleranza temporale e euristica.",
            "Le metriche con baseline zero sono escluse "
            "dal rilevatore precedente."
        ]
    }