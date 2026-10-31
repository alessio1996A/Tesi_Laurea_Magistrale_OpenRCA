"""R06 - candidato 'container read I/O load' per OpenRCA Market.

Detector indipendente da Gemini e da ground truth. Opera su valori osservati
``container_fs_reads_MB./dev/vda`` senza interpretarli come contatori cumulativi
ne' come throughput al secondo. Il suffisso MB e' trattato come unita' riportata
nel CSV, non come semantica definitivamente validata.

Confronta una baseline esplicita (potenzialmente non sana) con la finestra
successiva. Richiede una sequenza persistente di valori sopra una soglia
esplorativa. E' un *candidato da verificare*, mai una root cause certa.

Non contiene alcuna regola per le quattro classi riservate del protocollo 11+4.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

READ_MB = "container_fs_reads_MB./dev/vda"
READ_OPS = "container_fs_reads./dev/vda"
REQUIRED_COLUMNS = {"timestamp", "cmdb_id", "kpi_name", "value"}


def _serie(df: pd.DataFrame, kpi: str) -> pd.Series:
    righe = df.loc[df["kpi_name"].eq(kpi), ["timestamp", "value"]].copy()
    if righe.empty:
        return pd.Series(dtype="float64", name=kpi)
    righe["timestamp"] = pd.to_numeric(righe["timestamp"], errors="coerce")
    righe["value"] = pd.to_numeric(righe["value"], errors="coerce")
    righe = righe.replace([float("inf"), -float("inf")], float("nan"))
    righe = righe.dropna(subset=["timestamp", "value"])
    if righe.empty:
        return pd.Series(dtype="float64", name=kpi)
    # Duplicati medianati: nessuna somma, nessun incremento artificiale.
    serie = righe.groupby("timestamp")["value"].median().sort_index()
    serie.name = kpi
    return serie


def valuta_r06_container_read_io(
    telemetria: pd.DataFrame,
    componente: str,
    start_unix: int,
    baseline_end_unix: int,
    end_unix: int,
    *,
    soglia_robusta: float = 3.5,
    incremento_minimo_relativo: float = 0.25,
    incremento_minimo_mb: float = 1.0,
    consecutivi_minimi: int = 3,
    campioni_baseline_minimi: int = 8,
    massimo_gap_factor: float = 1.5,
) -> dict[str, Any]:
    """Valuta un'ipotesi di attivita' I/O di lettura elevata per un container.

    ``incremento_minimo_mb`` e le altre soglie sono euristiche *provvisorie*
    definite indipendentemente dalle etichette. Valori per campione, NON tassi.
    Una baseline tutta zero e' ammessa (container inattivo): non forza astensione.
    """
    if not isinstance(telemetria, pd.DataFrame):
        raise TypeError("telemetria deve essere un DataFrame")
    if not REQUIRED_COLUMNS.issubset(telemetria.columns):
        raise ValueError(f"Colonne necessarie: {sorted(REQUIRED_COLUMNS)}")
    if not isinstance(componente, str) or not componente.strip():
        raise ValueError("Componente non valido")
    if not (start_unix < baseline_end_unix < end_unix):
        raise ValueError("Intervallo temporale non valido")
    if any(not math.isfinite(float(v)) or float(v) <= 0 for v in (
        soglia_robusta, incremento_minimo_relativo, incremento_minimo_mb,
        massimo_gap_factor,
    )):
        raise ValueError("Soglie o fattori non validi")
    if consecutivi_minimi < 2 or campioni_baseline_minimi < 3 or massimo_gap_factor < 1:
        raise ValueError("Parametri campionamento non validi")

    esito: dict[str, Any] = {
        "rule_id": "R06",
        "classe_candidata": "container read I/O load",
        "componente_telemetria": componente,
        "status": "evidenza_insufficiente",
        "finestra": {
            "start_unix": int(start_unix),
            "baseline_end_unix": int(baseline_end_unix),
            "end_unix": int(end_unix),
        },
        "ipotesi": None,
        "evidenze": {},
        "limitazioni": [
            "La baseline puo' contenere gia' un guasto.",
            "La metrica reads_MB e' interpretata come livello osservato, non "
            "come contatore cumulativo o throughput verificato.",
            "Soglie esplorative, non calibrate su ground truth.",
            "Attivita' I/O di lettura non dimostra da sola la root cause; "
            "possibile effetto di carico applicativo o sintomo correlato.",
        ],
    }

    t = pd.to_numeric(telemetria["timestamp"], errors="coerce")
    scope = telemetria.loc[
        telemetria["cmdb_id"].eq(componente)
        & t.ge(start_unix)
        & t.lt(end_unix)
    ]
    serie = _serie(scope, READ_MB)
    base = serie.loc[(serie.index >= start_unix) & (serie.index < baseline_end_unix)]
    ricerca = serie.loc[(serie.index >= baseline_end_unix) & (serie.index < end_unix)]

    e = esito["evidenze"]
    e["campioni_baseline_reads_mb"] = int(len(base))
    e["campioni_ricerca_reads_mb"] = int(len(ricerca))
    if len(base) < campioni_baseline_minimi or len(ricerca) < consecutivi_minimi:
        esito["limitazioni"].append("Campioni reads_MB insufficienti.")
        return esito
    if (base < 0).any() or (ricerca < 0).any():
        esito["limitazioni"].append("Valori reads_MB negativi: semantica non verificata.")
        return esito

    mediana = float(base.median())
    mad = float((base - mediana).abs().median())
    e["baseline_mediana_reads_mb"] = mediana
    e["baseline_mad_reads_mb"] = mad
    # La baseline tutta zero e' valida; serve una soglia minima non nulla.
    soglia = max(
        mediana + soglia_robusta * 1.4826 * mad,
        mediana * (1.0 + incremento_minimo_relativo),
        mediana + incremento_minimo_mb,
    )
    e["soglia_reads_mb_esplorativa"] = float(soglia)
    e["campioni_reads_mb_oltre_soglia"] = int((ricerca > soglia).sum())

    intervalli = serie.index.to_series().diff().dropna()
    intervalli = intervalli.loc[intervalli > 0]
    if intervalli.empty:
        esito["limitazioni"].append("Cadenza del campionamento non valutabile.")
        return esito
    cadenza = float(intervalli.median())
    e["cadenza_mediana_secondi"] = cadenza
    max_gap = cadenza * massimo_gap_factor

    streak_start = None
    streak_last = None
    streak_count = 0
    candidato = None
    for timestamp, valore in ricerca.items():
        ts = float(timestamp)
        if valore > soglia:
            if streak_last is None or ts - streak_last > max_gap:
                streak_start, streak_count = ts, 1
            else:
                streak_count += 1
            streak_last = ts
            if streak_count >= consecutivi_minimi:
                candidato = (streak_start, ts, streak_count)
                break
        else:
            streak_start, streak_last, streak_count = None, None, 0

    if candidato is None:
        esito["status"] = "nessun_candidato"
        return esito

    t0, t1, n = candidato
    esito["status"] = "candidato_da_verificare"
    esito["ipotesi"] = {
        "classe": "container read I/O load",
        "timestamp_primo_segnale_unix": int(t0),
        "timestamp_ultimo_segnale_unix": int(t1),
        "campioni_consecutivi": int(n),
    }
    evento = ricerca.loc[(ricerca.index >= t0) & (ricerca.index <= t1)]
    e["massimo_reads_mb_evento"] = float(evento.max())
    e["massimo_reads_mb_ricerca"] = float(ricerca.max())

    # La metrica reads./dev/vda e' solo corroborazione descrittiva.
    # Non deduciamo read/s ne' convertiamo gli aggregati in contatori.
    ops = _serie(scope, READ_OPS)
    ops_evento = ops.loc[(ops.index >= t0) & (ops.index <= t1)]
    e["operazioni_lettura_accessorie"] = {
        "campioni_evento": int(len(ops_evento)),
        "campioni_positivi": int((ops_evento > 0).sum()),
        "massimo_osservato": float(ops_evento.max()) if len(ops_evento) else None,
    }
    if ops_evento.empty:
        esito["limitazioni"].append("Nessuna metrica reads per corroborazione.")
    elif not (ops_evento > 0).any():
        esito["limitazioni"].append(
            "Nessun valore positivo nella metrica reads di corroborazione."
        )
    return esito
