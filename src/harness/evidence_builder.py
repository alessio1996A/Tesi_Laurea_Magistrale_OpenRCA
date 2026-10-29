# src/harness/evidence_builder.py

import numpy as np
import pandas as pd

from collections import Counter

from harness.preprocessor import preprocessa_metriche
from harness.metric_quality import valuta_qualita_metriche
from harness.anomaly_detector import rileva_anomalie
from harness.structural_patterns import raggruppa_anomalie
from harness.topology import costruisci_mappa_nodi_container


# KPI dei nodi già esaminati nel nostro prototipo.
# La selezione è indipendente dalla causa reale del guasto.
REGEX_KPI_NODO = r"^system\.(?:cpu|load)\."

# KPI container esaminati per la qualità dei dati.
# Non applichiamo loro trasformazioni in tassi.
KPI_CONTAINER = {
    "container_cpu_load_average_10s",
    "container_cpu_usage_seconds",
    "container_cpu_user_seconds",
    "container_cpu_system_seconds",
}


def _filtra_finestra(
    df: pd.DataFrame,
    start_unix: int,
    end_unix: int
) -> pd.DataFrame:
    """Mantiene esclusivamente i campioni della finestra ufficiale."""

    colonne = {"timestamp", "cmdb_id", "kpi_name", "value"}

    if not colonne.issubset(df.columns):
        raise ValueError("Il DataFrame non contiene le colonne richieste.")

    dati = df[list(colonne)].copy()

    dati["timestamp"] = pd.to_numeric(
        dati["timestamp"], errors="coerce"
    )

    mask = (
        dati["timestamp"].ge(start_unix)
        & dati["timestamp"].lt(end_unix)
    )

    return dati.loc[mask].copy()


def _riepilogo_qualita(risultati: list[dict]) -> dict:
    """Conta le serie per stato di qualità."""

    conteggi = Counter(
        risultato["stato"]
        for risultato in risultati
    )

    return {
        "serie_totali": len(risultati),
        "serie_costanti": conteggi["serie_costante"],
        "serie_variabili": conteggi["serie_variabile"],
        "serie_insufficienti": conteggi["campioni_insufficienti"],
    }


def _valori_json(oggetto):
    """Converte eventuali numeri NumPy in valori JSON standard."""

    if isinstance(oggetto, dict):
        return {
            str(chiave): _valori_json(valore)
            for chiave, valore in oggetto.items()
        }

    if isinstance(oggetto, (list, tuple)):
        return [_valori_json(x) for x in oggetto]

    if isinstance(oggetto, np.generic):
        return _valori_json(oggetto.item())

    if isinstance(oggetto, float) and not np.isfinite(oggetto):
        return None

    return oggetto


