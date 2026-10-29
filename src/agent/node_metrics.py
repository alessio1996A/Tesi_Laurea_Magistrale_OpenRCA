
import zipfile
import re
import pandas as pd
from typing import Optional, Literal

from agent.tools import DATASET_ZIP_PATH, _get_telemetry_csv_paths


def tool_get_node_metrics(
    start_unix: int,
    end_unix: int,
    cmdb_id: Optional[str] = None,
    kpi_name: Optional[str] = None,
    max_rows: int = 100,
    market_system: Literal["cloudbed-1", "cloudbed-2"] = "cloudbed-1",
) -> str:
    """
    Restituisce statistiche delle metriche dei nodi.

    Analizza soltanto la finestra temporale richiesta.
    Non esegue anomaly detection o diagnosi automatica.
    """

    if start_unix >= end_unix:
        return "Errore: intervallo temporale non valido."

    if max_rows < 1:
        return "Errore: max_rows deve essere almeno 1."

    if not cmdb_id and not kpi_name:
        return "Specificare almeno cmdb_id oppure kpi_name."

    try:
        # Il filtro KPI supporta espressioni regolari.
        pattern = (
            re.compile(kpi_name, re.IGNORECASE)
            if kpi_name else None
        )

        # Recuperiamo soltanto i percorsi dei giorni necessari.
        percorsi = _get_telemetry_csv_paths(
            start_unix=start_unix,
            end_unix=end_unix,
            market_system=market_system,
            data_kind="node_metrics",
        )

        # Accumulatori per ogni coppia nodo/KPI.
        statistiche = {}
        totale_record = 0

        with zipfile.ZipFile(DATASET_ZIP_PATH, "r") as archivio:
            for percorso in percorsi:
                with archivio.open(percorso) as file:
                    for chunk in pd.read_csv(file, chunksize=100_000):

                        # Convertiamo timestamp e valori in numeri.
                        t = pd.to_numeric(
                            chunk["timestamp"], errors="coerce"
                        )
                        v = pd.to_numeric(
                            chunk["value"], errors="coerce"
                        )

                        # Filtriamo la finestra [inizio, fine).
                        mask = (
                            t.ge(start_unix)
                            & t.lt(end_unix)
                            & t.notna()
                            & v.notna()
                        )

                        if cmdb_id:
                            mask &= (
                                chunk["cmdb_id"].astype(str).str.lower()
                                == cmdb_id.strip().lower()
                            )

                        if pattern is not None:
                            mask &= chunk["kpi_name"].astype(str).str.contains(
                                pattern, na=False
                            )

                        filtrati = chunk.loc[
                            mask, ["cmdb_id", "kpi_name"]
                        ].copy()

                        if filtrati.empty:
                            continue

                        filtrati["timestamp"] = t.loc[mask]
                        filtrati["value"] = v.loc[mask]
                        totale_record += len(filtrati)

                        # Aggreghiamo i dati per nodo e KPI.
                        for chiave, gruppo in filtrati.groupby(
                            ["cmdb_id", "kpi_name"]
                        ):
                            valori = gruppo["value"]
                            tempi = gruppo["timestamp"]

                            if chiave not in statistiche:
                                statistiche[chiave] = {
                                    "campioni": 0,
                                    "somma": 0.0,
                                    "minimo": float("inf"),
                                    "massimo": float("-inf"),
                                    "primo_timestamp": float("inf"),
                                    "ultimo_timestamp": float("-inf"),
                                }

                            s = statistiche[chiave]
                            s["campioni"] += len(gruppo)
                            s["somma"] += valori.sum()
                            s["minimo"] = min(s["minimo"], valori.min())
                            s["massimo"] = max(s["massimo"], valori.max())
                            s["primo_timestamp"] = min(
                                s["primo_timestamp"], tempi.min()
                            )
                            s["ultimo_timestamp"] = max(
                                s["ultimo_timestamp"], tempi.max()
                            )

        if not statistiche:
            return "Nessuna metrica nodo trovata per i filtri richiesti."

        # Prepariamo un riepilogo compatto per l'LLM.
        righe = []

        for (nodo, kpi), s in statistiche.items():
            righe.append({
                "cmdb_id": nodo,
                "kpi_name": kpi,
                "campioni": s["campioni"],
                "media": round(s["somma"] / s["campioni"], 6),
                "minimo": round(s["minimo"], 6),
                "massimo": round(s["massimo"], 6),
                "primo_timestamp": int(s["primo_timestamp"]),
                "ultimo_timestamp": int(s["ultimo_timestamp"]),
            })

        riepilogo = pd.DataFrame(righe).sort_values(
            ["cmdb_id", "kpi_name"]
        )

        gruppi_totali = len(riepilogo)
        riepilogo = riepilogo.head(max_rows)

        return (
            f"Cloudbed: {market_system}\\n"
            f"Intervallo Unix: {start_unix} - {end_unix}\\n"
            f"Nodo: {cmdb_id or 'Tutti'}\\n"
            f"Filtro KPI: {kpi_name or 'Nessuno'}\\n"
            f"Record analizzati: {totale_record}\\n"
            f"Gruppi trovati: {gruppi_totali}\\n"
            f"Gruppi mostrati: {len(riepilogo)}\\n\\n"
            f"{riepilogo.to_string(index=False)}"
        )

    except Exception as exc:
        return f"Errore del tool: {type(exc).__name__}: {exc}"
