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
def compatta_anomalie_direzionali(
    anomalie: list[dict],
    start_unix: int,
    end_unix: int,
    max_distanza_secondi: int = 60
) -> dict:
    """
    Raggruppa gli episodi anomali rilevati dal
    detector direzionale.

    Due episodi vengono aggregati soltanto se:
      1. appartengono alla stessa sorgente;
      2. riguardano lo stesso componente;
      3. appartengono alla stessa famiglia;
      4. hanno la stessa direzione;
      5. sono temporalmente sovrapposti o vicini.

    Un gruppo è un'evidenza correlata, NON una root cause.

    Non usa ground truth e non assegna diagnosi.
    """

    from collections import defaultdict

    if start_unix >= end_unix:
        raise ValueError("Finestra temporale non valida.")

    if max_distanza_secondi < 0:
        raise ValueError("Distanza massima non valida.")

    # =====================================================
    # 1. VALIDAZIONE E ORGANIZZAZIONE
    # =====================================================

    richiesti = {
        "sorgente", "componente", "famiglia",
        "direzione", "kpi",
        "inizio_unix", "fine_unix",
        "score_picco"
    }

    per_componente = defaultdict(list)

    for evento in anomalie:

        if not richiesti.issubset(evento):
            raise ValueError(
                "Evento privo dei campi richiesti."
            )

        inizio = int(evento["inizio_unix"])
        fine = int(evento["fine_unix"])

        if not (start_unix <= inizio <= fine < end_unix):
            raise ValueError(
                "Evento esterno alla finestra ufficiale."
            )

        # Non mescoliamo sorgenti, componenti,
        # famiglie o direzioni differenti.
        chiave = (
            evento["sorgente"],
            evento["componente"],
            evento["famiglia"],
            evento["direzione"]
        )

        per_componente[chiave].append(evento)

    gruppi = []

    # =====================================================
    # 2. RAGGRUPPAMENTO TEMPORALE
    # =====================================================

    for chiave, eventi in sorted(
        per_componente.items()
    ):

        eventi = sorted(
            eventi,
            key=lambda e: (
                e["inizio_unix"],
                e["fine_unix"],
                e["kpi"]
            )
        )

        gruppo_corrente = []
        fine_corrente = None

        def registra_gruppo(episodi):
            """
            Trasforma un insieme di episodi correlati
            in una singola evidenza compatta.
            """

            if not episodi:
                return

            inizio = min(
                int(e["inizio_unix"])
                for e in episodi
            )

            fine = max(
                int(e["fine_unix"])
                for e in episodi
            )

            # Manteniamo i KPI distinti: più osservazioni
            # della stessa metrica non devono moltiplicare
            # il numero dei segnali indipendenti.
            nomi_kpi = sorted({
                str(e["kpi"])
                for e in episodi
            })

            sorgente, componente, famiglia, direzione = chiave

            gruppi.append({
                "sorgente": sorgente,
                "componente": componente,
                "famiglia": famiglia,
                "direzione": direzione,
                "inizio_osservato_unix": inizio,
                "fine_osservata_unix": fine,
                "kpi": nomi_kpi,
                "numero_kpi_distinti": len(nomi_kpi),
                "episodi_aggregati": len(episodi),

                # Se l'evento è vicino all'inizio della
                # finestra, il suo vero inizio potrebbe
                # precedere il periodo osservato.
                "vicino_inizio_finestra": (
                    inizio <= start_unix + 60
                ),

                "interpretazione": (
                    "Evidenza statistica correlata; "
                    "causalita non verificata."
                )
            })

        for evento in eventi:

            inizio_evento = int(
                evento["inizio_unix"]
            )

            fine_evento = int(
                evento["fine_unix"]
            )

            if not gruppo_corrente:

                gruppo_corrente = [evento]
                fine_corrente = fine_evento
                continue

            # Aggregazione solo con intervalli
            # sufficientemente vicini.
            if (
                inizio_evento
                <= fine_corrente + max_distanza_secondi
            ):

                gruppo_corrente.append(evento)

                fine_corrente = max(
                    fine_corrente,
                    fine_evento
                )

            else:

                registra_gruppo(gruppo_corrente)

                gruppo_corrente = [evento]
                fine_corrente = fine_evento

        registra_gruppo(gruppo_corrente)

    # =====================================================
    # 3. ORDINAMENTO DETERMINISTICO
    # =====================================================

    gruppi.sort(
        key=lambda g: (
            g["inizio_osservato_unix"],
            g["sorgente"],
            g["componente"],
            g["famiglia"]
        )
    )

    # =====================================================
    # 4. REPORT FINALE
    # =====================================================

    return {
        "versione": "directional_groups_v1",
        "finestra": {
            "start_unix": start_unix,
            "end_unix": end_unix
        },
        "episodi_originali": len(anomalie),
        "gruppi_totali": len(gruppi),
        "gruppi": gruppi
    }

