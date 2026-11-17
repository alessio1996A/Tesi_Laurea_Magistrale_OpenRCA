"""
Rilevatore preliminare di evidenze Mesh/Runtime per A1.

Obiettivo:
- Identificare aumenti persistenti nei segnali selezionati.
- Conservare la provenienza temporale e il componente.
- Evitare diagnosi causali automatiche.
- Limitare il numero di evidenze da inviare all'LLM.

Non usa ground truth e non chiama Gemini.

Struttura del modulo:
- `_prepara`: filtra e pulisce la telemetria nella finestra del caso;
- `_rileva_aumento`: cerca in una serie l'episodio di aumento persistente più intenso (mediana + MAD);
- `_analizza_mesh`: applica il rilevatore alle durate delle richieste del service mesh (Istio);
- `_analizza_runtime`: lo applica ai KPI della JVM (memoria heap e contatori del garbage collector);
- `_seleziona`: ordina le segnalazioni per intensità e applica il budget;
- `rileva_evidenze_mesh_runtime`: funzione pubblica che costruisce il report completo;
- `aggrega_evidenze_mesh`: raggruppa le evidenze Mesh delle repliche dello stesso servizio.

Le segnalazioni sono ipotesi osservative (`causa_verificata` è sempre False), non cause radice.
"""

import numpy as np
import pandas as pd

from harness.signal_catalog import (
    calcola_incrementi_runtime
)


# ============================================================
# 1. CONFIGURAZIONE
# ============================================================

# KPI della JVM analizzati: memoria heap in uso, numero di raccolte del garbage collector (contatore
# cumulativo) e tempo totale speso in raccolta (contatore cumulativo).
KPI_RUNTIME = (
    "java_lang_Memory_HeapMemoryUsage_used",
    "java_lang_GarbageCollector_CollectionCount.Copy",
    "java_lang_GarbageCollector_CollectionTime.Copy",
)