def costruisci_report_evidenze(
    df_nodi: pd.DataFrame,
    df_container: pd.DataFrame,
    cloudbed: str,
    start_unix: int,
    end_unix: int
) -> dict:
    """
    Integra i moduli deterministici dell'harness A1-v1.

    INPUT:
        Metriche dei nodi e dei container.
        Cloudbed e finestra ufficiale OpenRCA.

    OUTPUT:
        Report strutturato delle evidenze osservate.

    NON utilizza:
        - Gemini o altri LLM;
        - ground truth o record.csv;
        - diagnosi ricavate da etichette.

    Il report non dimostra relazioni causali.
    """

    if start_unix >= end_unix:
        raise ValueError("Intervallo temporale non valido.")

    if cloudbed not in {"cloudbed-1", "cloudbed-2"}:
        raise ValueError("Cloudbed non riconosciuto.")

    # =========================================================
    # 1. FILTRAGGIO DELLA FINESTRA UFFICIALE
    # =========================================================

    nodi = _filtra_finestra(
        df_nodi, start_unix, end_unix
    )

    container = _filtra_finestra(
        df_container, start_unix, end_unix
    )

    # =========================================================
    # 2. SELEZIONE DEI KPI DEL PROTOTIPO
    # =========================================================

    nodi_cpu = nodi[
        nodi["kpi_name"].astype(str).str.contains(
            REGEX_KPI_NODO,
            regex=True,
            na=False
        )
    ].copy()

    container_cpu = container[
        container["kpi_name"].isin(KPI_CONTAINER)
    ].copy()

    # =========================================================
    # 3. PREPROCESSING
    # =========================================================

    statistiche_nodi = (
        preprocessa_metriche(
            nodi_cpu,
            start_unix,
            end_unix,
            sorgente="node"
        )
        if not nodi_cpu.empty else []
    )

    statistiche_container = (
        preprocessa_metriche(
            container_cpu,
            start_unix,
            end_unix,
            sorgente="container"
        )
        if not container_cpu.empty else []
    )

    # =========================================================
    # 4. QUALITY CHECK
    # =========================================================

    qualita_nodi = (
        valuta_qualita_metriche(nodi_cpu)
        if not nodi_cpu.empty else []
    )

    qualita_container = (
        valuta_qualita_metriche(container_cpu)
        if not container_cpu.empty else []
    )

    # Per il rilevatore utilizziamo solo serie dei nodi
    # che non risultano costanti o insufficienti.
    serie_utilizzabili = {
        (r["componente"], r["kpi"])
        for r in qualita_nodi
        if r["stato"] == "serie_variabile"
    }

    if not nodi_cpu.empty:
        coppie = pd.MultiIndex.from_frame(
            nodi_cpu[["cmdb_id", "kpi_name"]]
        )

        mask_utilizzabili = coppie.isin(serie_utilizzabili)

        nodi_analizzabili = nodi_cpu.loc[
            mask_utilizzabili
        ].copy()

    else:
        nodi_analizzabili = nodi_cpu.copy()

    # =========================================================
    # 5. ANOMALY DETECTION
    # =========================================================

    anomalie = (
        rileva_anomalie(
            nodi_analizzabili,
            start_unix,
            end_unix,
            soglia=3.5,
            min_consecutivi=3
        )
        if not nodi_analizzabili.empty else []
    )

    anomalie.sort(
        key=lambda a: (
            a["timestamp_inizio"],
            a["componente"],
            a["kpi"]
        )
    )

    # =========================================================
    # 6. PATTERN STRUTTURALI
    # =========================================================

    patterns = raggruppa_anomalie(
        anomalie,
        max_distanza_secondi=180,
        min_kpi=2
    )

    # Evitiamo di duplicare le anomalie nel report:
    # ciascun pattern contiene già il proprio riepilogo.
    patterns_compatti = [
        {
            chiave: valore
            for chiave, valore in pattern.items()
            if chiave != "evidenze"
        }
        for pattern in patterns
    ]

    # =========================================================
    # 7. TOPOLOGIA NODO-CONTAINER
    # =========================================================

    nodi_interesse = sorted({
        str(x)
        for x in nodi["cmdb_id"].dropna().unique()
    })

    topologia = costruisci_mappa_nodi_container(
        cmdb_ids=container["cmdb_id"].dropna().unique(),
        nodi_interesse=nodi_interesse
    )

    # Compattiamo i nomi dei container senza perdere
    # il conteggio totale delle associazioni.
    topologia_compatta = []

    for elemento in topologia:
        topologia_compatta.append({
            "nodo": elemento["nodo"],
            "numero_container": elemento["numero_container"],
            "numero_servizi": elemento["numero_servizi"],
            "associazioni_disponibili":
                elemento["associazioni_disponibili"],
            "esempi_container":
                elemento["container_osservati"][:12]
        })

    # =========================================================
    # 8. REPORT FINALE
    # =========================================================

    report = {
        "versione": "A1-v1",

        "caso": {
            "cloudbed": cloudbed,
            "start_unix": int(start_unix),
            "end_unix": int(end_unix)
        },

        "copertura": {
            "campioni_nodo": len(nodi),
            "campioni_container": len(container),
            "campioni_nodo_cpu_load": len(nodi_cpu),
            "campioni_container_cpu": len(container_cpu),
            "serie_preprocessate_nodo":
                len(statistiche_nodi),
            "serie_preprocessate_container":
                len(statistiche_container)
        },

        "qualita": {
            "nodi": _riepilogo_qualita(qualita_nodi),
            "container": _riepilogo_qualita(qualita_container)
        },

        "anomalie": {
            "totale": len(anomalie),
            "segnalazioni": anomalie[:30],
            "segnalazioni_omesse": max(0, len(anomalie) - 30)
        },

        "patterns": {
            "totale": len(patterns_compatti),
            "segnalazioni": patterns_compatti[:20],
            "segnalazioni_omesse":
                max(0, len(patterns_compatti) - 20)
        },

        "topologia": topologia_compatta,

        "limitazioni": [
            "Il rilevatore considera solo aumenti persistenti.",
            "In questa versione la detection è limitata "
            "ai KPI CPU/load dei nodi.",
            "I contatori container con semantica non verificata "
            "non vengono trasformati in tassi.",
            "Le associazioni nodo-container non dimostrano causalità.",
            "L'assenza di anomalie non dimostra "
            "l'assenza di guasti."
        ]
    }

    return _valori_json(report)