def costruisci_report_evidenze_v2(
    df_nodi,
    df_container,
    cloudbed: str,
    start_unix: int,
    end_unix: int
) -> dict:
    """
    Costruisce il report A1-v2.

    A1-v2 combina:
      1. Le evidenze originali di A1-v1;
      2. Il rilevamento direzionale multi-risorsa;
      3. La compattazione degli episodi correlati.

    I gruppi CPU del nuovo rilevatore non vengono
    aggiunti una seconda volta: l'analisi CPU/load
    rimane rappresentata dal report A1-v1.

    IMPORTANTE:
    - Non legge ground truth.
    - Non stabilisce la root cause.
    - Non chiama Gemini.
    - Non modifica A1-v1.
    """

    from harness.anomaly_detector import (
        rileva_anomalie_direzionali
    )

    # =====================================================
    # 1. VALIDAZIONE
    # =====================================================

    if cloudbed not in ("cloudbed-1", "cloudbed-2"):
        raise ValueError("Cloudbed non valido.")

    if start_unix >= end_unix:
        raise ValueError("Finestra temporale non valida.")

    # =====================================================
    # 2. REPORT ORIGINALE A1-v1
    # =====================================================

    # Riutilizziamo esattamente l'Evidence Builder
    # precedente, senza modificarne il comportamento.

    report_v1 = costruisci_report_evidenze(
        df_nodi=df_nodi,
        df_container=df_container,
        cloudbed=cloudbed,
        start_unix=start_unix,
        end_unix=end_unix
    )

    # =====================================================
    # 3. RILEVAMENTO DIREZIONALE DEI NODI
    # =====================================================

    anomalie_nodi = rileva_anomalie_direzionali(
        df=df_nodi,
        sorgente="node_metrics",
        start_unix=start_unix,
        end_unix=end_unix
    )

    # =====================================================
    # 4. RILEVAMENTO DIREZIONALE DEI CONTAINER
    # =====================================================

    anomalie_container = rileva_anomalie_direzionali(
        df=df_container,
        sorgente="container_metrics",
        start_unix=start_unix,
        end_unix=end_unix
    )

    # Uniamo i risultati delle due sorgenti.
    anomalie_direzionali = (
        anomalie_nodi + anomalie_container
    )

    # =====================================================
    # 5. COMPATTAZIONE DEGLI EPISODI
    # =====================================================

    report_compattazione = compatta_anomalie_direzionali(
        anomalie=anomalie_direzionali,
        start_unix=start_unix,
        end_unix=end_unix,
        max_distanza_secondi=60
    )

    gruppi_compatti = report_compattazione["gruppi"]

    # =====================================================
    # 6. SEPARAZIONE DELLA CPU
    # =====================================================

    # A1-v1 contiene già una rappresentazione
    # delle anomalie CPU/load.
    #
    # Non replichiamo quindi i nuovi gruppi CPU.
    #
    # Questa è una deduplicazione a livello di
    # famiglia, non una verifica che i singoli
    # episodi siano perfettamente equivalenti.

    gruppi_cpu = [
        gruppo
        for gruppo in gruppi_compatti
        if gruppo["famiglia"] == "cpu"
    ]

    gruppi_aggiuntivi = [
        gruppo
        for gruppo in gruppi_compatti
        if gruppo["famiglia"] != "cpu"
    ]

    # =====================================================
    # 7. ORDINAMENTO DETERMINISTICO
    # =====================================================

    # Manteniamo tutti i gruppi aggiuntivi.
    # Non introduciamo ancora un ranking o un limite
    # arbitrario che potrebbe nascondere evidenze.

    gruppi_aggiuntivi.sort(
        key=lambda g: (
            g["inizio_osservato_unix"],
            g["sorgente"],
            g["componente"],
            g["famiglia"],
            g["direzione"]
        )
    )

    # =====================================================
    # 8. CONTROLLO DEI BORDI TEMPORALI
    # =====================================================

    # Un episodio osservato all'inizio della finestra
    # potrebbe essere iniziato prima.
    #
    # Analogamente, un episodio vicino alla fine
    # potrebbe continuare oltre il periodo disponibile.

    gruppi_finali = []

    for gruppo in gruppi_aggiuntivi:

        copia = dict(gruppo)

        copia["vicino_fine_finestra"] = (
            copia["fine_osservata_unix"]
            >= end_unix - 60
        )

        gruppi_finali.append(copia)

    # =====================================================
    # 9. RIEPILOGO PER FAMIGLIA
    # =====================================================

    riepilogo_famiglie = {}

    for gruppo in gruppi_finali:

        famiglia = gruppo["famiglia"]

        riepilogo_famiglie[famiglia] = (
            riepilogo_famiglie.get(famiglia, 0) + 1
        )

    # =====================================================
    # 10. COSTRUZIONE DEL REPORT A1-v2
    # =====================================================

    report_v2 = {
        "versione": "A1-v2",

        "cloudbed": cloudbed,

        "finestra": {
            "start_unix": start_unix,
            "end_unix": end_unix
        },

        # Report originale conservato integralmente.
        "evidenze_v1": report_v1,

        # Nuova estensione multi-risorsa.
        "estensione_multi_risorsa": {

            "metodo": "directional_median_mad_v1",

            "episodi_nodi": len(anomalie_nodi),

            "episodi_container": len(
                anomalie_container
            ),

            "episodi_direzionali_totali": len(
                anomalie_direzionali
            ),

            "gruppi_direzionali_totali": len(
                gruppi_compatti
            ),

            # Gruppi CPU non aggiunti al report.
            "gruppi_cpu_non_duplicati": len(
                gruppi_cpu
            ),

            "gruppi_aggiuntivi_totali": len(
                gruppi_finali
            ),

            "gruppi_per_famiglia": riepilogo_famiglie,

            "gruppi": gruppi_finali
        },

        "limiti_interpretativi": [
            (
                "Le anomalie sono deviazioni statistiche "
                "e non costituiscono prove causali."
            ),
            (
                "KPI correlati non rappresentano "
                "necessariamente evidenze indipendenti."
            ),
            (
                "Il primo timestamp osservato non "
                "coincide necessariamente con l'inizio "
                "del guasto."
            ),
            (
                "L'assenza di anomalie rilevate non "
                "dimostra che un componente sia sano."
            ),
            (
                "I gruppi CPU del detector direzionale "
                "non sono riportati due volte; l'analisi "
                "CPU/load originale resta in evidenze_v1."
            )
        ]
    }

    return report_v2