# Prefissi dei KPI Istio: la durata delle richieste e il loro conteggio. Dopo il prefisso c'è lo stesso
# suffisso (la coppia sorgente/destinazione), che permette di accoppiare le due serie.
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

    Argomenti:
      df                   tabella con le colonne timestamp, cmdb_id, kpi_name, value.
      start_unix, end_unix finestra [start, end) da mantenere, in secondi unix.

    Restituisce una copia con soli numeri finiti, nessun campo mancante e solo i campioni della finestra.
    """

    # Colonne obbligatorie: senza di esse la telemetria non è utilizzabile.
    colonne = {
        "timestamp", "cmdb_id",
        "kpi_name", "value"
    }

    if not colonne.issubset(df.columns):
        raise ValueError("Colonne telemetria mancanti.")

    dati = df[
        ["timestamp", "cmdb_id", "kpi_name", "value"]
    ].copy()

    # Conversione numerica tollerante: i valori non convertibili diventano NaN e vengono scartati sotto.
    dati["timestamp"] = pd.to_numeric(
        dati["timestamp"], errors="coerce"
    )

    dati["value"] = pd.to_numeric(
        dati["value"], errors="coerce"
    )

    # Gli infiniti non sono misure valide: li trattiamo come valori mancanti.
    dati["value"] = dati["value"].replace(
        [np.inf, -np.inf], np.nan
    )

    dati = dati.dropna(
        subset=["timestamp", "value",
                "cmdb_id", "kpi_name"]
    )

    # Teniamo solo la finestra del caso: start incluso, end escluso.
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

    Argomenti:
      serie                DataFrame con le colonne `timestamp` e `value` (anche più campioni per istante).
      min_campioni         campioni minimi (dopo il consolidamento per istante) per valutare la serie.
      consecutivi          campioni sopra soglia di fila necessari per formare un episodio.
      max_gap_secondi      distanza massima tra due campioni successivi dello stesso episodio.
      scostamento_minimo   frazione minima della mediana che l'aumento deve superare (0.30 = 30%).

    Restituisce un dizionario con inizio, fine, durata in campioni, mediana, MAD, soglia, valore massimo,
    aumento percentuale e intensità relativa dell'episodio scelto.
    """

    # Più campioni con lo stesso istante vengono consolidati con la mediana; poi ordine cronologico.
    serie = (
        serie.groupby("timestamp", as_index=False)["value"]
        .median()
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    # Evitiamo decisioni su serie troppo brevi.
    if len(serie) < min_campioni:
        return None

    valori = serie["value"].to_numpy(dtype=float)
    tempi = serie["timestamp"].to_numpy(dtype=float)

    mediana = float(np.median(valori))

    # MAD (deviazione assoluta mediana): mediana delle distanze dei valori dalla mediana.
    mad = float(
        np.median(np.abs(valori - mediana))
    )

    # Soglia: la mediana più il maggiore tra tre margini: quattro dispersioni robuste (1.4826 * MAD),
    # la frazione minima della mediana e un minimo assoluto che evita una soglia coincidente con la mediana.
    soglia = mediana + max(
        4.0 * 1.4826 * mad,
        scostamento_minimo * abs(mediana),
        1e-9
    )

    sopra_soglia = valori > soglia

    # `episodi` conterrà coppie (posizione iniziale, posizione finale) dei tratti sopra soglia.
    # `inizio` è la posizione di apertura dell'episodio in corso (None = nessuno aperto);
    # `precedente` è la posizione dell'ultimo campione sopra soglia incluso nell'episodio.
    episodi = []
    inizio = None
    precedente = None

    # Individuiamo sequenze consecutive di campioni
    # sopra soglia, senza attraversare buchi temporali.
    for i, anomalo in enumerate(sopra_soglia):

        # Il campione è "consecutivo" se segue il precedente sopra soglia entro il salto temporale massimo.
        consecutivo = (
            precedente is not None
            and tempi[i] - tempi[precedente]
            <= max_gap_secondi
        )

        if anomalo:

            # Si apre un nuovo episodio se non ce n'è uno in corso o se c'è un salto temporale:
            # l'eventuale episodio precedente viene chiuso e registrato.
            if inizio is None or not consecutivo:

                if inizio is not None:
                    episodi.append((inizio, precedente))

                inizio = i

            precedente = i

        else:

            # Un campione sotto soglia chiude l'episodio in corso.
            if inizio is not None:
                episodi.append((inizio, precedente))

            inizio = None
            precedente = None

    # Registriamo l'eventuale ultimo episodio ancora aperto alla fine della serie.
    if inizio is not None:
        episodi.append((inizio, precedente))

    # Almeno tre campioni anomali consecutivi (valore di default del parametro `consecutivi`).
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

    # Valore massimo raggiunto dall'episodio scelto.
    massimo = float(
        np.max(valori[inizio:fine + 1])
    )

    # Descrizione dell'episodio: `aumento_pct` è None quando la mediana è quasi nulla (la percentuale
    # non sarebbe significativa); `intensita_relativa` è il superamento della soglia rapportato alla mediana
    # e serve a ordinare le segnalazioni in `_seleziona`.
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

    Argomenti:
      df  telemetria Mesh già ripulita da `_prepara` (colonne timestamp, cmdb_id, kpi_name, value).

    Restituisce una tupla: (segnalazioni, coppie durata/richieste esaminate, serie escluse perché con
    mediana della durata nulla).
    """

    segnalazioni = []
    coppie_esaminate = 0

    # Numero di serie Mesh con mediana della durata
    # nulla: non sono adatte a questo rilevatore
    # basato sullo scostamento relativo.
    baseline_zero_escluse = 0

    # Separiamo le serie del conteggio delle richieste da quelle della durata.
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

        # Consideriamo solo i componenti Mesh lato destinazione ("...destination...").
        if ".destination." not in str(componente):
            continue

        # Il KPI delle richieste ha lo stesso suffisso del KPI della durata: ricaviamo il nome accoppiato.
        suffisso = kpi[len(PREFISSO_DURATA):]

        kpi_richieste = PREFISSO_RICHIESTE + suffisso

        gruppo_richieste = gruppi_richieste.get(
            (componente, kpi_richieste)
        )

        # Senza la serie delle richieste accoppiata la durata non si può contestualizzare: si salta.
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

        # Servono almeno 10 istanti in comune; le coppie troppo corte non si valutano.
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

        # Campioni accoppiati che cadono dentro l'episodio: servono a riportare il livello di richieste
        # osservato mentre la durata era alta (contesto, non spiegazione).
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

    Argomenti:
      df                    telemetria Runtime già ripulita da `_prepara`.
      start_unix, end_unix  finestra del caso, in secondi unix (serve al calcolo degli incrementi).

    Restituisce una tupla: (segnalazioni, serie esaminate, numero di reset sospetti dei contatori).
    """

    segnalazioni = []
    serie_esaminate = 0
    reset_sospetti = 0

    # Teniamo soltanto i KPI della JVM previsti.
    df = df.loc[
        df["kpi_name"].isin(KPI_RUNTIME)
    ]

    for (componente, kpi), gruppo in df.groupby(
        ["cmdb_id", "kpi_name"]
    ):

        # La memoria heap è un livello: si analizza il valore così com'è.
        if kpi == "java_lang_Memory_HeapMemoryUsage_used":

            serie = gruppo[["timestamp", "value"]]

            famiglia = "memoria_heap"
            trasformazione = "livello_osservato"

        else:

            # I contatori del garbage collector sono cumulativi: si converte la serie in incremento al
            # minuto (calcolo condiviso con `signal_catalog`) e si analizza quello.
            trasformata = calcola_incrementi_runtime(
                df=gruppo,
                componente=componente,
                kpi_name=kpi,
                start_unix=start_unix,
                end_unix=end_unix
            )

            # Contiamo i punti in cui il contatore sembra essersi azzerato (riavvio del processo):
            # non producono un incremento negativo ma vengono segnalati nel report.
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

            # Famiglia: frequenza delle raccolte (conteggio) o tempo speso in raccolta.
            famiglia = (
                "frequenza_gc"
                if "CollectionCount" in kpi
                else "tempo_gc"
            )

            trasformazione = "incremento_per_minuto"

        # Servono almeno 10 campioni per valutare la serie.
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

    Argomenti:
      segnalazioni  elenco di segnalazioni, ciascuna con `evidenza.intensita_relativa`.
      limite        numero massimo di segnalazioni da restituire (budget).

    Restituisce le prime `limite` segnalazioni: prima la più intensa, a parità la più precoce, poi per
    componente e KPI in ordine alfabetico (ordinamento deterministico).
    """

    # Il segno meno su `intensita_relativa` ordina dal valore più alto al più basso.
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

    Argomenti:
      df_mesh, df_runtime       telemetria Mesh (Istio) e Runtime (JVM), con le colonne timestamp,
                                cmdb_id, kpi_name, value.
      start_unix, end_unix      finestra del caso, in secondi unix (start < end).
      max_evidenze_mesh         budget di evidenze Mesh da riportare (>= 0).
      max_evidenze_runtime      budget di evidenze Runtime da riportare (>= 0).

    Restituisce un report "mesh_runtime_evidence_v1" con finestra, copertura (cosa è stato esaminato ed
    escluso), conteggi (rilevate, selezionate, omesse per budget), le evidenze scelte e le limitazioni.

    Passi: (1) controllo degli argomenti; (2) pulizia della telemetria; (3) rilevamento Mesh e Runtime
    su tutte le serie; (4) selezione entro il budget; (5) costruzione del report.
    """

    # --- 1. Controllo degli argomenti.
    if start_unix >= end_unix:
        raise ValueError("Finestra temporale non valida.")

    if max_evidenze_mesh < 0 or max_evidenze_runtime < 0:
        raise ValueError("Budget negativo.")

    # --- 2. Pulizia: solo campioni validi nella finestra del caso.
    mesh = _prepara(
        df_mesh, start_unix, end_unix
    )

    runtime = _prepara(
        df_runtime, start_unix, end_unix
    )

    # --- 3. Rilevamento su TUTTE le serie: il budget si applica solo dopo, così i conteggi
    # (rilevate, omesse) restano completi.
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

    # --- 4. Selezione entro il budget, separatamente per Mesh e Runtime (le più intense per prime).
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

    # --- 5. Report: `omesse_per_budget` = evidenze rilevate meno quelle riportate.
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

    Argomenti:
      report              report "mesh_runtime_evidence_v1" NON troncato dal budget.
      tolleranza_secondi  distanza massima tra l'inizio del primo episodio di un gruppo e quello dei successivi.

    Restituisce un report "mesh_aggregation_v1" con le unità aggregate (multi-replica o singole), i
    conteggi e le limitazioni. Nessuna evidenza viene persa: l'insieme degli indici di origine prima e dopo
    l'aggregazione è controllato.

    Passi: (1) validazione; (2) estrazione delle evidenze Mesh con servizio e replica; (3) raggruppamento per
    servizio, rotta e KPI; (4) aggregazione temporale; (5) costruzione delle unità; (6) ordinamento;
    (7) controllo della provenienza; (8) report.
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

    # Elenco semplificato delle sole evidenze Mesh; `indice_origine` è la posizione nel report originale,
    # che permette di verificare alla fine che nessuna evidenza sia andata persa.
    elementi = []

    for indice, evidenza in enumerate(report["evidenze"]):

        # Le evidenze Runtime non partecipano all'aggregazione.
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

        # Dati dell'episodio rilevato (inizio, fine, mediana, massimo...) riportati nell'elemento.
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

    # `raggruppabili`: elementi raccolti per chiave (servizio, comunicazione, KPI).
    # `singole_non_identificabili`: elementi di cui non si è riconosciuto il servizio, ciascuno gruppo a sé.
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

    # Elenco finale dei gruppi: si parte dalle evidenze singole non identificabili.
    gruppi = list(singole_non_identificabili)

    # =====================================================
    # 4. AGGREGAZIONE TEMPORALE
    # =====================================================

    # Per ogni chiave (in ordine alfabetico, per un risultato deterministico) si ordinano gli episodi per
    # istante d'inizio e li si raccoglie in gruppi di repliche vicine nel tempo.
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

            # Componenti già presenti nel gruppo: la stessa replica non può comparire due volte.
            repliche_presenti = {
                e["componente"]
                for e in gruppo_corrente
            }

            # Stesso gruppo se è abbastanza vicino al primo episodio e porta una replica nuova;
            # altrimenti si chiude il gruppo e se ne apre uno nuovo.
            if (
                distanza <= tolleranza_secondi
                and elemento["componente"]
                not in repliche_presenti
            ):

                gruppo_corrente.append(elemento)

            else:

                gruppi.append(gruppo_corrente)
                gruppo_corrente = [elemento]

        # L'ultimo gruppo non viene chiuso dal ciclo: lo aggiungiamo qui.
        if gruppo_corrente:
            gruppi.append(gruppo_corrente)

    # =====================================================
    # 5. COSTRUZIONE DELLE UNITÀ AGGREGATE
    # =====================================================

    # Ogni gruppo diventa un'unità del report, con il dettaglio di ciascuna replica coinvolta.
    unita = []

    for gruppo in gruppi:

        # Ordine cronologico interno al gruppo (a parità: nome del componente).
        gruppo = sorted(
            gruppo,
            key=lambda x: (
                x["inizio"],
                x["componente"]
            )
        )

        # Il primo episodio del gruppo fornisce servizio, rotta e KPI (uguali per tutti, per costruzione).
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

        # Dettaglio per replica: tempi, valori e livello di richieste durante l'episodio.
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

        # Incremento assoluto di ogni replica rispetto alla propria mediana (mai negativo); il massimo
        # del gruppo serve a ordinare le unità.
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
    # (Il segno meno ordina dal valore più alto al più basso.)

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

    # Ogni evidenza Mesh originale deve comparire in una e una sola unità aggregata: si confrontano
    # gli indici di origine prima e dopo l'aggregazione.
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

    # Numero di unità multi-replica (le altre sono singole).
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